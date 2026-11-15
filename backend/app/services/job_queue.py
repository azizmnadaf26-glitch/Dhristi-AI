"""One worker thread, one priority queue. Analysis runs before simulations.

Only ONE Uvicorn worker is supported: each process would start its own queue and engine.
"""

import itertools
import logging
import queue as queue_module
import threading

from app.config import settings
from app.errors import AppError

logger = logging.getLogger("app.jobs")

PRIORITY_STOP = -1
PRIORITY_ANALYSIS = 0
PRIORITY_SIMULATION = 1


class JobQueue:
    def __init__(self) -> None:
        self._q: queue_module.PriorityQueue = queue_module.PriorityQueue()
        self._seq = itertools.count()
        self._lock = threading.Lock()
        self._waiting_analyses = 0
        self._thread: threading.Thread | None = None
        self._stopping = False
        self.inline = False  # tests only: run jobs immediately in the calling thread

    # ----- capacity -----
    def check_capacity(self) -> None:
        """Call BEFORE creating a case, so a refused upload leaves nothing behind."""
        with self._lock:
            if self._stopping or self._waiting_analyses >= settings.max_waiting_analyses:
                raise AppError(
                    503,
                    "server_busy",
                    "The server is busy. Please try again shortly.",
                    headers={"Retry-After": "30"},
                )

    # ----- submitting -----
    def submit_analysis(self, fn) -> None:
        self._submit(PRIORITY_ANALYSIS, fn)

    def submit_simulation(self, fn) -> None:
        self._submit(PRIORITY_SIMULATION, fn)

    def _submit(self, priority: int, fn) -> None:
        if self.inline:
            fn()
            return
        with self._lock:
            if self._stopping:
                raise AppError(
                    503,
                    "server_busy",
                    "The server is shutting down.",
                    headers={"Retry-After": "30"},
                )
            if priority == PRIORITY_ANALYSIS:
                self._waiting_analyses += 1
            self._start_locked()
            self._q.put((priority, next(self._seq), fn))

    # ----- worker -----
    def start(self) -> None:
        with self._lock:
            self._stopping = False
            self._start_locked()

    def _start_locked(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while True:
            priority, _, fn = self._q.get()
            if priority == PRIORITY_STOP or self._stopping:
                break
            with self._lock:
                if priority == PRIORITY_ANALYSIS:
                    self._waiting_analyses -= 1
            try:
                fn()
            except Exception:
                logger.exception("Background job failed")  # worker keeps running

    def shutdown(self, timeout_s: float = 30.0) -> None:
        """Stop accepting jobs; give the active job up to timeout_s seconds."""
        with self._lock:
            self._stopping = True
            thread = self._thread
            self._q.put((PRIORITY_STOP, next(self._seq), None))
        if thread is not None:
            thread.join(timeout_s)


queue = JobQueue()