#!/usr/bin/env bash
# vault-env.sh — 讀 Obsidian vault 設定，stdout 印 vault 絕對路徑（計劃書 plans/t6-bash-extraction.md C1）
#
# 用法：vault-env.sh [--optional]
#   預設（必須有）：.env 不存在 / 未填 / 目錄不存在 → exit 1，stderr 印設定步驟
#   --optional     ：缺設定一律無輸出、exit 0（呼叫端靜默降級）
#
# 為什麼不 source .env：source 會執行檔案裡任何指令；這裡只需要一個變數，所以只解析
# `OBSIDIAN_VAULT_PATH=` 那一行（去掉成對引號、展開開頭的 ~）。
# 原本 obsidian-save / knowledge-search / mentor-protocol / cooking-flow 各寫一份，已經分歧。
#
# 環境變數：AGENT_SKILL_ENV_FILE  取代 ~/Agent_skill/.env（測試用）
#           OBSIDIAN_VAULT_PATH   .env 沒有定義時沿用（與舊版 source .env 的語意一致）

set -u

ENV_FILE="${AGENT_SKILL_ENV_FILE:-$HOME/Agent_skill/.env}"
is_optional=false
case "${1:-}" in
  --optional) is_optional=true ;;
  '') ;;
  *) echo "vault-env: 未知參數 $1（用法：vault-env.sh [--optional]）" >&2; exit 2 ;;
esac

# 缺設定：--optional 靜默結束；否則印原因與設定步驟
missing() {
  $is_optional && exit 0
  echo "❌ $1" >&2
  echo "" >&2
  echo "設定步驟：" >&2
  echo "  1. cp ~/Agent_skill/.env.example ~/Agent_skill/.env（已存在就略過）" >&2
  echo "  2. 填入 OBSIDIAN_VAULT_PATH=<vault 的完整路徑>" >&2
  echo "     （Obsidian 左下角 vault 名稱右鍵 → 在 Finder 中顯示）" >&2
  echo "  3. 儲存後重新執行" >&2
  exit 1
}

# 解析一個 dotenv 值，語意對齊 bash 的 source（只支援 dotenv 常見寫法；if/readonly 等不支援）：
#   'x'：完全字面   "x"：只展開 $HOME / ${HOME}   無引號：\ 跳脫、遇到沒跳脫的空白就結束（之後是註解）、
#   展開 $HOME / ${HOME} 與開頭的 ~。引號後面接的東西（空白、# 註解）一律忽略
parse_value() {
  local raw="$1" value="" char index=0 length
  case "$raw" in
    \'*) value="${raw#\'}"; printf '%s' "${value%%\'*}"; return ;;
    \"*) value="${raw#\"}"; value="${value%%\"*}"; expand_home "$value"; return ;;
  esac
  length=${#raw}
  while [[ $index -lt $length ]]; do
    char="${raw:$index:1}"
    if [[ "$char" == '\' ]]; then index=$((index + 1)); value+="${raw:$index:1}"
    elif [[ "$char" == ' ' || "$char" == $'\t' ]]; then break
    else value+="$char"; fi
    index=$((index + 1))
  done
  case "$value" in "~") value="$HOME" ;; "~/"*) value="$HOME/${value#\~/}" ;; esac
  expand_home "$value"
}

expand_home() {
  local value="$1"
  value="${value//\$\{HOME\}/$HOME}"
  printf '%s' "${value//\$HOME/$HOME}"
}

# .env 裡有定義 → 用 .env 的（同 source 的覆蓋語意，取最後一個）；沒定義 → 保留環境變數原值
resolve_raw_path() {
  local line
  if [[ -f "$ENV_FILE" ]]; then
    line=$(sed -n -E 's/^[[:space:]]*(export[[:space:]]+)?OBSIDIAN_VAULT_PATH=//p' "$ENV_FILE" 2>/dev/null | tail -n 1)
    if grep -qE '^[[:space:]]*(export[[:space:]]+)?OBSIDIAN_VAULT_PATH=' "$ENV_FILE" 2>/dev/null; then
      parse_value "${line%$'\r'}"
      return
    fi
  fi
  printf '%s' "${OBSIDIAN_VAULT_PATH:-}"
}

if [[ ! -f "$ENV_FILE" && -z "${OBSIDIAN_VAULT_PATH:-}" ]]; then
  missing "找不到 ${ENV_FILE}（環境變數 OBSIDIAN_VAULT_PATH 也未設定）"
fi
# 權限檢查要在主程式做：resolve_raw_path 跑在 $(...) 子 shell，裡面的 exit 帶不回來
[[ ! -f "$ENV_FILE" || -r "$ENV_FILE" ]] || missing "${ENV_FILE} 無法讀取（檢查檔案權限）"
raw=$(resolve_raw_path)
[[ -n "$raw" ]] || missing "${ENV_FILE} 的 OBSIDIAN_VAULT_PATH 尚未填入"
[[ -d "$raw" ]] || missing "找不到 vault 目錄：${raw}"

# CDPATH 清空、加 --：值是相對路徑或以 - 開頭時，cd 不會跑到別的目錄
(CDPATH='' cd -- "$raw" && pwd)
