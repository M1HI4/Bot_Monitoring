from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.config.service import ConfigService
from app.utils.exceptions import PrometheusRequestError

logger = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service
        self._client: httpx.AsyncClient | None = None

    async def query_value(self, query: str) -> float | None:
        payload = await self._request_json("/api/v1/query", params={"query": query})
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        value = result[0].get("value", [])
        if len(value) < 2:
            return None
        return float(value[1])

    async def check_health(self) -> tuple[bool, str]:
        try:
            response = await self._request("/-/healthy")
        except PrometheusRequestError as exc:
            return False, str(exc)
        if response.status_code == 200:
            return True, "Prometheus healthy"
        return False, f"HTTP {response.status_code}"

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request_json(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._request(endpoint=endpoint, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise PrometheusRequestError("Prometheus returned invalid JSON.") from exc
        if payload.get("status") != "success":
            error = payload.get("error") or "unknown error"
            raise PrometheusRequestError(f"Prometheus API error: {error}")
        return payload

    async def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> httpx.Response:
        config = self.config_service.load_runtime_config()
        client = await self._get_client(timeout=config.prometheus.timeout_seconds)
        url = f"{config.prometheus.base_url.rstrip('/')}{endpoint}"
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise PrometheusRequestError("Таймаут при обращении к Prometheus.") from exc
        except httpx.HTTPStatusError as exc:
            raise PrometheusRequestError(f"Prometheus returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            logger.warning("Prometheus request failed: %s", exc)
            raise PrometheusRequestError("Prometheus недоступен.") from exc

    async def _get_client(self, timeout: float) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=timeout)
        else:
            self._client.timeout = httpx.Timeout(timeout)
        return self._client
