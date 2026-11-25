#!/bin/bash
# 공유 폴더(~/hanui) 대신 내 git worktree 에서 배포: 최신 받기(내 content·tools 원본 보존) → 빌드(메인 폴더의 그림 주문서 2개를 복사 — 안 하면 본문 그림이 빠짐) → 끊긴 링크·최종 점검·의료광고·400점 점검 → 커밋 → 푸시(거절되면 다시 받아 재시도).
# body-images.json 은 대화 세션 몫이라 커밋하지 않는다(빌드에만 씀). 로그는 $LOGDIR.
# 사용: WT=/tmp/내-worktree bash tools/wt_deploy.sh "커밋 메시지"   (worktree 만들기: git -C ~/hanui worktree add --detach /tmp/내-worktree origin/main)
set -u
WT="${WT:?WT=worktree 경로를 지정하세요}"
MAIN="${MAIN:-$HOME/hanui}"
LOGDIR="${LOGDIR:-/tmp/wt_deploy_logs}"; mkdir -p "$LOGDIR"
MSG="$1"
cd "$WT" || exit 1

sync_origin() {
  git fetch -q origin || return 1
  if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then return 0; fi
  git checkout -q -- content/body-images.json 2>/dev/null
  # 내 원본(content·tools)만 임시 커밋으로 보관한다. 공용 stash 는 다른 세션 항목과 섞이므로 쓰지 않는다.
  git add -A -- content tools
  local tmp=0
  if ! git diff --cached --quiet; then git commit -q --no-verify -m "임시: 내 원본(wt_deploy)" && tmp=1; fi
  git checkout -q -- . && git clean -fdq -- guide data >/dev/null   # 빌드 결과는 버리고 다시 빌드
  if ! git rebase -q origin/main; then
    git rebase --abort
    echo "!! 내 원본과 최신 원본이 충돌 — 멈춤(내 원본은 임시 커밋 $(git rev-parse --short HEAD) 에 있음)"; return 1
  fi
  [ $tmp = 1 ] && git reset -q --soft HEAD~1
  return 0
}

build_check() {
  cp "$MAIN/content/body-images.json" content/body-images.json
  cp "$MAIN/content/body-images-auto.json" content/body-images-auto.json 2>/dev/null
  python3 build.py > $LOGDIR/build.log 2>&1 || { echo "!! 빌드 실패"; tail -5 $LOGDIR/build.log; return 1; }
  tail -1 $LOGDIR/build.log
  python3 tools/check_links.py | tee $LOGDIR/links.log | tail -1
  grep -q "끊긴 링크 0개" $LOGDIR/links.log || { echo "!! 끊긴 링크"; grep -v "^검사한" $LOGDIR/links.log | head -20; return 1; }
  python3 tools/final_check.py | python3 -c "import json,sys;d=json.load(sys.stdin);ok=d['노량진점']==0 and not d['JSON-LD 오류'] and not d['H1 1개 아닌 페이지'];print('최종 점검', '통과' if ok else '실패', d['노량진점'], d['JSON-LD 오류'][:3], d['H1 1개 아닌 페이지'][:3]);sys.exit(0 if ok else 1)" || return 1
  python3 tools/ad_check.py --quiet > $LOGDIR/ad.log 2>&1 || { echo "!! 의료광고 차단"; head -20 $LOGDIR/ad.log; return 1; }
  echo "의료광고 검수 통과"
  python3 tools/site_audit.py --local --compare > $LOGDIR/audit.log 2>&1; rc=$?
  head -1 $LOGDIR/audit.log; tail -1 $LOGDIR/audit.log
  [ $rc -eq 0 ] || { echo "!! 점수 하락"; grep -i "주의\|개선" $LOGDIR/audit.log | head; return 1; }
}

for try in 1 2 3; do
  sync_origin || exit 1
  build_check || exit 1
  git checkout -q -- content/body-images.json
  git add -A
  git reset -q -- content/body-images-auto.json 2>/dev/null
  if git diff --cached --quiet; then echo "바뀐 것 없음"; exit 0; fi
  git commit -q -m "$MSG

${COAUTHOR:-Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>}" || exit 1
  if git push -q origin HEAD:main 2>$LOGDIR/push.log; then
    echo "푸시 완료: $(git log --oneline -1)"; git diff --stat HEAD~1 --shortstat; exit 0
  fi
  echo "푸시 거절(원격에 새 커밋) — 다시 받아서 재시도 $try"; cat $LOGDIR/push.log | head -3
  git reset -q --mixed HEAD~1
done
exit 1
