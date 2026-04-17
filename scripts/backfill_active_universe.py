from __future__ import annotations

import argparse
import io
import sqlite3
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime

import baostock as bs
import pandas as pd


@dataclass
class Config:
    db_path: str
    kline_limit: int
    basic_limit: int
    financial_quarters: int
    start_date: str
    end_date: str


def bs_login_silent():
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs.login()


def bs_logout_silent():
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs.logout()


def plain_to_bs(code: str) -> str:
    code = str(code).strip().replace('sh.', '').replace('sz.', '').replace('sh', '').replace('sz', '')
    return f"sh.{code}" if code.startswith('6') else f"sz.{code}"


def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS kline_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            change_pct REAL,
            amplitude REAL,
            turnover_rate REAL,
            pe_ttm REAL,
            pb_mrq REAL,
            adjust_flag TEXT DEFAULT 'bfq',
            frequency TEXT DEFAULT 'daily',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, date, frequency, adjust_flag)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_basic (
            code TEXT PRIMARY KEY,
            name TEXT,
            list_date TEXT,
            total_shares REAL,
            float_shares REAL,
            industry TEXT,
            area TEXT,
            market TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            report_date TEXT NOT NULL,
            pub_date TEXT,
            roe_avg REAL,
            roe_weight REAL,
            net_margin REAL,
            gross_margin REAL,
            net_profit REAL,
            eps_basic REAL,
            eps_diluted REAL,
            total_revenue REAL,
            total_shares REAL,
            float_shares REAL,
            debt_ratio REAL,
            current_ratio REAL,
            quick_ratio REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, report_date)
        )
        """
    )
    conn.commit()


def query_top_codes(conn: sqlite3.Connection, limit: int) -> list[str]:
    latest = conn.execute("SELECT MAX(date) FROM daily_market").fetchone()[0]
    rows = conn.execute(
        """
        SELECT code
        FROM daily_market
        WHERE date = ?
        ORDER BY amount DESC, change_pct DESC, code ASC
        LIMIT ?
        """,
        (latest, limit),
    ).fetchall()
    return [str(r[0]) for r in rows]


def get_coverage(conn: sqlite3.Connection) -> dict:
    latest_total = conn.execute("SELECT COUNT(DISTINCT code) FROM daily_market WHERE date=(SELECT MAX(date) FROM daily_market)").fetchone()[0]
    kline_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM kline_data WHERE frequency='daily' AND adjust_flag='bfq'").fetchone()[0]
    basic_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_basic").fetchone()[0]
    fin_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM financial_data").fetchone()[0]
    return {
        'latest_total': int(latest_total or 0),
        'kline_codes': int(kline_codes or 0),
        'basic_codes': int(basic_codes or 0),
        'financial_codes': int(fin_codes or 0),
    }


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
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    if not data:
        return []
    df = pd.DataFrame(data, columns=rs.fields)
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
        industry = None
    plain = bs_code.split('.')[-1]
    market = '主板' if plain.startswith(('60', '00')) else ('创业板' if plain.startswith('30') else ('科创板' if plain.startswith('68') else '主板'))
    return (
        plain,
        basic.get('code_name'),
        basic.get('ipoDate'),
        None,
        None,
        industry,
        None,
        market,
    )


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
            plain,
            report_date,
            profit.get('pubDate'),
            float(profit.get('roeAvg')) if profit.get('roeAvg') else None,
            float(profit.get('roeWeight')) if profit.get('roeWeight') else None,
            float(profit.get('npMargin')) if profit.get('npMargin') else None,
            float(profit.get('gpMargin')) if profit.get('gpMargin') else None,
            float(profit.get('netProfit')) if profit.get('netProfit') else None,
            float(profit.get('epsTTM')) if profit.get('epsTTM') else None,
            float(profit.get('epsDiluted')) if profit.get('epsDiluted') else None,
            float(profit.get('MBRevenue')) if profit.get('MBRevenue') else None,
            total_share,
            liqa_share,
            float(operation.get('debtToAsset')) if operation and operation.get('debtToAsset') else None,
            float(operation.get('currentRatio')) if operation and operation.get('currentRatio') else None,
            float(operation.get('quickRatio')) if operation and operation.get('quickRatio') else None,
        ),
        'update_basic': (total_share, liqa_share, plain),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db-path', default='data/stock_data.db')
    parser.add_argument('--kline-limit', type=int, default=400)
    parser.add_argument('--basic-limit', type=int, default=200)
    parser.add_argument('--financial-quarters', type=int, default=4)
    parser.add_argument('--start-date', default='2025-01-01')
    parser.add_argument('--end-date', default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    cfg = Config(**vars(args))

    conn = sqlite3.connect(cfg.db_path)
    ensure_schema(conn)
    before = get_coverage(conn)
    kline_codes = query_top_codes(conn, cfg.kline_limit)
    basic_codes = query_top_codes(conn, cfg.basic_limit)
    print('before', before)
    print(f'selected kline codes={len(kline_codes)} basic codes={len(basic_codes)}')

    lg = bs_login_silent()
    if lg.error_code != '0':
        print(f'baostock login failed: {lg.error_msg}', file=sys.stderr)
        sys.exit(1)

    kline_ok = kline_rows = 0
    basic_ok = fin_ok = 0
    started = time.time()
    try:
        cur = conn.cursor()
        for idx, code in enumerate(kline_codes, 1):
            bs_code = plain_to_bs(code)
            try:
                rows = fetch_kline_rows(bs_code, cfg.start_date, cfg.end_date)
                if rows:
                    cur.executemany(
                        """
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount, change_pct, amplitude, turnover_rate, pe_ttm, pb_mrq, adjust_flag, frequency)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'bfq', 'daily')
                        """,
                        rows,
                    )
                    kline_ok += 1
                    kline_rows += len(rows)
                if idx % 50 == 0:
                    conn.commit()
                    print(f'kline progress {idx}/{len(kline_codes)} ok={kline_ok} rows={kline_rows} elapsed={time.time()-started:.1f}s')
            except Exception as e:
                print(f'kline fail {code}: {e}')
        conn.commit()

        for idx, code in enumerate(basic_codes, 1):
            bs_code = plain_to_bs(code)
            try:
                payload = fetch_basic_payload(bs_code)
                if payload:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO stock_basic
                        (code, name, list_date, total_shares, float_shares, industry, area, market)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        payload,
                    )
                    basic_ok += 1
            except Exception as e:
                print(f'basic fail {code}: {e}')

            y = datetime.now().year
            q = (datetime.now().month - 1) // 3 + 1
            for _ in range(cfg.financial_quarters):
                try:
                    fin_payload = fetch_financial_payload(bs_code, y, q)
                    if fin_payload:
                        cur.execute(
                            """
                            INSERT OR REPLACE INTO financial_data
                            (code, report_date, pub_date, roe_avg, roe_weight, net_margin, gross_margin,
                             net_profit, eps_basic, eps_diluted, total_revenue, total_shares, float_shares,
                             debt_ratio, current_ratio, quick_ratio)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            fin_payload['insert'],
                        )
                        cur.execute(
                            """
                            UPDATE stock_basic
                            SET total_shares = COALESCE(?, total_shares),
                                float_shares = COALESCE(?, float_shares),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE code = ?
                            """,
                            fin_payload['update_basic'],
                        )
                        fin_ok += 1
                except Exception as e:
                    print(f'financial fail {code} {y}Q{q}: {e}')
                q -= 1
                if q <= 0:
                    q = 4
                    y -= 1

            if idx % 25 == 0:
                conn.commit()
                print(f'basic progress {idx}/{len(basic_codes)} basic_ok={basic_ok} fin_ok={fin_ok} elapsed={time.time()-started:.1f}s')
        conn.commit()
    finally:
        bs_logout_silent()
        after = get_coverage(conn)
        conn.close()
        print('after', after)
        print({
            'kline_ok': kline_ok,
            'kline_rows': kline_rows,
            'basic_ok': basic_ok,
            'financial_ok': fin_ok,
            'elapsed_sec': round(time.time() - started, 1),
        })


if __name__ == '__main__':
    main()
