"""Celery tasks: batch fan-out and per-file evaluation.

Pattern: Django ORM (sync) wraps asyncio.run(pipeline) for I/O.
All DB reads/writes happen outside asyncio.run() to avoid ORM/event-loop issues.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.batch.models import Evaluation, EvaluationJob
from config.celery import celery_app
from pipeline.llm import extract_scores
from pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)


class JobPaused(Exception):
    """Raised when job is paused — Celery retries later."""


_INTERNAL_RESULT_KEYS = {
    "usage", "llm_raw", "text_preview", "meta", "download_filename",
    "normalized_filename", "extraction_method", "doc_lang",
    "scores", "total_score", "score_level", "rubric_preview",
    "used_fix_docx", "used_vision_ocr", "was_empty_doc",
}


def _pick_llm_payload(result: dict[str, Any]) -> dict[str, Any]:
    if "llm_result" in result:
        return result["llm_result"]
    return {k: v for k, v in result.items() if k not in _INTERNAL_RESULT_KEYS}


def _feedback_from_parsed(parsed: dict[str, Any]) -> str:
    br = parsed.get("brief_report_json") or {}
    overall = br.get("overall_recommendation")
    return overall if isinstance(overall, str) else ""


def _write_report_file(eval_id: int, payload: dict[str, Any]) -> str:
    base = Path(settings.REPORTS_DIR)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{eval_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def _try_finalize_job(job_id: int) -> bool:
    """Atomically set job status to 'done' when all items processed. Returns True if finalized."""
    from django.db import transaction

    with transaction.atomic():
        try:
            job = EvaluationJob.objects.select_for_update().get(pk=job_id)
        except EvaluationJob.DoesNotExist:
            return False
        if job.status in (EvaluationJob.STATUS_DONE, EvaluationJob.STATUS_FAILED):
            return False
        if job.total <= 0:
            return False
        if job.processed + job.failed < job.total:
            return False
        EvaluationJob.objects.filter(pk=job_id).update(status=EvaluationJob.STATUS_DONE)
    return True


def _notify_webhook_sync(job_id: int) -> None:
    try:
        job = EvaluationJob.objects.get(pk=job_id)
    except EvaluationJob.DoesNotExist:
        return
    if not job.webhook_url:
        return
    from django.db.models import Avg
    avg = job.evaluations.filter(status="done").aggregate(a=Avg("score_percentage"))["a"] or 0
    payload = {
        "job_id": job_id,
        "status": job.status,
        "total": job.total,
        "processed": job.processed,
        "failed": job.failed,
        "avg_score": round(avg, 1),
    }
    try:
        import httpx as _httpx
        _httpx.post(job.webhook_url, json=payload, timeout=10.0)
    except Exception:
        logger.exception("[job=%s] webhook notification failed", job_id)


# ─── Main per-file task ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=288,
    default_retry_delay=15,
    name="tasks.evaluate.process_file",
)
def process_file(self, eval_id: int) -> None:  # noqa: C901
    # 1. Read evaluation
    try:
        ev = Evaluation.objects.select_related("job").get(pk=eval_id)
    except Evaluation.DoesNotExist:
        logger.warning("[eval=%s] not found, skipping", eval_id)
        return

    if ev.status == Evaluation.STATUS_DONE:
        return

    # 2. Check pause
    if ev.job_id:
        if EvaluationJob.objects.filter(pk=ev.job_id, paused=True).exists():
            raise self.retry(exc=JobPaused())

    # 3. Atomic claim
    claimed = Evaluation.objects.filter(pk=eval_id, status=Evaluation.STATUS_PENDING).update(
        status=Evaluation.STATUS_PROCESSING,
        current_step=1,
        started_at=timezone.now(),
    )
    if not claimed:
        logger.debug("[eval=%s] skip — already claimed or done", eval_id)
        return

    file_url = ev.file_url
    file_path = ev.file_path

    # 4. Run async pipeline (pure I/O, no ORM inside)
    try:
        from config.concurrency import init_concurrency
        init_concurrency()
        result = asyncio.run(run_pipeline(file_url, file_path, extract_only=False))
    except Exception as e:
        err = f"{e}\n{traceback.format_exc()}"
        logger.error("[eval=%s] pipeline error: %s", eval_id, err[:500])
        Evaluation.objects.filter(pk=eval_id).update(
            status=Evaluation.STATUS_FAILED,
            error=err[:10000],
            current_step=0,
            processed_at=timezone.now(),
        )
        if ev.job_id:
            EvaluationJob.objects.filter(pk=ev.job_id).update(failed=F("failed") + 1)
            if _try_finalize_job(ev.job_id):
                _notify_webhook_sync(ev.job_id)
        return

    # 5. Extract results
    parsed = _pick_llm_payload(result)
    scores, total_score, score_level = extract_scores(parsed)
    if result.get("scores") is not None:
        scores = result["scores"]
    if result.get("total_score") is not None:
        total_score = float(result["total_score"])
    if result.get("score_level") is not None:
        score_level = int(result["score_level"])

    pct = (float(total_score) / 75.0) * 100.0 if total_score is not None else 0.0
    usage = result.get("usage") or {}

    report_path = _write_report_file(eval_id, {"pipeline": result, "parsed": parsed})

    # 6. Save success
    Evaluation.objects.filter(pk=eval_id).update(
        status=Evaluation.STATUS_DONE,
        scores=scores,
        total_score=float(total_score),
        score_percentage=round(pct, 2),
        score_level=int(score_level),
        feedback=_feedback_from_parsed(parsed) or None,
        teacher_name=parsed.get("teacher_name") or None,
        topic=parsed.get("topic") or None,
        llm_result=parsed,
        report_path=report_path,
        extraction_method=result.get("extraction_method"),
        doc_lang=result.get("doc_lang"),
        file_size_bytes=result.get("file_size_bytes"),
        doc_chars=result.get("doc_chars"),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        used_vision_ocr=bool(result.get("used_vision_ocr")),
        used_fix_docx=bool(result.get("used_fix_docx")),
        was_empty_doc=bool(result.get("was_empty_doc")),
        current_step=8,
        processed_at=timezone.now(),
        error=None,
    )

    logger.info(
        "[eval=%s] done — level=%s pct=%.1f%%",
        eval_id, score_level, pct,
    )

    if ev.job_id:
        EvaluationJob.objects.filter(pk=ev.job_id).update(processed=F("processed") + 1)
        if _try_finalize_job(ev.job_id):
            _notify_webhook_sync(ev.job_id)


# ─── Job fan-out ──────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.evaluate.process_job")
def process_job(job_id: int) -> None:
    ids = list(
        Evaluation.objects.filter(job_id=job_id, status=Evaluation.STATUS_PENDING)
        .values_list("id", flat=True)
        .order_by("id")
    )
    for eid in ids:
        process_file.delay(eid)
    logger.info("[job=%s] queued %s evaluations", job_id, len(ids))


@celery_app.task(name="tasks.evaluate.ping")
def ping() -> str:
    return "ok"
