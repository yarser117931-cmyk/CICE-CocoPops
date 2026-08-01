
from __future__ import annotations

import os
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

app = FastAPI(title="CICE Coco Pops", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ODOO_URL = os.getenv("ODOO_URL", "https://cocopopsmx1.odoo.com").rstrip("/")
ODOO_DATABASE = os.getenv("ODOO_DATABASE", "cocopopsmx1")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Chihuahua")
CATEGORY_KEYWORDS = [
    x.strip().upper()
    for x in os.getenv(
        "FINISHED_CATEGORY_KEYWORDS",
        "PALETAS,NIEVE,HELADO,BOTES DE HELADO",
    ).split(",")
    if x.strip()
]
LOW_STOCK_THRESHOLD = float(os.getenv("LOW_STOCK_THRESHOLD", "25"))


def require_config() -> None:
    if not ODOO_API_KEY or ODOO_API_KEY == "PEGA_AQUI_TU_CLAVE_API":
        raise HTTPException(
            status_code=503,
            detail="Falta configurar ODOO_API_KEY en las variables del servidor.",
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
        detail = response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Odoo respondió {response.status_code}: {detail}",
        )
    return response.json()


def relation_name(value: Any) -> str:
    return str(value[1]) if isinstance(value, list) and len(value) > 1 else ""


def relation_id(value: Any) -> int | None:
    return int(value[0]) if isinstance(value, list) and value else None


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "odoo_url": ODOO_URL,
        "database": ODOO_DATABASE,
        "api_key_configured": bool(ODOO_API_KEY and ODOO_API_KEY != "PEGA_AQUI_TU_CLAVE_API"),
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
            "limit": 5000,
            "order": "name asc",
        },
    )

    finished_products = []
    for product in products:
        category = relation_name(product.get("categ_id"))
        if any(keyword in category.upper() for keyword in CATEGORY_KEYWORDS):
            finished_products.append(product)

    product_ids = [int(p["id"]) for p in finished_products]
    quants = []
    orderpoints = []
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
                "limit": 20000,
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
                ],
                "limit": 20000,
            },
        )

    inventory: dict[int, dict[str, Any]] = {}
    for product in finished_products:
        pid = int(product["id"])
        inventory[pid] = {
            "id": pid,
            "name": product.get("name", ""),
            "code": product.get("default_code") or "",
            "category": relation_name(product.get("categ_id")),
            "uom": relation_name(product.get("uom_id")),
            "quantity": 0.0,
            "reserved": 0.0,
            "available": 0.0,
            "minimum": 0.0,
            "coverage_pct": None,
            "status": "SIN_MINIMO",
        }

    for quant in quants:
        pid = relation_id(quant.get("product_id"))
        if pid in inventory:
            quantity = float(quant.get("quantity") or 0)
            reserved = float(quant.get("reserved_quantity") or 0)
            available = quant.get("available_quantity")
            if available is None:
                available = quantity - reserved
            inventory[pid]["quantity"] += quantity
            inventory[pid]["reserved"] += reserved
            inventory[pid]["available"] += float(available)

    for orderpoint in orderpoints:
        pid = relation_id(orderpoint.get("product_id"))
        if pid in inventory:
            inventory[pid]["minimum"] += float(orderpoint.get("product_min_qty") or 0)

    for item in inventory.values():
        minimum = item["minimum"]
        available = item["available"]
        if minimum <= 0:
            item["coverage_pct"] = None
            item["status"] = "SIN_MINIMO"
        else:
            coverage = round((available / minimum) * 100, 1)
            item["coverage_pct"] = coverage
            if available <= 0 or coverage < 50:
                item["status"] = "CRITICO"
            elif coverage < 100:
                item["status"] = "BAJO_MINIMO"
            elif coverage < 120:
                item["status"] = "EN_RIESGO"
            else:
                item["status"] = "SALUDABLE"

    priority = {"CRITICO": 0, "BAJO_MINIMO": 1, "EN_RIESGO": 2, "SALUDABLE": 3, "SIN_MINIMO": 4}
    inventory_items = sorted(
        inventory.values(),
        key=lambda item: (priority[item["status"]], item["coverage_pct"] if item["coverage_pct"] is not None else 999999, item["name"]),
    )
    comparable = [item for item in inventory_items if item["minimum"] > 0]
    total_available = round(sum(i["available"] for i in inventory_items), 2)
    total_minimum = round(sum(i["minimum"] for i in comparable), 2)
    global_coverage = round((total_available / total_minimum) * 100, 1) if total_minimum else None
    critical_count = sum(1 for i in comparable if i["status"] == "CRITICO")
    below_count = sum(1 for i in comparable if i["status"] == "BAJO_MINIMO")
    risk_count = sum(1 for i in comparable if i["status"] == "EN_RIESGO")
    healthy_count = sum(1 for i in comparable if i["status"] == "SALUDABLE")
    without_minimum = sum(1 for i in inventory_items if i["status"] == "SIN_MINIMO")

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
    planned_qty = round(sum(float(x.get("product_qty") or 0) for x in manufacturing), 2)
    done_qty = round(
        sum(
            float(x.get("product_qty") or 0)
            for x in manufacturing
            if x.get("state") == "done"
        ),
        2,
    )
    producing_qty = round(
        sum(float(x.get("qty_producing") or 0) for x in manufacturing), 2
    )
    production_progress = round(done_qty / planned_qty * 100, 1) if planned_qty else 0

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
    sales_total = round(sum(float(x.get("amount_total") or 0) for x in sales), 2)
    customers = {
        relation_name(x.get("partner_id"))
        for x in sales
        if relation_name(x.get("partner_id"))
    }
    pending_invoice = round(
        sum(
            float(x.get("amount_total") or 0)
            for x in sales
            if x.get("invoice_status") == "to invoice"
        ),
        2,
    )

    invoices = await odoo_call(
        "account.move",
        "search_read",
        {
            "domain": [
                ["invoice_date", "=", today_str],
                ["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
            ],
            "fields": [
                "name",
                "invoice_date",
                "partner_id",
                "amount_total",
                "payment_state",
            ],
            "limit": 5000,
            "order": "invoice_date desc",
        },
    )
    invoice_total = round(sum(float(x.get("amount_total") or 0) for x in invoices), 2)

    return {
        "generated_at": now.isoformat(),
        "source": {"url": ODOO_URL, "database": ODOO_DATABASE},
        "inventory": {
            "total_available": total_available,
            "total_minimum": total_minimum,
            "global_coverage_pct": global_coverage,
            "products": len(inventory_items),
            "products_with_minimum": len(comparable),
            "critical_count": critical_count,
            "below_minimum_count": below_count,
            "at_risk_count": risk_count,
            "healthy_count": healthy_count,
            "without_minimum_count": without_minimum,
            "priority": inventory_items[:12],
        },
        "production": {
            "orders": len(manufacturing),
            "planned": planned_qty,
            "done": done_qty,
            "producing": producing_qty,
            "progress": production_progress,
        },
        "sales": {
            "total": sales_total,
            "orders": len(sales),
            "customers": len(customers),
            "pending_invoice": pending_invoice,
            "invoiced_today": invoice_total,
        },
    }
