
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="CICE Coco Pops", version="1.3.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ODOO_URL = os.getenv("ODOO_URL", "https://cocopopsmx1.odoo.com").rstrip("/")
ODOO_DATABASE = os.getenv("ODOO_DATABASE", "cocopopsmx1")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Chihuahua")


def require_config() -> None:
    if not ODOO_API_KEY or ODOO_API_KEY == "PEGA_AQUI_TU_CLAVE_API":
        raise HTTPException(
            status_code=503,
            detail="Falta configurar ODOO_API_KEY en Render.",
        )


async def odoo_call(model: str, method: str, payload: dict[str, Any]) -> Any:
    require_config()
    url = f"{ODOO_URL}/json/2/{model}/{method}"
    headers = {
        "Authorization": f"bearer {ODOO_API_KEY}",
        "X-Odoo-Database": ODOO_DATABASE,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Odoo respondió {response.status_code}: {response.text[:600]}",
        )
    return response.json()


def relation_name(value: Any) -> str:
    return str(value[1]) if isinstance(value, list) and len(value) > 1 else ""


def relation_id(value: Any) -> int | None:
    return int(value[0]) if isinstance(value, list) and value else None


def executive_category(category_name: str) -> str:
    """Agrupa subcategorías operativas en categorías ejecutivas.

    Todo producto cuya ruta de categoría contenga FABRICACION/FABRICACIÓN
    se presenta en el tablero inicial como una sola categoría:
    FABRICACIÓN / INGREDIENTES.

    La subcategoría original se conserva para la tabla de detalle.
    """
    normalized = (
        category_name.upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )

    if "FABRICACION" in normalized:
        return "FABRICACIÓN / INGREDIENTES"

    return category_name


def product_status(available: float, minimum: float) -> tuple[str, float | None]:
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


def category_summary(name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [item for item in items if item["minimum"] > 0]

    total_available = round(sum(item["available"] for item in items), 2)
    total_on_hand = round(sum(item["on_hand"] for item in items), 2)
    total_reserved = round(sum(item["reserved"] for item in items), 2)
    total_minimum = round(sum(item["minimum"] for item in comparable), 2)

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
        "critical": sum(1 for item in comparable if item["status"] == "CRITICO"),
        "below_minimum": sum(
            1 for item in comparable if item["status"] == "BAJO_MINIMO"
        ),
        "at_risk": sum(1 for item in comparable if item["status"] == "EN_RIESGO"),
        "healthy": sum(1 for item in comparable if item["status"] == "SALUDABLE"),
        "without_minimum": sum(
            1 for item in items if item["status"] == "SIN_MINIMO"
        ),
    }


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.3.0",
        "odoo_url": ODOO_URL,
        "database": ODOO_DATABASE,
    }


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    today_str = start.strftime("%Y-%m-%d")

    products = await odoo_call(
        "product.product",
        "search_read",
        {
            "domain": [["active", "=", True]],
            "fields": ["id", "name", "default_code", "categ_id", "uom_id"],
            "limit": 10000,
            "order": "categ_id asc, name asc",
        },
    )

    product_ids = [int(product["id"]) for product in products]

    quants: list[dict[str, Any]] = []
    orderpoints: list[dict[str, Any]] = []

    if product_ids:
        quants = await odoo_call(
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

        orderpoints = await odoo_call(
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
        original_category = relation_name(product.get("categ_id")) or "Sin categoría"
        category = executive_category(original_category)
        inventory[product_id] = {
            "id": product_id,
            "name": product.get("name", ""),
            "code": product.get("default_code") or "",
            "category": category,
            "original_category": original_category,
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

    for orderpoint in orderpoints:
        product_id = relation_id(orderpoint.get("product_id"))
        if product_id not in inventory:
            continue

        inventory[product_id]["minimum"] += float(
            orderpoint.get("product_min_qty") or 0
        )
        inventory[product_id]["maximum"] += float(
            orderpoint.get("product_max_qty") or 0
        )

    items = list(inventory.values())

    for item in items:
        status, coverage = product_status(item["available"], item["minimum"])
        item["status"] = status
        item["coverage_pct"] = coverage
        item["gap"] = round(item["available"] - item["minimum"], 2)
        item["missing_to_minimum"] = round(
            max(item["minimum"] - item["available"], 0), 2
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
        "FABRICACION": 5,
        "FABRICACIÓN": 5,
        "LIMPIEZA": 6,
        "ADMON": 7,
    }

    categories.sort(
        key=lambda category: (
            category_priority.get(category["name"].upper(), 99),
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
            item["coverage_pct"] if item["coverage_pct"] is not None else 999999,
            item["name"].upper(),
        )
    )

    global_summary = category_summary("TODOS", items)

    manufacturing = await odoo_call(
        "mrp.production",
        "search_read",
        {
            "domain": [
                ["date_start", ">=", start_str],
                ["date_start", "<", end_str],
                ["state", "!=", "cancel"],
            ],
            "fields": [
                "name",
                "product_id",
                "product_qty",
                "qty_producing",
                "state",
                "date_start",
                "date_finished",
            ],
            "limit": 5000,
            "order": "date_start asc",
        },
    )

    planned_qty = round(
        sum(float(item.get("product_qty") or 0) for item in manufacturing), 2
    )
    done_qty = round(
        sum(
            float(item.get("product_qty") or 0)
            for item in manufacturing
            if item.get("state") == "done"
        ),
        2,
    )
    production_progress = (
        round((done_qty / planned_qty) * 100, 1) if planned_qty else 0
    )

    sales = await odoo_call(
        "sale.order",
        "search_read",
        {
            "domain": [
                ["date_order", ">=", start_str],
                ["date_order", "<", end_str],
                ["state", "in", ["sale", "done"]],
            ],
            "fields": [
                "name",
                "date_order",
                "partner_id",
                "amount_total",
                "invoice_status",
                "state",
            ],
            "limit": 5000,
            "order": "date_order desc",
        },
    )

    sales_total = round(
        sum(float(item.get("amount_total") or 0) for item in sales), 2
    )
    customers = {
        relation_name(item.get("partner_id"))
        for item in sales
        if relation_name(item.get("partner_id"))
    }

    invoices = await odoo_call(
        "account.move",
        "search_read",
        {
            "domain": [
                ["invoice_date", "=", today_str],
                ["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
            ],
            "fields": ["name", "amount_total"],
            "limit": 5000,
        },
    )

    return {
        "generated_at": now.isoformat(),
        "source": {"url": ODOO_URL, "database": ODOO_DATABASE},
        "inventory": {
            "global": global_summary,
            "categories": categories,
            "products": items,
        },
        "production": {
            "orders": len(manufacturing),
            "planned": planned_qty,
            "done": done_qty,
            "progress": production_progress,
        },
        "sales": {
            "total": sales_total,
            "orders": len(sales),
            "customers": len(customers),
            "invoiced_today": round(
                sum(float(item.get("amount_total") or 0) for item in invoices), 2
            ),
        },
    }
