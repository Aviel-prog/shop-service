from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import AsyncIterator, Any, Generator

import httpx


class UnknownCurrency(Exception):
    """The provider doesn't know this currency code."""


class RatesUnavailable(Exception):
    """The provider is down, slow or broken. Try again later."""


class AsyncRatesClient:
    """The async RatesClient from step 1, trimmed: no retries, so the file stays short."""

    def __init__(self, base_url: str, timeout: float = 3.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        # `transport`: tests pass a fake one, so no real network is used
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def __aenter__(self) -> "AsyncRatesClient":
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def rate(self, base: str, quote: str) -> float:
        try:
            response = await self._http.get(f"/v2/rate/{base}/{quote}")
        except httpx.HTTPError as exc:
            raise RatesUnavailable(str(exc)) from exc
        if response.status_code == 422:
            raise UnknownCurrency(quote)
        if response.is_error:
            raise RatesUnavailable(f"provider answered {response.status_code}")
        return float(response.json()["rate"])

    @property
    def is_closed(self) -> bool:
        return self._http.is_closed

    async def aclose(self) -> None:
        await self._http.aclose()


@asynccontextmanager
async def open_rates(base_url: str, timeout: float = 3.0,
                     transport: httpx.AsyncBaseTransport | None = None) -> AsyncIterator[AsyncRatesClient]:
    client = AsyncRatesClient(base_url, timeout, transport)
    try:
        yield client
    finally:
        await client.aclose()

