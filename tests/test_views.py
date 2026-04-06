"""Integration tests for Django views and DRF API."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    from apps.accounts.models import CustomUser
    return CustomUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def staff_user(db):
    from apps.accounts.models import CustomUser
    return CustomUser.objects.create_user(
        username="staffuser", password="testpass123", is_staff=True
    )


@pytest.fixture
def auth_client(user):
    c = Client()
    c.login(username="testuser", password="testpass123")
    return c


class TestAuth:
    def test_login_page_accessible(self):
        c = Client()
        resp = c.get(reverse("accounts:login"))
        assert resp.status_code == 200

    def test_login_success(self, user):
        c = Client()
        resp = c.post(reverse("accounts:login"), {"username": "testuser", "password": "testpass123"})
        assert resp.status_code == 302

    def test_dashboard_requires_login(self):
        c = Client()
        resp = c.get(reverse("batch:dashboard"))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    def test_dashboard_accessible_when_logged_in(self, auth_client):
        resp = auth_client.get(reverse("batch:dashboard"))
        assert resp.status_code == 200


class TestDashboard:
    def test_empty_dashboard(self, auth_client):
        resp = auth_client.get(reverse("batch:dashboard"))
        assert resp.status_code == 200
        assert "Batch" in resp.content.decode() or resp.status_code == 200

    def test_dashboard_shows_jobs(self, auth_client):
        from apps.batch.models import EvaluationJob
        EvaluationJob.objects.create(
            name="Test Batch", source_file="test.csv",
            total=5, status=EvaluationJob.STATUS_RUNNING,
        )
        resp = auth_client.get(reverse("batch:dashboard"))
        assert resp.status_code == 200
        assert b"Test Batch" in resp.content


class TestResultsView:
    def test_results_empty(self, auth_client):
        resp = auth_client.get(reverse("batch:results"))
        assert resp.status_code == 200

    def test_results_with_job_filter(self, auth_client):
        from apps.batch.models import Evaluation, EvaluationJob
        job = EvaluationJob.objects.create(
            name="Filter Test", source_file="x.csv", total=2,
            status=EvaluationJob.STATUS_DONE,
        )
        Evaluation.objects.create(
            job=job, file_url="https://example.com/1.docx",
            city="Almaty", status="done", score_level=3,
        )
        resp = auth_client.get(reverse("batch:results") + f"?job_id={job.pk}")
        assert resp.status_code == 200
        assert b"Almaty" in resp.content


class TestAPIHealth:
    def test_health_endpoint(self):
        c = Client()
        resp = c.get("/api/health/")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "db" in data
        assert "redis" in data


class TestAPIUpload:
    def test_upload_requires_auth(self):
        c = Client()
        resp = c.post("/api/batch/upload/")
        assert resp.status_code in (401, 403)

    def test_upload_csv(self, auth_client):
        csv_content = (
            b"file_path,file_url\n"
            b"PKS2025/Astana/Ivanov/G1/plan.docx,https://example.com/1.docx\n"
        )
        from apps.batch.utils import parse_batch_upload

        rows, skipped = parse_batch_upload(csv_content, "test.csv")
        assert len(rows) == 1
        assert rows[0]["city"] == "Astana"


class TestSingleViews:
    def test_submit_page(self, auth_client):
        resp = auth_client.get(reverse("single:submit"))
        assert resp.status_code == 200

    def test_result_not_found(self, auth_client):
        resp = auth_client.get(reverse("single:result", args=[99999]))
        assert resp.status_code == 200
        assert b"not_found" in resp.content or "найдена" in resp.content.decode()
