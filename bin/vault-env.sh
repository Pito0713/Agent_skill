#!/usr/bin/env bash
# vault-env.sh — 讀 Obsidian vault 設定，stdout 印 vault 絕對路徑（計劃書 plans/t6-bash-extraction.md C1）
#
# 用法：vault-env.sh [--optional]
#   預設（必須有）：.env 不存在 / 未填 / 目錄不存在 → exit 1，stderr 印設定步驟
#   --optional     ：缺設定一律無輸出、exit 0（呼叫端靜默降級）
#
# 為什麼不 source .env：source 會執行檔案裡任何指令；這裡只需要一個變數，所以只解析
# `OBSIDIAN_VAULT_PATH=` 那一行（規則見 parse_value；不支援的寫法直接拒絕）。
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

# 解析一個 dotenv 值。支援範圍內與 bash 的 source 結果一致；範圍外一律回 3（呼叫端報「格式不支援」），
# 不猜——猜錯會回傳另一個存在的目錄，obsidian-save 就寫到錯的地方（C1 codex 審查）。
#   'x'  ：完全字面
#   "x"  ：\ 只跳脫 $ ` " \ ；展開 $HOME / ${HOME}
#   無引號：\ 跳脫任一字元；開頭的 ~ 與 $HOME / ${HOME} 展開；遇到空白結束
#   值結束後只能是空白或 # 註解。不支援（回 3）：其他變數、$(...)、反引號、引號接字串（"/a"/b）、
#   無引號值空白後還有東西（source 會把它當指令執行，不會設定變數）
parse_value() {
  local raw="$1" value="" char index=0 length=${#1}
  case "$raw" in
    \'*)
      raw="${raw#\'}"
      [[ "$raw" == *\'* ]] || return 3
      value="${raw%%\'*}"
      rest_is_comment "${raw#*\'}" || return 3
      printf '%s' "$value"; return 0 ;;
    \"*)
      index=1
      while :; do
        [[ $index -lt $length ]] || return 3            # 沒有收尾的 "
        char="${raw:$index:1}"
        case "$char" in
          '"') break ;;
          '\')
            case "${raw:$((index + 1)):1}" in
              '$'|'`'|'"'|'\') value+="${raw:$((index + 1)):1}"; index=$((index + 2)); continue ;;
              *) value+='\' ;;
            esac ;;
          '$') expand_dollar "$raw" "$index" || return 3; value+="$HOME"; index=$((index + DOLLAR_WIDTH)); continue ;;
          '`') return 3 ;;
          *) value+="$char" ;;
        esac
        index=$((index + 1))
      done
      rest_is_comment "${raw:$((index + 1))}" || return 3
      printf '%s' "$value"; return 0 ;;
  esac
  if [[ "${raw:0:1}" == '~' && ( $length -eq 1 || "${raw:1:1}" == / ) ]]; then value="$HOME"; index=1; fi
  while [[ $index -lt $length ]]; do
    char="${raw:$index:1}"
    case "$char" in
      '\') value+="${raw:$((index + 1)):1}"; index=$((index + 2)); continue ;;
      ' '|$'\t') rest_is_comment "${raw:$index}" || return 3; break ;;
      '$') expand_dollar "$raw" "$index" || return 3; value+="$HOME"; index=$((index + DOLLAR_WIDTH)); continue ;;
      '"'|"'"|'`') return 3 ;;
      *) value+="$char" ;;
    esac
    index=$((index + 1))
  done
  printf '%s' "$value"
}

# raw 在 index 處的 $ 是 ${HOME} 或 $HOME（後面不能再接變數名字元，$HOME_X 是另一個變數）→ DOLLAR_WIDTH 設為長度
expand_dollar() {
  local tail="${1:$2}"
  if [[ "${tail:0:7}" == '${HOME}' ]]; then DOLLAR_WIDTH=7; return 0; fi
  if [[ "${tail:0:5}" == '$HOME' && ! "${tail:5:1}" =~ [A-Za-z0-9_] ]]; then DOLLAR_WIDTH=5; return 0; fi
  return 1
}

# 值結束後剩下的部分：只能是空白，或空白後接 # 註解
rest_is_comment() {
  local rest="$1"
  [[ -z "$rest" ]] && return 0
  [[ "$rest" == [[:space:]]* ]] || return 1
  rest="${rest#"${rest%%[![:space:]]*}"}"
  [[ -z "$rest" || "$rest" == \#* ]]
}

# .env 裡有定義 → 用 .env 的（同 source 的覆蓋語意，取最後一個）；沒定義 → 保留環境變數原值
resolve_raw_path() {
  local line
  if [[ -f "$ENV_FILE" ]]; then
    line=$(sed -n -E 's/^[[:space:]]*(export[[:space:]]+)?OBSIDIAN_VAULT_PATH=//p' "$ENV_FILE" 2>/dev/null | tail -n 1)
    if grep -qE '^[[:space:]]*(export[[:space:]]+)?OBSIDIAN_VAULT_PATH=' "$ENV_FILE" 2>/dev/null; then
      parse_value "${line%$'\r'}"
      return    # 帶回 parse_value 的 exit code（3 = 格式不支援）
    fi
  fi
  printf '%s' "${OBSIDIAN_VAULT_PATH:-}"
}

if [[ ! -f "$ENV_FILE" && -z "${OBSIDIAN_VAULT_PATH:-}" ]]; then
  missing "找不到 ${ENV_FILE}（環境變數 OBSIDIAN_VAULT_PATH 也未設定）"
fi
# 權限檢查要在主程式做：resolve_raw_path 跑在 $(...) 子 shell，裡面的 exit 帶不回來
[[ ! -f "$ENV_FILE" || -r "$ENV_FILE" ]] || missing "${ENV_FILE} 無法讀取（檢查檔案權限）"
raw=$(resolve_raw_path) || missing "${ENV_FILE} 的 OBSIDIAN_VAULT_PATH 格式不支援（不猜，以免選到錯的目錄）——改用單引號包住完整路徑：OBSIDIAN_VAULT_PATH='/path/to/vault'"
[[ -n "$raw" ]] || missing "${ENV_FILE} 的 OBSIDIAN_VAULT_PATH 尚未填入"
[[ -d "$raw" ]] || missing "找不到 vault 目錄：${raw}"

# CDPATH 清空、加 --：值是相對路徑或以 - 開頭時，cd 不會跑到別的目錄
(CDPATH='' cd -- "$raw" && pwd)
