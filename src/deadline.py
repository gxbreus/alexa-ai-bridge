"""Bound the entire invocation, including client setup and DNS, on Lambda Linux."""
import signal
import threading
from contextlib import contextmanager


class RequestDeadlineExceeded(TimeoutError):
    pass


@contextmanager
def request_deadline(seconds):
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Request deadline requires Lambda's main thread")
    previous_handler = signal.getsignal(signal.SIGALRM)

    def interrupt(signum, frame):
        raise RequestDeadlineExceeded("Invocation time budget exhausted")

    signal.signal(signal.SIGALRM, interrupt)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
