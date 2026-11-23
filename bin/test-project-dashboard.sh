#!/usr/bin/env bash
# test-project-dashboard.sh — bin/project-dashboard.py 的測試。sessions 目錄與 repo 全在 mktemp -d。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/project-dashboard.py"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@users.noreply.github.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@users.noreply.github.com
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2}）"; }

SESSIONS="$SANDBOX/sessions"

# new_repo <名稱> <交接後 commit 數>：交接前 1 個、交接後 N 個 commit（用 committer date 控制）
new_repo() {
  local repo="$SANDBOX/repos/$1" i
  git init -q -b main "$repo" || exit 2
  GIT_COMMITTER_DATE="2026-11-01T09:00:00" GIT_AUTHOR_DATE="2026-11-01T09:00:00" \
    git -C "$repo" commit -q --allow-empty -m before || exit 2
  for ((i = 1; i <= $2; i++)); do
    GIT_COMMITTER_DATE="2026-11-10T09:0${i}:00" GIT_AUTHOR_DATE="2026-11-10T09:0${i}:00" \
      git -C "$repo" commit -q --allow-empty -m "after $i" || exit 2
  done
}

# write_latest <名稱> <路徑> <狀態行> <當前焦點> <卡住的點>
write_latest() {
  mkdir -p "$SESSIONS/$1"
  printf '# %s\n\n> 路徑：%s\n> 最後更新：2026-11-05 10:00\n> 寫入者：claude\n> 觸發來源：handoff\n> 狀態：%s\n\n## 當前焦點\n\n%s\n\n## 進行中\n\n- [ ] x\n\n## 卡住的點\n\n%s\n\n## 本輪決策\n\n- y\n' \
    "$1" "$2" "$3" "$4" "$5" >"$SESSIONS/$1/latest.md"
}

new_repo synced 0
new_repo behind 6
echo dirty >"$SANDBOX/repos/synced/untracked.txt"
write_latest synced "$SANDBOX/repos/synced" "🟢 順暢" "同步的專案" "無"
write_latest behind "$SANDBOX/repos/behind" "🟡 進行中" "落後很多的專案" "無（等使用者提供資料）"
write_latest gone "$SANDBOX/repos/does-not-exist" "⚫ 暫停" "已搬走" "無"
write_latest blocked "$SANDBOX/repos/synced" "🔴 卡住" "焦點含 | 直線的超長描述文字會被截斷到三十個字以內喔喔喔喔喔" "- 等 API 金鑰"
mkdir -p "$SESSIONS/oldformat"
printf '# oldformat\n\n> 狀態：🟢 順暢\n' >"$SESSIONS/oldformat/latest.md"

OUT=$(python3 "$TOOL" --sessions-dir "$SESSIONS" --today 2026-11-23); RC=$?
row() { grep "^| $1 |" <<<"$OUT"; }
cell() { row "$1" | awk -F ' [|] ' -v n="$2" '{print $n}'; }

echo "[整體]"
check "有紀錄 → exit 0" "$RC" 0
check "每個專案一列（含舊格式）" "$(grep -c '^| [a-z]' <<<"$OUT")" 5
grep -q "## 跨專案狀態（2026-11-23）" <<<"$OUT" && pass "標題帶日期" || fail "標題帶日期"

echo "[git 欄位現算]"
check "同步：落後 0" "$(cell synced 4)" 0
check "同步：未 commit 1（untracked 也算）" "$(cell synced 6)" 1
check "同步：分支現跑 git" "$(cell synced 5)" main
check "落後 6 → 加 ⚠️" "$(cell behind 4)" "6 ⚠️"
check "路徑不存在 → STALE" "$(cell gone 4)" STALE
check "STALE 的分支顯示 —" "$(cell gone 5)" "—"

echo "[交接欄位]"
check "狀態只取 emoji" "$(cell behind 2)" "🟡"
check "「無（備註）」不算 Blocker" "$(cell behind 8 | tr -d ' |')" "—"
check "有內容的卡住點 → 有" "$(cell blocked 8 | tr -d ' |')" "有"
row blocked | grep -qF '焦點含 \| 直線' && pass "欄位內的 | 被跳脫，不破壞表格" || fail "欄位內的 | 被跳脫，不破壞表格"
row blocked | grep -q '…' && pass "超長焦點被截斷" || fail "超長焦點被截斷"
check "舊格式缺欄位 → 顯示 — 不中斷" "$(cell oldformat 3)" "—"

echo "[需要展開]"
check "🔴、有 Blocker、落後 >5 的都列出" "$(tail -n 1 <<<"$OUT")" "需要展開：behind、blocked"

echo "[審查補案例]"
S2="$SANDBOX/sessions2"
# write2 <名稱> <latest.md 全文>
write2() { mkdir -p "$S2/$1"; printf '%s\n' "$2" >"$S2/$1/latest.md"; }
commit_at() { GIT_COMMITTER_DATE="$2" GIT_AUTHOR_DATE="$2" git -C "$1" commit -q --allow-empty -m "$2" || exit 2; }

dateonly="$SANDBOX/repos/dateonly"; git init -q -b main "$dateonly"
commit_at "$dateonly" "2026-11-04T23:00:00"; commit_at "$dateonly" "2026-11-05T00:30:00"; commit_at "$dateonly" "2026-11-05T23:00:00"
write2 dateonly "$(printf '# d\n\n> 路徑：%s\n> 最後更新：2026-11-05\n> 狀態：🟢 順暢\n' "$dateonly")"

multi="$SANDBOX/repos/multi"; git init -q -b main "$multi"
commit_at "$multi" "2026-11-01T09:00:00"; git -C "$multi" checkout -q -b feature
commit_at "$multi" "2026-11-10T09:00:00"; commit_at "$multi" "2026-11-10T10:00:00"; git -C "$multi" checkout -q main
write2 multi "$(printf '# m\n\n> 路徑：`%s`\n> 最後更新：2026-11-05 10:00\n> 狀態：🟢 順暢\n' "$multi")"

skew="$SANDBOX/repos/skew"; git init -q -b main "$skew"
commit_at "$skew" "2026-11-01T09:00:00"; commit_at "$skew" "2026-11-10T09:00:00"; commit_at "$skew" "2026-11-11T09:00:00"
commit_at "$skew" "2026-10-01T09:00:00"; commit_at "$skew" "2026-11-12T09:00:00"   # 時鐘倒退的 commit 夾在中間
write2 skew "$(printf '# s\n\n> 路徑：%s\n> 最後更新：2026-11-05 10:00\n> 狀態：🟢 順暢\n' "$skew")"

write2 emptyfields "$(printf '# e\n\n> 路徑：\n> 最後更新：2026-11-05 10:00\n> 狀態：\n\n## 當前焦點\n\nx\n')"
write2 badtime "$(printf '# b\n\n> 路徑：%s\n> 最後更新：未知\n> 狀態：🟢 順暢\n' "$dateonly")"
write2 realblock "$(printf '# r\n\n> 路徑：%s\n> 最後更新：2026-11-05 10:00\n> 狀態：🟢 順暢\n\n## 卡住的點\n\n無法連線到 staging DB，等 VPN\n' "$dateonly")"
mkdir -p "$S2/broken/latest.md"   # latest.md 是目錄 → 讀取失敗

pwned="$SANDBOX/repos/evil"; git init -q -b main "$pwned"; commit_at "$pwned" "2026-11-01T09:00:00"
git -C "$pwned" config core.fsmonitor "touch $SANDBOX/PWNED"
write2 evil "$(printf '# v\n\n> 路徑：%s\n> 最後更新：2026-11-05 10:00\n> 狀態：🟢 順暢\n' "$pwned")"

OUT=$(python3 "$TOOL" --sessions-dir "$S2" --today 2026-11-23 2>"$SANDBOX/err2"); RC=$?
check "只有日期的最後更新 = 當天 00:00（跟執行時間無關）" "$(cell dateonly 4)" 2
check "落後數算所有本機分支（不只目前所在分支）" "$(cell multi 4)" 2
check "反引號包住的路徑照樣解析（不誤判 STALE）" "$(cell multi 5)" main
check "時鐘倒退的 commit 不會讓計數提早停止" "$(cell skew 4)" 3
check "路徑欄留空 → STALE，不吃到下一行" "$(cell emptyfields 4)" STALE
check "狀態欄留空 → 顯示 —，不吃到下一行" "$(cell emptyfields 2)" "—"
check "最後更新解析不了 → 落後顯示 ?" "$(cell badtime 4)" "?"
check "「無法連線…」是真的 Blocker" "$(cell realblock 8 | tr -d ' |')" "有"
check "單一 latest.md 壞掉 → 整體仍 exit 0" "$RC" 0
check "壞掉的那列標成讀取失敗、其他列照常" "$(row broken | grep -c '讀取失敗'):$(grep -c '^| [a-z]' <<<"$OUT")" "1:8"
[[ ! -e "$SANDBOX/PWNED" ]] && pass "路徑指向的 repo 設了 fsmonitor 也不會被執行" || fail "路徑指向的 repo 設了 fsmonitor 也不會被執行"
# realblock 只有 Blocker（狀態 🟢、落後 2）：名單有它才證明 Blocker 這條判斷真的在作用
check "只有 Blocker 的專案也列入需要展開" "$(tail -n 1 <<<"$OUT" | grep -c 'realblock')" 1

echo "[codex 審查補案例]"
S3="$SANDBOX/sessions3"
write3() { mkdir -p "$S3/$1"; printf '%s\n' "$2" >"$S3/$1/latest.md"; }
write3 baddate "$(printf '# b\n\n> 路徑：%s\n> 最後更新：2026-02-30 10:00\n> 狀態：🔴 卡住\n\n## 卡住的點\n\n等 API\n' "$dateonly")"
OUT=$(python3 "$TOOL" --sessions-dir "$S3" --today 2026-11-23 2>&1); RC=$?
check "不存在的日期 → 落後 ?，其餘欄位照常（不變成讀取失敗）" "$(cell baddate 4):$(cell baddate 2):$(cell baddate 8 | tr -d ' |')" "?:🔴:有"
check "不存在的日期的專案仍列入需要展開" "$(tail -n 1 <<<"$OUT")" "需要展開：baddate"

write3 baddate "$(printf '# b\n\n> 路徑：%s\n> 最後更新：2026-11-05 10:00\n> 狀態：🟢 順暢\n' "$dateonly")"
OUT=$(GIT_DIR="$multi/.git" python3 "$TOOL" --sessions-dir "$S3" --today 2026-11-23 2>&1)
check "外部帶 GIT_DIR 也讀各自的 repo（分支 / 落後不被蓋掉）" "$(cell baddate 5):$(cell baddate 4)" "main:1"

NOGIT="$SANDBOX/nogit-bin"; mkdir -p "$NOGIT"; ln -s "$(command -v python3)" "$NOGIT/python3"
OUT=$(PATH="$NOGIT" "$NOGIT/python3" "$TOOL" --sessions-dir "$S3" 2>&1); RC=$?
check "找不到 git → exit 2 並明講（不是 traceback）" "$RC:$(grep -c '找不到 git' <<<"$OUT"):$(grep -c Traceback <<<"$OUT")" "2:1:0"

echo "[沒有紀錄]"
OUT=$(python3 "$TOOL" --sessions-dir "$SANDBOX/empty" 2>&1); RC=$?
check "沒有任何 latest.md → exit 1 並明講" "$RC:$(grep -c '尚無專案紀錄' <<<"$OUT")" "1:1"

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
