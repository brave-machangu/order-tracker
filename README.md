# Order Tracker

A small order tracking app for the AI Dev Tools Zoomcamp observability homework. It includes a web page, API, tests, and a Docker Compose setup. You add telemetry, alerts, and an incident responder in Homework 4.

The main user flow is creating an order and checking its status. Three sample orders are created on first startup.

## Run it

You need Docker with Compose. To run the tests, you also need Python 3.11+ and `uv`.

```bash
docker compose up --build -d --wait
```

Open <http://127.0.0.1:8000>. The API is at `/api/orders`, and the health check is at `/healthz`. Data is stored in a Docker volume and survives container recreation.

If port 8000 is occupied, set `ORDER_TRACKER_PORT`, for example:

```bash
ORDER_TRACKER_PORT=18080 docker compose up --build -d --wait
```

Run tests with `uv run --frozen pytest -q`. Stop the app with `docker compose down`. Add `-v` only if you also want to delete the order data.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Web page |
| GET | `/healthz` | Database health check |
| GET | `/api/orders` | List orders |
| POST | `/api/orders` | Create an order |
| GET | `/api/orders/{id}` | Check an order |
| PATCH | `/api/orders/{id}` | Change an order status |

The app uses SQLite to keep setup small. Run one app container at a time. The course exercise is about detecting and handling an incident, not scaling the database.

## Observability (Homework 4)

`docker compose up --build -d --wait` now also starts an OpenTelemetry Collector, Prometheus, Loki, Tempo, and Grafana.

| Service | URL | What it holds |
| --- | --- | --- |
| Grafana | <http://localhost:3000> (admin / admin) | Dashboard "Order Tracker", alert "Order Tracker 5xx responses" |
| Prometheus | <http://localhost:9090> | Metrics, e.g. `order_tracker_requests_total` |
| Loki | <http://localhost:3100> | Logs (`{service_name="order-tracker"}`) |
| Tempo | <http://localhost:3200> | Traces |

The app sends metrics, logs, and traces over OTLP to the Collector (`TELEMETRY_EXPORTER=otlp`). Set `TELEMETRY_EXPORTER=console` to print them to `docker compose logs app` instead, or `console,otlp` for both.

Configuration lives in `observability/`.

## Incident responder

`incident-response/responder.py` receives Grafana alert webhooks at `POST /alerts` on port 8001, saves evidence (endpoint, logs, traces, metrics) to `incident-response/incidents/<id>/`, starts a coding agent in headless mode, then verifies the result (tests + re-running failing requests).

```bash
uv run --project incident-response python incident-response/responder.py
```

The agent command is set with `AGENT_CMD` (default: Claude Code `claude -p`). See `docs/HOMEWORK-4-GUIDE.md`.
