"""儀表板的 HTML 呈現。所有來自 DB 或 log 的字串一律經 html.escape，避免資料內容被當成標記執行。"""

from html import escape

STYLE = """
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--up:#c0392b;--down:#1e8449;--warn:#b9770e}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--card:#1f1f22;--text:#ececef;--muted:#9a9aa2;--line:#33333a;--up:#ff6b5b;--down:#4cd07d;--warn:#f0b44c}}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 -apple-system,"PingFang TC","Noto Sans TC",sans-serif}
main{max-width:1280px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0}h2{font-size:16px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0;overflow-x:auto}
.note{color:var(--muted);font-size:12px}.banner{border-left:4px solid var(--warn)}
table{border-collapse:collapse;width:100%}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:500;font-size:12px}td.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}.grid{display:flex;gap:24px;flex-wrap:wrap}
"""


def _num(value, fmt="%.2f", signed=False):
    if value is None:
        return "–"
    text = (("%+" + fmt[1:]) if signed else fmt) % value
    return escape(text)


def _pct_class(value):
    """台股慣例：漲紅跌綠。"""
    if value is None or value == 0:
        return ""
    return "up" if value > 0 else "down"


def _table(headers, rows):
    head = "".join("<th>%s</th>" % escape(h) for h in headers)
    return "<table><tr>%s</tr>%s</table>" % (head, "".join(rows))


def _shares_text(shares):
    return "%d 張" % (shares // 1000) if shares % 1000 == 0 else "%d 股" % shares


def _position_row(item):
    ticker = "%s %s" % (escape(item["ticker"]), escape(item["name"] or ""))
    head = [ticker, escape(item["buy_date"]), _shares_text(item["shares"]), _num(item["buy_price"]),
            _num(item["amount"], "%.0f")]
    now = item["now"]
    if now is None:
        return "<tr>%s<td colspan=6 class=warn>%s</td></tr>" % (
            "".join("<td>%s</td>" % c for c in head), escape(item["error"]))
    if item["exdiv_unknown"]:
        pnl = '<span class=warn title="持有期間有金額未知的除權息">未還原</span>'
    else:
        pnl = '<span class="%s">%s（%s%%）</span>' % (_pct_class(item["pnl"]), _num(item["pnl"], "%.0f", True),
                                                     _num(item["return_pct"], signed=True))
    stop = ("無" if item["stop_loss"] is None else "%s（距 %s%%）" % (
        _num(item["stop_loss"]), _num(item["stop_distance_pct"], "%.1f", True)))
    alerts = "；".join(escape(a) for a in item["alerts"])
    cells = head + [_num(now["close"]), pnl, stop, "%d %s" % (now["final_score"], escape(now["signal"])),
                    '<span class=warn>%s</span>' % alerts if alerts else "–"]
    return "<tr>%s</tr>" % "".join(
        '<td class="num">%s</td>' % c if i in (3, 4, 5, 6) else "<td>%s</td>" % c for i, c in enumerate(cells))


def render_positions(items):
    if not items:
        return ('<section class="card"><h2>我的持股</h2><p class="note">目前沒有持股紀錄。'
                "新增：python3 positions.py add &lt;代號&gt; --price &lt;成交價&gt; --shares &lt;股數&gt;</p></section>")
    headers = ["標的", "買進日", "數量", "買進價", "進場金額", "收盤", "浮動損益", "停損（買進時固定）",
               "現在評分", "狀態警示"]
    return ('<section class="card"><h2>我的持股（%d 筆）</h2>%s<p class="note">進場金額＝成交價×股數，'
            "損益未扣手續費與證交稅，持有期間配息已還原計入。停損在買進時固定，不隨重算移動。"
            "狀態警示只描述規則觸發的狀態，不是出場建議；本工具不產生目標價。</p></section>"
            % (len(items), _table(headers, [_position_row(i) for i in items])))


def _prediction_row(item):
    now = item["now"]
    name = escape(item["name"] or "")
    ticker = "%s %s" % (escape(item["ticker"]), name)
    if now is None:
        return "<tr><td>–</td><td>%s</td><td colspan=8 class=warn>%s</td></tr>" % (ticker, escape(item["error"]))
    valuation = now.get("valuation") or {}
    entry = ("封鎖" if now["entry_blocked"]
             else "%s–%s（%s）" % (_num(now["entry_low"]), _num(now["entry_high"]), escape(now["entry_status"])))
    unrealized = item.get("unrealized")
    cells = [
        "<b>%d %s</b>" % (now["final_score"], escape(now["signal"])),
        ticker, escape(item["created_at"]), "%s（%d 天）" % (escape(item["due"]), item["days_left"]),
        "%d %s" % (item["score_then"], escape(item["signal_then"])),
        ('<span class="%s">%s%%</span>' % (_pct_class(unrealized), _num(unrealized, signed=True))
         if unrealized is not None
         else '<span class=warn title="持有期間有金額未知的除權息">未還原</span>' if item.get("exdiv_unknown")
         else "–"),
        _num(now["close"]), entry,
        escape("；".join(now["hard_rules"])) or "–",
        "%s／%s" % (_num(valuation.get("pe_percentile"), "%.0f"), _num(valuation.get("pb_percentile"), "%.0f")),
    ]
    return "<tr>%s</tr>" % "".join(
        '<td class="num">%s</td>' % c if i in (5, 6) else "<td>%s</td>" % c for i, c in enumerate(cells))


def render_predictions(items):
    if not items:
        return '<section class="card"><h2>預測現況</h2><p class="note">目前沒有 open 預測。</p></section>'
    headers = ["現在 ▼", "標的", "建立日", "到期日（剩餘）", "當時", "浮動報酬", "收盤", "進場區間（狀態）",
               "硬規則", "本益比／淨值比百分位"]
    return ('<section class="card"><h2>預測現況（%d 筆 open）</h2>%s<p class="note">「現在」以最新資料重算，'
            "只供對照；預測仍以建立當天為準，到期後由 reconcile 對帳。浮動報酬為建立日收盤至今的還原報酬，"
            "未扣成本。百分位是相對該股自身近 3 年的位置，不是貴或便宜的判斷。</p></section>"
            % (len(items), _table(headers, [_prediction_row(i) for i in items])))


def render_resolved(summary):
    gate = summary["gate"]
    thresholds = summary["thresholds"]
    counts = "、".join("%s %d" % (escape(k), v) for k, v in sorted(summary["status_counts"].items()))
    head = ("<p>已對帳 <b>%d</b> 筆（狀態：%s）｜方向命中率 %s｜門檻：%s（偏多≥%d／偏空&lt;%d）</p>"
            "<p>校準樣本進度：%d/%d 筆、%d/%d 週 → %s</p>"
            % (summary["total"], counts or "–",
               (_num(summary["hit_rate"], "%.1f") + "%") if summary["hit_rate"] is not None else "–",
               "預設" if thresholds["calibration_id"] is None else "第 %d 版" % thresholds["calibration_id"],
               thresholds["bull"], thresholds["bear"], gate["resolved"], gate["min_resolved"],
               gate["weeks"], gate["min_weeks"], "可執行 calibrate" if gate["passed"] else "未達門檻"))
    body = ""
    if summary["buckets"]:
        rows = ["<tr><td>%s</td><td class=num>%d</td><td class=num>%s%%</td><td class=num>%s%%</td></tr>"
                % (escape(label), n, _num(up, "%.1f"), _num(mean, signed=True))
                for label, (n, up, mean, _) in summary["buckets"]]
        body += _table(["分數區間", "樣本", "上漲比例", "平均報酬"], rows)
    if summary["recent"]:
        rows = ['<tr><td>%s</td><td>%s</td><td>%d %s</td><td class="num %s">%s%%</td><td>%s</td></tr>'
                % (escape(r["ticker"]), escape(r["resolve_date"] or ""), r["score"], escape(r["signal"]),
                   _pct_class(r["return_pct"]), _num(r["return_pct"], signed=True),
                   {1: "命中", 0: "未中"}.get(r["hit"], "中性不計"))
                for r in summary["recent"]]
        body += "<h2 style='margin-top:12px'>最近對帳</h2>" + _table(["標的", "對帳日", "當時", "報酬", "結果"], rows)
    note = '<p class="note">樣本少於 30 筆時統計上不具意義，不足以判斷準或不準。</p>'
    return '<section class="card"><h2>對帳與校準</h2>%s%s%s</section>' % (head, body, note)


def render_backtests(runs):
    if not runs:
        return '<section class="card"><h2>回測摘要</h2><p class="note">尚無完成的回測。</p></section>'
    rows = []
    for run in runs:
        for h in run["horizons"]:
            ic = h.get("ic")
            rows.append("<tr><td>run %d（%d 檔）</td><td>%s ~ %s</td><td class=num>%d 天</td><td class=num>%d</td>"
                        "<td class=num>%s%%</td><td class=num>%s</td><td class=num>%s</td><td>%s</td></tr>"
                        % (run["id"], run["tickers"], escape(run["start"]), escape(run["end"]), h["horizon"],
                           h["n"], _num(h.get("tradable_mean"), signed=True),
                           _num(ic["mean"], "%.3f", signed=True) if ic else "–",
                           _num(ic["t"], "%.1f", signed=True) if ic else "–", escape(h.get("verdict", "–"))))
    headers = ["回測", "期間", "持有", "樣本", "可成交平均", "Rank IC", "t", "判讀"]
    return ('<section class="card"><h2>回測摘要</h2>%s<p class="note">可成交＝次日開盤進場、扣手續費與證交稅。'
            "標的為現在挑選，有選股偏差；完整報告：python3 backtest.py report --run &lt;id&gt;</p></section>"
            % _table(headers, rows))


def render_schedule(logs):
    if not logs:
        return '<section class="card"><h2>排程狀態</h2><p class="note">尚無排程 log（~/.stock-tracker/logs）。</p></section>'
    rows = []
    for log in logs:
        ok = log["last_status"] == 0
        state = ("<span class=down>成功</span>" if ok else "<span class=up>失敗</span>"
                 if log["last_status"] is not None else "<span class=warn>未結束</span>")
        rows.append("<tr><td>%s</td><td class=num>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (escape(log["date"]), log["runs"], escape(log["last_end"] or "–"), state,
                       escape("；".join(log["failures"][-3:])) or ("略過 %d 次" % log["skips"] if log["skips"] else "–")))
    return ('<section class="card"><h2>排程狀態（launchd，週一至五 16:30）</h2>%s</section>'
            % _table(["日期", "執行次數", "最後結束", "結果", "失敗／備註"], rows))


def render_page(data):
    fresh = data["freshness"]
    header = ("<h1>台股追蹤儀表板</h1><p class=note>產生於 %s｜最新日線 %s｜最新估值 %s｜DB %s MB｜重新整理頁面即重算</p>"
              % (escape(fresh["generated_at"]), escape(fresh["latest_quote"] or "–"),
                 escape(fresh["latest_valuation"] or "–"), _num(fresh["db_mb"], "%.1f")))
    banner = ('<section class="card banner"><b>評分是技術面狀態描述，不是選股訊號。</b>'
              "兩組 3 年回測顯示總分沒有可證實的預測力（ADR-026）；本頁不構成投資建議。</section>")
    sections = [render_positions(data.get("positions", [])), render_predictions(data["predictions"]), render_resolved(data["resolved"]),
                render_backtests(data["backtests"]), render_schedule(data["schedule"])]
    return ("<!doctype html><html lang=zh-Hant><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><title>台股追蹤儀表板</title>"
            "<style>%s</style></head><body><main>%s%s%s</main></body></html>"
            % (STYLE, header, banner, "".join(sections)))
