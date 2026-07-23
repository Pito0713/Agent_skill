"""台股六維評分 v1 — 確定性計算，不含任何 LLM 判斷。

配分定義見 references/scoring-rubric.md。權重是 v1 假設，
待 track record 累積後用 track.py report 的分維表現回頭校準。

用法：python3 score.py 2330 [--json]
"""

import argparse
import json
import sys

import db
import indicators

MIN_BARS = 60                # 少於此根數不出評分（MA60 無法成立）
LIMIT_UP_RATIO = 1.095       # 台股漲跌幅 10%，留 0.5% 容差判定觸及漲停
NEUTRAL_CAP = 59             # 硬規則壓制後的分數上限（= 中性區間頂端）

SIGNAL_BANDS = [(75, "強烈偏多"), (60, "偏多"), (45, "中性"), (30, "偏空"), (0, "強烈偏空")]


def load_series(conn, ticker):
    """讀出日線，並標記序列中是否存在「偵測到除權息但查無金額」的日子。

    不可用 adj_close == close 推斷未還原：還原是往回調整，
    最近一次除權息之後的日期本來就維持原值，那樣會誤判為未知。
    """
    rows = conn.execute(
        "SELECT date, open, high, low, close, adj_close, volume, is_exdiv"
        " FROM daily_quotes WHERE ticker = ? ORDER BY date", (ticker,)).fetchall()
    unknown = conn.execute(
        "SELECT COUNT(*) FROM daily_quotes q LEFT JOIN dividends d"
        "  ON d.ticker = q.ticker AND d.ex_date = q.date"
        " WHERE q.ticker = ? AND q.is_exdiv = 1 AND d.ex_date IS NULL",
        (ticker,)).fetchone()[0]
    return rows, (["has_unadjusted_exdiv"] if unknown else [])


def score_trend(close, ma5, ma20, ma60):
    """趨勢 25 分：站上月線 10 + 短中多頭 8 + 中長多頭 7。"""
    points = 0
    if ma20 and close > ma20:
        points += 10
    if ma5 and ma20 and ma5 > ma20:
        points += 8
    if ma20 and ma60 and ma20 > ma60:
        points += 7
    return points


def score_bias(bias_pct):
    """乖離 20 分：進場點核心，適度負乖離最佳、追高歸零。"""
    for threshold, points in [(-12, 8), (-8, 14), (-3, 20), (0, 17),
                              (3, 12), (8, 7), (15, 3)]:
        if bias_pct < threshold:
            return points
    return 0


def score_support(close, low60, high60):
    """支撐/壓力 15 分：貼近支撐 10 + 上檔空間 5。"""
    points = 0
    distance = (close - low60) / low60 * 100 if low60 else 999
    for threshold, value in [(5, 10), (12, 8), (25, 5), (40, 2)]:
        if distance <= threshold:
            points += value
            break
    room = (high60 - close) / close * 100 if close else 0
    for threshold, value in [(15, 5), (8, 3), (3, 1)]:
        if room >= threshold:
            points += value
            break
    return points


def score_volume(close, prev_close, volume, avg_volume):
    """量能 15 分：價量配合最佳，價漲量縮（背離）與價跌量增（賣壓）扣分。"""
    if not avg_volume:
        return 8
    ratio = volume / avg_volume
    rising = close > prev_close
    falling = close < prev_close
    if rising and ratio > 1.2:
        return 15
    if rising and ratio >= 0.8:
        return 11
    if falling and ratio < 0.8:
        return 11
    if rising:
        return 6
    if falling and ratio > 1.2:
        return 2
    return 8


def score_macd(dif, dea):
    """MACD 15 分：零軸之上金叉最強，零軸之下死叉最弱。"""
    if dif is None or dea is None:
        return 0
    if dif > dea:
        return 15 if dif > 0 else 11
    return 6 if dif > 0 else 0


def score_rsi(value):
    """RSI 10 分：中性偏低最適合進場，超買歸零。"""
    if value is None:
        return 0
    for threshold, points in [(20, 5), (30, 7), (40, 9), (60, 10), (70, 6), (80, 3)]:
        if value < threshold:
            return points
    return 0


def to_signal(total):
    for threshold, label in SIGNAL_BANDS:
        if total >= threshold:
            return label
    return "強烈偏空"


def _downgrade(signal):
    labels = [label for _, label in SIGNAL_BANDS]
    index = labels.index(signal)
    return labels[min(index + 1, len(labels) - 1)]


def apply_hard_rules(result, rsi_value, bias_pct, rows, avg_volume):
    """硬規則：觸發即壓制訊號，避免評分把明顯高風險狀態講成好進場點。"""
    triggered = []
    latest, previous = rows[-1], rows[-2]

    if rsi_value is not None and rsi_value > 80:
        triggered.append("RSI>80 超買，訊號壓至中性")
        result["score_capped"] = min(result["score"], NEUTRAL_CAP)
    if bias_pct > 15:
        triggered.append("正乖離>15% 追高，訊號壓至中性")
        result["score_capped"] = min(result.get("score_capped", result["score"]), NEUTRAL_CAP)
    if latest["high"] >= previous["close"] * LIMIT_UP_RATIO:
        triggered.append("當日觸及漲停，流動性失真，不出進場區間")
        result["entry_blocked"] = True
    if avg_volume and latest["volume"] < avg_volume * 0.5:
        triggered.append("量能不足均量50%，訊號降一級")
        result["downgrade"] = True
    return triggered


def evaluate(conn, ticker):
    """回傳完整評分結果 dict。資料不足直接拋錯，不出半套判斷。"""
    rows, flags = load_series(conn, ticker)
    if len(rows) < MIN_BARS:
        raise RuntimeError("%s 僅 %d 根日線，少於 %d 根，不出評分" % (ticker, len(rows), MIN_BARS))

    closes = [r["adj_close"] or r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    volumes = [r["volume"] for r in rows]

    ma5, ma20, ma60 = (indicators.sma(closes, n) for n in (5, 20, 60))
    bias_pct = (closes[-1] - ma20) / ma20 * 100 if ma20 else 0.0
    low60, high60 = min(lows[-60:]), max(highs[-60:])
    avg_volume = indicators.sma(volumes, 20)
    rsi_value = indicators.rsi(closes, 14)
    dif, dea, _ = indicators.macd(closes)
    atr_value = indicators.atr(highs, lows, closes, 14)

    parts = {
        "trend": score_trend(closes[-1], ma5, ma20, ma60),
        "bias": score_bias(bias_pct),
        "support": score_support(closes[-1], low60, high60),
        "volume": score_volume(closes[-1], closes[-2], volumes[-1], avg_volume),
        "macd": score_macd(dif, dea),
        "rsi": score_rsi(rsi_value),
    }
    result = {"ticker": ticker, "date": rows[-1]["date"], "close": rows[-1]["close"],
              "adj_close": closes[-1], "parts": parts, "score": sum(parts.values()),
              "flags": flags}

    result["hard_rules"] = apply_hard_rules(result, rsi_value, bias_pct, rows, avg_volume)
    final_score = result.pop("score_capped", result["score"])
    signal = to_signal(final_score)
    if result.pop("downgrade", False):
        signal = _downgrade(signal)
    result["final_score"] = final_score
    result["signal"] = signal

    # 兩個價位各司其職：MA20 當回檔進場錨點，停損用 ATR 由進場價往下推。
    # （不用 min(MA20, low60) 當錨點：實測發現 MA20 幾乎恆大於 low60，
    #   會讓錨點永遠落在 60 日低點、進場區間遠離現價而失去意義。）
    blocked = result.pop("entry_blocked", False)
    result["entry_blocked"] = blocked
    if blocked:
        result.update({"entry_low": None, "entry_high": None,
                       "stop_loss": None, "entry_status": "封鎖"})
    else:
        entry_low = round(ma20 - 0.5 * atr_value, 2)
        entry_high = round(ma20 + 0.5 * atr_value, 2)
        close_now = rows[-1]["close"]
        result.update({
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": round(entry_low - 2 * atr_value, 2),
            "entry_status": ("區間內" if entry_low <= close_now <= entry_high
                             else "現價偏高" if close_now > entry_high else "現價偏低"),
        })
    result["indicators"] = {
        "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
        "bias20_pct": round(bias_pct, 2), "rsi14": round(rsi_value, 2),
        "macd_dif": round(dif, 2), "macd_dea": round(dea, 2),
        "atr14": round(atr_value, 2), "low60": low60, "high60": high60,
        "volume_ratio": round(volumes[-1] / avg_volume, 2),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="台股六維評分")
    parser.add_argument("ticker")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 供程式串接")
    args = parser.parse_args()

    conn = db.connect()
    try:
        result = evaluate(conn, args.ticker)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("%s  資料基準日 %s  收盤 %.2f" % (result["ticker"], result["date"], result["close"]))
    print("總分 %d/100 -> %s" % (result["final_score"], result["signal"]))
    for key, value in result["parts"].items():
        print("  %-8s %2d" % (key, value))
    if result["hard_rules"]:
        print("硬規則觸發：")
        for rule in result["hard_rules"]:
            print("  - %s" % rule)
    if result["entry_blocked"]:
        print("進場區間：不提供（硬規則封鎖）")
    else:
        print("進場區間 %.2f ~ %.2f（%s），停損 %.2f"
              % (result["entry_low"], result["entry_high"],
                 result["entry_status"], result["stop_loss"]))


if __name__ == "__main__":
    main()
