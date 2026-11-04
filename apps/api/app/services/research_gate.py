"""One fail-closed policy for legacy numerical research.

DailyBar/RealtimeQuote carry no per-row PIT/provenance contract. A readiness
summary or an environment toggle must never promote those rows to verified data.
"""
import os


class ResearchEligibilityError(ValueError):
    pass


def explicit_test_demo() -> bool:
    return (os.getenv("APP_ENV", "dev").strip().lower() == "test"
            and os.getenv("MARKET_DATA_MODE", "real").strip().lower() == "mock")


def require_legacy_research_eligibility() -> None:
    if not explicit_test_demo():
        raise ResearchEligibilityError(
            "Legacy research data lacks per-row source/PIT verification; real recommendations and backtests are blocked. "
            "Public quotes remain available as unverified observations.")


def research_contract() -> dict:
    return {"source_grade": "synthetic_demo" if explicit_test_demo() else "unverified_legacy_store",
            "factor_version": "legacy-research-r14", "validated_alpha": False,
            "research_eligible": False, "can_trade": False,
            "confidence_is_probability": False}
