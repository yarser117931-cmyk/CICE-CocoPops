
from __future__ import annotations

from typing import Any


def relation_name(value: Any) -> str:
    return (
        str(value[1])
        if isinstance(value, list) and len(value) > 1
        else ""
    )


def relation_id(value: Any) -> int | None:
    return int(value[0]) if isinstance(value, list) and value else None


def normalize(value: str) -> str:
    return (
        value.upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )


def executive_category(category_name: str) -> str:
    normalized = normalize(category_name)

    if "FABRICACION" in normalized:
        return "FABRICACIÓN / INGREDIENTES"

    if "PALETA" in normalized:
        return "PALETAS"

    return category_name


def product_status(
    available: float,
    minimum: float,
) -> tuple[str, float | None]:
    if minimum <= 0:
        return "SIN_MINIMO", None

    coverage = round((available / minimum) * 100, 1)

    if available <= 0 or coverage < 50:
        return "CRITICO", coverage
    if coverage < 100:
        return "BAJO_MINIMO", coverage
    if coverage < 120:
        return "EN_RIESGO", coverage
    return "SALUDABLE", coverage
