"""儀表板的資料層：只讀 DB 與 log，組出各區塊要顯示的數字。不產生 HTML、不寫入任何東西。

所有數字都來自既有 script 的同一套計算（score.evaluate、calibrate、backtest_stats），
儀表板只是換一種呈現方式，不另做一套口徑。
"""

import glob
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import backtest_report
import backtest_stats
import calibrate
import db
import detail as stock_details
import positions as holdings
import score as scoring
import track

LOG_DIR = os.path.expanduser("~/.stock-tracker/logs")
RECENT_LOG_FILES = 7
END_LINE = re.compile(r"^== (\S+ \S+) 結束 status=(\d+)")
SKIP_LINE = re.compile(r"^== (\S+ \S+) 另一個更新仍在執行")


def connect_readonly(path=None):
    """唯讀連線：儀表板只看不寫。DB 不存在時拋 RuntimeError（唯讀模式不會自動建檔）。"""
    path = path or os.environ.get("STOCK_TRACKER_DB") or db.DEFAULT_DB_PATH
    if not os.path.exists(path):
        raise RuntimeError("找不到資料庫：%s" % path)
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _unrealized_return(conn, ticker, created_at, latest):
    """建立日收盤到最新收盤的還原報酬 %，口徑同 track 對帳（兩端都讀現行還原價）。

    持有期間有金額未知的除權息時呼叫端不算（同對帳的 needs_review），避免把未還原的除息缺口顯示成虧損。
    """
    start = conn.execute("SELECT close, adj_close FROM daily_quotes WHERE ticker = ? AND date = ?",
                         (ticker, created_at)).fetchone()
    if start is None:
        return None
    return ((latest["adj_close"] / (start["adj_close"] or start["close"])) - 1) * 100


def open_predictions(conn):
    """open 預測逐筆：當時判斷、以最新資料重算的現況、到期日、浮動報酬、估值百分位。"""
    today = date.today()
    output = []
    for row in conn.execute("SELECT * FROM predictions WHERE status = 'open' ORDER BY created_at, ticker"):
        due = date.fromisoformat(row["created_at"]) + timedelta(days=row["horizon_days"])
        item = {"id": row["id"], "ticker": row["ticker"], "created_at": row["created_at"],
                "due": due.isoformat(), "days_left": (due - today).days,
                "score_then": row["score"], "signal_then": row["signal"], "thesis": row["thesis"],
                "now": None, "error": None}
        try:
            now = scoring.evaluate(conn, row["ticker"])
        except RuntimeError as error:
            item["error"] = str(error)
        else:
            item["now"] = now
            item["exdiv_unknown"] = bool(track._exdiv_unknown_in_window(conn, row["ticker"], row["created_at"],
                                                                       now["date"]))
            item["unrealized"] = (None if item["exdiv_unknown"]
                                  else _unrealized_return(conn, row["ticker"], row["created_at"], now))
        item["name"] = scoring.lookup_name(conn, row["ticker"])
        output.append(item)
    # 依最新重算分數高到低；同分維持建立日順序（sort 穩定），算不出分數的排最後
    output.sort(key=lambda item: -item["now"]["final_score"] if item["now"] else float("inf"))
    return output


def stock_detail(conn, ticker):
    """個股詳情（不抓新聞）。沒跑過 --fetch 的個股、或舊 DB 尚未建表（唯讀連線不會自動建）拋 LookupError。"""
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    missing = {"monthly_revenue", "quarterly_financials", "investor_conferences", "detail_views"} - tables
    if missing:
        raise LookupError("尚未建立個股詳情資料")
    # 只有使用者跑過 --fetch 的個股才有詳情頁，其他代號一律當不存在
    if not conn.execute("SELECT 1 FROM detail_views WHERE ticker = ?", (ticker,)).fetchone():
        raise LookupError("%s 沒有個股詳情" % ticker)
    return stock_details.build(conn, ticker, include_news=False)


def detail_views(conn):
    """查過詳情的個股：更新時間與各資料來源的最新日期，最近更新的在前。舊 DB 沒這張表回空清單。"""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'detail_views'").fetchone()
    if not exists:
        return []
    output = []
    for row in conn.execute("SELECT * FROM detail_views ORDER BY refreshed_at DESC, ticker"):
        ticker = row["ticker"]
        financial = conn.execute("SELECT year, quarter FROM quarterly_financials WHERE ticker = ?"
                                 " ORDER BY year DESC, quarter DESC LIMIT 1", (ticker,)).fetchone()
        output.append({
            "ticker": ticker, "name": scoring.lookup_name(conn, ticker), "refreshed_at": row["refreshed_at"],
            "age_days": (date.today() - date.fromisoformat(row["refreshed_at"][:10])).days,
            "failed_steps": json.loads(row["failed_steps"]),
            "quote_date": conn.execute("SELECT MAX(date) FROM daily_quotes WHERE ticker = ?", (ticker,)).fetchone()[0],
            "revenue_month": conn.execute("SELECT MAX(month) FROM monthly_revenue WHERE ticker = ?",
                                          (ticker,)).fetchone()[0],
            "financial_period": "%dQ%d" % (financial["year"], financial["quarter"]) if financial else None})
    return output


def open_positions(conn):
    """使用者持股現況；舊 DB 尚未建 positions 表（唯讀連線不會自動建）時回空清單。"""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'positions'").fetchone()
    return holdings.open_positions(conn) if exists else []


def resolved_summary(conn):
    """已對帳：整體方向命中率、分數分層、最近 10 筆明細、校準樣本進度。"""
    rows = calibrate.resolved_rows(conn)
    directional = [r for r in rows if r["hit"] is not None]
    passed, count, weeks = calibrate.gate_status(rows)
    status_counts = {r["status"]: r["c"] for r in conn.execute(
        "SELECT status, COUNT(*) c FROM predictions GROUP BY status")}
    return {
        "total": len(rows), "directional": len(directional),
        "hit_rate": (sum(r["hit"] for r in directional) / len(directional) * 100) if directional else None,
        "buckets": backtest_report.bucket_stats(rows) if rows else [],
        # rows 依建立日排序；不同持有期混在一起時，最近對帳要改依對帳日排
        "recent": [dict(r) for r in sorted(rows, key=lambda r: (r["resolve_date"] or "", r["id"]))[-10:]][::-1],
        "status_counts": status_counts,
        "gate": {"passed": passed, "resolved": count, "weeks": weeks,
                 "min_resolved": calibrate.MIN_RESOLVED, "min_weeks": calibrate.MIN_WEEKS},
        "thresholds": scoring.load_thresholds(conn),
    }


def _horizon_summary(samples, horizon):
    rows = backtest_report.tradable_rows(samples)
    if not rows:
        return {"horizon": horizon, "n": 0}
    summary = backtest_stats.summarize_ic(backtest_stats.weekly_ic(rows, "score", "tradable_return_pct"),
                                          horizon)
    return {"horizon": horizon, "n": len(rows),
            "tradable_mean": sum(r["tradable_return_pct"] for r in rows) / len(rows),
            "ic": summary, "verdict": backtest_stats.verdict(summary)}


def backtest_runs(conn, cache):
    """每個跑完的回測：標的數、期間、各持有期的可成交平均與 Rank IC。結果依 run id 快取（run 跑完即不變）。"""
    output = []
    for run in conn.execute("SELECT * FROM backtest_runs WHERE status = 'complete' ORDER BY id DESC"):
        if run["id"] not in cache:
            params = json.loads(run["params"])
            cache[run["id"]] = [_horizon_summary(backtest_report.load_samples(conn, run["id"], horizon), horizon)
                                for horizon in params["horizons"]]
        output.append({"id": run["id"], "created_at": run["created_at"], "start": run["start_date"],
                       "end": run["end_date"], "tickers": len(json.loads(run["tickers"])),
                       "skipped": len(json.loads(run["skipped"])), "horizons": cache[run["id"]]})
    return output


def _parse_log(path):
    """單日 log：最後一次結束狀態、失敗行、略過次數。"""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    ends = [END_LINE.match(line) for line in lines]
    ends = [m for m in ends if m]
    return {"date": os.path.basename(path)[7:15], "runs": len(ends),
            "last_end": ends[-1].group(1) if ends else None,
            "last_status": int(ends[-1].group(2)) if ends else None,
            "failures": [line for line in lines if line.startswith("!!")],
            "skips": sum(1 for line in lines if SKIP_LINE.match(line))}


def schedule_status(log_dir=LOG_DIR):
    """最近幾天的排程 log 摘要；沒有 log 資料夾回空清單。"""
    paths = sorted(glob.glob(os.path.join(log_dir, "update-*.log")), reverse=True)[:RECENT_LOG_FILES]
    return [_parse_log(path) for path in paths]


def freshness(conn):
    """資料新鮮度：最新日線、最新估值、DB 大小。"""
    latest_quote = conn.execute("SELECT MAX(date) FROM daily_quotes").fetchone()[0]
    latest_valuation = conn.execute("SELECT MAX(date) FROM valuations").fetchone()[0]
    path = os.environ.get("STOCK_TRACKER_DB") or db.DEFAULT_DB_PATH
    return {"latest_quote": latest_quote, "latest_valuation": latest_valuation,
            "db_mb": os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else None,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
