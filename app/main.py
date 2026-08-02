from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings
from app.database import database_enabled, initialize_database
from app.odoo import OdooClient
from app.services.copilot import answer_question
from app.services.dashboard import DashboardService
from app.services.history import trends
from app.services.warehouse import (
    executive_history,
    export_executive_csv,
    initialize_warehouse,
    inventory_history,
    warehouse_enabled,
)
from app.version import APP_VERSION

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
settings = Settings.from_env()
odoo = OdooClient(settings)
dashboard_service = DashboardService(settings, odoo)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    initialize_warehouse()
    await odoo.start()
    try:
        yield
    finally:
        await odoo.close()


app = FastAPI(
    title="CICE Coco Pops",
    version=APP_VERSION,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "architecture": "enterprise-consolidated",
        "database_enabled": database_enabled(),
        "warehouse_enabled": warehouse_enabled(),
        "odoo_configured": bool(settings.odoo_api_key),
    }


@app.get("/api/dashboard")
async def dashboard(
    refresh: Annotated[bool, Query(description="Ignora el caché temporal")] = False,
) -> dict[str, object]:
    return await dashboard_service.get_snapshot(force=refresh)


@app.post("/api/copilot")
async def copilot(payload: Annotated[CopilotRequest, Body()]) -> dict[str, object]:
    snapshot = await dashboard_service.get_snapshot()
    return answer_question(
        payload.question,
        snapshot["inventory"],
        snapshot["production"],
        snapshot["sales"],
        snapshot["ceo_priorities"],
    )


@app.get("/api/trends")
async def get_trends(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, object]:
    return trends(days)


@app.get("/api/history/summary")
async def history_summary(
    category: str = "TODOS",
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, object]:
    points = executive_history(category=category, days=days)
    if not points:
        return {
            "enabled": warehouse_enabled(),
            "category": category,
            "days": days,
            "points": [],
            "summary": {
                "coverage_change": None,
                "available_change": None,
                "critical_change": None,
                "sales_change": None,
                "production_change": None,
                "trend": "SIN_DATOS",
            },
        }

    first, last = points[0], points[-1]
    first_coverage = first.get("coverage_pct")
    last_coverage = last.get("coverage_pct")
    coverage_change = (
        round(float(last_coverage) - float(first_coverage), 1)
        if first_coverage is not None and last_coverage is not None
        else None
    )
    critical_change = int(last.get("critical") or 0) - int(first.get("critical") or 0)
    trend = "SIN_DATOS"
    if coverage_change is not None:
        if coverage_change > 3 and critical_change <= 0:
            trend = "MEJORA"
        elif coverage_change < -3 or critical_change > 0:
            trend = "DETERIORO"
        else:
            trend = "ESTABLE"

    return {
        "enabled": warehouse_enabled(),
        "category": category,
        "days": days,
        "points": points,
        "summary": {
            "coverage_change": coverage_change,
            "available_change": round(float(last.get("available") or 0) - float(first.get("available") or 0), 2),
            "critical_change": critical_change,
            "sales_change": round(float(last.get("sales_total") or 0) - float(first.get("sales_total") or 0), 2),
            "production_change": round(float(last.get("production_progress") or 0) - float(first.get("production_progress") or 0), 1),
            "trend": trend,
        },
    }


@app.get("/api/warehouse/executive")
async def warehouse_executive(
    category: str = "TODOS",
    days: Annotated[int, Query(ge=1, le=730)] = 90,
) -> dict[str, object]:
    return {
        "enabled": warehouse_enabled(),
        "category": category,
        "points": executive_history(category=category, days=days),
    }


@app.get("/api/warehouse/inventory")
async def warehouse_inventory(
    product_id: int | None = None,
    days: Annotated[int, Query(ge=1, le=730)] = 90,
) -> dict[str, object]:
    return {
        "enabled": warehouse_enabled(),
        "product_id": product_id,
        "points": inventory_history(product_id=product_id, days=days),
    }


@app.get("/api/warehouse/export.csv", response_class=PlainTextResponse)
async def warehouse_export(
    category: str = "TODOS",
    days: Annotated[int, Query(ge=1, le=730)] = 365,
) -> PlainTextResponse:
    safe_name = "".join(ch for ch in category.lower() if ch.isalnum() or ch in "-_ ").strip().replace(" ", "-") or "todos"
    return PlainTextResponse(
        export_executive_csv(category=category, days=days),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cice-{safe_name}-historico.csv"'},
    )
