#!/bin/bash
# 두 컴퓨터(윈도우 PC·맥미니)의 Claude 장기기억을 비공개 저장소 claude-memory 로 맞춘다.
# 맥미니: auto_run_mac.sh 가 매번 부른다. 수동: bash tools/sync_memory.sh
set -e
MEM="$HOME/.claude/projects/$(echo "$HOME/hanui" | sed 's/[^a-zA-Z0-9]/-/g')/memory"
REPO="$HOME/.claude-memory-sync"
mkdir -p "$MEM"
if [ ! -d "$REPO/.git" ]; then git clone -q https://github.com/ljh769-create/claude-memory "$REPO"; fi
cd "$REPO"
git pull -q --rebase --autostash || true
# 내 쪽에서 더 최근에 바뀐 파일은 저장소로, 저장소가 더 최근이면 내 쪽으로 (파일 단위, 최신 우선)
for f in "$MEM"/*.md; do [ -e "$f" ] || continue; b=$(basename "$f"); if [ ! -e "$REPO/$b" ] || [ "$f" -nt "$REPO/$b" ]; then cp -p "$f" "$REPO/$b"; fi; done
for f in "$REPO"/*.md; do b=$(basename "$f"); if [ ! -e "$MEM/$b" ] || [ "$f" -nt "$MEM/$b" ]; then cp -p "$f" "$MEM/$b"; fi; done
git add -A
git diff --cached --quiet || git commit -q -m "장기기억 동기화(맥미니) $(date '+%m/%d %H:%M')"
git push -q || true
