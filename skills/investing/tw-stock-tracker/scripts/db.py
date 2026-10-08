"""SQLite 儲存層：日線快取、除權息事件、預測記錄、校準門檻、估值與法人買賣超。

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
    stock_ratio REAL NOT NULL DEFAULT 0, -- 每股配股數（TWSE 原始值即每股）
    sub_ratio   REAL NOT NULL DEFAULT 0, -- 每股現金增資認購股數
    sub_price   REAL NOT NULL DEFAULT 0, -- 現金增資每股認購價
    source      TEXT,
    ref_ratio   REAL,                    -- 官方 參考價/前收；有值時還原直接用它，不依賴本地前收
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
    hit                  INTEGER,
    market_state         TEXT,           -- tw-market-rotation 背景欄位，未安裝時 NULL
    sector_quadrant      TEXT,           -- 同上；僅供分組校準，不影響評分
    calibration_id       INTEGER,        -- 當時採用的 calibrations.id；NULL = 預設門檻
    pe                   REAL,           -- 估值：只顯示與記錄，不參與評分
    pb                   REAL,
    dividend_yield       REAL,
    pe_percentile        REAL,           -- 相對自身近 3 年的百分位；歷史不足或虧損為 NULL
    pb_percentile        REAL,
    yield_percentile     REAL
);

CREATE TABLE IF NOT EXISTS calibrations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL,      -- 執行校準的日期
    bull_threshold   INTEGER NOT NULL,
    bear_threshold   INTEGER NOT NULL,
    train_n          INTEGER NOT NULL,   -- 剔除重疊後的前段筆數
    valid_n          INTEGER NOT NULL,
    train_metric     REAL NOT NULL,      -- 前段平均方向報酬 %
    valid_metric     REAL NOT NULL,      -- 後段平均方向報酬 %
    baseline_metric  REAL NOT NULL,      -- 後段「全判偏多」平均報酬 %
    current_metric   REAL,               -- 後段沿用舊門檻的平均方向報酬 %；無方向預測時 NULL
    adopted          INTEGER NOT NULL DEFAULT 0  -- 1 = 使用者以 --apply 核准
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,           -- 執行日
    start_date  TEXT NOT NULL,           -- 最早評估日
    end_date    TEXT NOT NULL,           -- 最晚評估日
    tickers     TEXT NOT NULL,           -- JSON array
    params      TEXT NOT NULL,           -- JSON：years、horizons、報告分組用門檻
    status      TEXT NOT NULL DEFAULT 'running',  -- running / complete
    skipped     TEXT NOT NULL DEFAULT '[]'        -- JSON：抓取或評分失敗而略過的標的與原因
);

CREATE TABLE IF NOT EXISTS backtest_samples (
    run_id          INTEGER NOT NULL,
    ticker          TEXT NOT NULL,
    as_of           TEXT NOT NULL,       -- 評估日（只用此日以前的資料評分）
    horizon_days    INTEGER NOT NULL,
    score           INTEGER NOT NULL,
    s_trend         INTEGER NOT NULL,
    s_bias          INTEGER NOT NULL,
    s_support       INTEGER NOT NULL,
    s_volume        INTEGER NOT NULL,
    s_macd          INTEGER NOT NULL,
    s_rsi           INTEGER NOT NULL,
    signal          TEXT NOT NULL,
    hard_rules      TEXT NOT NULL DEFAULT '[]',
    end_date        TEXT,                -- 對帳用的那根日線
    return_pct      REAL,                -- 還原價報酬；排除時 NULL
    excluded_reason TEXT,                -- NULL = 計入統計
    pe_percentile    REAL,               -- 評估日當時的估值百分位（只用當日以前的歷史）
    pb_percentile    REAL,
    yield_percentile REAL,
    entry_date               TEXT,       -- 可成交口徑：次一交易日開盤進場
    tradable_return_pct      REAL,       -- 可成交口徑報酬（扣手續費與證交稅）
    tradable_excluded_reason TEXT,       -- 可成交口徑排除原因；NULL = 計入
    flow_foreign_5d  REAL,               -- 法人因子：近 N 日淨買超 ÷ 成交股數（只用 as_of 以前）
    flow_foreign_20d REAL,
    flow_trust_5d    REAL,
    flow_trust_20d   REAL,
    PRIMARY KEY (run_id, ticker, as_of, horizon_days)
);

CREATE TABLE IF NOT EXISTS valuations (
    ticker         TEXT NOT NULL,
    date           TEXT NOT NULL,
    pe             REAL,                 -- 本益比；虧損或無資料為 NULL
    pb             REAL,                 -- 股價淨值比
    dividend_yield REAL,                 -- 殖利率 %
    fiscal_period  TEXT,                 -- 計算所用財報年/季（僅上市提供）
    source         TEXT NOT NULL,        -- BWIBBU_d / TPEX_PE
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS valuation_fetches (
    date    TEXT NOT NULL,
    market  TEXT NOT NULL,               -- TWSE / TPEx
    rows    INTEGER NOT NULL,            -- 0 = 休市日（只記已確定的過去日期）
    PRIMARY KEY (date, market)
);

CREATE TABLE IF NOT EXISTS institutional_flows (
    ticker      TEXT NOT NULL,
    date        TEXT NOT NULL,
    foreign_net INTEGER NOT NULL,        -- 外資買賣超股數（不含外資自營商）
    trust_net   INTEGER NOT NULL,        -- 投信
    dealer_net  INTEGER NOT NULL,        -- 自營商合計（自行買賣 + 避險）
    total_net   INTEGER NOT NULL,        -- 三大法人合計
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS flow_fetches (
    date    TEXT NOT NULL,
    market  TEXT NOT NULL,               -- TWSE / TPEx
    rows    INTEGER NOT NULL,            -- 0 = 休市日（只記已確定的過去日期）
    PRIMARY KEY (date, market)
);

CREATE INDEX IF NOT EXISTS idx_pred_status ON predictions(status, ticker);
"""


# 後加欄位：CREATE TABLE IF NOT EXISTS 不會替舊 DB 補欄位，需逐一 ALTER
ADDED_COLUMNS = {
    "predictions": (("market_state", "TEXT"), ("sector_quadrant", "TEXT"),
                    ("calibration_id", "INTEGER"), ("pe", "REAL"), ("pb", "REAL"),
                    ("dividend_yield", "REAL"), ("pe_percentile", "REAL"),
                    ("pb_percentile", "REAL"), ("yield_percentile", "REAL")),
    "backtest_samples": (("pe_percentile", "REAL"), ("pb_percentile", "REAL"),
                         ("yield_percentile", "REAL"), ("entry_date", "TEXT"),
                         ("tradable_return_pct", "REAL"), ("tradable_excluded_reason", "TEXT"),
                         ("flow_foreign_5d", "REAL"), ("flow_foreign_20d", "REAL"),
                         ("flow_trust_5d", "REAL"), ("flow_trust_20d", "REAL")),
    "dividends": (("sub_ratio", "REAL NOT NULL DEFAULT 0"),
                  ("sub_price", "REAL NOT NULL DEFAULT 0"), ("ref_ratio", "REAL")),
    "backtest_runs": (("status", "TEXT NOT NULL DEFAULT 'running'"),
                      ("skipped", "TEXT NOT NULL DEFAULT '[]'")),
}


def _migrate(conn):
    """冪等補上舊 DB 缺少的欄位，不動既有資料。"""
    for table, columns in ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(%s)" % table)}
        for column, column_type in columns:
            if column not in existing:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, column_type))
    conn.commit()


def connect(db_path=None):
    """開啟連線並確保 schema 存在。"""
    path = db_path or os.environ.get("STOCK_TRACKER_DB") or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn
