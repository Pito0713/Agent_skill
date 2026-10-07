"""歷史重演回測：每週最後一個交易日只用當天以前的資料評分，再用之後 7/14/30 天的還原價對帳。

描述的是「這套評分過去的表現」，不是預測。結果存 backtest_* 表，不進 predictions，
也不餵給 calibrate：標的是現在挑的（選股偏差），各週的報酬窗口互相重疊，
都會讓結果比真實預測樂觀。

用法：
  python3 backtest.py run [--years 3] [--tickers 2330 2317] [--no-fetch]
  python3 backtest.py report [--horizon 30] [--run ID]
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta

import backtest_report
import db
import fetch_twse
import score as scoring
import track

HORIZONS = (7, 14, 30)
WARMUP_MONTHS = 4       # MIN_BARS 60 根約 3 個月，多抓 1 個月緩衝
MAX_ROLL_DAYS = 7       # 對帳日晚於到期日超過此天數（長期停牌或資料缺口）即排除
PART_COLUMNS = ("trend", "bias", "support", "volume", "macd", "rsi")


def shift_month(month, delta):
    """'202301' 加減月數。"""
    index = int(month[:4]) * 12 + int(month[4:]) - 1 + delta
    return "%04d%02d" % (index // 12, index % 12 + 1)


def month_span(first, last):
    """含頭尾的連續 'YYYYMM' 清單。"""
    months = [first]
    while months[-1] < last:
        months.append(shift_month(months[-1], 1))
    return months


def history_blocks(cached_months, need_from, current):
    """要補抓的月份區段，每段連續（TPEx 靠相鄰日收盤差偵測除權息）。

    - 往前延伸：抓到最早快取月為止。那個月的首日當初沒有前收可比，除權息標記不可信，順便重抓
    - 往後：從需要範圍內第一個缺月的前一個月（沒有缺月則最後快取月）抓到當月。
      缺口前那個月可能是當初抓到一半的月份，重抓才能讓下一段拿到正確前收
    兩段不重疊；各段第一根的前收由 sync_months 從 DB 讀。
    """
    if not cached_months:
        return [month_span(need_from, current)]
    first, last = min(cached_months), max(cached_months)
    blocks = []
    if need_from < first:
        blocks.append(month_span(need_from, first))
    holes = [m for m in month_span(max(first, need_from), last) if m not in cached_months]
    resume = shift_month(holes[0], -1) if holes else last
    if blocks and resume <= blocks[-1][-1]:
        resume = shift_month(blocks[-1][-1], 1)
    if resume <= current:
        blocks.append(month_span(resume, current))
    return blocks


def ensure_history(conn, ticker, start_date):
    cached = {row[0].replace("-", "") for row in conn.execute(
        "SELECT DISTINCT substr(date, 1, 7) FROM daily_quotes WHERE ticker = ?", (ticker,))}
    need_from = shift_month(start_date.strftime("%Y%m"), -WARMUP_MONTHS)
    blocks = history_blocks(cached, need_from, date.today().strftime("%Y%m"))
    for months in blocks:
        summary = fetch_twse.sync_months(conn, ticker, months)
        if summary["unadjusted_exdiv"]:
            print("  [warn] %s 除權息金額未知：%s" % (ticker, ", ".join(summary["unadjusted_exdiv"])),
                  file=sys.stderr)


def weekly_dates(conn, ticker, start, end):
    """每個 ISO 週的最後一個交易日。每週只取一天，避免相鄰日的報酬窗口幾乎完全重疊。"""
    last_by_week = {}
    for row in conn.execute("SELECT date FROM daily_quotes WHERE ticker = ? AND date BETWEEN ? AND ?"
                            " ORDER BY date", (ticker, start, end)):
        week = datetime.strptime(row["date"], "%Y-%m-%d").isocalendar()[:2]
        last_by_week[week] = row["date"]
    return sorted(last_by_week.values())


def forward_return(conn, ticker, as_of, horizon):
    """回傳 (end_date, return_pct, excluded_reason)；尚未到期回 None。口徑同 track 對帳。"""
    due = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=horizon)).strftime("%Y-%m-%d")
    end = track._first_quote_on_or_after(conn, ticker, due)
    if end is None:
        # 市場資料已過到期日夠久卻沒有這檔的行情 → 停牌或下市，算排除而非未到期
        latest = conn.execute("SELECT MAX(date) FROM daily_quotes").fetchone()[0]
        overdue = (datetime.strptime(latest, "%Y-%m-%d")
                   - datetime.strptime(due, "%Y-%m-%d")).days > MAX_ROLL_DAYS
        return (None, None, "no_quote_near_due") if overdue else None
    rolled = (datetime.strptime(end["date"], "%Y-%m-%d")
              - datetime.strptime(due, "%Y-%m-%d")).days
    if rolled > MAX_ROLL_DAYS:
        return end["date"], None, "no_quote_near_due"
    if track._exdiv_unknown_in_window(conn, ticker, as_of, end["date"]):
        return end["date"], None, "unknown_exdiv_in_window"
    start = conn.execute("SELECT close, adj_close FROM daily_quotes WHERE ticker = ? AND date = ?",
                         (ticker, as_of)).fetchone()
    adj_start = start["adj_close"] or start["close"]
    adj_end = end["adj_close"] or end["close"]
    return end["date"], round((adj_end / adj_start - 1.0) * 100, 4), None


def score_one_date(conn, run_id, ticker, as_of):
    """評一個評估日並寫入各期間樣本。回傳寫入筆數；資料不足 60 根回 0。"""
    try:
        result = scoring.evaluate(conn, ticker, as_of=as_of)
    except RuntimeError:
        return 0
    lookback_flag = "unknown_exdiv_in_lookback" if result["flags"] else None
    written = 0
    for horizon in HORIZONS:
        outcome = forward_return(conn, ticker, as_of, horizon)
        if outcome is None:
            continue
        end_date, return_pct, excluded = outcome
        excluded = lookback_flag or excluded
        conn.execute(
            "INSERT OR REPLACE INTO backtest_samples (run_id, ticker, as_of, horizon_days, score,"
            " s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, hard_rules,"
            " end_date, return_pct, excluded_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, ticker, as_of, horizon, result["final_score"],
             *(result["parts"][name] for name in PART_COLUMNS), result["signal"],
             json.dumps(result["hard_rules"], ensure_ascii=False), end_date,
             None if excluded else return_pct, excluded))
        written += 1
    return written


def default_tickers(conn):
    return [row["ticker"] for row in
            conn.execute("SELECT DISTINCT ticker FROM daily_quotes ORDER BY ticker")]


def cmd_run(conn, args):
    tickers = args.tickers or default_tickers(conn)
    if not tickers:
        raise RuntimeError("沒有任何標的：先用 fetch_twse.py 抓過，或以 --tickers 指定")
    start = date.today() - timedelta(days=round(args.years * 365))
    thresholds = scoring.load_thresholds(conn)
    cursor = conn.execute(
        "INSERT INTO backtest_runs (created_at, start_date, end_date, tickers, params)"
        " VALUES (?, ?, ?, ?, ?)",
        (date.today().isoformat(), start.isoformat(), date.today().isoformat(), json.dumps(tickers),
         json.dumps({"years": args.years, "horizons": HORIZONS, "bull": thresholds["bull"],
                     "bear": thresholds["bear"]})))
    run_id = cursor.lastrowid
    conn.commit()
    # 先全部抓完再評分：forward_return 以 DB 最新日期判斷「逾期無行情」，
    # 邊抓邊評會讓結果隨標的處理順序而變
    skipped = []
    if not args.no_fetch:
        for index, ticker in enumerate(tickers, 1):
            print("抓取 [%d/%d] %s" % (index, len(tickers), ticker), flush=True)
            _attempt(conn, skipped, ticker, lambda: ensure_history(conn, ticker, start))
    failed = {item["ticker"] for item in skipped}
    for index, ticker in enumerate(tickers, 1):
        if ticker in failed:
            continue
        outcome = _attempt(conn, skipped, ticker,
                           lambda: score_ticker(conn, run_id, ticker, start))
        if outcome:
            print("評分 [%d/%d] %s：%d 個評估週、%d 筆樣本" % (index, len(tickers), ticker,
                                                     outcome[1], outcome[0]), flush=True)
    conn.execute("UPDATE backtest_runs SET status = 'complete', skipped = ? WHERE id = ?",
                 (json.dumps(skipped, ensure_ascii=False), run_id))
    conn.commit()
    print("回測完成：run %d，略過 %d 檔。看結果：python3 backtest.py report" % (run_id, len(skipped)))


def _attempt(conn, skipped, ticker, action):
    """執行單一標的的步驟；RuntimeError 記入 skipped 並回 None，不中斷整個 run。"""
    try:
        return action()
    except RuntimeError as error:
        conn.rollback()
        skipped.append({"ticker": ticker, "reason": str(error)})
        print("  %s：略過（%s）" % (ticker, error), flush=True)
        return None


def score_ticker(conn, run_id, ticker, start):
    """單一標的逐週評分。回傳 (樣本筆數, 評估週數)。零樣本拋 RuntimeError。"""
    dates = weekly_dates(conn, ticker, start.isoformat(), date.today().isoformat())
    written = sum(score_one_date(conn, run_id, ticker, as_of) for as_of in dates)
    conn.commit()
    if not written:
        raise RuntimeError("沒有任何可用樣本（評估期內日線不足 60 根或無資料）")
    return written, len(dates)


def main():
    parser = argparse.ArgumentParser(description="台股評分歷史重演回測")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="抓歷史資料並重演評分")
    run.add_argument("--years", type=float, default=3, help="回測年數，預設 3")
    run.add_argument("--tickers", nargs="+", help="預設為 DB 中已有日線的全部標的")
    run.add_argument("--no-fetch", action="store_true", help="只用已快取資料，不抓網路")
    report = sub.add_parser("report", help="輸出分組表現與逐季趨勢")
    report.add_argument("--horizon", type=int, choices=HORIZONS, default=30, help="逐季趨勢用的期間")
    report.add_argument("--run", type=int, help="預設為最新一次 run")

    args = parser.parse_args()
    conn = db.connect()
    try:
        {"run": cmd_run, "report": backtest_report.cmd_report}[args.command](conn, args)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
