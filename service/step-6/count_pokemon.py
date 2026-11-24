import asyncio

import httpx

from pages import all_results


async def show(request: httpx.Request) -> None:
    print("  GET", request.url)


async def main() -> None:
    names: list[str] = []
    async with httpx.AsyncClient(
        base_url="https://pokeapi.co",
        timeout=10,
        event_hooks={"request": [show]},
    ) as http:
        async for p in all_results(http, "/api/v2/pokemon?limit=200"):
            names.append(p["name"])
            if len(names) >= 250:
                break

    print(len(names), "pokemon. First:", names[0], " Last:", names[-1])


asyncio.run(main())