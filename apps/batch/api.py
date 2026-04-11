"""DRF API: batch upload, job management, evaluation results, stats."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Evaluation, EvaluationJob
from .serializers import EvaluationJobSerializer, EvaluationSerializer
from .utils import parse_batch_upload


def _check_api_key(request: Request) -> bool:
    """Allow if EVALUATOR_API_KEY not configured, else require X-API-Key header."""
    key = getattr(settings, "EVALUATOR_API_KEY", "")
    if not key:
        return True
    return request.META.get("HTTP_X_API_KEY") == key


# ─── Batch upload ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_batch(request: Request) -> Response:
    if not _check_api_key(request):
        return Response({"detail": "Invalid or missing X-API-Key"}, status=status.HTTP_401_UNAUTHORIZED)

    file_obj = request.FILES.get("file")
    if not file_obj:
        return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

    content = file_obj.read()
    if not content:
        return Response({"detail": "Empty file"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        rows, skipped = parse_batch_upload(content, file_obj.name)
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if not rows:
        return Response({"detail": "No valid rows (file_url required)"}, status=status.HTTP_400_BAD_REQUEST)

    name = request.data.get("name") or file_obj.name
    webhook_url = request.data.get("webhook_url") or None

    job = EvaluationJob.objects.create(
        name=name,
        source_file=file_obj.name,
        total=len(rows),
        status=EvaluationJob.STATUS_RUNNING,
        webhook_url=webhook_url,
        created_by=request.user,
    )

    evals = [
        Evaluation(
            job=job,
            evaluator_config_id=job.evaluator_config_id,
            file_path=r.get("file_path"),
            file_url=r["file_url"],
            city=r.get("city"),
            trainer=r.get("trainer"),
            group_name=r.get("group_name"),
            file_name=r.get("file_name"),
        )
        for r in rows
    ]
    created = Evaluation.objects.bulk_create(evals)

    from tasks.evaluate import process_job
    process_job.delay(job.pk)

    return Response(
        {
            "job_id": job.pk,
            "name": job.name,
            "total": len(rows),
            "skipped_rows": skipped,
            "status": "running",
            "message": f"Батч принят. {len(rows)} файлов поставлено в очередь.",
        },
        status=status.HTTP_202_ACCEPTED,
    )


# ─── Job management ───────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_job(request: Request, job_id: int) -> Response:
    try:
        job = EvaluationJob.objects.get(pk=job_id)
    except EvaluationJob.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    agg = job.evaluations.filter(status="done").aggregate(avg_pct=Avg("score_percentage"))
    level_dist = dict(
        job.evaluations.filter(status="done", score_level__isnull=False)
        .values("score_level")
        .annotate(cnt=Count("id"))
        .values_list("score_level", "cnt")
    )
    for i in range(1, 5):
        level_dist.setdefault(i, 0)

    return Response(
        {
            "id": job.pk,
            "name": job.name,
            "status": job.status,
            "total": job.total,
            "processed": job.processed,
            "failed": job.failed,
            "paused": job.paused,
            "progress_percent": job.progress_percent,
            "avg_score_percentage": round(agg["avg_pct"] or 0, 1),
            "level_distribution": level_dist,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_failed(request: Request, job_id: int) -> Response:
    if not _check_api_key(request):
        return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        job = EvaluationJob.objects.get(pk=job_id)
    except EvaluationJob.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    ids = list(job.evaluations.filter(status="failed").values_list("id", flat=True))
    Evaluation.objects.filter(id__in=ids).update(
        status="pending", error=None, current_step=0,
        started_at=None, processed_at=None,
    )
    EvaluationJob.objects.filter(pk=job_id).update(
        failed=F("failed") - len(ids),
        status=EvaluationJob.STATUS_RUNNING,
    )

    from tasks.evaluate import process_file
    for eid in ids:
        process_file.delay(eid)

    return Response({"job_id": job_id, "requeued": len(ids)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pause_job(request: Request, job_id: int) -> Response:
    EvaluationJob.objects.filter(pk=job_id).update(paused=True)
    return Response({"job_id": job_id, "status": "paused"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_job(request: Request, job_id: int) -> Response:
    EvaluationJob.objects.filter(pk=job_id).update(paused=False)
    return Response({"job_id": job_id, "status": "running"})


# ─── Evaluations ──────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_evaluations(request: Request) -> Response:
    qs = Evaluation.objects.select_related("job").order_by("-created_at")
    job_id = request.query_params.get("job_id")
    if job_id:
        qs = qs.filter(job_id=job_id)
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    city = request.query_params.get("city")
    if city:
        qs = qs.filter(city__icontains=city)
    level = request.query_params.get("level")
    if level:
        qs = qs.filter(score_level=level)

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    offset = (page - 1) * page_size
    total_count = qs.count()
    items = EvaluationSerializer(qs[offset: offset + page_size], many=True).data

    return Response({"count": total_count, "page": page, "results": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_evaluation(request: Request, eval_id: int) -> Response:
    try:
        ev = Evaluation.objects.get(pk=eval_id)
    except Evaluation.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(EvaluationSerializer(ev).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_evaluation(request: Request, eval_id: int) -> Response:
    updated = Evaluation.objects.filter(pk=eval_id, status__in=["failed", "pending"]).update(
        status="pending", error=None, current_step=0, started_at=None, processed_at=None,
    )
    if not updated:
        return Response({"detail": "Not found or not retryable"}, status=status.HTTP_404_NOT_FOUND)
    from tasks.evaluate import process_file
    process_file.delay(eval_id)
    return Response({"eval_id": eval_id, "status": "requeued"})


# ─── Single evaluation (Beles-style) ─────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evaluate_single(request: Request) -> Response:
    if not _check_api_key(request):
        return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    material_id = request.data.get("material_id")
    file_url = request.data.get("file_url")
    if not file_url:
        return Response({"detail": "file_url required"}, status=status.HTTP_400_BAD_REQUEST)

    job = EvaluationJob.objects.create(
        name=f"single:{material_id}",
        source_file="single",
        total=1,
        status=EvaluationJob.STATUS_RUNNING,
    )
    ev = Evaluation.objects.create(
        job=job,
        file_url=file_url,
        material_id=material_id,
    )
    from tasks.evaluate import process_file
    process_file.delay(ev.pk)

    return Response(
        {"material_id": material_id, "eval_id": ev.pk, "status": "accepted"},
        status=status.HTTP_202_ACCEPTED,
    )


# ─── Stats ────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stats(request: Request) -> Response:
    from django.db.models import Count

    total_jobs = EvaluationJob.objects.count()
    total_evals = Evaluation.objects.count()
    done_evals = Evaluation.objects.filter(status="done").count()
    failed_evals = Evaluation.objects.filter(status="failed").count()
    avg_pct = Evaluation.objects.filter(status="done").aggregate(a=Avg("score_percentage"))["a"] or 0

    level_dist = dict(
        Evaluation.objects.filter(status="done", score_level__isnull=False)
        .values("score_level")
        .annotate(cnt=Count("id"))
        .values_list("score_level", "cnt")
    )

    return Response(
        {
            "total_jobs": total_jobs,
            "total_evaluations": total_evals,
            "done": done_evals,
            "failed": failed_evals,
            "avg_score_percentage": round(avg_pct, 1),
            "level_distribution": level_dist,
        }
    )


# ─── Health ───────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([])
def health(request: Request) -> Response:
    db_ok = False
    redis_ok = False

    try:
        from django.db import connection
        connection.ensure_connection()
        db_ok = True
    except Exception:
        pass

    try:
        import redis as redis_lib
        from django.conf import settings as dj_settings
        r = redis_lib.from_url(dj_settings.CELERY_BROKER_URL)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    overall = "healthy" if (db_ok and redis_ok) else ("degraded" if (db_ok or redis_ok) else "unhealthy")
    return Response(
        {"status": overall, "db": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"},
        status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
