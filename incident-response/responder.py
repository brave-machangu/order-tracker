"""Incident responder for Order Tracker.

Grafana sends alert webhooks to ``POST /alerts`` (port 8001). For each firing
alert the responder:

1. saves the alert and the evidence needed to understand it (endpoint, time
   window, dashboard link, error logs from Loki, error traces from Tempo,
   metrics from Prometheus) into ``incident-response/incidents/<id>/``;
2. starts a coding agent in headless mode with a prompt built from that evidence;
3. saves the agent's answer and, for real incidents, runs its own verification
   (tests + re-running the failing requests) so the result does not rely on the
   model's word alone.

Run it from the repository root:

    uv run --project incident-response python incident-response/responder.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request

ROOT = Path(__file__).resolve().parent
REPO = Path(os.getenv("REPO_DIR", ROOT.parent)).resolve()
INCIDENTS = Path(os.getenv("INCIDENTS_DIR", ROOT / "incidents")).resolve()
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
TEMPO_URL = os.getenv("TEMPO_URL", "http://localhost:3200")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
SERVICE_NAME = os.getenv("SERVICE_NAME", "order-tracker")
EVIDENCE_MINUTES = int(os.getenv("EVIDENCE_MINUTES", "15"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "1800"))
COOLDOWN = timedelta(minutes=int(os.getenv("COOLDOWN_MINUTES", "15")))

# The headless agent command. "{prompt}" is replaced by the full prompt text
# (as one argument). Override with AGENT_CMD for a different agent.
# Verify the flags against your agent's current CLI docs. Use forward slashes in
# Windows paths (C:/Users/...), because backslashes are treated as escapes.
DEFAULT_AGENT_CMD = (
    "claude -p {prompt} --permission-mode acceptEdits "
    '--allowedTools "Bash(uv run:*)" "Bash(docker compose:*)" "Bash(curl:*)" '
    '"Bash(git:*)" Read Edit Write Grep Glob'
)
AGENT_CMD = os.getenv("AGENT_CMD", DEFAULT_AGENT_CMD)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("responder")

app = FastAPI(title="Order Tracker incident responder")
jobs: "queue.Queue[dict[str, Any]]" = queue.Queue()
recent: dict[str, datetime] = {}  # fingerprint -> when we last accepted it
recent_lock = threading.Lock()


# --------------------------------------------------------------------------- API
@app.get("/healthz")
def health():
    return {"status": "ok", "queued": jobs.qsize()}


@app.post("/alerts", status_code=202)
async def receive_alerts(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"invalid JSON: {exc}") from exc

    alerts = payload.get("alerts") or []
    firing = [a for a in alerts if a.get("status", "firing") == "firing"]
    if not firing:
        _append_log("resolved.log", payload)
        log.info("Received %d non-firing alert(s); nothing to do", len(alerts))
        return {"accepted": False, "reason": "no firing alerts"}

    now = datetime.now(timezone.utc)
    new_alerts = []
    with recent_lock:
        for alert in firing:
            fp = fingerprint(alert)
            last = recent.get(fp)
            if last and now - last < COOLDOWN:
                log.info("Skipping duplicate alert %s (handled %s)", fp, last.isoformat())
                continue
            recent[fp] = now
            new_alerts.append(alert)
    if not new_alerts:
        return {"accepted": False, "reason": "duplicate of an incident already being handled"}

    incident_id = now.strftime("%Y%m%d-%H%M%S") + "-" + slug(
        new_alerts[0].get("labels", {}).get("alertname", "alert")
    )
    incident_dir = INCIDENTS / incident_id
    incident_dir.mkdir(parents=True, exist_ok=True)
    write_json(incident_dir / "alert.json", {**payload, "alerts": new_alerts})
    write_json(incident_dir / "status.json", {"state": "queued", "received_at": now.isoformat()})
    jobs.put({"id": incident_id, "dir": incident_dir, "alerts": new_alerts, "received_at": now})
    log.info("Incident %s queued (%d alert(s))", incident_id, len(new_alerts))
    return {"accepted": True, "incident_id": incident_id, "incident_dir": str(incident_dir)}


@app.get("/incidents")
def list_incidents():
    items = []
    for d in sorted(INCIDENTS.glob("*/"), reverse=True):
        status = read_json(d / "status.json")
        items.append({"id": d.name, **status})
    return items


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    d = INCIDENTS / incident_id
    if not d.is_dir() or d.parent != INCIDENTS:
        raise HTTPException(404, "unknown incident")
    output = (d / "agent-output.md").read_text() if (d / "agent-output.md").exists() else ""
    return {
        "id": incident_id,
        "status": read_json(d / "status.json"),
        "verification": read_json(d / "verification.json"),
        "agent_output": output,
        "files": sorted(p.name for p in d.iterdir()),
    }


# ------------------------------------------------------------------- the worker
def worker() -> None:
    while True:
        job = jobs.get()
        try:
            handle_incident(job)
        except Exception:  # noqa: BLE001
            log.exception("Incident %s failed", job["id"])
            update_status(job["dir"], state="error")
        finally:
            jobs.task_done()


def handle_incident(job: dict[str, Any]) -> None:
    incident_dir: Path = job["dir"]
    alert = job["alerts"][0]
    labels = alert.get("labels", {}) or {}
    annotations = alert.get("annotations", {}) or {}
    is_test = str(labels.get("test", "")).lower() == "true"

    update_status(incident_dir, state="collecting_evidence")
    evidence = collect_evidence(alert, job["received_at"])
    write_json(incident_dir / "metrics.json", evidence["metrics"])
    write_json(incident_dir / "logs.json", evidence["logs"])
    write_json(incident_dir / "traces.json", evidence["traces"])
    (incident_dir / "evidence.md").write_text(evidence_markdown(job, alert, evidence, is_test))

    endpoint = annotations.get("endpoint") or " ".join(
        v for v in (labels.get("http_method"), labels.get("http_route")) if v
    ) or "unknown"
    prompt = Template((ROOT / "prompt_template.md").read_text()).safe_substitute(
        incident_id=job["id"],
        incident_dir=str(incident_dir),
        alertname=labels.get("alertname", "unknown"),
        status=alert.get("status", "firing"),
        endpoint=endpoint,
        window=f"{annotations.get('time_window', '5m')} (evidence collected for the last {EVIDENCE_MINUTES} minutes)",
        dashboard_url=alert.get("dashboardURL") or annotations.get("dashboard_url", "n/a"),
        summary=annotations.get("summary", "n/a"),
        is_test="yes" if is_test else "no",
        repo=str(REPO),
        app_url=APP_URL,
    )
    (incident_dir / "prompt.md").write_text(prompt)

    update_status(incident_dir, state="agent_running", agent_started_at=now_iso())
    exit_code, output = run_agent(prompt, incident_dir)
    last_line = next((l.strip() for l in reversed(output.splitlines()) if l.strip()), "")
    update_status(
        incident_dir,
        state="agent_finished",
        agent_finished_at=now_iso(),
        agent_exit_code=exit_code,
        agent_last_line=last_line,
    )
    log.info("Agent finished for %s (exit %s). Last line: %s", job["id"], exit_code, last_line)

    if not is_test:
        verification = verify(evidence["affected_paths"])
        write_json(incident_dir / "verification.json", verification)
        update_status(incident_dir, state="done", verified=verification["passed"])
        log.info("Verification for %s: %s", job["id"], "PASSED" if verification["passed"] else "FAILED")
    else:
        update_status(incident_dir, state="done")


def run_agent(prompt: str, incident_dir: Path) -> tuple[int, str]:
    cmd = [prompt if part == "{prompt}" else part for part in shlex.split(AGENT_CMD)]
    # Resolve the executable on PATH (on Windows this finds claude.exe / claude.cmd).
    cmd[0] = shutil.which(cmd[0].strip('"')) or cmd[0]
    log.info("Starting agent: %s", " ".join(p if p != prompt else "<prompt>" for p in cmd))
    try:
        result = subprocess.run(
            cmd, cwd=REPO, capture_output=True, text=True, timeout=AGENT_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        code, out, err = result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        code, out, err = 127, "", f"Agent command not found: {cmd[0]}. Set AGENT_CMD."
    except subprocess.TimeoutExpired as exc:
        code = 124
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = f"Agent timed out after {AGENT_TIMEOUT}s"
    (incident_dir / "agent-output.md").write_text(out)
    (incident_dir / "agent-stderr.log").write_text(err or "")
    return code, out


# ------------------------------------------------------------------ evidence
def collect_evidence(alert: dict[str, Any], received_at: datetime) -> dict[str, Any]:
    end = received_at + timedelta(seconds=30)
    start = received_at - timedelta(minutes=EVIDENCE_MINUTES)
    evidence: dict[str, Any] = {"metrics": {}, "logs": {}, "traces": {}, "affected_paths": []}

    with httpx.Client(timeout=10) as client:
        # Metrics: 5xx and request rate per endpoint.
        queries = {
            "5xx_last_5m_by_endpoint": 'sum by (http_method, http_route, http_status_code) '
            '(increase(order_tracker_requests_total{http_status_code=~"5.."}[5m]))',
            "requests_last_5m_by_endpoint_and_status": "sum by (http_method, http_route, http_status_code) "
            "(increase(order_tracker_requests_total[5m]))",
        }
        for name, q in queries.items():
            evidence["metrics"][name] = safe_get(
                client, f"{PROMETHEUS_URL}/api/v1/query", {"query": q}
            )

        # Logs: errors and warnings from the app in the window.
        evidence["logs"]["errors"] = loki_lines(
            client, f'{{service_name="{SERVICE_NAME}"}} | severity_text=~"ERROR|WARN.*"', start, end
        )
        evidence["logs"]["all_recent"] = loki_lines(
            client, f'{{service_name="{SERVICE_NAME}"}}', start, end, limit=100
        )

        # Traces: failed requests, with exception events and stack traces.
        search = safe_get(
            client,
            f"{TEMPO_URL}/api/search",
            {
                "q": f'{{ resource.service.name = "{SERVICE_NAME}" && status = error }}',
                "start": int(start.timestamp()),
                "end": int(end.timestamp()),
                "limit": 20,
            },
        )
        details = []
        for t in (search.get("traces") or [])[:3] if isinstance(search, dict) else []:
            trace = safe_get(client, f"{TEMPO_URL}/api/traces/{t['traceID']}", {},
                             headers={"Accept": "application/json"})
            details.append(summarize_trace(t["traceID"], trace))
        evidence["traces"] = {"search": search, "error_traces": details}

    paths = {d["http_target"] for d in details if d.get("http_target")}
    # Also pick request paths out of the error log lines (order_id=...).
    for line in evidence["logs"]["errors"]:
        m = re.search(r"order_id=(\S+)", line.get("line", ""))
        if m and "status=5" in line.get("line", ""):
            paths.add(f"/api/orders/{m.group(1)}")
    evidence["affected_paths"] = sorted(paths)
    return evidence


def loki_lines(client, query, start, end, limit=50):
    data = safe_get(
        client,
        f"{LOKI_URL}/loki/api/v1/query_range",
        {"query": query, "start": int(start.timestamp() * 1e9), "end": int(end.timestamp() * 1e9),
         "limit": limit, "direction": "backward"},
    )
    lines = []
    if isinstance(data, dict) and data.get("status") == "success":
        for stream in data["data"]["result"]:
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                lines.append({
                    "time": datetime.fromtimestamp(int(ts) / 1e9, timezone.utc).isoformat(),
                    "level": labels.get("severity_text") or labels.get("detected_level"),
                    "trace_id": labels.get("trace_id"),
                    "line": line,
                })
    elif isinstance(data, dict) and "error" in data:
        lines.append({"error": data["error"]})
    return sorted(lines, key=lambda l: l.get("time", ""), reverse=True)


def summarize_trace(trace_id: str, trace: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"trace_id": trace_id, "spans": []}
    if not isinstance(trace, dict):
        return summary
    for batch in trace.get("batches") or trace.get("resourceSpans") or []:
        for scope in batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []:
            for span in scope.get("spans", []):
                attrs = attr_dict(span.get("attributes", []))
                info = {
                    "name": span.get("name"),
                    "status": span.get("status", {}),
                    "attributes": {k: v for k, v in attrs.items()
                                   if k.startswith(("http.", "url.", "order."))},
                    "exceptions": [],
                }
                target = attrs.get("http.target") or attrs.get("url.path")
                if target and not summary.get("http_target"):
                    summary["http_target"] = target
                for event in span.get("events", []):
                    if event.get("name") == "exception":
                        ea = attr_dict(event.get("attributes", []))
                        info["exceptions"].append({
                            "type": ea.get("exception.type"),
                            "message": ea.get("exception.message"),
                            "stacktrace": ea.get("exception.stacktrace"),
                        })
                summary["spans"].append(info)
    return summary


def attr_dict(attributes):
    out = {}
    for a in attributes:
        value = a.get("value", {})
        out[a.get("key")] = next(iter(value.values()), None) if value else None
    return out


def evidence_markdown(job, alert, evidence, is_test) -> str:
    labels = alert.get("labels", {}) or {}
    ann = alert.get("annotations", {}) or {}
    lines = [
        f"# Incident {job['id']}",
        "",
        f"- Alert: **{labels.get('alertname', 'unknown')}** ({alert.get('status', 'firing')})",
        f"- Test notification: {'yes' if is_test else 'no'}",
        f"- Endpoint: {ann.get('endpoint') or labels.get('http_route', 'unknown')}",
        f"- Time window: {ann.get('time_window', 'n/a')}; evidence covers the last {EVIDENCE_MINUTES} minutes",
        f"- Started at: {alert.get('startsAt', 'n/a')}",
        f"- Dashboard: {alert.get('dashboardURL') or ann.get('dashboard_url', 'n/a')}",
        f"- Panel: {alert.get('panelURL', 'n/a')}",
        f"- Summary: {ann.get('summary', 'n/a')}",
        f"- Description: {ann.get('description', 'n/a')}",
        f"- Labels: `{json.dumps(labels)}`",
        f"- Affected request paths: {', '.join(evidence['affected_paths']) or 'none found'}",
        "",
        "## Error and warning logs (newest first)",
        "",
    ]
    errors = evidence["logs"].get("errors") or []
    lines += [f"- `{e.get('time')}` {e.get('level')}: {e.get('line', e.get('error'))[:2000]}"
              for e in errors[:20]] or ["- none"]
    lines += ["", "## Error traces", ""]
    traces = evidence["traces"].get("error_traces") or []
    if not traces:
        lines.append("- none")
    for t in traces:
        lines.append(f"### Trace {t['trace_id']} ({t.get('http_target', '?')})")
        for span in t["spans"]:
            lines.append(f"- span `{span['name']}` status={span['status'].get('code', 'unset')} "
                         f"attrs={json.dumps(span['attributes'])}")
            for exc in span["exceptions"]:
                lines.append(f"  - exception {exc['type']}: {exc['message']}")
                if exc.get("stacktrace"):
                    lines += ["", "```", exc["stacktrace"].strip(), "```", ""]
    lines += ["", "## Metrics", "", "```json", json.dumps(evidence["metrics"], indent=2)[:6000], "```"]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------- verification
def verify(paths: list[str]) -> dict[str, Any]:
    """The system checks the agent's work: tests pass and the failing requests now succeed."""
    result: dict[str, Any] = {"checked_at": now_iso(), "requests": []}
    tests = subprocess.run(["uv", "run", "--frozen", "pytest", "-q"], cwd=REPO,
                           capture_output=True, text=True, timeout=600)
    result["tests"] = {"exit_code": tests.returncode, "tail": tests.stdout[-1500:]}
    ok = tests.returncode == 0
    with httpx.Client(timeout=10) as client:
        for path in paths:
            try:
                status = client.get(APP_URL + path).status_code
            except httpx.HTTPError as exc:
                status = f"error: {exc}"
            result["requests"].append({"path": path, "status": status})
            ok = ok and isinstance(status, int) and status < 500
    result["passed"] = ok
    return result


# -------------------------------------------------------------------- helpers
def safe_get(client, url, params, headers=None):
    try:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001 - evidence is best effort
        return {"error": f"{type(exc).__name__}: {exc}", "url": url}


def fingerprint(alert):
    if alert.get("fingerprint"):
        return alert["fingerprint"]
    return hashlib.sha1(json.dumps(alert.get("labels", {}), sort_keys=True).encode()).hexdigest()[:16]


def slug(text):
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:40] or "alert"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def update_status(incident_dir: Path, **fields):
    status = read_json(incident_dir / "status.json")
    status.update(fields)
    write_json(incident_dir / "status.json", status)


def _append_log(name, payload):
    INCIDENTS.mkdir(parents=True, exist_ok=True)
    with open(INCIDENTS / name, "a") as fh:
        fh.write(json.dumps({"received_at": now_iso(), "payload": payload}) + "\n")


threading.Thread(target=worker, daemon=True, name="incident-worker").start()

if __name__ == "__main__":
    INCIDENTS.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host=os.getenv("RESPONDER_HOST", "0.0.0.0"), port=int(os.getenv("RESPONDER_PORT", "8001")))
