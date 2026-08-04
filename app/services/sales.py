from __future__ import annotations

from datetime import datetime
from typing import Any

from app.helpers import relation_name
from app.odoo import OdooClient


def _sales_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(item.get("id") or 0),
        "order": str(item.get("name") or "—"),
        "date": item.get("date_order"),
        "customer": relation_name(item.get("partner_id")) or "Cliente no identificado",
        "total": round(float(item.get("amount_total") or 0), 2),
        "invoice_status": str(item.get("invoice_status") or ""),
        "state": str(item.get("state") or ""),
        "status": (
            "FACTURADA"
            if item.get("invoice_status") == "invoiced"
            else "POR FACTURAR"
            if item.get("invoice_status") == "to invoice"
            else "SIN PENDIENTE"
        ),
    }


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
                "id",
                "name",
                "date_order",
                "partner_id",
                "amount_total",
                "invoice_status",
                "state",
            ],
            "limit": 1000,
            "order": "date_order desc",
        },
    )

    details = [_sales_detail(item) for item in sales]
    customers = {
        item["customer"]
        for item in details
        if item["customer"] and item["customer"] != "Cliente no identificado"
    }

    invoices: list[dict[str, Any]] = []
    invoice_warning = ""
    try:
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
    except Exception as error:
        invoice_warning = str(error)

    return {
        "total": round(sum(item["total"] for item in details), 2),
        "orders": len(details),
        "customers": len(customers),
        "pending_invoice": round(
            sum(
                item["total"]
                for item in details
                if item["invoice_status"] == "to invoice"
            ),
            2,
        ),
        "invoiced_today": round(
            sum(float(item.get("amount_total") or 0) for item in invoices),
            2,
        ),
        "details": details,
        "invoice_warning": invoice_warning,
    }
