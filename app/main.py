
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.odoo import OdooClient
from app.database import database_enabled, initialize_database
from app.services.history import capture_snapshot, trends
from app.services.intelligence import build_intelligence
from app.services.inventory import build_inventory
from app.services.production import build_production
from app.services.sales import build_sales
from app.services.warehouse import (
    executive_history,
    export_executive_csv,
    initialize_warehouse,
    inventory_history,
    save_warehouse_snapshot,
    warehouse_enabled,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

settings = Settings.from_env()
odoo = OdooClient(settings)

app = FastAPI(
    title="CICE Coco Pops",
    version="7.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.on_event("startup")
async def startup() -> None:
    initialize_database()
    initialize_warehouse()


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "7.0.0",
        "architecture": "modular-data-warehouse",
        "database_enabled": database_enabled(),
        "warehouse_enabled": warehouse_enabled(),
        "odoo_url": settings.odoo_url,
        "database": settings.odoo_database,
    }


@app.get("/api/trends")
async def get_trends(days: int = 30) -> dict[str, object]:
    return trends(days)


@app.get("/api/warehouse/executive")
async def warehouse_executive(
    category: str = "TODOS",
    days: int = 90,
) -> dict[str, object]:
    return {
        "enabled": warehouse_enabled(),
        "category": category,
        "points": executive_history(category=category, days=days),
    }


@app.get("/api/warehouse/inventory")
async def warehouse_inventory(
    product_id: int | None = None,
    days: int = 90,
) -> dict[str, object]:
    return {
        "enabled": warehouse_enabled(),
        "product_id": product_id,
        "points": inventory_history(product_id=product_id, days=days),
    }


@app.get(
    "/api/warehouse/export.csv",
    response_class=PlainTextResponse,
)
async def warehouse_export(
    category: str = "TODOS",
    days: int = 365,
) -> PlainTextResponse:
    content = export_executive_csv(category=category, days=days)
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="cice-{category.lower()}-historico.csv"'
            )
        },
    )


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)
    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end = start + timedelta(days=1)

    inventory = await build_inventory(odoo)
    production = await build_production(odoo, start, end)
    sales = await build_sales(odoo, start, end)
    intelligence = build_intelligence(
        inventory,
        production,
        sales,
    )

    history = capture_snapshot(
        today=start.date(),
        inventory=inventory,
        production=production,
        sales=sales,
    )

    warehouse = save_warehouse_snapshot(
        snapshot_date=start.date(),
        inventory=inventory,
        production=production,
        sales=sales,
    )

    return {
        "generated_at": now.isoformat(),
        "source": {
            "url": settings.odoo_url,
            "database": settings.odoo_database,
        },
        "inventory": inventory,
        "production": production,
        "sales": sales,
        "history": history,
        "warehouse": warehouse,
        **intelligence,
    }
