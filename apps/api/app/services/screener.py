import json
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import RealtimeQuote, ScreenerCandidate, ScreenerPreset, ScreenerRun


class ScreenerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, filters: dict, mode: str = "intraday") -> ScreenerRun:
        run = ScreenerRun(mode=mode, status="completed", filters_json=json.dumps(filters, ensure_ascii=True))
        self.db.add(run)
        self.db.flush()

        quotes = self.db.scalars(select(RealtimeQuote).order_by(desc(RealtimeQuote.quote_time)).limit(200)).all()
        latest_by_symbol: dict[str, RealtimeQuote] = {}
        for q in quotes:
            if q.symbol not in latest_by_symbol:
                latest_by_symbol[q.symbol] = q

        ranked = sorted(
            latest_by_symbol.values(),
            key=lambda x: (x.change_pct, x.amount),
            reverse=True,
        )

        min_change = float(filters.get("min_change_pct", -100))
        max_change = float(filters.get("max_change_pct", 100))
        top_n = int(filters.get("top_n", 100))
        candidates = [q for q in ranked if min_change <= q.change_pct <= max_change][:top_n]

        for idx, item in enumerate(candidates, start=1):
            base_score = round(item.change_pct * 10 + min(item.amount / 1000000, 40), 2)
            self.db.add(
                ScreenerCandidate(
                    screener_run_id=run.id,
                    symbol=item.symbol,
                    base_score=base_score,
                    rank_no=idx,
                    filter_snapshot=json.dumps(filters, ensure_ascii=True),
                    tags=json.dumps(["momentum"] if item.change_pct > 2 else ["watch"], ensure_ascii=True),
                    risk_hints=json.dumps(["high_volatility"] if item.change_pct > 8 else [], ensure_ascii=True),
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

