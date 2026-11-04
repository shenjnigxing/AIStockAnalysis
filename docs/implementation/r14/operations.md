# R14 operational remediation

Implemented in independent branch `fix/r14-operations`; no product-model or frontend-source edits.

| Work package | Change | Validation |
|---|---|---|
| G03 | Test conftest checks URL before any application engine import, refuses persistent URLs, supplies in-memory DB by default and rejects an already-imported persistent engine | Isolated subprocess refuses file URL while an SQLite sentinel remains unchanged; no-URL import selects memory |
| O01/O02, S03 | Personal Compose stack uses only API/Web, host loopback ports and shared host `./data`; no exposed unused PostgreSQL/Redis or fixed PG password | Configuration assertions; Docker runtime unavailable |
| O02 | Database initialization inspects existing model table columns, type affinities and primary keys before create_all; incompatible structure refuses startup without row/schema mutation | Isolated incompatible-schema sentinel test; normal full backend tests pass |
| O03 | Makefile accepts portable PYTHON and runs API tests under explicit memory DB | Static command review and direct equivalent full suite |
| O04 | Collector catches per-item SQLAlchemy failures, attempts rollback, emits normalized failure without credentials and continues subsequent instruments/cycles | Real collector with injected storage failure; next item and next cycle succeed |
| O05 | Docker frontend copies lock and runs npm ci; container listens on network interface; source mount no longer hides installed dependencies; root dockerignore excludes host node_modules/.next/.env/data | Configuration assertions; no Docker build claimed |

Commands in the worktree with `/tmp/aistock-r14/bin/python` and explicit `DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api`:

- `pytest -q apps/api/tests/test_r14_operations.py apps/api/tests/test_local_collection_r12.py --disable-warnings`: **15 passed**.
- `pytest -q apps/api/tests tests/unit --disable-warnings`: **199 passed** (194 original + 5 operational tests).
- `git diff --check`: passed.

Limits: schema preflight is a safe refusal mechanism, not an automated migration framework or live backup protocol. It does not infer that a user database has already failed an upgrade. Cross-process quote locking is still not implemented; personal single-collector operation remains the supported mode. No new Windows or Docker runtime execution was possible in this worktree, and no real external provider/account was contacted.
