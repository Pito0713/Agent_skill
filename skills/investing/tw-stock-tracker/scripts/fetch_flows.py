"""三大法人買賣超抓取：上市 T86、上櫃 insti/dailyTrade，皆為「某一天、全市場」一次請求。

存全市場而非只存追蹤標的：請求成本相同，之後新增標的不必重抓歷史。
法人因子要算近 5／20 個交易日的累計，所以逐日抓（估值是每週一天，兩者不同）。
抓過的 (日期, 市場) 記在 flow_fetches，不重抓；休市日回空也記，
但最近幾天回空可能只是尚未公布，不記，下次再試。

用法：
  python3 fetch_flows.py backfill [--years 3]   # 逐日回補，首次 3 年約 75 分鐘
  python3 fetch_flows.py latest                 # 補最近 30 天內缺的交易日
"""

import argparse
import sys
import time
from datetime import date, timedelta

import db
import fetch_tpex
import fetch_twse

TWSE_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date=%s&selectType=ALLBUT0999&response=json"
TPEX_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=%s&response=json"
REQUEST_GAP_SEC = 3.0
MARKETS = ("TWSE", "TPEx")
UNPUBLISHED_GRACE_DAYS = 7   # 這幾天內回空不記為休市，可能只是還沒公布
LATEST_DAYS = 30
TWSE_NO_DATA = "沒有符合條件的資料"
TWSE_FIELDS = ("證券代號", "外陸資買賣超股數(不含外資自營商)", "投信買賣超股數",
               "自營商買賣超股數", "三大法人買賣超股數")
# TPEx 欄名只有重複的「買進／賣出／買賣超股數」，看不出屬於哪個法人，只能靠位置。
# 群組順序：外資(不含外資自營商)、外資自營商、外資合計、投信、自營商自行買賣、
# 自營商避險、自營商合計、三大法人合計——以「外資合計 + 投信 + 自營商合計 = 三大法人合計」
# 對 2026-10-07 全部 901 筆驗證過。parse_tpex 每筆都重驗各組「買 − 賣 = 超」與三條加總關係，
# 大多數錯位會拋錯；但「外資」與「外資自營商」整組互換時等式對稱、驗不出來（外資自營商幾乎全為 0，
# 互換會讓外資因子全變 0，回測報告會看得出異常）。
TPEX_COLUMN_COUNT = 24
TPEX_GROUP_NETS = (4, 7, 10, 13, 16, 19, 22)   # 各組「買賣超」欄；買進、賣出在其前兩欄
TPEX_FOREIGN, TPEX_FOREIGN_DEALER, TPEX_FOREIGN_TOTAL = 4, 7, 10
TPEX_TRUST, TPEX_DEALER_SELF, TPEX_DEALER_HEDGE, TPEX_DEALER_TOTAL, TPEX_TOTAL = 13, 16, 19, 22, 23


def _to_int(raw):
    text = str(raw).replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        raise RuntimeError("法人買賣超數值無法解析：%r" % raw)


def parse_twse(payload, day):
    """T86 -> [(ticker, foreign_net, trust_net, dealer_net, total_net)]。休市回 []。

    只有明確的「查無資料」才算休市；其他非 OK（如系統忙碌）拋錯，
    否則會被記成休市而永久不再重試。
    """
    stat = str(payload.get("stat") or "")
    if TWSE_NO_DATA in stat:
        return []
    data = payload.get("data")
    if stat != "OK" or not data:
        raise RuntimeError("T86 回應異常：stat=%s、%d 筆" % (stat or "無", len(data or [])))
    if payload.get("date") != day.strftime("%Y%m%d"):
        raise RuntimeError("T86 回傳日期 %s 與請求 %s 不符" % (payload.get("date"), day))
    fields = payload.get("fields") or []
    missing = [name for name in TWSE_FIELDS if name not in fields]
    if missing:
        raise RuntimeError("T86 欄位缺少 %s，格式可能已變更" % "、".join(missing))
    indexes = [fields.index(name) for name in TWSE_FIELDS]
    return [(row[indexes[0]].strip(), *(_to_int(row[i]) for i in indexes[1:])) for row in data]


def _tpex_total(value, foreign_column):
    return value[foreign_column] + value[TPEX_TRUST] + value[TPEX_DEALER_TOTAL]


def _check_tpex_row(row):
    # 官方說明的合計是否含外資自營商無法實證（抽查多日全市場，外資自營商皆為 0），
    # 兩種算法都接受，避免合法資料被擋；外資因子只用「不含外資自營商」那欄，不受影響。
    value = {i: _to_int(row[i]) for i in range(2, TPEX_COLUMN_COUNT)}
    consistent = (
        all(value[net - 2] - value[net - 1] == value[net] for net in TPEX_GROUP_NETS)
        and value[TPEX_FOREIGN] + value[TPEX_FOREIGN_DEALER] == value[TPEX_FOREIGN_TOTAL]
        and value[TPEX_DEALER_SELF] + value[TPEX_DEALER_HEDGE] == value[TPEX_DEALER_TOTAL]
        and value[TPEX_TOTAL] in (_tpex_total(value, TPEX_FOREIGN_TOTAL), _tpex_total(value, TPEX_FOREIGN)))
    if not consistent:
        raise RuntimeError("上櫃法人資料 %s 加總不符，欄位順序可能已變更" % row[0])
    return (row[0].strip(), value[TPEX_FOREIGN], value[TPEX_TRUST], value[TPEX_DEALER_TOTAL],
            value[TPEX_TOTAL])


def parse_tpex(payload, day):
    """insti/dailyTrade -> 同 parse_twse。休市回 stat ok 但空表。"""
    if str(payload.get("stat") or "").lower() != "ok" or "tables" not in payload:
        raise RuntimeError("上櫃法人回應異常：%s" % (payload.get("stat") or "無 stat"))
    tables = payload.get("tables") or []
    if not tables or not isinstance(tables[0].get("data"), list):
        raise RuntimeError("上櫃法人回應缺少資料表")
    # 先驗日期再判空表：回錯日期的空表若當成休市，會被永久快取而不再重試
    if payload.get("date") != day.strftime("%Y%m%d"):
        raise RuntimeError("上櫃法人回傳日期 %s 與請求 %s 不符" % (payload.get("date"), day))
    table = tables[0]
    if not table["data"]:
        return []
    if len(table.get("fields") or []) != TPEX_COLUMN_COUNT:
        raise RuntimeError("上櫃法人欄位數 %d ≠ %d，格式可能已變更"
                           % (len(table.get("fields") or []), TPEX_COLUMN_COUNT))
    return [_check_tpex_row(row) for row in table["data"]]


def _request(day, market):
    if market == "TWSE":
        return parse_twse(fetch_twse._get_json(TWSE_URL % day.strftime("%Y%m%d")), day)
    return parse_tpex(fetch_tpex._get_json(TPEX_URL % day.strftime("%Y/%m/%d")), day)


def is_fetched(conn, day, market):
    return conn.execute("SELECT 1 FROM flow_fetches WHERE date = ? AND market = ?",
                        (day.isoformat(), market)).fetchone() is not None


def fetch_date(conn, day, market):
    """抓一天、一個市場並落庫。回傳筆數；0 = 休市或尚未公布。"""
    rows = _request(day, market)
    conn.executemany(
        "INSERT OR REPLACE INTO institutional_flows (ticker, date, foreign_net, trust_net,"
        " dealer_net, total_net) VALUES (?, ?, ?, ?, ?, ?)",
        [(ticker, day.isoformat(), *values) for ticker, *values in rows])
    if rows or day < date.today() - timedelta(days=UNPUBLISHED_GRACE_DAYS):
        conn.execute("INSERT OR REPLACE INTO flow_fetches (date, market, rows) VALUES (?, ?, ?)",
                     (day.isoformat(), market, len(rows)))
    conn.commit()
    return len(rows)


def weekdays_between(start, end):
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            yield cursor
        cursor += timedelta(days=1)


def backfill(conn, start, end):
    """start ~ end 每個平日、兩個市場，已抓過的略過。回傳本次實際請求次數。"""
    requested = 0
    days = list(weekdays_between(start, end))
    for index, day in enumerate(days, 1):
        for market in MARKETS:
            if is_fetched(conn, day, market):
                continue
            time.sleep(REQUEST_GAP_SEC)
            fetch_date(conn, day, market)
            requested += 1
        if index % 50 == 0 or index == len(days):
            print("  法人買賣超 %d/%d 天（至 %s）" % (index, len(days), day), flush=True)
    return requested


def main():
    parser = argparse.ArgumentParser(description="抓取上市／上櫃三大法人買賣超（全市場、逐日）")
    sub = parser.add_subparsers(dest="command", required=True)
    backfill_parser = sub.add_parser("backfill", help="逐日回補歷史")
    backfill_parser.add_argument("--years", type=float, default=3, help="回溯年數，預設 3")
    sub.add_parser("latest", help="補最近 %d 天內缺的交易日" % LATEST_DAYS)
    args = parser.parse_args()

    conn = db.connect()
    try:
        today = date.today()
        days = round(args.years * 365) if args.command == "backfill" else LATEST_DAYS
        requested = backfill(conn, today - timedelta(days=days), today)
        print("法人買賣超回補完成：本次請求 %d 次" % requested)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
