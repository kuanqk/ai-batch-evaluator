"""Tests for /api/ev/<slug>/… per-config API."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def ev_config():
    from apps.evaluators.models import EvaluatorConfig

    return EvaluatorConfig.objects.create(
        name="API Test",
        slug="api-test",
        api_key="correct-secret-key",
        is_active=True,
        delivery_type=EvaluatorConfig.DELIVERY_DB_ONLY,
    )


class TestConfigEvaluate:
    @patch("tasks.evaluate.process_file.delay")
    def test_evaluate_202_with_valid_key(self, mock_delay, api_client, ev_config):
        url = reverse("api-ev-evaluate", kwargs={"slug": ev_config.slug})
        resp = api_client.post(
            url,
            {"file_url": "https://example.com/doc.docx", "material_id": 1},
            format="json",
            HTTP_X_API_KEY="correct-secret-key",
        )
        assert resp.status_code == 202
        assert resp.data["status"] == "accepted"
        mock_delay.assert_called_once()

    def test_evaluate_403_without_key(self, api_client, ev_config):
        url = reverse("api-ev-evaluate", kwargs={"slug": ev_config.slug})
        resp = api_client.post(
            url,
            {"file_url": "https://example.com/doc.docx"},
            format="json",
        )
        assert resp.status_code == 403

    def test_evaluate_403_wrong_key(self, api_client, ev_config):
        url = reverse("api-ev-evaluate", kwargs={"slug": ev_config.slug})
        resp = api_client.post(
            url,
            {"file_url": "https://example.com/doc.docx"},
            format="json",
            HTTP_X_API_KEY="wrong",
        )
        assert resp.status_code == 403

    def test_evaluate_400_no_file_url(self, api_client, ev_config):
        url = reverse("api-ev-evaluate", kwargs={"slug": ev_config.slug})
        resp = api_client.post(
            url,
            {},
            format="json",
            HTTP_X_API_KEY="correct-secret-key",
        )
        assert resp.status_code == 400


class TestConfigHealth:
    def test_health_200(self, api_client, ev_config):
        url = reverse("api-ev-health", kwargs={"slug": ev_config.slug})
        resp = api_client.get(url)
        assert resp.status_code in (200, 503)
        assert resp.data["slug"] == ev_config.slug


class TestConfigAPIKeyPermission:
    def test_stats_requires_key(self, api_client, ev_config):
        url = reverse("api-ev-stats", kwargs={"slug": ev_config.slug})
        assert api_client.get(url).status_code == 403
        r = api_client.get(url, HTTP_X_API_KEY="correct-secret-key")
        assert r.status_code == 200
        assert r.data["slug"] == ev_config.slug
