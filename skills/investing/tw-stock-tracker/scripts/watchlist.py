"""觀察清單的隱藏管理：手動隱藏／恢復，以及「連續一週偏空」自動隱藏。

子指令（寫入指令只在資料主機跑）：
  hide <代號> [--note 文字]   手動隱藏
  unhide <代號>               恢復
  list                        列出已隱藏的個股
  auto [--dry-run]            套用自動隱藏規則（daily_score.py run 結束時也會自動跑）

自動隱藏規則（使用者 2026-11-11 決定）：
  - 最近 STREAK_DAYS 個交易日每天都有評分快照，且每天的分數都低於「當天生效的偏空門檻」
    （score.load_thresholds，門檻校準後自動跟著變）；漏跑缺一天就不算
  - 有未平倉持股的個股永不自動隱藏（隱藏持股等於隱藏風險）；有未到期預測的照樣隱藏，對帳不受影響
  - 隱藏後停止每日評分，不會自動恢復，要用 unhide

隱藏是顯示偏好，不是判斷：分數未經驗證（ADR-031），隱藏不代表這檔會跌。
"""

import argparse
import sys
from datetime import datetime

import db
import fetch_twse
import score as scoring

STREAK_DAYS = 5
REASON_MANUAL = "manual"
REASON_AUTO_BEARISH = "auto_bearish"
REASON_LABELS = {REASON_MANUAL: "手動", REASON_AUTO_BEARISH: "連續一週偏空"}


def hidden_tickers(conn):
    """已隱藏的代號集合。"""
    return {row["ticker"] for row in conn.execute("SELECT ticker FROM hidden_tickers")}


def list_hidden(conn):
    rows = conn.execute("SELECT * FROM hidden_tickers ORDER BY hidden_at DESC, ticker").fetchall()
    return [dict(row) for row in rows]


def hide(conn, ticker, reason=REASON_MANUAL, note=None):
    """隱藏一檔；已隱藏則保留原紀錄（不覆蓋原因與時間），回傳是否新增。"""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO hidden_tickers (ticker, hidden_at, reason, note) VALUES (?, ?, ?, ?)",
        (ticker, datetime.now().strftime("%Y-%m-%d %H:%M"), reason, note))
    conn.commit()
    return cursor.rowcount == 1


def unhide(conn, ticker):
    """恢復一檔，回傳是否原本有隱藏。"""
    cursor = conn.execute("DELETE FROM hidden_tickers WHERE ticker = ?", (ticker,))
    conn.commit()
    return cursor.rowcount == 1


def recent_trading_days(conn, count=STREAK_DAYS):
    """daily_quotes 中最近 count 個交易日，由舊到新。"""
    rows = conn.execute("SELECT DISTINCT date FROM daily_quotes ORDER BY date DESC LIMIT ?", (count,)).fetchall()
    return [row["date"] for row in reversed(rows)]


def _open_position_tickers(conn):
    return {row["ticker"] for row in conn.execute("SELECT DISTINCT ticker FROM positions WHERE status = 'open'")}


def is_bearish_streak(conn, ticker, days):
    """days 內每天都有快照，且每天分數都低於當天生效的偏空門檻。"""
    rows = conn.execute(
        "SELECT date, score FROM daily_scores WHERE ticker = ? AND date >= ? AND date <= ?",
        (ticker, days[0], days[-1])).fetchall()
    scores = {row["date"]: row["score"] for row in rows}
    if any(day not in scores for day in days):
        return False
    return all(scores[day] < scoring.load_thresholds(conn, day)["bear"] for day in days)


def find_auto_hide_candidates(conn, tickers):
    """在 tickers 中找出符合自動隱藏規則的代號（已隱藏、持股中的排除）。"""
    days = recent_trading_days(conn)
    if len(days) < STREAK_DAYS:
        return []
    excluded = hidden_tickers(conn) | _open_position_tickers(conn)
    return [ticker for ticker in tickers if ticker not in excluded and is_bearish_streak(conn, ticker, days)]


def apply_auto_hide(conn, tickers, dry_run=False):
    """套用自動隱藏，回傳被隱藏（或 dry-run 時會被隱藏）的代號。"""
    candidates = find_auto_hide_candidates(conn, tickers)
    if dry_run:
        return candidates
    note = "連續 %d 個交易日低於偏空門檻（%s 起）" % (STREAK_DAYS, recent_trading_days(conn)[0]) if candidates else None
    return [ticker for ticker in candidates if hide(conn, ticker, REASON_AUTO_BEARISH, note)]


# ── CLI ──────────────────────────────────────────────────────────────────────

def cmd_hide(conn, args):
    if hide(conn, args.ticker, REASON_MANUAL, args.note):
        print("已隱藏 %s：不再出現在評分排行與個股詳情區塊，每日評分也不再抓它" % args.ticker)
    else:
        print("%s 原本就已隱藏" % args.ticker)


def cmd_unhide(conn, args):
    if unhide(conn, args.ticker):
        print("已恢復 %s：下次每日評分開始重新抓取（隱藏期間的分數會有空缺）" % args.ticker)
    else:
        print("%s 沒有被隱藏" % args.ticker)


def cmd_list(conn, _args):
    items = list_hidden(conn)
    if not items:
        print("沒有隱藏的個股")
        return
    for item in items:
        print("%-8s %-16s %-8s %s" % (item["ticker"], item["hidden_at"],
                                      REASON_LABELS.get(item["reason"], item["reason"]), item["note"] or ""))


def cmd_auto(conn, args):
    import daily_score  # 延遲載入：daily_score 也 import 本模組
    hidden = apply_auto_hide(conn, daily_score.load_watchlist(conn), dry_run=args.dry_run)
    prefix = "[dry-run] 會隱藏" if args.dry_run else "已自動隱藏"
    print("%s %d 檔%s" % (prefix, len(hidden), "：" + ", ".join(hidden) if hidden else ""))


def build_parser():
    parser = argparse.ArgumentParser(description="觀察清單隱藏管理")
    sub = parser.add_subparsers(dest="command", required=True)
    hide_cmd = sub.add_parser("hide", help="手動隱藏")
    hide_cmd.add_argument("ticker")
    hide_cmd.add_argument("--note", help="備註")
    unhide_cmd = sub.add_parser("unhide", help="恢復")
    unhide_cmd.add_argument("ticker")
    sub.add_parser("list", help="列出已隱藏")
    auto_cmd = sub.add_parser("auto", help="套用連續一週偏空的自動隱藏")
    auto_cmd.add_argument("--dry-run", action="store_true", help="只列出會被隱藏的，不寫入")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "ticker", None) and not fetch_twse.TICKER_PATTERN.match(args.ticker):
        parser.error("代號格式不符：%s" % args.ticker)
    conn = db.connect()
    try:
        {"hide": cmd_hide, "unhide": cmd_unhide, "list": cmd_list, "auto": cmd_auto}[args.command](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
