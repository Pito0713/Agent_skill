"""儀表板的個股詳情頁（/stock/<代號>）。資料來自 detail.build，只讀 DB、不抓新聞、不發任何外部請求。

所有字串經 html.escape；外部連結只接受 http(s)，避免 DB 內容變成 javascript: 連結。
"""

from html import escape

from dashboard_views import STYLE, _num, _pct_class, _table


def _link(url, label):
    if not url or not url.startswith(("https://", "http://")):
        return "–"
    return '<a href="%s" rel="noopener noreferrer" target="_blank">%s</a>' % (escape(url), escape(label))


def _pct(value):
    return '<span class="%s">%s%%</span>' % (_pct_class(value), _num(value, signed=True)) if value is not None else "–"


def _price_card(detail):
    price, score = detail["price"], detail["score"]
    if not price:
        return '<section class="card"><h2>價量</h2><p class=note>沒有日線。</p></section>'
    returns = "｜".join("%s %s" % (escape(k), _pct(v)) for k, v in price["returns_pct"].items())
    body = "<p>收盤 <b>%s</b>（%s）｜還原報酬 %s</p>" % (_num(price["close"]), escape(price["date"]), returns)
    if score:
        entry = ("封鎖" if score["entry_blocked"] else "%s–%s（%s），停損 %s" % (
            _num(score["entry_low"]), _num(score["entry_high"]), escape(score["entry_status"]),
            _num(score["stop_loss"])))
        body += "<p>技術評分 <b>%d %s</b>｜進場區間 %s｜硬規則：%s</p>" % (
            score["final_score"], escape(score["signal"]), entry, escape("；".join(score["hard_rules"])) or "無")
    valuation = detail["valuation"]
    if valuation:
        body += "<p>本益比 %s（百分位 %s）｜淨值比 %s（百分位 %s）｜殖利率 %s%%｜估值日 %s</p>" % (
            _num(valuation["pe"]), _num(valuation["pe_percentile"], "%.0f"), _num(valuation["pb"]),
            _num(valuation["pb_percentile"], "%.0f"), _num(valuation["dividend_yield"]), escape(valuation["date"]))
    return '<section class="card"><h2>價量與評分</h2>%s</section>' % body


def _flows_card(flows):
    rows = []
    for window, values in flows.items():
        if values is None:
            rows.append("<tr><td>%s</td><td colspan=4 class=note>法人資料未抓齊</td></tr>" % escape(window))
            continue
        rows.append("<tr><td>%s</td>%s</tr>" % (escape(window), "".join(
            '<td class="num %s">%s</td>' % (_pct_class(values[k]), _num(values[k], "%.0f", True))
            for k in ("foreign", "trust", "dealer", "total"))))
    return ('<section class="card"><h2>三大法人淨買賣超（張）</h2>%s</section>'
            % _table(["區間", "外資", "投信", "自營商", "合計"], rows))


def _revenue_card(revenue):
    if not revenue:
        return '<section class="card"><h2>月營收</h2><p class=note>沒有月營收資料。</p></section>'
    rows = ["<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
            "<td class=num>%s</td><td>%s</td></tr>"
            % (escape(r["month"]), _num(r["revenue"] / 1000, "%.0f"), _pct(r["yoy_pct"]), _pct(r["mom_pct"]),
               _pct(r["cum_yoy_pct"]), escape(r["note"] or "–"))
            for r in reversed(revenue["history"])]
    return ('<section class="card"><h2>月營收（百萬元，最新 %s）</h2>%s<p class=note>增減率由原始數字計算，'
            "與官方公布的百分比可能差 0.01。備註為公司自填原文。</p></section>"
            % (escape(revenue["latest"]["month"]), _table(["月份", "營收", "年增", "月增", "累計年增", "公司備註"], rows)))


def _financials_card(fin):
    if not fin:
        return '<section class="card"><h2>財報</h2><p class=note>沒有財報資料。</p></section>'
    return ('<section class="card"><h2>財報 %s（%s）</h2><p>EPS %s 元｜單季 EPS（近似）%s｜去年同期累計 EPS %s</p>'
            "<p>營收 %s 百萬｜營業利益率 %s%%｜稅後淨利率 %s%%｜出表 %s</p>"
            "<p class=note>交易所只提供最新一季；DB 已存 %d 季，前一季與去年同期要累積到才算得出。</p></section>"
            % (escape(fin["period"]), escape(fin["basis"]), _num(fin["eps_cumulative"]),
               _num(fin["eps_quarter_approx"]), _num(fin["eps_cumulative_last_year"]),
               _num(fin["revenue"] / 1000 if fin["revenue"] is not None else None, "%.0f"),
               _num(fin["operating_margin_pct"]), _num(fin["net_margin_pct"]), escape(fin["published"] or "–"),
               fin["periods_stored"]))


def _conferences_card(conferences):
    if not conferences:
        return '<section class="card"><h2>法說會</h2><p class=note>近期沒有法說會紀錄。</p></section>'
    rows = ["<tr><td>%s</td><td style='white-space:normal'>%s</td><td>%s %s %s</td></tr>"
            % (escape(c["date"] + (" ~ " + c["end_date"] if c["end_date"] else "")), escape(c["summary"] or "–"),
               _link(c["slides_zh"], "中文簡報"), _link(c["slides_en"], "英文簡報"), _link(c["website"], "公司網站"))
            for c in conferences]
    return ('<section class="card"><h2>法說會</h2>%s<p class=note>擇要訊息為公司原文；前瞻指引請看簡報原檔。'
            "抓取於 %s。</p></section>" % (_table(["日期", "擇要訊息", "連結"], rows),
                                          escape(max(c["fetched_at"] for c in conferences))))


def _refresh_banner(refreshed):
    if refreshed is None:
        return ("<section class='card banner'><b>尚未用 --fetch 更新過</b>：下列資料可能是其他流程順帶抓的、不完整。"
                "在對話中說「重新更新 &lt;代號&gt;」即可完整抓取。</section>")
    failed = "、".join(refreshed["failed_steps"])
    return ("<section class='card banner'><b>資料更新於 %s</b>%s<br><span class=note>各區塊另標資料日期；"
            "要重抓請在對話中說「重新更新 &lt;代號&gt;」。</span></section>"
            % (escape(refreshed["at"]), "｜<span class=warn>更新失敗：%s</span>" % escape(failed) if failed else ""))


def render_detail(detail):
    title = "%s %s" % (detail["ticker"], detail["name"] or "")
    missing = "".join("<li>%s</li>" % escape(m) for m in detail["missing"])
    sections = [_price_card(detail), _flows_card(detail["flows_lots"]), _revenue_card(detail["revenue"]),
                _financials_card(detail["financials"]), _conferences_card(detail["conferences"])]
    header = ('<p><a href="/">← 回儀表板</a></p><h1>%s</h1><p class=note>頁面產生於 %s｜基本面只顯示、不參與評分；'
              "新聞請在對話中用 detail.py 查詢（儀表板不發外部請求）</p>%s"
              % (escape(title), escape(detail["generated_at"]),
                 _refresh_banner(detail["refreshed"])
                 + ("<section class='card banner'><b>缺漏</b><ul>%s</ul></section>" % missing if missing else "")))
    return ("<!doctype html><html lang=zh-Hant><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><title>%s｜個股詳情</title>"
            "<style>%s</style></head><body><main>%s%s</main></body></html>"
            % (escape(title), STYLE, header, "".join(sections)))
