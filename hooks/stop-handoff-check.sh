#!/usr/bin/env bash
# stop-handoff-check.sh — 【已停用，待刪除】ADR-015（2026-07-31）
#
# 本檔即將刪除。保留至下游 6 個掛載點移除為止——先刪檔會讓那些掛載變成
# exit 127「command not found」，故順序為：kill-switch → 清下游掛載 → 刪本檔。
#
# 停用原因（ADR-015）：交接觸發權全數歸還使用者。Stop hook 的觸發源是 harness
# 生命週期事件（一輪回應結束），而「收工」是使用者的意圖宣告——hook 在原理上
# 觀測不到後者，只能猜。ADR-014 已停用本 hook 但未移除下游掛載，導致 2026-07-27
# 至 07-31 間仍有 6 次 BLOCK 橫跨 3 個專案。
#
# 取代方案：純 L1——使用者說「handoff / 收工 / 交接」才寫 latest.md，模型只負責
# 在段落完成時提醒一次，不攔截。見 governance/enforcement-layers.md §4。
#
# 以下原始邏輯保留供考古，永不執行。

exit 0

set -u   # 不用 -e：fail-open

INPUT=$(cat 2>/dev/null) || exit 0
export INPUT

LOG_DIR="$HOME/.agent-sessions"
mkdir -p "$LOG_DIR" 2>/dev/null

if [[ "${AGENT_SKILL_HOOK_BYPASS:-0}" == "1" ]]; then
  echo "$(date '+%F %T') stop-handoff-check BYPASS pwd=$PWD" >> "$LOG_DIR/hook.log" 2>/dev/null
  exit 0
fi

command -v python3 >/dev/null 2>&1 || exit 0

python3 - <<'PY' 2>/dev/null || exit 0
import json, os, subprocess, sys, time
from pathlib import Path

def allow():
    sys.exit(0)

try:
    data = json.loads(os.environ.get("INPUT", "{}"))
except Exception:
    allow()

# 防死循環：本 session 已被 Stop hook 擋過一次 → 放行
if data.get("stop_hook_active"):
    allow()

cwd = data.get("cwd") or os.getcwd()
transcript = data.get("transcript_path", "")

# 非 git 專案不在鐵律 1 範圍
r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                   capture_output=True, text=True)
if r.returncode != 0:
    allow()
repo = r.stdout.strip()
project = os.path.basename(repo)
latest = Path.home() / ".agent-sessions" / project / "latest.md"

if not transcript or not os.path.exists(transcript):
    allow()

# 掃 transcript（字串比對，不逐行 json.loads——transcript 可能數十 MB）：
#   wrote_repo   = 本 session 有 Write/Edit/NotebookEdit 落在 repo 內，或 Bash 跑過 git commit
#   wrote_latest = 本 session 碰過 latest.md
wrote_repo = False
wrote_latest = False
latest_str = str(latest)
write_tools = ('"Write"', '"Edit"', '"NotebookEdit"')
try:
    with open(transcript, errors="ignore") as f:
        for line in f:
            if "tool_use" not in line:
                continue
            if latest_str in line:
                wrote_latest = True
            if not wrote_repo:
                if (repo + "/" in line and any(t in line for t in write_tools)) or \
                   ('"Bash"' in line and "git commit" in line):
                    wrote_repo = True
            if wrote_repo and wrote_latest:
                break
except OSError:
    allow()

if not wrote_repo:
    allow()

# latest.md 在 session 期間被更新（含本 session 外的手動更新）也算已交接
try:
    if latest.exists() and latest.stat().st_mtime >= os.path.getctime(transcript):
        wrote_latest = True
except OSError:
    pass

if wrote_latest:
    allow()

# 擋下收工，回饋補救指令
try:
    with open(Path.home() / ".agent-sessions" / "hook.log", "a") as lg:
        lg.write(f"{time.strftime('%F %T')} stop-handoff-check BLOCK repo={repo}\n")
except OSError:
    pass

reason = (
    f"[stop-handoff-check] 本 session 修改了 {project}，但交接檔 {latest} 未更新"
    "（鐵律 1「交接必落地」）。收工前請：\n"
    "1. 依 ~/Agent_skill/skills/productivity/handoff/SKILL.md「Phase 最終」格式更新 latest.md"
    "（寫入前先重讀現有內容——若「最後更新」晚於本輪開工時間，必須合併、禁止整檔覆蓋）\n"
    "2. 用 Agent tool 喚醒查核員：prompt 採 ~/Agent_skill/agents/06-governance/handoff-verifier.md，"
    "查核通過再收工\n"
    "（本提醒每 session 僅出現一次；緊急情況可 AGENT_SKILL_HOOK_BYPASS=1 旁路，事件會留檔）"
)
print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
sys.exit(0)
PY
exit 0
