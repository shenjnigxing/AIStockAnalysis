from __future__ import annotations

import argparse
import io
import sqlite3
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime

import baostock as bs
import pandas as pd


def bs_login_silent():
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs.login()


def bs_logout_silent():
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs.logout()


def is_limit_up(code: str, change_pct: float) -> bool:
    code = str(code)
    cp = float(change_pct or 0)
    if code.startswith(("300", "301", "688")):
        return cp >= 19.5
    return cp >= 9.5


def plain_to_bs(code: str) -> str:
    code = str(code).strip().replace('sh.', '').replace('sz.', '').replace('sh', '').replace('sz', '')
    return f"sh.{code}" if code.startswith('6') else f"sz.{code}"


def fetch_kline_rows(bs_code: str, start_date: str, end_date: str):
    fields = "date,code,open,high,low,close,volume,amount,turn,pctChg,peTTM,pbMRQ"
    rs = bs.query_history_k_data_plus(
        code=bs_code,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != '0':
        raise RuntimeError(f"kline query failed for {bs_code}: {rs.error_msg}")
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return []
    df = pd.DataFrame(rows, columns=rs.fields)
    for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg', 'peTTM', 'pbMRQ']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.rename(columns={'turn': 'turnover_rate', 'pctChg': 'change_pct', 'peTTM': 'pe_ttm', 'pbMRQ': 'pb_mrq'})
    df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1) * 100).round(2)
    plain = bs_code.split('.')[-1]
    out = []
    for _, row in df.iterrows():
        out.append((
            plain,
            row.get('date'),
            None if pd.isna(row.get('open')) else float(row.get('open')),
            None if pd.isna(row.get('high')) else float(row.get('high')),
            None if pd.isna(row.get('low')) else float(row.get('low')),
            None if pd.isna(row.get('close')) else float(row.get('close')),
            None if pd.isna(row.get('volume')) else float(row.get('volume')),
            None if pd.isna(row.get('amount')) else float(row.get('amount')),
            None if pd.isna(row.get('change_pct')) else float(row.get('change_pct')),
            None if pd.isna(row.get('amplitude')) else float(row.get('amplitude')),
            None if pd.isna(row.get('turnover_rate')) else float(row.get('turnover_rate')),
            None if pd.isna(row.get('pe_ttm')) else float(row.get('pe_ttm')),
            None if pd.isna(row.get('pb_mrq')) else float(row.get('pb_mrq')),
        ))
    return out


def fetch_basic_payload(bs_code: str):
    rs = bs.query_stock_basic(code=bs_code)
    if rs.error_code != '0' or not rs.data:
        return None
    basic = dict(zip(rs.fields, rs.data[0]))
    industry = None
    try:
        rs_ind = bs.query_stock_industry(code=bs_code)
        if rs_ind.error_code == '0' and rs_ind.data:
            industry = dict(zip(rs_ind.fields, rs_ind.data[0])).get('industry')
    except Exception:
        pass
    plain = bs_code.split('.')[-1]
    market = '主板' if plain.startswith(('60', '00')) else ('创业板' if plain.startswith('30') else ('科创板' if plain.startswith('68') else '主板'))
    return (plain, basic.get('code_name'), basic.get('ipoDate'), None, None, industry, None, market)


def fetch_financial_payload(bs_code: str, year: int, quarter: int):
    rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
    profit = dict(zip(rs_profit.fields, rs_profit.data[0])) if rs_profit.data else None
    if not profit:
        return None
    rs_operation = bs.query_operation_data(code=bs_code, year=year, quarter=quarter)
    operation = dict(zip(rs_operation.fields, rs_operation.data[0])) if rs_operation.data else None
    plain = bs_code.split('.')[-1]
    report_date = profit.get('statDate') or f"{year}-{(quarter-1)*3+1:02d}-01"
    total_share = float(profit.get('totalShare')) if profit.get('totalShare') else None
    liqa_share = float(profit.get('liqaShare')) if profit.get('liqaShare') else None
    return {
        'insert': (
            plain, report_date, profit.get('pubDate'),
            float(profit.get('roeAvg')) if profit.get('roeAvg') else None,
            float(profit.get('roeWeight')) if profit.get('roeWeight') else None,
            float(profit.get('npMargin')) if profit.get('npMargin') else None,
            float(profit.get('gpMargin')) if profit.get('gpMargin') else None,
            float(profit.get('netProfit')) if profit.get('netProfit') else None,
            float(profit.get('epsTTM')) if profit.get('epsTTM') else None,
            float(profit.get('epsDiluted')) if profit.get('epsDiluted') else None,
            float(profit.get('MBRevenue')) if profit.get('MBRevenue') else None,
            total_share, liqa_share,
            float(operation.get('debtToAsset')) if operation and operation.get('debtToAsset') else None,
            float(operation.get('currentRatio')) if operation and operation.get('currentRatio') else None,
            float(operation.get('quickRatio')) if operation and operation.get('quickRatio') else None,
        ),
        'update_basic': (total_share, liqa_share, plain),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db-path', default='data/stock_data.db')
    p.add_argument('--start-date', default='2025-01-01')
    p.add_argument('--end-date', default=datetime.now().strftime('%Y-%m-%d'))
    p.add_argument('--financial-quarters', type=int, default=4)
    args = p.parse_args()

    conn = sqlite3.connect(args.db_path)
    latest = conn.execute("SELECT MAX(date) FROM daily_market").fetchone()[0]
    rows = conn.execute("SELECT code,name,change_pct FROM daily_market WHERE date=? ORDER BY amount DESC", (latest,)).fetchall()
    codes = [str(code) for code, _, cp in rows if is_limit_up(str(code), float(cp or 0))]
    print({'latest': latest, 'limitup_codes': len(codes)})
    lg = bs_login_silent()
    if lg.error_code != '0':
        print(f'baostock login failed: {lg.error_msg}', file=sys.stderr)
        sys.exit(1)
    started = time.time()
    kline_ok = basic_ok = fin_ok = 0
    try:
        cur = conn.cursor()
        for idx, code in enumerate(codes, 1):
            bs_code = plain_to_bs(code)
            try:
                krows = fetch_kline_rows(bs_code, args.start_date, args.end_date)
                if krows:
                    cur.executemany(
                        """
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount, change_pct, amplitude, turnover_rate, pe_ttm, pb_mrq, adjust_flag, frequency)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'bfq', 'daily')
                        """,
                        krows,
                    )
                    kline_ok += 1
            except Exception as e:
                print('kline fail', code, e)
            try:
                basic = fetch_basic_payload(bs_code)
                if basic:
                    cur.execute(
                        "INSERT OR REPLACE INTO stock_basic (code,name,list_date,total_shares,float_shares,industry,area,market) VALUES (?,?,?,?,?,?,?,?)",
                        basic,
                    )
                    basic_ok += 1
            except Exception as e:
                print('basic fail', code, e)
            y = datetime.now().year
            q = (datetime.now().month - 1)//3 + 1
            for _ in range(args.financial_quarters):
                try:
                    payload = fetch_financial_payload(bs_code, y, q)
                    if payload:
                        cur.execute(
                            """
                            INSERT OR REPLACE INTO financial_data
                            (code, report_date, pub_date, roe_avg, roe_weight, net_margin, gross_margin,
                             net_profit, eps_basic, eps_diluted, total_revenue, total_shares, float_shares,
                             debt_ratio, current_ratio, quick_ratio)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            payload['insert'],
                        )
                        cur.execute(
                            "UPDATE stock_basic SET total_shares=COALESCE(?, total_shares), float_shares=COALESCE(?, float_shares), updated_at=CURRENT_TIMESTAMP WHERE code=?",
                            payload['update_basic'],
                        )
                        fin_ok += 1
                except Exception as e:
                    print('fin fail', code, y, q, e)
                q -= 1
                if q <= 0:
                    q = 4
                    y -= 1
            if idx % 10 == 0:
                conn.commit()
                print(f'progress {idx}/{len(codes)} kline_ok={kline_ok} basic_ok={basic_ok} fin_ok={fin_ok} elapsed={time.time()-started:.1f}s')
        conn.commit()
        print({'done_codes': len(codes), 'kline_ok': kline_ok, 'basic_ok': basic_ok, 'fin_ok': fin_ok, 'elapsed_sec': round(time.time()-started,1)})
    finally:
        bs_logout_silent()
        conn.close()


if __name__ == '__main__':
    main()
