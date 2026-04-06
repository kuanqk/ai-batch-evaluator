"""DRF URL patterns (prefixed /api/)."""

from django.urls import path

from . import api

urlpatterns = [
    path("health/", api.health, name="api-health"),
    path("batch/upload/", api.upload_batch, name="api-batch-upload"),
    path("batch/<int:job_id>/", api.get_job, name="api-batch-detail"),
    path("batch/<int:job_id>/retry-failed/", api.retry_failed, name="api-batch-retry-failed"),
    path("batch/<int:job_id>/pause/", api.pause_job, name="api-batch-pause"),
    path("batch/<int:job_id>/resume/", api.resume_job, name="api-batch-resume"),
    path("evaluations/", api.list_evaluations, name="api-evaluations-list"),
    path("evaluations/<int:eval_id>/", api.get_evaluation, name="api-evaluation-detail"),
    path("evaluations/<int:eval_id>/retry/", api.retry_evaluation, name="api-evaluation-retry"),
    path("evaluate/", api.evaluate_single, name="api-evaluate-single"),
    path("stats/", api.stats, name="api-stats"),
]
