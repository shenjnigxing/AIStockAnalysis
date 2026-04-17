# AIStockAnalysis product-oriented remediation plan

Goal: unify startup/runtime behavior, improve portability, and simplify page responsibilities so the app behaves consistently as a product.

Tasks:
1. Add failing tests for startup consistency, route behavior, and portable config assumptions.
2. Refactor backend startup into a single canonical app setup path used by all entry points.
3. Simplify run_api.py into a thin runner and make Playwright config portable.
4. Apply fast PM-oriented frontend fixes: standard nav, rename screener templates, reduce homepage overlap, move admin actions out of primary flow where possible.
5. Run pytest and Playwright verification.
