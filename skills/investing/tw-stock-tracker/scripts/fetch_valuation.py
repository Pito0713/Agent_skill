"""估值資料抓取：上市 BWIBBU_d、上櫃 peQryDate，皆為「某一天、全市場」一次請求。

存全市場而非只存追蹤標的：請求成本相同，之後新增標的不必重抓歷史。
抓過的 (日期, 市場) 記在 valuation_fetches，不重抓；休市日回空也記，
但最近幾天回空可能只是尚未公布，不記，下次再試。

用法：
  python3 fetch_valuation.py backfill [--years 4]   # 每週一個交易日，供百分位與回測用
  python3 fetch_valuation.py latest 2330 5425       # 補這幾檔最新交易日的估值
"""

import argparse
import sys
import time
from datetime import date, timedelta

import db
import fetch_tpex
import fetch_twse

TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date=%s&selectType=ALL&response=json"
TPEX_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?date=%s&response=json"
REQUEST_GAP_SEC = 3.0
MARKETS = ("TWSE", "TPEx")
UNPUBLISHED_GRACE_DAYS = 7   # 這幾天內回空不記為休市，可能只是還沒公布
TWSE_FIELDS = ("證券代號", "本益比", "股價淨值比", "殖利率(%)", "財報年/季")
TPEX_FIELDS = ("股票代號", "本益比", "股價淨值比", "殖利率(%)")


def _to_float(raw):
    text = str(raw).replace(",", "").strip()
    try:
        return float(text) if text not in ("", "-", "--", "---", "N/A") else None
    except ValueError:
        return None


def _positive(raw):
    """本益比、淨值比：虧損時 TWSE 填 '-' 或 0，一律視為無資料。"""
    value = _to_float(raw)
    return value if value and value > 0 else None


def _rows_by_fields(fields, data, required):
    missing = [name for name in required if name not in fields]
    if missing:
        raise RuntimeError("估值資料欄位缺少 %s，格式可能已變更" % "、".join(missing))
    indexes = [fields.index(name) for name in required]
    return [[row[i] for i in indexes] for row in data]


TWSE_NO_DATA = "沒有符合條件的資料"


def parse_twse(payload):
    """BWIBBU_d -> [(ticker, pe, pb, dividend_yield, fiscal_period)]。休市回 []。

    只有明確的「查無資料」才算休市；其他非 OK（如系統忙碌）拋錯，
    否則會被記成休市而永久不再重試。
    """
    stat = str(payload.get("stat") or "")
    if TWSE_NO_DATA in stat:
        return []
    data = payload.get("data")
    if stat != "OK" or not data:
        raise RuntimeError("BWIBBU_d 回應異常：stat=%s、%d 筆" % (stat or "無", len(data or [])))
    return [(ticker.strip(), _positive(pe), _positive(pb), _to_float(dy), str(period).strip() or None)
            for ticker, pe, pb, dy, period in
            _rows_by_fields(payload.get("fields") or [], data, TWSE_FIELDS)]


def parse_tpex(payload):
    """peQryDate -> 同 parse_twse；上櫃不提供財報季別。休市回 stat ok 但空表。"""
    if str(payload.get("stat") or "").lower() != "ok" or "tables" not in payload:
        raise RuntimeError("peQryDate 回應異常：%s" % (payload.get("stat") or "無 stat"))
    tables = payload.get("tables") or []
    if not tables or not isinstance(tables[0].get("data"), list):
        raise RuntimeError("peQryDate 回應缺少資料表")
    data = tables[0]["data"]
    if not data:
        return []
    return [(ticker.strip(), _positive(pe), _positive(pb), _to_float(dy), None)
            for ticker, pe, pb, dy in _rows_by_fields(tables[0].get("fields") or [], data, TPEX_FIELDS)]


def _request(day, market):
    if market == "TWSE":
        return parse_twse(fetch_twse._get_json(TWSE_URL % day.strftime("%Y%m%d"))), "BWIBBU_d"
    return parse_tpex(fetch_tpex._get_json(TPEX_URL % day.strftime("%Y/%m/%d"))), "TPEX_PE"


def is_fetched(conn, day, market):
    return conn.execute("SELECT 1 FROM valuation_fetches WHERE date = ? AND market = ?",
                        (day.isoformat(), market)).fetchone() is not None


def fetch_date(conn, day, market):
    """抓一天、一個市場並落庫。回傳筆數；0 = 休市或尚未公布。"""
    rows, source = _request(day, market)
    conn.executemany(
        "INSERT OR REPLACE INTO valuations (ticker, date, pe, pb, dividend_yield, fiscal_period,"
        " source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(ticker, day.isoformat(), pe, pb, dy, period, source) for ticker, pe, pb, dy, period in rows])
    if rows or day < date.today() - timedelta(days=UNPUBLISHED_GRACE_DAYS):
        conn.execute("INSERT OR REPLACE INTO valuation_fetches (date, market, rows) VALUES (?, ?, ?)",
                     (day.isoformat(), market, len(rows)))
    conn.commit()
    return len(rows)


def _fetch_with_gap(conn, day, market):
    time.sleep(REQUEST_GAP_SEC)
    return fetch_date(conn, day, market)


def backfill_week(conn, friday, market):
    """週五起往回找到第一個有資料的交易日。整週休市（如春節）回 0。"""
    for offset in range(5):
        day = friday - timedelta(days=offset)
        if is_fetched(conn, day, market):
            if conn.execute("SELECT rows FROM valuation_fetches WHERE date = ? AND market = ?",
                            (day.isoformat(), market)).fetchone()["rows"]:
                return day
            continue
        if _fetch_with_gap(conn, day, market):
            return day
    return None


def fridays_between(start, end):
    cursor = start + timedelta(days=(4 - start.weekday()) % 7)
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=7)


def backfill(conn, start, end):
    """start ~ end 每週一個交易日、兩個市場。回傳有資料的 (日期, 市場) 數。"""
    found = 0
    fridays = list(fridays_between(start, end))
    for index, friday in enumerate(fridays, 1):
        for market in MARKETS:
            found += backfill_week(conn, friday, market) is not None
        if index % 10 == 0 or index == len(fridays):
            print("  估值 %d/%d 週（至 %s）" % (index, len(fridays), friday), flush=True)
    return found


def sync_latest(conn, ticker):
    """補該檔最新一根日線那天的估值（兩個市場都查，不必知道市場別）。"""
    latest = conn.execute("SELECT MAX(date) FROM daily_quotes WHERE ticker = ?", (ticker,)).fetchone()[0]
    if latest is None:
        return
    day = date.fromisoformat(latest)
    for market in MARKETS:
        if not is_fetched(conn, day, market):
            _fetch_with_gap(conn, day, market)


def main():
    parser = argparse.ArgumentParser(description="抓取上市／上櫃估值（本益比、淨值比、殖利率）")
    sub = parser.add_subparsers(dest="command", required=True)
    backfill_parser = sub.add_parser("backfill", help="每週一個交易日的歷史估值")
    backfill_parser.add_argument("--years", type=float, default=4, help="回溯年數，預設 4")
    latest_parser = sub.add_parser("latest", help="補指定標的最新交易日的估值")
    latest_parser.add_argument("tickers", nargs="+")
    args = parser.parse_args()

    conn = db.connect()
    try:
        if args.command == "backfill":
            today = date.today()
            found = backfill(conn, today - timedelta(days=round(args.years * 365)), today)
            print("估值回補完成：%d 個（日期, 市場）有資料" % found)
        else:
            for ticker in args.tickers:
                sync_latest(conn, ticker)
            print("已補 %s 的最新估值" % "、".join(args.tickers))
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
