"""TWSE 盤後資料抓取：日線 OHLCV、除權息事件、還原股價計算。

資料源（皆免金鑰）：
  - STOCK_DAY   : 個股單月日線。漲跌價差欄位的 "X" 前綴 = 該日除權息（TWSE 不計算漲跌）。
  - TWT48U_ALL  : 除權除息預告表。只涵蓋「滾動未來約 5 週」，故僅前瞻窗口有配息金額。
  - TWT49U      : 除權除息計算結果表（歷史）。預告表查不到的除權息日由它補，見 fetch_exright。

還原股價：參考價 = (前收盤 - 現金股利 + 認購價 × 增資率) / (1 + 配股率 + 增資率)，往前累乘 factor。
  公式出自 TWSE 除權除息參考價試算頁（announcement/ex-right/cal.html）。
偵測得到除權息日但查不到金額時，adj_close 留 NULL 並由呼叫端標記，
不猜數字——錯誤的還原價會讓 track record 統計失真。

上櫃股不在 STOCK_DAY，sync_ticker 查無資料時改走 fetch_tpex。
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

import db
import fetch_exright
import fetch_tpex

STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
DIVIDEND_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
USER_AGENT = "Mozilla/5.0 (compatible; tw-stock-tracker/1.0)"
REQUEST_GAP_SEC = 3.0  # TWSE 對密集請求會擋，月份之間強制間隔
# 普通股 4 碼、ETF/債券 ETF 可達 6 碼含英文尾碼（00710B、00994A、01004T）
TICKER_PATTERN = re.compile(r"^[0-9]{4}[0-9A-Z]{0,2}$")


def _get_json(url, retries=3):
    """取回 JSON，失敗時退避重試。逾重試次數則拋出，不回傳半成品。"""
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError("TWSE 請求失敗 %s: %s" % (url, last_error))


def roc_to_iso(roc_date):
    """民國日期 '115/06/01' -> '2026-06-01'。"""
    year, month, day = roc_date.strip().split("/")
    return "%04d-%s-%s" % (int(year) + 1911, month, day)


def _to_float(raw):
    text = raw.replace(",", "").strip()
    return float(text) if text and text not in ("--", "---") else None


def parse_stock_day(payload):
    """把 STOCK_DAY 回應轉成 dict list；跳過缺價的停牌日。"""
    rows = []
    for row in payload.get("data") or []:
        close = _to_float(row[6])
        if close is None:
            continue
        rows.append({
            "date": roc_to_iso(row[0]),
            "open": _to_float(row[3]),
            "high": _to_float(row[4]),
            "low": _to_float(row[5]),
            "close": close,
            "volume": int(row[1].replace(",", "").strip() or 0),
            "is_exdiv": 1 if "X" in row[7].upper() else 0,
        })
    return rows


def fetch_months(ticker, months):
    """抓取指定月份清單（['202606', ...]）的日線。"""
    all_rows = []
    for index, month in enumerate(months):
        if index:
            time.sleep(REQUEST_GAP_SEC)
        payload = _get_json("%s?response=json&date=%s01&stockNo=%s" % (STOCK_DAY_URL, month, ticker))
        if payload.get("stat") != "OK":
            # 未來月份或無交易資料會回非 OK，屬正常情形，略過但不靜默失敗
            print("  [warn] %s %s: %s" % (ticker, month, payload.get("stat")), file=sys.stderr)
            continue
        all_rows.extend(parse_stock_day(payload))
    return all_rows


def recent_months(count, end_date=None):
    """回傳最近 count 個月的 'YYYYMM' 清單（含當月），由舊到新。"""
    cursor = end_date or date.today()
    months = []
    for _ in range(count):
        months.append(cursor.strftime("%Y%m"))
        cursor = cursor.replace(day=1) - timedelta(days=1)
    return list(reversed(months))


def save_quotes(conn, ticker, rows):
    conn.executemany(
        "INSERT OR REPLACE INTO daily_quotes"
        " (ticker, date, open, high, low, close, volume, is_exdiv, adj_close)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(ticker, r["date"], r["open"], r["high"], r["low"], r["close"],
          r["volume"], r["is_exdiv"]) for r in rows],
    )
    conn.commit()


def _subscription_price(raw):
    """認購價。未公告時 TWSE 回「尚未公告」等文字，回傳 None 而非 0——
    當 0 算會把參考價壓低成看似合理的錯數字。"""
    try:
        return _to_float(raw or "")
    except ValueError:
        return None


def parse_dividend_row(row):
    """TWT48U_ALL 單列 -> dividends 欄位 tuple；無事件或金額未定者回 None（維持「金額未知」）。"""
    cash = _to_float(row.get("CashDividend") or "") or 0.0
    # 原始值已是每股配股數（實測興泰 0.5 元配股回 0.04999999），不可再除 1000
    stock_ratio = _to_float(row.get("StockDividendRatio") or "") or 0.0
    sub_ratio = _to_float(row.get("SubscriptionRatio") or "") or 0.0
    sub_price = _subscription_price(row.get("SubscriptionPricePerShare")) if sub_ratio else 0.0
    if not sub_price and sub_ratio:
        return None
    if cash == 0.0 and stock_ratio == 0.0 and sub_ratio == 0.0:
        return None
    raw_date = (row.get("Date") or "").strip()
    if len(raw_date) != 7:
        return None
    ex_date = "%04d-%s-%s" % (int(raw_date[:3]) + 1911, raw_date[3:5], raw_date[5:7])
    return (row["Code"].strip(), ex_date, cash, stock_ratio, sub_ratio, sub_price, "TWT48U_ALL")


def sync_dividends(conn):
    """抓除權息預告表存入 dividends。回傳寫入筆數。"""
    records = [r for r in map(parse_dividend_row, _get_json(DIVIDEND_URL)) if r]
    # upsert 而非 REPLACE：REPLACE 會整列重建，清掉 TWT49U 補上的官方 ref_ratio
    conn.executemany(
        "INSERT INTO dividends"
        " (ticker, ex_date, cash, stock_ratio, sub_ratio, sub_price, source)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(ticker, ex_date) DO UPDATE SET cash = excluded.cash,"
        " stock_ratio = excluded.stock_ratio, sub_ratio = excluded.sub_ratio,"
        " sub_price = excluded.sub_price, source = excluded.source", records)
    conn.commit()
    return len(records)


def rebuild_adj_close(conn, ticker):
    """重算還原收盤價。回傳 (已還原筆數, 金額未知的除權息日清單)。

    往回累乘：某日之前的所有價格，都要乘上該除權息日的 參考價/前收盤 factor。
    """
    quotes = conn.execute(
        "SELECT date, close, is_exdiv FROM daily_quotes WHERE ticker = ? ORDER BY date",
        (ticker,)).fetchall()
    if not quotes:
        return 0, []

    dividend_map = {
        row["ex_date"]: row
        for row in conn.execute("SELECT * FROM dividends WHERE ticker = ?", (ticker,))
    }

    factors = [1.0] * len(quotes)   # 各日「之後所有除權息」的累積 factor
    unknown_dates = []
    cumulative = 1.0
    for index in range(len(quotes) - 1, -1, -1):
        factors[index] = cumulative
        if quotes[index]["is_exdiv"] and index > 0:
            event = dividend_map.get(quotes[index]["date"])
            if event is None:
                unknown_dates.append(quotes[index]["date"])
                continue  # 金額未知：不猜，保持 factor 不變並回報
            if event["ref_ratio"] is not None:
                # 官方比例：本地日線若有缺口，上一根收盤不等於官方前收，用差額還原會失準
                cumulative *= event["ref_ratio"]
                continue
            prev_close = quotes[index - 1]["close"]
            reference = ((prev_close - event["cash"] + event["sub_price"] * event["sub_ratio"])
                         / (1.0 + event["stock_ratio"] + event["sub_ratio"]))
            cumulative *= reference / prev_close

    conn.executemany(
        "UPDATE daily_quotes SET adj_close = ? WHERE ticker = ? AND date = ?",
        [(round(quotes[i]["close"] * factors[i], 4), ticker, quotes[i]["date"])
         for i in range(len(quotes))])
    conn.commit()
    return len(quotes), unknown_dates


def sync_ticker(conn, ticker, months=7):
    """抓取 + 落庫 + 還原，一次完成。回傳摘要 dict。

    先試 TWSE（上市），查無資料才轉 TPEx（上櫃）——代號本身看不出市場別，
    只能靠實際查詢判定。
    """
    if not TICKER_PATTERN.match(ticker or ""):
        raise RuntimeError("股票代號格式不符（4–6 碼數字，ETF 可含英文尾碼）：%r" % ticker)
    month_list = recent_months(months)
    market = "TWSE"
    rows = fetch_months(ticker, month_list)
    if not rows:
        market = "TPEx"
        rows, implied_events = fetch_tpex.fetch_months(ticker, month_list)
        if implied_events:
            fetch_tpex.save_implied_dividends(conn, ticker, implied_events)
    if not rows:
        raise RuntimeError("%s 無任何日線資料（TWSE 與 TPEx 皆查無），無法分析" % ticker)
    save_quotes(conn, ticker, rows)
    count, unknown = rebuild_adj_close(conn, ticker)
    if unknown and market == "TWSE":
        # 上櫃已由漲跌欄反推；上市的歷史金額要另查計算結果表。查不到者（如減資）維持未知
        fill_historical_exdiv(conn, unknown)
        count, unknown = rebuild_adj_close(conn, ticker)
    return {"ticker": ticker, "bars": count, "latest": rows[-1]["date"],
            "market": market, "unadjusted_exdiv": unknown}


def fill_historical_exdiv(conn, unknown_dates):
    """用 TWT49U 補「偵測到除權息但查無金額」的日子。單次請求涵蓋整段日期、全市場。"""
    time.sleep(REQUEST_GAP_SEC)
    payload = _get_json(fetch_exright.build_url(min(unknown_dates), max(unknown_dates)))
    return fetch_exright.save_events(conn, fetch_exright.parse_events(payload))


def main():
    parser = argparse.ArgumentParser(description="抓取台股盤後資料（上市走 TWSE、上櫃走 TPEx）")
    parser.add_argument("tickers", nargs="+", help="股票代號，如 2330")
    parser.add_argument("--months", type=int, default=7, help="回溯月數（預設 7，約 120 個交易日）")
    parser.add_argument("--skip-dividends", action="store_true")
    args = parser.parse_args()

    conn = db.connect()
    if not args.skip_dividends:
        print("除權息預告表：寫入 %d 筆" % sync_dividends(conn))
    for ticker in args.tickers:
        summary = sync_ticker(conn, ticker, args.months)
        print("%(ticker)s（%(market)s）：%(bars)d 根日線，最新 %(latest)s" % summary)
        if summary["unadjusted_exdiv"]:
            print("  [warn] 除權息金額未知，未還原：%s" % ", ".join(summary["unadjusted_exdiv"]))
    conn.close()


if __name__ == "__main__":
    main()
