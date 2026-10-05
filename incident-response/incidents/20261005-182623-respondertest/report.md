# Incident 20261005-182623-respondertest — report

**Outcome: test alert acknowledged. No incident, no fix, no deploy, no commit.**

## What happened

Grafana sent the `ResponderTest` alert with label `test=true` and the summary
"Test notification; no incident to fix". The responder started this run
automatically.

## Root cause

None. This is a test notification of the alert-to-responder pipeline, not a
service failure. The evidence agrees:

- `5xx_last_5m_by_endpoint` is empty: no 5xx responses in the window.
- The only non-2xx traffic is `GET /api/orders/standard-1002` returning 404
  (two requests, user agent `curl/8.21.0`, at 18:23:10 and 18:25:29 UTC).
  The traceback shows `app/main.py` line 116 raising
  `HTTPException(404, "Order not found")` on purpose, which is the handled
  not-found path, not a crash.

## The fix

None made. Per policy step 2, no files were changed other than this report.
`app/`, `tests/`, `observability/` and `incident-response/` are untouched.

## How I verified

- Read `evidence.md` and `alert.json`: label `test=true`, alertname
  `ResponderTest`, no endpoint, no dashboard.
- Checked the metrics section of `evidence.md`: zero 5xx series, one 404 series.
- Did not reproduce with curl, run the test suite, or redeploy, since policy
  step 2 ends the run for test notifications.

## Follow-ups

- The `order.lookup` span is marked `STATUS_CODE_ERROR` and records an
  exception for a plain 404. That is why two handled not-found lookups show up
  under "Error traces". If an expected 404 should not count as an error trace,
  a developer may want to change how the span is marked. Not changed here: it
  is not a failure and is out of scope for a test alert.
- I did not check whether `standard-1002` is an order id that should exist.
  If it is, the 404 itself is worth a look.
