"""每日評分快照：對觀察清單每日評分並存快照，提供趨勢與排行查詢。

子指令：
  run              抓最新日線 → 評最新交易日 → upsert（source=live）
  backfill -n N    用 score.evaluate(as_of) 回補過去 N 個交易日（source=backfill）
  trend <代號>     逐日總分與六分項，預設 60 個交易日
  rank             觀察清單最新分數、5 日 Δ、20 日 Δ，依分數排序

所有輸出均標示「未驗證」，不含「買入」「賣出」字眼。
"""

import argparse
import json
import sys
from datetime import datetime

import db
import fetch_twse
import score as scoring

# ── 常數 ────────────────────────────────────────────────────────────────────

DISCLAIMER = "【注意：以下分數未經驗證，不代表任何買賣建議】"
SOURCE_LIVE = "live"
SOURCE_BACKFILL = "backfill"


# ── 觀察清單 ─────────────────────────────────────────────────────────────────

def load_watchlist(conn):
    """取 predictions ∪ detail_views ∪ positions 的 ticker 聯集，排序後回傳。"""
    rows = conn.execute(
        "SELECT ticker FROM predictions"
        " UNION SELECT ticker FROM detail_views"
        " UNION SELECT ticker FROM positions"
        " ORDER BY ticker"
    ).fetchall()
    return [r["ticker"] for r in rows]


# ── DB 操作 ──────────────────────────────────────────────────────────────────

def _computed_at_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def upsert_score(conn, result, source):
    """將評分結果 upsert 至 daily_scores。

    原子操作保護 live 快照不被 backfill 覆蓋；同 source 同日重跑視為冪等更新。
    回傳 True 表示有寫入/更新，False 表示受 live 保護未寫入。
    """
    cursor = conn.execute(
        "INSERT INTO daily_scores"
        " (ticker, date, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
        "  signal, hard_rules, source, computed_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(ticker, date) DO UPDATE SET"
        "  score=excluded.score, s_trend=excluded.s_trend, s_bias=excluded.s_bias,"
        "  s_support=excluded.s_support, s_volume=excluded.s_volume,"
        "  s_macd=excluded.s_macd, s_rsi=excluded.s_rsi,"
        "  signal=excluded.signal, hard_rules=excluded.hard_rules,"
        "  source=excluded.source, computed_at=excluded.computed_at"
        " WHERE NOT (daily_scores.source = 'live' AND excluded.source = 'backfill')",
        (result["ticker"], result["date"],
         result["final_score"],
         result["parts"]["trend"], result["parts"]["bias"],
         result["parts"]["support"], result["parts"]["volume"],
         result["parts"]["macd"], result["parts"]["rsi"],
         result["signal"],
         json.dumps(result["hard_rules"], ensure_ascii=False),
         source, _computed_at_now())
    )
    return cursor.rowcount > 0


# ── run ──────────────────────────────────────────────────────────────────────

def cmd_run(conn, _args):
    """抓日線 → 評最新交易日 → upsert（source=live）。單檔失敗不中斷整批。"""
    tickers = load_watchlist(conn)
    print("觀察清單：%d 檔  %s" % (len(tickers), DISCLAIMER))
    success_count, skip_count, fail_tickers = 0, 0, []

    for ticker in tickers:
        try:
            fetch_twse.sync_ticker(conn, ticker)
            rows, _ = scoring.load_series(conn, ticker)
            if len(rows) < scoring.MIN_BARS:
                print("[skip] %s: 日線不足 %d 根（現有 %d 根），略過" % (
                    ticker, scoring.MIN_BARS, len(rows)), file=sys.stderr)
                skip_count += 1
                continue
            result = scoring.evaluate(conn, ticker)
            upsert_score(conn, result, SOURCE_LIVE)
            conn.commit()
            success_count += 1
        except (RuntimeError, ValueError, KeyError) as error:
            print("[fail] %s: %s" % (ticker, error), file=sys.stderr)
            fail_tickers.append(ticker)

    print("完成：成功 %d、資料不足略過 %d、失敗 %d" % (
        success_count, skip_count, len(fail_tickers)))
    if fail_tickers:
        print("失敗清單：%s" % ", ".join(fail_tickers), file=sys.stderr)
        sys.exit(1)


# ── backfill ─────────────────────────────────────────────────────────────────

def _trading_days_before(conn, days):
    """從 daily_quotes 取最近 days 個交易日（由舊到新），供回補使用。"""
    rows = conn.execute(
        "SELECT DISTINCT date FROM daily_quotes ORDER BY date DESC LIMIT ?",
        (days,)
    ).fetchall()
    return [r["date"] for r in reversed(rows)]


def cmd_backfill(conn, args):
    """用 score.evaluate(as_of) 回補過去 N 個交易日，source=backfill，不覆蓋 live。"""
    tickers = load_watchlist(conn)
    as_of_dates = _trading_days_before(conn, args.days)
    if not as_of_dates:
        print("DB 無日線資料，無法回補")
        return

    print("回補：%d 檔 × %d 個交易日  %s" % (len(tickers), len(as_of_dates), DISCLAIMER))
    success_count, skip_count, fail_count = 0, 0, 0
    fail_tickers = []

    for ticker in tickers:
        for as_of in as_of_dates:
            try:
                rows, _ = scoring.load_series(conn, ticker, as_of=as_of)
                if len(rows) < scoring.MIN_BARS:
                    skip_count += 1
                    continue
                result = scoring.evaluate(conn, ticker, as_of=as_of)
                inserted = upsert_score(conn, result, SOURCE_BACKFILL)
                if inserted:
                    success_count += 1
            except (RuntimeError, ValueError, KeyError) as error:
                print("[fail] %s %s: %s" % (ticker, as_of, error), file=sys.stderr)
                fail_count += 1
                if ticker not in fail_tickers:
                    fail_tickers.append(ticker)
        conn.commit()

    print("回補完成：成功 %d、資料不足略過 %d、失敗 %d" % (
        success_count, skip_count, fail_count))
    if fail_tickers:
        sys.exit(1)


# ── trend ────────────────────────────────────────────────────────────────────

def cmd_trend(conn, args):
    """印出單檔最近 days 個交易日的分項逐日分數，標示 source。"""
    rows = conn.execute(
        "SELECT date, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, source"
        " FROM daily_scores WHERE ticker = ? ORDER BY date DESC LIMIT ?",
        (args.ticker, args.days)
    ).fetchall()

    if not rows:
        print("%s 尚無評分快照" % args.ticker)
        return

    print(DISCLAIMER)
    print("%-12s %5s %5s %5s %5s %5s %5s %5s  %-8s  %s"
          % ("日期", "總分", "趨勢", "乖離", "支撐", "量能", "MACD", "RSI", "訊號", "來源"))
    print("-" * 72)
    for row in reversed(rows):
        src_mark = "●" if row["source"] == SOURCE_LIVE else "○"
        print("%-12s %5d %5d %5d %5d %5d %5d %5d  %-8s  %s%s"
              % (row["date"], row["score"],
                 row["s_trend"], row["s_bias"], row["s_support"],
                 row["s_volume"], row["s_macd"], row["s_rsi"],
                 row["signal"], src_mark, row["source"]))


# ── rank ─────────────────────────────────────────────────────────────────────

def _latest_score_row(conn, ticker):
    return conn.execute(
        "SELECT date, score FROM daily_scores WHERE ticker = ? ORDER BY date DESC LIMIT 1",
        (ticker,)
    ).fetchone()


def _score_n_rows_ago(conn, ticker, latest_date, n_rows):
    """取 latest_date 往前數第 n_rows 根的分數（以 daily_scores 的行數計）。"""
    row = conn.execute(
        "SELECT score FROM daily_scores WHERE ticker = ? AND date <= ?"
        " ORDER BY date DESC LIMIT 1 OFFSET ?",
        (ticker, latest_date, n_rows)
    ).fetchone()
    return row["score"] if row else None


def _delta_label(delta):
    if delta is None:
        return "  N/A"
    sign = "+" if delta >= 0 else ""
    return "%s%d" % (sign, delta)


def cmd_rank(conn, _args):
    """列出觀察清單最新分數、5 日 Δ、20 日 Δ，依分數由高至低排序。"""
    tickers = load_watchlist(conn)
    entries = []

    for ticker in tickers:
        latest = _latest_score_row(conn, ticker)
        if not latest:
            continue
        score_5d_ago = _score_n_rows_ago(conn, ticker, latest["date"], 5)
        score_20d_ago = _score_n_rows_ago(conn, ticker, latest["date"], 20)
        delta_5 = (latest["score"] - score_5d_ago) if score_5d_ago is not None else None
        delta_20 = (latest["score"] - score_20d_ago) if score_20d_ago is not None else None
        entries.append((ticker, latest["date"], latest["score"], delta_5, delta_20))

    if not entries:
        print("尚無任何評分快照")
        return

    entries.sort(key=lambda e: -e[2])
    print(DISCLAIMER)
    print("%-8s %-12s %5s %6s %6s" % ("代號", "最新日期", "分數", "5日Δ", "20日Δ"))
    print("-" * 46)
    for ticker, latest_date, score_val, d5, d20 in entries:
        print("%-8s %-12s %5d %6s %6s"
              % (ticker, latest_date, score_val, _delta_label(d5), _delta_label(d20)))


# ── CLI ──────────────────────────────────────────────────────────────────────

def _positive_int(value):
    """驗證參數為正整數（> 0），供 argparse 使用。"""
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("%r 不是有效整數" % value)
    if val <= 0:
        raise argparse.ArgumentTypeError("%r 必須為正整數（> 0）" % value)
    return val


def build_parser():
    parser = argparse.ArgumentParser(description="每日評分快照（未驗證）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="抓日線並對觀察清單評分，寫入今日快照（source=live）")

    backfill_cmd = sub.add_parser("backfill", help="回補過去 N 個交易日的快照（source=backfill）")
    backfill_cmd.add_argument("--days", type=_positive_int, default=60,
                              metavar="N", help="回補交易日數，預設 60")

    trend_cmd = sub.add_parser("trend", help="逐日分數趨勢")
    trend_cmd.add_argument("ticker", help="股票代號")
    trend_cmd.add_argument("--days", type=_positive_int, default=60, metavar="N",
                           help="顯示最近 N 個交易日，預設 60")

    sub.add_parser("rank", help="觀察清單排行（最新分數與 5/20 日 Δ）")
    return parser


def main():
    args = build_parser().parse_args()
    conn = db.connect()
    try:
        dispatch = {
            "run": cmd_run,
            "backfill": cmd_backfill,
            "trend": cmd_trend,
            "rank": cmd_rank,
        }
        dispatch[args.command](conn, args)
    except (RuntimeError, ValueError, KeyError) as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
