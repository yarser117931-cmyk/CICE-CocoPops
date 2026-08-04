
from __future__ import annotations

from datetime import datetime, timedelta
from time import perf_counter
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.odoo import OdooClient
from app.database import database_enabled, initialize_database
from app.services.history import capture_snapshot, trends
from app.services.intelligence import build_intelligence
from app.services.inventory import build_inventory
from app.services.production import build_production
from app.services.priorities import build_ceo_priorities
from app.services.copilot import answer_question
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
    version="12.2.1",
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
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/actualizar-cice", response_class=HTMLResponse)
async def actualizar_cice() -> HTMLResponse:
    """Elimina versiones antiguas guardadas por el navegador y abre CICE 12."""
    return HTMLResponse(
        """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Actualizando CICE</title>
  <style>
    body{font-family:Arial,sans-serif;background:#fffaf7;color:#5c1028;
         display:grid;place-items:center;min-height:100vh;margin:0;text-align:center}
    .box{max-width:460px;padding:32px;border:1px solid #eadfda;border-radius:22px;
         box-shadow:0 18px 45px rgba(92,16,40,.12);background:white}
    .spinner{width:48px;height:48px;border:5px solid #eadfda;border-top-color:#861f41;
             border-radius:50%;margin:0 auto 20px;animation:girar .8s linear infinite}
    @keyframes girar{to{transform:rotate(360deg)}}
  </style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <h1>Actualizando CICE</h1>
    <p>Estamos eliminando la versión anterior guardada en este dispositivo.</p>
  </div>
  <script>
    (async () => {
      try {
        if ('serviceWorker' in navigator) {
          const registrations = await navigator.serviceWorker.getRegistrations();
          await Promise.all(registrations.map(registration => registration.unregister()));
        }
        if ('caches' in window) {
          const keys = await caches.keys();
          await Promise.all(keys.map(key => caches.delete(key)));
        }
        localStorage.removeItem('cice-version');
        sessionStorage.clear();
      } finally {
        location.replace('/?version=12.2.1&actualizado=' + Date.now());
      }
    })();
  </script>
</body>
</html>
        """,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Clear-Site-Data": '"cache"',
        },
    )


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "12.2.1",
        "architecture": "modular-data-warehouse",
        "database_enabled": database_enabled(),
        "warehouse_enabled": warehouse_enabled(),
        "odoo_url": settings.odoo_url,
        "database": settings.odoo_database,
    }


@app.get("/api/trends")
async def get_trends(days: int = 30) -> dict[str, object]:
    return trends(days)




def build_historical_summary(
    category: str = "TODOS",
    days: int = 30,
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

    first = points[0]
    last = points[-1]

    first_coverage = first.get("coverage_pct")
    last_coverage = last.get("coverage_pct")

    coverage_change = None
    if first_coverage is not None and last_coverage is not None:
        coverage_change = round(last_coverage - first_coverage, 1)

    critical_change = int(last.get("critical") or 0) - int(first.get("critical") or 0)
    available_change = round(
        float(last.get("available") or 0)
        - float(first.get("available") or 0),
        2,
    )
    sales_change = round(
        float(last.get("sales_total") or 0)
        - float(first.get("sales_total") or 0),
        2,
    )
    production_change = round(
        float(last.get("production_progress") or 0)
        - float(first.get("production_progress") or 0),
        1,
    )

    if coverage_change is None:
        trend = "SIN_DATOS"
    elif coverage_change > 3 and critical_change <= 0:
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
            "available_change": available_change,
            "critical_change": critical_change,
            "sales_change": sales_change,
            "production_change": production_change,
            "trend": trend,
        },
    }



@app.get("/api/history/summary")
async def history_summary(
    category: str = "TODOS",
    days: int = 30,
) -> dict[str, object]:
    return build_historical_summary(category=category, days=days)


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



@app.post("/api/copilot")
async def copilot(payload: dict[str, object]) -> dict[str, object]:
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    inventory = await build_inventory(odoo)
    production = await build_production(odoo, start, end)
    sales = await build_sales(odoo, start, end)
    priorities = build_ceo_priorities(inventory, production, sales)

    question = str(payload.get("question") or "")
    return answer_question(
        question,
        inventory,
        production,
        sales,
        priorities,
    )


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    started_at = perf_counter()
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

    ceo_priorities = build_ceo_priorities(
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
        "query_duration_ms": round((perf_counter() - started_at) * 1000),
        "source": {
            "url": settings.odoo_url,
            "database": settings.odoo_database,
        },
        "inventory": inventory,
        "production": production,
        "sales": sales,
        "history": history,
        "warehouse": warehouse,
        "ceo_priorities": ceo_priorities,
        **intelligence,
    }
