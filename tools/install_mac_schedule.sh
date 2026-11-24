#!/bin/bash
# 미니맥에서 한 번만 실행: 15분마다 auto_run_mac.sh 를 자동 실행하도록 launchd 에 등록한다.
# 해제: bash tools/install_mac_schedule.sh off
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.gooddream.autowork"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "off" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$PLIST"; echo "자동 실행을 껐습니다."; exit 0
fi

chmod +x "$PROJ/tools/auto_run_mac.sh"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$PROJ/tools/auto_run_mac.sh</string></array>
  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/gooddream-auto.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/gooddream-auto.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "✅ 15분마다 자동 실행 등록 완료 (바로 한 번 시작됩니다). 기록: 바탕화면/자동작업_기록.txt"
