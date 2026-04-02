# Schema Overview

核心表分组：
- 行情与同步：`stock_master`, `daily_bars`, `minute_bars`, `realtime_quotes`, `sync_jobs`, `sync_checkpoints`
- 策略推荐：`strategy_definitions`, `strategy_runs`, `strategy_signals`, `recommendation_runs`, `recommendations`
- 交易回测：`backtest_jobs`, `backtest_reports`, `backtest_trades`, `backtest_equity_curves`
- 仿真实盘：`paper_*`, `live_*`, `order_previews`
- 风控运营：`risk_configs`, `risk_events`, `kill_switch_status`, `notifications`, `replay_records`, `audit_logs`
