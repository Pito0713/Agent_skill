#!/usr/bin/env bash
# scan-downstream.sh — 唯讀掃描下游 Claude/Codex skill farm 的 dangling symlink。
#
# 用法：bash bin/scan-downstream.sh [專案目錄 ...]
# 未提供參數時掃描下方已知專案；不存在的目錄會提示並略過。

set -euo pipefail

KNOWN_DOWNSTREAMS=(
  "$HOME/WakaWaka"
  "$HOME/AG_knowledge"
  "$HOME/gps_position"
  "$HOME/quant_platform"
  "$HOME/shopee"
  "$HOME/Stock_model"
  "$HOME/tabetemiru"
)

if [[ $# -gt 0 ]]; then
  PROJECTS=("$@")
else
  PROJECTS=("${KNOWN_DOWNSTREAMS[@]}")
fi

dangling_count=0

scan_farm() {
  local project_dir="$1"
  local harness="$2"
  local farm_root="$project_dir/.$harness/skills"
  local entry target project_name

  [[ -d "$farm_root" ]] || return 0
  project_name="$(basename "$project_dir")"
  for entry in "$farm_root"/*; do
    [[ -L "$entry" && ! -e "$entry" ]] || continue
    target="$(readlink "$entry")"
    printf '%s:%s:%s -> %s\n' "$project_name" "$harness" "$(basename "$entry")" "$target"
    dangling_count=$((dangling_count + 1))
  done
}

for project_dir in "${PROJECTS[@]}"; do
  if [[ ! -d "$project_dir" ]]; then
    echo "⚠️  略過不存在的下游目錄：$project_dir" >&2
    continue
  fi
  scan_farm "$project_dir" claude
  scan_farm "$project_dir" codex
done

if [[ "$dangling_count" -eq 0 ]]; then
  echo "✅ 無 dangling"
fi
