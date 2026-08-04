from __future__ import annotations

from datetime import datetime
from typing import Any

from app.odoo import OdooClient


STATE_LABELS = {
    "draft": "Borrador",
    "confirmed": "Confirmada",
    "progress": "En producción",
    "to_close": "Por cerrar",
    "done": "Terminada",
    "cancel": "Cancelada",
}


async def _read_orders(
    client: OdooClient,
    domain: list[Any],
    *,
    limit: int = 5000,
    order: str = "date_start desc",
) -> list[dict[str, Any]]:
    return await client.call(
        "mrp.production",
        "search_read",
        {
            "domain": domain,
            "fields": [
                "name",
                "product_id",
                "product_qty",
                "product_uom_id",
                "qty_producing",
                "state",
                "date_start",
                "date_finished",
                "origin",
            ],
            "limit": limit,
            "order": order,
        },
    )


def _order_detail(item: dict[str, Any]) -> dict[str, Any]:
    product = item.get("product_id") or [False, "Producto sin nombre"]
    uom = item.get("product_uom_id") or [False, "Unidad"]
    state = str(item.get("state") or "draft")
    planned = round(float(item.get("product_qty") or 0), 2)
    produced = planned if state == "done" else round(float(item.get("qty_producing") or 0), 2)

    return {
        "id": int(item.get("id") or 0),
        "order": str(item.get("name") or "—"),
        "product_id": int(product[0] or 0),
        "product": str(product[1] or "Producto sin nombre"),
        "quantity": planned,
        "produced": produced,
        "uom": str(uom[1] or "Unidad"),
        "state": state,
        "state_label": STATE_LABELS.get(state, state.replace("_", " ").title()),
        "status": "CERRADA" if state == "done" else "ABIERTA",
        "is_closed": state == "done",
        "date_start": item.get("date_start"),
        "date_finished": item.get("date_finished"),
        "origin": str(item.get("origin") or ""),
    }


async def build_production(
    client: OdooClient,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    start_text = start.strftime("%Y-%m-%d %H:%M:%S")
    end_text = end.strftime("%Y-%m-%d %H:%M:%S")

    # Métricas del día: conserva la lógica histórica del tablero.
    today_orders = await _read_orders(
        client,
        [
            ["date_start", ">=", start_text],
            ["date_start", "<", end_text],
            ["state", "!=", "cancel"],
        ],
        order="date_start asc",
    )

    # Detalle ejecutivo: toda orden que sigue abierta, aunque sea anterior,
    # más las órdenes terminadas hoy. Así la CEO no pierde órdenes atrasadas.
    open_orders = await _read_orders(
        client,
        [["state", "not in", ["done", "cancel"]]],
        limit=1000,
        order="date_start asc",
    )
    finished_today = await _read_orders(
        client,
        [
            ["state", "=", "done"],
            ["date_finished", ">=", start_text],
            ["date_finished", "<", end_text],
        ],
        limit=1000,
        order="date_finished desc",
    )

    combined: dict[int, dict[str, Any]] = {}
    for item in [*open_orders, *finished_today]:
        combined[int(item.get("id") or 0)] = item
    details = [_order_detail(item) for item in combined.values()]
    details.sort(key=lambda row: (row["is_closed"], row["date_start"] or "", row["order"]))

    planned = round(sum(float(item.get("product_qty") or 0) for item in today_orders), 2)
    done = round(
        sum(
            float(item.get("product_qty") or 0)
            for item in today_orders
            if item.get("state") == "done"
        ),
        2,
    )
    producing = round(
        sum(float(item.get("qty_producing") or 0) for item in today_orders),
        2,
    )
    progress = round((done / planned) * 100, 1) if planned else 0

    return {
        "orders": len(today_orders),
        "planned": planned,
        "done": done,
        "producing": producing,
        "progress": progress,
        "open_orders": len(open_orders),
        "finished_today": len(finished_today),
        "details": details,
    }
