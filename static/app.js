/* dl-1 // front panel logic
   one job at a time from this panel. the server streams events over sse;
   this file just turns them into log lines, a meter and a save key. */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const el = {
    device: $("#device"), form: $("#form"), url: $("#url"), clear: $("#clear"),
    run: $("#run"), runLabel: $("#run-label"), runGlyph: $("#run-glyph"), hint: $("#hint"),
    status: $("#status"), log: $("#log"), pct: $("#pct"), meter: $("#meter"),
    size: $("#tele-size"), speed: $("#tele-speed"), eta: $("#tele-eta"),
    result: $("#result"), resultName: $("#result-name"), resultSpec: $("#result-spec"), save: $("#save"),
    specYt: $("#spec-ytdlp"), specFf: $("#spec-ffmpeg"), specJs: $("#spec-js"),
    keyMp3: $("#key-mp3"), specMp3: $("#spec-mp3"),
  };

  const SEGMENTS = 40;
  const MAX_LINES = 400;
  const TERMINAL = ["done", "error", "cancelled"];
  const state = { job: null, es: null, t0: 0, busy: false };

  for (let i = 0; i < SEGMENTS; i++) el.meter.appendChild(document.createElement("i"));

  // ── formatting ───────────────────────────────────────────────────────────
  const pad = (n) => String(n).padStart(2, "0");
  const fmtTime = (s) => { s = Math.max(0, Math.floor(s || 0)); return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; };
  const fmtSize = (n) => {
    if (n == null) return "--";
    const units = ["b", "kb", "mb", "gb"]; let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${i ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
  };
  const fmtSpeed = (n) => (n ? `${fmtSize(n)}/s` : "--");
  const elapsed = () => (state.t0 ? (Date.now() - state.t0) / 1000 : 0);

  // ── display ──────────────────────────────────────────────────────────────
  function line(text, level = "info", t) {
    const li = document.createElement("li");
    li.className = `log__line log__line--${level}`;
    const ts = document.createElement("span"); ts.className = "t"; ts.textContent = fmtTime(t ?? elapsed());
    const msg = document.createElement("span"); msg.className = "m"; msg.textContent = text;
    li.append(ts, msg);
    el.log.appendChild(li);
    while (el.log.children.length > MAX_LINES) el.log.removeChild(el.log.firstChild);
    el.log.scrollTop = el.log.scrollHeight;
  }
  const setState = (s) => { el.device.dataset.state = s; };            // idle | busy | done | error
  const setStatus = (text) => { el.status.textContent = `status // ${text}`; };
  const setHint = (text) => { el.hint.textContent = text; };

  function setProgress(p) {
    const pct = p && p.percent != null ? Math.max(0, Math.min(100, p.percent)) : null;
    el.pct.textContent = pct == null ? "---" : String(Math.round(pct));
    const lit = pct == null ? 0 : Math.round((pct / 100) * SEGMENTS);
    [...el.meter.children].forEach((seg, i) => seg.classList.toggle("on", i < lit));
    const size = !p ? "--" : p.total ? `${fmtSize(p.downloaded)} / ${fmtSize(p.total)}` : fmtSize(p.downloaded);
    el.size.textContent = `size // ${size}`;
    el.speed.textContent = `speed // ${p ? fmtSpeed(p.speed) : "--"}`;
    el.eta.textContent = `eta // ${p && p.eta != null ? fmtTime(p.eta) : "--"}`;
  }

  function setRunMode(stop) {
    state.busy = stop;
    el.runLabel.textContent = stop ? "stop" : "run";
    el.runGlyph.textContent = stop ? "■" : "→";
    el.run.classList.toggle("is-stop", stop);
  }

  function showResult(file) {
    el.result.hidden = false;
    el.resultName.textContent = file.name;
    el.resultSpec.textContent = `format // ${file.ext} // ${fmtSize(file.size)}`;
    el.save.href = file.url;
    el.save.setAttribute("download", file.name);
    setProgress({ percent: 100, downloaded: file.size, total: file.size, speed: null, eta: 0 });
  }

  function finish(kind) {                                                // done | error | stopped
    detach();
    setRunMode(false);
    if (kind === "done") { setState("done"); setStatus("done"); setHint("done. hit save file →"); }
    else if (kind === "stopped") { setState("idle"); setStatus("stopped"); setHint("stopped."); sessionStorage.removeItem("dl1.job"); }
    else { setState("error"); setStatus("error"); setHint("didn't work. check the log, fix the link, try again."); sessionStorage.removeItem("dl1.job"); }
  }

  // ── server ───────────────────────────────────────────────────────────────
  async function health() {
    try {
      const h = await (await fetch("/api/health")).json();
      el.specYt.textContent = `yt-dlp // ${h.ytdlp}`;
      el.specFf.textContent = `ffmpeg // ${h.ffmpeg ? "ok" : "missing"}`;
      el.specJs.textContent = `js runtime // ${h.js_runtime || "none"}`;
      line(`dl-1 online // yt-dlp ${h.ytdlp} // ffmpeg ${h.ffmpeg ? "ok" : "missing"} // js ${h.js_runtime || "none"}`, "dim");
      if (!h.ffmpeg) {
        line("ffmpeg not found — mp3 and merged hi-res video are off. see readme.", "warn");
        el.keyMp3.classList.add("switch__key--off");
        el.keyMp3.querySelector("input").disabled = true;
        el.specMp3.textContent = "needs ffmpeg";
      }
      if (!h.js_runtime) line("no js runtime found — youtube may offer fewer formats. install deno or node (see readme).", "warn");
      if (h.cookies) line(`cookies // ${h.cookies}`, "dim");
      line("ready.");
      return true;
    } catch {
      line("can't reach the server. is run.sh running?", "error");
      setState("error"); setStatus("offline");
      return false;
    }
  }

  function attach(jobId) {
    detach();
    state.job = jobId;
    sessionStorage.setItem("dl1.job", jobId);
    const es = new EventSource(`/api/jobs/${jobId}/events`);
    state.es = es;
    const data = (e) => JSON.parse(e.data);

    es.addEventListener("log", (e) => { const d = data(e); line(d.text, d.level, d.t); });
    es.addEventListener("meta", (e) => {
      const d = data(e);
      const bits = [`title // ${d.title}`];
      if (d.uploader) bits.push(d.uploader);
      if (d.duration) bits.push(fmtTime(d.duration));
      line(bits.join(" // "), "info", d.t);
      document.title = `dl-1 // ${d.title}`;
    });
    es.addEventListener("status", (e) => setStatus(data(e).value));
    es.addEventListener("progress", (e) => setProgress(data(e)));
    es.addEventListener("done", (e) => { showResult(data(e).file); finish("done"); });
    es.addEventListener("error", (e) => {
      if (e.data === undefined) {                                        // native: the connection itself
        if (es.readyState === EventSource.CLOSED) { line("lost the connection to the server.", "error"); finish("error"); }
        return;                                                          // otherwise it reconnects by itself
      }
      finish(data(e).cancelled ? "stopped" : "error");                   // ours: the job failed or was stopped
    });
    es.addEventListener("end", () => detach());
  }

  function detach() {
    if (state.es) { state.es.close(); state.es = null; }
  }

  async function start(url, format) {
    el.log.innerHTML = "";
    el.result.hidden = true;
    setProgress(null);
    state.t0 = Date.now();
    document.title = "dl-1 // universal media downloader";
    setState("busy"); setStatus("sending"); setRunMode(true); setHint("working…");
    line(`source // ${url}`, "dim");
    line(`format // ${format}`, "dim");
    try {
      const res = await fetch("/api/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, format }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `server said ${res.status}`);
      attach(body.id);
    } catch (err) {
      line(err.message, "error");
      finish("error");
    }
  }

  async function stop() {
    if (!state.job) return;
    setHint("stopping…");
    await fetch(`/api/jobs/${state.job}`, { method: "DELETE" }).catch(() => {});
  }

  // ── wiring ───────────────────────────────────────────────────────────────
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.busy) return stop();
    const url = el.url.value.trim();
    if (!url) { line("paste a link first.", "error"); setState("error"); setStatus("error"); setHint("no link."); el.url.focus(); return; }
    start(url, el.form.format.value);
  });
  el.clear.addEventListener("click", () => { el.url.value = ""; el.url.focus(); });

  // inside dl-1.app the page runs in a native window (pywebview): saving goes through
  // the python api into ~/downloads and finder reveals the file. in a browser the
  // plain download link does the job and these two listeners stay out of the way.
  el.save.addEventListener("click", async (e) => {
    if (!window.pywebview) return;
    e.preventDefault();
    setHint("saving…");
    try {
      const res = await window.pywebview.api.save(state.job, el.resultName.textContent);
      if (res.ok) { line(`saved // ${res.path}`, "ok"); setHint("saved. finder has it."); }
      else { line(res.error, "error"); setHint("couldn't save."); }
    } catch (err) { line(`couldn't save // ${err}`, "error"); setHint("couldn't save."); }
  });
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[target=_blank]");
    if (a && window.pywebview) { e.preventDefault(); window.pywebview.api.open_url(a.href); }
  });
  el.url.addEventListener("focus", () => { if (!state.busy && el.device.dataset.state === "error") { setState("idle"); setStatus("idle"); setHint("ready."); } });

  // after a reload, pick the last job back up (the server replays its history)
  (async () => {
    el.url.focus();
    if (!(await health())) return;
    const prev = sessionStorage.getItem("dl1.job");
    if (!prev) return;
    const res = await fetch(`/api/jobs/${prev}`).catch(() => null);
    if (!res || !res.ok) { sessionStorage.removeItem("dl1.job"); return; }
    const job = await res.json();
    if (TERMINAL.includes(job.status) && job.status !== "done") { sessionStorage.removeItem("dl1.job"); return; }
    state.t0 = job.created * 1000;
    el.log.innerHTML = "";
    el.url.value = job.url;
    el.form.format.value = job.format;
    setState(job.status === "done" ? "done" : "busy");
    setStatus(job.status);
    setRunMode(job.status !== "done");
    line("reattached to the last job.", "dim");
    attach(prev);
  })();
})();
