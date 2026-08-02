
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


class Base(DeclarativeBase):
    pass


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    inventory_available: Mapped[float] = mapped_column(Float, default=0)
    inventory_on_hand: Mapped[float] = mapped_column(Float, default=0)
    inventory_reserved: Mapped[float] = mapped_column(Float, default=0)
    inventory_minimum: Mapped[float] = mapped_column(Float, default=0)

    products_total: Mapped[int] = mapped_column(Integer, default=0)
    products_critical: Mapped[int] = mapped_column(Integer, default=0)
    products_below_minimum: Mapped[int] = mapped_column(Integer, default=0)
    products_at_risk: Mapped[int] = mapped_column(Integer, default=0)
    products_healthy: Mapped[int] = mapped_column(Integer, default=0)
    products_without_minimum: Mapped[int] = mapped_column(Integer, default=0)

    production_orders: Mapped[int] = mapped_column(Integer, default=0)
    production_planned: Mapped[float] = mapped_column(Float, default=0)
    production_done: Mapped[float] = mapped_column(Float, default=0)
    production_progress: Mapped[float] = mapped_column(Float, default=0)

    sales_total: Mapped[float] = mapped_column(Float, default=0)
    sales_orders: Mapped[int] = mapped_column(Integer, default=0)
    sales_customers: Mapped[int] = mapped_column(Integer, default=0)
    invoiced_today: Mapped[float] = mapped_column(Float, default=0)


def database_enabled() -> bool:
    return bool(DATABASE_URL)


engine = (
    create_engine(DATABASE_URL, pool_pre_ping=True)
    if database_enabled()
    else None
)


def initialize_database() -> None:
    if engine is not None:
        Base.metadata.create_all(engine)


def save_daily_snapshot(
    snapshot_date: date,
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
) -> bool:
    if engine is None:
        return False

    summary = inventory["global"]

    with Session(engine) as session:
        existing = session.query(DailySnapshot).filter_by(
            snapshot_date=snapshot_date
        ).first()

        if existing is not None:
            return False

        session.add(
            DailySnapshot(
                snapshot_date=snapshot_date,
                inventory_available=float(summary.get("available") or 0),
                inventory_on_hand=float(summary.get("on_hand") or 0),
                inventory_reserved=float(summary.get("reserved") or 0),
                inventory_minimum=float(summary.get("minimum") or 0),
                products_total=int(summary.get("products") or 0),
                products_critical=int(summary.get("critical") or 0),
                products_below_minimum=int(summary.get("below_minimum") or 0),
                products_at_risk=int(summary.get("at_risk") or 0),
                products_healthy=int(summary.get("healthy") or 0),
                products_without_minimum=int(summary.get("without_minimum") or 0),
                production_orders=int(production.get("orders") or 0),
                production_planned=float(production.get("planned") or 0),
                production_done=float(production.get("done") or 0),
                production_progress=float(production.get("progress") or 0),
                sales_total=float(sales.get("total") or 0),
                sales_orders=int(sales.get("orders") or 0),
                sales_customers=int(sales.get("customers") or 0),
                invoiced_today=float(sales.get("invoiced_today") or 0),
            )
        )
        session.commit()
        return True


def read_trends(days: int = 30) -> list[dict[str, Any]]:
    if engine is None:
        return []

    safe_days = max(1, min(days, 365))

    with Session(engine) as session:
        rows = (
            session.query(DailySnapshot)
            .order_by(DailySnapshot.snapshot_date.desc())
            .limit(safe_days)
            .all()
        )

    rows.reverse()

    return [
        {
            "date": row.snapshot_date.isoformat(),
            "inventory_available": row.inventory_available,
            "inventory_minimum": row.inventory_minimum,
            "products_critical": row.products_critical,
            "products_below_minimum": row.products_below_minimum,
            "products_healthy": row.products_healthy,
            "production_progress": row.production_progress,
            "sales_total": row.sales_total,
            "sales_orders": row.sales_orders,
            "invoiced_today": row.invoiced_today,
        }
        for row in rows
    ]
