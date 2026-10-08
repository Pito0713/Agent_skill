"""全市場評分篩選：對全市場 DB 的每檔普通股跑同一套 score.evaluate，取前 N 名，
再依所屬產業的資金流向（tw-market-rotation 的成交比重變化）排序。

描述「目前技術面狀態最強的一批」，不是買進名單：回測顯示總分沒有可證實的預測力（ADR-026）。
全市場日線與逐檔日線的上櫃成交量有 1–2% 落差，--verify 會用逐檔資料（tracker.db）重抓重算前 N 名，
輸出以逐檔分數為準。

用法：
  python3 screen.py [--top 20] [--min-turnover 10000000] [--verify] [--json]
"""

import argparse
import importlib.util
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

import db
import fetch_market_daily
import fetch_twse
import score as scoring

COMMON_STOCK = re.compile(r"^[1-9][0-9]{3}$")   # 排除 ETF／ETN（00 開頭）、特別股、受益證券
MIN_TURNOVER = 10_000_000       # 20 日均成交金額（元），太冷門的股票指標雜訊大
TURNOVER_DAYS = 20
SECTORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "tw-market-rotation", "scripts", "sectors.py")


def latest_trading_day(conn):
    """兩個市場都有資料的最近一天；只抓到一個市場的日子不算，否則另一市場整批被排除。"""
    row = conn.execute("SELECT MAX(date) FROM (SELECT date FROM market_fetches WHERE rows > 0"
                       " GROUP BY date HAVING COUNT(*) = 2)").fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("全市場 DB 沒有資料：先跑 python3 fetch_market_daily.py sync")
    return row[0]


def recent_trading_days(conn, as_of, count):
    """as_of（含）以前、兩個市場都有資料的最近 count 個交易日；不足或中間有漏抓的日子回 None
    （漏抓會讓窗口往前延伸，算到的不是最近 count 個實際交易日）。"""
    days = [r[0] for r in conn.execute(
        "SELECT date FROM market_fetches WHERE rows > 0 AND date <= ? GROUP BY date"
        " HAVING COUNT(*) = 2 ORDER BY date DESC LIMIT ?", (as_of, count))]
    if len(days) < count:
        return None
    holidays = fetch_market_daily.confirmed_holidays(conn)
    if any(fetch_market_daily.has_unconfirmed_gap(holidays, earlier, later)
           for later, earlier in zip(days, days[1:])):
        return None
    return days


def average_turnovers(conn, days):
    """{代號: 近 N 個交易日的官方成交金額平均}。無成交（停牌）的日子算 0，避免拿更早的成交補位。
    任一天缺成交金額（舊版資料）的標的不列入，不用收盤價 × 量估算。"""
    rows = conn.execute(
        "SELECT ticker, SUM(turnover) total, COUNT(turnover) known, COUNT(*) bars FROM daily_quotes"
        " WHERE date IN (%s) GROUP BY ticker" % ",".join("?" * len(days)), days).fetchall()
    return {r["ticker"]: r["total"] / len(days) for r in rows if r["known"] == r["bars"]}


def universe(conn, as_of, min_turnover):
    """as_of 當天有成交、近 20 個交易日均成交金額達門檻的普通股。"""
    days = recent_trading_days(conn, as_of, TURNOVER_DAYS)
    if days is None:
        raise RuntimeError("全市場 DB 近 %d 個交易日不完整（不足或有漏抓），先跑 fetch_market_daily.py sync"
                           % TURNOVER_DAYS)
    turnovers = average_turnovers(conn, days)
    traded = {r["ticker"] for r in conn.execute("SELECT ticker FROM daily_quotes WHERE date = ?", (as_of,))}
    return [(ticker, turnovers[ticker]) for ticker in sorted(traded)
            if COMMON_STOCK.match(ticker) and ticker in turnovers and turnovers[ticker] >= min_turnover]


def score_universe(conn, candidates, as_of):
    results = []
    for ticker, turnover in candidates:
        try:
            result = scoring.evaluate(conn, ticker, as_of=as_of)
        except RuntimeError:
            continue   # 日線不足 60 根（新上市）
        result["avg_turnover"] = turnover
        results.append(result)
    return results


def top_n(results, count):
    """依最終分數由高到低取前 count 名；同分以代號排序，另回傳與第 count 名同分而落選的檔數。"""
    ranked = sorted(results, key=lambda r: (-r["final_score"], r["ticker"]))
    chosen = ranked[:count]
    if not chosen:
        return [], 0
    cutoff = chosen[-1]["final_score"]
    left_out = sum(1 for r in ranked[count:] if r["final_score"] == cutoff)
    return chosen, left_out


def _sector_names():
    """產業代碼 → 名稱，取自 tw-market-rotation；未安裝時回空 dict，只顯示代碼。"""
    if not os.path.exists(SECTORS_PATH):
        return {}
    spec = importlib.util.spec_from_file_location("rotation_sectors", SECTORS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {code: names[0] for code, names in module.INDUSTRIES.items()}


def sector_flows(tracker_conn, as_of):
    if tracker_conn is None:
        return {}, None
    return _sector_flows(tracker_conn, as_of)


def _sector_flows(tracker_conn, as_of):
    """{產業代碼: (排名, share_delta, 象限)} 與資料日期；rotation 契約表不存在回 ({}, None)。

    排名依成交比重變化由大到小：正值代表近 5 日資金比重高於 20 日平均。
    """
    present = {r["name"] for r in tracker_conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "sector_context" not in present:
        return {}, None
    flow_date = tracker_conn.execute("SELECT MAX(date) FROM sector_context WHERE date <= ?"
                                     " AND share_delta IS NOT NULL", (as_of,)).fetchone()[0]
    if flow_date is None:
        return {}, None
    rows = tracker_conn.execute(
        "SELECT industry_code, share_delta, quadrant FROM sector_context WHERE date = ?"
        " AND share_delta IS NOT NULL ORDER BY share_delta DESC", (flow_date,)).fetchall()
    return ({r["industry_code"]: (rank, r["share_delta"], r["quadrant"])
             for rank, r in enumerate(rows, 1)}, flow_date)


def open_tracker_readonly():
    """讀 rotation 契約表與校準門檻用；不建表、不 migrate，避免一般篩選也寫入 tracker.db。
    tracker.db 為預設的 rollback journal 模式；若改成 WAL，唯讀連線仍可能建立 -shm 檔。"""
    path = os.environ.get("STOCK_TRACKER_DB") or db.DEFAULT_DB_PATH
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def sync_calibrations(market_conn, tracker_conn):
    """把 tracker.db 的校準門檻複製到全市場 DB：硬規則以 bull − 1 壓分，門檻不同會改變前 N 名。"""
    rows = [] if tracker_conn is None else [tuple(r) for r in tracker_conn.execute(
        "SELECT id, created_at, bull_threshold, bear_threshold, train_n, valid_n, train_metric,"
        " valid_metric, baseline_metric, current_metric, adopted FROM calibrations")]
    market_conn.execute("DELETE FROM calibrations")
    market_conn.executemany("INSERT INTO calibrations (id, created_at, bull_threshold, bear_threshold,"
                            " train_n, valid_n, train_metric, valid_metric, baseline_metric,"
                            " current_metric, adopted) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    market_conn.commit()


def verify_with_tracker(tracker_conn, chosen, as_of):
    """用逐檔資料重抓、以同一個 as_of 重算。回傳 {代號: 逐檔評分結果或錯誤字串}。"""
    print("以逐檔資料覆核前 %d 名（每檔約 20 秒）" % len(chosen), file=sys.stderr, flush=True)
    verified = {}
    for result in chosen:
        ticker = result["ticker"]
        try:
            fetch_twse.sync_ticker(tracker_conn, ticker)
            result_now = scoring.evaluate(tracker_conn, ticker, as_of=as_of)
            verified[ticker] = (result_now if result_now["date"] == as_of
                                else "逐檔資料沒有 %s 的日線（最新 %s）" % (as_of, result_now["date"]))
        except RuntimeError as error:
            verified[ticker] = str(error)
    return verified


def build_rows(market_conn, chosen, flows, verified):
    """合併評分、產業資金流向與覆核結果，依產業資金流向排名排序（無產業資料者排最後）。"""
    names = _sector_names()
    rows = []
    for result in chosen:
        info = market_conn.execute("SELECT name, market, industry_code FROM securities WHERE ticker = ?",
                                   (result["ticker"],)).fetchone()
        code = info["industry_code"] if info else None
        flow_rank, share_delta, quadrant = flows.get(code, (None, None, None))
        canonical = verified.get(result["ticker"])
        final = canonical if isinstance(canonical, dict) else result
        rows.append({
            "ticker": result["ticker"], "name": info["name"] if info else None,
            "market": info["market"] if info else None, "industry_code": code,
            "industry": names.get(code, code), "flow_rank": flow_rank,
            "share_delta_pp": None if share_delta is None else round(share_delta * 100, 2),
            "quadrant": quadrant, "screen_score": result["final_score"],
            "score": final["final_score"], "signal": final["signal"], "parts": final["parts"],
            "entry_status": final["entry_status"], "bias20_pct": final["indicators"]["bias20_pct"],
            "hard_rules": final["hard_rules"], "flags": final["flags"], "close": final["close"],
            "entry_low": final["entry_low"], "entry_high": final["entry_high"],
            "stop_loss": final["stop_loss"], "date": final["date"],
            "avg_turnover": round(result["avg_turnover"]),
            "verified": None if canonical is None else
            (canonical if isinstance(canonical, str) else canonical["final_score"] == result["final_score"]),
        })
    return sorted(rows, key=lambda r: (r["flow_rank"] is None, r["flow_rank"] or 0, -r["score"]))


def print_table(summary, rows):
    print("=== 全市場評分前 %(top)d 名（%(as_of)s；%(universe)d 檔符合流動性，%(scored)d 檔可評分）===" % summary)
    print("產業資金流向：%s（成交比重變化，5 日均 − 20 日均）" % (summary["flow_date"] or "無資料"))
    if summary["ties_left_out"]:
        print("⚠️  另有 %d 檔與第 %d 名同分，依代號排序後落選" % (summary["ties_left_out"], summary["top"]))
    for r in rows:
        print("%-3s %-6s %-8s %-8s 比重變化 %s %-9s 分數 %3d %-4s %-6s 乖離 %+6.2f%% %s"
              % (r["flow_rank"] or "-", r["ticker"], r["name"] or "", r["industry"] or "無產業",
                 "—" if r["share_delta_pp"] is None else "%+.2fpp" % r["share_delta_pp"],
                 r["quadrant"] or "", r["score"], r["signal"], r["entry_status"], r["bias20_pct"],
                 "、".join(r["hard_rules"])))
    print("⚠️  技術面狀態描述，非買進名單；回測顯示總分沒有可證實的預測力（ADR-026）。")


def positive_int(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("必須是正整數，收到 %s" % text)
    return value


def non_negative(text):
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("必須是非負數，收到 %s" % text)
    return value


def main():
    parser = argparse.ArgumentParser(description="全市場評分篩選，依產業資金流向排序")
    parser.add_argument("--top", type=positive_int, default=20)
    parser.add_argument("--min-turnover", type=non_negative, default=MIN_TURNOVER,
                        help="20 日均成交金額門檻（元）")
    parser.add_argument("--verify", action="store_true", help="以逐檔資料重抓重算前 N 名")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    market_conn, tracker_conn = db.connect_market(), open_tracker_readonly()
    try:
        as_of = latest_trading_day(market_conn)
        sync_calibrations(market_conn, tracker_conn)
        candidates = universe(market_conn, as_of, args.min_turnover)
        results = score_universe(market_conn, candidates, as_of)
        chosen, ties = top_n(results, args.top)
        flows, flow_date = sector_flows(tracker_conn, as_of)
        verified = {}
        if args.verify:   # 覆核才需要寫入 tracker.db（逐檔日線），另開可寫連線
            writable = db.connect()
            try:
                verified = verify_with_tracker(writable, chosen, as_of)
            finally:
                writable.close()
        rows = build_rows(market_conn, chosen, flows, verified)
        summary = {"as_of": as_of, "top": args.top, "universe": len(candidates), "scored": len(results),
                   "ties_left_out": ties, "flow_date": flow_date}
        if args.json:
            print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
        else:
            print_table(summary, rows)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        market_conn.close()
        if tracker_conn is not None:
            tracker_conn.close()


if __name__ == "__main__":
    main()
