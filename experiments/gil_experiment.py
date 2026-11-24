import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

N = 50_000_000


def countdown(n: int) -> None:
    """Pure Python CPU work: nothing but bytecode."""
    while n > 0:
        n -= 1


def wait(seconds: float) -> None:
    """Pure waiting: stands in for a network call."""
    time.sleep(seconds)


def timed(label: str, fn) -> None:
    start = time.perf_counter()
    fn()
    print(f"  {label:<34} {time.perf_counter() - start:6.2f} s")


if __name__ == "__main__":      # required when you use processes -- F explains why
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"Python {sys.version.split()[0]}  GIL enabled: {gil}")

    print("CPU-bound: count down from 50 million, in total")
    timed("one thread, all the work", lambda: countdown(N))
    with ThreadPoolExecutor(2) as pool:
        timed("2 threads, half the work each", lambda: list(pool.map(countdown, [N // 2] * 2)))
    with ProcessPoolExecutor(2) as pool:
        list(pool.map(countdown, [1, 1]))              # start the processes before timing
        timed("2 processes, half the work each", lambda: list(pool.map(countdown, [N // 2] * 2)))

    print("IO-bound: 10 waits of 0.5 s, in total")
    timed("one thread, one after another", lambda: [wait(0.5) for _ in range(10)])
    with ThreadPoolExecutor(10) as pool:
        timed("10 threads", lambda: list(pool.map(wait, [0.5] * 10)))