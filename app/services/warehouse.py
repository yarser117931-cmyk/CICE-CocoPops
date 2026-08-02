
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base, engine


class DimCategory(Base):
    __tablename__ = "dw_dim_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    executive_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DimProduct(Base):
    __tablename__ = "dw_dim_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    odoo_product_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(100), default="")
    name: Mapped[str] = mapped_column(String(300), index=True)
    original_category: Mapped[str] = mapped_column(String(250), default="")
    executive_category: Mapped[str] = mapped_column(String(200), index=True)
    uom: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FactInventoryDaily(Base):
    __tablename__ = "dw_fact_inventory_daily"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_date",
            "odoo_product_id",
            name="uq_inventory_day_product",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    odoo_product_id: Mapped[int] = mapped_column(Integer, index=True)

    available: Mapped[float] = mapped_column(Float, default=0)
    on_hand: Mapped[float] = mapped_column(Float, default=0)
    reserved: Mapped[float] = mapped_column(Float, default=0)
    minimum: Mapped[float] = mapped_column(Float, default=0)
    maximum: Mapped[float] = mapped_column(Float, default=0)
    missing_to_minimum: Mapped[float] = mapped_column(Float, default=0)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FactExecutiveDaily(Base):
    __tablename__ = "dw_fact_executive_daily"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_date",
            "category_name",
            name="uq_executive_day_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    category_name: Mapped[str] = mapped_column(String(200), index=True)

    products: Mapped[int] = mapped_column(Integer, default=0)
    products_with_minimum: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[float] = mapped_column(Float, default=0)
    on_hand: Mapped[float] = mapped_column(Float, default=0)
    reserved: Mapped[float] = mapped_column(Float, default=0)
    minimum: Mapped[float] = mapped_column(Float, default=0)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical: Mapped[int] = mapped_column(Integer, default=0)
    below_minimum: Mapped[int] = mapped_column(Integer, default=0)
    at_risk: Mapped[int] = mapped_column(Integer, default=0)
    healthy: Mapped[int] = mapped_column(Integer, default=0)
    without_minimum: Mapped[int] = mapped_column(Integer, default=0)

    production_orders: Mapped[int] = mapped_column(Integer, default=0)
    production_planned: Mapped[float] = mapped_column(Float, default=0)
    production_done: Mapped[float] = mapped_column(Float, default=0)
    production_progress: Mapped[float] = mapped_column(Float, default=0)

    sales_total: Mapped[float] = mapped_column(Float, default=0)
    sales_orders: Mapped[int] = mapped_column(Integer, default=0)
    sales_customers: Mapped[int] = mapped_column(Integer, default=0)
    invoiced_today: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def initialize_warehouse() -> None:
    if engine is not None:
        Base.metadata.create_all(engine)


def warehouse_enabled() -> bool:
    return engine is not None


def save_warehouse_snapshot(
    snapshot_date: date,
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
) -> dict[str, Any]:
    if engine is None:
        return {
            "enabled": False,
            "saved_products": 0,
            "saved_categories": 0,
            "message": "No existe una DATABASE_URL persistente.",
        }

    products = inventory["products"]
    categories = [inventory["global"], *inventory["categories"]]

    saved_products = 0
    saved_categories = 0

    with Session(engine) as session:
        for product in products:
            product_id = int(product["id"])

            dimension = session.execute(
                select(DimProduct).where(
                    DimProduct.odoo_product_id == product_id
                )
            ).scalar_one_or_none()

            if dimension is None:
                session.add(
                    DimProduct(
                        odoo_product_id=product_id,
                        code=product.get("code") or "",
                        name=product.get("name") or "",
                        original_category=product.get("original_category") or "",
                        executive_category=product.get("category") or "",
                        uom=product.get("uom") or "",
                    )
                )
            else:
                dimension.code = product.get("code") or ""
                dimension.name = product.get("name") or ""
                dimension.original_category = (
                    product.get("original_category") or ""
                )
                dimension.executive_category = product.get("category") or ""
                dimension.uom = product.get("uom") or ""

            existing = session.execute(
                select(FactInventoryDaily).where(
                    FactInventoryDaily.snapshot_date == snapshot_date,
                    FactInventoryDaily.odoo_product_id == product_id,
                )
            ).scalar_one_or_none()

            values = {
                "available": float(product.get("available") or 0),
                "on_hand": float(product.get("on_hand") or 0),
                "reserved": float(product.get("reserved") or 0),
                "minimum": float(product.get("minimum") or 0),
                "maximum": float(product.get("maximum") or 0),
                "missing_to_minimum": float(product.get("missing_to_minimum") or 0),
                "coverage_pct": product.get("coverage_pct"),
                "status": product.get("status") or "SIN_DATOS",
            }
            if existing is None:
                existing = FactInventoryDaily(
                    snapshot_date=snapshot_date,
                    odoo_product_id=product_id,
                )
                session.add(existing)
                saved_products += 1
            for field, value in values.items():
                setattr(existing, field, value)

        for category in categories:
            category_name = category.get("name") or "TODOS"

            existing = session.execute(
                select(FactExecutiveDaily).where(
                    FactExecutiveDaily.snapshot_date == snapshot_date,
                    FactExecutiveDaily.category_name == category_name,
                )
            ).scalar_one_or_none()

            values = {
                "products": int(category.get("products") or 0),
                "products_with_minimum": int(category.get("products_with_minimum") or 0),
                "available": float(category.get("available") or 0),
                "on_hand": float(category.get("on_hand") or 0),
                "reserved": float(category.get("reserved") or 0),
                "minimum": float(category.get("minimum") or 0),
                "coverage_pct": category.get("coverage_pct"),
                "critical": int(category.get("critical") or 0),
                "below_minimum": int(category.get("below_minimum") or 0),
                "at_risk": int(category.get("at_risk") or 0),
                "healthy": int(category.get("healthy") or 0),
                "without_minimum": int(category.get("without_minimum") or 0),
                "production_orders": int(production.get("orders") or 0),
                "production_planned": float(production.get("planned") or 0),
                "production_done": float(production.get("done") or 0),
                "production_progress": float(production.get("progress") or 0),
                "sales_total": float(sales.get("total") or 0),
                "sales_orders": int(sales.get("orders") or 0),
                "sales_customers": int(sales.get("customers") or 0),
                "invoiced_today": float(sales.get("invoiced_today") or 0),
            }
            if existing is None:
                existing = FactExecutiveDaily(
                    snapshot_date=snapshot_date,
                    category_name=category_name,
                )
                session.add(existing)
                saved_categories += 1
            for field, value in values.items():
                setattr(existing, field, value)

        session.commit()

    return {
        "enabled": True,
        "saved_products": saved_products,
        "saved_categories": saved_categories,
        "message": "Fotografía diaria enviada al Data Warehouse.",
    }


def inventory_history(
    product_id: int | None = None,
    days: int = 90,
) -> list[dict[str, Any]]:
    if engine is None:
        return []

    safe_days = max(1, min(days, 730))

    with Session(engine) as session:
        query = select(FactInventoryDaily).order_by(
            FactInventoryDaily.snapshot_date.desc()
        )

        if product_id is not None:
            query = query.where(
                FactInventoryDaily.odoo_product_id == product_id
            )

        rows = session.execute(query.limit(safe_days)).scalars().all()

    rows.reverse()

    return [
        {
            "date": row.snapshot_date.isoformat(),
            "product_id": row.odoo_product_id,
            "available": row.available,
            "on_hand": row.on_hand,
            "reserved": row.reserved,
            "minimum": row.minimum,
            "missing_to_minimum": row.missing_to_minimum,
            "coverage_pct": row.coverage_pct,
            "status": row.status,
        }
        for row in rows
    ]


def executive_history(
    category: str = "TODOS",
    days: int = 90,
) -> list[dict[str, Any]]:
    if engine is None:
        return []

    safe_days = max(1, min(days, 730))

    with Session(engine) as session:
        rows = session.execute(
            select(FactExecutiveDaily)
            .where(FactExecutiveDaily.category_name == category)
            .order_by(FactExecutiveDaily.snapshot_date.desc())
            .limit(safe_days)
        ).scalars().all()

    rows.reverse()

    return [
        {
            "date": row.snapshot_date.isoformat(),
            "category": row.category_name,
            "products": row.products,
            "available": row.available,
            "minimum": row.minimum,
            "coverage_pct": row.coverage_pct,
            "critical": row.critical,
            "below_minimum": row.below_minimum,
            "healthy": row.healthy,
            "production_progress": row.production_progress,
            "sales_total": row.sales_total,
            "sales_orders": row.sales_orders,
        }
        for row in rows
    ]


def export_executive_csv(category: str = "TODOS", days: int = 365) -> str:
    rows = executive_history(category=category, days=days)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "date",
            "category",
            "products",
            "available",
            "minimum",
            "coverage_pct",
            "critical",
            "below_minimum",
            "healthy",
            "production_progress",
            "sales_total",
            "sales_orders",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
