import json
from collections import defaultdict
from datetime import datetime
from statistics import mean

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import DailyBar, RecommendationResult, RecommendationRun, ScreenerCandidate, StrategyDefinition, StrategyRun, StrategySignal, RealtimeQuote
from app.services.audit import write_audit
from app.services.strategy_engine import StrategyRegistry


def _to_level(score: float) -> str:
    if score >= 78:
        return "A"
    if score >= 63:
        return "B"
    if score >= 48:
        return "C"
    return "D"


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _loads_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return [str(item) for item in value] if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _risk_from_tags(tags: list[str], market_state: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    if "high_volatility" in tags:
        score += 12.0
        reasons.append("波动风险偏高")
    if "low_liquidity" in tags:
        score += 10.0
        reasons.append("流动性不足")
    if "weak_volume" in tags:
        score += 6.0
        reasons.append("成交量支撑偏弱")
    if "market_state_conflict" in tags:
        score += 8.0
        reasons.append("当前市场状态与战法冲突")
    if market_state == "weak":
        score += 6.0
    elif market_state == "panic":
        score += 12.0
    elif market_state == "neutral":
        score += 2.0
    return min(score, 60.0), reasons


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.registry = StrategyRegistry()

    def _enabled_strategy_keys(self) -> list[str]:
        rows = list(self.db.scalars(select(StrategyDefinition)).all())
        if not rows:
            return [s.strategy_key for s in self.registry.list_strategies()]
        keys = [row.strategy_key for row in rows if row.enabled]
        return keys if keys else [s.strategy_key for s in self.registry.list_strategies()]

    def _latest_quote_by_symbol(self, symbols: list[str]) -> dict[str, RealtimeQuote]:
        if not symbols:
            return {}
        rows = list(
            self.db.scalars(
                select(RealtimeQuote)
                .where(RealtimeQuote.symbol.in_(symbols))
                .order_by(desc(RealtimeQuote.quote_time))
            ).all()
        )
        latest: dict[str, RealtimeQuote] = {}
        for row in rows:
            if row.symbol not in latest:
                latest[row.symbol] = row
        return latest

    def _bars_by_symbol(self, symbols: list[str], limit: int = 30) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for symbol in symbols:
            bars = list(
                self.db.scalars(
                    select(DailyBar).where(DailyBar.symbol == symbol).order_by(desc(DailyBar.trade_date)).limit(limit)
                ).all()
            )
            bars.reverse()
            result[symbol] = [
                {
                    "trade_date": row.trade_date.isoformat(),
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                    "amount": row.amount,
                }
                for row in bars
            ]
        return result

    def _action_suggestion(self, level: str, market_state: str, risk_score: float) -> str:
        if level == "A" and risk_score <= 20:
            return "execute"
        if level == "A":
            return "execute_with_caution"
        if level == "B" and market_state in {"bullish", "neutral"}:
            return "watch_breakout"
        if level == "B":
            return "observe"
        if level == "C":
            return "research"
        return "avoid"

    def run(self, market_state: str = "neutral", llm_enabled: bool = False) -> RecommendationRun:
        run = RecommendationRun(status="completed", market_state=market_state)
        self.db.add(run)
        self.db.flush()

        candidates = list(
            self.db.scalars(
                select(ScreenerCandidate).order_by(ScreenerCandidate.screener_run_id.desc(), ScreenerCandidate.rank_no).limit(200)
            ).all()
        )
        if not candidates:
            write_audit(
                self.db,
                action="recommendation.run",
                detail=f"run_id={run.id}; market_state={market_state}; llm_enabled={llm_enabled}; items=0",
            )
            self.db.commit()
            self.db.refresh(run)
            return run

        symbols = list({c.symbol for c in candidates})
        latest_quotes = self._latest_quote_by_symbol(symbols)
        bars_by_symbol = self._bars_by_symbol(symbols)
        enabled_keys = self._enabled_strategy_keys()

        strategy_run = StrategyRun(scope="batch", symbol="", status="completed")
        self.db.add(strategy_run)
        self.db.flush()

        grouped_signals: dict[str, list[StrategySignal]] = defaultdict(list)
        for symbol in symbols:
            quote = latest_quotes.get(symbol)
            quote_context = (
                {
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "volume": quote.volume,
                    "amount": quote.amount,
                }
                if quote
                else {}
            )
            context = {
                "market_state": market_state,
                "quote": quote_context,
                "daily_bars": bars_by_symbol.get(symbol, []),
            }
            outputs = self.registry.evaluate(symbol=symbol, strategy_keys=enabled_keys, context=context)
            for output in outputs:
                row = StrategySignal(
                    strategy_run_id=strategy_run.id,
                    symbol=symbol,
                    strategy_key=output.strategy_key,
                    hit=output.hit,
                    score=output.score,
                    confidence=output.confidence,
                    reasons=json.dumps(output.reasons, ensure_ascii=True),
                    risk_tags=json.dumps(output.risk_tags, ensure_ascii=True),
                    feature_snapshot=json.dumps(output.feature_snapshot, ensure_ascii=True),
                    market_fit_score=output.market_fit_score,
                    conflict_tags=json.dumps(output.conflict_tags, ensure_ascii=True),
                    created_at=datetime.utcnow(),
                )
                self.db.add(row)
                grouped_signals[symbol].append(row)

        rows: list[RecommendationResult] = []
        for c in candidates:
            signals = grouped_signals.get(c.symbol, [])
            hit_signals = [s for s in signals if s.hit]
            candidate_risks = _loads_json_list(c.risk_hints)
            signal_risks = []
            conflict_tags = []
            for signal in hit_signals:
                signal_risks.extend(_loads_json_list(signal.risk_tags))
                conflict_tags.extend(_loads_json_list(signal.conflict_tags))
            total_risk_tags = sorted(set(candidate_risks + signal_risks + conflict_tags))

            strategy_strength = mean([s.score for s in hit_signals]) if hit_signals else 0.0
            avg_market_fit = mean([s.market_fit_score for s in hit_signals]) if hit_signals else 0.0
            resonance_score = _clip(len(hit_signals) * 8.0 + strategy_strength * 0.4 + avg_market_fit * 20.0, 0.0, 100.0)
            quant_score = round(_clip(c.base_score * 0.45 + strategy_strength * 0.35 + resonance_score * 0.2, 0.0, 100.0), 2)

            risk_score_value, risk_notes = _risk_from_tags(total_risk_tags, market_state)
            risk_score = round(risk_score_value, 2)

            if llm_enabled:
                llm_adj = round(_clip((avg_market_fit * 100 - risk_score) * 0.05 + len(hit_signals) * 0.2, -4.0, 4.0), 2)
            else:
                llm_adj = 0.0

            total = round(_clip(quant_score - risk_score + llm_adj, 0.0, 100.0), 2)
            level = _to_level(total)

            sorted_hits = sorted(hit_signals, key=lambda item: item.score, reverse=True)
            hit_keys = [s.strategy_key for s in sorted_hits][:8]
            reasons = [
                f"候选基础分={round(c.base_score, 2)}",
                f"战法命中={len(hit_signals)}",
                f"市场状态={market_state}",
                f"共振分={round(resonance_score, 2)}",
            ]
            counter_arguments = risk_notes[:]
            if not counter_arguments and level in {"C", "D"}:
                counter_arguments.append("信号强度不足")

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
                llm_explanation=(
                    "LLM解释：量价结构与战法共振较强，建议结合风控阈值执行。"
                    if llm_enabled
                    else ""
                ),
                counter_arguments=json.dumps(counter_arguments, ensure_ascii=True),
                risk_tags=json.dumps(total_risk_tags, ensure_ascii=True),
                action_suggestion=self._action_suggestion(level, market_state, risk_score),
                confidence_level=round(_clip(0.25 + quant_score / 130.0 - risk_score / 250.0 + len(hit_signals) * 0.02, 0.05, 0.98), 2),
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
            detail=(
                f"run_id={run.id}; strategy_run_id={strategy_run.id}; "
                f"market_state={market_state}; llm_enabled={llm_enabled}; items={len(rows)}"
            ),
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
