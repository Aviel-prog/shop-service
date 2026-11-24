import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing


async def rows() -> AsyncGenerator[int, None]:
    """Pretend this holds something open: a streaming HTTP response, a database cursor..."""
    print("  opened")
    try:
        for n in range(1_000):
            yield n
    finally:
        print("  closed")          # cleanup -- but WHEN does it run?


async def main() -> None:
    print("plain async for, then break:")
    async for n in rows():
        if n == 2:
            break
    print("  after the loop")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    print("  two awaits later")

    print("same thing inside aclosing():")
    async with aclosing(rows()) as numbers:
        async for n in numbers:
            if n == 2:
                break
    print("  after the loop")


asyncio.run(main())