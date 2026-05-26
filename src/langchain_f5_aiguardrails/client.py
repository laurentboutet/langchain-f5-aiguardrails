"""HTTP client for the F5 AI Guardrails scan API.

Provides :class:`F5GuardrailClient` — an async-first (with sync wrapper)
client for ``POST /backend/v1/scans``.  HTTP connections are created lazily
and managed via ``httpx.Client`` / ``httpx.AsyncClient``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import GuardrailConfig
from .exceptions import (
    F5GuardrailAPIError,
    F5GuardrailAuthError,
    F5GuardrailTimeoutError,
)
from .types import ScanRequest, ScanResponse

logger = logging.getLogger("langchain_f5_aiguardrails.client")

_SCAN_PATH = "/backend/v1/scans"


class F5GuardrailClient:
    """Client for the F5 AI Guardrails scan API.

    Example::

        client = F5GuardrailClient(
            api_key="my-key",
            base_url="https://us1.calypsoai.app",
        )
        response = client.scan(ScanRequest(input="Hello world"))
        print(response.outcome)  # "cleared"
        client.close()

    Async usage::

        response = await client.scan_async(ScanRequest(input="Hello world"))
        await client.close_async()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://us1.calypsoai.app",
        project: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._project = project
        self._timeout = timeout
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lazy client creation
    # ------------------------------------------------------------------

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=httpx.Timeout(self._timeout),
            )
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=httpx.Timeout(self._timeout),
            )
        return self._async_client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------

    def _build_payload(self, request: ScanRequest) -> dict[str, Any]:
        """Convert a :class:`ScanRequest` into the JSON body for the API."""
        payload = request.to_api_payload()
        # Inject default project when request does not specify one.
        if self._project and "project" not in payload:
            payload["project"] = self._project
        return payload

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> ScanResponse:
        """Parse the API JSON into a validated :class:`ScanResponse`."""
        return ScanResponse.model_validate(data)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Raise typed exceptions for known HTTP error codes."""
        if response.status_code in (401, 403):
            raise F5GuardrailAuthError(
                f"HTTP {response.status_code}: {response.text}"
            )
        if response.status_code >= 400:
            raise F5GuardrailAPIError(
                f"F5 scan API returned HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )

    # ------------------------------------------------------------------
    # Sync scan
    # ------------------------------------------------------------------

    def scan(self, request: ScanRequest) -> ScanResponse:
        """Send a synchronous scan request.

        Args:
            request: The scan request payload.

        Returns:
            The parsed scan response.

        Raises:
            F5GuardrailAuthError: On 401/403.
            F5GuardrailAPIError: On other HTTP errors.
            F5GuardrailTimeoutError: On request timeout.
        """
        payload = self._build_payload(request)
        logger.debug("Scanning content (sync): %d chars", len(request.input))

        try:
            client = self._get_sync_client()
            resp = client.post(_SCAN_PATH, json=payload)
            self._raise_for_status(resp)
            return self._parse_response(resp.json())
        except httpx.TimeoutException as exc:
            raise F5GuardrailTimeoutError(
                f"Scan request timed out after {self._timeout}s",
                timeout=self._timeout,
            ) from exc

    # ------------------------------------------------------------------
    # Async scan
    # ------------------------------------------------------------------

    async def scan_async(self, request: ScanRequest) -> ScanResponse:
        """Send an asynchronous scan request.

        Args:
            request: The scan request payload.

        Returns:
            The parsed scan response.

        Raises:
            F5GuardrailAuthError: On 401/403.
            F5GuardrailAPIError: On other HTTP errors.
            F5GuardrailTimeoutError: On request timeout.
        """
        payload = self._build_payload(request)
        logger.debug("Scanning content (async): %d chars", len(request.input))

        try:
            client = self._get_async_client()
            resp = await client.post(_SCAN_PATH, json=payload)
            self._raise_for_status(resp)
            return self._parse_response(resp.json())
        except httpx.TimeoutException as exc:
            raise F5GuardrailTimeoutError(
                f"Scan request timed out after {self._timeout}s",
                timeout=self._timeout,
            ) from exc

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the synchronous HTTP client and release connections."""
        if self._sync_client is not None and not self._sync_client.is_closed:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        """Close the asynchronous HTTP client and release connections."""
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: GuardrailConfig,
        *,
        direction: str = "request",
    ) -> F5GuardrailClient:
        """Create a client from a :class:`GuardrailConfig` instance.

        Args:
            config: The validated configuration.
            direction: Which API key to use — ``"request"`` or ``"response"``.
                Defaults to ``"request"``.

        Returns:
            A configured :class:`F5GuardrailClient`.
        """
        if direction == "response":
            api_key = config.api_key_response
        else:
            api_key = config.api_key_request
        return cls(
            api_key=api_key,
            base_url=config.base_url,
            project=config.project,
            timeout=config.timeout,
        )

    @classmethod
    def from_env(cls, *, direction: str = "request") -> F5GuardrailClient:
        """Create a client from ``F5_GUARDRAIL_*`` environment variables.

        Args:
            direction: Which API key to use — ``"request"`` or ``"response"``.
                Defaults to ``"request"``.
        """
        config = GuardrailConfig.from_env()
        return cls.from_config(config, direction=direction)
