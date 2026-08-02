import unittest
from datetime import datetime
from zoneinfo import ZoneInfo


class TestBusinessDayTimezone(unittest.TestCase):
    def test_chihuahua_day_converts_to_utc(self):
        local = datetime(2026, 8, 1, tzinfo=ZoneInfo("America/Chihuahua"))
        utc = local.astimezone(ZoneInfo("UTC"))
        self.assertEqual(utc.hour, 6)


if __name__ == "__main__":
    unittest.main()
