from pathlib import Path


def test_phase0_directories_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    required = [
        "apps/api",
        "apps/web",
        "services",
        "packages",
        "data",
        "infra",
        "tests",
        "docs",
    ]
    for rel in required:
        assert (root / rel).exists(), f"Missing: {rel}"

