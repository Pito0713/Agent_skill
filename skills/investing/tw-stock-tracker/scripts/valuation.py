"""估值快照：本益比、淨值比、殖利率，以及相對該股自身近 3 年的百分位。

只描述「目前在自己歷史的哪個位置」，不判斷貴或便宜、不參與 100 分評分——
跟大盤／類股背景欄位一樣，先記錄，等回測或 track record 證明有預測力再談。
只讀 DB；資料由 fetch_valuation 負責。百分位只用 as_of 以前的歷史，回測可直接沿用。
"""

from datetime import date, timedelta

LOOKBACK_DAYS = 3 * 365
MIN_HISTORY = 52            # 至少 52 個不同的週（約 1 年）；不足就不給百分位
STALE_DAYS = 7              # 最近一筆估值距 as_of 超過此天數視為無資料
METRICS = (("pe", "本益比", "pe_percentile"), ("pb", "股價淨值比", "pb_percentile"),
           ("dividend_yield", "殖利率", "yield_percentile"))


def _weekly_history(conn, ticker, column, current):
    """近 3 年、current 之前的歷史值，每個 ISO 週只留最後一筆。

    週回補與 record 時補的每日資料會混在一起；不去重的話，記錄頻繁的期間權重被放大，
    且 52 筆每日資料只涵蓋兩個多月，卻會被當成一年歷史。
    """
    by_week = {}
    for day, value in conn.execute(
            "SELECT date, %s FROM valuations WHERE ticker = ? AND date > ? AND date < ?"
            " AND %s IS NOT NULL ORDER BY date" % (column, column),
            (ticker, (date.fromisoformat(current["date"]) - timedelta(days=LOOKBACK_DAYS)).isoformat(),
             current["date"])):
        by_week[date.fromisoformat(day).isocalendar()[:2]] = value
    return list(by_week.values())


def _percentile(conn, ticker, column, current):
    """current 在歷史值中的百分位（≤ current 的比例）。回傳 (百分位或 None, 歷史週數)。"""
    history = _weekly_history(conn, ticker, column, current)
    if len(history) < MIN_HISTORY or current[column] is None:
        return None, len(history)
    return round(sum(1 for value in history if value <= current[column]) / len(history) * 100, 1), \
        len(history)


def snapshot(conn, ticker, as_of):
    """as_of（含）以前最近一筆估值與百分位；查無或過舊回 None。"""
    current = conn.execute(
        "SELECT * FROM valuations WHERE ticker = ? AND date <= ? AND date >= ?"
        " ORDER BY date DESC LIMIT 1",
        (ticker, as_of, (date.fromisoformat(as_of) - timedelta(days=STALE_DAYS)).isoformat())
    ).fetchone()
    if current is None:
        return None
    result = {"date": current["date"], "fiscal_period": current["fiscal_period"]}
    for column, _, percentile_key in METRICS:
        percentile, history_n = _percentile(conn, ticker, column, current)
        result[column] = current[column]
        result[percentile_key] = percentile
        result[column + "_history_n"] = history_n
    return result


def percentile_values(snap):
    """(pe_percentile, pb_percentile, yield_percentile)；無快照全為 None。"""
    return tuple(snap[key] if snap else None for _, _, key in METRICS)


def attach_to_prediction(conn, prediction_id, snap):
    """把估值與百分位寫進 predictions。不 commit：由呼叫端與預測本身同一筆交易提交，
    避免預測已落庫、估值寫入失敗時，重跑產生重複預測。"""
    if not snap:
        return
    conn.execute(
        "UPDATE predictions SET pe = ?, pb = ?, dividend_yield = ?, pe_percentile = ?,"
        " pb_percentile = ?, yield_percentile = ? WHERE id = ?",
        (snap["pe"], snap["pb"], snap["dividend_yield"], *percentile_values(snap), prediction_id))


def describe(snap):
    """一行文字，如「本益比 18.20（近 3 年第 35.0 百分位）｜…」。"""
    if snap is None:
        return "估值：無資料（ETF、尚未抓取，或最近一週沒有估值）"
    parts = []
    for column, label, percentile_key in METRICS:
        value = snap[column]
        if value is None:
            parts.append("%s —（虧損或無資料）" % label)
        elif snap[percentile_key] is None:
            parts.append("%s %.2f（歷史 %d 週，不足 %d 週不給百分位）"
                         % (label, value, snap[column + "_history_n"], MIN_HISTORY))
        else:
            parts.append("%s %.2f（近 3 年第 %.0f 百分位）" % (label, value, snap[percentile_key]))
    return "估值（%s）：%s" % (snap["date"], "｜".join(parts))
