from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from pages import AllResults, all_results

Walk = Callable[[httpx.AsyncClient, str], AsyncIterator[dict[str, Any]]]


class FakeCatalog:
    """A paginated API with the same shape as PokeAPI: count, next, previous, results."""

    def __init__(self, names: list[str], page_size: int = 2, broken_page: int | None = None) -> None:
        self.names = names
        self.page_size = page_size
        self.broken_page = broken_page
        self.pages_requested: list[int] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        self.pages_requested.append(page)
        if page == self.broken_page:
            return httpx.Response(500)
        start = (page - 1) * self.page_size
        has_more = start + self.page_size < len(self.names)
        return httpx.Response(200, json={
            "count": len(self.names),
            "next": f"https://catalog.test/items?page={page + 1}" if has_more else None,
            "previous": None,
            "results": [{"name": n} for n in self.names[start:start + self.page_size]],
        })

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(self.handle))


@pytest.fixture(params=[AllResults, all_results], ids=["class", "generator"])
def walk(request: pytest.FixtureRequest) -> Walk:
    """Every test runs twice: with your class (B1), then with your async generator (B2)."""
    chosen: Walk = request.param
    return chosen


@pytest.mark.asyncio
async def test_every_item_in_order(walk: Walk) -> None:
    catalog = FakeCatalog(["ant", "bee", "cat", "dog", "eel"])
    async with catalog.client() as http:
        names = [item["name"] async for item in walk(http, "/items")]
    assert names == ["ant", "bee", "cat", "dog", "eel"]
    assert catalog.pages_requested == [1, 2, 3]


@pytest.mark.asyncio
async def test_asks_for_a_page_only_when_it_needs_it(walk: Walk) -> None:
    catalog = FakeCatalog(["ant", "bee", "cat", "dog", "eel"])
    async with catalog.client() as http:
        async for item in walk(http, "/items"):
            if item["name"] == "bee":          # the last item on page 1
                break
    assert catalog.pages_requested == [1]


@pytest.mark.asyncio
async def test_empty_catalog(walk: Walk) -> None:
    catalog = FakeCatalog([])
    async with catalog.client() as http:
        names = [item["name"] async for item in walk(http, "/items")]
    assert names == []
    assert catalog.pages_requested == [1]


@pytest.mark.asyncio
async def test_a_broken_page_raises_after_the_good_ones(walk: Walk) -> None:
    catalog = FakeCatalog(["ant", "bee", "cat", "dog", "eel"], broken_page=2)
    names: list[str] = []
    async with catalog.client() as http:
        with pytest.raises(httpx.HTTPStatusError):
            async for item in walk(http, "/items"):
                names.append(item["name"])
    assert names == ["ant", "bee"]