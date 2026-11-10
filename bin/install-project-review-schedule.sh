#!/usr/bin/env bash
# install-project-review-schedule.sh — 安裝／移除 project-review 的 launchd 排程（每天 09:00）。
# 錯開 skill 體檢（週二、五 10:00）。plist 屬於每台機器自己的設定，不進 repo。
# 寫法沿用 install-skill-health-schedule.sh（第二處重複，依「第三次才抽」先不抽共用 lib）。
#
# 用法：
#   bash bin/install-project-review-schedule.sh --dry-run    只印 plist，不寫檔、不 load
#   bash bin/install-project-review-schedule.sh              寫 plist 並 launchctl load
#   bash bin/install-project-review-schedule.sh --uninstall  launchctl unload 並刪 plist
#
# 環境變數（皆可選，主要給測試用）：
#   PROJECT_REVIEW_LAUNCH_AGENTS_DIR  plist 目錄（預設 $HOME/Library/LaunchAgents）
#   PROJECT_REVIEW_LAUNCHCTL          launchctl 指令（預設 launchctl）

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REVIEW_SCRIPT="$SCRIPT_DIR/project-review.py"
LABEL="local.agent-skill.project-review"
AGENTS_DIR="${PROJECT_REVIEW_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
LAUNCHCTL="${PROJECT_REVIEW_LAUNCHCTL:-launchctl}"
PLIST_PATH="$AGENTS_DIR/$LABEL.plist"
LOG_DIR="$HOME/.agent-reports/project-review"
RUN_HOUR=9
BASE_PATH_DIRS=(/opt/homebrew/bin /usr/local/bin /usr/bin /bin /usr/sbin /sbin)

log_message() { printf 'install-project-review-schedule: %s\n' "$*" >&2; }

xml_escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

# launchd 的 PATH 極簡；專案檢查要用 npm / swift / pytest 等，所以帶入安裝當下的 PATH（只留絕對路徑、去重）
build_path_value() {
  local result="" dir
  local IFS=':'
  for dir in $PATH "${BASE_PATH_DIRS[@]}"; do
    [[ "$dir" == /* ]] || continue
    case ":$result:" in *":$dir:"*) ;; *) result="${result:+$result:}$dir" ;; esac
  done
  printf '%s' "$result"
}

print_plist() {
  local python_path="$1" path_value="$2" script log_path
  script=$(xml_escape "$REVIEW_SCRIPT"); python_path=$(xml_escape "$python_path")
  path_value=$(xml_escape "$path_value"); log_path=$(xml_escape "$LOG_DIR/launchd.log")
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python_path</string>
    <string>$script</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$RUN_HOUR</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$path_value</string>
    <key>PYTHONDONTWRITEBYTECODE</key>
    <string>1</string>
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
  local dry_run="$1" python_path path_value
  [[ -f "$REVIEW_SCRIPT" ]] || { log_message "找不到 $REVIEW_SCRIPT"; return 1; }
  python_path=$(command -v python3) || { log_message "找不到 python3"; return 1; }
  path_value=$(build_path_value)
  if [[ $dry_run -eq 1 ]]; then print_plist "$python_path" "$path_value"; return 0; fi
  # launchd 在腳本執行前就開 log 檔，目錄須先存在
  mkdir -p "$AGENTS_DIR" "$LOG_DIR" || { log_message "無法建立目錄"; return 1; }
  [[ ! -f "$PLIST_PATH" ]] || "$LAUNCHCTL" unload "$PLIST_PATH" >/dev/null 2>&1 || true
  print_plist "$python_path" "$path_value" >"$PLIST_PATH" || { log_message "寫入 $PLIST_PATH 失敗"; return 1; }
  "$LAUNCHCTL" load "$PLIST_PATH" || { log_message "launchctl load 失敗：$PLIST_PATH"; return 1; }
  echo "已安裝並載入：${PLIST_PATH}（驗證：launchctl list | grep agent-skill.project-review）"
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
