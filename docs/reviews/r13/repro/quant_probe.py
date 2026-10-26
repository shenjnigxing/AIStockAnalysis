# Review reproduction only: fixtures, no market claims or external network.
import os
if os.environ.get("DATABASE_URL") != "sqlite:///:memory:":
    raise SystemExit("Set DATABASE_URL=sqlite:///:memory: to protect stored data")
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.base import Base
from app.db.models import DailyBar
from app.services.backtest import BacktestService
from datetime import date,timedelta
import json
init_db()
for name,prices in [('A',[10]*20+[12]),('B',[10]*20+[12,12.04]),('C',[10]*20+[12,12.1,10])]:
 with SessionLocal() as db:
  for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())
  db.commit()
  for i,p in enumerate(prices):
   db.add(DailyBar(symbol='600000',trade_date=date(2026,1,1)+timedelta(days=i),open=10,high=max(13,p),low=9,close=p,volume=1000000,amount=10000000))
  db.commit()
  s=BacktestService(db)
  job=s.run({'symbol':'600000','initial_cash':10000,'commission':0,'stamp_tax':0,'slippage':0,'position_limit':.3})
  trades=s.trades(job.id)
  cash=10000
  for t in trades:
   gross=t.price*t.quantity
   cash += gross-5 if t.side=='sell' else -(gross+5)
  print(name,[(t.side,t.price,t.quantity,str(t.trade_time)) for t in trades],s.equity(job.id)[-1].equity,cash,json.loads(s.report(job.id).metrics_json))
