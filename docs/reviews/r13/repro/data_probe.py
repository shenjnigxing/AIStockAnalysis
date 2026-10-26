# Review reproduction only: fixtures, no market claims or external network.
import os
if os.environ.get("DATABASE_URL") != "sqlite:///:memory:":
    raise SystemExit("Set DATABASE_URL=sqlite:///:memory: to protect stored data")
import os,sys,json
from datetime import date,timedelta,datetime
from types import SimpleNamespace
from unittest.mock import patch
class Frame:
 def __init__(self,rows):self.rows=rows
 empty=False
 def __len__(self):return len(self.rows)
 def iterrows(self):return iter(enumerate(self.rows))
from sqlalchemy import select
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.models import DailyBar,SyncCheckpoint
from app.services.public_quote_sources import fetch_public_quote,SOURCES
from app.services.public_quote_cache import refresh_quote
from app.services.data_sync import DataSyncService
os.environ['MARKET_DATA_MODE']='real'
init_db()
# All public responses below are fixtures, never a live-network success.
sge=Frame([{'品种':'Ag99.99','时间':'14:00','现价':8500,'更新时间':'2026-10-20 14:00:00'}])
with patch.dict(sys.modules,{'akshare':SimpleNamespace(spot_quotations_sge=lambda **kw:sge)}):
 result=fetch_public_quote('sge_gold','Ag99.99')
 print('DATA-01',{'value':result['value'],'declared_unit':SOURCES['sge_gold']['unit']})
future=Frame([{'symbol':'螺纹钢2612','current_price':3333,'time':'140000'}])
with patch.dict(sys.modules,{'akshare':SimpleNamespace(futures_zh_spot=lambda **kw:future)}):
 result=fetch_public_quote('futures','AU2612')
 with SessionLocal() as db:
  with patch('app.services.public_quote_cache.fetch_supervised',return_value=result):
   stored=refresh_quote(db,kind='futures',symbol='AU2612')
   print('DATA-02',{'requested':'AU2612','stored_symbol':stored['quote']['symbol'],'value':stored['quote']['value'],'raw_symbol':result['source_record']['symbol']})
with SessionLocal() as db:
 service=DataSyncService(db)
 requested_end=date(2026,10,20); returned_day=requested_end-timedelta(days=1)
 service.adapter.fetch_daily_bars=lambda **kw:[{'symbol':'600000','trade_date':returned_day,'open':10,'high':11,'low':9,'close':10,'volume':100,'amount':1000}]
 job=service.sync_daily(['600000'],requested_end-timedelta(days=3),requested_end)
 checkpoint=db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.scope_key=='600000'))
 row=db.scalar(select(DailyBar).where(DailyBar.symbol=='600000'))
 print('DATA-03',{'job':job.status,'last_actual_day':str(row.trade_date),'checkpoint':checkpoint.checkpoint_value,'next_default_start':str(date.fromisoformat(checkpoint.checkpoint_value)+timedelta(days=1))})
 # date outside requested interval remains accepted.
 service.adapter.fetch_daily_bars=lambda **kw:[{'symbol':'600001','trade_date':date(2099,1,1),'open':10,'high':11,'low':9,'close':10,'volume':100,'amount':1000}]
 job=service.sync_daily(['600001'],date(2026,10,1),date(2026,10,20))
 row=db.scalar(select(DailyBar).where(DailyBar.symbol=='600001'))
 print('DATA-04',{'job':job.status,'persisted_future_date':str(row.trade_date)})
