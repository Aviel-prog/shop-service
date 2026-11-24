from collections import deque
from collections.abc import AsyncIterator
from typing import Any

import httpx

Item = dict[str, Any]


def _extract_page(payload: dict[str, Any]) -> tuple[list[Item], str | None]:
    items = payload.get("results") if "results" in payload else payload.get("items", [])
    next_url = payload.get("next")
    return list(items), next_url


class AllResults:
    """Part B1. Every item from a paginated API, fetching one page at a time:

        async for item in AllResults(http, "/api/v2/pokemon?limit=100"):
            ...
    """

    def __init__(self, http: httpx.AsyncClient, first_url: str) -> None:
        self._http = http
        self._next_url: str | None = first_url
        self._items: deque[Item] = deque()

    def __aiter__(self) -> "AllResults":
        return self

    async def __anext__(self) -> Item:
        while not self._items:
            if self._next_url is None:
                raise StopAsyncIteration

            response = await self._http.get(self._next_url)
            response.raise_for_status()

            page_items, self._next_url = _extract_page(response.json())
            self._items.extend(page_items)

        return self._items.popleft()


async def all_results(http: httpx.AsyncClient, url: str | None) -> AsyncIterator[Item]:
    """Part B2: async generator yielding every item lazily across pages."""
    next_url = url
    while next_url is not None:
        response = await http.get(next_url)
        response.raise_for_status()

        page_items, next_url = _extract_page(response.json())
        for item in page_items:
            yield item
