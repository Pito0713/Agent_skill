"""SQLite 儲存層：原始資料快取 + 對 tw-stock-tracker 公開的契約表。

與 tw-stock-tracker 共用同一個 DB（~/.stock-tracker/tracker.db），
這樣 tracker 只需 SQL JOIN 就能讀背景欄位，兩個 skill 不互相 import 程式碼。

契約表（stock_industry / market_context / sector_context）的欄位是跨 skill 介面，
改動前必須同步 tw-stock-tracker/references/db-schema.md。
"""

import os
import sqlite3

DEFAULT_DB_PATH = os.path.expanduser("~/.stock-tracker/tracker.db")

SCHEMA = """
-- 原始快取：每個查過的日期記一筆，非交易日也記，避免重抓
CREATE TABLE IF NOT EXISTS rotation_fetch_log (
    date        TEXT PRIMARY KEY,        -- ISO yyyy-mm-dd
    is_trading  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS market_daily (
    date        TEXT PRIMARY KEY,
    turnover    REAL NOT NULL,           -- 證券合計成交金額（元）
    advances    INTEGER NOT NULL,        -- 上漲家數（股票）
    declines    INTEGER NOT NULL,        -- 下跌家數（股票）
    taiex       REAL NOT NULL            -- 發行量加權股價指數收盤
);

CREATE TABLE IF NOT EXISTS sector_daily (
    date          TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    index_close   REAL,
    turnover      REAL,                  -- 類股成交金額（元）
    PRIMARY KEY (date, industry_code)
);

-- ===== 契約表：tw-stock-tracker 會讀 =====
CREATE TABLE IF NOT EXISTS stock_industry (
    ticker        TEXT PRIMARY KEY,
    industry_code TEXT,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS market_context (
    date           TEXT PRIMARY KEY,
    turnover_ratio REAL,
    breadth_5d     REAL,
    market_state   TEXT                  -- 充足 / 普通 / 不足 / NULL(資料不足)
);

CREATE TABLE IF NOT EXISTS sector_context (
    date          TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    rs_ratio      REAL,
    rs_momentum   REAL,
    quadrant      TEXT,                  -- Leading / Weakening / Lagging / Improving / NULL
    share_delta   REAL,
    PRIMARY KEY (date, industry_code)
);
"""


def connect(db_path=None):
    """開啟連線並確保 schema 存在。"""
    path = db_path or os.environ.get("STOCK_TRACKER_DB") or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
