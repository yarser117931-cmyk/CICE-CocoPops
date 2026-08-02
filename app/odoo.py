from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from .config import Settings


class OdooClient:
    """Reusable asynchronous client for Odoo JSON-2 calls."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(45.0, connect=15.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

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
        await self.start()
        assert self._client is not None

        url = f"{self.settings.odoo_url}/json/2/{model}/{method}"
        headers = {
            "Authorization": f"bearer {self.settings.odoo_api_key}",
            "X-Odoo-Database": self.settings.odoo_database,
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="Odoo tardó demasiado en responder. Intenta actualizar nuevamente.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail="No fue posible comunicarse con Odoo.",
            ) from exc

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Odoo respondió {response.status_code}: "
                    f"{response.text[:400]}"
                ),
            )

        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="Odoo devolvió una respuesta que no se pudo interpretar.",
            ) from exc
