
from __future__ import annotations

from typing import Any


def build_intelligence(
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
) -> dict[str, Any]:
    items = inventory["products"]
    global_summary = inventory["global"]

    alerts: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    critical_items = [
        item for item in items
        if item["status"] in ("CRITICO", "BAJO_MINIMO")
    ]
    critical_items.sort(
        key=lambda item: (
            (
                item["coverage_pct"]
                if item["coverage_pct"] is not None
                else 999999
            ),
            item["name"],
        )
    )

    for item in critical_items[:20]:
        level = (
            "CRITICO"
            if item["status"] == "CRITICO"
            else "IMPORTANTE"
        )

        alerts.append({
            "level": level,
            "title": item["name"],
            "message": (
                f"Disponible {round(item['available'], 2)} "
                f"contra mínimo {round(item['minimum'], 2)}."
            ),
            "category": item["category"],
        })

    for item in critical_items[:5]:
        is_finished = any(
            word in item["category"].upper()
            for word in ("PALETA", "NIEVE", "HELADO", "PASTEL")
        )
        action = "Fabricar" if is_finished else "Reabastecer"

        recommendations.append({
            "priority": (
                "ALTA"
                if item["status"] == "CRITICO"
                else "MEDIA"
            ),
            "action": action,
            "product": item["name"],
            "category": item["category"],
            "message": (
                f"Disponible {round(item['available'], 2)} "
                f"contra mínimo {round(item['minimum'], 2)}. "
                f"Faltan {round(item['missing_to_minimum'], 2)} "
                f"{item['uom']}."
            ),
        })

    coverage = global_summary["coverage_pct"]

    if coverage is None:
        company_status = "SIN_DATOS"
    elif coverage < 80 or global_summary["critical"] > 0:
        company_status = "CRITICO"
    elif coverage < 100 or global_summary["below_minimum"] > 0:
        company_status = "ATENCION"
    else:
        company_status = "ESTABLE"

    headline = {
        "CRITICO": "La empresa requiere atención inmediata en inventarios.",
        "ATENCION": "La operación presenta alertas que deben revisarse hoy.",
        "ESTABLE": "La operación se encuentra estable.",
        "SIN_DATOS": "Falta configurar información para evaluar inventarios.",
    }[company_status]

    executive_summary = {
        "company_status": company_status,
        "headline": headline,
        "inventory_message": (
            f"{global_summary['critical']} productos críticos, "
            f"{global_summary['below_minimum']} bajo mínimo y "
            f"{global_summary['at_risk']} en riesgo."
        ),
        "production_message": (
            f"{production['orders']} órdenes de fabricación hoy con "
            f"{production['progress']}% de avance terminado."
        ),
        "sales_message": (
            f"Ventas confirmadas por {sales['total']} en "
            f"{sales['orders']} pedidos."
        ),
    }

    return {
        "alerts": alerts,
        "recommendations": recommendations,
        "executive_summary": executive_summary,
    }
