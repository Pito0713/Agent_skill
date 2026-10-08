"""三大法人因子：近 N 個交易日的法人淨買超 ÷ 同期成交股數。

因子清單在實作前就鎖定（外資、投信 × 5、20 日），跑完回測不再增減——
多挑幾個總會有一個看起來顯著（見 ADR-026 的教訓）。自營商不測：部位多為權證避險，雜訊大。
只記錄、不參與 100 分評分；只用 as_of 以前的資料，回測可直接沿用。
只讀 DB；資料由 fetch_flows 負責。
"""

from fetch_flows import MARKETS

WINDOWS = (5, 20)
ACTORS = (("foreign", "foreign_net"), ("trust", "trust_net"))
FACTOR_COLUMNS = tuple("flow_%s_%dd" % (actor, window) for actor, _ in ACTORS for window in WINDOWS)


def _covered(conn, day):
    """兩個市場當天都已抓且有資料，才能把「名單上沒有這檔」解讀為法人零買賣。"""
    count = conn.execute("SELECT COUNT(*) FROM flow_fetches WHERE date = ? AND rows > 0",
                         (day,)).fetchone()[0]
    return count == len(MARKETS)


def _window_factor(conn, ticker, bars, column):
    """bars 為由新到舊的 (date, volume)。任一天沒抓到或成交量合計為 0 回 None。"""
    if any(not _covered(conn, day) for day, _ in bars):
        return None
    volume = sum(v for _, v in bars)
    if volume <= 0:
        return None
    placeholders = ",".join("?" * len(bars))
    net = conn.execute(
        "SELECT COALESCE(SUM(%s), 0) FROM institutional_flows WHERE ticker = ? AND date IN (%s)"
        % (column, placeholders), (ticker, *(day for day, _ in bars))).fetchone()[0]
    return round(net / volume, 6)


def factor_values(conn, ticker, as_of):
    """依 FACTOR_COLUMNS 順序回傳 tuple；日線不足或法人資料缺漏的因子為 None。"""
    bars = [(r["date"], r["volume"]) for r in conn.execute(
        "SELECT date, volume FROM daily_quotes WHERE ticker = ? AND date <= ?"
        " ORDER BY date DESC LIMIT ?", (ticker, as_of, max(WINDOWS)))]
    values = []
    for _, column in ACTORS:
        for window in WINDOWS:
            values.append(_window_factor(conn, ticker, bars[:window], column)
                          if len(bars) >= window else None)
    return tuple(values)
