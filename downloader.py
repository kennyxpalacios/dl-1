"""
downloader.py — the yt-dlp engine behind dl-1.

one pure function: `download(url, fmt, out_dir, emit)`. it fetches + converts
the media and streams log / progress / meta events to `emit` while it works.
no web framework in here, so you can reuse it from a cli, a cron job, anything.

add a preset to FORMATS and it shows up in the api + ui automatically.
"""
from __future__ import annotations

import functools
import glob
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError

Emit = Callable[[dict], None]

# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------
FORMATS: dict[str, dict] = {
    "mp4": {
        "label": "video // high res",
        "ext": "mp4",
        "needs_ffmpeg": True,   # merging separate video + audio streams
        "compat": "h264",       # re-encode vp9 / av1 / hevc to h.264 so the file plays everywhere
        "ydl": {
            # best h.264 video + aac audio, merged into mp4: highest resolution
            # the site offers in a codec that plays everywhere and cuts cleanly
            # in premiere / resolve / final cut. falls back to anything if the
            # site has no separate streams (instagram, tiktok, ...).
            # want max resolution regardless of codec (4k av1 / vp9 on youtube)?
            # swap the selector for: "bestvideo*+bestaudio/best"
            "format": (
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo*+bestaudio/best"
            ),
            "merge_output_format": "mp4",
        },
    },
    "mp3": {
        "label": "audio // 320 kbps",
        "ext": "mp3",
        "needs_ffmpeg": True,   # transcoding to mp3
        "ydl": {
            "format": "bestaudio/best",
            "writethumbnail": True,   # grabbed so it can be embedded as cover art
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
            ],
        },
    },
}

_PP_LABELS = {
    "Merger": "merging streams",
    "ExtractAudio": "converting to mp3",
    "Metadata": "writing metadata",
    "EmbedThumbnail": "embedding cover art",
    "ThumbnailsConvertor": "converting thumbnail",
    "MoveFiles": "moving file",
}

_SCRAP_SUFFIXES = {".part", ".ytdl", ".webp", ".jpg", ".jpeg", ".png", ".json", ".temp", ".tmp"}


class DownloadFailed(Exception):
    """raised with a short, human message in str(exc). safe to show in the ui."""


# ---------------------------------------------------------------------------
# tool discovery (ffmpeg, js runtime, cookies)
# ---------------------------------------------------------------------------
def find_ffmpeg() -> Optional[str]:
    """$DL1_FFMPEG → ffmpeg on PATH → the binary bundled with imageio-ffmpeg."""
    env = os.environ.get("DL1_FFMPEG")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # optional dependency, see requirements.txt
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


_JS_RUNTIMES = ("deno", "node", "bun", "quickjs")
_JS_EXTRA_DIRS = (
    "/opt/homebrew/bin", "/usr/local/bin",
    "~/.deno/bin", "~/.bun/bin", "~/.local/bin",
    "~/.nvm/versions/node/*/bin", "~/.volta/bin", "~/.fnm/aliases/default/bin",
    "~/.cache/codex-runtimes/*/dependencies/node/bin",
)


def find_js_runtime() -> Optional[tuple[str, str]]:
    """
    youtube wants a javascript runtime for its challenge scripts (deno is the
    official pick; node works too). returns (name, path) or None. without one,
    youtube still works today but with a warning and possibly fewer formats.
    override with DL1_JS_RUNTIME=name:/path/to/binary
    """
    env = os.environ.get("DL1_JS_RUNTIME")
    if env:
        name, _, path = env.partition(":")
        if name in _JS_RUNTIMES and path and Path(path).exists():
            return name, path
    for name in _JS_RUNTIMES:
        found = shutil.which(name)
        if found:
            return name, found
    for pattern in _JS_EXTRA_DIRS:
        for d in sorted(glob.glob(os.path.expanduser(pattern)), reverse=True):
            for name in _JS_RUNTIMES:
                candidate = Path(d) / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return name, str(candidate)
    return None


def cookie_opts() -> dict:
    """sites that demand a login (instagram, vimeo, age-gated youtube) work with your browser's cookies."""
    opts: dict = {}
    browser = os.environ.get("DL1_COOKIES_FROM_BROWSER")   # e.g. chrome, firefox, safari, brave, edge
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    cookie_file = os.environ.get("DL1_COOKIES_FILE")         # netscape cookies.txt
    if cookie_file and Path(cookie_file).exists():
        opts["cookiefile"] = cookie_file
    return opts


def engine_info() -> dict:
    """what the health endpoint + header readout show."""
    js = find_js_runtime()
    return {
        "ytdlp": yt_dlp.version.__version__,
        "ffmpeg": find_ffmpeg(),
        "js_runtime": js[0] if js else None,
        "cookies": "browser" if os.environ.get("DL1_COOKIES_FROM_BROWSER")
                   else "file" if os.environ.get("DL1_COOKIES_FILE") else None,
        "formats": {k: {"label": v["label"], "ext": v["ext"]} for k, v in FORMATS.items()},
    }


# ---------------------------------------------------------------------------
# yt-dlp plumbing: logger + hooks → emit()
# ---------------------------------------------------------------------------
def _log(text: str, level: str = "info") -> dict:
    return {"type": "log", "level": level, "text": text}


class _Logger:
    """routes yt-dlp's console chatter into the event stream."""

    def __init__(self, emit: Emit, out_dir: Path):
        self.emit = emit
        self._prefix = str(out_dir) + os.sep   # shown as bare filenames in the log

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            return                       # true debug noise
        self.info(msg)                   # yt-dlp sends info through debug() too

    def info(self, msg: str) -> None:
        if msg.startswith("[download]") and ("%" in msg or "Download completed" in msg):
            return                       # the progress hook covers these
        if msg.startswith("Deleting original file"):
            return
        self.emit(_log(msg.replace(self._prefix, "")))

    def warning(self, msg: str) -> None:
        self.emit(_log(msg, "warn"))

    def error(self, msg: str) -> None:
        self.emit(_log(msg, "error"))


class _Hooks:
    def __init__(self, emit: Emit, cancelled: Callable[[], bool]):
        self.emit = emit
        self.cancelled = cancelled
        self._last = 0.0
        self._meta_sent = False
        self._stream = 0
        self._last_pp = None             # yt-dlp registers param-defined postprocessor hooks twice

    def _check_cancel(self) -> None:
        if self.cancelled():
            raise DownloadCancelled("cancelled by user")

    def progress(self, d: dict) -> None:
        self._check_cancel()
        info = d.get("info_dict") or {}
        if not self._meta_sent and info.get("title"):
            self._meta_sent = True
            self.emit({
                "type": "meta",
                "title": info.get("title"),
                "uploader": info.get("uploader") or info.get("channel"),
                "duration": info.get("duration"),
                "site": info.get("extractor_key"),
            })
        status = d.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - self._last < 0.25 and d.get("downloaded_bytes"):
                return                   # throttle: ~4 updates/sec is plenty
            self._last = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            self.emit({
                "type": "progress",
                "phase": "download",
                "percent": round(done / total * 100, 1) if total else None,
                "downloaded": done,
                "total": total,
                "speed": d.get("speed"),
                "eta": d.get("eta"),
            })
        elif status == "finished":
            self._stream += 1
            kind = "audio" if info.get("vcodec") in (None, "none") else "video"
            res = f" {info.get('height')}p" if kind == "video" and info.get("height") else ""
            size = d.get("total_bytes") or d.get("downloaded_bytes")
            self.emit({"type": "progress", "phase": "download", "percent": 100,
                       "downloaded": size, "total": size, "speed": None, "eta": 0})
            self.emit(_log(f"stream {self._stream} complete // {kind}{res} // {human_size(size)}"))

    def postprocessor(self, d: dict) -> None:
        self._check_cancel()
        name = d.get("postprocessor") or ""
        if name == "MoveFiles":
            return                       # internal shuffle, not worth a line
        key = (name, d.get("status"))
        if key == self._last_pp:
            return                       # duplicate hook call, see __init__
        self._last_pp = key
        label = _PP_LABELS.get(name, name.lower() or "processing")
        if d.get("status") == "started":
            self.emit({"type": "status", "value": "converting"})
            self.emit(_log(f"{label} // start"))
        elif d.get("status") == "finished":
            self.emit(_log(f"{label} // done"))


# ---------------------------------------------------------------------------
# errors → one clean line
# ---------------------------------------------------------------------------
_ERROR_RULES: list[tuple[tuple[str, ...], str]] = [
    (("cancelled by user",), "stopped."),
    (("ffprobe and ffmpeg not found", "ffmpeg not found", "ffmpeg is not installed", "ffmpeg could not be found"),
     "ffmpeg is missing — needed for mp3 + merged video. see readme."),
    (("private video", "this video is private"),
     "this video is private. the owner has to make it public or unlisted."),
    (("sign in to confirm your age", "age-restricted", "age restricted"),
     "age-restricted — needs a logged-in session. set DL1_COOKIES_FROM_BROWSER (see readme)."),
    (("confirm you're not a bot", "confirm you’re not a bot"),
     "the site wants proof you're not a bot. wait a minute and retry, or pass browser cookies (see readme)."),
    (("login required", "only works when logged-in", "logged-in", "rate-limit reached or login required",
      "use --cookies"),
     "this one needs a login. set DL1_COOKIES_FROM_BROWSER=chrome (see readme) and retry."),
    (("requested format is not available", "no video formats found", "no suitable formats"),
     "no downloadable formats found for this link."),
    (("video unavailable", "content isn't available", "is unavailable", "has been removed"),
     "unavailable — removed, region-locked, or the link is wrong."),
    (("unsupported url",), "unsupported url. yt-dlp doesn't know how to read this one."),
    (("is not a valid url",), "that's not a valid url."),
    (("http error 404",), "nothing at that url (404)."),
    (("http error 403",), "the site refused the request (403). retry, or pass browser cookies."),
    (("http error 429", "too many requests"), "rate-limited (429). give it a few minutes."),
    (("name or service not known", "nodename nor servname", "network is unreachable",
      "temporary failure in name resolution", "connection refused", "timed out", "unable to download webpage"),
     "network error — can't reach the site."),
]


def clean_error(exc: BaseException) -> str:
    raw = str(exc) or exc.__class__.__name__
    low = raw.lower()
    for needles, message in _ERROR_RULES:
        if any(n in low for n in needles):
            return message
    text = raw.strip().splitlines()[0]
    text = re.sub(r"^error:\s*", "", text, flags=re.I)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)        # "[youtube] "
    text = re.sub(r"^[\w-]{6,}:\s*", "", text)        # "dQw4w9WgXcQ: "
    return (text[:200].rstrip(". ") or "unknown error") + "."


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------
def download(url: str, fmt: str, out_dir: Path, emit: Emit, *,
             cancelled: Callable[[], bool] = lambda: False) -> dict:
    """
    download `url` as `fmt` into `out_dir`. returns a result dict:
    {path, name, size, ext, title, uploader, duration}. raises DownloadFailed
    (clean message) or DownloadCancelled (if `cancelled()` turned true).
    """
    if fmt not in FORMATS:
        raise DownloadFailed(f"unknown format '{fmt}'. options: {', '.join(FORMATS)}.")
    preset = FORMATS[fmt]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    hooks = _Hooks(emit, cancelled)
    opts: dict = {
        "logger": _Logger(emit, out_dir),
        "progress_hooks": [hooks.progress],
        "postprocessor_hooks": [hooks.postprocessor],
        "outtmpl": {"default": str(out_dir / "%(title).150B [%(id)s].%(ext)s")},
        "noplaylist": True,            # a playlist link downloads just the linked video
        "noprogress": True,            # hooks replace the console progress bar
        "overwrites": True,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "quiet": False,
        "no_warnings": False,
    }

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    elif preset.get("needs_ffmpeg"):
        emit(_log("ffmpeg not found — merge / conversion steps will fail. see readme.", "warn"))

    js = find_js_runtime()
    if js:
        opts["js_runtimes"] = {js[0]: {"path": js[1]}}
    opts.update(cookie_opts())
    opts.update(preset["ydl"])

    emit(_log(f"engine yt-dlp {yt_dlp.version.__version__}"
              f" // ffmpeg {'ok' if ffmpeg else 'missing'}"
              f" // js {js[0] if js else 'none'}"))

    info: Optional[dict] = None
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadCancelled:
        raise
    except DownloadError as exc:
        # a failed postprocessing step (say, cover art) still leaves a usable file behind
        salvaged = _resolve_output(out_dir, preset["ext"], None) if "postprocessing" in str(exc).lower() else None
        if salvaged is None:
            raise DownloadFailed(clean_error(exc)) from exc
        emit(_log(f"a post-processing step failed ({clean_error(exc)}) — keeping the file anyway", "warn"))
    except Exception as exc:  # noqa: BLE001 — anything else becomes a clean message too
        raise DownloadFailed(clean_error(exc)) from exc

    path = _resolve_output(out_dir, preset["ext"], info)
    if path is None:
        raise DownloadFailed("finished, but no output file was produced. check the log above.")

    if preset.get("compat") == "h264" and ffmpeg:
        path = ensure_h264(path, ffmpeg, emit, cancelled)

    info = info or {}
    return {
        "path": str(path),
        "name": path.name,
        "size": path.stat().st_size,
        "ext": path.suffix.lstrip(".").lower(),
        "title": info.get("title") or path.stem,
        "uploader": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
    }


def _resolve_output(out_dir: Path, ext: str, info: Optional[dict]) -> Optional[Path]:
    """the final file: yt-dlp tells us when it can; otherwise the biggest real media file in the folder."""
    candidates: list[Path] = []
    for rd in (info or {}).get("requested_downloads") or []:
        fp = rd.get("filepath")
        if fp and Path(fp).is_file():
            candidates.append(Path(fp))
    if not candidates:
        candidates = [p for p in out_dir.iterdir() if p.is_file() and p.suffix.lower() == f".{ext}"]
    if not candidates:
        candidates = [p for p in out_dir.iterdir()
                      if p.is_file() and not p.name.startswith(".") and p.suffix.lower() not in _SCRAP_SUFFIXES]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


# ---------------------------------------------------------------------------
# compatibility pass: whatever the site served, the mp4 leaves as h.264 + aac
# ---------------------------------------------------------------------------
PLAYABLE_VIDEO = {"h264"}
PLAYABLE_AUDIO = {"aac", "mp3", None}


def probe(ffmpeg: str, path: Path) -> dict:
    """codecs, duration and bitrate via `ffmpeg -i` (no ffprobe needed)."""
    out = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    video = re.search(r"Stream #\d+:\d+.*?: Video: (\w+)", out)
    audio = re.search(r"Stream #\d+:\d+.*?: Audio: (\w+)", out)
    dur = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    rate = re.search(r"bitrate: (\d+) kb/s", out)
    return {
        "vcodec": video.group(1) if video else None,
        "acodec": audio.group(1) if audio else None,
        "duration": (int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])) if dur else None,
        "kbps": int(rate.group(1)) if rate else None,
    }


@functools.lru_cache(maxsize=4)
def h264_encoder(ffmpeg: str) -> Optional[str]:
    """apple's hardware encoder when the build has it (fast), else libx264 (slower, still fine)."""
    out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    for name in ("h264_videotoolbox", "libx264"):
        if re.search(rf"\b{name}\b", out):
            return name
    return None


def ensure_h264(path: Path, ffmpeg: str, emit: Emit, cancelled: Callable[[], bool]) -> Path:
    """re-encode in place when the video isn't h.264 (or the audio isn't aac). same filename comes back."""
    meta = probe(ffmpeg, path)
    v_ok = meta["vcodec"] in PLAYABLE_VIDEO
    a_ok = meta["acodec"] in PLAYABLE_AUDIO
    if v_ok and a_ok:
        emit(_log(f"codec check // {meta['vcodec']} + {meta['acodec']} // plays everywhere"))
        return path
    encoder = h264_encoder(ffmpeg)
    if encoder is None:
        emit(_log(f"codec check // {meta['vcodec']} video, but this ffmpeg has no h.264 encoder — "
                  "quicktime won't play it. install a full ffmpeg (see readme).", "warn"))
        return path

    emit({"type": "status", "value": "converting"})
    emit(_log(f"codec check // {meta['vcodec']} video — quicktime and most editors can't play that. "
              f"re-encoding to h.264 ({'hardware' if 'videotoolbox' in encoder else 'software'})"))
    tmp = path.with_name(path.stem + ".h264.tmp.mp4")
    if encoder == "h264_videotoolbox":
        kbps = int(min(max((meta["kbps"] or 2000) * 1.8, 3000), 24000))
        video_args = ["-c:v", encoder, "-b:v", f"{kbps}k", "-profile:v", "high", "-allow_sw", "1"]
    else:
        video_args = ["-c:v", encoder, "-preset", "medium", "-crf", "18"]
    audio_args = ["-c:a", "copy"] if a_ok else ["-c:a", "aac", "-b:a", "192k"]
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
           "-i", str(path), "-map", "0:v:0", "-map", "0:a?", *video_args, "-pix_fmt", "yuv420p",
           *audio_args, "-movflags", "+faststart", str(tmp)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = meta["duration"] or 0
    last = 0.0
    try:
        for raw in proc.stdout:
            if cancelled():
                proc.kill()
                raise DownloadCancelled("cancelled by user")
            key, _, value = raw.strip().partition("=")
            if key == "out_time_us" and duration and value.isdigit():
                done = int(value) / 1_000_000
                now = time.monotonic()
                if now - last >= 0.25:
                    last = now
                    emit({"type": "progress", "phase": "encode", "percent": round(min(done / duration, 1) * 100, 1),
                          "downloaded": None, "total": None, "speed": None, "eta": None})
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        err = (proc.stderr.read() or "").strip().splitlines()
        tmp.unlink(missing_ok=True)
        emit(_log(f"re-encode failed ({err[-1] if err else 'unknown error'}) — keeping the original file", "warn"))
        return path
    path.unlink()
    tmp.rename(path)
    emit({"type": "progress", "phase": "encode", "percent": 100, "downloaded": None, "total": None, "speed": None, "eta": 0})
    emit(_log(f"re-encode done // h.264 + aac // {human_size(path.stat().st_size)}"))
    return path


def human_size(n: Optional[float]) -> str:
    if not n:
        return "--"
    for unit in ("b", "kb", "mb", "gb"):
        if n < 1024 or unit == "gb":
            return f"{n:.0f} {unit}" if unit == "b" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} gb"
