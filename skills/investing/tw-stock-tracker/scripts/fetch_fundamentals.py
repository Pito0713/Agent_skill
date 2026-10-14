"""基本面抓取：月營收與最新一季財報（EPS），皆為「全市場」一次請求。

資料源（皆免金鑰，2026-10 實測可用）：
  - 月營收最新一期：TWSE OpenAPI t187ap05_L、TPEx mopsfin_t187ap05_O
  - 月營收歷史：MOPS 舊站靜態頁 mopsov.twse.com.tw/nas/t21/{sii,otc}/t21sc03_{民國年}_{月}_{0 國內,1 國外}.html
    （2025-02 MOPS 改版後新站同路徑 404，只剩舊網域可用；舊網域停用時歷史回補會失敗，最新一期不受影響）
  - 財報：TWSE OpenAPI t187ap14_L、TPEx mopsfin_t187ap14_O，只給最新一季、且為年初至該季累計
OpenAPI 不給歷史財報：每季靠排程抓到時落庫，自然累積；不回補（使用者裁決，2026-10-14）。

用法：
  python3 fetch_fundamentals.py latest                 # 最新一期月營收 + 最新一季財報（4 次請求）
  python3 fetch_fundamentals.py backfill [--months 13] # 月營收歷史，已抓過的月份不重抓
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import db

USER_AGENT = "Mozilla/5.0 (compatible; tw-stock-tracker/1.0)"
REQUEST_GAP_SEC = 3.0
MARKETS = ("TWSE", "TPEx")
REVENUE_API = {"TWSE": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
               "TPEx": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"}
EPS_API = {"TWSE": "https://openapi.twse.com.tw/v1/opendata/t187ap14_L",
           "TPEx": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O"}
EPS_SOURCES = {"TWSE": "t187ap14_L", "TPEx": "t187ap14_O"}
MOPS_TYPEK = {"TWSE": "sii", "TPEx": "otc"}
REVENUE_HTML_URL = "https://mopsov.twse.com.tw/nas/t21/%s/t21sc03_%d_%d_%d.html"
REVENUE_HTML_PAGES = (0, 1)   # 0 國內公司、1 國外公司（KY 股只在這頁）
REVENUE_HTML_TITLE = "營業收入統計表"
# 法定公布期限為次月 10 日；之後才把「已抓過」記死，之前抓到的可能缺晚報的公司
REVENUE_DEADLINE_DAY = 15
HTML_ROW = re.compile(r"<tr align=right><td align=center>([0-9A-Z]{4,6})</td><td align=left>.*?</td>(.*?)</tr>",
                      re.S)
HTML_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)   # 年增率欄是大寫 <Td>
HTML_CELLS = 9   # 當月、上月、去年當月、上月增減%、去年同月增減%、當月累計、去年累計、前期增減%、備註


def get_text(url, data=None, encoding="utf-8", retries=3):
    """GET（data 為 dict 時 POST 表單）取回文字。404 回 None（未公布）；其他失敗重試後拋錯。"""
    body = urllib.parse.urlencode(data).encode("ascii") if data else None
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode(encoding, errors="replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last_error = error
        except OSError as error:   # 涵蓋 URLError 與讀取逾時
            last_error = error
        time.sleep(2 ** attempt)
    raise RuntimeError("請求失敗 %s: %s" % (url, last_error))


def _get_json_list(url):
    text = get_text(url)
    try:
        payload = json.loads(text) if text else None
    except json.JSONDecodeError as error:
        raise RuntimeError("%s 回應不是 JSON：%s" % (url, error)) from error
    if not isinstance(payload, list):
        raise RuntimeError("%s 回應格式異常" % url)
    return payload


def to_int(raw):
    text = str(raw or "").replace(",", "").strip()
    try:
        return int(round(float(text))) if text not in ("", "-", "--", "---") else None
    except ValueError:
        return None


def to_float(raw):
    text = str(raw or "").replace(",", "").strip()
    try:
        return float(text) if text not in ("", "-", "--", "---") else None
    except ValueError:
        return None


def roc_month_to_iso(raw):
    """'11509' -> '2026-09'。"""
    text = str(raw).strip()
    return "%04d-%s" % (int(text[:-2]) + 1911, text[-2:])


def roc_date_to_iso(raw):
    """'1151014' -> '2026-10-14'；格式不符回 None。"""
    text = str(raw or "").strip()
    if not text.isdigit() or len(text) < 7:
        return None
    return "%04d-%s-%s" % (int(text[:-4]) + 1911, text[-4:-2], text[-2:])


def _note(raw):
    text = re.sub(r"<[^>]+>", "", str(raw or "")).strip()
    return None if text in ("", "-") else text


def parse_revenue_api(payload):
    """t187ap05 -> [(ticker, month, revenue, prev, last_year, cum, cum_last_year, note)]。缺當月營收的列略過。"""
    rows = []
    for item in payload:
        revenue = to_int(item.get("營業收入-當月營收"))
        if revenue is None or not item.get("公司代號") or not item.get("資料年月"):
            continue
        rows.append((str(item["公司代號"]).strip(), roc_month_to_iso(item["資料年月"]), revenue,
                     to_int(item.get("營業收入-上月營收")), to_int(item.get("營業收入-去年當月營收")),
                     to_int(item.get("累計營業收入-當月累計營收")), to_int(item.get("累計營業收入-去年累計營收")),
                     _note(item.get("備註"))))
    if payload and not rows:
        raise RuntimeError("月營收 API 有資料但解析不到任何一列，欄位可能已變更")
    return rows


def parse_revenue_html(text, month):
    """t21sc03 靜態頁 -> 同 parse_revenue_api。合計列不是代號開頭，regex 自然略過。

    不是營收統計頁（維護頁、封鎖頁）拋錯，避免被當成「這個月沒有資料」。
    """
    if REVENUE_HTML_TITLE not in text:
        raise RuntimeError("月營收頁 %s 不是統計表（可能是維護或封鎖頁）" % month)
    rows = []
    for ticker, rest in HTML_ROW.findall(text):
        cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in HTML_CELL.findall(rest)]
        if len(cells) != HTML_CELLS:
            raise RuntimeError("月營收頁 %s 欄位數 %d ≠ %d，格式可能已變更" % (month, len(cells), HTML_CELLS))
        revenue = to_int(cells[0])
        if revenue is None:
            continue
        rows.append((ticker, month, revenue, to_int(cells[1]), to_int(cells[2]), to_int(cells[5]),
                     to_int(cells[6]), _note(cells[8])))
    return rows


def parse_eps_api(payload, market):
    """t187ap14 -> [(ticker, year, quarter, eps, revenue, op_income, non_op, net_income, published)]。"""
    keys = (("公司代號", "年度", "基本每股盈餘(元)", "出表日期") if market == "TWSE"
            else ("SecuritiesCompanyCode", "Year", "基本每股盈餘", "Date"))
    code_key, year_key, eps_key, date_key = keys
    rows = []
    for item in payload:
        code, year, quarter = item.get(code_key), to_int(item.get(year_key)), to_int(item.get("季別"))
        if not code or year is None or quarter not in (1, 2, 3, 4):
            continue
        rows.append((str(code).strip(), year + 1911, quarter, to_float(item.get(eps_key)),
                     to_int(item.get("營業收入")), to_int(item.get("營業利益")),
                     to_int(item.get("營業外收入及支出")), to_int(item.get("稅後淨利")),
                     roc_date_to_iso(item.get(date_key))))
    if payload and not rows:
        raise RuntimeError("財報 API 有資料但解析不到任何一列，欄位可能已變更")
    return rows


def save_revenue(conn, rows, source):
    conn.executemany(
        "INSERT OR REPLACE INTO monthly_revenue (ticker, month, revenue, prev_month_revenue, last_year_revenue,"
        " cum_revenue, cum_last_year_revenue, note, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(*row, source) for row in rows])
    conn.commit()


def save_financials(conn, rows, market):
    conn.executemany(
        "INSERT OR REPLACE INTO quarterly_financials (ticker, year, quarter, eps, revenue, operating_income,"
        " non_operating, net_income, published, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(*row, EPS_SOURCES[market]) for row in rows])
    conn.commit()


def sync_latest(conn):
    """兩個市場的最新月營收與最新一季財報。回傳 (營收筆數, 財報筆數)。"""
    revenue_n = eps_n = 0
    for market in MARKETS:
        rows = parse_revenue_api(_get_json_list(REVENUE_API[market]))
        save_revenue(conn, rows, "OPENAPI")
        revenue_n += len(rows)
        time.sleep(REQUEST_GAP_SEC)
        rows = parse_eps_api(_get_json_list(EPS_API[market]), market)
        save_financials(conn, rows, market)
        eps_n += len(rows)
        time.sleep(REQUEST_GAP_SEC)
    return revenue_n, eps_n


def recent_months(count, today=None):
    """不含本月（本月營收尚未公布）往前 count 個月，由舊到新，'yyyy-mm'。"""
    today = today or date.today()
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        months.append("%04d-%02d" % (year, month))
    return months[::-1]


def _past_deadline(month, today):
    year, mon = (int(part) for part in month.split("-"))
    year, mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    return today >= date(year, mon, REVENUE_DEADLINE_DAY)


def backfill(conn, months, today=None):
    """逐月逐市場抓靜態頁。已記錄的 (月, 市場) 不重抓。回傳本次實際請求次數。"""
    today = today or date.today()
    requested = 0
    for month in months:
        year, mon = (int(part) for part in month.split("-"))
        for market in MARKETS:
            if conn.execute("SELECT 1 FROM revenue_fetches WHERE month = ? AND market = ?",
                            (month, market)).fetchone():
                continue
            rows, all_pages_published = [], True
            for page in REVENUE_HTML_PAGES:
                time.sleep(REQUEST_GAP_SEC)
                requested += 1
                text = get_text(REVENUE_HTML_URL % (MOPS_TYPEK[market], year - 1911, mon, page),
                                encoding="cp950")
                if text is None:
                    all_pages_published = False   # 國外頁可能較晚上線，404 的月份不能記成完成
                    continue
                rows += parse_revenue_html(text, month)
            # 公司更正營收時重抓要能蓋掉舊的靜態頁數字；OpenAPI 的列不覆蓋（官方 API 優先）
            conn.executemany(
                "INSERT INTO monthly_revenue (ticker, month, revenue, prev_month_revenue,"
                " last_year_revenue, cum_revenue, cum_last_year_revenue, note, source)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'MOPS_HTML')"
                " ON CONFLICT(ticker, month) DO UPDATE SET revenue = excluded.revenue,"
                " prev_month_revenue = excluded.prev_month_revenue, last_year_revenue = excluded.last_year_revenue,"
                " cum_revenue = excluded.cum_revenue, cum_last_year_revenue = excluded.cum_last_year_revenue,"
                " note = excluded.note WHERE monthly_revenue.source = 'MOPS_HTML'", rows)
            if rows and all_pages_published and _past_deadline(month, today):
                conn.execute("INSERT OR REPLACE INTO revenue_fetches (month, market, rows) VALUES (?, ?, ?)",
                             (month, market, len(rows)))
            conn.commit()
    return requested


def main():
    parser = argparse.ArgumentParser(description="抓取月營收與最新一季財報（全市場）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("latest", help="最新一期月營收 + 最新一季財報")
    backfill_parser = sub.add_parser("backfill", help="月營收歷史（MOPS 舊站靜態頁）")
    backfill_parser.add_argument("--months", type=int, default=13, help="往前幾個月，預設 13")
    args = parser.parse_args()

    conn = db.connect()
    try:
        if args.command == "latest":
            print("基本面更新完成：月營收 %d 筆、財報 %d 筆" % sync_latest(conn))
        else:
            requested = backfill(conn, recent_months(max(args.months, 1)))
            print("月營收回補完成：本次請求 %d 次" % requested)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
