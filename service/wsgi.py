import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor

from app import create_app
from rates import RatesClient

total_cores = os.cpu_count() or 1
# CPU-heavy work runs in these processes. 'forkserver' is the default on Linux from
# Python 3.14; setting ittotal_coreshere gives you the same behaviour on 3.13. (Step 5 explains why.)
cpu_pool = ProcessPoolExecutor(max_workers=total_cores, mp_context=multiprocessing.get_context("forkserver"))

app = create_app(
    RatesClient(
        base_url=os.environ.get("RATES_URL", "https://api.frankfurter.dev"),
        slow_seconds=float(os.environ.get("SLOW_RATES_SECONDS", "0")),
    ),
    cpu_pool=cpu_pool,
)

# Demo data, created at startup. Each gunicorn worker runs this file separately,
# so every worker gets its own copy of the widget, and its own 5 in stock.
demo = app.test_client()
demo.post("/products", json={"sku": "widget", "name": "Widget", "price_cents": 1000, "currency": "EUR"})
demo.put("/products/widget/stock", json={"quantity": 5})