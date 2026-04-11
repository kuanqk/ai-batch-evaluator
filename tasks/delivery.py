"""Push evaluation results to Beles or webhook per EvaluatorConfig."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from apps.evaluators.models import EvaluatorConfig
from apps.batch.models import Evaluation

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


def _beles_target_url(cfg: EvaluatorConfig, material_id: int | None) -> str | None:
    if not cfg.beles_base_url or material_id is None:
        return None
    tpl = (cfg.beles_endpoint_tpl or "/postcourse/materials/{id}/ai-analysis/").strip()
    path = tpl.replace("{id}", str(material_id))
    if not path.startswith("/"):
        path = "/" + path
    return cfg.beles_base_url.rstrip("/") + path


def _payload_for_external(ev: Evaluation) -> dict[str, Any]:
    return {
        "eval_id": ev.pk,
        "material_id": ev.material_id,
        "status": ev.status,
        "llm_result": ev.llm_result,
        "scores": ev.scores,
        "total_score": ev.total_score,
        "score_percentage": ev.score_percentage,
        "score_level": ev.score_level,
        "feedback": ev.feedback,
        "teacher_name": ev.teacher_name,
        "topic": ev.topic,
        "report_path": ev.report_path,
    }


def _request_with_retries(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any],
    attempts: int,
) -> None:
    last_err: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                r = client.request(method.upper(), url, headers=headers, json=json_body)
                r.raise_for_status()
            logger.info("Delivery OK %s %s (attempt %s)", method, url, attempt + 1)
            return
        except Exception as e:
            last_err = e
            logger.warning(
                "Delivery attempt %s/%s failed: %s",
                attempt + 1,
                attempts,
                e,
            )
            if attempt < attempts - 1:
                time.sleep(min(2**attempt, 30))
    if last_err:
        logger.error("Delivery failed after %s attempts: %s", attempts, last_err)


def deliver_evaluation_outcome(eval_id: int) -> None:
    """
    Send result to Beles or per-config webhook when EvaluatorConfig requests it.
    Failures are logged; evaluation row stays DONE.
    """
    try:
        ev = Evaluation.objects.select_related("evaluator_config").get(pk=eval_id)
    except Evaluation.DoesNotExist:
        return

    cfg = ev.evaluator_config
    if not cfg:
        return
    if cfg.delivery_type == EvaluatorConfig.DELIVERY_DB_ONLY:
        return

    attempts = int(cfg.retry_attempts) if cfg.enable_retry else 1

    body = _payload_for_external(ev)

    if cfg.delivery_type == EvaluatorConfig.DELIVERY_WEBHOOK:
        url = (cfg.webhook_url or "").strip()
        if not url:
            logger.warning("[eval=%s] webhook delivery skipped: empty webhook_url", eval_id)
            return
        headers = {"Content-Type": "application/json"}
        _request_with_retries("POST", url, headers=headers, json_body=body, attempts=attempts)
        return

    if cfg.delivery_type == EvaluatorConfig.DELIVERY_BELES:
        url = _beles_target_url(cfg, ev.material_id)
        if not url:
            logger.warning(
                "[eval=%s] Beles delivery skipped: missing base_url or material_id",
                eval_id,
            )
            return
        if not (cfg.beles_api_key or "").strip():
            logger.warning("[eval=%s] Beles delivery skipped: empty beles_api_key", eval_id)
            return
        method = (cfg.beles_http_method or "PATCH").strip().upper()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.beles_api_key.strip()}",
        }
        _request_with_retries(method, url, headers=headers, json_body=body, attempts=attempts)
        return
