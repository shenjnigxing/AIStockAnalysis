import json
from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestEquityCurve, BacktestJob, BacktestReport, BacktestTrade, DailyBar
from app.services.audit import write_audit


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
        if bars:
            return bars

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
        name = payload.get("name", f"backtest-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        job = BacktestJob(name=name, job_type=payload.get("type", "strategy"), params_json=json.dumps(payload, ensure_ascii=True))
        self.db.add(job)
        self.db.flush()

        symbol = str(payload.get("symbol", "000001"))
        start_date = payload.get("start_date")
        end_date = payload.get("end_date")
        bars = self._load_bars(symbol=symbol, start_date=start_date, end_date=end_date)

        init_cash = float(payload.get("initial_cash", 1_000_000))
        commission_rate = float(payload.get("commission", 0.0003))
        stamp_tax_rate = float(payload.get("stamp_tax", 0.001))
        slippage_rate = float(payload.get("slippage", 0.0008))
        position_limit = _clip(float(payload.get("position_limit", 0.3)), 0.05, 1.0)
        stop_loss = _clip(float(payload.get("stop_loss", 0.06)), 0.01, 0.5)
        take_profit = _clip(float(payload.get("take_profit", 0.14)), 0.01, 1.0)

        cash = init_cash
        quantity = 0
        avg_price = 0.0
        holding_days = 0
        turnover_amount = 0.0
        fee_total = 0.0
        win_trades = 0
        loss_trades = 0
        trade_profits: list[float] = []
        equity_curve: list[float] = []
        benchmark_curve: list[float] = []
        total_trade_days = max(1, len(bars))

        closes = [bar.close for bar in bars]
        for idx, bar in enumerate(bars):
            current_close = float(bar.close)
            benchmark_curve.append(current_close)
            ma5 = mean(closes[max(0, idx - 4): idx + 1])
            ma20 = mean(closes[max(0, idx - 19): idx + 1])
            momentum = ((current_close - closes[max(0, idx - 5)]) / max(closes[max(0, idx - 5)], 1e-6)) if idx >= 5 else 0.0

            signal_buy = quantity == 0 and idx >= 20 and current_close > ma5 > ma20 and momentum > 0.01
            stop_by_loss = quantity > 0 and current_close <= avg_price * (1 - stop_loss)
            stop_by_gain = quantity > 0 and current_close >= avg_price * (1 + take_profit)
            trend_break = quantity > 0 and current_close < ma20
            signal_sell = stop_by_loss or stop_by_gain or trend_break

            if signal_buy:
                order_cash = (cash + quantity * current_close) * position_limit
                exec_price = current_close * (1 + slippage_rate)
                buy_qty = int(order_cash / max(exec_price, 1e-6) // 100 * 100)
                if buy_qty > 0:
                    gross = buy_qty * exec_price
                    commission = max(5.0, gross * commission_rate)
                    total_cost = gross + commission
                    if total_cost <= cash:
                        cash -= total_cost
                        quantity += buy_qty
                        avg_price = exec_price
                        turnover_amount += gross
                        fee_total += commission
                        self.db.add(
                            BacktestTrade(
                                job_id=job.id,
                                symbol=symbol,
                                side="buy",
                                price=round(exec_price, 4),
                                quantity=buy_qty,
                                trade_time=datetime.combine(bar.trade_date, datetime.min.time()),
                            )
                        )

            elif signal_sell and quantity > 0:
                exec_price = current_close * (1 - slippage_rate)
                gross = quantity * exec_price
                commission = max(5.0, gross * commission_rate)
                stamp = gross * stamp_tax_rate
                net = gross - commission - stamp
                pnl = net - quantity * avg_price
                cash += net
                turnover_amount += gross
                fee_total += commission + stamp
                if pnl >= 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                trade_profits.append(pnl)
                self.db.add(
                    BacktestTrade(
                        job_id=job.id,
                        symbol=symbol,
                        side="sell",
                        price=round(exec_price, 4),
                        quantity=quantity,
                        trade_time=datetime.combine(bar.trade_date, datetime.min.time()),
                    )
                )
                quantity = 0
                avg_price = 0.0
                holding_days = 0

            if quantity > 0:
                holding_days += 1
            equity = cash + quantity * current_close
            equity_curve.append(round(equity, 2))
            self.db.add(
                BacktestEquityCurve(
                    job_id=job.id,
                    point_time=datetime.combine(bar.trade_date, datetime.min.time()),
                    equity=round(equity, 2),
                )
            )

        if quantity > 0:
            final_close = float(bars[-1].close)
            exec_price = final_close * (1 - slippage_rate)
            gross = quantity * exec_price
            commission = max(5.0, gross * commission_rate)
            stamp = gross * stamp_tax_rate
            net = gross - commission - stamp
            pnl = net - quantity * avg_price
            cash += net
            turnover_amount += gross
            fee_total += commission + stamp
            if pnl >= 0:
                win_trades += 1
            else:
                loss_trades += 1
            trade_profits.append(pnl)
            self.db.add(
                BacktestTrade(
                    job_id=job.id,
                    symbol=symbol,
                    side="sell",
                    price=round(exec_price, 4),
                    quantity=quantity,
                    trade_time=datetime.combine(bars[-1].trade_date, datetime.min.time()),
                )
            )
            quantity = 0

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
        sharpe = annual_return / max(volatility, 1e-6)
        sortino = annual_return / max(downside_vol, 1e-6)
        calmar = annual_return / max(max_dd, 1e-6)
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
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "calmar": round(calmar, 4),
            "win_rate": round(win_rate, 4),
            "pnl_ratio": round(pnl_ratio, 4),
            "turnover": round(turnover_amount / max(init_cash, 1e-6), 4),
            "avg_holding_days": round((holding_days / max(total_trades, 1)), 2),
            "total_trades": total_trades,
            "slippage_impact": round(slippage_rate, 4),
            "cost_impact": round(fee_total / max(init_cash, 1e-6), 4),
            "capacity_hint": "low" if turnover_amount < init_cash * 1.2 else "medium" if turnover_amount < init_cash * 3.0 else "high",
        }
        report = BacktestReport(job_id=job.id, metrics_json=json.dumps(metrics, ensure_ascii=True))
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
        return list(self.db.scalars(select(BacktestJob).order_by(BacktestJob.created_at.desc())).all())

    def report(self, job_id: int) -> BacktestReport | None:
        return self.db.scalar(select(BacktestReport).where(BacktestReport.job_id == job_id))

    def trades(self, job_id: int) -> list[BacktestTrade]:
        return list(self.db.scalars(select(BacktestTrade).where(BacktestTrade.job_id == job_id)).all())

    def equity(self, job_id: int) -> list[BacktestEquityCurve]:
        return list(self.db.scalars(select(BacktestEquityCurve).where(BacktestEquityCurve.job_id == job_id)).all())
