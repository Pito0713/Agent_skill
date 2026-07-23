"""技術指標計算，純 stdlib。

一律吃「還原收盤價序列」；呼叫端負責在 adj_close 為 NULL 時退回原始價並標記。
"""


def sma(values, period):
    """簡單移動平均，資料不足回 None。"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def sma_series(values, period):
    """整段 SMA 序列（長度 = len(values) - period + 1）。"""
    if len(values) < period:
        return []
    return [sum(values[i:i + period]) / period for i in range(len(values) - period + 1)]


def ema_series(values, period):
    """指數移動平均序列，種子用前 period 筆的 SMA。"""
    if len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    series = [current]
    for value in values[period:]:
        current = (value - current) * multiplier + current
        series.append(current)
    return series


def rsi(values, period=14):
    """Wilder RSI。全漲無跌回 100.0。"""
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def macd(values, fast=12, slow=26, signal=9):
    """回傳 (dif, dea, histogram)，資料不足回 (None, None, None)。"""
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    if not fast_ema or not slow_ema:
        return None, None, None
    # 對齊尾端：兩序列起點不同，取共同長度
    length = min(len(fast_ema), len(slow_ema))
    dif_series = [fast_ema[-length:][i] - slow_ema[-length:][i] for i in range(length)]
    dea_series = ema_series(dif_series, signal)
    if not dea_series:
        return None, None, None
    dif, dea = dif_series[-1], dea_series[-1]
    return dif, dea, dif - dea


def atr(highs, lows, closes, period=14):
    """Average True Range，用於推導進場區間與停損。"""
    if len(closes) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(closes)):
        true_ranges.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    current = sum(true_ranges[:period]) / period
    for value in true_ranges[period:]:
        current = (current * (period - 1) + value) / period
    return current
