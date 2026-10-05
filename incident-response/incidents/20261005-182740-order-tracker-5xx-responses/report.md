# Incident report: 20261005-182740-order-tracker-5xx-responses

- Alert: Order Tracker 5xx responses (critical, firing since 2026-10-05T18:27:30Z)
- Endpoint: `GET /api/orders/{order_id}`
- Outcome: **FIXED** and redeployed

## What happened

`GET /api/orders/express-1002` returned HTTP 500 (`Internal Server Error`).
The error log and trace `65d51d527e694e0628167870f1ace7df` both show:

```
File "/app/app/main.py", line 60, in order_detail
    estimated_at = placed_at.replace(day=placed_at.day + 2)
ValueError: day is out of range for month
```

The order was placed on 2026-09-30, so the code asked for "September 32nd".

The two `standard-1002` entries in the evidence are ordinary 404s for an order id
that does not exist. They are warnings, not part of this failure, and are unchanged.

## Root cause

`order_detail()` in `app/main.py` computed the express delivery estimate by adding 2
to the day-of-month number (`placed_at.replace(day=placed_at.day + 2)`) instead of
adding two days to the date. That raises `ValueError` for any express order placed on
one of the last two days of a month. Standard orders skip this code path, which is why
only express orders were affected.

The same function is reached from `POST /api/orders` and `PATCH /api/orders/{order_id}`
(both return `get_order(...)`), so creating or updating an express order on those days
would have failed with a 500 as well, after the database write had already been committed.

## The fix

One line in `app/main.py`:

```diff
-        estimated_at = placed_at.replace(day=placed_at.day + 2)
+        estimated_at = placed_at + timedelta(days=2)
```

`timedelta` was already imported. No data or schema change.

Regression tests added in `tests/test_api.py`:

- `test_express_order_placed_at_month_end` - requests the seeded `express-1002` order
  (always seeded on the last day of the previous month) and expects 200 with an
  `estimated_delivery`.
- `test_express_estimated_delivery_rolls_over_month` - calls `order_detail()` with fixed
  dates: month end (09-30), year end (12-31), leap-year February (2028-02-28) and a
  mid-month control (10-05).

## Verification

1. Reproduced before the fix: `curl http://localhost:8000/api/orders/express-1002` -> `HTTP 500`.
2. With the fix reverted, `uv run --frozen pytest -q` -> `4 failed, 4 passed`
   (the new tests fail with `ValueError: day is out of range for month`; the mid-month
   control passes, as expected).
3. With the fix applied, `uv run --frozen pytest -q` -> `8 passed`.
4. Redeployed with `docker compose up --build -d --wait app`; the app container reported Healthy.
5. After redeploy:
   - `GET /api/orders/express-1002` -> `HTTP 200`, `"estimated_delivery":"2026-10-02"`
   - `GET /api/orders/standard-1001` -> `HTTP 200`
   - `GET /api/orders/standard-1002` -> `HTTP 404` (order does not exist, expected)
   - `GET /healthz` -> `HTTP 200`

Not checked: I did not wait for the Grafana alert to move back to normal. It should
clear by itself once the 500 drops out of the 5-minute window.

## Follow-ups

- Confirm in Grafana that the alert resolves.
- `create_order` and `update_status` commit the database write before building the
  response through `get_order()`. If the response step fails, the client sees a 500 for
  a change that was saved. Worth reviewing separately; not changed here.
- The "+2 days" estimate is plain calendar days. If express delivery should skip
  weekends or holidays, that is a product decision and is not handled.
- Commit is local on branch `homework-4` and has not been pushed.
