#!/bin/bash
# 미니맥 자동 운영: launchd가 15분마다 부르고, 한 번에 약 45분씩 쉬지 않고 일함 → Claude를 화면 없이 띄워 tools/auto_prompt.md 대로 일하고 배포한다.
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
# 한도에 걸려 쉬는 중이면 Claude 없이 예약 글만 시간 맞춰 공개
[ -f "$FLAG" ] && [ ! -f "$LOCK" ] && bash "$PROJ/tools/publish_tick.sh"
if [ -f "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -55 2>/dev/null)" ]; then
  log "이전 자동 작업이 아직 진행 중이라 건너뜀"; exit 0
fi
# 속도 조절(원장님 지시 2026-11-25): 5시간 한도 리셋 시각에 맞춰 고르게 다 쓰기. 쉬는 시간이면 Claude 를 띄우지 않고 끝냄.
if ! PACE_MSG="$(python3 tools/pace.py gate)"; then
  [ ! -f "$LOCK" ] && [ -f "$PROJ/tools/publish_tick.sh" ] && bash "$PROJ/tools/publish_tick.sh"   # 쉬는 동안에도 예약 글은 시간 맞춰 공개
  [ "$(date +%M)" -lt 15 ] && log "$PACE_MSG"   # 기록이 너무 많아지지 않게 한 시간에 한 번만
  exit 0
fi
STAMP="$PROJ/tools/.last_run"
# 원장님 지시(2026-11-25): "100% 쓸 때까지 작업을 찾아서" → 간격 제한 없음. 잠금만으로 겹침 방지, 끝나면 15분 안에 다음 실행.
date > "$STAMP"
date > "$LOCK"
# 작업이 길어져도(서브에이전트 등) 잠금이 오래된 것으로 보이지 않게 5분마다 갱신
( while sleep 300; do [ -f "$LOCK" ] && date > "$LOCK"; done ) &
TOUCHER=$!
trap 'kill $TOUCHER 2>/dev/null; rm -f "$LOCK"' EXIT

command -v claude >/dev/null || { log "Claude 실행 파일을 찾지 못함"; exit 1; }

# 처음 한 번: 자동 실행에 필요한 권한 파일 만들기 (gitignore 라 저장소에 없음)
if [ ! -f .claude/settings.local.json ]; then
  mkdir -p .claude
  cat > .claude/settings.local.json <<'EOF'
{"permissions":{"allow":["Bash","Edit","Write","Read","Glob","Grep","WebFetch","WebSearch","Skill","Agent","ToolSearch","NotebookEdit"]}}
EOF
fi

PROMPT='Read tools/auto_prompt.md (UTF-8, Korean) in this project and carry out every step in it exactly. Reply in Korean. You are running on macOS (the Mac mini server): use python3 instead of python, use ~/Desktop for the Desktop folder, and replace every "msg *" popup with: osascript -e '"'"'display notification "<message>" with title "좋은꿈 홈페이지"'"'"'.'

START=$(date +%s)
# 한 번 불릴 때 Claude 를 한 번 돌리고, 걸린 시간에 비례해 쉰다(tools/pace.py 가 다음 실행 시각을 정함).
git pull --rebase --autostash >/dev/null 2>&1
date > "$LOCK"
log "자동 작업 시작"
EFFORT="$(python3 tools/pace.py effort 2>/dev/null || echo xhigh)"
log "지능: $EFFORT"
OUT="$(claude -p "$PROMPT" --model opus --effort "$EFFORT" 2>&1)"
ALL="$OUT"
LAST="$(echo "$OUT" | grep -v '^[[:space:]]*$' | tail -3 | tr '\n' ' ' | cut -c1-400)"
log "끝: $LAST"
printf '%s' "$OUT" > "$PROJ/tools/.last_out.txt"
python3 tools/pace.py record "$START" "$(date +%s)" "$PROJ/tools/.last_out.txt" >/dev/null 2>&1
log "속도: $(python3 tools/pace.py status | head -1)"
OUT="$ALL"

if echo "$LAST" | grep -qiE 'hit your .*limit|usage limit|rate limit|429'; then
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
