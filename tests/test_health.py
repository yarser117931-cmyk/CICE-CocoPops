import unittest

from fastapi.testclient import TestClient

from app.main import app


class TestHealth(unittest.TestCase):
    def test_health_does_not_expose_secret(self):
        with TestClient(app) as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "1.0.0")
        self.assertNotIn("odoo_api_key", payload)


if __name__ == "__main__":
    unittest.main()
