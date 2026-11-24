from concurrent.futures import ProcessPoolExecutor

from m7.C.service.app import create_app


class NoRates:
    def rate(self, base: str, quote: str) -> float:
        raise AssertionError("the report never needs exchange rates")


def test_report() -> None:
    client = create_app(NoRates()).test_client()  # no pool: the report runs right here
    report = client.get("/reports/sales?orders=1000").json
    assert report is not None
    assert report["orders"] == 1000
    assert len(report["top"]) == 3


def test_report_in_a_real_process_pool() -> None:
    # The test above can't catch a pickling mistake: nothing is pickled there. This one can.
    expected = create_app(NoRates()).test_client().get("/reports/sales?orders=1000").json
    with ProcessPoolExecutor(max_workers=1) as pool:
        client = create_app(NoRates(), cpu_pool=pool).test_client()
        response = client.get("/reports/sales?orders=1000")
    assert response.status_code == 200
    assert response.json == expected
