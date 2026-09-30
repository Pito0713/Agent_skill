"""TWSE 盤後大盤／類股資料抓取（皆免金鑰）。

每個交易日 2 次請求：
  - MI_INDEX?type=ALLBUT0999 : 一次含類股指數收盤、大盤成交金額、漲跌家數
  - BFIAMU                  : 各類股成交金額
另有 t187ap03_L（上市公司產業別）供個股 → 類股對應。

⚠️ openapi 的 twtazu_od（漲跌家數）資料停在 2026-06-05 不再更新，禁用。
不 import tw-stock-tracker 的 fetch 模組：兩個 skill 必須能各自獨立運作。
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

import sectors

MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=%s&type=ALLBUT0999&response=json"
BFIAMU_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BFIAMU?date=%s&response=json"
INDUSTRY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
USER_AGENT = "Mozilla/5.0 (compatible; tw-market-rotation/1.0)"
REQUEST_GAP_SEC = 3.0        # TWSE 對密集請求會擋
HOLIDAY_WEEKDAY_BUFFER = 15  # 往回掃的平日上限 = 所需交易日 + 此緩衝（春節約休 7 個平日，另留餘裕）
INDUSTRY_REFRESH_DAYS = 7
# 假日／未開市時 TWSE 回的 stat；其他非 OK 訊息一律視為錯誤，避免把交易日誤記成假日
NO_DATA_STAT = "沒有符合條件的資料"


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


def _to_number(raw):
    """'6,223(55)' -> 6223.0；空值或 '--' -> None。括號內是漲跌停家數，不需要。"""
    text = re.sub(r"\(.*\)", "", str(raw)).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _find_table(payload, keyword):
    for table in payload.get("tables") or []:
        if keyword in (table.get("title") or ""):
            return table
    return None


def _parse_breadth(payload):
    table = _find_table(payload, "漲跌證券數")
    if table is None:
        raise RuntimeError("MI_INDEX 缺少漲跌證券數表")
    counts = {}
    for row in table["data"]:
        label = row[0]
        stock_count = _to_number(row[2])     # 第三欄是「股票」，不含權證等
        # 個別欄位缺值存 NULL，讓下游窗口計算自然得到 NULL，而不是整批 sync 中止
        count = None if stock_count is None else int(stock_count)
        if label.startswith("上漲"):
            counts["advances"] = count
        elif label.startswith("下跌"):
            counts["declines"] = count
    if len(counts) != 2:
        raise RuntimeError("MI_INDEX 漲跌家數解析失敗：%s" % table["data"])
    return counts


def _parse_turnover(payload):
    table = _find_table(payload, "大盤統計")
    if table is None:
        raise RuntimeError("MI_INDEX 缺少大盤統計資訊表")
    for row in table["data"]:
        # 證券合計 = 一般股票 + 變更交易 + 創新板，與類股成交金額口徑一致（排除 ETF、權證）
        if row[0].startswith("證券合計"):
            return _to_number(row[1])
    raise RuntimeError("MI_INDEX 大盤統計缺少「證券合計」列")


def parse_mi_index(payload):
    """回傳 {'turnover', 'advances', 'declines', 'taiex', 'index_closes': {code: close}}。"""
    table = _find_table(payload, "價格指數(臺灣證券交易所)")
    if table is None:
        raise RuntimeError("MI_INDEX 缺少價格指數表")
    closes = {row[0].strip(): _to_number(row[1]) for row in table["data"]}
    taiex = closes.get(sectors.BENCHMARK_INDEX_NAME)
    if taiex is None:
        raise RuntimeError("MI_INDEX 缺少加權指數收盤")
    index_closes = {code: closes[name] for name, code in sectors.MI_INDEX_TO_CODE.items()
                    if closes.get(name) is not None}
    result = {"turnover": _parse_turnover(payload), "taiex": taiex,
              "index_closes": index_closes}
    result.update(_parse_breadth(payload))
    return result


def parse_bfiamu(payload):
    """回傳 {code: 類股成交金額}；母類股與無代碼的分類自然被略過。"""
    turnovers = {}
    for row in payload.get("data") or []:
        code = sectors.BFIAMU_TO_CODE.get(row[0].strip())
        if code is not None:
            turnovers[code] = _to_number(row[2])
    return turnovers


def _is_no_data(payload):
    """True=假日無資料、False=有資料；其他非 OK 回應直接拋錯。"""
    stat = payload.get("stat") or ""
    if stat == "OK":
        return False
    if NO_DATA_STAT in stat:
        return True
    raise RuntimeError("TWSE 非預期回應：%s" % stat)


def _save_day(conn, iso_date, market, sector_turnovers):
    conn.execute(
        "INSERT OR REPLACE INTO market_daily (date, turnover, advances, declines, taiex)"
        " VALUES (?, ?, ?, ?, ?)",
        (iso_date, market["turnover"], market["advances"], market["declines"], market["taiex"]))
    codes = set(market["index_closes"]) | set(sector_turnovers)
    conn.executemany(
        "INSERT OR REPLACE INTO sector_daily (date, industry_code, index_close, turnover)"
        " VALUES (?, ?, ?, ?)",
        [(iso_date, code, market["index_closes"].get(code), sector_turnovers.get(code))
         for code in sorted(codes)])
    # BFIAMU 缺資料時不寫 fetch_log：下次 sync 會重抓該日，等資料補公布
    if sector_turnovers:
        conn.execute("INSERT OR REPLACE INTO rotation_fetch_log (date, is_trading) VALUES (?, 1)",
                     (iso_date,))


def fetch_day(conn, day):
    """抓單日並落庫。回傳 True=交易日、False=無資料。"""
    compact = day.strftime("%Y%m%d")
    mi_payload = _get_json(MI_INDEX_URL % compact)
    if _is_no_data(mi_payload):
        return False
    time.sleep(REQUEST_GAP_SEC)
    bf_payload = _get_json(BFIAMU_URL % compact)
    sector_turnovers = {} if _is_no_data(bf_payload) else parse_bfiamu(bf_payload)
    if not sector_turnovers:
        print("  [warn] %s BFIAMU 無資料，類股成交比重暫缺，下次 sync 重抓" % day, file=sys.stderr)
    _save_day(conn, day.isoformat(), parse_mi_index(mi_payload), sector_turnovers)
    return True


def _logged_status(conn, iso_date):
    row = conn.execute("SELECT is_trading FROM rotation_fetch_log WHERE date = ?",
                       (iso_date,)).fetchone()
    return None if row is None else bool(row["is_trading"])


def sync_days(conn, trading_days_needed, today=None):
    """由今天往回補到至少 trading_days_needed 個交易日。回傳 (新抓天數, 交易日總數)。"""
    today = today or date.today()
    cursor, trading_count, fetched, weekdays_seen = today, 0, 0, 0
    max_weekdays = trading_days_needed + HOLIDAY_WEEKDAY_BUFFER
    while trading_count < trading_days_needed and weekdays_seen < max_weekdays:
        if cursor.weekday() < 5:
            weekdays_seen += 1
            status = _logged_status(conn, cursor.isoformat())
            if status is None:
                if fetched:
                    time.sleep(REQUEST_GAP_SEC)
                status = fetch_day(conn, cursor)
                fetched += 1
                # 當天可能只是還沒公布，不記成非交易日，下次再試
                if not status and cursor != today:
                    conn.execute("INSERT OR REPLACE INTO rotation_fetch_log VALUES (?, 0)",
                                 (cursor.isoformat(),))
                conn.commit()
            trading_count += 1 if status else 0
        cursor -= timedelta(days=1)
    return fetched, trading_count


def sync_industry(conn, force=False):
    """更新個股 → 產業代碼對應。7 天內更新過就略過。回傳寫入筆數（略過回傳 0）。"""
    last = conn.execute("SELECT MAX(updated_at) m FROM stock_industry").fetchone()["m"]
    threshold = (date.today() - timedelta(days=INDUSTRY_REFRESH_DAYS)).isoformat()
    if not force and last and last >= threshold:
        return 0
    rows = [(r["公司代號"].strip(), (r.get("產業別") or "").strip() or None,
             date.today().isoformat()) for r in _get_json(INDUSTRY_URL)]
    conn.executemany("INSERT OR REPLACE INTO stock_industry (ticker, industry_code, updated_at)"
                     " VALUES (?, ?, ?)", rows)
    conn.commit()
    return len(rows)
