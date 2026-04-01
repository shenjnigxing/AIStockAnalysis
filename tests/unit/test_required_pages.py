from pathlib import Path


def test_required_pages_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    required = [
        "apps/web/app/login/page.tsx",
        "apps/web/app/dashboard/page.tsx",
        "apps/web/app/data-center/page.tsx",
        "apps/web/app/scanner/page.tsx",
        "apps/web/app/strategies/page.tsx",
        "apps/web/app/recommendations/page.tsx",
        "apps/web/app/stock/[symbol]/page.tsx",
        "apps/web/app/backtests/page.tsx",
        "apps/web/app/paper-trading/page.tsx",
        "apps/web/app/live-trading/page.tsx",
        "apps/web/app/portfolio/page.tsx",
        "apps/web/app/notifications/page.tsx",
        "apps/web/app/settings/page.tsx",
        "apps/web/app/replay/page.tsx",
        "apps/web/app/init/page.tsx",
    ]
    for rel in required:
        assert (root / rel).exists(), f"Missing page route file: {rel}"
