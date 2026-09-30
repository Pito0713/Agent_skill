"""大盤量能狀態 + 類股輪動（RRG 近似）計算與報告。

子命令：
  sync    回補 TWSE 資料、更新產業對應、重算契約表
  report  輸出大盤狀態與類股象限

公式與門檻說明見 references/method.md。窗口資料不足或有缺值時一律寫 NULL，不猜。
"""

import argparse
import sys

import fetch_market
import schema
import sectors

TURNOVER_WINDOW = 20
BREADTH_WINDOW = 5
RS_WINDOW = 20
MOMENTUM_LAG = 5
SHARE_SHORT_WINDOW = 5
SHARE_LONG_WINDOW = 20

# 暫定門檻，待 tw-stock-tracker 對帳樣本校準
STRONG_TURNOVER_RATIO = 1.1
WEAK_TURNOVER_RATIO = 0.8
STRONG_BREADTH = 0.5
WEAK_BREADTH = 0.4

QUADRANT_ORDER = ("Leading", "Improving", "Weakening", "Lagging")


def window_mean(values, end_index, size):
    """values[end_index-size+1 .. end_index] 的平均；不足 size 筆或含 None 回傳 None。"""
    if end_index + 1 < size:
        return None
    window = values[end_index - size + 1:end_index + 1]
    if any(v is None for v in window):
        return None
    return sum(window) / size


def classify_market(turnover_ratio, breadth_5d):
    if turnover_ratio is None or breadth_5d is None:
        return None
    if turnover_ratio < WEAK_TURNOVER_RATIO or breadth_5d < WEAK_BREADTH:
        return "不足"
    if turnover_ratio >= STRONG_TURNOVER_RATIO and breadth_5d >= STRONG_BREADTH:
        return "充足"
    return "普通"


def classify_quadrant(rs_ratio, rs_momentum):
    if rs_ratio is None or rs_momentum is None:
        return None
    if rs_ratio >= 100:
        return "Leading" if rs_momentum >= 100 else "Weakening"
    return "Improving" if rs_momentum >= 100 else "Lagging"


def compute_market_context(rows):
    """rows：依日期排序的 dict(date, turnover, advances, declines)。"""
    turnovers = [r["turnover"] for r in rows]
    breadths = []
    for r in rows:
        if r["advances"] is None or r["declines"] is None:
            breadths.append(None)
            continue
        total = r["advances"] + r["declines"]
        breadths.append(r["advances"] / total if total else None)
    output = []
    for i, r in enumerate(rows):
        average = window_mean(turnovers, i, TURNOVER_WINDOW)
        ratio = turnovers[i] / average if average else None      # 窗口含當日，缺值時 average 已是 None
        breadth_5d = window_mean(breadths, i, BREADTH_WINDOW)
        output.append({"date": r["date"], "turnover_ratio": ratio, "breadth_5d": breadth_5d,
                       "market_state": classify_market(ratio, breadth_5d)})
    return output


def _ratio_series(numerators, denominators):
    return [n / d if n is not None and d else None for n, d in zip(numerators, denominators)]


def compute_sector_series(closes, turnovers, taiex, market_turnovers):
    """單一類股：各序列皆與日期對齊（缺值為 None）。回傳每日 dict 清單（不含 date）。"""
    rs = _ratio_series(closes, taiex)
    shares = _ratio_series(turnovers, market_turnovers)
    rs_ratios = []
    for i in range(len(rs)):
        rs_average = window_mean(rs, i, RS_WINDOW)
        rs_ratios.append(100 * rs[i] / rs_average if rs_average else None)
    output = []
    for i in range(len(rs)):
        lagged = rs_ratios[i - MOMENTUM_LAG] if i >= MOMENTUM_LAG else None
        momentum = 100 * rs_ratios[i] / lagged if rs_ratios[i] is not None and lagged else None
        short = window_mean(shares, i, SHARE_SHORT_WINDOW)
        long = window_mean(shares, i, SHARE_LONG_WINDOW)
        output.append({"rs_ratio": rs_ratios[i], "rs_momentum": momentum,
                       "quadrant": classify_quadrant(rs_ratios[i], momentum),
                       "share_delta": short - long if short is not None and long is not None else None})
    return output


def _load_market(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM market_daily ORDER BY date")]


def _load_sector_rows(conn, code, dates):
    by_date = {r["date"]: r for r in conn.execute(
        "SELECT date, index_close, turnover FROM sector_daily WHERE industry_code = ?", (code,))}
    closes = [by_date[d]["index_close"] if d in by_date else None for d in dates]
    turnovers = [by_date[d]["turnover"] if d in by_date else None for d in dates]
    return closes, turnovers


def rebuild_context(conn):
    """由快取重算全部契約表列。回傳 (大盤天數, 類股列數)。"""
    market = _load_market(conn)
    dates = [r["date"] for r in market]
    conn.executemany(
        "INSERT OR REPLACE INTO market_context (date, turnover_ratio, breadth_5d, market_state)"
        " VALUES (:date, :turnover_ratio, :breadth_5d, :market_state)",
        compute_market_context(market))
    taiex = [r["taiex"] for r in market]
    market_turnovers = [r["turnover"] for r in market]
    sector_rows = []
    for code in sectors.INDUSTRIES:
        closes, turnovers = _load_sector_rows(conn, code, dates)
        for day, values in zip(dates, compute_sector_series(closes, turnovers, taiex,
                                                             market_turnovers)):
            sector_rows.append(dict(values, date=day, industry_code=code))
    conn.executemany(
        "INSERT OR REPLACE INTO sector_context"
        " (date, industry_code, rs_ratio, rs_momentum, quadrant, share_delta)"
        " VALUES (:date, :industry_code, :rs_ratio, :rs_momentum, :quadrant, :share_delta)",
        sector_rows)
    conn.commit()
    return len(market), len(sector_rows)


def _fmt(value, pattern):
    return "—" if value is None else pattern % value


def render_report(conn, target_date=None):
    """回傳報告文字。target_date 為 None 時用最新一個交易日。"""
    market = conn.execute(
        "SELECT * FROM market_context WHERE (? IS NULL OR date <= ?) ORDER BY date DESC LIMIT 1",
        (target_date, target_date)).fetchone()
    if market is None:
        return "沒有資料，請先執行 sync"
    lines = ["=== 大盤量能與類股輪動 %s ===" % market["date"],
             "大盤狀態：%s（量能比 %s，5 日寬度 %s）" % (
                 market["market_state"] or "資料不足",
                 _fmt(market["turnover_ratio"], "%.2f"), _fmt(market["breadth_5d"], "%.2f"))]
    rows = conn.execute("SELECT * FROM sector_context WHERE date = ?", (market["date"],)).fetchall()
    for quadrant in QUADRANT_ORDER + (None,):
        group = sorted((r for r in rows if r["quadrant"] == quadrant),
                       key=lambda r: -(r["share_delta"] or 0))
        if not group:
            continue
        lines.append("\n--- %s ---" % (quadrant or "資料不足"))
        lines.append("%-10s %9s %9s %12s" % ("類股", "RS-Ratio", "RS-Mom", "比重變化(pp)"))
        for r in group:
            # round 後 + 0.0 把 -0.0 正規化，避免報告出現「-0.00」
            share = None if r["share_delta"] is None else round(r["share_delta"] * 100, 2) + 0.0
            lines.append("%-10s %9s %9s %12s" % (
                sectors.display_name(r["industry_code"]), _fmt(r["rs_ratio"], "%.2f"),
                _fmt(r["rs_momentum"], "%.2f"), _fmt(share, "%+.2f")))
    lines.append("\n註：RRG 為 JdK 公式的近似；門檻未經對帳校準，只當背景參考。")
    return "\n".join(lines)


def cmd_sync(conn, args):
    written = fetch_market.sync_industry(conn)
    print("產業對應：%s" % ("更新 %d 筆" % written if written else "7 天內已更新，略過"))
    fetched, trading = fetch_market.sync_days(conn, args.days)
    print("回補：新抓 %d 天，快取交易日 %d 天" % (fetched, trading))
    if trading < args.days:
        print("[warn] 交易日 %d < 要求 %d，部分指標會是 NULL" % (trading, args.days), file=sys.stderr)
    days, sector_rows = rebuild_context(conn)
    print("重算契約表：大盤 %d 天、類股 %d 列" % (days, sector_rows))


def cmd_report(conn, args):
    print(render_report(conn, args.date))


def main():
    parser = argparse.ArgumentParser(description="台股大盤量能與類股輪動")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="回補資料並重算")
    sync.add_argument("--days", type=int, default=60, help="至少保有的交易日數，預設 60")
    report = sub.add_parser("report", help="輸出報告")
    report.add_argument("--date", help="YYYY-MM-DD，預設最新交易日")
    args = parser.parse_args()

    conn = schema.connect()
    try:
        {"sync": cmd_sync, "report": cmd_report}[args.command](conn, args)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
