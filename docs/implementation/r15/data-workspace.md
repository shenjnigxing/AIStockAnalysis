# R15 market workspace read models

## Delivered contract

- `GET /api/research/v3/market-data/history?kind=us_equity&symbol=AAPL&limit=90`
  returns `{kind, symbol, points, basis: "collection_snapshots", can_trade: false}`.
  Each point is the existing fully verified quote output, including source,
  units, collection time, source time quality, freshness and integrity hashes.
  The newest 2–240 observations are returned in ascending collection time, with
  insertion ID as a deterministic tie-break. Missing history is an empty list.
- `GET /api/research/v3/market-data/overview?kind=us_equity&limit=100`
  returns `{items, rejected_count, can_trade: false}`. `kind` is optional; the
  limit is 1–200. SQL selects the latest published insertion for each kind and
  symbol, orders by collection time descending, and limits rows before Python
  verification. Corrupt latest observations are omitted and counted, without
  falling back to an older value. The count describes rejected rows in this
  bounded selection, not every historical record in the database.

Both endpoints read the existing cache, do not request upstream providers, and
do not alter the schema, refresh authorization, notebook or trading paths.
Invalid identities and bounds return 422. Any corrupt selected history point
rejects the entire history with 409, avoiding a misleading connected series.

## Display boundary

These are collection observations. They are not OHLC bars, a complete daily
price history, live data, a total-return series or a return benchmark. Repeated
source values can exist when collections refer to the same provider update.
The frontend must label this basis and retain source and freshness warnings.

## Verification

Executed locally on 2026-10-28:

```sh
DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/aistock-r15/bin/python -m pytest -q apps/api/tests/test_r15_workspace_data.py apps/api/tests/test_public_quotes_r11.py apps/api/tests/test_r14_data.py --disable-warnings
```

Result: **59 passed** (106 existing dependency warnings). Tests cover empty
states, canonical identity, kind/symbol isolation, ascending bounded history,
latest-only overview, market filtering, query bounds, integrity failure,
no stale fallback and no provider invocation or cache mutation during reads.
Upstream quotes are explicit fixtures; no live availability claim is made.
