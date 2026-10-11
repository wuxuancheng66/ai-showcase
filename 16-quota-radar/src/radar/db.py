"""SQLite 存储层：WAL 模式 + 全部表结构。薄封装，无 ORM 依赖。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from radar.config import db_path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    key TEXT PRIMARY KEY,            -- provider/model_id
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    display_name TEXT,
    input_price REAL,                -- USD / 1M tokens
    output_price REAL,               -- USD / 1M tokens
    context_len INTEGER,
    free INTEGER NOT NULL DEFAULT 0,
    capability_score REAL,
    scenario_flags TEXT,             -- JSON: {"reasoning":bool,"code":bool}
    source TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_models_free ON models(free);
CREATE INDEX IF NOT EXISTS idx_models_score ON models(capability_score);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key TEXT NOT NULL,
    input_price REAL,
    output_price REAL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,              -- price_drop/price_rise/new_model/new_free_model/model_removed/context_change/channel_status/activity
    target TEXT NOT NULL,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    summary TEXT,
    notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT,
    tier TEXT,                       -- free / cheap
    url TEXT,
    kind TEXT,                       -- api / page
    requires_key INTEGER DEFAULT 0,
    env_key TEXT,                    -- .env 中存放自有 API key 的变量名
    probe_type TEXT,
    probe_base_url TEXT,
    probe_model TEXT,
    free_tier_desc TEXT,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',  -- unknown/ok/limited/error/dead
    last_checked TEXT,
    last_ok TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    kind TEXT,                       -- daily / promo
    note TEXT,
    content_hash TEXT,
    last_seen TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/done
    done_at TEXT
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT,
    model_key TEXT,
    tokens INTEGER NOT NULL,
    note TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configured_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,             -- openclaw / 未来其他 agent
    channel_id TEXT,                 -- 来源渠道 id（channels.yaml）
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    base_url TEXT,
    set_default INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,      -- 部署后验证通过才置 1
    verify_detail TEXT,
    deployed_at TEXT,
    verified_at TEXT
);

CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS monitor_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_tokens INTEGER,
    used_tokens INTEGER,
    limit_tokens INTEGER,
    balance_value REAL,
    balance_unit TEXT,
    daily_burn REAL,
    days_left REAL,
    cost_usd REAL,
    confidence REAL NOT NULL DEFAULT 0.5,
    detail TEXT,
    captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_subject_time
ON monitor_snapshots(subject, id DESC);

CREATE TABLE IF NOT EXISTS job_state (
    job_name TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'idle',      -- idle/running/ok/error/skipped
    last_started_at TEXT,
    last_finished_at TEXT,
    duration_ms INTEGER,
    last_error TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path(), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """轻量、可重复的 SQLite schema 迁移。

    v1 是当前的基线与版本登记；旧数据库只有 user_version=0，执行后会安全升级。
    后续版本只允许在这里追加前向迁移，不在启动路径里做破坏性变更。
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"数据库 schema 版本 {current} 高于程序支持的 {SCHEMA_VERSION}，请升级 QuotaRadar"
        )

    migrations = {
        1: lambda _c: None,
    }
    for version in range(current + 1, SCHEMA_VERSION + 1):
        migrations[version](conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES(?,?)",
            (version, now_iso()),
        )
        conn.execute(f"PRAGMA user_version={version}")


def init_db(path: Path | None = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def kv_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
