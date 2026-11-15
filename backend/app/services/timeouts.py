"""Run a function with a time limit.

Python cannot kill a thread. On timeout the call is ABANDONED (it keeps running
in the background and its result is ignored). The job is never retried.
"""

import threading


class JobTimeout(Exception):
    pass


def call_with_timeout(fn, timeout_s: float):
    box: dict = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as error:  # handed back to the caller below
            box["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise JobTimeout(f"Engine call took longer than {timeout_s} seconds")
    if "error" in box:
        raise box["error"]
    return box["value"]