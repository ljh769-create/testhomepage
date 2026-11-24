#!/bin/bash
# 미니맥 자동 운영: launchd가 30분마다(실제 간격은 아래 STAMP로 30분) 실행 → Claude를 화면 없이 띄워 tools/auto_prompt.md 대로 일하고 배포한다.
# 로그: ~/Desktop/자동작업_기록.txt   잠금: tools/.auto_run.lock (55분 안에 겹쳐 실행되지 않게)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/Desktop/자동작업_기록.txt"
LOCK="$PROJ/tools/.auto_run.lock"
FLAG="$PROJ/tools/.limit_flag"
log() { echo "[$(date '+%Y-%m-%d %H:%M')] $*" >> "$LOG"; }
notify() { osascript -e "display notification \"$1\" with title \"좋은꿈 홈페이지 작업\"" 2>/dev/null; python3 "$PROJ/tools/notify.py" "$1" >/dev/null 2>&1; }

cd "$PROJ" || exit 1
python3 tools/write_status.py >/dev/null 2>&1

# 겹쳐 실행 방지 (55분 이내 잠금이 있으면 건너뜀)
if [ -f "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -55 2>/dev/null)" ]; then
  log "이전 자동 작업이 아직 진행 중이라 건너뜀"; exit 0
fi
# 원장님 지시(2026-11-24): 사용량 절약을 위해 30분 간격. launchd가 30분마다(실제 간격은 아래 STAMP로 30분) 불러도 마지막 시작 뒤 28분이 안 됐으면 건너뜀.
STAMP="$PROJ/tools/.last_run"
# 한도에 걸려 멈춘 상태(.limit_flag)면 30분 간격을 무시하고 launchd가 부를 때마다(15분) 바로 다시 시도 → 한도가 풀리면 곧바로 이어서 작업
if [ ! -f "$FLAG" ] && [ -f "$STAMP" ] && [ -n "$(find "$STAMP" -mmin -28 2>/dev/null)" ]; then exit 0; fi
date > "$STAMP"
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
  if [ ! -f "$FLAG" ]; then date > "$FLAG"; notify "사용 한도에 걸려 잠시 멈춤. 풀리면 15분 안에 자동으로 이어서 합니다."; fi
elif [ -f "$FLAG" ]; then
  rm -f "$FLAG"; notify "한도가 풀려 작업을 다시 시작했습니다."
fi

# 실행 뒤 안전 점검: 차단 항목이 남아 있으면 폰 알림
if ! python3 tools/ad_check.py --quiet >/tmp/ad_check_last.txt 2>&1; then
  notify "의료광고 검수 차단 항목이 있습니다. 미니맥 확인 필요: $(head -c 300 /tmp/ad_check_last.txt | tr -s '
' ' ')"
fi
# Claude 가 아예 못 돌았으면 알림 (로그인 만료 등)
if echo "$OUT" | grep -qiE 'not logged in|please run /login|invalid api key|authentication'; then
  notify "Claude 로그인이 풀렸습니다. 미니맥에서 claude 를 열어 다시 로그인해 주세요."
fi
# 하루 한 번 생존 신호 (오전 9시 이후 첫 실행)
HB="$PROJ/tools/.heartbeat_date"
if [ "$(date +%H)" -ge 9 ] && [ "$(cat "$HB" 2>/dev/null)" != "$(date +%F)" ]; then
  date +%F > "$HB"; notify "미니맥 자동 운영 정상 작동 중 ($(date '+%m-%d %H:%M'))"
fi
