import threading
import time

import pytest
from flask.testing import FlaskClient


from app import create_app
from rates import RatesUnavailable, UnknownCurrency


class SlowFakeRates:
    """Each call takes a moment, and the fake counts how many calls run at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()      # this fake is called from several threads -- D explains why it needs a lock
        self.in_flight = 0
        self.most_at_once = 0

    def rate(self, base: str, quote: str) -> float:
        with self._lock:
            self.in_flight += 1
            self.most_at_once = max(self.most_at_once, self.in_flight)
        try:
            time.sleep(0.05)
            if quote == "XYZ":
                raise UnknownCurrency(quote)
            if quote == "DOWN":
                raise RatesUnavailable("provider down")
            return 2.0
        finally:
            with self._lock:
                self.in_flight -= 1


@pytest.fixture
def rates() -> SlowFakeRates:
    return SlowFakeRates()


@pytest.fixture
def client(rates: SlowFakeRates) -> FlaskClient:
    client = create_app(rates).test_client()
    client.post("/products", json={"sku": "widget", "name": "Widget", "price_cents": 1000, "currency": "EUR"})
    return client


def test_prices_in_several_currencies(client: FlaskClient) -> None:
    response = client.get("/products/widget/prices?currencies=usd,GBP,EUR")
    assert response.json == {"sku": "widget", "prices": {"USD": 2000, "GBP": 2000, "EUR": 1000}, "errors": {}}


def test_lookups_run_at_the_same_time(client: FlaskClient, rates: SlowFakeRates) -> None:
    client.get("/products/widget/prices?currencies=USD,GBP,ILS,JPY")
    assert rates.most_at_once == 4


def test_one_bad_currency_does_not_spoil_the_rest(client: FlaskClient) -> None:
    response = client.get("/products/widget/prices?currencies=USD,XYZ,DOWN")
    assert response.json == {
        "sku": "widget",
        "prices": {"USD": 2000},
        "errors": {"XYZ": "unknown currency", "DOWN": "rates unavailable"},
    }


def test_too_many_currencies(client: FlaskClient) -> None:
    many = ",".join(f"C{i}" for i in range(11))
    assert client.get(f"/products/widget/prices?currencies={many}").status_code == 400