"""回測的排名相關係數（Rank IC）統計。純函式，不碰 DB；只用標準函式庫，不需 scipy。

Rank IC：每個評估週，橫斷面上「分數排名」與「之後報酬排名」的相關係數。
構想借自 qlib（contrib/eva/alpha.py 的 calc_ic、workflow/record_temp.py 的 ICIR）。
"""

import math
import statistics
from datetime import datetime

MIN_CROSS_SECTION = 5   # 當週有效標的少於此數不算 IC，相關係數太不穩
SIGNIFICANT_T = 2.0
MIN_EFFECTIVE_WEEKS = 10   # 重疊修正後的有效週數低於此，t 值不下結論


def average_ranks(values):
    """1 起算的名次，同值取平均名次（評分多為整數，同分很常見）。"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def pearson(xs, ys):
    """樣本不足或任一邊沒有變異（如當週全部同分）回 None。"""
    if len(xs) < 2:
        return None
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denominator = math.sqrt(sum(d * d for d in dx) * sum(d * d for d in dy))
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denominator


def spearman(xs, ys):
    return pearson(average_ranks(xs), average_ranks(ys))


def week_of(day):
    return datetime.strptime(day, "%Y-%m-%d").isocalendar()[:2]


def weekly_ic(samples, value_key, return_key):
    """[(週, Rank IC)]。samples 為已排除無效報酬的列；不足 MIN_CROSS_SECTION 或無變異的週略過。"""
    by_week = {}
    for row in samples:
        by_week.setdefault(week_of(row["as_of"]), []).append(row)
    output = []
    for week, rows in sorted(by_week.items()):
        if len(rows) < MIN_CROSS_SECTION:
            continue
        ic = spearman([r[value_key] for r in rows], [r[return_key] for r in rows])
        if ic is not None:
            output.append((week, ic))
    return output


def summarize_ic(weekly, horizon_days):
    """dict：weeks、mean、std、icir、positive_ratio、overlap、t；不足 2 週或零變異回 None。

    相鄰週的持有期間重疊時，週與週的 IC 不獨立。以「持有跨幾週」把有效週數打折：
    t = ICIR × √(週數 ÷ 重疊倍數)。比 Newey-West 粗略，但方向保守。
    """
    values = [ic for _, ic in weekly]
    if len(values) < 2:
        return None
    std = statistics.stdev(values)
    if std == 0:
        return None
    mean = statistics.mean(values)
    overlap = math.ceil(horizon_days / 7)
    icir = mean / std
    return {"weeks": len(values), "mean": mean, "std": std, "icir": icir,
            "positive_ratio": sum(1 for v in values if v > 0) / len(values) * 100,
            "overlap": overlap, "effective_weeks": len(values) / overlap,
            "t": icir * math.sqrt(len(values) / overlap)}


def verdict(summary):
    if summary is None:
        return "樣本不足"
    if summary["effective_weeks"] < MIN_EFFECTIVE_WEEKS:
        return "有效週數 %.1f 不足 %d，不下結論" % (summary["effective_weeks"], MIN_EFFECTIVE_WEEKS)
    return "統計上可分辨" if abs(summary["t"]) >= SIGNIFICANT_T else "無法和運氣區分"
