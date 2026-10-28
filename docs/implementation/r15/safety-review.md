# R15 independent API/data safety review

Reviewed implementation: `3a9977f` (backend implementation `e9d858b`). Reviewer used a separate worktree/branch and did not modify implementation.

## Executed evidence

- `DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/aistock-r15/bin/python -m pytest -q apps/api/tests/test_r15_workspace_data.py --disable-warnings`: **14 passed**.
- Published one source-stubbed observation through the real cache publication service, then changed its database value to `float('inf')`. History returned **422**, `Unsupported quote instrument`; overview returned **200**, no items, `rejected_count=1`. No live-provider claim is made.
- Ran SQLite `EXPLAIN QUERY PLAN` on the overview aggregate/join. The plan scans snapshots through the kind index and uses temporary B-trees for GROUP BY and ORDER BY; the outer LIMIT does not bound database work.

## Findings

| Severity | Finding | Required correction / release condition |
|---|---|---|
| P2 | A non-finite corrupted cached value is misreported by history as invalid user input422. `_canonical(...allow_nan=False)` raises `ValueError`; the route treats this as unsupported identity. The read still fails closed, but contradicts the documented corruption409 contract and gives the wrong recovery advice. | Explicitly validate cached numerical values inside integrity verification and raise `QuoteIntegrityError`; add a corruption regression covering history409 and overview rejection. |
| P2 | `limit` bounds returned/materialized rows, not the SQL aggregation workload. Full accumulated history participates in max-id-per-instrument grouping. | Do not claim bounded execution time. For the current local personal deployment, document dataset/latency limits and avoid presenting this as a scalable quote service. Larger deployments need an indexed latest-snapshot read model and query/retention budget. |
| P2 | Overview defaults to100 and caps at200 with no pagination or truncation metadata. A caller cannot distinguish “instrument never collected” from “older cached instrument omitted from this result.” `rejected_count` only counts rejected rows inside that selected window. | UI must call missing table values “not in loaded overview” rather than prove absence; expose truncation/scope metadata or pagination before claiming complete market coverage. |

## Positive checks and boundaries

- Exact `kind+symbol` filters isolate history, with stable collection-time/id ordering and explicit `collection_snapshots` semantics.
- Read APIs reuse hash/source/unit verification; corrupted latest data is not silently replaced with older values.
- Query literal/identity/count validation rejects unsupported requests. Read paths do not call external providers or write fetch attempts.
- Responses retain `can_trade=false`, `research_eligible=false`, provenance, source-time quality and freshness. No endpoint promotes notes/observations into numerical signals or orders.
- Hashes detect accidental mutation, not malicious database administrators; these are application-generated hashes, not exchange signatures. A point-in-time data feed, authenticated external source, market history completeness and production-scale capacity were not validated here.

Correction: cached-value integrity verification now explicitly rejects non-finite, nonpositive and out-of-range values before canonical hashing. Five regression cases verify history409 and overview rejection. The full R15 workspace data suite passes19 tests. SQL workload and coverage-window limits remain documented constraints; the frontend must disclose its loaded scope. Final correction integration is recorded in the parent R15 delivery report. This review alone does not accept the full frontend journey or visual quality.
