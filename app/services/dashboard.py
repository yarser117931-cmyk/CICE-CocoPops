from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from time import monotonic, perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from app.config import Settings
from app.odoo import OdooClient
from app.services.history import capture_snapshot
from app.services.intelligence import build_intelligence
from app.services.inventory import build_inventory
from app.services.priorities import build_ceo_priorities
from app.services.production import build_production
from app.services.sales import build_sales
from app.services.warehouse import save_warehouse_snapshot


class DashboardService:
    """Builds one consistent operational snapshot and briefly caches it."""

    def __init__(
        self,
        settings: Settings,
        odoo: OdooClient,
        cache_seconds: int = 45,
    ) -> None:
        self.settings = settings
        self.odoo = odoo
        self.cache_seconds = cache_seconds
        self._cache: dict[str, Any] | None = None
        self._cache_time = 0.0
        self._lock = asyncio.Lock()

    async def get_snapshot(self, force: bool = False) -> dict[str, Any]:
        now_mono = monotonic()
        if (
            not force
            and self._cache is not None
            and now_mono - self._cache_time < self.cache_seconds
        ):
            result = deepcopy(self._cache)
            result["cache"] = {"hit": True, "ttl_seconds": self.cache_seconds}
            return result

        async with self._lock:
            now_mono = monotonic()
            if (
                not force
                and self._cache is not None
                and now_mono - self._cache_time < self.cache_seconds
            ):
                result = deepcopy(self._cache)
                result["cache"] = {"hit": True, "ttl_seconds": self.cache_seconds}
                return result

            started_at = perf_counter()
            timezone = ZoneInfo(self.settings.timezone)
            now = datetime.now(timezone)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

            inventory, production, sales = await asyncio.gather(
                build_inventory(self.odoo),
                build_production(self.odoo, start, end),
                build_sales(self.odoo, start, end),
            )

            intelligence = build_intelligence(inventory, production, sales)
            ceo_priorities = build_ceo_priorities(inventory, production, sales)

            # These functions safely no-op when DATABASE_URL is absent.
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

            snapshot: dict[str, Any] = {
                "generated_at": now.isoformat(),
                "query_duration_ms": round((perf_counter() - started_at) * 1000),
                "source": {"system": "Odoo"},
                "inventory": inventory,
                "production": production,
                "sales": sales,
                "history": history,
                "warehouse": warehouse,
                "ceo_priorities": ceo_priorities,
                "cache": {"hit": False, "ttl_seconds": self.cache_seconds},
                **intelligence,
            }
            self._cache = deepcopy(snapshot)
            self._cache_time = monotonic()
            return snapshot
