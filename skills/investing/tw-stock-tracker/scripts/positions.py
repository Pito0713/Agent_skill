"""使用者實際持股：記錄買進、平倉，並算出進場金額、浮動損益、固定停損與狀態警示。

  python3 positions.py add <代號> --price 12.1 --shares 5000 [--date 2026-10-14] [--note ...]
  python3 positions.py close <id> --price 13.0 [--date 2026-10-20]
  python3 positions.py list [--all]

停損在買進時固定：取 buy_date 當天（尚無當天日線時取之前最近一根）的評分停損，之後不隨重算移動。
狀態警示只描述規則觸發的狀態，不產生目標價或出場價（見 SKILL.md「已知限制 6」）。
持股與 predictions 完全分開，不進對帳、校準或回測統計。
"""

import argparse
import json
import sys
from datetime import date

import db
import fetch_twse
import score as scoring
import track

BEARISH = ("偏空", "強烈偏空")


def _parse_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("日期格式須為 yyyy-mm-dd，收到 %s" % text) from error


def _positive_float(text):
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("必須大於 0，收到 %s" % text)
    return value


def add_position(conn, ticker, buy_date, buy_price, shares, note=""):
    """以 buy_date（含）以前的資料評分，固定當時的停損後落一筆 open 持股。回傳新 id 與評分結果。"""
    if buy_date > date.today().isoformat():
        raise RuntimeError("買進日 %s 晚於今天" % buy_date)
    result = scoring.evaluate(conn, ticker, as_of=buy_date)
    # evaluate 的停損是現行還原基準；換回該日原始價，之後才能用除權息比例換算到任何一天的基準
    stop_loss = (None if result["stop_loss"] is None
                 else round(result["stop_loss"] * result["close"] / result["adj_close"], 2))
    cursor = conn.execute(
        "INSERT INTO positions (ticker, buy_date, buy_price, shares, basis_date, basis_close, stop_loss,"
        " score, signal, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ticker, buy_date, buy_price, shares, result["date"], result["close"], stop_loss,
         result["final_score"], result["signal"], note))
    conn.commit()
    return cursor.lastrowid, result, stop_loss


def close_position(conn, position_id, sell_price, sell_date):
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    if row is None:
        raise RuntimeError("找不到持股 id %d" % position_id)
    if row["status"] != "open":
        raise RuntimeError("持股 id %d 已平倉" % position_id)
    if sell_date < row["buy_date"]:
        raise RuntimeError("平倉日 %s 早於買進日 %s" % (sell_date, row["buy_date"]))
    conn.execute("UPDATE positions SET status = 'closed', sell_date = ?, sell_price = ? WHERE id = ?",
                 (sell_date, sell_price, position_id))
    conn.commit()


def _basis_factor(conn, row):
    """basis_date 那根日線現在的還原比例（adj/close）；之後若有已知除權息，比例會小於 1。"""
    quote = conn.execute("SELECT close, adj_close FROM daily_quotes WHERE ticker = ? AND date = ?",
                         (row["ticker"], row["basis_date"])).fetchone()
    if quote is None:
        return None
    return (quote["adj_close"] or quote["close"]) / quote["close"]


def position_status(conn, row):
    """一筆 open 持股的現況：進場金額、市值、浮動損益、停損距離、狀態警示。

    損益與停損比較都換到現行還原基準，持有期間配息不會被當成虧損或誤觸停損；
    期間有金額未知的除權息時無法換算，損益與停損比較都不給數字（同對帳的 needs_review）。
    """
    item = {"id": row["id"], "ticker": row["ticker"], "buy_date": row["buy_date"],
            "buy_price": row["buy_price"], "shares": row["shares"],
            "amount": row["buy_price"] * row["shares"], "stop_loss": row["stop_loss"],
            "score_then": row["score"], "signal_then": row["signal"], "note": row["note"],
            "name": scoring.lookup_name(conn, row["ticker"]), "now": None, "error": None,
            "exdiv_unknown": False, "return_pct": None, "pnl": None, "stop_distance_pct": None,
            "alerts": []}
    try:
        now = scoring.evaluate(conn, row["ticker"])
    except RuntimeError as error:
        item["error"] = str(error)
        return item
    item["now"] = now
    item["market_value"] = now["close"] * row["shares"]
    item["exdiv_unknown"] = bool(track._exdiv_unknown_in_window(conn, row["ticker"], row["basis_date"],
                                                               now["date"]))
    factor = _basis_factor(conn, row)
    if not item["exdiv_unknown"] and factor is not None:
        item["return_pct"] = (now["adj_close"] / (row["buy_price"] * factor) - 1) * 100
        item["pnl"] = item["amount"] * item["return_pct"] / 100
        if row["stop_loss"] is not None:
            adjusted_stop = row["stop_loss"] * factor
            item["stop_distance_pct"] = (now["adj_close"] / adjusted_stop - 1) * 100
            if now["adj_close"] < adjusted_stop:
                item["alerts"].append("收盤跌破買進時停損")
    item["alerts"].extend(_state_alerts(row, now))
    return item


def _state_alerts(row, now):
    """規則觸發的狀態描述，不是出場建議。"""
    alerts = []
    if row["stop_loss"] is None:
        alerts.append("買進時進場被硬規則封鎖，無規則停損")
    if now["signal"] in BEARISH:
        alerts.append("評分轉%s" % now["signal"])
    if now["adj_close"] < now["indicators"]["ma20"]:
        alerts.append("收盤低於 MA20")
    alerts.extend(now["hard_rules"])
    return alerts


def open_positions(conn):
    rows = conn.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY buy_date, id").fetchall()
    return [position_status(conn, row) for row in rows]


def cmd_add(conn, args):
    fetch_twse.sync_ticker(conn, args.ticker)
    position_id, result, stop_loss = add_position(conn, args.ticker, args.date, args.price, args.shares,
                                                  args.note)
    print(json.dumps({"position_id": position_id, "ticker": args.ticker, "buy_date": args.date,
                      "buy_price": args.price, "shares": args.shares, "amount": args.price * args.shares,
                      "stop_basis_date": result["date"], "stop_loss": stop_loss,
                      "score": result["final_score"], "signal": result["signal"]},
                     ensure_ascii=False, indent=2))


def cmd_close(conn, args):
    close_position(conn, args.id, args.price, args.date)
    print("持股 id %d 已平倉：%s 賣出價 %s" % (args.id, args.date, args.price))


def cmd_list(conn, args):
    query = "SELECT * FROM positions" + ("" if args.all else " WHERE status = 'open'") + " ORDER BY id"
    for row in conn.execute(query):
        print(json.dumps(dict(row), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="使用者持股記錄")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="記錄一筆買進")
    add.add_argument("ticker")
    add.add_argument("--price", type=_positive_float, required=True, help="成交價")
    add.add_argument("--shares", type=track.positive_int, required=True, help="股數（1 張 = 1000）")
    add.add_argument("--date", type=_parse_date, default=date.today().isoformat(), help="成交日，預設今天")
    add.add_argument("--note", default="")
    close = sub.add_parser("close", help="平倉")
    close.add_argument("id", type=int)
    close.add_argument("--price", type=_positive_float, required=True, help="賣出價")
    close.add_argument("--date", type=_parse_date, default=date.today().isoformat(), help="賣出日，預設今天")
    listing = sub.add_parser("list", help="列出持股")
    listing.add_argument("--all", action="store_true", help="含已平倉")

    args = parser.parse_args()
    conn = db.connect()
    try:
        {"add": cmd_add, "close": cmd_close, "list": cmd_list}[args.command](conn, args)
    except RuntimeError as error:
        print("錯誤：%s" % error, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
