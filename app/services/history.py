
from __future__ import annotations

from datetime import date
from typing import Any

from app.database import (
    database_enabled,
    read_trends,
    save_daily_snapshot,
)


def capture_snapshot(
    today: date,
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
) -> dict[str, Any]:
    if not database_enabled():
        return {
            "enabled": False,
            "saved_today": False,
            "message": "DATABASE_URL no está configurada.",
        }

    saved = save_daily_snapshot(
        snapshot_date=today,
        inventory=inventory,
        production=production,
        sales=sales,
    )

    return {
        "enabled": True,
        "saved_today": saved,
        "message": (
            "Se creó el resumen diario."
            if saved
            else "Se actualizó el resumen de hoy."
        ),
    }


def trends(days: int = 30) -> dict[str, Any]:
    rows = read_trends(days)

    summary = {
        "inventory_available_change": None,
        "critical_change": None,
        "sales_change": None,
    }

    if len(rows) >= 2:
        first = rows[0]
        last = rows[-1]
        summary = {
            "inventory_available_change": round(
                last["inventory_available"] - first["inventory_available"],
                2,
            ),
            "critical_change": (
                last["products_critical"] - first["products_critical"]
            ),
            "sales_change": round(
                last["sales_total"] - first["sales_total"],
                2,
            ),
        }

    return {
        "enabled": database_enabled(),
        "days_requested": days,
        "points": rows,
        "summary": summary,
    }
