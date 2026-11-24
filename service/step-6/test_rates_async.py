import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import httpx
import pytest

from rates_async import AsyncRatesClient, open_rates


def fake_frankfurter(request: httpx.Request) -> httpx.Response:
    """Stands in for Frankfurter. Knows one rate: EUR -> USD."""
    if request.url.path == "/v2/rate/EUR/USD":
        return httpx.Response(200, json={"base": "EUR", "quote": "USD", "rate": 1.10})
    return httpx.Response(422)


FAKE = httpx.MockTransport(fake_frankfurter)
Opener = Callable[[], AbstractAsyncContextManager[AsyncRatesClient]]


@pytest.fixture(params=["class", "function"])
def open_client(request: pytest.FixtureRequest) -> Opener:
    """Every test runs twice: with your class (A1), then with open_rates (A2)."""
    if request.param == "class":
        return lambda: AsyncRatesClient("https://frankfurter.test", transport=FAKE)
    return lambda: open_rates("https://frankfurter.test", transport=FAKE)


@pytest.mark.asyncio
async def test_works_inside_the_block(open_client: Opener) -> None:
    async with open_client() as rates:
        assert await rates.rate("EUR", "USD") == 1.10
        assert not rates.is_closed


@pytest.mark.asyncio
async def test_closed_after_the_block(open_client: Opener) -> None:
    async with open_client() as rates:
        await rates.rate("EUR", "USD")
    assert rates.is_closed


@pytest.mark.asyncio
async def test_closed_when_the_block_fails_and_the_error_still_comes_out(open_client: Opener) -> None:
    with pytest.raises(ZeroDivisionError):
        async with open_client() as rates:
            1 / 0
    assert rates.is_closed


@pytest.mark.asyncio
async def test_closed_when_the_task_is_cancelled(open_client: Opener) -> None:
    clients: list[AsyncRatesClient] = []

    async def handler() -> None:
        async with open_client() as rates:
            clients.append(rates)
            await asyncio.sleep(60)          # a slow call -- it gets cancelled long before

    task = asyncio.create_task(handler())
    await asyncio.wait([task], timeout=0.1)  # let it get inside the block (returns early if it crashed)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert clients[0].is_closed