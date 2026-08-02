import unittest

from app.helpers import executive_category, product_status


class TestExecutiveCategories(unittest.TestCase):
    def test_paletas_are_grouped(self):
        self.assertEqual(
            executive_category("PALETAS / Paletas Gourmet"),
            "PALETAS",
        )

    def test_fabricacion_is_grouped(self):
        self.assertEqual(
            executive_category("Fabricación / Polvos"),
            "FABRICACIÓN / INGREDIENTES",
        )

    def test_other_category_is_preserved(self):
        self.assertEqual(
            executive_category("Empaque y presentación"),
            "Empaque y presentación",
        )


class TestProductStatus(unittest.TestCase):
    def test_without_minimum(self):
        self.assertEqual(product_status(20, 0), ("SIN_MINIMO", None))

    def test_critical(self):
        self.assertEqual(product_status(20, 100), ("CRITICO", 20.0))

    def test_below_minimum(self):
        self.assertEqual(product_status(75, 100), ("BAJO_MINIMO", 75.0))

    def test_at_risk(self):
        self.assertEqual(product_status(110, 100), ("EN_RIESGO", 110.0))

    def test_healthy(self):
        self.assertEqual(product_status(130, 100), ("SALUDABLE", 130.0))


if __name__ == "__main__":
    unittest.main()
