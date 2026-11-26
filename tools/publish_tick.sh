#!/bin/bash
# 예약 글을 시간에 맞춰 공개(빌드·점검·푸시만, Claude 안 씀). auto_run_mac.sh 가 Claude 작업이 없을 때(한도 대기 등) 부른다.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1
git pull -q --rebase --autostash >/dev/null 2>&1
python3 build.py >/dev/null 2>&1 || exit 1
python3 tools/check_links.py | grep -q "끊긴 링크 0개" || exit 1
python3 tools/final_check.py | python3 -c "import json,sys;d=json.load(sys.stdin);sys.exit(0 if d['노량진점']==0 and not d['JSON-LD 오류'] and not d['H1 1개 아닌 페이지'] else 1)" || exit 1
git add -A guide today.html data llms.txt llms-full.txt sitemap.xml feed.xml index.html queue.html 2>/dev/null
git diff --cached --quiet && exit 0
git commit -q -m "예약 글 시간별 공개($(date '+%m/%d %H시'))"
# 원장님 지시(2026-11-26): 푸시(배포)는 3시간마다 — 커밋만 해 두고 때가 되면 한꺼번에 푸시
python3 tools/push_gate.py check >/dev/null && git push -q && python3 tools/push_gate.py done >/dev/null
