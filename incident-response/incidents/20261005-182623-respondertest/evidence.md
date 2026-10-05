# Incident 20261005-182623-respondertest

- Alert: **ResponderTest** (firing)
- Test notification: yes
- Endpoint: unknown
- Time window: n/a; evidence covers the last 15 minutes
- Started at: n/a
- Dashboard: n/a
- Panel: n/a
- Summary: Test notification; no incident to fix
- Description: n/a
- Labels: `{"alertname": "ResponderTest", "test": "true"}`
- Affected request paths: /api/orders/standard-1002

## Error and warning logs (newest first)

- `2026-10-05T18:25:29.305484+00:00` WARN: order lookup not found order_id=standard-1002 status=404 trace_id=73455354a03b81d9e9bbf445c34ccb05
- `2026-10-05T18:23:10.934127+00:00` WARN: order lookup not found order_id=standard-1002 status=404 trace_id=3e88d627a111dc814c7524eabd84cc51

## Error traces

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
      "result": []
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
            1791224786.823,
            "1.0373326910328808"
          ]
        }
      ]
    }
  }
}
```
