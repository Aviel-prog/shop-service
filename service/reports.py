import random
from collections import defaultdict


def load_orders(n: int, seed: int = 42) -> list[tuple[str, int, int]]:
    """Stands in for reading orders from a database: the same fake data every time."""
    rng = random.Random(seed)
    skus = [f"sku-{i}" for i in range(200)]
    return [(rng.choice(skus), rng.randint(1, 5), rng.randint(100, 10_000)) for _ in range(n)]


def sales_report(n_orders: int = 400_000, top: int = 3) -> dict[str, object]:
    """Pure Python CPU work: loops, dicts, sorting."""
    revenue: dict[str, int] = defaultdict(int)
    units: dict[str, int] = defaultdict(int)
    for sku, quantity, unit_cents in load_orders(n_orders):
        revenue[sku] += quantity * unit_cents
        units[sku] += quantity
    best = sorted(revenue.items(), key=lambda item: item[1], reverse=True)[:top]
    return {"orders": n_orders,
            "top": [{"sku": sku, "revenue_cents": cents, "units": units[sku]} for sku, cents in best]}