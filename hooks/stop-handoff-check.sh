#!/usr/bin/env bash
# stop-handoff-check.sh — Claude Code Stop hook：收工守門（交接必落地）
#
# 對應正本條文（enforcement-layers.md §5 防漂移：改正本時同步檢查本檔）：
#   - ~/.claude/CLAUDE.md 鐵律 1「交接必落地」；Agent_skill CLAUDE.md 鐵律 6
#   - ~/Agent_skill/governance/maintenance-protocol.md §6（交接正本規約）
#   - 設計與驗收標準：~/Agent_skill/governance/enforcement-layers.md §4
#
# 行為：本 session 對 git repo 有寫入、但 ~/.agent-sessions/<專案>/latest.md 未更新
#       → 擋下這次收工並提示補交接 + 喚醒 handoff-verifier。
# 防死循環：stop_hook_active=true（已因 Stop hook 續跑過）→ 放行，每 session 僅擋一次。
# 旁路：AGENT_SKILL_HOOK_BYPASS=1（事件記入 ~/.agent-sessions/hook.log 供事後審）。
# 失敗策略：fail-open——解析失敗、python3 缺席、任何內部錯誤一律放行，不阻塞收工。

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
    "1. 依 ~/Agent_skill/skills/productivity/handoff.md「Phase 最終」格式更新 latest.md"
    "（寫入前先重讀現有內容——若「最後更新」晚於本輪開工時間，必須合併、禁止整檔覆蓋）\n"
    "2. 用 Agent tool 喚醒查核員：prompt 採 ~/Agent_skill/agents/06-governance/handoff-verifier.md，"
    "查核通過再收工\n"
    "（本提醒每 session 僅出現一次；緊急情況可 AGENT_SKILL_HOOK_BYPASS=1 旁路，事件會留檔）"
)
print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
sys.exit(0)
PY
exit 0
