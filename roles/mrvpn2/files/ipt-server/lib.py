from functools import wraps
import time
import logging
import ipaddress


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


def is_ipv4(ip):
    """
    Check if a given IP address is a valid IPv4 address.

    :param ip: The IP address to be checked.
    :return: True if the IP address is a valid IPv4 address, False otherwise.
    """
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False
