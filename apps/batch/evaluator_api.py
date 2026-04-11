"""Per-config API: /api/ev/<slug>/… (X-API-Key per EvaluatorConfig)."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evaluators.models import EvaluatorConfig
from apps.batch.models import Evaluation, EvaluationJob
from apps.batch.utils import parse_batch_upload
from django.conf import settings


class ConfigAPIKeyPermission(BasePermission):
    """Require X-API-Key to match EvaluatorConfig.api_key for this slug."""

    def has_permission(self, request: Request, view) -> bool:
        slug = view.kwargs.get("slug")
        if not slug:
            return False
        try:
            cfg = EvaluatorConfig.objects.get(slug=slug, is_active=True)
        except EvaluatorConfig.DoesNotExist:
            raise Http404("Unknown or inactive config slug")
        if not (cfg.api_key or "").strip():
            return False
        key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
        return key == cfg.api_key


class ConfigEvaluateView(APIView):
    """POST { material_id?, file_url } — queue single evaluation for this config."""

    permission_classes = [ConfigAPIKeyPermission]
    authentication_classes: list = []

    def post(self, request: Request, slug: str) -> Response:
        cfg = get_object_or_404(EvaluatorConfig, slug=slug, is_active=True)
        file_url = request.data.get("file_url")
        if not file_url:
            return Response({"detail": "file_url required"}, status=status.HTTP_400_BAD_REQUEST)

        material_id = request.data.get("material_id")

        job = EvaluationJob.objects.create(
            name=f"single:{material_id or 'none'}",
            source_file="single",
            total=1,
            status=EvaluationJob.STATUS_RUNNING,
            evaluator_config=cfg,
        )
        ev = Evaluation.objects.create(
            job=job,
            evaluator_config=cfg,
            file_url=file_url,
            material_id=material_id,
        )
        from tasks.evaluate import process_file

        process_file.delay(ev.pk)

        return Response(
            {
                "material_id": material_id,
                "eval_id": ev.pk,
                "status": "accepted",
                "message": "File accepted for evaluation",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ConfigBatchUploadView(APIView):
    """POST multipart file — same columns as /api/batch/upload/, scoped to config."""

    permission_classes = [ConfigAPIKeyPermission]
    authentication_classes: list = []

    def post(self, request: Request, slug: str) -> Response:
        cfg = get_object_or_404(EvaluatorConfig, slug=slug, is_active=True)
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
            evaluator_config=cfg,
            created_by=None,
        )
        Evaluation.objects.bulk_create(
            [
                Evaluation(
                    job=job,
                    evaluator_config=cfg,
                    file_path=r.get("file_path"),
                    file_url=r["file_url"],
                    city=r.get("city"),
                    trainer=r.get("trainer"),
                    group_name=r.get("group_name"),
                    file_name=r.get("file_name"),
                )
                for r in rows
            ]
        )

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


class ConfigHealthView(APIView):
    """Lightweight health for this slug (config must exist and be active)."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request, slug: str) -> Response:
        get_object_or_404(EvaluatorConfig, slug=slug, is_active=True)
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

            r = redis_lib.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            redis_ok = True
        except Exception:
            pass
        overall = "healthy" if (db_ok and redis_ok) else ("degraded" if (db_ok or redis_ok) else "unhealthy")
        return Response(
            {
                "slug": slug,
                "status": overall,
                "db": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
            status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ConfigStatsView(APIView):
    """Basic stats + config limits (global semaphores are process-wide)."""

    permission_classes = [ConfigAPIKeyPermission]
    authentication_classes: list = []

    def get(self, request: Request, slug: str) -> Response:
        cfg = get_object_or_404(EvaluatorConfig, slug=slug, is_active=True)
        return Response(
            {
                "slug": cfg.slug,
                "name": cfg.name,
                "evaluation_slots": cfg.evaluation_slots,
                "llm_model": cfg.llm_model,
                "vision_model": cfg.vision_model,
                "global": {
                    "nitec_max_workers": settings.NITEC_MAX_WORKERS,
                    "max_concurrent_downloads": settings.MAX_CONCURRENT_DOWNLOADS,
                    "max_concurrent_vision": settings.MAX_CONCURRENT_VISION,
                },
            }
        )
