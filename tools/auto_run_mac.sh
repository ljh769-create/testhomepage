#!/bin/bash
# 미니맥 자동 운영: launchd가 15분마다 실행 → Claude를 화면 없이 띄워 tools/auto_prompt.md 대로 일하고 배포한다.
# 로그: ~/Desktop/자동작업_기록.txt   잠금: tools/.auto_run.lock (55분 안에 겹쳐 실행되지 않게)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/Desktop/자동작업_기록.txt"
LOCK="$PROJ/tools/.auto_run.lock"
FLAG="$PROJ/tools/.limit_flag"
log() { echo "[$(date '+%Y-%m-%d %H:%M')] $*" >> "$LOG"; }
notify() { osascript -e "display notification \"$1\" with title \"좋은꿈 홈페이지 작업\"" 2>/dev/null; }

cd "$PROJ" || exit 1
python3 tools/write_status.py >/dev/null 2>&1

# 겹쳐 실행 방지 (55분 이내 잠금이 있으면 건너뜀)
if [ -f "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -55 2>/dev/null)" ]; then
  log "이전 자동 작업이 아직 진행 중이라 건너뜀"; exit 0
fi
date > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

command -v claude >/dev/null || { log "Claude 실행 파일을 찾지 못함"; exit 1; }

# 처음 한 번: 자동 실행에 필요한 권한 파일 만들기 (gitignore 라 저장소에 없음)
if [ ! -f .claude/settings.local.json ]; then
  mkdir -p .claude
  cat > .claude/settings.local.json <<'EOF'
{"permissions":{"allow":["Bash","Edit","Write","Read","Glob","Grep","WebFetch","WebSearch","Skill","Agent","ToolSearch","NotebookEdit"]}}
EOF
fi

PROMPT='Read tools/auto_prompt.md (UTF-8, Korean) in this project and carry out every step in it exactly. Reply in Korean. You are running on macOS (the Mac mini server): use python3 instead of python, use ~/Desktop for the Desktop folder, and replace every "msg *" popup with: osascript -e '"'"'display notification "<message>" with title "좋은꿈 홈페이지"'"'"'.'

git pull --rebase --autostash >/dev/null 2>&1
log "자동 작업 시작"
OUT="$(claude -p "$PROMPT" --model opus 2>&1)"
LAST="$(echo "$OUT" | grep -v '^[[:space:]]*$' | tail -3 | tr '\n' ' ')"
log "끝: $LAST"

if echo "$OUT" | grep -qiE 'limit|한도|429'; then
  if [ ! -f "$FLAG" ]; then date > "$FLAG"; notify "사용 한도에 걸려 잠시 멈춤. 풀리면 15분 안에 자동 재시작합니다."; fi
elif [ -f "$FLAG" ]; then
  rm -f "$FLAG"; notify "한도가 풀려 작업을 다시 시작했습니다."
fi
