# R15 independent skeptical-user review

Reviewed commit: `2d0f7b9`. Reviewer worked on dedicated branch `review/r15-skeptic`, independently of implementation. Evidence below is source/state-path review, not a claim of executed browser tasks; local browser binary download was unavailable. Browser acceptance and screenshot inspection remain separate gates.

## Findings before correction

### S15-01 — P1: manually checked instrument can disagree with research identity

Observed path: choose AAPL, enter thesis, then type MSFT into `检查标的代码` and press `检查快照`. The handler calls `invalidate();setSymbol(...)` directly and does not call `transition` or update `draft.symbol`. MSFT evidence can therefore remain beside an AAPL research note; save still posts AAPL. Conversely, typing a new `研究标的代码` only changes the draft while old evidence remains visible.

Required correction: a single committed instrument context across quote/history/editor, or an explicit separate search query which changes committed context only through a guarded selection. Manual draft identity edits must clear conflicting evidence. A pending write must prevent every context-changing control.

### S15-02 — P1: new-record and candidate paths retain mismatched evidence

`newNote()` resets only editor fields, leaving quote/history/symbol at the prior instrument. Candidate selection changes symbol and quote but does not populate/reset the editor. These bypass the advertised same-instrument research journey even though the market-row path uses `discover()` correctly.

Required correction: route every identity-changing entry point through one context application function; new blank research must clear old selected evidence, and candidates must populate the same draft identity.

### S15-03 — P1: sidebar navigation bypasses unsaved protection

The unsaved link interceptor is `onClickCapture` on `.rt`. `AppShell` renders the sidebar and header links outside this subtree. A Next Link such as the sidebar's `行情源与账户` can perform SPA navigation without firing `beforeunload`, dropping an unsaved note without the inline discard prompt.

Required correction: protect all relevant in-app link navigation, including AppShell links; test a sidebar link while a draft is dirty. Browser reload/closing still needs `beforeunload` as a separate safeguard.

### S15-04 — P2: invalid save can retain an old success message

After saving successfully, clear the thesis and click save. The validation branch sets `saveError` and returns before clearing `notice`; old success feedback can coexist with a failure. `remove()` similarly does not clear prior status before a failed deletion.

Required correction: clear success feedback at the start of any attempted mutation, including client validation failure; preserve user input and identify the current result accurately.

### S15-05 — P2: discard prompt can be outside the user's viewport

The inline unsaved prompt is inserted near the top of a potentially long terminal page. There is no focus or scroll management when a lower-page action triggers it, so the user can experience an apparently unresponsive control. Its alert role announces text but does not move keyboard focus to the decision.

Required correction: bring the prompt into view and move focus to its safe action, or use an accessible focused confirmation dialog. Restore sensible focus after cancel/confirm.

## Required second-pass acceptance

- Manual lookup, draft-code editing, new record and candidate paths all preserve one instrument identity or explicitly clear stale evidence.
- Dirty sidebar navigation requires discard; cancel preserves note and location.
- Save/delete failures never coexist with a previous successful status.
- Unsaved confirmation is visible and keyboard reachable even when triggered near the bottom of the page.
- Re-run existing market/row async race tests plus the added cases; retain fixture-vs-real-API evidence separation.

No P0 trading bypass or fabricated numeric output was identified in the reviewed frontend diff. That is a scoped review observation, not a broad security or investment-quality certification.
