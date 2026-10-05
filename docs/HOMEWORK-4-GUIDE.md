# Homework 4: DevOps and Observability, step by step

This guide follows the AI Shipping Blog article *DevOps and Observability for an AI-Built App*
(<https://aishippingblog.com/p/devops-and-observability-for-an-ai>) and applies it to the
Order Tracker starter (<https://github.com/alexeygrigorev/order-tracker>).

The article's ideas, mapped to this homework:

| Article idea | Where it shows up here |
| --- | --- |
| Instrument the backend with OpenTelemetry: metrics, logs, traces | Q2: `app/telemetry.py` |
| A separate observability stack: Collector, Prometheus, Loki, Tempo, Grafana | Q3: `observability/` + `compose.yaml` |
| Alert on real user impact, with service, owner, and dashboard link in the payload | Q4: `observability/grafana/provisioning/alerting/rules.yaml` |
| An on-call worker that launches a headless coding agent when an alert fires | Q5: `incident-response/responder.py` |
| Introduce a reproducible bug and check that alert -> agent -> fix works | Q6: `express-1002` |
| "The model may reason. The system must observe, authorize, verify, and remember." | The responder saves evidence, the prompt sets the policy, the responder re-checks the fix itself |

The article polls the alert API every minute. Here, Grafana pushes a webhook instead, as the homework asks.

---

## Step 0. Set up

1. On GitHub, fork `alexeygrigorev/order-tracker`, then clone **your fork**:

   ```bash
   git clone https://github.com/<your-user>/order-tracker.git
   cd order-tracker
   git checkout -b homework-4
   ```

2. **Check the tools.** Open a terminal: Terminal on Mac, a normal terminal on Linux, and
   PowerShell or Git Bash on Windows. Where the PowerShell command differs, the guide shows
   it. Then run the three checks below. Each should print a version number;
   your numbers will differ from the examples.

   ```bash
   docker compose version     # e.g. "Docker Compose version v2.29.1"
   uv --version               # e.g. "uv 0.8.22"
   claude --version           # Claude Code; skip this if you use another agent
   ```

   If a command prints "command not found", install that tool, close the terminal, open a
   new one, and run the check again:

   | Tool | How to install |
   | --- | --- |
   | Docker + Compose | Install **Docker Desktop** (Mac/Windows) from <https://docs.docker.com/get-docker/> and start it. On Linux, install Docker Engine and the `docker-compose-plugin` package. If you see "Cannot connect to the Docker daemon", Docker isn't running: start Docker Desktop. |
   | uv | Mac/Linux/Git Bash: `curl -LsSf https://astral.sh/uv/install.sh \| sh`. Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
   | Claude Code | Follow <https://docs.claude.com/en/docs/claude-code/setup> (one option is `npm install -g @anthropic-ai/claude-code`, which needs Node.js). Run `claude` once and log in, because the responder in Q5 can't log in for you. Install options change, so check the docs page. |

   Also check that git knows who you are, because `git am` creates commits:

   ```bash
   git config user.name || git config --global user.name "Your Name"
   git config user.email || git config --global user.email "you@example.com"
   ```

3. **Add the homework files.** Pick option A or B.

   **Option A: patches (recommended, one commit per question).**

   a. Download the 6 `.patch` files from the chat (`0001-Q2-...patch` to `0006-Docs-...patch`)
      and put them in one folder, e.g. `~/Downloads/hw4-patches/`.
      Make sure the folder holds nothing but those 6 files.

   b. In your clone, on the `homework-4` branch:

      ```bash
      cd order-tracker                    # the folder you cloned in step 1
      git status                          # should say "On branch homework-4" and "nothing to commit"
      git am ~/Downloads/hw4-patches/*.patch
      ```

      On Windows with Git Bash, your Downloads folder is usually `/c/Users/<you>/Downloads`.

      **Windows PowerShell:** `*.patch` is not expanded for `git am`, so pass the files
      explicitly, sorted by name:

      ```powershell
      git am (Get-ChildItem "$HOME\Downloads\hw4-patches\*.patch" | Sort-Object Name).FullName
      ```

   c. Check that it worked:

      ```bash
      git log --oneline -7
      ```

      You should see six new commits on top of the starter's last commit:
      `Q2: ...`, `Q3: ...`, `Q4: ...`, `Q5: ...`, `Q6: ...`, `Docs: ...`.

   d. If `git am` stops with an error, run `git am --abort` to undo it. This usually happens
      when the clone has changes or the folder holds extra files. Make sure `git status` is
      clean, and try again.

   **Option B: zip.**

   ```bash
   cd order-tracker
   unzip ~/Downloads/order-tracker-homework4.zip -d /tmp/hw4   # creates /tmp/hw4/order-tracker/
   cp -r /tmp/hw4/order-tracker/. .                            # copy everything over your clone
   git add -A
   git commit -m "Homework 4: telemetry, observability stack, alert, responder"
   ```

   On Windows you can also right-click the zip, choose "Extract All", and copy the contents of
   the extracted `order-tracker` folder into your clone. Replace files when asked.

4. **Push the branch** to your fork, so GitHub has it from the start:

   ```bash
   git push -u origin homework-4
   ```

   Refresh your fork on GitHub, switch the branch selector to `homework-4`, and you should see
   `observability/`, `incident-response/`, and `docs/`.

If you want to build each step with your own agent instead, use the prompt given in each step
and compare the agent's result with these files.

---

## Question 1. Run the app

```bash
docker compose up --build -d --wait
curl http://localhost:8000/healthz
```

The `/healthz` route runs `SELECT 1` on SQLite and returns `{"status": "ok"}`.

**Answer: `{"status":"ok"}`**

---

## Question 2. Instrument one endpoint (console)

Article idea: before you can debug, you need signals. Metrics say *how much*, logs say *what
happened*, traces say *where the time went and what failed*.

**Prompt for your agent:**

> Add OpenTelemetry metrics, logs, and traces for order lookups (`GET /api/orders/{order_id}`)
> in this FastAPI app. Add a request counter with attributes `http.route` (the route template,
> not the raw path) and `http.status_code`. Write a log line per lookup that includes the
> trace id. Use FastAPI auto-instrumentation for traces. Export everything to the console
> for now. Keep the tests passing.

**What was added:**

- `app/telemetry.py`: tracer, meter, and logger providers. Exporter selected with
  `TELEMETRY_EXPORTER` (`console`, `otlp`, `console,otlp`, `none`).
- Metric `order_tracker.requests` (counter) with `http.method`, `http.route`, `http.status_code`.
  Also a duration histogram and an `order_tracker.order_lookups` counter.
- `FastAPIInstrumentor` for server spans, plus a custom `order.lookup` span.
- Lookup logs such as `order lookup ok order_id=standard-1001 ... status=200 trace_id=...`.
- Dependencies in `pyproject.toml` / `uv.lock`. Tests set `TELEMETRY_EXPORTER=none`.

**Run it in console mode** (the final `compose.yaml` defaults to `otlp`, so override it):

```bash
TELEMETRY_EXPORTER=console docker compose up --build -d --wait app
curl -i http://localhost:8000/api/orders/standard-1001
sleep 10
docker compose logs app | grep -A 12 '"name": "order_tracker.requests"'
```

You will see:

```json
"attributes": {
    "http.method": "GET",
    "http.route": "/api/orders/{order_id}",
    "http.status_code": 200
},
```

`standard-1001` is one of the 3 seeded orders, so the lookup succeeds.

**Answer: 200**

---

## Question 3. Build the telemetry pipeline

Article idea: telemetry goes to a dedicated stack. The app only knows one address, the
Collector, which fans signals out to the right storage.

```
app --OTLP/HTTP--> otel-collector --> Prometheus (metrics, scraped from :8889)
                                  --> Loki       (logs, OTLP at /otlp)
                                  --> Tempo      (traces, OTLP gRPC)
                    Grafana reads all three
```

**Prompt for your agent:**

> Add an OpenTelemetry Collector, Prometheus, Loki, Tempo, and Grafana to `compose.yaml`.
> Send the app's metrics, logs, and traces over OTLP to the Collector, and from there to
> Prometheus, Loki, and Tempo. Provision Grafana data sources (with links from logs to traces
> and from traces to logs) and a dashboard for request counts and errors. Put all
> configuration under `observability/`.

**Files:**

- `observability/otel-collector.yaml`: OTLP receivers on 0.0.0.0:4317/4318 (newer collector
  versions listen on localhost by default, so 0.0.0.0 matters in Docker).
- `observability/prometheus.yml`: scrapes `otel-collector:8889`.
- `observability/loki.yaml`, `observability/tempo.yaml`: single-node configs (data in `/tmp`
  inside the containers, so logs and traces are lost when the containers are recreated).
- `observability/grafana/provisioning/datasources/datasources.yaml`: Prometheus, Loki, Tempo.
- `observability/grafana/dashboards/order-tracker.json`: requests, 5xx, 4xx, error rate,
  5xx by endpoint, request rate, p95 latency, lookups, logs, traces.

**Run and check:**

```bash
docker compose up --build -d --wait
curl -i http://localhost:8000/api/orders/standard-1002
```

Open <http://localhost:3000> (admin / admin):

1. **Metric**: Explore -> Prometheus -> `order_tracker_requests_total`. You will see a series
   with `http_route="/api/orders/{order_id}"` and `http_status_code="404"`.
   Or open Dashboards -> Order Tracker -> Order Tracker.
2. **Log**: Explore -> Loki -> `{service_name="order-tracker"} |= "standard-1002"`. You will
   see `order lookup not found order_id=standard-1002 status=404 trace_id=...`.
3. **Trace**: click the `TraceID` link on the log line, or Explore -> Tempo -> Search.

Wait about 15-30 seconds after the request (5 s export interval + 5 s scrape interval).

The seeded orders are `standard-1001`, `express-1002`, and `standard-1003`. There is no
`standard-1002`, so the API answers 404.

**Answer: 404**

---

## Question 4. Configure the alert

Article idea: alert on user impact (server errors), not CPU graphs, and put enough context in
the alert that whoever receives it (human or agent) can start right away.

**Prompt for your agent:**

> Add a provisioned Grafana alert rule that fires on 5xx responses from Order Tracker.
> Group by endpoint so the alert carries `http_method` and `http_route`. Include the endpoint,
> the time window, and a dashboard link in the annotations. Treat "no data" (no 5xx at all)
> as Normal. Evaluate every 10 seconds.

**File:** `observability/grafana/provisioning/alerting/rules.yaml`

- Query (5-minute window, per endpoint):

  ```promql
  sum by (http_method, http_route) (
    (increase(order_tracker_requests_total{http_status_code=~"5.."}[5m]) > 0)
    or
    (order_tracker_requests_total{http_status_code=~"5.."}
      unless order_tracker_requests_total{http_status_code=~"5.."} offset 5m)
  )
  ```

  The second part matters: `increase()` returns 0 for the very first 5xx, because a brand-new
  counter series has no earlier sample to compare with. I checked this against Prometheus:
  for a single 500, plain `increase()` returned 0 and this query returned 1.
- Condition: value > 0. `for: 0s`, so it goes straight to Firing.
- `noDataState: OK`: when there are no 5xx series at all, the rule shows **Normal**, not "No data".
- Annotations: `endpoint`, `time_window: 5m`, `dashboard_url`, `summary`, `description`,
  `runbook`, and `__dashboardUid__` / `__panelId__` (these link the alert to the dashboard panel).
- Labels: `severity`, `service`, `team` (the article's "owner").

**Run and check:**

```bash
docker compose up -d --force-recreate grafana
curl -i http://localhost:8000/api/orders/standard-1002
```

Grafana -> Alerting -> Alert rules -> folder "Order Tracker Alerts" -> "Order Tracker 5xx responses".

The lookup returns 404. That is a client error (4xx), not a server error (5xx), so the alert
condition is not met. Because "no data" is mapped to OK, the state is Normal.

**Answer: Normal**

---

## Question 5. Build the automatic responder

Article idea: an on-call worker that wakes up when an alert fires and starts a headless coding
agent with a clear prompt: investigate, reproduce, make a minimal fix, run tests, commit, or
explain why it is a false positive.

**Prompt for your agent:**

> Build a FastAPI service in `incident-response/` that listens on port 8001 and accepts
> Grafana alert webhooks at `POST /alerts`. For each firing alert, create
> `incident-response/incidents/<timestamp>-<alertname>/` and save the alert payload, the
> affected endpoint, the time window, the dashboard link, recent error logs from Loki, error
> traces (with exception stack traces) from Tempo, and 5xx metrics from Prometheus. Then start
> the coding agent in headless mode with a prompt built from this evidence, in the repository
> root, and save its output. If the alert has `test=true`, the agent must not change code.
> After the agent finishes, re-run the tests and the failing requests to verify the fix.

**Files:**

- `incident-response/responder.py`: the service.
  - `POST /alerts`: accepts the Grafana payload, ignores `resolved`, skips duplicates
    (same fingerprint within 15 minutes), queues incidents and handles one at a time.
  - Evidence: `alert.json`, `metrics.json`, `logs.json`, `traces.json`, `evidence.md`
    (readable summary with stack traces and the affected paths, e.g. `/api/orders/express-1002`).
  - Agent: `prompt.md` (the exact prompt), `agent-output.md`, `agent-stderr.log`.
  - System verification: `verification.json` (pytest + re-running affected requests).
  - `GET /incidents` and `GET /incidents/{id}` to check progress.
- `incident-response/prompt_template.md`: the policy for the agent. Its last line must be a
  `STATUS:` line, which makes the outcome easy to read and parse.

**Agent command.** The default is Claude Code in print (headless) mode:

```
claude -p {prompt} --permission-mode acceptEdits --allowedTools "Bash(uv run:*)" "Bash(docker compose:*)" "Bash(curl:*)" "Bash(git:*)" Read Edit Write Grep Glob
```

`{prompt}` is replaced by the prompt text. To use another agent, set `AGENT_CMD`. For example,
for Codex CLI, something like `AGENT_CMD='codex exec --full-auto {prompt}'`.
**Check the flags in your agent's current docs (`claude --help`, `codex exec --help`).** CLI
options change between versions, and I could not run a real agent in my sandbox.

**Run and test:**

```bash
# terminal 1, from the repository root
uv run --project incident-response python incident-response/responder.py

# terminal 2
curl -X POST http://localhost:8001/alerts \
  -H 'Content-Type: application/json' \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"ResponderTest","test":"true"},"annotations":{"summary":"Test notification; no incident to fix"}}]}'

curl -s http://localhost:8001/incidents          # wait for "state": "done"
cat incident-response/incidents/*-respondertest/agent-output.md
```

The responder log also prints `Agent finished ... Last line: ...`.

**Answer:** copy what **your** agent wrote. The prompt asks it to finish with
`STATUS: TEST_ALERT_ACKNOWLEDGED - no incident to fix`, so expect something like
"This is a test notification, no code changes made", followed by that line. The exact wording
depends on your agent.

---

## Question 6. Watch the agent fix the incident

**Connect Grafana to the responder** (already in the repo):

- `observability/grafana/provisioning/alerting/contact-points.yaml`: webhook contact point
  `incident-responder` -> `http://host.docker.internal:8001/alerts`.
- `observability/grafana/provisioning/alerting/policies.yaml`: routes all alerts to it
  (`group_wait: 10s`, `repeat_interval: 4h`).
- `compose.yaml`: Grafana has `extra_hosts: host.docker.internal:host-gateway`, so on Linux the
  container can reach the responder on your machine. The responder listens on `0.0.0.0:8001`
  for this reason. On Docker Desktop (Mac/Windows), `host.docker.internal` works as is.

```bash
docker compose up -d --force-recreate grafana
# responder still running in terminal 1
curl -i http://localhost:8000/api/orders/express-1002     # HTTP 500
```

What happens next:

1. Within about 20-30 s the alert goes **Firing** (one 500 is enough with this query; repeat
   the request if it does not).
2. About 10 s later Grafana POSTs to `/alerts`. The responder logs `Incident ... queued`.
3. `evidence.md` contains the error log and the stack trace from Tempo:

   ```
   File "/app/app/main.py", in order_detail
     estimated_at = placed_at.replace(day=placed_at.day + 2)
   ValueError: day is out of range for month
   ```

4. The agent reproduces the error, fixes it, adds a regression test, runs
   `uv run --frozen pytest -q`, runs `docker compose up --build -d --wait app`, and commits.
5. The responder writes `verification.json`: tests pass and `/api/orders/express-1002` -> 200.

Check it yourself:

```bash
curl -i http://localhost:8000/api/orders/express-1002   # now 200 with estimated_delivery
git log -1
```

**Root cause.** `express-1002` is seeded with `created_at` = the last day of the previous
month. For express orders, the app computes the delivery date with
`placed_at.replace(day=placed_at.day + 2)`, for example day 30 + 2 = 32, which does not exist,
so Python raises `ValueError` and the API returns 500. The right fix is date arithmetic:

```python
estimated_at = placed_at + timedelta(days=2)
```

I reproduced the error and checked this fix and a regression test (an order placed on
2026-01-31 should get delivery 2026-02-02). The agent's fix may look a bit different.

**Answer: The express delivery date calculation tried to use a day that does not exist in that month.**

---

## Submission checklist

```bash
git add -A
git status            # telemetry, observability/, incident-response/ (with incidents/), agent's fix
git commit -m "Homework 4: incident evidence"   # if anything is left uncommitted
git push -u origin homework-4
```

Then submit the link to your fork on the course platform. You can also merge `homework-4` into
`main` first, so the link shows the final state.

Commit:

- [ ] telemetry code (`app/telemetry.py`, `app/main.py`, `pyproject.toml`, `uv.lock`)
- [ ] `observability/` (collector, Prometheus, Loki, Tempo, Grafana data sources, dashboard, alert, contact point, policy)
- [ ] `incident-response/` (responder, prompt, `incidents/` with the evidence from Q5 and Q6)
- [ ] the agent's fix and regression test

## Troubleshooting

- **Port already in use**: `ORDER_TRACKER_PORT=18080 docker compose up ...` for the app.
  Grafana, Prometheus, Loki, Tempo, and the collector use 3000, 9090, 3100, 3200, 4317, 4318.
- **No metrics in Grafana**: `curl -s localhost:9090/api/v1/targets` should show the collector
  target `up`. `docker compose logs otel-collector` shows export errors.
- **Alert never reaches the responder**: Alerting -> Contact points -> incident-responder ->
  Test. On Linux, a firewall (ufw) may block containers from reaching port 8001 on the host.
- **Agent does nothing**: read `agent-stderr.log` in the incident folder. Exit code 127 means
  the agent command was not found, so set `AGENT_CMD`. Permission errors mean the allowed-tools
  flags need adjusting for your agent version.
- **Want to run Q6 again**: `git revert` the agent's fix, `docker compose up --build -d --wait app`,
  and wait 15 minutes (the responder's duplicate cooldown) or restart the responder.
