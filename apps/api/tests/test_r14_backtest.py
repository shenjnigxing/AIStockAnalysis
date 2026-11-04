"""Actual backtest accounting and execution regression; artificial memory-only bars."""
from datetime import date, timedelta
import json
import math
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db.models import BacktestJob, DailyBar
from app.db.session import SessionLocal
from app.services.backtest import BacktestService, BacktestParameters

client = TestClient(app)


def run_prices(monkeypatch, closes, opens=None, **overrides):
    monkeypatch.setenv('MARKET_DATA_MODE', 'mock')
    with SessionLocal() as db:
        for i, close in enumerate(closes):
            opened = opens[i] if opens else close
            db.add(DailyBar(symbol='600000',trade_date=date(2026,1,1)+timedelta(days=i),
                open=opened,high=max(opened,close)+1,low=min(opened,close)-1,close=close,volume=1e6,amount=1e7))
        db.commit()
        service=BacktestService(db)
        job=service.run({'symbol':'600000','initial_cash':10000,'position_limit':.3,
            'commission':0,'stamp_tax':0,'slippage':0,**overrides})
        metrics=json.loads(service.report(job.id).metrics_json)
        trades=[(t.side,t.price,t.quantity,t.trade_time) for t in service.trades(job.id)]
        equity=[e.equity for e in service.equity(job.id)]
    return metrics,trades,equity


def test_final_cash_curve_return_and_full_round_trip_cost_agree(monkeypatch):
    prices=[10]*20+[12,12.04,12.04]
    opens=[10]*20+[12,12,12.04]
    m,trades,curve=run_prices(monkeypatch,prices,opens)
    cash=10000
    for side,price,qty,_ in trades:
        gross=price*qty
        cash+=gross-5 if side=='sell' else -(gross+5)
    assert cash == pytest.approx(9998)
    assert curve[-1] == m['final_cash'] == pytest.approx(cash)
    assert m['total_return'] == pytest.approx(round((cash-10000)/10000,4))
    assert m['win_rate'] == 0  # gross profit 8, two commissions 10
    assert m['avg_holding_days'] == 1
    assert m['cost_impact'] == .001
    assert m['sortino'] is None
    assert m['sortino_status'] == 'insufficient_downside_observations'


@pytest.mark.parametrize('prices',[[10]*20+[12],[10]*20+[12,12.04]])
def test_no_last_bar_entry_or_same_bar_signal_fill(monkeypatch,prices):
    m,trades,curve=run_prices(monkeypatch,prices)
    assert trades == []
    assert curve[-1] == 10000
    assert m['total_trades'] == 0


def test_signal_executes_next_open_and_exit_holding_period_survives_reset(monkeypatch):
    prices=[10]*20+[12,12,9,9,9]
    opens=[10]*20+[12,12.5,12,9.5,9]
    m,trades,curve=run_prices(monkeypatch,prices,opens,stop_loss=.2)
    assert trades[0][0:2] == ('buy',12.5)
    assert trades[0][3].date() == date(2026,1,22) # signal Jan21, trade Jan22
    assert trades[1][0:2] == ('sell',9.5) # loss at Jan23 close, exit Jan24 open
    assert m['avg_holding_days'] == 2
    assert m['win_rate'] == 0


@pytest.mark.parametrize('key,value',[
    ('commission',-.01),('commission',.5),('slippage',-.5),('stamp_tax',-.5),
    ('initial_cash',0),('position_limit',2),('stop_loss',0),('take_profit',-1),
    ('slippage','NaN'),('initial_cash','Infinity'),('end_date','invalid'),
])
def test_invalid_costs_and_parameters_return_422_before_any_job(key,value):
    response=client.post('/api/backtest/run',json={'symbol':'600000',key:value})
    assert response.status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(BacktestJob.id)) is None


def test_service_call_cannot_bypass_typed_cost_validation(monkeypatch):
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            BacktestService(db).run({'slippage':-.5})
        assert db.scalar(select(BacktestJob.id)) is None
    with pytest.raises(ValueError):
        BacktestParameters(start_date='2026-02-01',end_date='2026-01-01')


def test_unverified_real_data_cannot_use_backtest_routes(monkeypatch):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    for path in ['/api/backtest/jobs','/api/backtest/report/1','/api/backtest/report/1/detail',
                 '/api/backtest/trades/1','/api/backtest/equity/1']:
        assert client.get(path).status_code == 409
    assert client.post('/api/backtest/run',json={}).status_code == 409
