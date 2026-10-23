"""
jobs.py — in-memory job registry + worker pool for dl-1.

each job owns a folder under downloads/<job id>/, a history of events
(log / meta / status / done / error) and a coalesced progress snapshot.
the server streams the events; downloader.py produces them. there is no
database on purpose: restart the server and the slate is clean.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from yt_dlp.utils import DownloadCancelled

from downloader import DownloadFailed, clean_error, download, human_size

log = logging.getLogger("dl1.jobs")

TERMINAL = {"done", "error", "cancelled"}


@dataclass
class Job:
    id: str
    url: str
    fmt: str
    dir: Path
    created: float = field(default_factory=time.time)
    status: str = "queued"                      # queued → fetching → converting → done | error | cancelled
    events: list = field(default_factory=list)  # everything except progress, in order
    progress: dict = field(default_factory=dict)
    progress_seq: int = 0                       # bumps on every progress update
    result: Optional[dict] = None               # from downloader.download()
    error: Optional[str] = None
    cancel_requested: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # downloader.py calls this from a worker thread
    def emit(self, event: dict) -> None:
        with self.lock:
            kind = event.get("type")
            if kind == "progress":
                self.progress = event
                self.progress_seq += 1
                return
            if kind == "status":
                self.status = event["value"]
            elif kind == "done":
                self.status = "done"
            elif kind == "error":
                self.status = "cancelled" if event.get("cancelled") else "error"
            event.setdefault("t", round(time.time() - self.created, 2))
            self.events.append(event)

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL

    @property
    def file(self) -> Optional[Path]:
        if self.status == "done" and self.result:
            p = Path(self.result["path"])
            return p if p.is_file() else None
        return None

    def summary(self) -> dict:
        public_result = {k: v for k, v in (self.result or {}).items() if k != "path"}
        return {
            "id": self.id, "url": self.url, "format": self.fmt, "status": self.status,
            "progress": self.progress, "result": public_result or None, "error": self.error,
            "created": self.created,
        }


class JobStore:
    def __init__(self, root: Path, workers: int = 2, retention_minutes: int = 120):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention = retention_minutes * 60
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dl1")
        threading.Thread(target=self._sweep_forever, name="dl1-sweeper", daemon=True).start()

    # -- public ---------------------------------------------------------------
    def create(self, url: str, fmt: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, url=url, fmt=fmt, dir=self.root / job_id)
        with self._lock:
            self._jobs[job_id] = job
        job.emit({"type": "status", "value": "queued"})
        job.emit({"type": "log", "level": "info", "text": f"job {job_id} // {fmt} // queued"})
        self._pool.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.finished:
            return False
        job.cancel_requested = True       # the worker raises on its next hook call
        return True

    def all(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    # -- worker ---------------------------------------------------------------
    def _run(self, job: Job) -> None:
        if job.cancel_requested:
            self._fail(job, "stopped.", cancelled=True)
            return
        job.emit({"type": "status", "value": "fetching"})
        try:
            result = download(job.url, job.fmt, job.dir, job.emit,
                              cancelled=lambda: job.cancel_requested)
        except DownloadCancelled:
            self._fail(job, "stopped.", cancelled=True)
        except DownloadFailed as exc:
            self._fail(job, str(exc))
        except Exception as exc:  # noqa: BLE001 — last line of defence, never crash the worker
            log.exception("job %s crashed", job.id)
            self._fail(job, f"unexpected error // {clean_error(exc)}")
        else:
            job.result = result
            job.emit({"type": "log", "level": "ok",
                      "text": f"ready // {result['name']} // {human_size(result['size'])}"})
            job.emit({"type": "done", "file": {
                "name": result["name"], "size": result["size"], "ext": result["ext"],
                "title": result["title"], "url": f"/api/jobs/{job.id}/file",
            }})

    def _fail(self, job: Job, message: str, cancelled: bool = False) -> None:
        job.error = message
        job.emit({"type": "log", "level": "warn" if cancelled else "error", "text": message})
        job.emit({"type": "error", "message": message, "cancelled": cancelled})
        shutil.rmtree(job.dir, ignore_errors=True)

    # -- housekeeping ---------------------------------------------------------
    def _sweep_forever(self) -> None:
        while True:
            try:
                self.sweep()
            except Exception:  # noqa: BLE001
                log.exception("sweep failed")
            time.sleep(300)

    def sweep(self) -> int:
        """drop finished jobs (and orphan folders from earlier runs) older than the retention window."""
        cutoff = time.time() - self.retention
        removed = 0
        with self._lock:
            live = set(self._jobs)
            for job_id, job in list(self._jobs.items()):
                if job.finished and job.created < cutoff:
                    shutil.rmtree(job.dir, ignore_errors=True)
                    del self._jobs[job_id]
                    removed += 1
        for folder in self.root.iterdir():
            if folder.is_dir() and folder.name not in live and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        if removed:
            log.info("swept %d old job folder(s)", removed)
        return removed
