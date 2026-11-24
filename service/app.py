import asyncio
import inspect
import threading
from concurrent.futures import Executor
from typing import Protocol, runtime_checkable

from dataclasses import asdict, dataclass
from flask import Flask, request
from flask.typing import ResponseReturnValue

from rates import RatesUnavailable, UnknownCurrency
from reports import sales_report


@runtime_checkable
class RateSource(Protocol):
    async def rate(self, base: str, quote: str) -> float: ...


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    currency: str


stock: dict[str, int] = {}
stock_lock = threading.Lock()


async def _fetch_rate(rates: RateSource, base: str, quote: str) -> float:
    """Safely fetch a rate whether the underlying rates source is async or sync (tests)."""
    if base == quote:
        return 1.0
    if asyncio.iscoroutinefunction(rates.rate):
        return await rates.rate(base, quote)
    res = await asyncio.to_thread(rates.rate, base, quote)
    if inspect.isawaitable(res):
        return await res
    return res  # type: ignore[return-value]


def create_app(rates: RateSource, cpu_pool: Executor | None = None) -> Flask:
    app = Flask(__name__)
    products: dict[str, Product] = {}

    @app.post("/products")  # type: ignore
    async def add_product() -> ResponseReturnValue:
        data = request.get_json()
        product = Product(
            sku=data["sku"],
            name=data["name"],
            price_cents=int(data["price_cents"]),
            currency=data["currency"].upper(),
        )
        products[product.sku] = product
        return asdict(product), 201

    @app.get("/products/<sku>")  # type: ignore
    async def get_product(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        return asdict(products[sku])

    @app.get("/products/<sku>/price")  # type: ignore
    async def get_price(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        product = products[sku]
        raw_currency = request.args.get("currency", "").strip()
        target = raw_currency.upper() if raw_currency else product.currency

        try:
            rate = await _fetch_rate(rates, product.currency, target)
        except UnknownCurrency:
            return {"error": f"unknown currency {target}"}, 400
        except RatesUnavailable:
            return {"error": "rates unavailable"}, 502

        return {
            "sku": sku,
            "currency": target,
            "price_cents": round(product.price_cents * rate),
        }

    @app.get("/products/<sku>/prices")  # type: ignore
    async def get_prices(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        product = products[sku]

        wanted = [c.strip().upper() for c in request.args.get("currencies", "").split(",") if c.strip()]
        if len(wanted) > 10:
            return {"error": "at most 10 currencies per request"}, 400

        async def fetch_one(currency: str) -> tuple[str, int]:
            rate = await _fetch_rate(rates, product.currency, currency)
            return currency, round(product.price_cents * rate)

        prices: dict[str, int] = {}
        errors: dict[str, str] = {}

        # Concurrently fetch all requested rates using asyncio.gather
        tasks = [fetch_one(c) for c in wanted]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for currency, res in zip(wanted, results):
            if isinstance(res, UnknownCurrency):
                errors[currency] = "unknown currency"
            elif isinstance(res, RatesUnavailable):
                errors[currency] = "rates unavailable"
            elif isinstance(res, Exception):
                errors[currency] = "rates unavailable"
            else:
                curr_code, val = res
                prices[curr_code] = val

        return {"sku": sku, "prices": prices, "errors": errors}

    @app.get("/products/<sku>/prices/lazy")  # type: ignore
    async def get_prices_lazy(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        product = products[sku]

        wanted = {c.strip().upper() for c in request.args.get("currencies", "").split(",") if c.strip()}
        if not wanted:
            return {"error": "currencies query param required"}, 400
        if len(wanted) > 10:
            return {"error": "at most 10 currencies per request"}, 400

        iter_fn = getattr(rates, "iter_rates", None)
        if iter_fn is None or not inspect.isasyncgenfunction(iter_fn):
            return {"error": "rate source does not support lazy iteration"}, 501

        prices: dict[str, int] = {}
        if product.currency in wanted:
            prices[product.currency] = product.price_cents

        try:
            async for curr_code, rate in iter_fn(product.currency, list(wanted - prices.keys())):
                if curr_code in wanted and curr_code not in prices:
                    prices[curr_code] = round(product.price_cents * rate)
                # Stop fetching further pages once all requested currencies are found
                if len(prices) == len(wanted):
                    break
        except UnknownCurrency as exc:
            return {"error": f"unknown currency {exc}"}, 400
        except RatesUnavailable:
            return {"error": "rates unavailable"}, 502

        missing = sorted(wanted - prices.keys())
        return {
            "sku": sku,
            "prices": prices,
            "missing": missing,
        }

    @app.put("/products/<sku>/stock")  # type: ignore
    async def set_stock(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        with stock_lock:
            stock[sku] = int(request.get_json()["quantity"])
        return {"sku": sku, "stock": stock[sku]}

    @app.get("/products/<sku>/stock")  # type: ignore
    async def get_stock(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        return {"sku": sku, "stock": stock.get(sku, 0)}

    @app.post("/products/<sku>/reserve")  # type: ignore
    async def reserve(sku: str) -> ResponseReturnValue:
        if sku not in products:
            return {"error": f"no product {sku}"}, 404
        product = products[sku]
        data = request.get_json()
        quantity = int(data["quantity"])
        currency = data.get("currency", product.currency).upper()

        with stock_lock:  # 1. check and take
            if stock.get(sku, 0) < quantity:
                return {"error": "not enough stock"}, 409
            stock[sku] -= quantity
        try:  # 2. slow work asynchronously, with the lock released
            rate = await _fetch_rate(rates, product.currency, currency)
        except (UnknownCurrency, RatesUnavailable) as exc:
            with stock_lock:  # give back
                stock[sku] += quantity
            if isinstance(exc, UnknownCurrency):
                return {"error": f"unknown currency {currency}"}, 400
            return {"error": "exchange rates are unavailable, try again later"}, 502
        return {"sku": sku, "quantity": quantity, "currency": currency,
                "price_cents": round(product.price_cents * quantity * rate)}, 201

    @app.get("/reports/sales")  # type: ignore
    async def get_sales_report() -> ResponseReturnValue:
        orders = int(request.args.get("orders", "400000"))
        if cpu_pool is None:  # no pool given (tests): just run it here
            return sales_report(orders)

        # Run CPU-heavy work asynchronously in the process pool without blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(cpu_pool, sales_report, orders)

    return app
