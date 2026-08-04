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
    fields: list[str],
    limit: int = 5000,
    order: str = "date_start desc",
) -> list[dict[str, Any]]:
    return await client.call(
        "mrp.production",
        "search_read",
        {
            "domain": domain,
            "fields": fields,
            "limit": limit,
            "order": order,
        },
    )


def _order_detail(item: dict[str, Any]) -> dict[str, Any]:
    product = item.get("product_id") or [False, "Producto sin nombre"]
    state = str(item.get("state") or "draft")
    planned = round(float(item.get("product_qty") or 0), 2)
    produced = planned if state == "done" else round(
        float(item.get("qty_producing") or 0),
        2,
    )

    return {
        "id": int(item.get("id") or 0),
        "order": str(item.get("name") or "—"),
        "product_id": int(product[0] or 0),
        "product": str(product[1] or "Producto sin nombre"),
        "quantity": planned,
        "produced": produced,
        "uom": "Pieza",
        "state": state,
        "state_label": STATE_LABELS.get(
            state,
            state.replace("_", " ").title(),
        ),
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
    """Build production metrics without allowing detail errors to break CICE."""

    start_text = start.strftime("%Y-%m-%d %H:%M:%S")
    end_text = end.strftime("%Y-%m-%d %H:%M:%S")

    base_fields = [
        "name",
        "product_id",
        "product_qty",
        "qty_producing",
        "state",
        "date_start",
        "date_finished",
    ]

    # This is the original query that was already proven to work.
    today_orders = await _read_orders(
        client,
        [
            ["date_start", ">=", start_text],
            ["date_start", "<", end_text],
            ["state", "!=", "cancel"],
        ],
        fields=base_fields,
        limit=5000,
        order="date_start asc",
    )

    planned = round(
        sum(float(item.get("product_qty") or 0) for item in today_orders),
        2,
    )
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

    details: list[dict[str, Any]] = []
    detail_warning = ""

    # Detail is optional. If Odoo rejects a field/query or responds slowly,
    # inventory and sales still load normally.
    try:
        detail_fields = [*base_fields, "origin"]

        open_orders = await _read_orders(
            client,
            [["state", "not in", ["done", "cancel"]]],
            fields=detail_fields,
            limit=250,
            order="date_start desc",
        )
        finished_today = await _read_orders(
            client,
            [
                ["state", "=", "done"],
                ["date_finished", ">=", start_text],
                ["date_finished", "<", end_text],
            ],
            fields=detail_fields,
            limit=250,
            order="date_finished desc",
        )

        combined: dict[int, dict[str, Any]] = {}
        for item in [*open_orders, *finished_today]:
            record_id = int(item.get("id") or 0)
            if record_id:
                combined[record_id] = item

        details = [_order_detail(item) for item in combined.values()]
        details.sort(
            key=lambda row: (
                row["is_closed"],
                row["date_start"] or "",
                row["order"],
            ),
            reverse=False,
        )
        open_count = len(open_orders)
        finished_count = len(finished_today)
    except Exception as error:
        # Never take down the complete executive dashboard because of
        # the optional detailed production list.
        detail_warning = str(error)
        details = [_order_detail(item) for item in today_orders]
        open_count = sum(1 for item in today_orders if item.get("state") != "done")
        finished_count = sum(1 for item in today_orders if item.get("state") == "done")

    return {
        "orders": len(today_orders),
        "planned": planned,
        "done": done,
        "producing": producing,
        "progress": progress,
        "open_orders": open_count,
        "finished_today": finished_count,
        "details": details,
        "detail_warning": detail_warning,
    }
