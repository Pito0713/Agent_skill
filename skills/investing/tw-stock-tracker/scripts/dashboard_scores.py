"""每日評分快照的唯讀呈現；SVG 不依賴外部資源。"""

from html import escape

from dashboard_views import _num, _table, _ticker_link

EMPTY_MESSAGE = "尚無評分快照（執行 daily_score.py run / backfill 後出現）"
DISCLAIMER = '<p class="warn"><strong>未驗證：分數趨勢與排行未經驗證，不代表進出場建議。</strong></p>'


def render_rankings(items: list[dict]) -> str:
    rows = []
    for item in items:
        ticker = (_ticker_link(item["ticker"], item["name"]) if item.get("has_detail")
                  else "%s %s" % (escape(item["ticker"]), escape(item["name"] or "")))
        numbers = [_num(item["score"], "%.0f")]
        numbers += ["—" if item[key] is None else _num(item[key], "%.0f", True)
                    for key in ("delta_5", "delta_20")]
        rows.append("<tr><td>%s</td><td>%s</td>%s</tr>" % (
            ticker, escape(item["date"]), "".join('<td class="num">%s</td>' % n for n in numbers)))
    body = (_table(["代號", "最新日期", "分數", "5 日 Δ", "20 日 Δ"], rows)
            if rows else '<p class="note">%s</p>' % EMPTY_MESSAGE)
    return ('<section class="card banner"><h2>評分排行</h2>%s%s'
            '<p class="note">各檔採最新快照；Δ 依快照交易日列數計，資料不足顯示 —。</p></section>'
            % (DISCLAIMER, body))


def _render_point(item: dict, coordinates: tuple[float, float]) -> str:
    horizontal, vertical = coordinates
    is_live = item["source"] == "live"
    style = 'fill="currentColor"' if is_live else 'fill="var(--card)" stroke-dasharray="2 1"'
    marker = "score-live" if is_live else "score-backfill"
    title = "%s｜%s 分｜%s" % (item["date"], item["score"], item["source"])
    return ('<circle class="%s" cx="%.2f" cy="%.2f" r="4" stroke="currentColor" %s>'
            '<title>%s</title></circle>' % (marker, horizontal, vertical, style, escape(title)))


def _render_chart(items: list[dict]) -> str:
    coordinates = [(45 + index * 610 / (len(items) - 1), 220 - float(item["score"]) * 2)
                   for index, item in enumerate(items)]
    points = " ".join("%.2f,%.2f" % point for point in coordinates)
    axes = "".join(
        '<line x1="45" y1="%d" x2="655" y2="%d" stroke="var(--line)"/>'
        '<text x="35" y="%d" text-anchor="end" fill="currentColor">%d</text>'
        % (220 - score * 2, 220 - score * 2, 224 - score * 2, score)
        for score in (0, 50, 100))
    markers = "".join(_render_point(item, point) for item, point in zip(items, coordinates))
    return ('<svg viewBox="0 0 700 260" role="img" aria-label="總分趨勢，縱軸 0 至 100"'
            ' style="width:100%%;max-width:900px"><title>最近 %d 筆總分趨勢</title>%s'
            '<polyline points="%s" fill="none" stroke="currentColor" stroke-width="2"/>%s'
            '<text x="45" y="250" fill="currentColor">%s</text>'
            '<text x="655" y="250" text-anchor="end" fill="currentColor">%s</text></svg>'
            % (len(items), axes, points, markers, escape(items[0]["date"]), escape(items[-1]["date"])))


def render_trend(items: list[dict]) -> str:
    if not items:
        body = '<p class="note">%s</p>' % EMPTY_MESSAGE
    elif len(items) == 1:
        body = '<p class="note">僅 1 筆評分快照（%s，%s 分），至少 2 筆才能繪製趨勢。</p>' % (
            escape(items[0]["date"]), _num(items[0]["score"], "%.0f"))
    else:
        body = _render_chart(items[-60:])
    return ('<section class="card banner"><h2>分數趨勢</h2>%s%s'
            '<p class="note">圖例：● 實心 live（當日快照）；○ 空心虛線 backfill（事後回補）。'
            '橫軸按快照順序排列，縱軸固定 0–100。</p></section>' % (DISCLAIMER, body))
