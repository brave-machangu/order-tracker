The incident is fixed and redeployed: `GET /api/orders/express-1002` now returns 200 with `"estimated_delivery":"2026-10-02"` instead of a 500.

- **Root cause:** `order_detail()` in `app/main.py` added 2 to the day-of-month number instead of adding two days to the date. Any express order placed on the last two days of a month raised `ValueError: day is out of range for month`; this one was placed on 2026-09-30.
- **Fix:** one line, now `placed_at + timedelta(days=2)`. No data or schema change.
- **Tests:** added a request test for the seeded month-end express order and a date test covering month end, year end and leap-year February. With the fix reverted, 4 of the 8 tests fail; with it applied, all 8 pass.
- **Deploy check:** the app container came back Healthy, `standard-1001` returns 200 and `/healthz` returns 200.
- **Commit:** `5d66d9e` on `homework-4`, not pushed. Only `app/main.py` and `tests/test_api.py` are in it; the incident folder is left untracked, like the other incident folders.
- **Report:** `report.md` is written in the incident folder.

The `standard-1002` entries in the evidence are ordinary 404s for an order that does not exist, so I left them alone.

Still open:
- I did not wait for the Grafana alert to return to normal; it should clear once the 500 leaves the 5-minute window.
- `POST /api/orders` and `PATCH /api/orders/{order_id}` save to the database before building the response through the same function, so they could return a 500 for a change that was saved. This fix removes the known trigger, but the ordering is worth a separate review.

STATUS: FIXED - express delivery estimate added 2 to the day-of-month instead of adding two days, raising ValueError for orders placed at month end
