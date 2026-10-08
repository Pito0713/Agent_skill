"""全市場日線：上市 MI_INDEX、上櫃 afterTrading/otc，皆為「某一天、全市場」一次請求。

寫入全市場 DB（db.MARKET_DB_PATH），不寫 tracker.db：上櫃全市場表的成交股數與逐檔表
差約 1–2%，混用會讓同一檔的單檔分析分數隨資料源改變。篩選結果要以逐檔資料覆核。

除權息：上市看「漲跌(+/-)」的 X 標記，金額由 TWT48U_ALL／TWT49U 補；
上櫃存官方「漲跌」，事後逐檔與前一交易日收盤比對反推（同 fetch_tpex.parse_days 的邏輯）。

用法：
  python3 fetch_market_daily.py sync [--days 200]   # 補最近 N 個曆日缺的交易日並重算還原價
"""

import argparse
import sys
import time
from datetime import date, timedelta

import db
import fetch_tpex
import fetch_twse

TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=%s&type=ALLBUT0999&response=json"
TPEX_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date=%s&type=EW&response=json"
TWSE_INDUSTRY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_INDUSTRY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
# 上櫃除權除息計算結果表：全市場、可查日期區間。全市場日線表的「漲跌」在除權息日填「除息」等文字，
# 推不出金額，要靠這張表的官方參考價
TPEX_EXRIGHT_URL = "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ?startDate=%s&endDate=%s&response=json"
TPEX_EXRIGHT_FIELDS = ("除權息日期", "代號", "除權息前收盤價", "除權息參考價")
REQUEST_GAP_SEC = 3.0
MARKETS = ("TWSE", "TPEx")
UNPUBLISHED_GRACE_DAYS = 7
DEFAULT_DAYS = 200          # 約 135 個交易日：評分要 60 根，MACD／RSI 暖機再多抓
TWSE_NO_DATA = "沒有符合條件的資料"
TWSE_TABLE = "每日收盤行情"
TWSE_FIELDS = ("證券代號", "證券名稱", "成交股數", "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)",
               "成交金額")
TPEX_FIELDS = ("代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "成交股數", "成交金額(元)")


def _to_float(raw):
    text = str(raw).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _pick(fields, required, source):
    names = [str(name).strip() for name in fields]
    missing = [name for name in required if name not in names]
    if missing:
        raise RuntimeError("%s 欄位缺少 %s，格式可能已變更" % (source, "、".join(missing)))
    return [names.index(name) for name in required]


def _quote(ticker, name, prices, amounts):
    """prices = (open, high, low, close)、amounts = (成交股數, 成交金額)；
    任一價格不是數字（當日無成交）回 None。"""
    volume, turnover = amounts
    if any(value is None for value in prices) or volume is None:
        return None
    open_, high, low, close = prices
    return {"ticker": ticker.strip(), "name": name.strip(), "open": open_, "high": high,
            "low": low, "close": close, "volume": int(volume), "turnover": turnover}


def parse_twse(payload, day):
    """MI_INDEX -> [quote dict，含 is_exdiv]。休市回 []。"""
    stat = str(payload.get("stat") or "")
    if TWSE_NO_DATA in stat:
        return []
    if stat != "OK":
        raise RuntimeError("MI_INDEX 回應異常：stat=%s" % (stat or "無"))
    if payload.get("date") != day.strftime("%Y%m%d"):
        raise RuntimeError("MI_INDEX 回傳日期 %s 與請求 %s 不符" % (payload.get("date"), day))
    table = next((t for t in payload.get("tables") or [] if TWSE_TABLE in str(t.get("title"))), None)
    if table is None or not table.get("data"):
        raise RuntimeError("MI_INDEX 缺少每日收盤行情表")
    index = _pick(table.get("fields") or [], TWSE_FIELDS, "MI_INDEX")
    quotes = []
    for row in table["data"]:
        values = [row[i] for i in index]
        quote = _quote(values[0], values[1], [_to_float(v) for v in values[3:7]],
                       (_to_float(values[2]), _to_float(values[8])))
        if quote:
            quote["is_exdiv"] = 1 if "X" in str(values[7]) else 0
            quotes.append(quote)
    return quotes


def parse_tpex(payload, day):
    """afterTrading/otc -> [quote dict，含 change]。休市回 stat ok 但空表。"""
    if str(payload.get("stat") or "").lower() != "ok" or "tables" not in payload:
        raise RuntimeError("上櫃日線回應異常：%s" % (payload.get("stat") or "無 stat"))
    if payload.get("date") != day.strftime("%Y%m%d"):
        raise RuntimeError("上櫃日線回傳日期 %s 與請求 %s 不符" % (payload.get("date"), day))
    tables = payload.get("tables") or []
    if not tables or not isinstance(tables[0].get("data"), list):
        raise RuntimeError("上櫃日線回應缺少資料表")
    if not tables[0]["data"]:
        return []
    index = _pick(tables[0].get("fields") or [], TPEX_FIELDS, "上櫃日線")
    quotes = []
    for row in tables[0]["data"]:
        values = [row[i] for i in index]
        prices = [_to_float(values[i]) for i in (4, 5, 6, 2)]
        quote = _quote(values[0], values[1], prices, (_to_float(values[7]), _to_float(values[8])))
        if quote:
            quote["change"] = _to_float(values[3])
            quotes.append(quote)
    return quotes


def _request(day, market):
    if market == "TWSE":
        return parse_twse(fetch_twse._get_json(TWSE_URL % day.strftime("%Y%m%d")), day)
    return parse_tpex(fetch_tpex._get_json(TPEX_URL % day.strftime("%Y/%m/%d")), day)


def is_fetched(conn, day, market):
    return conn.execute("SELECT 1 FROM market_fetches WHERE date = ? AND market = ?",
                        (day.isoformat(), market)).fetchone() is not None


def save_day(conn, day, market, quotes):
    iso = day.isoformat()
    # 上市的 X 標記是官方資料，重抓直接覆寫；上櫃旗標由 detect_tpex_exdiv 判定，
    # 重抓時保留既有值——前一交易日不確定而無法重判時，不能讓已知（含金額未知）的除權息日消失
    keep_flag = market == "TPEx"
    conn.executemany(
        "INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume, is_exdiv, adj_close,"
        " turnover) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?) ON CONFLICT(ticker, date) DO UPDATE SET"
        " open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close,"
        " volume = excluded.volume, adj_close = NULL, turnover = excluded.turnover"
        + ("" if keep_flag else ", is_exdiv = excluded.is_exdiv"),
        [(q["ticker"], iso, q["open"], q["high"], q["low"], q["close"], q["volume"],
          q.get("is_exdiv", 0), q["turnover"]) for q in quotes])
    if market == "TPEx":
        conn.executemany("INSERT OR REPLACE INTO tpex_changes (ticker, date, change) VALUES (?, ?, ?)",
                         [(q["ticker"], iso, q["change"]) for q in quotes])
    conn.executemany(
        "INSERT INTO securities (ticker, name, market) VALUES (?, ?, ?)"
        " ON CONFLICT(ticker) DO UPDATE SET name = excluded.name, market = excluded.market",
        [(q["ticker"], q["name"], market) for q in quotes])
    if quotes:
        conn.execute("INSERT OR REPLACE INTO market_fetches (date, market, rows) VALUES (?, ?, ?)",
                     (iso, market, len(quotes)))
    conn.commit()


def fetch_day(conn, day, force=False):
    """抓一天、兩個市場。休市要兩個市場都回空才記（TWSE 的查無資料回應不帶日期，單看一邊不可靠）；
    一邊有資料、一邊空 → 拋錯不記，下次重試。回傳請求次數。"""
    pending = [m for m in MARKETS if force or not is_fetched(conn, day, m)]
    results = {}
    for market in pending:
        time.sleep(REQUEST_GAP_SEC)
        results[market] = _request(day, market)
    for market, quotes in results.items():
        save_day(conn, day, market, quotes)
    empty = [m for m, quotes in results.items() if not quotes]
    if not empty:
        return len(pending)
    other_rows = [r["rows"] for r in conn.execute(
        "SELECT rows FROM market_fetches WHERE date = ?", (day.isoformat(),))]
    if any(other_rows) or len(empty) < len(results):
        raise RuntimeError("%s %s 回空但另一市場有資料，不記為休市" % (day, "、".join(empty)))
    if day < date.today() - timedelta(days=UNPUBLISHED_GRACE_DAYS):   # 兩市場皆無資料才走到這裡
        conn.executemany("INSERT OR REPLACE INTO market_fetches (date, market, rows) VALUES (?, ?, 0)",
                         [(day.isoformat(), m) for m in empty])
        conn.commit()
    return len(pending)


def weekdays_between(start, end):
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            yield cursor
        cursor += timedelta(days=1)


def fetch_days(conn, start, end):
    """start ~ end 每個平日、兩個市場，已抓過的略過。回傳本次請求次數。"""
    return sum(fetch_day(conn, day) for day in weekdays_between(start, end))


def confirmed_holidays(conn):
    """兩個市場都記為 0 筆的日子。單一市場的 0 筆不算（舊版程式曾單邊回空就記錄）。"""
    return {r[0] for r in conn.execute("SELECT date FROM market_fetches WHERE rows = 0"
                                       " GROUP BY date HAVING COUNT(*) = %d" % len(MARKETS))}


def drop_one_sided_holidays(conn):
    """清掉單邊 0 筆的紀錄讓它重抓。回傳清掉的筆數。"""
    cursor = conn.execute("DELETE FROM market_fetches WHERE rows = 0 AND date NOT IN (SELECT date FROM"
                          " market_fetches WHERE rows = 0 GROUP BY date HAVING COUNT(*) = %d)" % len(MARKETS))
    conn.commit()
    return cursor.rowcount


def has_unconfirmed_gap(holidays, earlier, later):
    """earlier 與 later（不含）之間是否有平日既不是交易日也不是確認休市——可能漏抓一天。"""
    gap = weekdays_between(date.fromisoformat(earlier) + timedelta(days=1),
                           date.fromisoformat(later) - timedelta(days=1))
    return any(day.isoformat() not in holidays for day in gap)


def previous_trading_days(conn):
    """{上櫃交易日: 確定的前一交易日}。兩者之間的每個平日都必須是確認休市，
    否則中間可能漏抓一天，拿更早的收盤比對會把正常漲跌誤判成除權息。"""
    holidays = confirmed_holidays(conn)
    trading = [r[0] for r in conn.execute(
        "SELECT date FROM market_fetches WHERE market = 'TPEx' AND rows > 0 ORDER BY date")]
    return {current: prev for prev, current in zip(trading, trading[1:])
            if not has_unconfirmed_gap(holidays, prev, current)}


def detect_tpex_exdiv(conn):
    """上櫃逐檔比對：官方漲跌 ≠ 與前一交易日收盤的差 → 除權息日，反推約當現金。

    只和「上櫃前一個交易日」比：該股前一交易日沒有行情（停牌）就無從判斷，不標記。
    回傳反推出的事件數。
    """
    previous_day = previous_trading_days(conn)
    events = {}
    flags = []      # (is_exdiv, ticker, date)：只更新能判定的日子，判不了的保留既有旗標
    tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM securities WHERE market = 'TPEx'")]
    for ticker in tickers:
        rows = conn.execute(
            "SELECT q.date, q.close, c.change FROM daily_quotes q JOIN tpex_changes c"
            " ON c.ticker = q.ticker AND c.date = q.date WHERE q.ticker = ? ORDER BY q.date",
            (ticker,)).fetchall()
        for prev, row in zip(rows, rows[1:]):
            if previous_day.get(row["date"]) != prev["date"]:
                continue
            change = row["change"]
            if change is not None and abs((row["close"] - prev["close"]) - change) <= fetch_tpex.EXDIV_TOLERANCE:
                flags.append((0, ticker, row["date"]))
                continue
            flags.append((1, ticker, row["date"]))
            cash = prev["close"] - (row["close"] - change) if change is not None else None
            if cash and cash > 0:
                events.setdefault(ticker, []).append((row["date"], round(cash, 4)))
    conn.executemany("UPDATE daily_quotes SET is_exdiv = ? WHERE ticker = ? AND date = ?", flags)
    for ticker, ticker_events in events.items():
        fetch_tpex.save_implied_dividends(conn, ticker, ticker_events)
    conn.commit()
    return sum(len(v) for v in events.values())


def _roc_to_iso(text):
    year, month, day = text.strip().split("/")
    return "%04d-%s-%s" % (int(year) + 1911, month, day)


def parse_tpex_exright(payload):
    """exDailyQ -> [(ticker, ex_date, ref_ratio)]；ref_ratio = 官方參考價 / 除權息前收盤價。"""
    if str(payload.get("stat") or "").lower() != "ok":
        raise RuntimeError("上櫃除權息結果表回應異常：%s" % (payload.get("stat") or "無 stat"))
    tables = payload.get("tables") or []
    if not tables or not isinstance(tables[0].get("data"), list):
        raise RuntimeError("上櫃除權息結果表缺少資料表")
    if not tables[0]["data"]:
        return []
    index = _pick(tables[0].get("fields") or [], TPEX_EXRIGHT_FIELDS, "上櫃除權息結果表")
    events = []
    for row in tables[0]["data"]:
        day, ticker, before, reference = (row[i] for i in index)
        before, reference = _to_float(before), _to_float(reference)
        if before and reference and before > 0:
            events.append((ticker.strip(), _roc_to_iso(day), round(reference / before, 8)))
    return events


def fill_tpex_exright(conn, start, end):
    """逐月查上櫃除權息結果表，以官方比例寫入 dividends（rebuild 有 ref_ratio 時直接用它）。回傳筆數。"""
    saved = 0
    cursor = start.replace(day=1)
    while cursor <= end:
        month_end = min((cursor + timedelta(days=32)).replace(day=1) - timedelta(days=1), end)
        time.sleep(REQUEST_GAP_SEC)
        events = parse_tpex_exright(fetch_tpex._get_json(
            TPEX_EXRIGHT_URL % (max(cursor, start).strftime("%Y/%m/%d"), month_end.strftime("%Y/%m/%d"))))
        conn.executemany(
            "INSERT INTO dividends (ticker, ex_date, cash, stock_ratio, sub_ratio, sub_price, source, ref_ratio)"
            " VALUES (?, ?, 0, 0, 0, 0, 'TPEX_EXDAILY', ?) ON CONFLICT(ticker, ex_date) DO UPDATE SET"
            " ref_ratio = excluded.ref_ratio, source = excluded.source", events)
        conn.executemany("UPDATE daily_quotes SET is_exdiv = 1 WHERE ticker = ? AND date = ?",
                         [(ticker, day) for ticker, day, _ in events])
        saved += len(events)
        cursor = month_end + timedelta(days=1)
    conn.commit()
    return saved


def clear_twse_no_comparison(conn):
    """上市的 X 是「不比價」，含前一日無收盤價、新上市、恢復交易，不全是除權息。
    查無除權息事件、且上市前一交易日（確定，中間無漏抓）該股沒有行情者，不是除權息日，清掉旗標。
    回傳清掉的筆數。前一交易日有行情卻查無事件者（如減資）維持未知，由旗標揭露。"""
    holidays = confirmed_holidays(conn)
    trading = [r[0] for r in conn.execute(
        "SELECT date FROM market_fetches WHERE market = 'TWSE' AND rows > 0 ORDER BY date")]
    previous = {cur: prev for prev, cur in zip(trading, trading[1:])
                if not has_unconfirmed_gap(holidays, prev, cur)}
    candidates = conn.execute(
        "SELECT q.ticker, q.date FROM daily_quotes q JOIN securities s ON s.ticker = q.ticker"
        " WHERE s.market = 'TWSE' AND q.is_exdiv = 1 AND NOT EXISTS (SELECT 1 FROM dividends d"
        " WHERE d.ticker = q.ticker AND d.ex_date = q.date)").fetchall()
    cleared = [(r["ticker"], r["date"]) for r in candidates
               if r["date"] in previous and conn.execute(
                   "SELECT 1 FROM daily_quotes WHERE ticker = ? AND date = ?",
                   (r["ticker"], previous[r["date"]])).fetchone() is None]
    conn.executemany("UPDATE daily_quotes SET is_exdiv = 0 WHERE ticker = ? AND date = ?", cleared)
    conn.commit()
    return len(cleared)


def rebuild_all(conn):
    """全部標的重算還原價；上市金額未知的除權息日以 TWT49U 一次補齊後再算。回傳仍未知的筆數。"""
    tickers = [r["ticker"] for r in conn.execute("SELECT ticker, market FROM securities")]
    markets = dict(conn.execute("SELECT ticker, market FROM securities").fetchall())
    unknown = {}
    for ticker in tickers:
        _, dates = fetch_twse.rebuild_adj_close(conn, ticker)
        if dates:
            unknown[ticker] = dates
    twse_unknown = sorted({d for t, dates in unknown.items() if markets[t] == "TWSE" for d in dates})
    if twse_unknown:
        fetch_twse.fill_historical_exdiv(conn, twse_unknown)
        print("  上市「不比價」非除權息、清掉旗標 %d 筆" % clear_twse_no_comparison(conn), flush=True)
        for ticker in [t for t in unknown if markets[t] == "TWSE"]:
            _, dates = fetch_twse.rebuild_adj_close(conn, ticker)
            unknown[ticker] = dates
    return sum(len(dates) for dates in unknown.values())


def sync_industries(conn):
    """上市、上櫃公司基本資料的產業代碼。回傳寫入筆數。"""
    pairs = [(r["公司代號"].strip(), (r.get("產業別") or "").strip() or None)
             for r in fetch_twse._get_json(TWSE_INDUSTRY_URL)]
    time.sleep(REQUEST_GAP_SEC)
    pairs += [(r["SecuritiesCompanyCode"].strip(), (r.get("SecuritiesIndustryCode") or "").strip() or None)
              for r in fetch_tpex._get_json(TPEX_INDUSTRY_URL)]
    conn.executemany("UPDATE securities SET industry_code = ? WHERE ticker = ?",
                     [(code, ticker) for ticker, code in pairs])
    conn.commit()
    return len(pairs)


def sync(conn, days):
    today = date.today()
    dropped = drop_one_sided_holidays(conn)
    print("抓取全市場日線（最近 %d 個曆日，已抓過的略過；清掉單邊休市紀錄 %d 筆）" % (days, dropped), flush=True)
    requested = fetch_days(conn, today - timedelta(days=days), today)
    print("  本次請求 %d 次；除權息預告表 %d 筆" % (requested, fetch_twse.sync_dividends(conn)), flush=True)
    print("  上櫃反推除權息 %d 筆" % detect_tpex_exdiv(conn), flush=True)
    print("  上櫃除權息結果表 %d 筆" % fill_tpex_exright(conn, today - timedelta(days=days), today), flush=True)
    print("  重算還原價：仍有 %d 個除權息日金額未知" % rebuild_all(conn), flush=True)
    print("  產業代碼 %d 筆" % sync_industries(conn), flush=True)


def main():
    parser = argparse.ArgumentParser(description="抓取上市／上櫃全市場日線到全市場 DB")
    sub = parser.add_subparsers(dest="command", required=True)
    sync_parser = sub.add_parser("sync", help="補最近 N 個曆日缺的交易日並重算還原價")
    sync_parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args()
    conn = db.connect_market()
    try:
        sync(conn, args.days)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
