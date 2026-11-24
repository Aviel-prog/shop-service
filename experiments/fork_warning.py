import multiprocessing
import threading
import time
from concurrent.futures import ProcessPoolExecutor


def double(n: int) -> int:
    return n * 2


if __name__ == "__main__":
    busy = threading.Thread(target=time.sleep, args=(1,))   # a server always has other threads
    busy.start()
    for method in ("fork", "forkserver"):
        with ProcessPoolExecutor(1, mp_context=multiprocessing.get_context(method)) as pool:
            print(method, pool.submit(double, 21).result())
    busy.join()