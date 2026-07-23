"""預測記錄、對帳、校準報告。

三個子命令：
  record    跑評分並落一筆 open 預測（thesis 由 LLM 提供，是唯一 LLM 欄位）
  reconcile 掃到期的 open 預測，抓真實價算報酬與命中
  report    輸出命中率與「按分數分層的校準度」

命中定義：偏多類看報酬>0、偏空類看報酬<0；中性不計入命中率（hit 留 NULL）。
持有期間有除權息但金額未知者一律標 needs_review，不用錯的還原價算報酬。
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

import db
import fetch_twse
import score as scoring

MIN_SAMPLE = 30              # 低於此樣本數，統計只當雜訊看
BULLISH = ("偏多", "強烈偏多")
BEARISH = ("偏空", "強烈偏空")
BUCKETS = [(75, 101, "75-100 強烈偏多"), (60, 75, "60-74 偏多"),
           (45, 60, "45-59 中性"), (30, 45, "30-44 偏空"), (0, 30, "0-29 強烈偏空")]


def cmd_record(conn, args):
    """評分 + 落一筆預測。"""
    fetch_twse.sync_ticker(conn, args.ticker)
    result = scoring.evaluate(conn, args.ticker)
    cursor = conn.execute(
        "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
        " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
        " signal, entry_low, entry_high, stop_loss, hard_rules, flags, thesis, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'open')",
        (result["date"], args.ticker, args.horizon, result["close"], result["adj_close"],
         result["final_score"], result["parts"]["trend"], result["parts"]["bias"],
         result["parts"]["support"], result["parts"]["volume"], result["parts"]["macd"],
         result["parts"]["rsi"], result["signal"], result["entry_low"], result["entry_high"],
         result["stop_loss"], json.dumps(result["hard_rules"], ensure_ascii=False),
         json.dumps(result["flags"], ensure_ascii=False), args.thesis))
    conn.commit()
    result["prediction_id"] = cursor.lastrowid
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _exdiv_unknown_in_window(conn, ticker, start_date, end_date):
    """持有期間是否存在「偵測到除權息但查無金額」的日子。"""
    rows = conn.execute(
        "SELECT q.date FROM daily_quotes q LEFT JOIN dividends d"
        "  ON d.ticker = q.ticker AND d.ex_date = q.date"
        " WHERE q.ticker = ? AND q.is_exdiv = 1 AND q.date > ? AND q.date <= ?"
        "   AND d.ex_date IS NULL", (ticker, start_date, end_date)).fetchall()
    return [r["date"] for r in rows]


def _first_quote_on_or_after(conn, ticker, target_date):
    return conn.execute(
        "SELECT date, close, adj_close FROM daily_quotes"
        " WHERE ticker = ? AND date >= ? ORDER BY date LIMIT 1",
        (ticker, target_date)).fetchone()


def _resolve_one(conn, row):
    """對帳單筆。回傳狀態字串。"""
    due = (datetime.strptime(row["created_at"], "%Y-%m-%d")
           + timedelta(days=row["horizon_days"])).strftime("%Y-%m-%d")
    quote = _first_quote_on_or_after(conn, row["ticker"], due)
    if quote is None:
        return "pending"

    unknown = _exdiv_unknown_in_window(conn, row["ticker"], row["created_at"], quote["date"])
    if unknown:
        conn.execute("UPDATE predictions SET status='needs_review', resolve_date=?,"
                     " close_at_resolve=? WHERE id=?",
                     (quote["date"], quote["close"], row["id"]))
        return "needs_review"

    adj_end = quote["adj_close"] or quote["close"]
    return_pct = (adj_end / row["adj_close_at_pred"] - 1.0) * 100
    hit = None
    if row["signal"] in BULLISH:
        hit = 1 if return_pct > 0 else 0
    elif row["signal"] in BEARISH:
        hit = 1 if return_pct < 0 else 0
    conn.execute(
        "UPDATE predictions SET status='resolved', resolve_date=?, close_at_resolve=?,"
        " adj_close_at_resolve=?, return_pct=?, hit=? WHERE id=?",
        (quote["date"], quote["close"], adj_end, round(return_pct, 4), hit, row["id"]))
    return "resolved"


def cmd_reconcile(conn, args):
    """抓新資料後，對帳所有到期的 open 預測。"""
    open_rows = conn.execute(
        "SELECT * FROM predictions WHERE status = 'open' ORDER BY created_at").fetchall()
    if not open_rows:
        print("沒有待對帳的預測")
        return
    for ticker in sorted({r["ticker"] for r in open_rows}):
        summary = fetch_twse.sync_ticker(conn, ticker)
        if summary["unadjusted_exdiv"]:
            print("[warn] %s 除權息金額未知：%s"
                  % (ticker, ", ".join(summary["unadjusted_exdiv"])), file=sys.stderr)

    tally = {}
    for row in open_rows:
        status = _resolve_one(conn, row)
        tally[status] = tally.get(status, 0) + 1
    conn.commit()
    print("對帳完成：" + "、".join("%s %d 筆" % (k, v) for k, v in sorted(tally.items())))


def _calibration_rows(conn):
    return conn.execute(
        "SELECT * FROM predictions WHERE status = 'resolved'").fetchall()


def _bucket_stats(rows):
    """按分數分層算命中率——校準度的核心：高分區是否真的比較準。"""
    output = []
    for low, high, label in BUCKETS:
        subset = [r for r in rows if low <= r["score"] < high and r["hit"] is not None]
        if not subset:
            continue
        hits = sum(r["hit"] for r in subset)
        avg_return = sum(r["return_pct"] for r in subset) / len(subset)
        output.append((label, len(subset), hits / len(subset) * 100, avg_return))
    return output


def _dimension_power(rows):
    """各維度預測力：該維度得分高於中位數 vs 低於中位數的平均報酬差。"""
    output = []
    for dimension in ("trend", "bias", "support", "volume", "macd", "rsi"):
        column = "s_" + dimension
        values = sorted(r[column] for r in rows)
        if len(values) < 4:
            continue
        median = values[len(values) // 2]
        high = [r["return_pct"] for r in rows if r[column] >= median]
        low = [r["return_pct"] for r in rows if r[column] < median]
        if not high or not low:
            continue
        output.append((dimension, sum(high) / len(high) - sum(low) / len(low),
                       len(high), len(low)))
    return sorted(output, key=lambda x: -x[1])


def cmd_report(conn, args):
    rows = _calibration_rows(conn)
    total = len(rows)
    print("=== Track Record 報告 ===")
    print("已對帳樣本：%d 筆" % total)
    if total < MIN_SAMPLE:
        print("\n⚠️  樣本數 %d < %d，以下統計在統計上不具意義，僅供觀察趨勢，"
              "不足以判斷分析品質。" % (total, MIN_SAMPLE))
    if not total:
        return

    directional = [r for r in rows if r["hit"] is not None]
    if directional:
        hits = sum(r["hit"] for r in directional)
        print("\n整體方向命中率：%.1f%% (%d/%d，中性 %d 筆不計入)"
              % (hits / len(directional) * 100, hits, len(directional),
                 total - len(directional)))

    print("\n--- 校準度（按分數分層）---")
    print("%-18s %6s %10s %12s" % ("分數區間", "樣本", "命中率", "平均報酬"))
    for label, count, hit_rate, avg_return in _bucket_stats(rows):
        print("%-18s %6d %9.1f%% %11.2f%%" % (label, count, hit_rate, avg_return))
    print("解讀：分數越高、命中率應越高。若高分區沒有明顯優勢，代表權重需要調整。")

    print("\n--- 各維度預測力（高分組平均報酬 − 低分組）---")
    for dimension, delta, n_high, n_low in _dimension_power(rows):
        print("  %-8s %+7.2f%%  (高分組 %d / 低分組 %d)" % (dimension, delta, n_high, n_low))
    print("解讀：數值為正代表該維度有預測力；長期為負或近零者，應調降權重。")

    pending = conn.execute(
        "SELECT status, COUNT(*) c FROM predictions WHERE status != 'resolved'"
        " GROUP BY status").fetchall()
    if pending:
        print("\n未結案：" + "、".join("%s %d 筆" % (r["status"], r["c"]) for r in pending))


def main():
    parser = argparse.ArgumentParser(description="台股預測記錄與校準追蹤")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="評分並記錄一筆預測")
    record.add_argument("ticker")
    record.add_argument("--horizon", type=int, default=30, help="時間框架天數，預設 30")
    record.add_argument("--thesis", default="", help="LLM 撰寫的判斷摘要")

    sub.add_parser("reconcile", help="對帳到期預測")
    sub.add_parser("report", help="輸出命中率與校準度")

    args = parser.parse_args()
    conn = db.connect()
    try:
        {"record": cmd_record, "reconcile": cmd_reconcile, "report": cmd_report}[args.command](conn, args)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
