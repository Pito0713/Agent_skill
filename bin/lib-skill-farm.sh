#!/usr/bin/env bash
# lib-skill-farm.sh — 三 harness 共用的 skill link farm 核心。**唯一正本**。
#
# 被 bin/setup-*.sh 與 bin/inject-*.sh source。
# 🔴 harness 腳本內不得再出現 ln -sfn / rm 等接線動作——出現就代表核心又被複製了一份，
#    這正是 governance/lessons.md 2026-07-07「下游副本漂移」記過的錯。
#
# 兩階段契約：呼叫端必須先對所有目標跑 preflight_*，全數通過後才進 install_*。
# preflight 階段只做「檢查」與「建父目錄」（mkdir -p 冪等無破壞性），不建任何 symlink。

SKILL_NAMES=()
SKILL_TARGETS=()
SKILL_FARM_REPO=""

# load_skill_index <repository_dir>
# 填充 SKILL_NAMES / SKILL_TARGETS，並記住正本路徑供 prune 判斷使用。
load_skill_index() {
  local repository_dir="$1"
  SKILL_FARM_REPO="$repository_dir"
  SKILL_NAMES=()
  SKILL_TARGETS=()
  while IFS=$'\t' read -r skill_name skill_path; do
    SKILL_NAMES+=("$skill_name")
    SKILL_TARGETS+=("$repository_dir/$skill_path")
  done < <(python3 - "$repository_dir/skills/index.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as index_file:
    for skill in json.load(index_file)["skills"]:
        print(f"{skill['name']}\t{skill['path'].removesuffix('/SKILL.md')}")
PY
  )
  if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
    echo "⚠️  skills/index.json 未讀到任何 skill；中止以免建出空 farm。" >&2
    return 1
  fi
}

# extra entries 格式："<name>:<absolute_target>"，供 harness 掛非 skill 的正本目錄
# （例：Claude 的 rules / governance，因為 @ 語法只認 ~/.claude/skills/ 前綴）。
_farm_entry_name() { printf '%s' "${1%%:*}"; }
_farm_entry_target() { printf '%s' "${1#*:}"; }

# _check_entry <path> <expected_target>：entry 未占用或已是預期 symlink → 0
_check_entry() {
  local entry_path="$1"
  local expected_target="$2"
  [[ -e "$entry_path" || -L "$entry_path" ]] || return 0
  [[ -L "$entry_path" && "$(readlink "$entry_path")" == "$expected_target" ]]
}

# preflight_farm <farm_root> [extra_entry ...]
preflight_farm() {
  local farm_root="$1"
  shift
  local index entry
  if ! mkdir -p "$(dirname "$farm_root")" 2>/dev/null; then
    echo "⚠️  無法建立 $farm_root 的父目錄；未進行任何安裝。" >&2
    return 1
  fi
  # 舊架構的整目錄 symlink 允許遷移；實體檔案則拒絕（可能是使用者的東西）
  if [[ ! -L "$farm_root" && -e "$farm_root" && ! -d "$farm_root" ]]; then
    echo "⚠️  $farm_root 不是目錄；未進行任何安裝。" >&2
    return 1
  fi
  [[ -d "$farm_root" && ! -L "$farm_root" ]] || return 0
  for ((index = 0; index < ${#SKILL_NAMES[@]}; index++)); do
    if ! _check_entry "$farm_root/${SKILL_NAMES[$index]}" "${SKILL_TARGETS[$index]}"; then
      echo "⚠️  skill entry 衝突：$farm_root/${SKILL_NAMES[$index]}；未進行任何安裝。" >&2
      return 1
    fi
  done
  for entry in "$@"; do
    if ! _check_entry "$farm_root/$(_farm_entry_name "$entry")" "$(_farm_entry_target "$entry")"; then
      echo "⚠️  entry 衝突：$farm_root/$(_farm_entry_name "$entry")；未進行任何安裝。" >&2
      return 1
    fi
  done
}

# prune_orphan_entries <farm_root>
# 只清「指向本 repo skills/ 但已不在 index」的 entry。第三方 entry 與 extra entry
# （指向 repo/rules、repo/governance）前綴不符，一律保留。
prune_orphan_entries() {
  local farm_root="$1"
  local entry entry_target entry_name
  for entry in "$farm_root"/*; do
    [[ -L "$entry" ]] || continue
    entry_target="$(readlink "$entry")"
    [[ "$entry_target" == "$SKILL_FARM_REPO/skills/"* ]] || continue
    entry_name="$(basename "$entry")"
    if ! printf '%s\n' "${SKILL_NAMES[@]}" | grep -qxF "$entry_name"; then
      rm "$entry"
      echo "🧹 已清除孤兒 entry：$entry_name"
    fi
  done
}

# install_farm <farm_root> [extra_entry ...]
install_farm() {
  local farm_root="$1"
  shift
  local index entry
  [[ -L "$farm_root" ]] && rm "$farm_root"   # 舊架構整目錄 symlink → 換成 link farm
  mkdir -p "$farm_root"
  for ((index = 0; index < ${#SKILL_NAMES[@]}; index++)); do
    ln -sfn "${SKILL_TARGETS[$index]}" "$farm_root/${SKILL_NAMES[$index]}"
  done
  for entry in "$@"; do
    ln -sfn "$(_farm_entry_target "$entry")" "$farm_root/$(_farm_entry_name "$entry")"
  done
  prune_orphan_entries "$farm_root"
}

# preflight_file_link <target_path> <expected_source>
preflight_file_link() {
  local target_path="$1"
  if ! mkdir -p "$(dirname "$target_path")" 2>/dev/null; then
    echo "⚠️  無法建立 $target_path 的父目錄；未進行任何安裝。" >&2
    return 1
  fi
  if ! _check_entry "$target_path" "$2"; then
    echo "⚠️  $target_path 已被其他內容占用；未進行任何安裝。" >&2
    return 1
  fi
}

# install_file_link <source_path> <target_path>
install_file_link() {
  ln -sfn "$1" "$2"
  echo "✅ $2 → $1"
}

# ─── 下游入口檔的 managed block（inject-*.sh 共用）─────────────────────────
AGENT_SKILL_BEGIN_MARKER="<!-- agent-skill:begin -->"
AGENT_SKILL_END_MARKER="<!-- agent-skill:end -->"

# preflight_markers <target_file>：marker 必須成對且至多一組，否則不動該檔
preflight_markers() {
  local target_file="$1"
  local begin_count=0 end_count=0
  if ! mkdir -p "$(dirname "$target_file")" 2>/dev/null; then
    echo "⚠️  無法建立 $target_file 的父目錄；未進行任何注入。" >&2
    return 1
  fi
  if [[ -f "$target_file" ]]; then
    begin_count="$(grep -cF "$AGENT_SKILL_BEGIN_MARKER" "$target_file" || true)"
    end_count="$(grep -cF "$AGENT_SKILL_END_MARKER" "$target_file" || true)"
  fi
  if [[ "$begin_count" -ne "$end_count" || "$begin_count" -gt 1 ]]; then
    echo "⚠️  $target_file 的 Agent Skill markers 不完整；未進行任何注入。" >&2
    return 1
  fi
}

# write_managed_block <target_file> <block_body>
# 只替換自己的 managed block，marker 外的既有內容原樣保留在區塊之後。
write_managed_block() {
  local target_file="$1"
  local block_body="$2"
  local retained_content
  retained_content="$(mktemp)"
  if [[ -f "$target_file" ]]; then
    awk -v begin="$AGENT_SKILL_BEGIN_MARKER" -v end="$AGENT_SKILL_END_MARKER" '
      $0 == begin { skipping=1; next }
      $0 == end { skipping=0; after=1; next }
      skipping { next }
      after && !seen && $0 == "" { next }
      { seen=1; print }
    ' "$target_file" > "$retained_content"
  fi
  {
    printf '%s\n' "$AGENT_SKILL_BEGIN_MARKER"
    printf '%s\n' "$block_body"
    printf '%s\n' "$AGENT_SKILL_END_MARKER"
    if [[ -s "$retained_content" ]]; then
      printf '\n'
      cat "$retained_content"
    fi
  } > "$target_file"
  rm "$retained_content"
}
