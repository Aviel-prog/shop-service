import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


class UnknownCurrency(Exception):
    """The provider doesn't know this currency code."""


class RatesUnavailable(Exception):
    """The provider is down, slow or broken. Try again later."""


class RatesClient:
    """Talks asynchronously to the Frankfurter API."""

    def __init__(self, base_url: str, timeout: float = 3.0, slow_seconds: float = 0.0) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._slow_seconds = slow_seconds

    async def __aenter__(self) -> "RatesClient":
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
            return await self._fetch(base, quote)
        except httpx.HTTPError as exc:
            raise RatesUnavailable(str(exc)) from exc

    async def iter_rates(
        self,
        base: str,
        quotes: list[str] | None = None,
        page_size: int = 10,
    ) -> AsyncIterator[tuple[str, float]]:
        """
        Lazily yields (quote_currency, rate) pairs page by page.
        Fetches the next page only when current-page items are exhausted
        and the caller requests another item.
        """
        page: int | None = 1
        params: dict[str, str | int] = {"base": base.upper(), "page": page, "per_page": page_size}
        if quotes:
            params["symbols"] = ",".join(c.upper() for c in quotes)

        while page is not None:
            params["page"] = page
            try:
                payload = await self._fetch_page(params)
            except httpx.HTTPError as exc:
                raise RatesUnavailable(str(exc)) from exc

            rates_map: dict[str, float] = payload.get("rates", {})
            if not rates_map:
                break

            for quote, rate_val in rates_map.items():
                yield quote.upper(), float(rate_val)

            next_page = payload.get("next_page")
            page = int(next_page) if next_page is not None else None

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_fixed(0.2),
        reraise=True,
    )
    async def _fetch(self, base: str, quote: str) -> float:
        if self._slow_seconds:
            await asyncio.sleep(self._slow_seconds)
        response = await self._http.get(f"/v2/rate/{base}/{quote}")
        if response.status_code == 422:
            raise UnknownCurrency(quote)
        response.raise_for_status()
        return float(response.json()["rate"])

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_fixed(0.2),
        reraise=True,
    )
    async def _fetch_page(self, params: dict[str, str | int]) -> dict:
        if self._slow_seconds:
            await asyncio.sleep(self._slow_seconds)
        response = await self._http.get("/v2/rates", params=params)
        if response.status_code == 422:
            raise UnknownCurrency(str(params.get("symbols", "")))
        response.raise_for_status()
        return response.json()