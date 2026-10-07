"""訊號門檻校準的離線測試：合成對帳樣本，不打網路、不碰正式 DB。"""

import argparse
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import calibrate  # noqa: E402
import db  # noqa: E402
import score  # noqa: E402
import track  # noqa: E402

# 每週一組分數與對應報酬。設計成 偏多≥70／偏空<35 是唯一最佳解：
# 62、66 判偏多會賠，38、42 判偏空會賠；72、32 讓邊界門檻嚴格優於鄰近候選。
WEEKLY_SAMPLES = [(20, -4), (25, -4), (32, -6), (38, 3), (42, 3), (50, 0),
                  (55, 0), (62, -3), (66, -3), (72, 6), (80, 4), (88, 4)]
FIRST_MONDAY = date(2027, 1, 4)
HORIZON_DAYS = 14


def insert_resolved(conn, created_at, score_value, return_pct, hard_rules=()):
    """原始分放在 s_trend，其餘分項為 0，使分項加總 = 原始分。"""
    resolve_date = created_at + timedelta(days=HORIZON_DAYS)
    conn.execute(
        "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
        " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
        " signal, hard_rules, status, resolve_date, return_pct, hit)"
        " VALUES (?, '2330', ?, 100, 100, ?, ?, 0, 0, 0, 0, 0, '中性', ?, 'resolved', ?, ?, NULL)",
        (created_at.isoformat(), HORIZON_DAYS, score_value, score_value,
         json.dumps(list(hard_rules), ensure_ascii=False), resolve_date.isoformat(), return_pct))


def seed_weeks(conn, weeks, samples=WEEKLY_SAMPLES, start_week=0):
    for week in range(start_week, start_week + weeks):
        for score_value, return_pct in samples:
            insert_resolved(conn, FIRST_MONDAY + timedelta(weeks=week), score_value, return_pct)
    conn.commit()


class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def run_command(self, apply):
        with mock.patch("builtins.print"):
            calibrate.cmd_calibrate(self.conn, argparse.Namespace(apply=apply))

    def calibration_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM calibrations").fetchone()[0]

    def test_too_few_rows_is_refused_even_with_apply(self):
        seed_weeks(self.conn, 9)                          # 108 筆 < 120
        self.assertEqual(calibrate.run_calibration(self.conn)["verdict"], "insufficient")
        with self.assertRaises(RuntimeError):
            self.run_command(apply=True)
        self.assertEqual(self.calibration_count(), 0)

    def test_enough_rows_but_too_few_weeks_is_refused(self):
        seed_weeks(self.conn, 5, WEEKLY_SAMPLES * 3)      # 180 筆，只有 5 週
        proposal = calibrate.run_calibration(self.conn)
        self.assertEqual((proposal["resolved"], proposal["weeks"]), (180, 5))
        self.assertEqual(proposal["verdict"], "insufficient")

    def test_split_drops_train_rows_whose_outcome_overlaps_validation(self):
        seed_weeks(self.conn, 20)
        rows = calibrate.resolved_rows(self.conn)
        train, valid, cut = calibrate.split_train_valid(rows)
        self.assertTrue(all(r["resolve_date"] < cut for r in train))
        self.assertTrue(all(r["created_at"] >= cut for r in valid))
        overlapping = [r for r in rows if r["created_at"] < cut <= r["resolve_date"]]
        self.assertTrue(overlapping)                      # 確實有被剔除的樣本
        self.assertEqual(len(train) + len(valid) + len(overlapping), len(rows))

    def test_finds_best_thresholds_and_writes_only_on_apply(self):
        seed_weeks(self.conn, 20)
        proposal = calibrate.run_calibration(self.conn)
        self.assertEqual(proposal["verdict"], "adopt", proposal["reasons"])
        self.assertEqual((proposal["bull"], proposal["bear"]), (70, 35))
        self.assertGreater(proposal["valid_metric"], proposal["current_metric"])

        self.run_command(apply=False)
        self.assertEqual(self.calibration_count(), 0)
        self.run_command(apply=True)
        thresholds = score.load_thresholds(self.conn)
        self.assertEqual((thresholds["bull"], thresholds["bear"]), (70, 35))
        self.assertIsNotNone(thresholds["calibration_id"])

        self.assertEqual(calibrate.run_calibration(self.conn)["verdict"], "keep")

    def test_losing_to_always_bullish_baseline_is_rejected(self):
        bull_market = [(score_value, 5) for score_value, _ in WEEKLY_SAMPLES]
        seed_weeks(self.conn, 20, bull_market)
        proposal = calibrate.run_calibration(self.conn)
        self.assertEqual(proposal["verdict"], "reject")
        self.assertIn("後段平均方向報酬未贏過「全判偏多」對照組", proposal["reasons"])
        with self.assertRaises(RuntimeError):
            self.run_command(apply=True)

    def test_thresholds_chosen_on_train_fail_on_validation(self):
        seed_weeks(self.conn, 14)                         # 前段：70/35 最佳
        # 後段行情反轉且放大 5 倍：若搜尋誤用全部資料或後段，挑出的就不會是 70/35
        reversed_samples = [(s, -5 * r) for s, r in WEEKLY_SAMPLES]
        seed_weeks(self.conn, 6, reversed_samples, start_week=14)
        proposal = calibrate.run_calibration(self.conn)
        self.assertEqual(proposal["valid_start"], (FIRST_MONDAY + timedelta(weeks=14)).isoformat())
        self.assertEqual((proposal["bull"], proposal["bear"]), (70, 35))
        self.assertEqual(proposal["verdict"], "reject")

    def test_tie_with_current_thresholds_is_rejected(self):
        polarized = [(20, -4)] * 6 + [(80, 4)] * 6        # 任何門檻組的方向報酬都是 4%
        seed_weeks(self.conn, 20, polarized)
        proposal = calibrate.run_calibration(self.conn)
        self.assertNotEqual((proposal["bull"], proposal["bear"]), (60, 45))
        self.assertEqual(proposal["valid_metric"], proposal["current_metric"])
        self.assertEqual(proposal["verdict"], "reject")

    def test_record_stores_calibration_id_in_effect(self):
        fake = {"date": "2027-06-01", "close": 100.0, "adj_close": 100.0, "final_score": 72,
                "parts": dict.fromkeys(("trend", "bias", "support", "volume", "macd", "rsi"), 0),
                "signal": "偏多", "entry_low": None, "entry_high": None, "stop_loss": None,
                "hard_rules": [], "flags": [],
                "thresholds": {"calibration_id": 7, "bull": 70, "bear": 35}}
        args = argparse.Namespace(ticker="2330", horizon=30, thesis="test")
        with mock.patch.object(track.fetch_twse, "sync_ticker"), \
                mock.patch.object(track.scoring, "evaluate", return_value=fake), \
                mock.patch("builtins.print"):
            track.cmd_record(self.conn, args)
        row = self.conn.execute("SELECT calibration_id FROM predictions").fetchone()
        self.assertEqual(row["calibration_id"], 7)


class SignalReplayTest(unittest.TestCase):
    """回測時要能重現當時的硬規則，否則門檻一動，被壓制的高風險樣本會被當成偏多。"""

    def row(self, raw_total, rules, stored_score=None):
        row = dict.fromkeys(calibrate.PART_COLUMNS, 0)
        row.update(s_trend=raw_total, hard_rules=json.dumps(rules, ensure_ascii=False),
                   score=raw_total if stored_score is None else stored_score)
        return row

    def test_capped_score_from_lower_old_threshold_is_recapped_from_raw_total(self):
        # 舊門檻偏多 50 時，原始 80 分被壓成 49 存檔；新門檻 60/50 下 evaluate 會壓成 59 → 中性
        capped = self.row(80, ["RSI>80 超買，訊號壓至中性"], stored_score=49)
        self.assertEqual(calibrate.resignal(capped, 60, 50), "中性")

    def test_capped_score_stays_neutral_under_lower_bull_threshold(self):
        capped = self.row(70, ["RSI>80 超買，訊號壓至中性"], stored_score=59)
        self.assertEqual(calibrate.resignal(capped, 55, 40), "中性")
        self.assertEqual(calibrate.resignal(self.row(59, []), 55, 40), "偏多")

    def test_downgrade_applies_after_cap(self):
        rules = ["RSI>80 超買，訊號壓至中性", "量能不足均量50%，訊號降一級"]
        self.assertEqual(calibrate.resignal(self.row(70, rules, stored_score=59), 55, 40), "偏空")

    def test_hard_rule_cap_follows_bull_threshold(self):
        result = {"score": 80, "thresholds": {"calibration_id": 1, "bull": 70, "bear": 35}}
        rows = [{"close": 100}, {"high": 101, "volume": 1000}]
        score.apply_hard_rules(result, 85, 0, rows, 1000)
        self.assertEqual(result["score_capped"], 69)
        self.assertEqual(score.to_signal(69, 70, 35), "中性")

    def test_default_bands_unchanged(self):
        expected = {75: "強烈偏多", 60: "偏多", 59: "中性", 45: "中性",
                    44: "偏空", 30: "偏空", 29: "強烈偏空"}
        for value, label in expected.items():
            self.assertEqual(score.to_signal(value), label)


if __name__ == "__main__":
    unittest.main()
