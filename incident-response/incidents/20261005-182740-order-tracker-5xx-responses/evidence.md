# Incident 20261005-182740-order-tracker-5xx-responses

- Alert: **Order Tracker 5xx responses** (firing)
- Test notification: no
- Endpoint: GET /api/orders/{order_id}
- Time window: 5m; evidence covers the last 15 minutes
- Started at: 2026-10-05T18:27:30Z
- Dashboard: http://localhost:3000/d/order-tracker?orgId=1
- Panel: http://localhost:3000/d/order-tracker?orgId=1&viewPanel=5
- Summary: Order Tracker returned 5xx responses on GET /api/orders/{order_id}
- Description: About 1 server errors (HTTP 5xx) on endpoint GET /api/orders/{order_id} in the last 5 minutes.
- Labels: `{"alertname": "Order Tracker 5xx responses", "grafana_folder": "Order Tracker Alerts", "http_method": "GET", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "orders"}`
- Affected request paths: /api/orders/express-1002, /api/orders/standard-1002

## Error and warning logs (newest first)

- `2026-10-05T18:27:15.507030+00:00` ERROR: order lookup failed order_id=express-1002 priority=express created_at=2026-09-30T18:20:03.259964+00:00 status=500 trace_id=65d51d527e694e0628167870f1ace7df
- `2026-10-05T18:25:29.305484+00:00` WARN: order lookup not found order_id=standard-1002 status=404 trace_id=73455354a03b81d9e9bbf445c34ccb05
- `2026-10-05T18:23:10.934127+00:00` WARN: order lookup not found order_id=standard-1002 status=404 trace_id=3e88d627a111dc814c7524eabd84cc51

## Error traces

### Trace 65d51d527e694e0628167870f1ace7df (/api/orders/express-1002)
- span `order.lookup` status=STATUS_CODE_ERROR attrs={"order.id": "express-1002", "order.priority": "express"}
  - exception ValueError: day is out of range for month

```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 602, in use_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/__init__.py", line 1136, in start_as_current_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 441, in start_as_current_span
    yield span
  File "/app/app/main.py", line 119, in get_order
    order = order_detail(row)
            ^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 60, in order_detail
    estimated_at = placed_at.replace(day=placed_at.day + 2)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: day is out of range for month
```

- span `GET /api/orders/{order_id} http send` status=STATUS_CODE_ERROR attrs={"http.status_code": "500"}
- span `GET /api/orders/{order_id} http send` status=unset attrs={}
- span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR attrs={"http.scheme": "http", "http.host": "10.215.24.7:8000", "http.flavor": "1.1", "http.target": "/api/orders/express-1002", "http.server_name": "localhost:8000", "http.user_agent": "curl/8.21.0", "http.route": "/api/orders/{order_id}", "http.method": "GET", "http.url": "http://localhost:8000/api/orders/express-1002", "http.status_code": "500"}
  - exception ValueError: day is out of range for month

```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/instrumentation/fastapi/__init__.py", line 360, in __call__
    await self.app(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/middleware/base.py", line 193, in __call__
    response = await self.dispatch_func(request, call_next)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/telemetry.py", line 149, in record_request_metrics
    response = await call_next(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/starlette/middleware/base.py", line 168, in call_next
    raise app_exc from app_exc.__cause__ or app_exc.__context__
  File "/app/.venv/lib/python3.12/site-packages/starlette/middleware/base.py", line 144, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/app/.venv/lib/python3.12/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/routing.py", line 670, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 2734, in app
    await route.handle(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 1281, in handle
    await super().handle(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/routing.py", line 280, in handle
    await self.app(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 158, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 144, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 706, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 354, in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/starlette/concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 119, in get_order
    order = order_detail(row)
            ^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 60, in order_detail
    estimated_at = placed_at.replace(day=placed_at.day + 2)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: day is out of range for month
```

### Trace 73455354a03b81d9e9bbf445c34ccb05 (/api/orders/standard-1002)
- span `order.lookup` status=STATUS_CODE_ERROR attrs={"order.id": "standard-1002"}
  - exception fastapi.exceptions.HTTPException: 404: Order not found

```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 602, in use_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/__init__.py", line 1136, in start_as_current_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 441, in start_as_current_span
    yield span
  File "/app/app/main.py", line 116, in get_order
    raise HTTPException(404, "Order not found")
fastapi.exceptions.HTTPException: 404: Order not found
```

- span `GET /api/orders/{order_id} http send` status=unset attrs={"http.status_code": "404"}
- span `GET /api/orders/{order_id} http send` status=unset attrs={}
- span `GET /api/orders/{order_id} http send` status=unset attrs={}
- span `GET /api/orders/{order_id}` status=unset attrs={"http.scheme": "http", "http.host": "10.215.24.7:8000", "http.flavor": "1.1", "http.target": "/api/orders/standard-1002", "http.server_name": "localhost:8000", "http.user_agent": "curl/8.21.0", "http.route": "/api/orders/{order_id}", "http.method": "GET", "http.url": "http://localhost:8000/api/orders/standard-1002", "http.status_code": "404"}
### Trace 3e88d627a111dc814c7524eabd84cc51 (/api/orders/standard-1002)
- span `order.lookup` status=STATUS_CODE_ERROR attrs={"order.id": "standard-1002"}
  - exception fastapi.exceptions.HTTPException: 404: Order not found

```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 602, in use_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/__init__.py", line 1136, in start_as_current_span
    yield span
  File "/app/.venv/lib/python3.12/site-packages/opentelemetry/trace/__init__.py", line 441, in start_as_current_span
    yield span
  File "/app/app/main.py", line 116, in get_order
    raise HTTPException(404, "Order not found")
fastapi.exceptions.HTTPException: 404: Order not found
```

- span `GET /api/orders/{order_id} http send` status=unset attrs={"http.status_code": "404"}
- span `GET /api/orders/{order_id} http send` status=unset attrs={}
- span `GET /api/orders/{order_id} http send` status=unset attrs={}
- span `GET /api/orders/{order_id}` status=unset attrs={"http.scheme": "http", "http.host": "10.215.24.7:8000", "http.flavor": "1.1", "http.target": "/api/orders/standard-1002", "http.server_name": "localhost:8000", "http.user_agent": "curl/8.21.0", "http.route": "/api/orders/{order_id}", "http.method": "GET", "http.url": "http://localhost:8000/api/orders/standard-1002", "http.status_code": "404"}

## Metrics

```json
{
  "5xx_last_5m_by_endpoint": {
    "status": "success",
    "data": {
      "resultType": "vector",
      "result": [
        {
          "metric": {
            "http_method": "GET",
            "http_route": "/api/orders/{order_id}",
            "http_status_code": "500"
          },
          "value": [
            1791224862.128,
            "0"
          ]
        }
      ]
    }
  },
  "requests_last_5m_by_endpoint_and_status": {
    "status": "success",
    "data": {
      "resultType": "vector",
      "result": [
        {
          "metric": {
            "http_method": "GET",
            "http_route": "/api/orders/{order_id}",
            "http_status_code": "404"
          },
          "value": [
            1791224862.131,
            "1.0277634230655315"
          ]
        },
        {
          "metric": {
            "http_method": "GET",
            "http_route": "/api/orders/{order_id}",
            "http_status_code": "500"
          },
          "value": [
            1791224862.131,
            "0"
          ]
        }
      ]
    }
  }
}
```
