"""訊號門檻校準：用已對帳預測挑偏多／偏空門檻，前段挑、後段驗，使用者核准才生效。

構想借自 QuantDinger ai_calibration（對帳結果回寫門檻），但修掉它的三個問題：
- 同一批資料挑門檻又算命中率 → 依時間切前後段，且剔除對帳期間跨進後段的前段樣本
- 對錯標準不一致（HOLD ±5% vs BUY >2%）→ 統一用平均方向報酬，並要求贏過「全判偏多」
- 啟動時自動套用 → 預設只出提案，--apply 才寫入
"""

import json
from datetime import date, datetime

import score as scoring

BULL_CANDIDATES = range(50, 80, 5)   # 50..75
BEAR_CANDIDATES = range(25, 55, 5)   # 25..50
MIN_RESOLVED = 120
MIN_WEEKS = 12          # 同週預測被同一段大盤牽動，有效樣本看週數而非筆數
TRAIN_RATIO = 0.7
MIN_SIDE_SAMPLE = 15    # 偏多、偏空各自最少筆數，防止門檻推到極端靠少數樣本取勝
PART_COLUMNS = ("s_trend", "s_bias", "s_support", "s_volume", "s_macd", "s_rsi")
BULLISH = tuple(scoring.SIGNAL_LABELS[:2])
BEARISH = tuple(scoring.SIGNAL_LABELS[3:])


def resolved_rows(conn):
    return conn.execute(
        "SELECT * FROM predictions WHERE status = 'resolved' AND return_pct IS NOT NULL"
        " ORDER BY created_at, id").fetchall()


def gate_status(rows):
    """樣本門檻：回傳 (是否通過, 已對帳筆數, 涵蓋週數)。"""
    weeks = len({datetime.strptime(r["created_at"], "%Y-%m-%d").isocalendar()[:2]
                 for r in rows})
    return len(rows) >= MIN_RESOLVED and weeks >= MIN_WEEKS, len(rows), weeks


def resignal(row, bull, bear):
    """照新門檻重判訊號，並重現當時觸發的硬規則（壓至中性、降一級），順序同 score.evaluate。

    不可用 row["score"]：那是被當時門檻壓制過的分數，舊門檻偏低時會壓到中性以下，
    換門檻後誤判成偏空。六維分項加總才是壓制前的原始分。
    """
    rules = json.loads(row["hard_rules"] or "[]")
    total = sum(row[column] for column in PART_COLUMNS)
    if any(scoring.CAP_RULE_MARK in rule for rule in rules):
        total = min(total, bull - 1)
    signal = scoring.to_signal(total, bull, bear)
    if any(scoring.DOWNGRADE_RULE_MARK in rule for rule in rules):
        signal = scoring.downgrade(signal)
    return signal


def evaluate_thresholds(rows, bull, bear):
    """回傳 (平均方向報酬 %, 偏多筆數, 偏空筆數)。偏空的報酬取負號；中性不計入。"""
    bull_returns, bear_returns = [], []
    for row in rows:
        signal = resignal(row, bull, bear)
        if signal in BULLISH:
            bull_returns.append(row["return_pct"])
        elif signal in BEARISH:
            bear_returns.append(-row["return_pct"])
    directional = bull_returns + bear_returns
    metric = sum(directional) / len(directional) if directional else None
    return metric, len(bull_returns), len(bear_returns)


def split_train_valid(rows):
    """依建立日切前後段，同一天的預測不拆開。

    前段中對帳日落在後段起點（含）之後者剔除：它的報酬期間與後段重疊，
    等於挑門檻時已看過後段的行情。
    """
    cut = rows[int(len(rows) * TRAIN_RATIO)]["created_at"]
    train = [r for r in rows if r["created_at"] < cut and r["resolve_date"] < cut]
    valid = [r for r in rows if r["created_at"] >= cut]
    return train, valid, cut


def search_best(train):
    """在前段挑平均方向報酬最高的門檻組；任一邊不足 MIN_SIDE_SAMPLE 的組合不列入。"""
    best = None
    for bull in BULL_CANDIDATES:
        for bear in BEAR_CANDIDATES:
            if bear >= bull:
                continue
            metric, n_bull, n_bear = evaluate_thresholds(train, bull, bear)
            if metric is None or min(n_bull, n_bear) < MIN_SIDE_SAMPLE:
                continue
            if best is None or metric > best["train_metric"]:
                best = {"bull": bull, "bear": bear, "train_metric": metric}
    return best


def _rejection_reasons(proposal):
    reasons = []
    if min(proposal["valid_bull_n"], proposal["valid_bear_n"]) < MIN_SIDE_SAMPLE:
        reasons.append("後段偏多 %d 筆／偏空 %d 筆，任一邊少於 %d"
                       % (proposal["valid_bull_n"], proposal["valid_bear_n"], MIN_SIDE_SAMPLE))
    valid_metric = proposal["valid_metric"]
    if valid_metric is None or valid_metric <= proposal["baseline_metric"]:
        reasons.append("後段平均方向報酬未贏過「全判偏多」對照組")
    current_metric = proposal["current_metric"]
    if valid_metric is not None and current_metric is not None and valid_metric <= current_metric:
        reasons.append("後段表現沒有贏過目前門檻（平手也不換，避免無意義的版本更迭）")
    return reasons


def run_calibration(conn):
    """產生校準提案，不寫 DB。verdict：adopt / keep / reject / insufficient。"""
    rows = resolved_rows(conn)
    passed, count, weeks = gate_status(rows)
    proposal = {"resolved": count, "weeks": weeks, "verdict": "insufficient", "reasons": []}
    if not passed:
        proposal["reasons"].append("樣本不足：已對帳 %d/%d 筆、涵蓋 %d/%d 週"
                                   % (count, MIN_RESOLVED, weeks, MIN_WEEKS))
        return proposal

    train, valid, cut = split_train_valid(rows)
    proposal.update({"valid_start": cut, "train_n": len(train), "valid_n": len(valid)})
    best = search_best(train)
    if best is None:
        proposal["verdict"] = "reject"
        proposal["reasons"].append("前段沒有任何門檻組讓偏多、偏空各達 %d 筆" % MIN_SIDE_SAMPLE)
        return proposal

    current = scoring.load_thresholds(conn)
    valid_metric, n_bull, n_bear = evaluate_thresholds(valid, best["bull"], best["bear"])
    current_metric = evaluate_thresholds(valid, current["bull"], current["bear"])[0]
    proposal.update(best, current=current, valid_metric=valid_metric,
                    current_metric=current_metric, valid_bull_n=n_bull, valid_bear_n=n_bear,
                    baseline_metric=sum(r["return_pct"] for r in valid) / len(valid))
    if (best["bull"], best["bear"]) == (current["bull"], current["bear"]):
        proposal["verdict"] = "keep"
        return proposal
    proposal["reasons"] = _rejection_reasons(proposal)
    proposal["verdict"] = "reject" if proposal["reasons"] else "adopt"
    return proposal


def save_calibration(conn, proposal):
    cursor = conn.execute(
        "INSERT INTO calibrations (created_at, bull_threshold, bear_threshold, train_n,"
        " valid_n, train_metric, valid_metric, baseline_metric, current_metric, adopted)"
        " VALUES (?,?,?,?,?,?,?,?,?,1)",
        (date.today().isoformat(), proposal["bull"], proposal["bear"], proposal["train_n"],
         proposal["valid_n"], proposal["train_metric"], proposal["valid_metric"],
         proposal["baseline_metric"], proposal["current_metric"]))
    conn.commit()
    return cursor.lastrowid


def _format_metric(value):
    return "—" if value is None else "%+.2f%%" % value


def print_proposal(proposal):
    print("=== 訊號門檻校準 ===")
    print("已對帳 %d 筆、涵蓋 %d 週" % (proposal["resolved"], proposal["weeks"]))
    if "bull" in proposal:
        current = proposal["current"]
        print("前段 %d 筆（剔除重疊後）／後段 %d 筆（%s 起）"
              % (proposal["train_n"], proposal["valid_n"], proposal["valid_start"]))
        print("候選門檻：偏多≥%d／偏空<%d（目前 偏多≥%d／偏空<%d）"
              % (proposal["bull"], proposal["bear"], current["bull"], current["bear"]))
        print("平均方向報酬：前段 %s｜後段 %s｜後段沿用目前門檻 %s｜後段全判偏多 %s"
              % tuple(_format_metric(proposal[key]) for key in
                      ("train_metric", "valid_metric", "current_metric", "baseline_metric")))
        print("後段偏多 %d 筆／偏空 %d 筆" % (proposal["valid_bull_n"], proposal["valid_bear_n"]))
    verdicts = {"adopt": "建議採用", "keep": "目前門檻已是最佳，不需更新",
                "reject": "不建議採用", "insufficient": "拒絕校準"}
    print("結論：%s" % verdicts[proposal["verdict"]])
    for reason in proposal["reasons"]:
        print("  - %s" % reason)


def cmd_calibrate(conn, args):
    proposal = run_calibration(conn)
    print_proposal(proposal)
    if not args.apply:
        if proposal["verdict"] == "adopt":
            print("尚未寫入。確認採用請加 --apply。")
        return
    if proposal["verdict"] != "adopt":
        raise RuntimeError("提案未通過驗證，拒絕寫入")
    calibration_id = save_calibration(conn, proposal)
    print("已核准第 %d 版門檻：偏多≥%d／偏空<%d，之後的 record 開始生效"
          % (calibration_id, proposal["bull"], proposal["bear"]))


def print_threshold_status(conn):
    """report 用：目前門檻版本、距校準樣本門檻的進度、各版本的方向命中率。"""
    current = scoring.load_thresholds(conn)
    version = ("預設" if current["calibration_id"] is None
               else "第 %d 版" % current["calibration_id"])
    rows = resolved_rows(conn)
    passed, count, weeks = gate_status(rows)
    print("\n--- 訊號門檻 ---")
    print("目前：%s（偏多≥%d／偏空<%d）" % (version, current["bull"], current["bear"]))
    print("校準樣本：已對帳 %d/%d 筆、涵蓋 %d/%d 週 → %s"
          % (count, MIN_RESOLVED, weeks, MIN_WEEKS,
             "可執行 track.py calibrate" if passed else "未達門檻，calibrate 會拒絕"))
    groups = {}
    for row in rows:
        if row["hit"] is not None:
            groups.setdefault(row["calibration_id"], []).append(row["hit"])
    for calibration_id, hits in sorted(groups.items(), key=lambda item: item[0] or 0):
        label = "預設門檻" if calibration_id is None else "第 %d 版" % calibration_id
        print("  %-8s 方向預測 %4d 筆  命中率 %5.1f%%"
              % (label, len(hits), sum(hits) / len(hits) * 100))
