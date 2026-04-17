"""A 股数据引擎 - 支持历史 K 线和基本面数据的数据管理器。"""

import sqlite3
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import os
import shutil
import io
from contextlib import redirect_stdout, redirect_stderr

def _can_open_sqlite(db_path: str) -> bool:
    try:
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS __healthcheck (id INTEGER)")
        conn.execute("INSERT INTO __healthcheck (id) VALUES (1)")
        conn.execute("DELETE FROM __healthcheck WHERE id = 1")
        conn.execute("PRAGMA integrity_check")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def _resolve_db_path() -> str:
    """选择可写的数据库路径：优先环境变量，其次项目目录，失败回退共享内存库。"""
    env_path = os.environ.get("ASTOCK_DB_PATH", "").strip()
    if env_path:
        if _can_open_sqlite(env_path):
            print(f"使用环境变量数据库路径: {env_path}")
            return env_path
        print(f"警告：ASTOCK_DB_PATH 不可写，忽略该路径: {env_path}")

    project_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_data.db")
    if _can_open_sqlite(project_path):
        return project_path

    mem_uri = "file:astock_memdb?mode=memory&cache=shared"
    try:
        conn = sqlite3.connect(mem_uri, uri=True)
        conn.execute("CREATE TABLE IF NOT EXISTS __healthcheck (id INTEGER)")
        conn.commit()
        conn.close()
        print("警告：项目目录数据库不可写，已切换到共享内存数据库（重启后数据会丢失）")
        return mem_uri
    except Exception:
        raise RuntimeError("无法找到可写的 SQLite 数据库路径")


# 使用可写路径
DB_PATH = _resolve_db_path()
_MEM_KEEPER = sqlite3.connect(DB_PATH, uri=True) if "mode=memory" in DB_PATH else None
_STOCK_POOL_CACHE = {"ts": 0.0, "codes": []}


def _bs_login_silent(bs_module):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs_module.login()


def _bs_logout_silent(bs_module):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return bs_module.logout()


def get_db_meta() -> dict:
    """返回数据库运行信息。"""
    is_memory = "mode=memory" in DB_PATH
    return {
        "db_path": DB_PATH,
        "db_mode": "memory" if is_memory else "file",
        "persistent": not is_memory,
    }


def _rebuild_db_file():
    """当数据库出现磁盘 I/O 异常时，备份并重建。"""
    if "mode=memory" in DB_PATH:
        return
    if os.path.exists(DB_PATH):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak_path = f"{DB_PATH}.{ts}.bak"
        try:
            shutil.copy2(DB_PATH, bak_path)
            print(f"已备份异常数据库到: {bak_path}")
        except Exception as e:
            print(f"备份数据库失败：{e}")
    for p in [DB_PATH, f"{DB_PATH}-journal"]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    # 仅重建空文件，表结构由后续 init_db 负责创建
    conn = sqlite3.connect(DB_PATH)
    conn.close()


def get_db_connection():
    """获取数据库连接。"""
    try:
        use_uri = "mode=memory" in DB_PATH
        conn = sqlite3.connect(DB_PATH, uri=use_uri)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        # 某些异常中断会残留 journal，导致后续出现 disk I/O error
        if "disk I/O error" in str(e):
            journal_path = f"{DB_PATH}-journal"
            if os.path.exists(journal_path):
                try:
                    os.remove(journal_path)
                except Exception:
                    pass
            use_uri = "mode=memory" in DB_PATH
            conn = sqlite3.connect(DB_PATH, uri=use_uri)
            conn.row_factory = sqlite3.Row
            return conn
        raise


def init_db(_retried: bool = False):
    """初始化 SQLite 数据库，创建所有表。"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except sqlite3.OperationalError as e:
        if "disk I/O error" in str(e) and not _retried:
            print("初始化数据库时遇到 I/O 异常，尝试重建数据库...")
            _rebuild_db_file()
            return init_db(_retried=True)
        raise

    # 1. 每日市场快照表 (现有表升级)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_market (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            name TEXT,
            price REAL,
            pe REAL,
            pb REAL,
            turnover REAL,
            volume REAL,
            amount REAL,
            change_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, date)
        )
    """)

    # 2. K 线历史数据表 (支持复权)
    cursor.execute("""
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
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kline_code ON kline_data(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kline_date ON kline_data(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kline_freq ON kline_data(frequency)")

    # 3. 股票基本信息表
    cursor.execute("""
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
    """)

    # 4. 财务指标表 (季度)
    cursor.execute("""
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
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_code ON financial_data(code)")

    # 5. 股东数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_holder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            report_date TEXT NOT NULL,
            holder_count INTEGER,
            avg_holdings REAL,
            top10_holder_ratio REAL,
            top10_flow_ratio REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, report_date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_holder_code ON stock_holder(code)")

    try:
        conn.commit()
        conn.close()
        print("数据库初始化完成")
    except sqlite3.OperationalError as e:
        if "disk I/O error" in str(e) and not _retried:
            print("提交数据库结构时遇到 I/O 异常，尝试重建数据库...")
            try:
                conn.close()
            except Exception:
                pass
            _rebuild_db_file()
            return init_db(_retried=True)
        raise


# ==================== 实时行情数据获取 ====================

def _get_all_a_share_codes():
    """获取所有 A 股股票代码列表（本地优先，外部兜底）。"""
    import baostock as bs

    # 先走内存缓存，避免频繁读取或网络查询
    now = time.time()
    if _STOCK_POOL_CACHE["codes"] and now - _STOCK_POOL_CACHE["ts"] <= 3600:
        return list(_STOCK_POOL_CACHE["codes"])

    # 1) 本地库优先（增量模式）：只要本地股票池规模足够，后续刷新不再全量依赖外网代码列表
    try:
        init_db()
        conn = get_db_connection()
        try:
            q = """
                SELECT DISTINCT code FROM (
                    SELECT code FROM daily_market
                    UNION ALL
                    SELECT code FROM stock_basic
                ) t
                WHERE code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
                ORDER BY code
            """
            df = pd.read_sql(q, conn)
        finally:
            conn.close()

        if not df.empty:
            codes = df["code"].astype(str).tolist()
            formatted = [f"sh{c}" if c.startswith("6") else f"sz{c}" for c in codes if len(c) == 6]
            # A 股池正常应在 3000+，达到该规模即认为本地池可用
            if len(formatted) >= 3000:
                print(f"从本地数据库复用股票池：{len(formatted)}")
                _STOCK_POOL_CACHE["ts"] = now
                _STOCK_POOL_CACHE["codes"] = list(formatted)
                return formatted
    except Exception as e:
        print(f"从本地数据库读取股票池失败：{e}")

    # 2) 本地不足时，才访问 Baostock 拉全量股票池
    try:
        _bs_login_silent(bs)
        rs = bs.query_all_stock(day=datetime.now().strftime("%Y-%m-%d"))

        codes = []
        while rs.next():
            row = rs.get_row_data()
            code = row[rs.fields.index('code')]
            code_name = row[rs.fields.index('code_name')]

            # 过滤掉指数和其他非股票品种
            if '.' in code:
                # 转换代码格式 (sh.600000 -> sh600000)
                formatted_code = code.replace('.', '')
                # 只保留常见 A 股股票代码段，过滤指数/ETF/债券
                is_a_share = code.startswith(('sh.60', 'sh.68', 'sz.00', 'sz.30'))
                bad_name_tokens = ['指数', 'ETF', 'LOF', '债', '基金', '转债']
                if (
                    is_a_share
                    and code_name
                    and not code_name.endswith('B')
                    and not any(t in code_name for t in bad_name_tokens)
                ):
                    codes.append(formatted_code)

        _bs_logout_silent(bs)

        if codes:
            print(f"从 Baostock 获取到 {len(codes)} 只股票")
            _STOCK_POOL_CACHE["ts"] = now
            _STOCK_POOL_CACHE["codes"] = list(codes)
            return codes

    except Exception as e:
        print(f"Baostock 获取股票列表失败：{e}")

    # 3) 备用方案：复用 daily_market，避免盲扫过多无效代码
    print("使用备用方案获取代码列表...")
    try:
        init_db()
        conn = get_db_connection()
        df = pd.read_sql("SELECT DISTINCT code FROM daily_market ORDER BY code", conn)
        conn.close()
        if not df.empty:
            codes = df["code"].astype(str).tolist()
            # 转为腾讯接口格式
            formatted = [f"sh{c}" if c.startswith("6") else f"sz{c}" for c in codes if len(c) == 6]
            if formatted:
                print(f"从本地数据库复用股票池：{len(formatted)}")
                _STOCK_POOL_CACHE["ts"] = now
                _STOCK_POOL_CACHE["codes"] = list(formatted)
                return formatted
    except Exception as e:
        print(f"从本地数据库读取股票池失败：{e}")

    # 最后兜底：仅生成常见 A 股主代码段（控制数量）
    codes = []
    for prefix in ["600", "601", "603", "605", "688"]:
        for i in range(1000):
            codes.append(f"sh{prefix}{i:03d}")
    for prefix in ["000", "001", "002", "003", "300", "301"]:
        for i in range(1000):
            codes.append(f"sz{prefix}{i:03d}")
    _STOCK_POOL_CACHE["ts"] = now
    _STOCK_POOL_CACHE["codes"] = list(codes)
    return codes


def fetch_and_cache(force_refresh: bool = False):
    """从腾讯财经获取实时行情数据并缓存。"""
    try:
        init_db()
    except sqlite3.OperationalError as e:
        if "disk I/O error" in str(e):
            print("刷新前检测到数据库 I/O 异常，尝试修复后继续...")
            _rebuild_db_file()
            init_db()
        else:
            raise
    print("正在获取 A 股实时行情...")
    today = datetime.now().strftime("%Y-%m-%d")

    latest_df = pd.DataFrame()
    latest_date = None
    latest_refresh_at = None
    try:
        conn = get_db_connection()
        try:
            latest_meta = pd.read_sql("SELECT MAX(date) AS latest_date, MAX(created_at) AS latest_refresh_at FROM daily_market", conn).iloc[0]
            latest_date = latest_meta.get("latest_date")
            latest_refresh_at = latest_meta.get("latest_refresh_at")
            if latest_date:
                latest_df = pd.read_sql("SELECT * FROM daily_market WHERE date = ?", conn, params=[latest_date])
        finally:
            conn.close()
    except Exception:
        latest_df = pd.DataFrame()

    # 若当日数据刚更新过，直接复用，避免短时间重复全量拉取。
    # 但手动刷新时应强制重新抓取，否则“刚刷新却仍显示旧刷新时间”会误导前端。
    if not force_refresh and latest_date == today and not latest_df.empty:
        try:
            dt = pd.to_datetime(latest_refresh_at, errors="coerce")
            age_sec = (datetime.now() - dt.to_pydatetime()).total_seconds() if pd.notna(dt) else 999999
        except Exception:
            age_sec = 999999
        if age_sec <= 120 and len(latest_df) >= 3000:
            print(f"复用最新快照：{latest_date}，距今 {int(age_sec)} 秒，股票数 {len(latest_df)}")
            return latest_df

    # 优先增量：若已有当日快照，则按当日股票池更新；否则走全量池
    if latest_date == today and not latest_df.empty:
        codes = latest_df["code"].astype(str).tolist()
        all_codes = [f"sh{c}" if c.startswith("6") else f"sz{c}" for c in codes if len(c) == 6]
        print(f"增量更新模式：使用当日股票池 {len(all_codes)} 只")
    else:
        all_codes = _get_all_a_share_codes()
        print(f"全量更新模式：待检测代码数量 {len(all_codes)}")

    all_data = []
    batch_size = 100
    valid_count = 0
    invalid_count = 0
    session = requests.Session()
    session.trust_env = False

    for i in range(0, len(all_codes), batch_size):
        batch = all_codes[i:i+batch_size]
        code_str = ','.join(batch)

        try:
            url = f'http://qt.gtimg.cn/q={code_str}'
            resp = session.get(url, timeout=10)
            resp.encoding = 'gbk'

            for line in resp.text.split('\n'):
                if not line.strip():
                    continue
                parts = line.split('~')
                if len(parts) < 50:
                    invalid_count += 1
                    continue

                try:
                    raw_code = parts[2].strip()
                    code = raw_code[2:] if raw_code.startswith(("sh", "sz")) and len(raw_code) >= 8 else raw_code
                    code = code.replace(".", "")
                    name = parts[1]
                    price = float(parts[3]) if parts[3] else 0

                    # 价格为 0 或无效的跳过
                    if price <= 0:
                        invalid_count += 1
                        continue

                    # 过滤无效股票（名称为空或价格异常）
                    if not name or name.strip() == '':
                        invalid_count += 1
                        continue

                    # 腾讯字段：32 通常是涨跌幅百分比；38 为换手率，误用会导致“几乎全涨”
                    change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else 0
                    pb = float(parts[46]) if len(parts) > 46 and parts[46] else 0
                    pe = float(parts[47]) if len(parts) > 47 and parts[47] else 0
                    volume = float(parts[6]) if len(parts) > 6 and parts[6] else 0  # 手
                    amount = float(parts[37]) if len(parts) > 37 and parts[37] else 0  # 万元
                    float_shares = float(parts[49]) if len(parts) > 49 and parts[49] else 0
                    turnover_from_api = float(parts[38]) if len(parts) > 38 and parts[38] else 0

                    # 计算换手率
                    turnover_calc = round((volume * 100) / (float_shares * 1e8) * 100, 2) if float_shares > 0 else 0
                    turnover = turnover_from_api if turnover_from_api > 0 else turnover_calc

                    # 基础过滤：仅保留 6 位股票代码；剔除常见非股票名称
                    if len(code) != 6 or not code[:1].isdigit():
                        invalid_count += 1
                        continue
                    bad_name_tokens = ["指数", "ETF", "LOF", "债", "基金", "转债"]
                    if any(t in name for t in bad_name_tokens):
                        invalid_count += 1
                        continue

                    # 异常涨跌幅裁剪（防止字段异常污染）
                    if abs(change_pct) > 40:
                        invalid_count += 1
                        continue

                    all_data.append({
                        'code': code,
                        'name': name,
                        'price': price,
                        'pe': pe,
                        'pb': pb,
                        'turnover': turnover,
                        'volume': volume,
                        'amount': amount * 10000,  # 转为元
                        'change_pct': change_pct,
                        'date': datetime.now().strftime("%Y-%m-%d")
                    })
                    valid_count += 1
                except Exception as e:
                    invalid_count += 1
                    continue
        except Exception as e:
            print(f'Batch {i} error: {e}')
            continue

    if all_data:
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset=['code'])
        df = df[df['price'] > 0]
        # 保留 A 股主要代码段
        df = df[df["code"].str.match(r"^(60|68|00|30)\d{4}$", na=False)]

        # 保存到 daily_market 表
        try:
            conn = get_db_connection()
            conn.execute("DELETE FROM daily_market WHERE date = ?", (today,))
            df.to_sql('daily_market', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
        except sqlite3.OperationalError as e:
            if "disk I/O error" not in str(e):
                raise
            print("检测到数据库 I/O 异常，正在重建数据库并重试写入...")
            _rebuild_db_file()
            conn = get_db_connection()
            conn.execute("DELETE FROM daily_market WHERE date = ?", (today,))
            df.to_sql('daily_market', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()

        print(f"成功获取 {len(df)} 只股票实时行情")
        print(f"有效股票：{valid_count}, 无效代码：{invalid_count}")

        # 统计各板块股票数量（代码为纯数字格式）
        kcb_count = len(df[df['code'].str.startswith('688')])
        sh_count = len(df[df['code'].str.startswith('6')]) - kcb_count
        cyb_count = len(df[df['code'].str.startswith('30')])
        sz_count = len(df[df['code'].str.startswith('0')])
        print(f"  沪市主板：{sh_count}, 科创板：{kcb_count}")
        print(f"  深市主板：{sz_count}, 创业板：{cyb_count}")

        return df
    else:
        raise Exception("未能获取到任何数据")


# ==================== 5 分钟 K 线数据获取 (使用新浪财经) ====================

def fetch_min_kline(code: str, period: str = '5', timeout_sec: float = 6.0, datalen: int = 512) -> pd.DataFrame:
    """
    获取单只股票的分钟 K 线数据（从新浪财经）。

    Args:
        code: 股票代码 (如 sh600000 或 sz000001)
        period: K 线周期，支持 1/5/15/30/60 (分钟)

    Returns:
        DataFrame with minute K-line data (最近 1024 根 K 线)

    数据源：http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
    """
    # 转换代码格式 (600000 -> sh600000)
    if not code.startswith(('sh', 'sz')):
        if code.startswith('6'):
            code = f'sh{code}'
        else:
            code = f'sz{code}'

    safe_timeout = max(2.0, float(timeout_sec or 6.0))
    safe_datalen = max(120, min(int(datalen or 512), 1024))
    url = (
        "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={code}&scale={period}&ma=no&datalen={safe_datalen}"
    )

    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, timeout=(3.5, safe_timeout))
        resp.encoding = 'utf-8'

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code} for {code}")
            return pd.DataFrame()

        import json
        data_list = json.loads(resp.text)

        if not data_list:
            return pd.DataFrame()

        # 解析数据（新浪 API 返回的字段是 day 不是 date，没有 amount 字段）
        df_data = []
        for row in data_list:
            df_data.append({
                'date': row.get('day', ''),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('volume', 0)),
                'amount': float(row.get('volume', 0)) * 100  # 估算成交额（手 *100）
            })

        df = pd.DataFrame(df_data)

        # 数据清洗
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

        # 计算涨跌幅
        df['change_pct'] = df['close'].pct_change() * 100

        # 计算振幅
        df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1) * 100).round(2)

        # 添加周期标记
        df['frequency'] = f'{period}min'

        return df

    except Exception as e:
        print(f"Error fetching {code} {period}min K-line: {e}")
        return pd.DataFrame()


def save_min_kline_for_all_stocks(period: str = '5', batch_size: int = 50):
    """
    批量获取所有股票的分钟 K 线数据并保存。

    Args:
        period: K 线周期 (分钟)
        batch_size: 每批处理的股票数量
    """
    init_db()

    # 获取股票列表
    conn = get_db_connection()
    query = "SELECT DISTINCT code, name FROM daily_market ORDER BY code"
    stock_df = pd.read_sql(query, conn)
    conn.close()

    stock_list = list(zip(stock_df['code'].tolist(), stock_df['name'].tolist()))
    print(f"共找到 {len(stock_list)} 只股票，开始获取 {period}分钟 K 线数据...")

    conn = get_db_connection()
    cursor = conn.cursor()

    success_count = 0
    fail_count = 0

    for idx, (code, name) in enumerate(stock_list):
        try:
            if (idx + 1) % 100 == 0:
                print(f"[{idx+1}/{len(stock_list)}] 获取 {code} {name}...")

            df = fetch_min_kline(code, period)

            if len(df) > 0:
                # 批量插入
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount,
                         change_pct, amplitude, frequency, adjust_flag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        code, row['date'], row['open'], row['high'],
                        row['low'], row['close'], row['volume'], row['amount'],
                        row.get('change_pct'), row.get('amplitude'), f'{period}min', 'bfq'
                    ))

                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            fail_count += 1
            print(f"  错误：{code} - {e}")
            continue

        # 每批提交
        if (idx + 1) % batch_size == 0:
            conn.commit()

    conn.commit()
    conn.close()

    print(f"\n完成！成功：{success_count}, 失败：{fail_count}")


# ==================== 历史 K 线数据获取 (使用 Baostock) ====================

def fetch_kline_history(code: str, start_date: str = None, end_date: str = None, adjust_flag: str = '3', bs_module=None):
    """
    获取单只股票的历史 K 线数据。

    Args:
        code: 股票代码 (如 sh600000)
        start_date: 开始日期 YYYY-MM-DD，默认 5 年前
        end_date: 结束日期 YYYY-MM-DD，默认今天
        adjust_flag: 复权类型 1=后复权，2=前复权，3=不复权
        bs_module: 可选，已登录的 baostock 模块，用于批量任务复用会话

    Returns:
        DataFrame with K-line data
    """
    import baostock as bs

    client = bs_module or bs
    owns_session = bs_module is None
    if owns_session:
        _bs_login_silent(client)

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    fields = "date,code,open,high,low,close,volume,amount,turn,pctChg,peTTM,pbMRQ"
    rs = client.query_history_k_data_plus(
        code=code,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag=adjust_flag
    )

    if rs.error_code != '0':
        print(f"Baostock error: {rs.error_msg}")
        if owns_session:
            _bs_logout_silent(client)
        return pd.DataFrame()

    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())

    if owns_session:
        _bs_logout_silent(client)

    if not data_list:
        return pd.DataFrame()

    df = pd.DataFrame(data_list, columns=rs.fields)

    # 数据清洗和转换
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg', 'peTTM', 'pbMRQ']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.rename(columns={
        'turn': 'turnover_rate',
        'pctChg': 'change_pct',
        'peTTM': 'pe_ttm',
        'pbMRQ': 'pb_mrq'
    })

    # 计算振幅
    if 'amplitude' not in df.columns and 'high' in df.columns and 'low' in df.columns:
        df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1) * 100).round(2)

    return df


def save_kline_for_all_stocks(batch_size: int = 50, start_date: str = None):
    """
    批量获取所有股票的历史 K 线数据并保存。

    Args:
        batch_size: 每批处理的股票数量
        start_date: 开始日期，默认 5 年前
    """
    import baostock as bs

    init_db()

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # 获取股票列表
    _bs_login_silent(bs)
    stock_list = []

    # 获取沪深 A 股列表
    rs = bs.query_all_stock(day=end_date)
    while rs.next():
        row = rs.get_row_data()
        code = row[rs.fields.index('code')]
        code_name = row[rs.fields.index('code_name')]
        # 过滤掉 ST，保留当前产品覆盖的主板/科创板/创业板
        if 'ST' not in code_name and code.startswith(('sh.60', 'sh.68', 'sz.00', 'sz.001', 'sz.002', 'sz.003', 'sz.30')):
            # baostock 拉取使用 sh.600000 / sz.000001，落库统一保存为 6 位数字代码
            stock_list.append((code, code_name))

    print(f"共找到 {len(stock_list)} 只股票，开始获取 K 线数据...")

    conn = get_db_connection()
    cursor = conn.cursor()

    success_count = 0
    fail_count = 0

    for idx, (code, name) in enumerate(stock_list):
        try:
            print(f"[{idx+1}/{len(stock_list)}] 获取 {code} {name} 的 K 线数据...")

            # 获取不复权数据（复用当前 baostock 会话，避免每只股票重复登录）
            df = fetch_kline_history(code, start_date, end_date, adjust_flag='3', bs_module=bs)

            if len(df) > 0:
                normalized_code = str(code).split('.')[-1]
                df['code'] = normalized_code
                df['adjust_flag'] = 'bfq'

                # 批量插入
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount, change_pct, amplitude, turnover_rate, pe_ttm, pb_mrq, adjust_flag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('code'), row.get('date'), row.get('open'), row.get('high'),
                        row.get('low'), row.get('close'), row.get('volume'), row.get('amount'),
                        row.get('change_pct'), row.get('amplitude'), row.get('turnover_rate'),
                        row.get('pe_ttm'), row.get('pb_mrq'), 'bfq'
                    ))

                success_count += 1
            else:
                fail_count += 1
                print(f"  警告：{code} 没有获取到数据")

            # 按 batch_size 提交，避免长事务占用过久
            if batch_size > 0 and (idx + 1) % batch_size == 0:
                conn.commit()
                print(f"  已提交 {idx+1} 只股票的数据")

        except Exception as e:
            fail_count += 1
            print(f"  错误：{code} - {e}")
            continue

    conn.commit()
    conn.close()
    _bs_logout_silent(bs)

    print(f"\n完成！成功：{success_count}, 失败：{fail_count}")


# ==================== 基本面数据获取 ====================

def fetch_stock_basic_info(code: str, bs_module=None):
    """获取股票基本信息。"""
    import baostock as bs

    client = bs_module or bs
    owns_session = bs_module is None

    code = str(code).strip()
    plain_code = code.replace("sh.", "").replace("sz.", "").replace("sh", "").replace("sz", "")
    bs_code = f"sh.{plain_code}" if plain_code.startswith("6") else f"sz.{plain_code}"

    if owns_session:
        lg = _bs_login_silent(client)
        if lg.error_code != "0":
            return None

    # 获取股票基本资料
    rs = client.query_stock_basic(code=bs_code)

    if rs.error_code != '0' or not rs.data:
        if owns_session:
            _bs_logout_silent(client)
        return None

    row = rs.data[0]
    result = dict(zip(rs.fields, row))

    # 获取行业资料
    industry = None
    try:
        rs_ind = client.query_stock_industry(code=bs_code)
        if rs_ind.error_code == "0" and rs_ind.data:
            ind = dict(zip(rs_ind.fields, rs_ind.data[0]))
            industry = ind.get("industry")
    except Exception:
        industry = None

    if owns_session:
        _bs_logout_silent(client)

    # 保存到数据库
    conn = get_db_connection()
    cursor = conn.cursor()

    # 从财务表补最新股本
    latest_fin = cursor.execute(
        """
        SELECT total_shares, float_shares
        FROM financial_data
        WHERE code = ?
        ORDER BY report_date DESC
        LIMIT 1
        """,
        (plain_code,),
    ).fetchone()
    total_shares = float(latest_fin["total_shares"]) if latest_fin and latest_fin["total_shares"] is not None else None
    float_shares = float(latest_fin["float_shares"]) if latest_fin and latest_fin["float_shares"] is not None else None

    cursor.execute("""
        INSERT OR REPLACE INTO stock_basic
        (code, name, list_date, total_shares, float_shares, industry, area, market)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        plain_code,
        result.get('code_name'),
        result.get('ipoDate'),
        total_shares,
        float_shares,
        industry,
        None,  # area
        '主板' if plain_code.startswith(('60', '00')) else ('创业板' if plain_code.startswith('30') else ('科创板' if plain_code.startswith('68') else '主板'))
    ))

    conn.commit()
    conn.close()

    return result


def fetch_financial_data(code: str, year: int = None, quarter: int = None, bs_module=None):
    """
    获取股票财务指标数据。

    Args:
        code: 股票代码
        year: 年份，默认当前年
        quarter: 季度 1-4，默认当前季度
        bs_module: 可选，已登录的 baostock 模块，用于批量任务复用会话
    """
    import baostock as bs

    client = bs_module or bs
    owns_session = bs_module is None

    code = str(code).strip()
    plain_code = code.replace("sh.", "").replace("sz.", "").replace("sh", "").replace("sz", "")
    bs_code = f"sh.{plain_code}" if plain_code.startswith("6") else f"sz.{plain_code}"

    if year is None:
        year = datetime.now().year
    if quarter is None:
        quarter = (datetime.now().month - 1) // 3 + 1

    if owns_session:
        _bs_login_silent(client)

    # 获取盈利能力数据
    rs_profit = client.query_profit_data(code=bs_code, year=year, quarter=quarter)
    profit_data = None
    if rs_profit.data:
        profit_data = dict(zip(rs_profit.fields, rs_profit.data[0]))

    # 获取营运能力数据
    rs_operation = client.query_operation_data(code=bs_code, year=year, quarter=quarter)
    operation_data = None
    if rs_operation.data:
        operation_data = dict(zip(rs_operation.fields, rs_operation.data[0]))

    # 获取成长能力数据
    rs_growth = client.query_growth_data(code=bs_code, year=year, quarter=quarter)
    growth_data = None
    if rs_growth.data:
        growth_data = dict(zip(rs_growth.fields, rs_growth.data[0]))

    if owns_session:
        _bs_logout_silent(client)

    # 合并数据并保存
    if profit_data:
        conn = get_db_connection()
        cursor = conn.cursor()

        report_date = profit_data.get("statDate") or f"{year}-{(quarter-1)*3+1:02d}-01"

        cursor.execute("""
            INSERT OR REPLACE INTO financial_data
            (code, report_date, pub_date, roe_avg, roe_weight, net_margin, gross_margin,
             net_profit, eps_basic, eps_diluted, total_revenue, total_shares, float_shares,
             debt_ratio, current_ratio, quick_ratio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plain_code,
            report_date,
            profit_data.get('pubDate') if profit_data else None,
            float(profit_data.get('roeAvg')) if profit_data and profit_data.get('roeAvg') else None,
            float(profit_data.get('roeWeight')) if profit_data and profit_data.get('roeWeight') else None,
            float(profit_data.get('npMargin')) if profit_data and profit_data.get('npMargin') else None,
            float(profit_data.get('gpMargin')) if profit_data and profit_data.get('gpMargin') else None,
            float(profit_data.get('netProfit')) if profit_data and profit_data.get('netProfit') else None,
            float(profit_data.get('epsTTM')) if profit_data and profit_data.get('epsTTM') else None,
            float(profit_data.get('epsDiluted')) if profit_data and profit_data.get('epsDiluted') else None,
            float(profit_data.get('MBRevenue')) if profit_data and profit_data.get('MBRevenue') else None,
            float(profit_data.get('totalShare')) if profit_data and profit_data.get('totalShare') else None,
            float(profit_data.get('liqaShare')) if profit_data and profit_data.get('liqaShare') else None,
            float(operation_data.get('debtToAsset')) if operation_data and operation_data.get('debtToAsset') else None,
            float(operation_data.get('currentRatio')) if operation_data and operation_data.get('currentRatio') else None,
            float(operation_data.get('quickRatio')) if operation_data and operation_data.get('quickRatio') else None,
        ))

        # 同步回写 stock_basic 的股本字段，保证数据中心可见
        cursor.execute(
            """
            UPDATE stock_basic
            SET total_shares = COALESCE(?, total_shares),
                float_shares = COALESCE(?, float_shares),
                updated_at = CURRENT_TIMESTAMP
            WHERE code = ?
            """,
            (
                float(profit_data.get('totalShare')) if profit_data and profit_data.get('totalShare') else None,
                float(profit_data.get('liqaShare')) if profit_data and profit_data.get('liqaShare') else None,
                plain_code,
            ),
        )

        conn.commit()
        conn.close()

    return {
        'profit': profit_data,
        'operation': operation_data,
        'growth': growth_data
    }


# ==================== 数据查询函数 ====================

def load_market_data() -> pd.DataFrame:
    """从 SQLite 读取最新市场数据。"""
    init_db()
    conn = get_db_connection()
    query = """
        SELECT * FROM daily_market
        WHERE date = (SELECT MAX(date) FROM daily_market)
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def get_latest_data() -> pd.DataFrame:
    """获取最新日期的数据。"""
    return load_market_data()


def get_kline_data(code: str, start_date: str = None, end_date: str = None, adjust_flag: str = 'bfq', frequency: str = 'daily') -> pd.DataFrame:
    """获取单只股票的 K 线数据（支持分钟 K 线）。

    Args:
        code: 股票代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        adjust_flag: 复权类型
        frequency: K 线频率 daily/daily, 5min, 15min, 30min, 60min
    """
    init_db()
    conn = get_db_connection()

    query = "SELECT * FROM kline_data WHERE code = ? AND adjust_flag = ? AND frequency = ?"
    params = [code, adjust_flag, frequency]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY date"

    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


def get_available_dates() -> list:
    """获取可用的数据日期列表。"""
    init_db()
    conn = get_db_connection()
    query = "SELECT DISTINCT date FROM daily_market ORDER BY date DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df['date'].tolist()


def get_stock_list() -> pd.DataFrame:
    """获取股票列表。"""
    init_db()
    conn = get_db_connection()
    query = "SELECT DISTINCT code, name FROM daily_market ORDER BY code"
    df = pd.read_sql(query, conn)
    conn.close()
    return df
