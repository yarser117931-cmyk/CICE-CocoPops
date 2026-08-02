import unittest

from app.services.history import trends


class TestHistory(unittest.TestCase):
    def test_safe_without_database(self):
        result = trends(30)
        self.assertIn("enabled", result)
        self.assertIn("points", result)
        self.assertIn("summary", result)


if __name__ == "__main__":
    unittest.main()
