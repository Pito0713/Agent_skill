#!/usr/bin/env bash
# hooks/pre-tool-run.sh
# Claude Code PreToolUse hook：攔截危險指令，要求確認
#
# 設定方式（.claude/settings.json）：
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Bash",
#         "hooks": [{ "type": "command", "command": "bash hooks/pre-tool-run.sh" }]
#       }
#     ]
#   }
# }
#
# Claude Code 會將指令以 JSON 傳入 stdin：
# { "tool_name": "Bash", "tool_input": { "command": "rm -rf ..." } }

set -euo pipefail

# 讀取 stdin（Claude Code 傳入的指令資訊）
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('tool_input', {}).get('command', ''))" 2>/dev/null || echo "")

if [[ -z "$COMMAND" ]]; then
  exit 0  # 無法解析，放行
fi

# ─────────────────────────────────────────
# 危險指令清單
# ─────────────────────────────────────────

# Level 1：直接阻擋（不論任何情況）
BLOCKED_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \$HOME"
  "dd if=/dev/zero"
  "mkfs\."
  "> /dev/sda"
  "chmod -R 777 /"
  "curl.*\| *bash"
  "wget.*\| *bash"
  "curl.*\| *sh"
  ":(){:|:&};:"          # Fork bomb
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "🚫 BLOCKED: Dangerous command detected"
    echo "   Pattern matched: $pattern"
    echo "   Command: $COMMAND"
    echo ""
    echo "This command has been blocked by pre-tool-run hook."
    echo "If you're certain this is safe, run it manually in your terminal."
    exit 1
  fi
done

# Level 2：高風險指令，輸出警告（讓 Claude 看到）
HIGH_RISK_PATTERNS=(
  "rm -rf"
  "DROP TABLE"
  "DROP DATABASE"
  "DELETE FROM.*WHERE"
  "truncate"
  "git push.*--force"
  "git push.*-f "
  "kubectl delete"
  "terraform destroy"
  "aws.*delete"
  "gcloud.*delete"
)

WARNINGS=()
for pattern in "${HIGH_RISK_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$pattern"; then
    WARNINGS+=("$pattern")
  fi
done

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
  echo "⚠️  HIGH-RISK COMMAND DETECTED"
  echo "   Command: $COMMAND"
  echo "   Matched patterns: ${WARNINGS[*]}"
  echo ""
  echo "Please verify this is intentional before proceeding."
  echo "Consider: Does this need a backup first? Is there a dry-run option?"
  # 警告但不阻擋，讓 Claude 自行判斷
fi

# Level 3：生產環境操作偵測
PROD_INDICATORS=(
  "production"
  "prod-"
  "-prod\b"
  "PROD_"
  "live-"
)

for indicator in "${PROD_INDICATORS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$indicator"; then
    echo "🔴 PRODUCTION ENVIRONMENT DETECTED in command"
    echo "   Command: $COMMAND"
    echo "   Ensure you have verified this in staging first."
    break
  fi
done

exit 0
