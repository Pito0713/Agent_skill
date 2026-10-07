"""上櫃（TPEx）盤後日線抓取。

TWSE STOCK_DAY 只收上市股，上櫃股（如 5425 台半）在那支 API 一律回「沒有符合條件的資料」，
必須改走 TPEx 個股日成交資訊。兩邊欄位序相同，但有兩個差異必須處理：

  1. 成交量單位是仟股，需乘 1000 還原成股數，否則量比和上市股不可比。
  2. 除權息日不以 "X" 標記。TPEx 的「漲跌」是對除權息參考價計算的，
     所以「漲跌 ≠ 收盤差額」就是除權息日，且差額可反推出當日參考價
     （已含現金股利、配股、現增的綜合效果）。這比 TWSE 預告表只有未來 5 週
     的限制更好：回溯窗口內的除權息都還原得出來。

HTTP helper 刻意不與 fetch_twse 共用——fetch_twse 匯入本模組，反向匯入會成循環。
"""

import json
import sys
import time
import urllib.request

TPEX_DAY_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
USER_AGENT = "Mozilla/5.0 (compatible; tw-stock-tracker/1.0)"
REQUEST_GAP_SEC = 3.0   # 與 TWSE 同樣對密集請求設間隔
EXDIV_TOLERANCE = 0.051  # 台股最小跳動 0.01–0.05，容差取 0.051 避開進位誤差


def _get_json(url, retries=3):
    """取回 JSON，失敗時退避重試。逾重試次數則拋出，不回傳半成品。"""
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        # OSError 涵蓋 URLError 與讀取中的 socket.timeout（Python 3.9 它不是 TimeoutError 子類）
        except (OSError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError("TPEx 請求失敗 %s: %s" % (url, last_error))


def _to_float(raw):
    text = str(raw).replace(",", "").strip()
    try:
        return float(text) if text and text not in ("--", "---") else None
    except ValueError:
        return None


def roc_to_iso(roc_date):
    """民國日期 '115/09/01' -> '2026-09-01'。"""
    year, month, day = roc_date.strip().split("/")
    return "%04d-%s-%s" % (int(year) + 1911, month, day)


def parse_days(raw_rows, prev_close=None):
    """TPEx 日成交列 -> (rows, exdiv_events)。

    raw_rows 必須是跨月串接後、由舊到新的完整序列——除權息是靠與前一日收盤
    比對推出來的，逐月切開會漏掉落在月初的除權息日。
    prev_close 為第一根之前那天的收盤（由 DB 提供）；沒給則第一根無從判斷，
    重抓既有月份時會把該日原有的除權息標記覆蓋成 0。

    exdiv_events 為 [(ex_date, cash_equivalent)]：反推成功者才入列，
    推不出來（漲跌欄非數字、參考價不合理）只標 is_exdiv，金額留給
    has_unadjusted_exdiv 旗標去揭露，不猜數字。
    """
    rows = []
    events = []
    for raw in raw_rows:
        close = _to_float(raw[6])
        if close is None:
            continue   # 停牌日無價，跳過
        change = _to_float(raw[7])
        volume_lots = _to_float(raw[1]) or 0.0
        row = {
            "date": roc_to_iso(raw[0]),
            "open": _to_float(raw[3]),
            "high": _to_float(raw[4]),
            "low": _to_float(raw[5]),
            "close": close,
            "volume": int(round(volume_lots * 1000)),
            "is_exdiv": 0,
        }
        if prev_close is not None:
            if change is None or abs((close - prev_close) - change) > EXDIV_TOLERANCE:
                row["is_exdiv"] = 1
                reference = close - change if change is not None else None
                cash_equivalent = prev_close - reference if reference else None
                if cash_equivalent and cash_equivalent > 0:
                    events.append((row["date"], round(cash_equivalent, 4)))
        rows.append(row)
        prev_close = close
    return rows, events


def fetch_months(ticker, months, prev_close=None):
    """抓取指定月份清單（['202609', ...]，由舊到新）的上櫃日線。prev_close 見 parse_days。

    回傳 (rows, exdiv_events)；查無資料回 ([], [])，由呼叫端決定如何回報。
    """
    raw_rows = []
    for index, month in enumerate(months):
        if index:
            time.sleep(REQUEST_GAP_SEC)
        url = "%s?code=%s&date=%s/%s/01&id=&response=json" % (
            TPEX_DAY_URL, ticker, month[:4], month[4:])
        tables = _get_json(url).get("tables") or []
        data = (tables[0].get("data") if tables else None) or []
        if not data:
            # 未來月份或未上櫃會回空表，屬正常情形，略過但不靜默失敗
            print("  [warn] TPEx %s %s：無資料" % (ticker, month), file=sys.stderr)
            continue
        raw_rows.extend(data)
    return parse_days(raw_rows, prev_close)


def save_implied_dividends(conn, ticker, events):
    """把反推出的除權息金額寫入 dividends，讓 rebuild_adj_close 原樣可用。

    參考價公式在 stock_ratio / sub_ratio 皆為 0 時退化成「前收盤 - cash」，
    正好等於這裡反推的結果——配股與現增的效果已含在參考價裡，
    不可再另外填比率，否則會被重複扣一次。
    """
    conn.executemany(
        "INSERT OR REPLACE INTO dividends"
        " (ticker, ex_date, cash, stock_ratio, sub_ratio, sub_price, source)"
        " VALUES (?, ?, ?, 0, 0, 0, 'TPEX_IMPLIED')",
        [(ticker, ex_date, cash) for ex_date, cash in events])
    conn.commit()
    return len(events)
