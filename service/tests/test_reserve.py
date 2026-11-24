import threading
import time

import pytest
from app import create_app
from flask import Flask
from rates import UnknownCurrency


class SlowRates:
    """The rate lookup takes a moment, like a real network call."""

    def rate(self, base: str, quote: str) -> float:
        time.sleep(0.05)
        if quote == "XYZ":
            raise UnknownCurrency(quote)
        return 1.10


@pytest.fixture
def app() -> Flask:
    app = create_app(SlowRates())
    client = app.test_client()
    client.post("/products", json={"sku": "widget", "name": "Widget", "price_cents": 1000, "currency": "EUR"})
    client.put("/products/widget/stock", json={"quantity": 5})
    return app


def test_never_sells_more_than_in_stock(app: Flask) -> None:
    customers = 20
    start_together = threading.Barrier(customers)  # every thread waits here, then all go at once
    results: list[int] = []
    results_lock = threading.Lock()

    def customer() -> None:
        client = app.test_client()  # one client per thread
        start_together.wait()
        status = client.post("/products/widget/reserve", json={"quantity": 1, "currency": "USD"}).status_code
        with results_lock:
            results.append(status)

    threads = [threading.Thread(target=customer) for _ in range(customers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(201) == 5
    assert results.count(409) == 15
    assert app.test_client().get("/products/widget/stock").json == {"sku": "widget", "stock": 0}


def test_failed_quote_gives_the_stock_back(app: Flask) -> None:
    client = app.test_client()
    response = client.post("/products/widget/reserve", json={"quantity": 2, "currency": "XYZ"})
    assert response.status_code == 400
    assert client.get("/products/widget/stock").json == {"sku": "widget", "stock": 5}
