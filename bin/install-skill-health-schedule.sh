#!/usr/bin/env bash
# install-skill-health-schedule.sh — 安裝／移除 skill 體檢的 launchd 排程（每週二、五 10:00，含 B 層）。
# 規格：plans/skill-health-check.md §4 T4。plist 屬於每台機器自己的設定，不進 repo。
#
# 用法：
#   bash bin/install-skill-health-schedule.sh --dry-run    只印 plist，不寫檔、不 load
#   bash bin/install-skill-health-schedule.sh              寫 plist 並 launchctl load
#   bash bin/install-skill-health-schedule.sh --uninstall  launchctl unload 並刪 plist
#
# 環境變數（皆可選，主要給測試用）：
#   SKILL_HEALTH_LAUNCH_AGENTS_DIR  plist 目錄（預設 $HOME/Library/LaunchAgents）
#   SKILL_HEALTH_LAUNCHCTL          launchctl 指令（預設 launchctl）
#   SKILL_HEALTH_CLAUDE_CMD         解析 claude 位置用的指令名（預設 claude）

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_SCRIPT="$SCRIPT_DIR/skill-health.sh"
LABEL="local.agent-skill.health"
AGENTS_DIR="${SKILL_HEALTH_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
LAUNCHCTL="${SKILL_HEALTH_LAUNCHCTL:-launchctl}"
PLIST_PATH="$AGENTS_DIR/$LABEL.plist"
LOG_DIR="$HOME/.agent-reports/skill-health"
BASE_PATH_DIRS=(/opt/homebrew/bin /usr/local/bin /usr/bin /bin /usr/sbin /sbin)

log_message() { printf 'install-skill-health-schedule: %s\n' "$*" >&2; }

xml_escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

# launchd 的 PATH 極簡：用 claude 所在目錄 + 常見目錄組成絕對路徑清單（去重）
build_path_value() {
  local claude_dir="$1" result="$1" dir
  for dir in "${BASE_PATH_DIRS[@]}"; do
    case ":$result:" in *":$dir:"*) ;; *) result="$result:$dir" ;; esac
  done
  printf '%s' "$result"
}

resolve_claude_dir() {
  local claude_path
  claude_path=$(command -v "${SKILL_HEALTH_CLAUDE_CMD:-claude}") || return 1
  [[ "$claude_path" == /* ]] || return 1
  dirname "$claude_path"
}

print_plist() {
  local path_value="$1" script log_path
  script=$(xml_escape "$HEALTH_SCRIPT"); path_value=$(xml_escape "$path_value"); log_path=$(xml_escape "$LOG_DIR/launchd.log")
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$script</string>
    <string>--with-review</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict>
      <key>Weekday</key>
      <integer>2</integer>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>5</integer>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$path_value</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$log_path</string>
  <key>StandardErrorPath</key>
  <string>$log_path</string>
</dict>
</plist>
EOF
}

do_install() {
  local dry_run="$1" claude_dir path_value
  [[ -f "$HEALTH_SCRIPT" ]] || { log_message "找不到 $HEALTH_SCRIPT"; return 1; }
  claude_dir=$(resolve_claude_dir) || { log_message "找不到 claude（command -v ${SKILL_HEALTH_CLAUDE_CMD:-claude} 無結果）；B 層需要它，請先安裝或把它加進 PATH"; return 1; }
  path_value=$(build_path_value "$claude_dir")
  if [[ $dry_run -eq 1 ]]; then print_plist "$path_value"; return 0; fi
  # launchd 在腳本執行前就開 log 檔，目錄須先存在
  mkdir -p "$AGENTS_DIR" "$LOG_DIR" || { log_message "無法建立目錄"; return 1; }
  # 重新安裝：先卸載舊的（沒載入過會失敗，忽略）
  [[ ! -f "$PLIST_PATH" ]] || "$LAUNCHCTL" unload "$PLIST_PATH" >/dev/null 2>&1 || true
  print_plist "$path_value" >"$PLIST_PATH" || { log_message "寫入 $PLIST_PATH 失敗"; return 1; }
  "$LAUNCHCTL" load "$PLIST_PATH" || { log_message "launchctl load 失敗：$PLIST_PATH"; return 1; }
  echo "已安裝並載入：${PLIST_PATH}（驗證：launchctl list | grep agent-skill.health）"
}

do_uninstall() {
  if [[ $1 -eq 1 ]]; then echo "[dry-run] 會執行：launchctl unload $PLIST_PATH 並刪除該檔"; return 0; fi
  if [[ ! -f "$PLIST_PATH" ]]; then echo "未安裝（找不到 ${PLIST_PATH}），無需移除"; return 0; fi
  "$LAUNCHCTL" unload "$PLIST_PATH" || log_message "launchctl unload 失敗（可能未載入），仍會刪除 plist"
  rm -f "$PLIST_PATH" || { log_message "刪除 $PLIST_PATH 失敗"; return 1; }
  echo "已移除：$PLIST_PATH"
}

main() {
  local dry_run=0 uninstall=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run=1 ;;
      --uninstall) uninstall=1 ;;
      *) log_message "未知參數：$1（支援：--dry-run、--uninstall）"; return 64 ;;
    esac
    shift
  done
  if [[ $uninstall -eq 1 ]]; then do_uninstall "$dry_run"; else do_install "$dry_run"; fi
}

main "$@"
