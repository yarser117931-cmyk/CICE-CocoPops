import unittest

from app.services.warehouse import (
    executive_history,
    export_executive_csv,
    inventory_history,
)


class TestWarehouseSafeMode(unittest.TestCase):
    def test_inventory_history_safe(self):
        self.assertIsInstance(inventory_history(days=10), list)

    def test_executive_history_safe(self):
        self.assertIsInstance(executive_history(days=10), list)

    def test_csv_export_has_header(self):
        csv_text = export_executive_csv()
        self.assertIn("date,category,products", csv_text)


if __name__ == "__main__":
    unittest.main()
