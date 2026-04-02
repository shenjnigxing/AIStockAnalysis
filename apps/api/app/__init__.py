from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_repo_packages() -> None:
    # Allow the API composition layer (apps/api) to import extracted domain modules
    # stored in top-level services/* and packages/* directories.
    repo_root = Path(__file__).resolve().parents[3]
    module_roots = [
        repo_root / "services" / "data-ingest",
        repo_root / "services" / "screener",
        repo_root / "services" / "strategy-engine",
        repo_root / "services" / "recommendation-engine",
        repo_root / "services" / "backtest-engine",
        repo_root / "services" / "paper-trading",
        repo_root / "services" / "broker-adapter",
        repo_root / "services" / "risk-engine",
        repo_root / "services" / "notification-service",
        repo_root / "packages" / "common",
        repo_root / "packages" / "contracts",
        repo_root / "packages" / "config",
        repo_root / "packages" / "logger",
    ]
    for root in module_roots:
        root_str = str(root)
        if root.exists() and root_str not in sys.path:
            sys.path.insert(0, root_str)


_bootstrap_repo_packages()
