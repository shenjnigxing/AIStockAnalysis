from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationSnapshot:
    symbol: str
    level: str
    total_score: float
    risk_score: float
    action_suggestion: str
