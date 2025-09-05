from functools import wraps
import time
import logging
from contextlib import contextmanager


def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        s_ars = [a.__repr__() for a in args]
        s_kws = [f'{k}={v.__repr__()}' for k, v in kwargs.items()]
        logging.info(f'Function {func.__name__}{s_ars} {s_kws} Took {total_time:.4f} seconds')
        return result

    return timeit_wrapper


@contextmanager
def TimeMeasure(description: str):
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    duration = end_time - start_time
    logging.info(f"{description} took {duration:.4f} seconds")
