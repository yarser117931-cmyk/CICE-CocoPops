
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    odoo_url: str
    odoo_database: str
    odoo_api_key: str
    timezone: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            odoo_url=os.getenv(
                "ODOO_URL",
                "https://cocopopsmx1.odoo.com",
            ).rstrip("/"),
            odoo_database=os.getenv("ODOO_DATABASE", "cocopopsmx1"),
            odoo_api_key=os.getenv("ODOO_API_KEY", ""),
            timezone=os.getenv("TIMEZONE", "America/Chihuahua"),
        )
