"""個股事件：法說會（MOPS，落庫）與新聞（Google News RSS，不落庫）。

  - 法說會：mopsov.twse.com.tw/mops/web/ajax_t100sb02_1（POST，單一公司、單一年度）。
    擇要訊息與簡報是前瞻指引唯一可引用的來源；簡報 PDF 以 GET 直連 /nas/STR/<檔名>。
  - 新聞：Google News RSS 不是官方 API，格式可能變、也可能被擋；只有標題、來源、時間、連結。
    新聞只給 LLM 摘要並附連結，不進評分、不落庫——不是可回測的資料。

用法：
  python3 fetch_events.py conferences 2330   # 抓今年與去年的法說會並落庫
  python3 fetch_events.py news 2330          # 印出近期新聞 JSON（不寫 DB）
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import db
import fetch_fundamentals
from fetch_twse import TICKER_PATTERN

CONFERENCE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1"
SLIDES_URL = "https://mopsov.twse.com.tw/nas/STR/%s"
NEWS_URL = "https://news.google.com/rss/search?q=%s&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
NEWS_LIMIT = 10
NEWS_MAX_AGE_DAYS = 30
CONFERENCE_ROW = re.compile(r"<tr class='(?:even|odd)' data-type='body'\s*>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
PDF_NAME = re.compile(r"fileName\.value=\"([0-9A-Za-z_.-]+\.pdf)\"")
HREF = re.compile(r"href='(https?://[^']+)'")
ROC_DATE = re.compile(r"(\d{2,3})/(\d{2})/(\d{2})")
CONFERENCE_CELLS = 12
NO_DATA = "查無資料"


def _text(cell):
    return html.unescape(re.sub(r"<[^>]+>", " ", cell)).strip() or None


def _roc_dates(text):
    return ["%04d-%s-%s" % (int(y) + 1911, m, d) for y, m, d in ROC_DATE.findall(text or "")]


def parse_conferences(page, ticker):
    """法說會頁 -> dict list。查無資料回 []；欄位數不符或整頁認不出拋錯（格式變更、維護或封鎖頁）。"""
    rows = CONFERENCE_ROW.findall(page)
    if not rows:
        if NO_DATA in page:
            return []
        raise RuntimeError("法說會頁面無法解析（可能是維護、封鎖或格式變更）")
    output = []
    for row in rows:
        cells = CELL.findall(row)
        if len(cells) != CONFERENCE_CELLS:
            raise RuntimeError("法說會表格欄位數 %d ≠ %d，格式可能已變更" % (len(cells), CONFERENCE_CELLS))
        if _text(cells[0]) != ticker:
            continue
        dates = _roc_dates(cells[2])
        if not dates:
            continue
        slides = [PDF_NAME.search(cells[i]) for i in (6, 7)]
        website = HREF.search(cells[8])
        output.append({
            "date": dates[0], "end_date": dates[1] if len(dates) > 1 else None,
            "time": _text(cells[3]) or "", "location": _text(cells[4]), "summary": _text(cells[5]),
            "slides_zh": SLIDES_URL % slides[0].group(1) if slides[0] else None,
            "slides_en": SLIDES_URL % slides[1].group(1) if slides[1] else None,
            "website": website.group(1) if website else None,
        })
    return output


def _request_conferences(ticker, market, roc_year):
    form = {"encodeURIComponent": 1, "step": 1, "firstin": 1, "off": 1, "TYPEK": fetch_fundamentals.MOPS_TYPEK[market],
            "year": roc_year, "month": "all", "co_id": ticker}
    page = fetch_fundamentals.get_text(CONFERENCE_URL, data=form)
    if page is None:
        raise RuntimeError("法說會查詢回 404")
    return parse_conferences(page, ticker)


def sync_conferences(conn, ticker, today=None):
    """今年與去年、兩個市場都查（不必知道市場別），落庫。回傳筆數。"""
    today = today or date.today()
    found = []
    for market in fetch_fundamentals.MARKETS:
        for year in (today.year, today.year - 1):
            found += _request_conferences(ticker, market, year - 1911)
            time.sleep(fetch_fundamentals.REQUEST_GAP_SEC)
        if found:
            break   # 上市查到就不必再查上櫃
    conn.executemany(
        "INSERT OR REPLACE INTO investor_conferences (ticker, date, end_date, time, location, summary,"
        " slides_zh, slides_en, website, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(ticker, c["date"], c["end_date"], c["time"], c["location"], c["summary"], c["slides_zh"],
          c["slides_en"], c["website"], today.isoformat()) for c in found])
    conn.commit()
    return len(found)


def parse_news(xml_text, now=None, limit=NEWS_LIMIT, max_age_days=NEWS_MAX_AGE_DAYS):
    """RSS -> [{title, source, published, link}]，由新到舊、只留近 max_age_days 天。"""
    now = now or datetime.now(timezone.utc)
    # 系統 Python 的 expat 可能早於 2.4.1（沒有 entity 膨脹防護），RSS 本來就不需要 DTD
    if "<!DOCTYPE" in xml_text or "<!ENTITY" in xml_text:
        raise RuntimeError("新聞 RSS 含 DTD／entity 宣告，拒絕解析")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise RuntimeError("新聞 RSS 無法解析：%s" % error) from error
    items = []
    for node in root.iter("item"):
        try:
            published = parsedate_to_datetime(node.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if now - published > timedelta(days=max_age_days):
            continue
        items.append({"title": (node.findtext("title") or "").strip(),
                      "source": (node.findtext("source") or "").strip() or None,
                      "published": published.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
                      "link": (node.findtext("link") or "").strip()})
    items.sort(key=lambda item: item["published"], reverse=True)
    return items[:limit]


def fetch_news(ticker, name=None):
    """近期新聞。查詢字串用「代號 名稱」，避免同代號的其他東西（如型號）混進來。"""
    query = urllib.parse.quote(("%s %s" % (ticker, name or "")).strip())
    text = fetch_fundamentals.get_text(NEWS_URL % query)
    if text is None:
        raise RuntimeError("新聞 RSS 回 404")
    return parse_news(text)


def main():
    parser = argparse.ArgumentParser(description="個股法說會（落庫）與新聞（不落庫）")
    parser.add_argument("command", choices=("conferences", "news"))
    parser.add_argument("ticker")
    args = parser.parse_args()
    if not TICKER_PATTERN.match(args.ticker):
        parser.error("代號格式不符：%s" % args.ticker)

    conn = db.connect()
    try:
        if args.command == "conferences":
            print("法說會：%d 筆" % sync_conferences(conn, args.ticker))
        else:
            row = conn.execute("SELECT name FROM stock_names WHERE ticker = ?", (args.ticker,)).fetchone()
            print(json.dumps(fetch_news(args.ticker, row["name"] if row else None), ensure_ascii=False, indent=2))
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
