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

## Independent second pass

Reviewed correction `fc21741` (same frontend correction integrated in root `642a349`). This pass again inspected the implemented event/state paths; it did not execute a browser.

| Finding | Source review result |
|---|---|
| S15-01 | Corrected for reviewed paths. Lookup text is separate from selected identity. Committing a new lookup uses guarded `openInstrument`; draft-code changes invalidate old quote/history. |
| S15-02 | Corrected. New-note clears selected evidence and candidate lookup applies the same instrument context before showing evidence. |
| S15-03 | Corrected for ordinary sidebar/header/internal link clicks. Document capture runs before Next Link navigation and preserves input until explicit discard. Browser history navigation remains a separate gap below. |
| S15-04 | Corrected. Save clears notices before validation; delete clears old mutation status before request. |
| S15-05 | Corrected in source. Prompt scrolls into view, receives programmatic focus, and cancel restores the triggering element. Actual browser focus/visibility remains an e2e check. |

### S15-06 — P1: browser Back/Forward does not pass either navigation guard

A dirty draft is protected by captured document link clicks and `beforeunload`. App Router back/forward navigation can be a same-document `popstate` navigation, firing neither event. A user who entered from another in-app page can still lose a dirty draft by pressing the browser Back button. The revised code has no `popstate` handler or recoverable draft persistence.

Required correction: preserve and offer recovery of unsaved drafts across same-tab history navigation (for example session-scoped storage with a visible recovery decision), or implement tested history navigation protection. Add a real-browser case that navigates to research from another app route, edits a draft, presses Back and returns; the input must be recoverable. Any sensitive local persistence choice should remain scoped to this personal local research product and documented accurately.

Until S15-06 is corrected or explicitly deferred as a known limitation, the broad claim “unsaved work cannot be lost through navigation” is not supported. The five initial findings are otherwise corrected at the source-review level; browser CI must still verify their actual behavior.

## Third pass: history-navigation recovery

Reviewed recovery correction `da9c3a9` directly from the integrated root branch. This is source-level verification; browser tests are owned by the root acceptance run.

S15-06 is corrected at the source level for the intended same-tab history/reload journey:

- Dirty note fields, market, horizon and baseline are written to versioned `sessionStorage`; re-entry restores the selected identity and notebook fields, while quotes remain empty until checked again.
- Recovery validates market/horizon, identifier type, field lengths, baseline shape and dirty state. Invalid or clean recovery entries are removed instead of silently applied.
- The visible recovery banner states that the draft is unsaved and offers a focus action; it does not label browser storage as a server save.
- Successful save, editor reset and explicit discard clear the recovery slot. The explicit-discard navigation action does not mutate persistence dependencies afterward, so the discarded draft is not immediately re-created by the persistence effect.
- Storage read/write failures show a warning, rather than claiming successful protection.

Remaining scoped risks are acceptable as disclosed limitations of this personal local workspace: recovery belongs to the current browser tab/session and is not a durable backup; browser storage policies, tab closure and abrupt process termination can defeat it. There is one recoverable active draft, not a multi-document draft manager. A recovered edit of a server note is not an optimistic-concurrency mechanism; if the note was deleted or modified elsewhere, the server remains authoritative and a save can fail or replace a newer note. No claim of multi-user collaboration or conflict-free edits should be made.

The source-level findings S15-01 through S15-06 now have correction paths. Final delivery still depends on the root's actual browser cases for history return, explicit discard, sidebar navigation, focus and identity consistency. This report does not certify those browser outcomes before they run.
