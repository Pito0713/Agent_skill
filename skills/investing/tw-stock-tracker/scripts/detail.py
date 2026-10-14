"""個股詳情：把價量、技術評分、估值、法人、月營收、財報、法說會、新聞彙整成一份 JSON。

所有數字都由這裡從 DB 計算（年增率、月增率、利潤率、單季 EPS），LLM 只能轉述與解讀，
不得自行補數字。基本面只顯示、不參與評分。

用法：
  python3 detail.py 2330             # 不更新資料，直接用 DB 現有的（新聞即時抓，不落庫）
  python3 detail.py 2330 --fetch     # 先更新日線、估值、法人、月營收、財報、法說會（寫入 DB，只在資料主機跑）
  python3 detail.py 2330 --no-news   # 不抓新聞
"""

import argparse
import contextlib
import json
import sys
from datetime import date, datetime, timedelta

import db
import fetch_events
import fetch_flows
import fetch_fundamentals
import fetch_twse
import fetch_valuation
import score as scoring
import track
import valuation as valuations

RETURN_WINDOWS = (1, 5, 20, 60)
FLOW_WINDOWS = (5, 20)
FLOW_COLUMNS = ("foreign_net", "trust_net", "dealer_net", "total_net")
REVENUE_HISTORY_MONTHS = 13
CONFERENCE_LOOKBACK_DAYS = 365   # 抓取只查今年與去年；窗口不可超過一年，否則年初會漏
REVENUE_BACKFILL_MONTHS = 13


def _pct(now, before):
    """基期 ≤ 0（金控月營收含投資損益，可能為負）時成長率沒有意義，不給。"""
    return round((now / before - 1) * 100, 2) if now is not None and before and before > 0 else None


def _window_return(conn, ticker, rows, adjusted, bars):
    """窗口內有金額未知的除權息時不給數字（同對帳的 needs_review），避免把除息缺口當成下跌。"""
    if len(rows) <= bars or track._exdiv_unknown_in_window(conn, ticker, rows[bars]["date"], rows[0]["date"]):
        return None
    return _pct(adjusted[0], adjusted[bars])


def price_section(conn, ticker):
    """近期還原報酬（1/5/20/60 根）與最近 20 根收盤。"""
    rows = conn.execute("SELECT date, close, adj_close FROM daily_quotes WHERE ticker = ?"
                        " ORDER BY date DESC LIMIT ?", (ticker, max(RETURN_WINDOWS) + 1)).fetchall()
    if not rows:
        return None
    adjusted = [r["adj_close"] or r["close"] for r in rows]
    unknown = track._exdiv_unknown_in_window(conn, ticker, rows[-1]["date"], rows[0]["date"])
    return {"date": rows[0]["date"], "close": rows[0]["close"],
            "returns_pct": {"%dd" % n: _window_return(conn, ticker, rows, adjusted, n) for n in RETURN_WINDOWS},
            "unknown_exdiv_dates": unknown,
            "recent_closes": [{"date": r["date"], "close": r["close"]} for r in rows[:20]][::-1]}


def flows_section(conn, ticker):
    """近 5／20 個交易日三大法人淨買賣超（張）。任一天兩個市場沒抓齊就不給該窗口。"""
    days = [r["date"] for r in conn.execute("SELECT date FROM daily_quotes WHERE ticker = ?"
                                            " ORDER BY date DESC LIMIT ?", (ticker, max(FLOW_WINDOWS)))]
    output = {}
    for window in FLOW_WINDOWS:
        window_days = days[:window]
        covered = len(window_days) == window and all(
            conn.execute("SELECT COUNT(*) FROM flow_fetches WHERE date = ? AND rows > 0", (day,)).fetchone()[0]
            == len(fetch_flows.MARKETS) for day in window_days)
        if not covered:
            output["%dd" % window] = None
            continue
        placeholders = ",".join("?" * window)
        sums = conn.execute("SELECT %s FROM institutional_flows WHERE ticker = ? AND date IN (%s)"
                            % (", ".join("COALESCE(SUM(%s), 0)" % c for c in FLOW_COLUMNS), placeholders),
                            (ticker, *window_days)).fetchone()
        output["%dd" % window] = {column.replace("_net", ""): round(value / 1000, 1)
                                  for column, value in zip(FLOW_COLUMNS, sums)}
    return output


def _revenue_item(row):
    return {"month": row["month"], "revenue": row["revenue"],
            "yoy_pct": _pct(row["revenue"], row["last_year_revenue"]),
            "mom_pct": _pct(row["revenue"], row["prev_month_revenue"]),
            "cum_yoy_pct": _pct(row["cum_revenue"], row["cum_last_year_revenue"]),
            "note": row["note"], "source": row["source"]}


def revenue_section(conn, ticker):
    rows = conn.execute("SELECT * FROM monthly_revenue WHERE ticker = ? ORDER BY month DESC LIMIT ?",
                        (ticker, REVENUE_HISTORY_MONTHS)).fetchall()
    if not rows:
        return None
    return {"unit": "千元", "latest": _revenue_item(rows[0]),
            "history": [_revenue_item(r) for r in rows][::-1]}


def _margin(part, whole):
    return round(part / whole * 100, 2) if part is not None and whole else None


def financials_section(conn, ticker):
    """最新一季（累計）。DB 有同年前一季時，相減得單季 EPS；有去年同期時算 EPS 年增。"""
    rows = conn.execute("SELECT * FROM quarterly_financials WHERE ticker = ? ORDER BY year DESC, quarter DESC",
                        (ticker,)).fetchall()
    if not rows:
        return None
    latest = rows[0]
    by_period = {(r["year"], r["quarter"]): r for r in rows}
    previous = by_period.get((latest["year"], latest["quarter"] - 1))
    last_year = by_period.get((latest["year"] - 1, latest["quarter"]))
    single_eps = (latest["eps"] if latest["quarter"] == 1
                  else round(latest["eps"] - previous["eps"], 2)
                  if previous and latest["eps"] is not None and previous["eps"] is not None else None)
    return {"unit": "千元", "basis": "年初至該季累計",
            "period": "%dQ%d" % (latest["year"], latest["quarter"]), "published": latest["published"],
            # 累計相減：期間股數有變動（增資、減資）時與官方單季 EPS 會有小差異
            "eps_cumulative": latest["eps"], "eps_quarter_approx": single_eps,
            "eps_cumulative_last_year": last_year["eps"] if last_year else None,
            "revenue": latest["revenue"], "operating_income": latest["operating_income"],
            "net_income": latest["net_income"],
            "operating_margin_pct": _margin(latest["operating_income"], latest["revenue"]),
            "net_margin_pct": _margin(latest["net_income"], latest["revenue"]),
            "periods_stored": len(rows)}


def conferences_section(conn, ticker, today):
    since = (today - timedelta(days=CONFERENCE_LOOKBACK_DAYS)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT date, end_date, time, location, summary, slides_zh, slides_en, website, fetched_at"
        " FROM investor_conferences WHERE ticker = ? AND date >= ? ORDER BY date DESC", (ticker, since))]


def _score_section(conn, ticker):
    try:
        return scoring.evaluate(conn, ticker), None
    except RuntimeError as error:
        return None, str(error)


def build(conn, ticker, include_news=True, today=None):
    """組出詳情 dict。各段缺資料為 None，原因列在 missing，不以猜測值補。"""
    today = today or date.today()
    evaluation, score_error = _score_section(conn, ticker)
    price = price_section(conn, ticker)
    # 日線不足而評分失敗時，估值仍可單獨顯示；完全沒有日線就以今天為基準（過舊判定改用日曆天）
    snapshot = (evaluation.pop("valuation") if evaluation
                else valuations.snapshot(conn, ticker, price["date"] if price else today.isoformat()))
    result = {"ticker": ticker, "name": scoring.lookup_name(conn, ticker),
              "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "price": price, "score": evaluation, "valuation": snapshot,
              "flows_lots": flows_section(conn, ticker), "revenue": revenue_section(conn, ticker),
              "financials": financials_section(conn, ticker),
              "conferences": conferences_section(conn, ticker, today), "news": None, "missing": [],
              "refreshed": refresh_status(conn, ticker)}
    reasons = {"price": "沒有日線（先跑 --fetch）", "valuation": "無估值（ETF、虧損或未抓）",
               "revenue": "沒有月營收（ETF 沒有；或先跑 --fetch）", "financials": "沒有財報（ETF 沒有；或先跑 --fetch）"}
    result["missing"] = ["%s：%s" % (key, reason) for key, reason in reasons.items() if result[key] is None]
    if result["refreshed"] is None:
        result["missing"].append("refreshed：從未用 --fetch 更新過，資料可能是其他流程順帶抓的")
    elif result["refreshed"]["failed_steps"]:
        result["missing"].append("refreshed：上次更新失敗的來源：%s" % "、".join(result["refreshed"]["failed_steps"]))
    if score_error:
        result["missing"].append("score：%s" % score_error)
    if price and price["unknown_exdiv_dates"]:
        result["missing"].append("price：%s 有除權息但查無金額，跨到這些日子的報酬不給" % "、".join(
            price["unknown_exdiv_dates"]))
    if not result["conferences"]:
        result["missing"].append("conferences：近 %d 天沒有法說會紀錄" % CONFERENCE_LOOKBACK_DAYS)
    if include_news and not result["name"]:
        # 只用代號查（如 ETF 沒有中文名稱）實測幾乎都是無關新聞，寧可不給
        result["missing"].append("news：沒有中文名稱，只用代號查新聞不可靠，未查")
    elif include_news:
        try:
            result["news"] = fetch_events.fetch_news(ticker, result["name"])
        except RuntimeError as error:
            result["missing"].append("news：%s" % error)
    return result


def record_refresh(conn, ticker, failed_steps):
    """記下這次更新：儀表板「個股詳情」區塊靠它列出查過的個股與更新時間。"""
    conn.execute("INSERT OR REPLACE INTO detail_views (ticker, refreshed_at, failed_steps) VALUES (?, ?, ?)",
                 (ticker, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(failed_steps, ensure_ascii=False)))
    conn.commit()


def refresh_status(conn, ticker):
    row = conn.execute("SELECT refreshed_at, failed_steps FROM detail_views WHERE ticker = ?", (ticker,)).fetchone()
    return {"at": row["refreshed_at"], "failed_steps": json.loads(row["failed_steps"])} if row else None


def refresh(conn, ticker):
    """更新詳情所需的資料並記錄。單一來源失敗只警告、不擋其他來源（詳情是彙整，不是單一判斷）。"""
    today = date.today()
    steps = (("日線", lambda: fetch_twse.sync_ticker(conn, ticker)),
             ("估值", lambda: fetch_valuation.sync_latest(conn, ticker)),
             ("法人", lambda: fetch_flows.backfill(conn, today - timedelta(days=fetch_flows.LATEST_DAYS), today)),
             ("月營收與財報", lambda: fetch_fundamentals.sync_latest(conn)),
             ("月營收歷史", lambda: fetch_fundamentals.backfill(
                 conn, fetch_fundamentals.recent_months(REVENUE_BACKFILL_MONTHS))),
             ("法說會", lambda: fetch_events.sync_conferences(conn, ticker)))
    failed = []
    for label, step in steps:
        try:
            # 各 fetch 的進度訊息印在 stdout，導到 stderr，stdout 只留 JSON
            with contextlib.redirect_stdout(sys.stderr):
                step()
        except RuntimeError as error:
            print("[warn] %s 更新失敗：%s" % (label, error), file=sys.stderr)
            failed.append(label)
    record_refresh(conn, ticker, failed)


def main():
    parser = argparse.ArgumentParser(description="個股詳情（JSON）")
    parser.add_argument("ticker")
    parser.add_argument("--fetch", action="store_true", help="先更新資料（寫入 DB，只在資料主機跑）")
    parser.add_argument("--no-news", action="store_true", help="不抓新聞")
    args = parser.parse_args()
    if not fetch_twse.TICKER_PATTERN.match(args.ticker):
        parser.error("代號格式不符：%s" % args.ticker)

    conn = db.connect()
    try:
        if args.fetch:
            refresh(conn, args.ticker)
        print(json.dumps(build(conn, args.ticker, include_news=not args.no_news), ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
