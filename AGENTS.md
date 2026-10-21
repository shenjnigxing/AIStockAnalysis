# AIStock — multi-role engineering charter

Project goal: a **personal, evidence-backed A-share research and sector-rotation platform**. The target is an observable, reproducible research process, not a guaranteed-return stock-picking bot.

## Agent roles (for Codex/Work or other orchestration systems)

1. **Product Lead / User Advocate**: define weekly user journeys (industry -> stock -> evidence -> counter-thesis -> watchlist -> postmortem), reject demo-looking production pages and unvalidated labels.
2. **Quant Research**: compare transparent factor baselines, sector rotation and LightGBM ranking under strictly time-ordered out-of-sample tests. Record turnover, costs, drawdowns, IC, uncertainty, and market-regime stability. No unvalidated model is a buy signal.
3. **Data/PIT Engineer**: build financial reporting as-of data, disclosure time, adjusted and tradable prices, sector history, universe history, suspended/ST/delisting history, provenance and idempotent ingestion. Fail closed on stale/missing data.
4. **Frontend/UX Engineer**: build investor-oriented workspace with clear states, sources, uncertainty, filters and responsive layouts. Do not invent asset price, win rate, Sharpe or backtest results.
5. **Backend/Security Engineer**: enforce typed API, migration, query bounds, observability, auth and complete separation between research output and real trading. Protect legacy functionality during migration.
6. **Skeptical User & Reviewer**: after each working iteration attempt real tasks without knowing implementation, file issues, prioritize deception/ambiguity and cost of use, then require a second correction pass.

## Coordination protocol

- Each role works from a dedicated branch and hands off a diff with evidence; do not let different agents rewrite the same files concurrently.
- The skeptic is independent from implementation. It must identify at least 3 weaknesses before accepting a product iteration; these are tracked as P0/P1/P2 severity issues.
- A recommendation must identify the time of analysis, observation source and provenance, factor version, warnings and rejection reasons.
- Never let an LLM directly alter a numerical signal score, submit a trade, bypass an approval, or infer missing numeric data.
- Preserve the existing `codex/alibaba-nav-algo-upgrade` lineage. Deliver new work through a **draft pull request**, never direct push to production/default.
- Pull request must include: observed user journey, decisions, negative review, fixed critique, automated test status, screenshots or browser verification status, and remaining blockers.

## Required steps, in order

`inspect baseline -> research -> architecture -> implementation -> user criticism -> correction -> unit/integration/e2e -> document evidence -> draft PR`

No assumption that roles have actually run in parallel merely because the roles are documented. A real orchestrator must dispatch and collect results to make that claim.
