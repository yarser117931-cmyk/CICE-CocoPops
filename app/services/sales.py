
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.helpers import relation_name
from app.odoo import OdooClient


async def build_sales(
    client: OdooClient,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    today_str = start.strftime("%Y-%m-%d")

    sales = await client.call(
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

    customers = {
        relation_name(item.get("partner_id"))
        for item in sales
        if relation_name(item.get("partner_id"))
    }

    invoices = await client.call(
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
        "total": round(
            sum(float(item.get("amount_total") or 0) for item in sales),
            2,
        ),
        "orders": len(sales),
        "customers": len(customers),
        "pending_invoice": round(
            sum(
                float(item.get("amount_total") or 0)
                for item in sales
                if item.get("invoice_status") == "to invoice"
            ),
            2,
        ),
        "invoiced_today": round(
            sum(float(item.get("amount_total") or 0) for item in invoices),
            2,
        ),
    }
