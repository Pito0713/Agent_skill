#!/usr/bin/env bash
# pre-push-email-audit.sh — push 前擋下 author / committer 為個人信箱的 commit（正本；下游以 exec wrapper 指向本檔）
#
# 來源：governance/lessons.md 2026-11-20「push 到公開 repo 前沒檢查 commit author email」；
#       工單 plans/sink-candidates-t2.md W6。
#
# 為什麼直接攔截（不像 T5 只警告）：一旦 push 到 public，清除只能改寫歷史 + force push，
# 事後警告沒有意義。為什麼在 pre-push 而不是 pre-commit：信箱只有離開本機才會洩漏。
#
# 範圍：只看這次要 push 的 commit；`git config audit.pushEmailBaseline <sha>` 設定的
# 基準點（含）之前的 commit 一律不查——歷史已公開，改寫也收不回快取（使用者 2026-11-23 裁決）。
# 允許：*@users.noreply.github.com、noreply@anthropic.com。
# 旁路：git push --no-verify。
# 失敗策略：偵測到個人信箱 → 擋（fail-closed）；git 指令失敗等內部錯誤 → 放行並警告（fail-open）。

set -u

RED=$'\033[0;31m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
ALLOWED_EMAIL_PATTERN='(@users\.noreply\.github\.com|^noreply@anthropic\.com)$'
REMOTE_NAME="${1:-origin}"
# replace ref 會讓 hook 看到替換後的物件，但 push 送出的是原始物件 → 一律看原始物件
export GIT_NO_REPLACE_OBJECTS=1

warn() { echo "${YELLOW}⚠ pre-push email 檢查：$1${NC}" >&2; }

# 基準點只接受 commit sha：HEAD、main 這類會移動的 ref 會讓之後所有 commit 永遠被豁免。
# 不合法時不能靜默忽略——明講「本次不排除」，讓使用者知道設定沒生效
baseline_exclusion() {
  local baseline
  baseline=$(git config --get audit.pushEmailBaseline 2>/dev/null) || return 0
  if [[ ! "$baseline" =~ ^[0-9a-fA-F]{7,64}$ ]]; then
    warn "audit.pushEmailBaseline=${baseline} 不是 commit sha（不接受會移動的 ref），本次不排除任何歷史"
  elif git rev-parse -q --verify "${baseline}^{commit}" >/dev/null 2>&1; then
    echo "^${baseline}"
  else
    warn "audit.pushEmailBaseline=${baseline} 找不到這個 commit，本次不排除任何歷史"
  fi
}

# 印出「這個 remote 上已經有、不必再查」的 rev-list 參數，一行一個。
# 只排除**本 remote** 的 tracking ref：從私人 remote 推到公開 remote 時，私人那邊有的 commit 並未公開。
# 用 URL 直接 push（沒有對應的 remote 名稱）→ 只排除 remote_sha，寧可多查
push_range() {
  local remote_sha="$1"
  if [[ ! "$remote_sha" =~ ^0+$ ]] && git cat-file -e "${remote_sha}^{commit}" 2>/dev/null; then
    echo "^${remote_sha}"
  fi
  if git remote 2>/dev/null | grep -qxF -- "$REMOTE_NAME"; then
    echo "--not"; echo "--remotes=${REMOTE_NAME}"
  fi
}

# stdin：「短 sha<TAB>角色<TAB>信箱」；只印不在允許清單內的（比對前轉小寫，git 不會正規化大小寫）
filter_personal() {
  # pattern 用 ENVIRON 傳：awk -v 會處理反斜線跳脫，\. 會變成任意字元
  ALLOWED="$ALLOWED_EMAIL_PATTERN" awk -F '\t' '
    BEGIN { allowed = ENVIRON["ALLOWED"] }
    NF < 3 { next }
    tolower($3) !~ allowed { printf "  %s\t%s\t%s\n", $1, $2, $3 }
  '
}

# 印出這次 push 一個 ref 會送出的個人信箱
find_personal_emails() {
  local exclusion="$1" local_sha="$2" remote_sha="$3" range=("$2") line commits
  # 基準點排除必須放在 push_range 之前：--not 會反轉它後面所有參數，^sha 放後面會變成「包含」
  [[ -n "$exclusion" ]] && range+=("$exclusion")
  while IFS= read -r line; do range+=("$line"); done < <(push_range "$remote_sha")
  commits=$(git log --format='%h%x09author%x09%ae%n%h%x09committer%x09%ce' "${range[@]}" 2>/dev/null) \
    || { warn "git log 失敗，略過 ${local_sha:0:7}"; return 0; }
  printf '%s\n' "$commits" | filter_personal
}

# annotated tag 的 tagger 信箱跟著 tag 物件一起送出，git log 看不到
find_personal_tagger() {
  local tag_sha="$1" tagger
  [[ "$(git cat-file -t "$tag_sha" 2>/dev/null)" == tag ]] || return 0
  tagger=$(git cat-file -p "$tag_sha" 2>/dev/null | sed -n 's/^tagger .*<\(.*\)>.*/\1/p' | head -n 1)
  [[ -n "$tagger" ]] || return 0
  printf '%s\ttagger\t%s\n' "${tag_sha:0:7}" "$tagger" | filter_personal
}

exclusion=$(baseline_exclusion)
offenders=""
while read -r local_ref local_sha remote_ref remote_sha; do
  [[ -n "${local_sha:-}" ]] || continue
  [[ "$local_sha" =~ ^0+$ ]] && continue   # 刪除遠端分支，沒有 commit 要送出
  offenders+=$(find_personal_emails "$exclusion" "$local_sha" "$remote_sha")$'\n'
  offenders+=$(find_personal_tagger "$local_sha")$'\n'
done

offenders=$(printf '%s' "$offenders" | grep -v '^$' | sort -u)
[[ -z "$offenders" ]] && exit 0

echo "" >&2
echo "${RED}✖ pre-push 擋下：要送出的 commit 含個人信箱${NC}" >&2
echo "${YELLOW}  push 到公開 repo 後只能改寫歷史 + force push 才能清除。${NC}" >&2
echo "" >&2
printf '%s\n' "$offenders" >&2
echo "" >&2
echo "  修法：git config user.email <ID>+<帳號>@users.noreply.github.com，再 git commit --amend --reset-author（多個 commit 用 rebase）" >&2
echo "  既有歷史已公開、不打算改寫：git config audit.pushEmailBaseline <要豁免的最後一個 commit 的 sha>（不接受 HEAD 等會移動的 ref）" >&2
echo "  旁路：git push --no-verify" >&2
echo "" >&2
exit 1
