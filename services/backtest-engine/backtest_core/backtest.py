import json
import os
import math
from datetime import date, datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field, model_validator
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestEquityCurve, BacktestJob, BacktestReport, BacktestTrade, DailyBar
from app.services.audit import write_audit
from app.services.research_gate import require_legacy_research_eligibility, research_contract


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return variance ** 0.5


def _max_drawdown(equity: list[float]) -> float:
    peak = 0.0
    mdd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            mdd = max(mdd, (peak - value) / peak)
    return mdd


class BacktestParameters(BaseModel):
    """Shared HTTP/service contract; reject instead of clipping invalid finance inputs."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: str = Field(default="strategy", min_length=1, max_length=40)
    symbol: str = Field(default="000001", min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_.-]+$")
    start_date: date | None = None
    end_date: date | None = None
    initial_cash: float = Field(default=1_000_000, gt=0, le=1e12, allow_inf_nan=False)
    commission: float = Field(default=.0003, ge=0, le=.05, allow_inf_nan=False)
    stamp_tax: float = Field(default=.001, ge=0, le=.05, allow_inf_nan=False)
    slippage: float = Field(default=.0008, ge=0, le=.1, allow_inf_nan=False)
    position_limit: float = Field(default=.3, gt=0, le=1, allow_inf_nan=False)
    stop_loss: float = Field(default=.06, gt=0, le=.5, allow_inf_nan=False)
    take_profit: float = Field(default=.14, gt=0, le=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be later than end_date")
        if (self.start_date and self.start_date > date.today()) or (self.end_date and self.end_date > date.today()):
            raise ValueError("Future backtest dates are not allowed")
        return self


class BacktestDataUnavailableError(ValueError):
    """No sufficient stored observations; never fabricate a real-mode report."""


class BacktestService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_bars(self, symbol: str, start_date: str | None, end_date: str | None, fallback_days: int = 90) -> list[DailyBar]:
        stmt = select(DailyBar).where(DailyBar.symbol == symbol)
        if start_date:
            stmt = stmt.where(DailyBar.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(DailyBar.trade_date <= end_date)
        bars = list(self.db.scalars(stmt.order_by(DailyBar.trade_date)).all())
        demo_allowed = (os.getenv("MARKET_DATA_MODE", "real").strip().lower() == "mock"
                        and os.getenv("APP_ENV", "dev").strip().lower() != "production")
        if bars:
            if not demo_allowed and len(bars) < 21:
                raise BacktestDataUnavailableError("At least 21 stored daily bars are required")
            return bars
        if not demo_allowed:
            raise BacktestDataUnavailableError("No stored daily bars; real backtests never synthesize prices")

        seed_price = 10.0 + (sum(ord(ch) for ch in symbol) % 400) / 100.0
        now = datetime.utcnow()
        mock: list[DailyBar] = []
        price = seed_price
        for i in range(fallback_days):
            drift = 0.0015 * ((i % 13) - 6) + 0.0008 * ((i % 5) - 2)
            price = max(2.0, price * (1 + drift))
            high = price * (1 + 0.014 + (i % 4) * 0.002)
            low = price * (1 - 0.012 - (i % 3) * 0.0015)
            open_price = (high + low) / 2
            volume = 2_000_000 + i * 3_000
            amount = volume * price
            mock.append(
                DailyBar(
                    symbol=symbol,
                    trade_date=(now - timedelta(days=fallback_days - i)).date(),
                    open=round(open_price, 4),
                    high=round(high, 4),
                    low=round(low, 4),
                    close=round(price, 4),
                    volume=volume,
                    amount=round(amount, 2),
                )
            )
        return mock

    def run(self, payload: dict) -> BacktestJob:
        require_legacy_research_eligibility()
        params = BacktestParameters.model_validate(payload)
        payload = params.model_dump(mode="json")
        name = params.name or f"backtest-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        symbol = params.symbol
        bars = self._load_bars(symbol, payload["start_date"], payload["end_date"])
        if any(not math.isfinite(float(v)) or round(float(v), 4) <= 0 for bar in bars for v in (bar.open, bar.close)):
            raise BacktestDataUnavailableError("Open/close prices must be finite and positive")
        job = BacktestJob(name=name, job_type=params.type, params_json=json.dumps(payload, ensure_ascii=True))
        self.db.add(job)
        self.db.flush()
        init_cash = params.initial_cash
        commission_rate, stamp_tax_rate, slippage_rate = params.commission, params.stamp_tax, params.slippage
        position_limit, stop_loss, take_profit = params.position_limit, params.stop_loss, params.take_profit
        cash, quantity, avg_price = init_cash, 0, 0.0
        entry_cost, entry_idx = 0.0, None
        turnover_amount, fee_total = 0.0, 0.0
        win_trades, loss_trades = 0, 0
        trade_profits, holding_periods = [], []
        equity_curve, benchmark_curve = [], []
        total_trade_days = max(1, len(bars))
        closes = [float(bar.close) for bar in bars]
        pending = None

        def sell(price: float, idx: int, at: datetime):
            nonlocal cash, quantity, avg_price, entry_cost, turnover_amount, fee_total, win_trades, loss_trades, entry_idx
            exec_price = round(price * (1 - slippage_rate), 4)
            gross = quantity * exec_price
            commission = max(5.0, gross * commission_rate)
            stamp = gross * stamp_tax_rate
            net = gross - commission - stamp
            # Entry cost includes the original buy commission.
            pnl = net - entry_cost
            cash += net
            turnover_amount += gross
            fee_total += commission + stamp
            win_trades += int(pnl >= 0)
            loss_trades += int(pnl < 0)
            trade_profits.append(pnl)
            holding_periods.append(idx - entry_idx if entry_idx is not None else 0)
            self.db.add(BacktestTrade(job_id=job.id, symbol=symbol, side="sell", price=exec_price,
                                      quantity=quantity, trade_time=at))
            quantity, avg_price, entry_cost, entry_idx = 0, 0.0, 0.0, None

        for idx, bar in enumerate(bars):
            current_close = float(bar.close)
            benchmark_curve.append(current_close)
            # Only yesterday's complete signal may trade at today's open.
            if pending == "sell" and quantity:
                sell(float(bar.open), idx, datetime.combine(bar.trade_date, datetime.min.time()).replace(hour=9, minute=30))
            elif pending == "buy" and not quantity and idx < len(bars) - 1:
                exec_price = round(float(bar.open) * (1 + slippage_rate), 4)
                order_cash = cash * position_limit
                buy_qty = int(order_cash / exec_price // 100 * 100)
                while buy_qty > 0:
                    gross = buy_qty * exec_price
                    commission = max(5.0, gross * commission_rate)
                    if gross + commission <= cash:
                        break
                    buy_qty -= 100
                if buy_qty > 0:
                    entry_cost = gross + commission
                    cash -= entry_cost
                    quantity, avg_price, entry_idx = buy_qty, exec_price, idx
                    turnover_amount += gross
                    fee_total += commission
                    self.db.add(BacktestTrade(job_id=job.id, symbol=symbol, side="buy", price=exec_price,
                        quantity=buy_qty, trade_time=datetime.combine(bar.trade_date, datetime.min.time()).replace(hour=9, minute=30)))
            pending = None
            # Forced liquidation is performed BEFORE persisting final equity.
            if idx == len(bars) - 1 and quantity:
                sell(current_close, idx, datetime.combine(bar.trade_date, datetime.min.time()).replace(hour=15))
            equity = cash + quantity * current_close
            equity_curve.append(round(equity, 2))
            self.db.add(BacktestEquityCurve(job_id=job.id,
                point_time=datetime.combine(bar.trade_date, datetime.min.time()).replace(hour=15), equity=round(equity, 2)))
            if idx < len(bars) - 1:
                ma5 = mean(closes[max(0, idx - 4):idx + 1])
                ma20 = mean(closes[max(0, idx - 19):idx + 1])
                momentum = current_close / closes[max(0, idx - 5)] - 1 if idx >= 5 else 0.0
                if quantity and (current_close <= avg_price * (1-stop_loss) or current_close >= avg_price * (1+take_profit) or current_close < ma20):
                    pending = "sell"
                elif not quantity and idx >= 20 and current_close > ma5 > ma20 and momentum > .01:
                    pending = "buy"

        total_return = (equity_curve[-1] - init_cash) / max(init_cash, 1e-6) if equity_curve else 0.0
        benchmark_return = (
            (benchmark_curve[-1] - benchmark_curve[0]) / max(benchmark_curve[0], 1e-6)
            if len(benchmark_curve) >= 2
            else 0.0
        )
        daily_returns = [
            (equity_curve[idx] - equity_curve[idx - 1]) / max(equity_curve[idx - 1], 1e-6)
            for idx in range(1, len(equity_curve))
        ]
        downside_returns = [value for value in daily_returns if value < 0]
        volatility = _std(daily_returns) * (252 ** 0.5)
        downside_vol = _std(downside_returns) * (252 ** 0.5) if downside_returns else 0.0
        annual_return = (1 + total_return) ** (252 / max(total_trade_days, 1)) - 1 if total_trade_days > 0 else 0.0
        max_dd = _max_drawdown(equity_curve)
        sharpe = annual_return / volatility if len(daily_returns) >= 2 and volatility > 1e-12 else None
        sortino = annual_return / downside_vol if len(downside_returns) >= 2 and downside_vol > 1e-12 else None
        calmar = annual_return / max_dd if max_dd > 1e-12 else None
        total_trades = win_trades + loss_trades
        win_rate = (win_trades / total_trades) if total_trades else 0.0
        avg_profit = mean([value for value in trade_profits if value > 0]) if any(value > 0 for value in trade_profits) else 0.0
        avg_loss = abs(mean([value for value in trade_profits if value < 0])) if any(value < 0 for value in trade_profits) else 0.0
        pnl_ratio = (avg_profit / max(avg_loss, 1e-6)) if avg_profit and avg_loss else (1.0 if avg_profit else 0.0)

        metrics = {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "benchmark_return": round(benchmark_return, 4),
            "excess_return": round(total_return - benchmark_return, 4),
            "max_drawdown": round(max_dd, 4),
            "volatility": round(volatility, 4),
            "downside_volatility": round(downside_vol, 4),
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
            "sortino": round(sortino, 4) if sortino is not None else None,
            "sortino_status": "available" if sortino is not None else "insufficient_downside_observations",
            "execution_model": "previous_close_signal_next_open_v1",
            "final_cash": round(cash, 2),
            "calmar": round(calmar, 4) if calmar is not None else None,
            "win_rate": round(win_rate, 4),
            "pnl_ratio": round(pnl_ratio, 4),
            "turnover": round(turnover_amount / max(init_cash, 1e-6), 4),
            "avg_holding_days": round(mean(holding_periods), 2) if holding_periods else 0.0,
            "total_trades": total_trades,
            "slippage_impact": round(slippage_rate, 4),
            "cost_impact": round(fee_total / max(init_cash, 1e-6), 4),
            "capacity_hint": "low" if turnover_amount < init_cash * 1.2 else "medium" if turnover_amount < init_cash * 3.0 else "high",
        }
        metrics.update(research_contract())
        report = BacktestReport(job_id=job.id, metrics_json=json.dumps(metrics, ensure_ascii=True, allow_nan=False))
        self.db.add(report)
        write_audit(
            self.db,
            action="backtest.run",
            detail=f"job_id={job.id}; name={name}; symbol={symbol}; total_return={metrics['total_return']}",
        )
        self.db.commit()
        self.db.refresh(job)
        return job

    def jobs(self) -> list[BacktestJob]:
        require_legacy_research_eligibility()
        return list(self.db.scalars(select(BacktestJob).order_by(BacktestJob.created_at.desc())).all())

    def report(self, job_id: int) -> BacktestReport | None:
        require_legacy_research_eligibility()
        return self.db.scalar(select(BacktestReport).where(BacktestReport.job_id == job_id))

    def trades(self, job_id: int) -> list[BacktestTrade]:
        require_legacy_research_eligibility()
        return list(self.db.scalars(select(BacktestTrade).where(BacktestTrade.job_id == job_id)).all())

    def equity(self, job_id: int) -> list[BacktestEquityCurve]:
        require_legacy_research_eligibility()
        return list(self.db.scalars(select(BacktestEquityCurve).where(BacktestEquityCurve.job_id == job_id)).all())

    def report_detail(self, job_id: int) -> dict | None:
        require_legacy_research_eligibility()
        report = self.report(job_id)
        if report is None:
            return None
        metrics = json.loads(report.metrics_json)
        trades = self.trades(job_id)
        equities = sorted(self.equity(job_id), key=lambda item: item.point_time)
        if len(equities) < 2:
            return {
                "metrics": metrics,
                "granularity": {"daily_returns": [], "rolling_drawdown": [], "trade_distribution": {}},
            }

        values = [float(item.equity) for item in equities]
        daily_returns = [
            {
                "point_time": equities[idx].point_time.isoformat(),
                "return": round((values[idx] - values[idx - 1]) / max(values[idx - 1], 1e-6), 6),
            }
            for idx in range(1, len(values))
        ]
        rolling_drawdown: list[dict] = []
        peak = values[0]
        for idx, value in enumerate(values):
            peak = max(peak, value)
            dd = (peak - value) / max(peak, 1e-6)
            rolling_drawdown.append(
                {
                    "point_time": equities[idx].point_time.isoformat(),
                    "drawdown": round(dd, 6),
                }
            )
        buy_count = len([t for t in trades if t.side == "buy"])
        sell_count = len([t for t in trades if t.side == "sell"])
        avg_trade_notional = round(
            mean([float(t.price) * int(t.quantity) for t in trades]) if trades else 0.0,
            2,
        )
        return {
            "metrics": metrics,
            "granularity": {
                "daily_returns": daily_returns,
                "rolling_drawdown": rolling_drawdown,
                "trade_distribution": {
                    "buy_count": buy_count,
                    "sell_count": sell_count,
                    "avg_trade_notional": avg_trade_notional,
                },
            },
        }
