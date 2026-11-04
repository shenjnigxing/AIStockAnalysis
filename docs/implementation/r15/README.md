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

## Delivery verification update (2026-11-04)

The completed acceptance run [40686828044](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/40686828044) validated commit `2dfbcfbd9165df57bfe16c0eb07c4d9af3a54b91`: **286 API/unit tests and 13 browser tests passed**, including the actual API notebook flow and explicit-discard recovery regression. Production build, operations-handler security checks and dependency audit also passed in that run.

Desktop and 390px mobile screenshots were inspected. The desktop connects the selected instrument, source-labelled quote, interactive observation trace and saved thesis. The initial mobile order placed the editor too far below other panels; the final mobile adjustment places selected evidence and the notebook before category/watchlist/workflow panels. The mobile acceptance asserts this order and checks document overflow. No price data was invented to fill empty states. Browser screenshots use labelled fixtures, while the notebook integration uses the actual API.

Temporary draft recovery is scoped to one browser tab and is not a backup, multi-draft store or concurrent-edit merge. Source-cache history remains a collection-observation trace, not exchange OHLC. The overview loads at most 100 instruments in the UI; a missing row does not prove a missing database quote. SQL output bounds are not a constant-time guarantee on large histories.

The final mobile-adjusted build is revalidated in [41767952990](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/41767952990); final outcome is recorded below after completion.

### Final acceptance result

**Passed**: [41768135638](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/41768135638), validated commit `3b7805ba89e4b5148a1ce51ae996db8a7b7d4151`.

- 286 API/unit tests passed.
- 14 Chromium browser tests passed, including the actual notebook API, desktop/mobile layouts, stale-response isolation, keyboard point inspection, draft/discard/history recovery, deletion confirmation, failure feedback and combined category/search/horizon/incomplete-note filters.
- Production build, type validation, operations-handler security test and production dependency audit passed.
- Mobile-adjusted screenshots were downloaded and inspected from successful run 41767952990; its application code matches the final acceptance run. Selected quote, trajectory and notebook appear before categories/watchlist on mobile, with no document overflow in the acceptance scenario.
- Windows startup for the mobile-adjusted application also passed: [41767953004](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/41767953004).

The repository delivery remains a draft PR. This evidence establishes the scoped research-workspace behavior; it does not certify live provider stability, financial data coverage or investment returns.
