"""Background jobs: long stages run off the tool call and report progress through a file."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

RUNNING = "running"
DONE = "done"
ERROR = "error"

INTERRUPTED = "the job stopped when the server did."

_workers: dict[str, threading.Thread] = {}
_lock = threading.RLock()


class Job:
    """A Run's current or last background job. State lives in the Run folder, so polling reads disk."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def start(self, kind: str, total: int, work: Callable[[], Iterator[Any]], resume: str) -> dict[str, Any]:
        """Returns as soon as the worker is running; the caller must never wait on a job.

        resume tells a later poll how to finish this kind of job if the server dies mid-run.
        """
        with _lock:  # a poll must not see the worker registered but not yet started
            record = self._write(kind, RUNNING, 0, total, resume=resume)
            worker = threading.Thread(target=self._work, args=(kind, total, work, resume), daemon=True)
            _workers[str(self.path)] = worker
            worker.start()
        return record

    def status(self) -> dict[str, Any] | None:
        """Reads only: a job file saying running with no live worker means the server died mid-job."""
        with _lock:
            alive = self._alive()  # checked first, so a worker that just exited leaves a final file
            record = self._read()
        if record is None or record["state"] != RUNNING or alive:
            return record
        return {**record, "state": ERROR, "error": f"{INTERRUPTED} {record.get('resume', '')}".strip()}

    def _work(self, kind: str, total: int, work: Callable[[], Iterator[Any]], resume: str) -> None:
        done = 0
        try:
            for _ in work():
                done += 1
                self._write(kind, RUNNING, done, total, resume=resume)
        except Exception as exc:
            self._write(kind, ERROR, done, total, resume=resume, error=str(exc))
            return
        self._write(kind, DONE, done, total, resume=resume)

    def _alive(self) -> bool:
        worker = _workers.get(str(self.path))
        return worker is not None and worker.is_alive()

    def _read(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        try:
            return dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None  # a job file is derived state, so an unreadable one just means no job

    def _write(
        self, kind: str, state: str, done: int, total: int, resume: str, error: str | None = None
    ) -> dict[str, Any]:
        """Locked against the pollers, because a worker writes this file while they read it."""
        record: dict[str, Any] = {"job": kind, "state": state, "done": done, "total": total, "resume": resume}
        if error is not None:
            record["error"] = error
        with _lock:
            self.path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record
