
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.helpers import (
    executive_category,
    product_status,
    relation_id,
    relation_name,
)
from app.odoo import OdooClient


def category_summary(
    name: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    comparable = [item for item in items if item["minimum"] > 0]

    total_available = round(
        sum(item["available"] for item in items),
        2,
    )
    total_on_hand = round(
        sum(item["on_hand"] for item in items),
        2,
    )
    total_reserved = round(
        sum(item["reserved"] for item in items),
        2,
    )
    total_minimum = round(
        sum(item["minimum"] for item in comparable),
        2,
    )

    coverage = (
        round((total_available / total_minimum) * 100, 1)
        if total_minimum > 0
        else None
    )

    return {
        "name": name,
        "products": len(items),
        "products_with_minimum": len(comparable),
        "available": total_available,
        "on_hand": total_on_hand,
        "reserved": total_reserved,
        "minimum": total_minimum,
        "coverage_pct": coverage,
        "critical": sum(
            1 for item in comparable
            if item["status"] == "CRITICO"
        ),
        "below_minimum": sum(
            1 for item in comparable
            if item["status"] == "BAJO_MINIMO"
        ),
        "at_risk": sum(
            1 for item in comparable
            if item["status"] == "EN_RIESGO"
        ),
        "healthy": sum(
            1 for item in comparable
            if item["status"] == "SALUDABLE"
        ),
        "without_minimum": sum(
            1 for item in items
            if item["status"] == "SIN_MINIMO"
        ),
    }


async def build_inventory(
    client: OdooClient,
) -> dict[str, Any]:
    products = await client.call(
        "product.product",
        "search_read",
        {
            "domain": [["active", "=", True]],
            "fields": [
                "id",
                "name",
                "default_code",
                "categ_id",
                "uom_id",
            ],
            "limit": 10000,
            "order": "categ_id asc, name asc",
        },
    )

    product_ids = [int(product["id"]) for product in products]

    quants = []
    orderpoints = []

    if product_ids:
        quants = await client.call(
            "stock.quant",
            "search_read",
            {
                "domain": [
                    ["product_id", "in", product_ids],
                    ["location_id.usage", "=", "internal"],
                ],
                "fields": [
                    "product_id",
                    "quantity",
                    "reserved_quantity",
                    "available_quantity",
                    "location_id",
                ],
                "limit": 50000,
            },
        )

        orderpoints = await client.call(
            "stock.warehouse.orderpoint",
            "search_read",
            {
                "domain": [
                    ["product_id", "in", product_ids],
                    ["active", "=", True],
                ],
                "fields": [
                    "product_id",
                    "product_min_qty",
                    "product_max_qty",
                    "location_id",
                    "warehouse_id",
                ],
                "limit": 50000,
            },
        )

    inventory: dict[int, dict[str, Any]] = {}

    for product in products:
        product_id = int(product["id"])
        original = (
            relation_name(product.get("categ_id"))
            or "Sin categoría"
        )
        category = executive_category(original)

        inventory[product_id] = {
            "id": product_id,
            "name": product.get("name", ""),
            "code": product.get("default_code") or "",
            "category": category,
            "original_category": original,
            "uom": relation_name(product.get("uom_id")),
            "on_hand": 0.0,
            "reserved": 0.0,
            "available": 0.0,
            "minimum": 0.0,
            "maximum": 0.0,
        }

    for quant in quants:
        product_id = relation_id(quant.get("product_id"))
        if product_id not in inventory:
            continue

        quantity = float(quant.get("quantity") or 0)
        reserved = float(quant.get("reserved_quantity") or 0)
        available = quant.get("available_quantity")

        if available is None:
            available = quantity - reserved

        inventory[product_id]["on_hand"] += quantity
        inventory[product_id]["reserved"] += reserved
        inventory[product_id]["available"] += float(available)

    for point in orderpoints:
        product_id = relation_id(point.get("product_id"))
        if product_id not in inventory:
            continue

        inventory[product_id]["minimum"] += float(
            point.get("product_min_qty") or 0
        )
        inventory[product_id]["maximum"] += float(
            point.get("product_max_qty") or 0
        )

    items = list(inventory.values())

    for item in items:
        status, coverage = product_status(
            item["available"],
            item["minimum"],
        )
        item["status"] = status
        item["coverage_pct"] = coverage
        item["gap"] = round(
            item["available"] - item["minimum"],
            2,
        )
        item["missing_to_minimum"] = round(
            max(item["minimum"] - item["available"], 0),
            2,
        )

    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        category_groups[item["category"]].append(item)

    categories = [
        category_summary(name, category_items)
        for name, category_items in category_groups.items()
    ]

    category_priority = {
        "PALETAS": 0,
        "NIEVES": 1,
        "BOTES DE HELADO": 2,
        "PASTELES": 3,
        "EMPAQUE Y PRESENTACIÓN": 4,
        "FABRICACIÓN / INGREDIENTES": 5,
        "LIMPIEZA": 6,
        "ADMON": 7,
    }

    categories.sort(
        key=lambda category: (
            category_priority.get(
                category["name"].upper(),
                99,
            ),
            category["name"].upper(),
        )
    )

    status_priority = {
        "CRITICO": 0,
        "BAJO_MINIMO": 1,
        "EN_RIESGO": 2,
        "SALUDABLE": 3,
        "SIN_MINIMO": 4,
    }

    items.sort(
        key=lambda item: (
            item["category"].upper(),
            status_priority[item["status"]],
            (
                item["coverage_pct"]
                if item["coverage_pct"] is not None
                else 999999
            ),
            item["name"].upper(),
        )
    )

    return {
        "global": category_summary("TODOS", items),
        "categories": categories,
        "products": items,
    }
