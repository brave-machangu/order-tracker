"""OpenTelemetry setup for Order Tracker: metrics, logs, and traces.

Exporters are chosen with the TELEMETRY_EXPORTER environment variable:

* ``console``      - print signals to stdout (read them with ``docker compose logs app``)
* ``otlp``         - send signals to an OpenTelemetry Collector over OTLP/HTTP
* ``console,otlp`` - both
* ``none``         - disable exporting (used by the unit tests)

The OTLP endpoint comes from the standard ``OTEL_EXPORTER_OTLP_ENDPOINT``
variable (for example ``http://otel-collector:4318``).
"""

import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from starlette.routing import Match

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "order-tracker")

logger = logging.getLogger("order_tracker")
tracer = trace.get_tracer("order_tracker")
meter = metrics.get_meter("order_tracker")

# The request metric. In Prometheus it becomes ``order_tracker_requests_total``
# with labels ``http_method``, ``http_route`` and ``http_status_code``.
REQUESTS = meter.create_counter(
    "order_tracker.requests",
    unit="{request}",
    description="HTTP requests handled by Order Tracker, by route and status code",
)
DURATION = meter.create_histogram(
    "order_tracker.request.duration",
    unit="s",
    description="HTTP request duration, by route and status code",
    # The SDK's default buckets are sized for milliseconds; use second-sized ones.
    explicit_bucket_boundaries_advisory=[
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
    ],
)
ORDER_LOOKUPS = meter.create_counter(
    "order_tracker.order_lookups",
    unit="{lookup}",
    description="Order lookups by result (found, not_found, error)",
)


def _exporters():
    value = os.getenv("TELEMETRY_EXPORTER", "console")
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def setup_telemetry(app: FastAPI) -> None:
    """Configure providers and instrument the FastAPI app (idempotent)."""
    if getattr(app.state, "telemetry_ready", False):
        return
    app.state.telemetry_ready = True

    selected = _exporters()
    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": os.getenv("APP_VERSION", "local"),
            "deployment.environment": os.getenv("APP_ENV", "dev"),
        }
    )
    interval_ms = int(os.getenv("METRIC_EXPORT_INTERVAL_MS", "10000"))

    if "none" not in selected:
        # Traces
        tracer_provider = TracerProvider(resource=resource)
        # Metrics
        readers = []
        # Logs
        logger_provider = LoggerProvider(resource=resource)

        if "console" in selected:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            readers.append(
                PeriodicExportingMetricReader(
                    ConsoleMetricExporter(), export_interval_millis=interval_ms
                )
            )
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(ConsoleLogExporter())
            )

        if "otlp" in selected:
            # Imported lazily so console-only runs do not need the endpoint.
            from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                OTLPLogExporter,
            )
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(), export_interval_millis=interval_ms
                )
            )
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter())
            )

        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

        # Python logging -> OpenTelemetry logs (trace_id/span_id are attached
        # automatically when a log is written inside a request span).
        otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger.addHandler(otel_handler)

    # Plain stdout logs too, so `docker compose logs app` stays readable.
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(stream)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Automatic server spans for every request (records exceptions on 5xx).
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")

    @app.middleware("http")
    async def record_request_metrics(request: Request, call_next):
        route = route_template(app, request)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            if route != "/healthz":
                attributes = {
                    "http.method": request.method,
                    "http.route": route,
                    "http.status_code": status_code,
                }
                REQUESTS.add(1, attributes)
                DURATION.record(time.perf_counter() - start, attributes)


def route_template(app: FastAPI, request: Request) -> str:
    """Return the route template (``/api/orders/{order_id}``), not the raw path.

    Using the template keeps metric cardinality low: every order id shares
    one time series.
    """
    for route in app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return "unmatched"


def current_trace_id() -> str:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else ""
