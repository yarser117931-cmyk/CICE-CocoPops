
from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from .config import Settings


class OdooClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _require_key(self) -> None:
        key = self.settings.odoo_api_key
        if not key or key == "PEGA_AQUI_TU_CLAVE_API":
            raise HTTPException(
                status_code=503,
                detail="Falta configurar ODOO_API_KEY en Render.",
            )

    async def call(
        self,
        model: str,
        method: str,
        payload: dict[str, Any],
    ) -> Any:
        self._require_key()

        url = f"{self.settings.odoo_url}/json/2/{model}/{method}"
        headers = {
            "Authorization": f"bearer {self.settings.odoo_api_key}",
            "X-Odoo-Database": self.settings.odoo_database,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Odoo respondió {response.status_code}: "
                    f"{response.text[:600]}"
                ),
            )

        return response.json()
