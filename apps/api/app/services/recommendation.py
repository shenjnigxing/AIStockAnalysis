import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import RecommendationResult, RecommendationRun, ScreenerCandidate, StrategySignal
from app.services.audit import write_audit


def _to_level(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    return "D"


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, market_state: str = "neutral", llm_enabled: bool = False) -> RecommendationRun:
        run = RecommendationRun(status="completed", market_state=market_state)
        self.db.add(run)
        self.db.flush()

        candidates = list(self.db.scalars(select(ScreenerCandidate).order_by(ScreenerCandidate.rank_no).limit(200)).all())
        latest_signals = list(
            self.db.scalars(
                select(StrategySignal)
                .order_by(desc(StrategySignal.created_at))
                .limit(5000)
            ).all()
        )

        grouped_signals: dict[str, list[StrategySignal]] = defaultdict(list)
        for sig in latest_signals:
            grouped_signals[sig.symbol].append(sig)

        rows: list[RecommendationResult] = []
        for c in candidates:
            signals = grouped_signals.get(c.symbol, [])
            hit_signals = [s for s in signals if s.hit]
            strategy_boost = sum(s.score for s in hit_signals) / max(1, len(hit_signals)) if hit_signals else 0
            quant_score = round(min(100.0, c.base_score * 0.6 + strategy_boost * 0.4), 2)
            risk_score = round(15.0 if "high_volatility" in (c.risk_hints or "") else 5.0, 2)
            llm_adj = 3.0 if llm_enabled and hit_signals else 0.0
            total = round(quant_score - risk_score + llm_adj, 2)
            level = _to_level(total)
            hit_keys = [s.strategy_key for s in hit_signals][:8]
            reasons = [f"base_score={c.base_score}", f"strategy_hits={len(hit_signals)}", f"market_state={market_state}"]
            row = RecommendationResult(
                recommendation_run_id=run.id,
                symbol=c.symbol,
                final_rank=0,
                recommendation_level=level,
                total_score=total,
                quant_score=quant_score,
                risk_score=risk_score,
                llm_score_adjustment=llm_adj,
                hit_strategies=json.dumps(hit_keys, ensure_ascii=True),
                reasons=json.dumps(reasons, ensure_ascii=True),
                llm_explanation="Mock explainer: momentum and signal resonance support this ranking." if llm_enabled else "",
                counter_arguments=json.dumps(["watch volatility"], ensure_ascii=True),
                risk_tags=json.dumps(["high_volatility"] if risk_score >= 15 else [], ensure_ascii=True),
                action_suggestion="execute" if level == "A" else "observe",
                confidence_level=round(min(1.0, total / 100 + 0.25), 2),
                created_at=datetime.utcnow(),
            )
            rows.append(row)

        rows.sort(key=lambda x: x.total_score, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.final_rank = idx
            self.db.add(row)

        write_audit(
            self.db,
            action="recommendation.run",
            detail=f"run_id={run.id}; market_state={market_state}; llm_enabled={llm_enabled}; items={len(rows)}",
        )
        self.db.commit()
        self.db.refresh(run)
        return run

    def latest(self) -> list[RecommendationResult]:
        run = self.db.scalar(select(RecommendationRun).order_by(desc(RecommendationRun.created_at)))
        if run is None:
            return []
        return list(
            self.db.scalars(
                select(RecommendationResult)
                .where(RecommendationResult.recommendation_run_id == run.id)
                .order_by(RecommendationResult.final_rank)
            ).all()
        )
