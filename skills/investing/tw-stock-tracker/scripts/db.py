"""SQLite 儲存層：日線快取、除權息事件、預測記錄。

資料庫放家目錄（~/.stock-tracker/tracker.db），不進制度 repo：
predictions 是個人交易判斷資料且持續增長，不該污染三 harness 共用的正本。
"""

import os
import sqlite3

DEFAULT_DB_PATH = os.path.expanduser("~/.stock-tracker/tracker.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_quotes (
    ticker      TEXT NOT NULL,
    date        TEXT NOT NULL,           -- ISO yyyy-mm-dd
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,           -- 原始收盤價（未還原）
    volume      INTEGER NOT NULL,        -- 成交股數
    is_exdiv    INTEGER NOT NULL DEFAULT 0,  -- TWSE 漲跌價差 X 標記
    adj_close   REAL,                    -- 還原收盤價，由 rebuild_adj_close 計算
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS dividends (
    ticker      TEXT NOT NULL,
    ex_date     TEXT NOT NULL,           -- ISO yyyy-mm-dd
    cash        REAL NOT NULL DEFAULT 0, -- 每股現金股利
    stock_ratio REAL NOT NULL DEFAULT 0, -- 每股配股數（1000 股配 N 股 -> N/1000）
    source      TEXT,
    PRIMARY KEY (ticker, ex_date)
);

CREATE TABLE IF NOT EXISTS predictions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at           TEXT NOT NULL,  -- 資料基準日（最後一根日線的日期）
    ticker               TEXT NOT NULL,
    horizon_days         INTEGER NOT NULL,
    close_at_pred        REAL NOT NULL,
    adj_close_at_pred    REAL NOT NULL,
    score                INTEGER NOT NULL,
    s_trend              INTEGER NOT NULL,
    s_bias               INTEGER NOT NULL,
    s_support            INTEGER NOT NULL,
    s_volume             INTEGER NOT NULL,
    s_macd               INTEGER NOT NULL,
    s_rsi                INTEGER NOT NULL,
    signal               TEXT NOT NULL,
    entry_low            REAL,
    entry_high           REAL,
    stop_loss            REAL,
    hard_rules           TEXT NOT NULL DEFAULT '[]',  -- JSON array
    flags                TEXT NOT NULL DEFAULT '[]',  -- JSON array
    thesis               TEXT,           -- 唯一允許 LLM 寫入的欄位
    status               TEXT NOT NULL,  -- open / resolved / voided / needs_review
    resolve_date         TEXT,
    close_at_resolve     REAL,
    adj_close_at_resolve REAL,
    return_pct           REAL,
    hit                  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pred_status ON predictions(status, ticker);
"""


def connect(db_path=None):
    """開啟連線並確保 schema 存在。"""
    path = db_path or os.environ.get("STOCK_TRACKER_DB") or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
