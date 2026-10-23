"""
server.py — dl-1's http layer (fastapi).

routes
  GET    /                       the front panel (static/index.html)
  GET    /api/health             engine readout: yt-dlp version, ffmpeg, js runtime, formats
  POST   /api/jobs               {url, format} → 202 {id, status}
  GET    /api/jobs/{id}          job summary
  GET    /api/jobs/{id}/events   server-sent events: log / meta / status / progress / done / error / end
  GET    /api/jobs/{id}/file     the finished file, as a download
  DELETE /api/jobs/{id}          stop a running job

config — env vars, all optional
  DL1_HOST / DL1_PORT            bind address (run.sh reads these)          127.0.0.1 / 3300
  DL1_DOWNLOAD_DIR               where job folders live                     ./downloads
  DL1_MAX_WORKERS                parallel downloads                         2
  DL1_RETENTION_MINUTES          finished files are swept after this        120
  DL1_FFMPEG                     path to an ffmpeg binary                   auto-detect
  DL1_JS_RUNTIME                 name:/path, e.g. node:/usr/local/bin/node  auto-detect
  DL1_COOKIES_FROM_BROWSER       chrome | firefox | safari | brave | edge   off
  DL1_COOKIES_FILE               netscape-format cookies.txt                off
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from downloader import FORMATS, engine_info
from jobs import Job, JobStore

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = Path(os.environ.get("DL1_DOWNLOAD_DIR", BASE_DIR / "downloads"))
MEDIA_TYPES = {"mp4": "video/mp4", "mp3": "audio/mpeg", "m4a": "audio/mp4", "webm": "video/webm"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s // %(message)s")
log = logging.getLogger("dl1")

app = FastAPI(title="dl-1 // universal media downloader", version="1.0")
store = JobStore(
    DOWNLOAD_DIR,
    workers=int(os.environ.get("DL1_MAX_WORKERS", "2")),
    retention_minutes=int(os.environ.get("DL1_RETENTION_MINUTES", "120")),
)


@app.on_event("startup")
def _banner() -> None:
    info = engine_info()
    log.info("dl-1 ready // yt-dlp %s // ffmpeg %s // js runtime %s // downloads → %s",
             info["ytdlp"], "ok" if info["ffmpeg"] else "MISSING", info["js_runtime"] or "none", DOWNLOAD_DIR)


# ---------------------------------------------------------------------------
# front panel
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
class JobRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    format: str = "mp4"


def _job(job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "no such job. the server may have restarted — run it again.")
    return job


def _clean_url(raw: str) -> str:
    url = raw.strip()
    if url and "://" not in url:
        url = "https://" + url                       # forgive a pasted "youtube.com/watch?v=…"
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or "." not in parts.netloc:
        raise HTTPException(400, "that doesn't look like a link. paste the full url, including https://")
    return url


@app.get("/api/health")
def health() -> dict:
    info = engine_info()
    return {"ok": True, **info, "ffmpeg": bool(info["ffmpeg"]), "ffmpeg_path": info["ffmpeg"]}


@app.post("/api/jobs", status_code=202)
def create_job(req: JobRequest) -> dict:
    if req.format not in FORMATS:
        raise HTTPException(400, f"unknown format '{req.format}'. options: {', '.join(FORMATS)}")
    job = store.create(_clean_url(req.url), req.format)
    log.info("job %s // %s // %s", job.id, job.fmt, job.url)
    return {"id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return _job(job_id).summary()


@app.delete("/api/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    job = _job(job_id)
    return {"ok": store.cancel(job_id), "status": job.status}


@app.api_route("/api/jobs/{job_id}/file", methods=["GET", "HEAD"])
def get_file(job_id: str) -> FileResponse:
    job = _job(job_id)
    path = job.file                                   # always inside the job's own folder
    if path is None:
        raise HTTPException(409 if not job.finished else 404,
                            "no file yet." if not job.finished else "this job has no file (failed, stopped, or swept).")
    media = MEDIA_TYPES.get(path.suffix.lstrip(".").lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=path.name)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """replays the job's history, then follows it live until it ends."""
    job = _job(job_id)

    async def stream():
        sent = 0
        seen_seq = -1
        last_ping = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            with job.lock:
                fresh = job.events[sent:]
                sent = len(job.events)
                progress = job.progress if job.progress_seq != seen_seq else None
                seen_seq = job.progress_seq
                finished = job.finished
            for event in fresh:
                yield _sse(event["type"], event)
            if progress:
                yield _sse("progress", progress)
            if finished:
                yield _sse("end", {"status": job.status})
                return
            now = time.monotonic()
            if now - last_ping > 15:                  # keep proxies / browsers from timing out
                yield ": ping\n\n"
                last_ping = now
            await asyncio.sleep(0.15)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":                            # `python server.py` works too; run.sh is the usual way
    import uvicorn
    uvicorn.run("server:app", host=os.environ.get("DL1_HOST", "127.0.0.1"),
                port=int(os.environ.get("DL1_PORT", "3300")), reload=False)
