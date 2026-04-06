"""Tests for Django ORM models."""

import pytest
from django.db.models import F

pytestmark = pytest.mark.django_db


class TestEvaluationJob:
    def test_create_job(self):
        from apps.batch.models import EvaluationJob

        job = EvaluationJob.objects.create(
            name="Test Job",
            source_file="test.csv",
            total=10,
            status=EvaluationJob.STATUS_RUNNING,
        )
        assert job.pk is not None
        assert job.progress_percent == 0.0
        assert job.paused is False

    def test_progress_percent(self):
        from apps.batch.models import EvaluationJob

        job = EvaluationJob.objects.create(
            name="Progress Test",
            source_file="test.csv",
            total=10,
            processed=7,
            failed=1,
            status=EvaluationJob.STATUS_RUNNING,
        )
        assert job.progress_percent == 80.0

    def test_progress_zero_total(self):
        from apps.batch.models import EvaluationJob

        job = EvaluationJob(total=0, processed=0, failed=0)
        assert job.progress_percent == 0.0

    def test_atomic_increment(self):
        from apps.batch.models import EvaluationJob

        job = EvaluationJob.objects.create(
            name="Atomic",
            source_file="x.csv",
            total=5,
            status=EvaluationJob.STATUS_RUNNING,
        )
        EvaluationJob.objects.filter(pk=job.pk).update(processed=F("processed") + 1)
        EvaluationJob.objects.filter(pk=job.pk).update(processed=F("processed") + 1)
        job.refresh_from_db()
        assert job.processed == 2


class TestEvaluation:
    def test_create_evaluation(self):
        from apps.batch.models import Evaluation, EvaluationJob

        job = EvaluationJob.objects.create(
            name="Eval Test", source_file="x.csv", total=1,
            status=EvaluationJob.STATUS_RUNNING,
        )
        ev = Evaluation.objects.create(job=job, file_url="https://example.com/doc.docx")
        assert ev.pk is not None
        assert ev.status == Evaluation.STATUS_PENDING
        assert ev.current_step == 0

    def test_claim_evaluation(self):
        from apps.batch.models import Evaluation, EvaluationJob
        from django.utils import timezone

        job = EvaluationJob.objects.create(
            name="Claim Test", source_file="x.csv", total=1,
            status=EvaluationJob.STATUS_RUNNING,
        )
        ev = Evaluation.objects.create(job=job, file_url="https://example.com/test.pdf")

        # First claim succeeds
        claimed = Evaluation.objects.filter(pk=ev.pk, status="pending").update(
            status="processing", current_step=1, started_at=timezone.now(),
        )
        assert claimed == 1

        # Second claim fails (already processing)
        claimed2 = Evaluation.objects.filter(pk=ev.pk, status="pending").update(
            status="processing",
        )
        assert claimed2 == 0

    def test_evaluation_without_job(self):
        from apps.batch.models import Evaluation

        ev = Evaluation.objects.create(file_url="https://example.com/single.docx")
        assert ev.job is None
        assert ev.status == Evaluation.STATUS_PENDING
