import sqlite3

import core.data_manager as dm


def test_get_available_dates_order(tmp_path, monkeypatch):
    db = tmp_path / "dm_test.db"
    monkeypatch.setattr(dm, "DB_PATH", str(db))
    dm.init_db()

    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO daily_market (code, date, name, price) VALUES ('000001', '2026-03-29', '平安银行', 11.1)")
        conn.execute("INSERT INTO daily_market (code, date, name, price) VALUES ('000001', '2026-03-31', '平安银行', 12.1)")
        conn.execute("INSERT INTO daily_market (code, date, name, price) VALUES ('600000', '2026-03-30', '浦发银行', 10.1)")
        conn.commit()
    finally:
        conn.close()

    dates = dm.get_available_dates()
    assert dates == ["2026-03-31", "2026-03-30", "2026-03-29"]
