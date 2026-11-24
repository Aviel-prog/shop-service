import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from passwords import hash_password

from m7.C.service.reports import sales_report


def timed(label: str, fn) -> None:
    start = time.perf_counter()
    fn()
    print(f"  {label:<20} {time.perf_counter() - start:5.2f} s")


if __name__ == "__main__":
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"Python {sys.version.split()[0]}  GIL enabled: {gil}")
    for job, arg in ((hash_password, "hunter2"), (sales_report, 400_000)):
        print(f"4 x {job.__name__}:")
        timed("one after another", lambda: [job(arg) for _ in range(4)])
        with ThreadPoolExecutor(2) as pool:
            timed("2 threads", lambda: list(pool.map(job, [arg] * 4)))
        with ProcessPoolExecutor(2) as pool:
            list(pool.map(job, [arg] * 2))  # start the processes before timing
            timed("2 processes", lambda: list(pool.map(job, [arg] * 4)))
