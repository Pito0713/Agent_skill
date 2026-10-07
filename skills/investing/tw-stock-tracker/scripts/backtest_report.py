"""回測報告：分數分層表現、高低分組差距、逐季趨勢。由 backtest.py report 呼叫。"""

import json
import statistics
from collections import Counter
from datetime import datetime

import track

MIN_GROUP = 5           # 組內樣本低於此數只標示不足，不給數字
WARNING = ("⚠️  標的是現在挑的（選股偏差），相鄰週的報酬窗口互相重疊：結果會比真實預測樂觀。\n"
           "    這是歷史重演，不是預測；也不會拿來校準門檻。以下皆為描述性統計，沒有信賴區間。")


def load_run(conn, run_id):
    """預設讀最新一次跑完的 run；中途失敗的 run 只有指定 --run 才讀。"""
    if run_id is None:
        row = conn.execute("SELECT * FROM backtest_runs WHERE status = 'complete'"
                           " ORDER BY id DESC LIMIT 1").fetchone()
    else:
        row = conn.execute("SELECT * FROM backtest_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise RuntimeError("找不到回測結果：先跑 python3 backtest.py run")
    return row


def load_samples(conn, run_id, horizon):
    return conn.execute("SELECT * FROM backtest_samples WHERE run_id = ? AND horizon_days = ?",
                        (run_id, horizon)).fetchall()


def summarize(returns):
    """(樣本數, 上漲比例 %, 平均 %, 中位數 %)；空清單回 None。"""
    if not returns:
        return None
    up_ratio = sum(1 for value in returns if value > 0) / len(returns) * 100
    return len(returns), up_ratio, statistics.mean(returns), statistics.median(returns)


def bucket_stats(samples):
    output = []
    for low, high, label in track.BUCKETS:
        stats = summarize([r["return_pct"] for r in samples if low <= r["score"] < high])
        if stats:
            output.append((label, stats))
    return output


def score_spread(samples, bull, bear):
    """高分組（≥ bull）平均報酬 − 低分組（< bear）。任一組不足 MIN_GROUP 回 None。"""
    high = [r["return_pct"] for r in samples if r["score"] >= bull]
    low = [r["return_pct"] for r in samples if r["score"] < bear]
    if len(high) < MIN_GROUP or len(low) < MIN_GROUP:
        return None, len(high), len(low)
    return statistics.mean(high) - statistics.mean(low), len(high), len(low)


def week_of(day):
    return datetime.strptime(day, "%Y-%m-%d").isocalendar()[:2]


def same_week_spreads(samples, bull, bear):
    """[(週, 高分組平均 − 低分組平均)]，只取兩組都有樣本的週。

    同週內比較，兩組面對同一段大盤，排除「高分樣本剛好集中在多頭時期」的時點差異。
    """
    by_week = {}
    for row in samples:
        by_week.setdefault(week_of(row["as_of"]), []).append(row)
    output = []
    for week, rows in sorted(by_week.items()):
        high = [r["return_pct"] for r in rows if r["score"] >= bull]
        low = [r["return_pct"] for r in rows if r["score"] < bear]
        if high and low:
            output.append((week, statistics.mean(high) - statistics.mean(low)))
    return output


def summarize_spreads(spreads):
    """(週數, 高分組勝出週比例 %, 平均差 %)；週數不足 MIN_GROUP 回 None。"""
    if len(spreads) < MIN_GROUP:
        return None
    values = [value for _, value in spreads]
    return (len(values), sum(1 for v in values if v > 0) / len(values) * 100,
            statistics.mean(values))


def quarter_of(day):
    return "%sQ%d" % (day[:4], (int(day[5:7]) - 1) // 3 + 1)


def quarterly_spreads(samples, bull, bear):
    """逐季的同週比較摘要：[(季, summarize_spreads 結果或 None, 週數)]。"""
    by_quarter = {}
    for week, value in same_week_spreads(samples, bull, bear):
        monday = datetime.fromisocalendar(week[0], week[1], 1).strftime("%Y-%m-%d")
        by_quarter.setdefault(quarter_of(monday), []).append((week, value))
    return [(quarter, summarize_spreads(spreads), len(spreads))
            for quarter, spreads in sorted(by_quarter.items())]


def print_horizon(samples, horizon, bull, bear):
    included = [r for r in samples if r["excluded_reason"] is None]
    overall = summarize([r["return_pct"] for r in included])
    weeks = len({r["as_of"] for r in included})
    print("\n--- 持有 %d 天（%d 筆、%d 個評估日）---" % (horizon, len(included), weeks))
    if overall is None:
        print("  無可用樣本")
        return
    print("  %-16s %6s %8s %9s %9s %10s" % ("分數區間", "樣本", "上漲比例", "平均", "中位數", "相對全部"))
    for label, (count, up_ratio, mean, median) in bucket_stats(included):
        if count < MIN_GROUP:
            print("  %-16s %6d  樣本不足" % (label, count))
            continue
        print("  %-16s %6d %7.1f%% %+8.2f%% %+8.2f%% %+9.2f%%"
              % (label, count, up_ratio, mean, median, mean - overall[2]))
    count, up_ratio, mean, median = overall
    print("  %-16s %6d %7.1f%% %+8.2f%% %+8.2f%%" % ("全部（對照）", count, up_ratio, mean, median))
    spread, n_high, n_low = score_spread(included, bull, bear)
    if spread is None:
        print("  高分組 − 低分組（全期混合）：樣本不足（%d / %d）" % (n_high, n_low))
    else:
        print("  高分組（≥%d）− 低分組（<%d），全期混合：%+.2f%%（%d / %d 筆）"
              % (bull, bear, spread, n_high, n_low))
    week_summary = summarize_spreads(same_week_spreads(included, bull, bear))
    if week_summary is None:
        print("  同週比較：可比週數不足 %d" % MIN_GROUP)
    else:
        print("  同週比較：%d 週中高分組勝出 %.0f%%，平均差 %+.2f%%" % week_summary)


VALUATION_BANDS = (("低位 <33", 0, 33), ("中位 33-67", 33, 67), ("高位 ≥67", 67, 101))


def valuation_band(percentile):
    if percentile is None:
        return "無資料"
    return next(label for label, low, high in VALUATION_BANDS if low <= percentile < high)


def score_band(score_value, bull, bear):
    if score_value >= bull:
        return "高分 ≥%d" % bull
    return "低分 <%d" % bear if score_value < bear else "中性"


def valuation_grid(samples, bull, bear):
    """{(分數組, 本益比百分位組): [報酬...]}。"""
    grid = {}
    for row in samples:
        key = (score_band(row["score"], bull, bear), valuation_band(row["pe_percentile"]))
        grid.setdefault(key, []).append(row["return_pct"])
    return grid


def print_valuation_grid(samples, horizon, bull, bear):
    included = [r for r in samples if r["excluded_reason"] is None]
    grid = valuation_grid(included, bull, bear)
    columns = [label for label, _, _ in VALUATION_BANDS] + ["無資料"]
    print("\n--- 技術分 × 本益比百分位（相對自身近 3 年；持有 %d 天平均報酬，括號為筆數）---" % horizon)
    print("  %-10s" % "" + "".join("%16s" % column for column in columns))
    for band in ("高分 ≥%d" % bull, "中性", "低分 <%d" % bear):
        cells = []
        for column in columns:
            returns = grid.get((band, column), [])
            cells.append("%16s" % ("—(%d)" % len(returns) if len(returns) < MIN_GROUP
                                   else "%+.2f%% (%d)" % (statistics.mean(returns), len(returns))))
        print("  %-10s" % band + "".join(cells))
    print("解讀：百分位只表示相對該股自身歷史的位置，不是貴或便宜的判斷。格子未控制大盤時點，\n"
          "      筆數 < %d 不給數字；虧損股與 ETF 沒有本益比，歸「無資料」。" % MIN_GROUP)


def print_quarterly(samples, horizon, bull, bear):
    included = [r for r in samples if r["excluded_reason"] is None]
    print("\n--- 逐季同週比較（持有 %d 天）---" % horizon)
    for quarter, summary, weeks in quarterly_spreads(included, bull, bear):
        if summary is None:
            print("  %s  可比週數 %d，不足 %d" % (quarter, weeks, MIN_GROUP))
        else:
            print("  %s  %2d 週  高分組勝出 %3.0f%%  平均差 %+6.2f%%" % (quarter, *summary))
    print("解讀：同週比較已排除大盤時點差異，但未排除個股組成差異，也沒有信賴區間。\n"
          "      多數季度勝出比例明顯高於 50% 才算一致；正負交替代表評分只在某些行情有效。")


def cmd_report(conn, args):
    run = load_run(conn, args.run)
    params = json.loads(run["params"])
    bull, bear = params["bull"], params["bear"]
    tickers = json.loads(run["tickers"])
    print("=== 回測報告（run %d，%s 執行）===" % (run["id"], run["created_at"]))
    skipped = json.loads(run["skipped"])
    print("評估期間 %s ~ %s，指定 %d 檔，略過 %d 檔"
          % (run["start_date"], run["end_date"], len(tickers), len(skipped)))
    for item in skipped:
        print("  略過 %s：%s" % (item["ticker"], item["reason"]))
    if run["status"] != "complete":
        print("⚠️  這次 run 沒有跑完（status=%s），樣本不完整" % run["status"])
    print(WARNING)
    for horizon in params["horizons"]:
        samples = load_samples(conn, run["id"], horizon)
        excluded = Counter(r["excluded_reason"] for r in samples if r["excluded_reason"])
        print_horizon(samples, horizon, bull, bear)
        if excluded:
            print("  排除：" + "、".join("%s %d 筆" % item for item in sorted(excluded.items())))
    focus = load_samples(conn, run["id"], args.horizon)
    print_quarterly(focus, args.horizon, bull, bear)
    print_valuation_grid(focus, args.horizon, bull, bear)
