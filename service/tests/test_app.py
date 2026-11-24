import pytest
from flask.testing import FlaskClient

from app import create_app
from rates import RatesUnavailable, UnknownCurrency


class FakeRates:
    """Stands in for RatesClient. No network, ever."""

    def __init__(self) -> None:
        self.down = False

    def rate(self, base: str, quote: str) -> float:
        if self.down:
            raise RatesUnavailable("provider down")
        if quote == "XYZ":
            raise UnknownCurrency(quote)
        return 1.10


@pytest.fixture
def rates() -> FakeRates:
    return FakeRates()


@pytest.fixture
def client(rates: FakeRates) -> FlaskClient:
    client = create_app(rates).test_client()
    client.post("/products", json={"sku": "widget", "name": "Widget", "price_cents": 1000, "currency": "EUR"})
    return client


def test_add_and_get(client: FlaskClient) -> None:
    response = client.get("/products/widget")
    assert response.status_code == 200
    assert response.json == {"sku": "widget", "name": "Widget", "price_cents": 1000, "currency": "EUR"}


def test_missing_product(client: FlaskClient) -> None:
    assert client.get("/products/nope").status_code == 404


def test_price_in_other_currency(client: FlaskClient) -> None:
    response = client.get("/products/widget/price?currency=usd")
    assert response.json == {"sku": "widget", "currency": "USD", "price_cents": 1100}


def test_price_in_own_currency_skips_the_network(client: FlaskClient, rates: FakeRates) -> None:
    rates.down = True
    assert client.get("/products/widget/price").json == {"sku": "widget", "currency": "EUR", "price_cents": 1000}


def test_unknown_currency(client: FlaskClient) -> None:
    assert client.get("/products/widget/price?currency=XYZ").status_code == 400


def test_rates_down(client: FlaskClient, rates: FakeRates) -> None:
    rates.down = True
    response = client.get("/products/widget/price?currency=USD")
    assert response.status_code == 502