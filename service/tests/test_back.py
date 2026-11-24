# import asyncio
#
# from m7.C.service.app import fan_out_rates
# from m7.C.service.rates import RatesUnavailable
#
#
# class OverloadedRates:
#     """Simulates a downstream service that fails if too many calls run at once."""
#
#     def __init__(self, max_safe_concurrency: int = 50, delay: float = 0.02) -> None:
#         self.max_safe_concurrency = max_safe_concurrency
#         self.delay = delay
#         self.in_flight = 0
#
#     async def rate(self, base: str, quote: str) -> float:
#         self.in_flight += 1
#         try:
#             if self.in_flight > self.max_safe_concurrency:
#                 raise RatesUnavailable("downstream overloaded")
#             await asyncio.sleep(self.delay)
#             return 1.10
#         finally:
#             self.in_flight -= 1
#
#
# def test_unbounded_500_fan_out_overwhelms_target() -> None:
#     service = OverloadedRates(max_safe_concurrency=50, delay=0.02)
#     queries = [("EUR", "USD")] * 500
#
#     summary = asyncio.run(fan_out_rates(service, queries, max_concurrency=None))
#
#     assert summary["total"] == 500
#     assert summary["peak_in_flight"] > 50
#     assert summary["failed"] > 0
#
#
# def test_semaphore_backpressure_keeps_500_fan_out_healthy() -> None:
#     service = OverloadedRates(max_safe_concurrency=50, delay=0.02)
#     queries = [("EUR", "USD")] * 500
#
#     summary = asyncio.run(fan_out_rates(service, queries, max_concurrency=20))
#
#     assert summary["total"] == 500
#     assert summary["peak_in_flight"] <= 20
#     assert summary["succeeded"] == 500
#     assert summary["failed"] == 0
