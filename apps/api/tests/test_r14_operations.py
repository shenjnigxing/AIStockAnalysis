"""Non-destructive database/collector/deployment operational regression."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.cli import quotes
from app.db.init_db import SchemaCompatibilityError, validate_existing_schema

ROOT = Path(__file__).resolve().parents[3]


def test_test_fixture_rejects_persistent_database_before_import(tmp_path):
    dbfile = tmp_path / 'personal.sqlite3'
    with sqlite3.connect(dbfile) as db:
        db.execute('CREATE TABLE sentinel (value TEXT)')
        db.execute("INSERT INTO sentinel VALUES ('keep')")
    env = dict(os.environ, DATABASE_URL='sqlite:///' + dbfile.as_posix())
    result = subprocess.run([sys.executable, '-c',
        "import runpy; runpy.run_path('apps/api/tests/conftest.py')"],
        cwd=ROOT, env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'Refusing destructive tests' in result.stderr
    with sqlite3.connect(dbfile) as db:
        assert db.execute('SELECT value FROM sentinel').fetchall() == [('keep',)]


def test_default_test_collection_uses_memory_before_application_import():
    env = dict(os.environ)
    env.pop('DATABASE_URL', None)
    env['PYTHONPATH'] = str(ROOT / 'apps/api')
    result = subprocess.run([sys.executable, '-c',
        "import runpy; runpy.run_path('apps/api/tests/conftest.py'); "
        "from app.db.session import engine; print(engine.url)"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == 'sqlite:///:memory:'


def test_schema_preflight_rejects_incompatible_existing_table_without_mutation():
    from app.db import models  # register all metadata
    probe = create_engine('sqlite:///:memory:')
    with probe.begin() as connection:
        connection.execute(text('CREATE TABLE stock_master (id INTEGER PRIMARY KEY, symbol TEXT)'))
        connection.execute(text("INSERT INTO stock_master VALUES (1, 'keep')"))
    with pytest.raises(SchemaCompatibilityError, match='Incompatible database schema'):
        validate_existing_schema(probe)
    with probe.connect() as connection:
        assert connection.execute(text('SELECT symbol FROM stock_master')).all() == [('keep',)]


def test_storage_failure_isolated_and_next_cycle_can_continue(monkeypatch, capsys):
    calls = []
    def refresh(db, *, kind, symbol):
        calls.append(symbol)
        if symbol == 'AAPL':
            raise OperationalError('hidden', {}, RuntimeError('disconnected'))
        return {'cached': False, 'quote': {'symbol': symbol}}
    monkeypatch.setattr(quotes, 'refresh_quote', refresh)
    assert quotes.collect_once([('us_equity', 'AAPL'), ('us_etf', 'QQQ')]) == 1
    assert quotes.collect_once([('us_etf', 'QQQ')]) == 0
    records = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [x['state'] for x in records] == ['unavailable', 'collected', 'collected']
    assert 'hidden' not in str(records)
    assert calls == ['AAPL', 'QQQ', 'QQQ']


def test_deployment_is_local_and_dependency_install_is_locked():
    compose = (ROOT / 'docker-compose.yml').read_text()
    assert '127.0.0.1:8000:8000' in compose
    assert '127.0.0.1:3000:3000' in compose
    assert '5432:5432' not in compose and '6379:6379' not in compose
    assert './data:/data' in compose and 'sqlite:////data/aistock.local.sqlite3' in compose
    assert './apps/web:/app' not in compose
    dockerfile = (ROOT / 'apps/web/Dockerfile').read_text()
    assert 'RUN npm ci' in dockerfile and 'package-lock.json' in dockerfile
    assert '"0.0.0.0"' in dockerfile
