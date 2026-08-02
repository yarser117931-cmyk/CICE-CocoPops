
from __future__ import annotations

from typing import Any


FINISHED_PRODUCT_WORDS = (
    "PALETA",
    "NIEVE",
    "HELADO",
    "PASTEL",
)


def _is_finished_product(category: str) -> bool:
    upper = category.upper()
    return any(word in upper for word in FINISHED_PRODUCT_WORDS)


def build_ceo_priorities(
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
) -> dict[str, Any]:
    products = inventory["products"]

    actions: list[dict[str, Any]] = []

    # 1) Products below minimum.
    for product in products:
        status = product.get("status")
        if status not in ("CRITICO", "BAJO_MINIMO", "EN_RIESGO"):
            continue

        category = product.get("category") or ""
        finished = _is_finished_product(category)

        if status == "CRITICO":
            priority = "ALTA"
        elif status == "BAJO_MINIMO":
            priority = "MEDIA"
        else:
            priority = "PREVENTIVA"

        action_type = "FABRICAR" if finished else "REABASTECER"

        actions.append({
            "priority": priority,
            "type": action_type,
            "title": product.get("name") or "Producto sin nombre",
            "category": category,
            "product_id": product.get("id"),
            "available": float(product.get("available") or 0),
            "minimum": float(product.get("minimum") or 0),
            "missing": float(product.get("missing_to_minimum") or 0),
            "coverage_pct": product.get("coverage_pct"),
            "uom": product.get("uom") or "",
            "reason": (
                f"Disponible {round(float(product.get('available') or 0), 2)} "
                f"contra mínimo {round(float(product.get('minimum') or 0), 2)}."
            ),
        })

    priority_order = {
        "ALTA": 0,
        "MEDIA": 1,
        "PREVENTIVA": 2,
    }
    actions.sort(
        key=lambda item: (
            priority_order[item["priority"]],
            item["coverage_pct"] if item["coverage_pct"] is not None else 999999,
            item["title"],
        )
    )

    # 2) Executive operational actions.
    operational: list[dict[str, Any]] = []

    if production.get("orders", 0) > 0 and production.get("progress", 0) < 50:
        operational.append({
            "priority": "ALTA",
            "type": "PRODUCCION",
            "title": "Revisar avance de producción",
            "reason": (
                f"El avance del día es {production.get('progress', 0)}% "
                f"en {production.get('orders', 0)} órdenes."
            ),
        })
    elif production.get("orders", 0) > 0 and production.get("progress", 0) < 80:
        operational.append({
            "priority": "MEDIA",
            "type": "PRODUCCION",
            "title": "Vigilar cumplimiento del programa",
            "reason": (
                f"El avance del día es {production.get('progress', 0)}%."
            ),
        })

    if sales.get("orders", 0) == 0:
        operational.append({
            "priority": "PREVENTIVA",
            "type": "VENTAS",
            "title": "Confirmar registro de ventas del día",
            "reason": (
                "No se detectaron pedidos confirmados hoy en Odoo."
            ),
        })

    global_summary = inventory["global"]

    if global_summary.get("without_minimum", 0) > 0:
        operational.append({
            "priority": "MEDIA",
            "type": "CONFIGURACION",
            "title": "Completar políticas de stock mínimo",
            "reason": (
                f"{global_summary.get('without_minimum', 0)} productos "
                "todavía no tienen mínimo configurado."
            ),
        })

    # 3) Compact buckets for the CEO screen.
    buckets = {
        "urgent": [
            item for item in actions
            if item["priority"] == "ALTA"
        ][:10],
        "important": [
            item for item in actions
            if item["priority"] == "MEDIA"
        ][:10],
        "preventive": [
            item for item in actions
            if item["priority"] == "PREVENTIVA"
        ][:10],
        "operational": operational[:10],
    }

    return {
        "total_actions": len(actions) + len(operational),
        "urgent_count": len([
            item for item in actions
            if item["priority"] == "ALTA"
        ]),
        "important_count": len([
            item for item in actions
            if item["priority"] == "MEDIA"
        ]),
        "preventive_count": len([
            item for item in actions
            if item["priority"] == "PREVENTIVA"
        ]),
        "buckets": buckets,
        "top_actions": (actions + operational)[:12],
    }
