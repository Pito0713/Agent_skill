"""tw-market-rotation 背景欄位（大盤量能狀態、類股象限）的讀取與分組統計。

只讀不寫：背景欄位用於事後分組校準，刻意不參與評分。
"""

MIN_GROUP_SAMPLE = 5         # 背景欄位分組低於此數只標示，不給命中率
CONTEXT_TABLES = ("market_context", "sector_context", "stock_industry")


def lookup_context(conn, ticker, base_date):
    """讀 tw-market-rotation 契約表。表不存在或查無資料時回傳 (None, None)。

    只讀不寫：背景欄位用於事後分組校準，刻意不參與評分，
    否則在證明有預測力之前就會污染六維權重的校準。
    """
    present = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not set(CONTEXT_TABLES) <= present:
        return None, None
    market = conn.execute("SELECT market_state FROM market_context WHERE date = ?",
                          (base_date,)).fetchone()
    sector = conn.execute(
        "SELECT s.quadrant FROM stock_industry i JOIN sector_context s"
        "  ON s.industry_code = i.industry_code"
        " WHERE i.ticker = ? AND s.date = ?", (ticker, base_date)).fetchone()
    return (market["market_state"] if market else None,
            sector["quadrant"] if sector else None)


def context_group_stats(rows, column):
    """依背景欄位分組的命中率。NULL 歸「無資料」；只算有方向的預測（hit 非 NULL）。"""
    groups = {}
    for r in rows:
        if r["hit"] is None:
            continue
        groups.setdefault(r[column] or "無資料", []).append(r)
    output = []
    for label, subset in sorted(groups.items()):
        if len(subset) < MIN_GROUP_SAMPLE:
            output.append((label, len(subset), None, None))
            continue
        hits = sum(r["hit"] for r in subset)
        avg_return = sum(r["return_pct"] for r in subset) / len(subset)
        output.append((label, len(subset), hits / len(subset) * 100, avg_return))
    return output


def print_context_groups(rows):
    for column, title in (("market_state", "大盤狀態"), ("sector_quadrant", "類股象限")):
        print("\n--- 依%s分組（背景欄位，來源 tw-market-rotation）---" % title)
        for label, count, hit_rate, avg_return in context_group_stats(rows, column):
            if hit_rate is None:
                print("  %-10s %4d 筆  樣本不足" % (label, count))
            else:
                print("  %-10s %4d 筆  命中率 %5.1f%%  平均報酬 %+.2f%%"
                      % (label, count, hit_rate, avg_return))
    print("解讀：組間命中率若長期有明顯差距，才考慮讓背景欄位參與評分。")
