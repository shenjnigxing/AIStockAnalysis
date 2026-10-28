# R15 — connected daily research workspace

## Product outcome and scope

A user can browse collected instruments, select one, inspect its actual saved observations and source, write a thesis/counter-thesis/invalidation, save it, and return through filtered watchlists. Selection must not mix identities or silently discard edits. The existing R14 safety gates stay in place.

The UI follows the connected watchlist/detail/dashboard interaction patterns documented by [Koyfin](https://www.koyfin.com/features/watchlists/) and [TradingView](https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/). These are interaction references; this implementation does not claim their market coverage or analytical capabilities.

## Architecture

- Read-only bounded overview returns the latest integrity-checked cached snapshot for each instrument. It never triggers a provider request. Corrupted latest snapshots are excluded, not replaced silently by older values.
- Read-only bounded history returns saved collection observations for one exact instrument, in ascending collection-time order. It is not OHLC or a daily price history; collection time is not exchange time.
- Frontend keeps source provenance, unit, age and identity visible. Responses from an old selection cannot overwrite a new selection.
- Notebook persists existing typed user notes. User categories are not market sector classifications. Notes do not become signals or orders.
- No database schema change is required.

## Acceptance criteria

1. Market browser → selected snapshot/history → prefilled research identity → server save → reload/edit works.
2. Sparse/empty history never produces a fabricated trend. Point values and timestamps are accessible without a mouse.
3. Overview/history endpoints validate identities and query bounds, enforce hash checks, remain read-only, and do not make external calls.
4. A pending save locks context; a dirty draft requires explicit discard before context changes. Delete requires explicit confirmation.
5. Search, category, horizon and incomplete-note filters work together. Missing quotes render missing, not zero.
6. Failed requests preserve input, remove stale success feedback and offer a retry path.
7. Desktop and 390px mobile tasks, keyboard behavior, contrast and overflow receive browser checks.

## Explicit delivery limits

This is a personal research workspace, not a validated recommendation engine. Verified sector constituents, point-in-time financial health, market-cap screens, stable live-feed coverage, out-of-sample alpha, brokerage connections and actual trading are not delivered by this iteration. Actual cached-data coverage depends on successful collection. Test fixtures are never production sample prices.

## Evidence

Implementation, independent criticism, correction and test results are recorded below before delivery.

## Corrections and local verification (2026-10-28)

Independent product, data/API and skeptical-user reviews were performed separately from implementation. The skeptic found five issues in the first version, then a sixth browser-history gap. Corrections unify lookup/editor/evidence identity; protect sidebar navigation; clear old success notices before validation; focus and scroll the discard decision; and recover unsaved notes from validated per-tab session storage after Back/Forward navigation. Explicit discard and successful save remove that temporary draft. Storage can fail in restricted browsers; the UI reports that and server saving remains available.

- Python API/unit suite: **286 passed** after the numerical-integrity correction.
- Production Next build and TypeScript validation: passed with the recovery implementation.
- Production dependency audit: 0 vulnerabilities reported during this iteration.
- Actual Next operations handler security regression: passed.
- Local standalone HTTP smoke was attempted but could not establish the runtime loopback connection; it is not counted as a successful integration test. CI runs the actual API notebook create/edit/reload/delete flow separately from mocked market fixture scenarios.
- First browser CI: 8/9 passed; failure was an ambiguous alert locator also matching Next's route announcer. Application alert assertions were scoped, and further real-browser scenarios were added for manual lookup, sidebar navigation, invalid-save feedback and browser-history recovery.

Visual evidence uses clearly labelled `TEST_FIXTURE_NOT_LIVE` data. It proves rendering/interactions, not live provider coverage. Latest browser results and visual inspection are appended when the acceptance run completes.
