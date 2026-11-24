자동 작업(1시간마다, 원장님 승인: "그래픽·글 계속 늘리고 배포까지"). 한글로만 기록한다.
1) git pull --rebase 로 최신 상태를 받는다.
2) 발행된 글(build.load_posts()) 중 images/info/post-<slug>.svg 가 없는 글 10편을 골라, 기존 post-*.svg 와 같은 스타일의 안내 그림을 만든다(scratchpad 대신 tools/ 밖의 임시 파일은 %TEMP% 에). 규칙: 1200x675, 바닥글 '좋은꿈참사랑한의원 · 02-815-7510 · 일반 건강 정보이며 진단·치료를 대신하지 않습니다', '노량진점' 절대 금지, 글에 있는 사실만, 효과·가격·최상급 금지, 줄당 22자 이하, 주황 '먼저 확인이 필요한 신호' 상자(마음 관련은 109·119). 한 장 끝날 때마다 바로 저장.
   모든 발행 글에 그림이 있으면 대신 새 글 10편을 content/posts/bulk-auto-<날짜>.md 에 쓴다(기존 글과 같은 형식·의료광고 규칙, date 는 내일, content/drip.json 의 아직 발행 안 된 순서 맨 앞에 끼워 하루 2편 유지).
3) python build.py → python tools/check_links.py → python tools/final_check.py 를 돌려 끊긴 링크 0, 노량진점 0, JSON-LD 오류 0 일 때만 git add -A, git commit(메시지 끝에 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'), git pull --rebase, git push.
4) 마지막에 무엇을 했는지 한 줄로 출력한다.
