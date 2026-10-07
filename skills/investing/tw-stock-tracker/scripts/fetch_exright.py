"""TWSE 歷史除權息：TWT49U 除權除息計算結果表的解析與落庫。

TWT48U_ALL 預告表只涵蓋滾動未來約 5 週，更早的除權息日偵測得到（STOCK_DAY 的 X 標記）
卻查不到金額。TWT49U 是事後公布的計算結果，含官方「除權息前收盤價」與「除權息參考價」，
一次查詢可涵蓋多年、全市場（實測 2020–2023 單次回 3,974 筆）。

還原用官方「參考價 / 前收」比例（ref_ratio），不用本地上一根收盤：本地日線若有缺口，
兩者對不上，用差額還原會失準。cash 欄存「前收 − 參考價」僅供閱讀；參考價已含現金股利、
配股、現增的綜合效果，stock_ratio / sub_ratio 不填，否則會被重複扣一次。

不使用「最近一次申報每股淨值／盈餘」欄位：那是查詢當下的值，不是除權息當時的值。
HTTP 由 fetch_twse 負責（本模組被它匯入，反向匯入會成循環）。
"""

import re

EXRIGHT_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
ROC_DATE_PATTERN = re.compile(r"(\d+)年(\d{2})月(\d{2})日")
REQUIRED_FIELDS = ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價")


def _to_float(raw):
    text = str(raw).replace(",", "").strip()
    try:
        return float(text) if text and text not in ("--", "---") else None
    except ValueError:
        return None


def roc_text_to_iso(text):
    """'112年06月15日' -> '2023-06-15'。"""
    match = ROC_DATE_PATTERN.search(text or "")
    if not match:
        raise ValueError("無法解析民國日期：%r" % text)
    year, month, day = match.groups()
    return "%04d-%s-%s" % (int(year) + 1911, month, day)


def build_url(start_date, end_date):
    """日期為 ISO yyyy-mm-dd。"""
    return "%s?response=json&startDate=%s&endDate=%s" % (
        EXRIGHT_URL, start_date.replace("-", ""), end_date.replace("-", ""))


def parse_events(payload):
    """TWT49U 回應 -> [(ticker, ex_date, cash_equivalent, ref_ratio)]。

    欄位以名稱定位而非位置，TWSE 調整欄位順序時寧可報錯也不讀錯欄。
    差額可為負（現增認購價高於前收）。差額為 0 仍保存（ref_ratio = 1），
    否則該日永遠被當成金額未知，每次同步都重查。
    """
    rows = payload.get("data") or []
    if not rows:
        return []
    fields = payload.get("fields") or []
    missing = [name for name in REQUIRED_FIELDS if name not in fields]
    if missing:
        raise RuntimeError("TWT49U 欄位缺少 %s，格式可能已變更" % "、".join(missing))
    date_i, ticker_i, prev_i, ref_i = (fields.index(name) for name in REQUIRED_FIELDS)
    events = []
    for row in rows:
        prev_close, reference = _to_float(row[prev_i]), _to_float(row[ref_i])
        if not prev_close or not reference:
            continue
        events.append((row[ticker_i].strip(), roc_text_to_iso(row[date_i]),
                       round(prev_close - reference, 4), reference / prev_close))
    return events


def save_events(conn, events):
    """寫入 dividends，不覆蓋既有事件：預告表的分項金額比反推值資訊更完整。回傳新增筆數。"""
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO dividends"
        " (ticker, ex_date, cash, stock_ratio, sub_ratio, sub_price, source, ref_ratio)"
        " VALUES (?, ?, ?, 0, 0, 0, 'TWT49U', ?)", events)
    conn.commit()
    return conn.total_changes - before
