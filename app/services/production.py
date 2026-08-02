
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.odoo import OdooClient


async def build_production(
    client: OdooClient,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    manufacturing = await client.call(
        "mrp.production",
        "search_read",
        {
            "domain": [
                ["date_start", ">=", start.strftime("%Y-%m-%d %H:%M:%S")],
                ["date_start", "<", end.strftime("%Y-%m-%d %H:%M:%S")],
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

    planned = round(
        sum(float(item.get("product_qty") or 0) for item in manufacturing),
        2,
    )
    done = round(
        sum(
            float(item.get("product_qty") or 0)
            for item in manufacturing
            if item.get("state") == "done"
        ),
        2,
    )
    producing = round(
        sum(float(item.get("qty_producing") or 0) for item in manufacturing),
        2,
    )

    progress = round((done / planned) * 100, 1) if planned else 0

    return {
        "orders": len(manufacturing),
        "planned": planned,
        "done": done,
        "producing": producing,
        "progress": progress,
    }
