"""回測的「可成交」口徑：次一交易日開盤進場、扣台股交易成本、漲跌停買不到賣不掉。

收盤進場口徑（backtest.forward_return）與 track 對帳一致，但分數要收盤後才算得出來，
當天收盤價實際上買不到。這裡另算一個較接近真實可拿到的報酬，兩者並存。
構想借自 qlib backtest/exchange.py 的 open_cost / close_cost / limit_threshold。
"""

import score as scoring

BROKER_FEE = 0.001425        # 手續費，買賣各一次
STOCK_TAX = 0.003            # 證交稅，賣出時收
ETF_TAX = 0.001
LIMIT_DOWN_RATIO = 0.905     # 跌停 10%，留 0.5% 容差（對稱於 score.LIMIT_UP_RATIO）


def is_etf(ticker):
    return ticker.startswith("00")


def round_trip_rates(ticker, fee_discount):
    """(買進成本率, 賣出成本率)。不含最低手續費 20 元：那取決於每筆金額。"""
    fee = BROKER_FEE * fee_discount
    return fee, fee + (ETF_TAX if is_etf(ticker) else STOCK_TAX)


def _quote(conn, ticker, sql_tail, day):
    return conn.execute(
        "SELECT date, open, high, low, close, adj_close FROM daily_quotes WHERE ticker = ? AND "
        + sql_tail, (ticker, day)).fetchone()


def _adjust_factor(row):
    return (row["adj_close"] or row["close"]) / row["close"]


def tradable_return(conn, ticker, span, fee_discount):
    """span = (as_of, end_date)。回傳 (entry_date, return_pct, excluded_reason)。

    進場：as_of 之後第一根的開盤，開盤即漲停（≥ 前收 × 1.095）視為買不到。
    出場：end_date 收盤，跌停鎖死（最高 = 最低且 ≤ 前收 × 0.905）視為賣不掉。
    開盤價乘上當日的還原比例，與還原收盤同一基準，持有期間的除息才不會算成虧損。
    """
    as_of, end_date = span
    entry = _quote(conn, ticker, "date > ? ORDER BY date LIMIT 1", as_of)
    if entry is None or entry["date"] > end_date:
        return None, None, "no_entry_before_exit"
    signal_day = _quote(conn, ticker, "date = ?", as_of)
    if entry["open"] >= signal_day["close"] * scoring.LIMIT_UP_RATIO:
        return entry["date"], None, "entry_limit_up"
    exit_row = _quote(conn, ticker, "date = ?", end_date)
    before_exit = _quote(conn, ticker, "date < ? ORDER BY date DESC LIMIT 1", end_date)
    locked_down = (exit_row["high"] == exit_row["low"]
                   and exit_row["close"] <= before_exit["close"] * LIMIT_DOWN_RATIO)
    if locked_down:
        return entry["date"], None, "exit_limit_down"
    buy_rate, sell_rate = round_trip_rates(ticker, fee_discount)
    adj_open = entry["open"] * _adjust_factor(entry)
    adj_exit = exit_row["close"] * _adjust_factor(exit_row)
    net = adj_exit * (1 - sell_rate) / (adj_open * (1 + buy_rate)) - 1
    return entry["date"], round(net * 100, 4), None
