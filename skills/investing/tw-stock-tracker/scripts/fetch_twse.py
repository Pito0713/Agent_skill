"""TWSE 盤後資料抓取：日線 OHLCV、除權息事件、還原股價計算。

資料源（皆免金鑰）：
  - STOCK_DAY   : 個股單月日線。漲跌價差欄位的 "X" 前綴 = 該日除權息（TWSE 不計算漲跌）。
  - TWT48U_ALL  : 除權除息預告表。只涵蓋「滾動未來約 5 週」，故僅前瞻窗口有配息金額。

還原股價：參考價 = (前收盤 - 現金股利) / (1 + 配股率)，往前累乘 factor。
偵測得到除權息日但查不到金額時，adj_close 留 NULL 並由呼叫端標記，
不猜數字——錯誤的還原價會讓 track record 統計失真。
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

import db

STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
DIVIDEND_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
USER_AGENT = "Mozilla/5.0 (compatible; tw-stock-tracker/1.0)"
REQUEST_GAP_SEC = 3.0  # TWSE 對密集請求會擋，月份之間強制間隔


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


def sync_dividends(conn):
    """抓除權息預告表存入 dividends。回傳寫入筆數。"""
    payload = _get_json(DIVIDEND_URL)
    records = []
    for row in payload:
        cash = _to_float(row.get("CashDividend") or "") or 0.0
        stock_ratio = (_to_float(row.get("StockDividendRatio") or "") or 0.0) / 1000.0
        if cash == 0.0 and stock_ratio == 0.0:
            continue
        raw_date = (row.get("Date") or "").strip()
        if len(raw_date) != 7:
            continue
        ex_date = "%04d-%s-%s" % (int(raw_date[:3]) + 1911, raw_date[3:5], raw_date[5:7])
        records.append((row["Code"].strip(), ex_date, cash, stock_ratio, "TWT48U_ALL"))
    conn.executemany(
        "INSERT OR REPLACE INTO dividends (ticker, ex_date, cash, stock_ratio, source)"
        " VALUES (?, ?, ?, ?, ?)", records)
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
        row["ex_date"]: (row["cash"], row["stock_ratio"])
        for row in conn.execute("SELECT * FROM dividends WHERE ticker = ?", (ticker,))
    }

    factors = [1.0] * len(quotes)   # 各日「之後所有除權息」的累積 factor
    unknown_dates = []
    cumulative = 1.0
    for index in range(len(quotes) - 1, -1, -1):
        factors[index] = cumulative
        if quotes[index]["is_exdiv"] and index > 0:
            cash, stock_ratio = dividend_map.get(quotes[index]["date"], (None, None))
            if cash is None:
                unknown_dates.append(quotes[index]["date"])
                continue  # 金額未知：不猜，保持 factor 不變並回報
            prev_close = quotes[index - 1]["close"]
            cumulative *= ((prev_close - cash) / (1.0 + stock_ratio)) / prev_close

    conn.executemany(
        "UPDATE daily_quotes SET adj_close = ? WHERE ticker = ? AND date = ?",
        [(round(quotes[i]["close"] * factors[i], 4), ticker, quotes[i]["date"])
         for i in range(len(quotes))])
    conn.commit()
    return len(quotes), unknown_dates


def sync_ticker(conn, ticker, months=7):
    """抓取 + 落庫 + 還原，一次完成。回傳摘要 dict。"""
    rows = fetch_months(ticker, recent_months(months))
    if not rows:
        raise RuntimeError("%s 無任何日線資料，無法分析" % ticker)
    save_quotes(conn, ticker, rows)
    count, unknown = rebuild_adj_close(conn, ticker)
    return {"ticker": ticker, "bars": count, "latest": rows[-1]["date"],
            "unadjusted_exdiv": unknown}


def main():
    parser = argparse.ArgumentParser(description="抓取 TWSE 盤後資料")
    parser.add_argument("tickers", nargs="+", help="股票代號，如 2330")
    parser.add_argument("--months", type=int, default=7, help="回溯月數（預設 7，約 120 個交易日）")
    parser.add_argument("--skip-dividends", action="store_true")
    args = parser.parse_args()

    conn = db.connect()
    if not args.skip_dividends:
        print("除權息預告表：寫入 %d 筆" % sync_dividends(conn))
    for ticker in args.tickers:
        summary = sync_ticker(conn, ticker, args.months)
        print("%(ticker)s：%(bars)d 根日線，最新 %(latest)s" % summary)
        if summary["unadjusted_exdiv"]:
            print("  [warn] 除權息金額未知，未還原：%s" % ", ".join(summary["unadjusted_exdiv"]))
    conn.close()


if __name__ == "__main__":
    main()
