from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.health import get_readiness_status


class HealthEndpointTests(TestCase):
    def test_healthz_returns_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_readyz_returns_ok_when_dependencies_are_healthy(self):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["checks"]["database"]["status"], "ok")
        self.assertEqual(response.json()["checks"]["migrations"]["status"], "ok")


class ReadinessStatusTests(SimpleTestCase):
    @patch("core.health.check_migrations")
    @patch("core.health.check_database")
    def test_readiness_status_reports_error_when_dependency_fails(
        self,
        mock_check_database,
        mock_check_migrations,
    ):
        mock_check_database.return_value = {"status": "ok"}
        mock_check_migrations.return_value = {
            "status": "out_of_date",
            "pending_migrations": ["tasks.0003_example"],
        }

        payload = get_readiness_status()

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        self.assertEqual(payload["checks"]["migrations"]["status"], "out_of_date")
        self.assertEqual(
            payload["checks"]["migrations"]["pending_migrations"],
            ["tasks.0003_example"],
        )
