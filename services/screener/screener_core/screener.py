import json
import math
from datetime import datetime
from statistics import mean

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import DailyBar, RealtimeQuote, ScreenerCandidate, ScreenerPreset, ScreenerRun


def _as_float(value: object, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ScreenerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _recent_daily_bars(self, symbol: str, limit: int = 20) -> list[DailyBar]:
        return list(
            self.db.scalars(
                select(DailyBar).where(DailyBar.symbol == symbol).order_by(desc(DailyBar.trade_date)).limit(limit)
            ).all()
        )

    def _calc_features(self, quote: RealtimeQuote) -> dict[str, float | bool]:
        bars = self._recent_daily_bars(quote.symbol, limit=20)
        if bars:
            avg_daily_amount = mean(max(0.0, b.amount) for b in bars[:10])
            avg_daily_volume = mean(max(0.0, b.volume) for b in bars[:10])
            volatility = mean(
                ((b.high - b.low) / b.close * 100.0) for b in bars[:10] if b.close > 0
            )
            prev_window = [b.close for b in bars[1:6]]
            prev_high = max(prev_window) if prev_window else max(b.close for b in bars)
            breakout = quote.price >= prev_high * 1.01 if prev_high > 0 else False
        else:
            avg_daily_amount = max(quote.amount, 1.0)
            avg_daily_volume = max(quote.volume, 1.0)
            volatility = 3.2
            breakout = quote.change_pct >= 1.5

        volume_ratio = quote.volume / avg_daily_volume if avg_daily_volume > 0 else 1.0
        amount_ratio = quote.amount / avg_daily_amount if avg_daily_amount > 0 else 1.0
        return {
            "volatility": round(volatility, 4),
            "volume_ratio": round(volume_ratio, 4),
            "amount_ratio": round(amount_ratio, 4),
            "breakout": breakout,
        }

    def _score_quote(self, quote: RealtimeQuote, features: dict[str, float | bool]) -> float:
        volatility = float(features["volatility"])
        volume_ratio = float(features["volume_ratio"])
        momentum_score = _clip((quote.change_pct + 3.0) * 12.5, 0.0, 100.0)
        liquidity_score = _clip((math.log10(max(quote.amount, 1.0)) - 4.2) * 43.0, 0.0, 100.0)
        volume_score = _clip((volume_ratio - 0.5) * 55.0, 0.0, 100.0)
        breakout_score = 86.0 if bool(features["breakout"]) else 38.0
        stability_score = _clip(100.0 - abs(volatility - 3.0) * 18.0, 0.0, 100.0)

        return round(
            momentum_score * 0.34
            + liquidity_score * 0.22
            + volume_score * 0.16
            + breakout_score * 0.18
            + stability_score * 0.10,
            2,
        )

    def _build_tags(self, quote: RealtimeQuote, features: dict[str, float | bool]) -> list[str]:
        tags: list[str] = []
        if quote.change_pct >= 1.5:
            tags.append("momentum")
        if float(features["volume_ratio"]) >= 1.4:
            tags.append("volume_expand")
        if bool(features["breakout"]):
            tags.append("breakout")
        if quote.amount >= 20_000_000:
            tags.append("active_fund")
        if float(features["volatility"]) <= 2.0:
            tags.append("low_volatility")
        return tags or ["watch"]

    def _build_risk_hints(self, quote: RealtimeQuote, features: dict[str, float | bool], min_amount: float) -> list[str]:
        risk_hints: list[str] = []
        if quote.change_pct >= 7.5 or float(features["volatility"]) >= 6.5:
            risk_hints.append("high_volatility")
        if quote.amount < max(500_000.0, min_amount * 0.8):
            risk_hints.append("low_liquidity")
        if float(features["volume_ratio"]) < 0.75:
            risk_hints.append("weak_volume_support")
        if float(features["amount_ratio"]) >= 3.0:
            risk_hints.append("turnover_overheat")
        if quote.price <= 0:
            risk_hints.append("invalid_quote")
        return risk_hints

    def run(self, filters: dict, mode: str = "intraday") -> ScreenerRun:
        run = ScreenerRun(mode=mode, status="completed", filters_json=json.dumps(filters, ensure_ascii=True))
        self.db.add(run)
        self.db.flush()

        quotes = self.db.scalars(select(RealtimeQuote).order_by(desc(RealtimeQuote.quote_time)).limit(2000)).all()
        latest_by_symbol: dict[str, RealtimeQuote] = {}
        for q in quotes:
            if q.symbol not in latest_by_symbol:
                latest_by_symbol[q.symbol] = q

        min_change = _as_float(filters.get("min_change_pct"), -100.0)
        max_change = _as_float(filters.get("max_change_pct"), 100.0)
        min_amount = _as_float(filters.get("min_amount"), 0.0)
        min_price = _as_float(filters.get("min_price"), 0.0)
        max_price = _as_float(filters.get("max_price"), 99999.0)
        min_volume_ratio = _as_float(filters.get("min_volume_ratio"), 0.0)
        max_volatility = _as_float(filters.get("max_volatility"), 99.0)
        exclude_symbols = {str(s) for s in filters.get("exclude_symbols", []) if s}
        top_n = _clip(_as_int(filters.get("top_n"), 100), 1, 200)

        ranked: list[tuple[RealtimeQuote, float, list[str], list[str], float]] = []
        for quote in latest_by_symbol.values():
            if quote.symbol in exclude_symbols:
                continue
            features = self._calc_features(quote)
            volatility = float(features["volatility"])
            if not (min_change <= quote.change_pct <= max_change):
                continue
            if not (min_price <= quote.price <= max_price):
                continue
            if quote.amount < min_amount:
                continue
            if float(features["volume_ratio"]) < min_volume_ratio:
                continue
            if volatility > max_volatility:
                continue

            base_score = self._score_quote(quote, features)
            tags = self._build_tags(quote, features)
            risk_hints = self._build_risk_hints(quote, features, min_amount=min_amount)
            ranked.append((quote, base_score, tags, risk_hints, volatility))

        ranked.sort(key=lambda item: (item[1], item[0].amount, item[0].change_pct), reverse=True)
        selected = ranked[: int(top_n)]

        for idx, (quote, base_score, tags, risk_hints, volatility) in enumerate(selected, start=1):
            self.db.add(
                ScreenerCandidate(
                    screener_run_id=run.id,
                    symbol=quote.symbol,
                    base_score=base_score,
                    rank_no=idx,
                    filter_snapshot=json.dumps(filters, ensure_ascii=True),
                    tags=json.dumps(tags, ensure_ascii=True),
                    risk_hints=json.dumps(risk_hints + ([f"volatility_{volatility:.2f}"] if volatility > 0 else []), ensure_ascii=True),
                )
            )
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_presets(self) -> list[ScreenerPreset]:
        return list(self.db.scalars(select(ScreenerPreset).order_by(desc(ScreenerPreset.updated_at))).all())

    def create_preset(self, name: str, params: dict) -> ScreenerPreset:
        preset = self.db.scalar(select(ScreenerPreset).where(ScreenerPreset.name == name))
        if preset is None:
            preset = ScreenerPreset(name=name, params_json=json.dumps(params, ensure_ascii=True))
            self.db.add(preset)
        else:
            preset.params_json = json.dumps(params, ensure_ascii=True)
            preset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(preset)
        return preset

    def update_preset(self, preset_id: int, params: dict) -> ScreenerPreset | None:
        preset = self.db.get(ScreenerPreset, preset_id)
        if preset is None:
            return None
        preset.params_json = json.dumps(params, ensure_ascii=True)
        preset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(preset)
        return preset

    def latest_candidates(self) -> list[ScreenerCandidate]:
        run = self.db.scalar(select(ScreenerRun).order_by(desc(ScreenerRun.created_at)))
        if run is None:
            return []
        stmt = select(ScreenerCandidate).where(ScreenerCandidate.screener_run_id == run.id).order_by(ScreenerCandidate.rank_no)
        return list(self.db.scalars(stmt).all())

    def top100(self) -> list[ScreenerCandidate]:
        return self.latest_candidates()[:100]
