# 두 Claude 사이 작업 공유판 (윈도우 PC ↔ 맥미니)

원장님 지시(2026-11-25): "실시간으로 서로 공유해야지."
**규칙:** 작업을 시작하기 전에 `git pull` 하고 이 파일을 읽는다. 시작할 때 "지금 하는 일"에 한 줄 적고 push, 끝나면 지우고 "최근 끝낸 일"로 옮긴다. 다른 쪽이 같은 파일을 만지고 있으면 그 파일은 건드리지 않는다. 장기기억은 `tools/sync_memory.sh`(맥) / `tools/sync_memory.ps1`(윈도우)로 비공개 저장소와 맞춘다. 두 쪽 모두 Remote Control 이 켜져 있으면 SendMessage 로 서로 직접 알릴 수 있다.

## 지금 하는 일 (누가 · 무엇 · 건드리는 파일 · 시작 시각)
- 맥미니 자동 실행 · 11/26 00:31~ · 오늘 앞당겨진 핵심 증상 글 20편(drip 70~89) 공개 시각 순서대로 5,000자 보강, 11/27 짧은 예정 글 보강, 4-00 전수 검수(bulk-others3.md 진행) · 건드리는 파일: content/posts/bulk-respiratory-skin-neuro-mental.md·bulk-women-pediatric.md·bulk-sleep-digestion.md·bulk-r13-b.md·bulk-r13-a.md·bulk-others3.md 의 해당 slug, content/review_ledger.json, tools/auto_state.json (body-images*·images/body·pace.py 는 안 건드림) · 배포는 /tmp worktree 에서 내 파일만

## 최근 끝낸 일
- 클라우드 Claude(휴대폰 세션) · 11/25 밤 · 디자인 원칙 4-01 첫 적용: 원장님 소개 페이지 3개에 움직임(시네마틱 첫 화면·스크롤 나타나기·유리 카드·마우스 기울기 사진·숫자 올라가기). 공용 파일은 안 건드리고 새 파일 motion.css·motion.js(약 9KB, 라이브러리 없음, 움직임 줄이기 설정 존중) — 다른 페이지도 `<link rel="stylesheet" href="motion.css">` + `<script src="motion.js" defer>` 와 data-mo·tilt·cine·dp-glass·dp-cards·data-n 표시만 붙이면 같은 효과
- 클라우드 Claude(휴대폰 세션) · 11/25 밤 · 원장님 소개 페이지 doctor-lee·jo·jeong.html(ProfilePage, 글 감수자 표시·reviewedBy 를 doctor-lee.html#person 으로 연결, build.py build_doctors), 동네 질문 글 3편(content/posts/bulk-local-access.md: 일요일·공휴일 진료, 평일 퇴근길 저녁 진료, 숭실대·중앙대 시험 기간), 월 1회 AI 노출 점검(tools/ai_visibility.md·.py, 매뉴얼 F2). 조영기·정원영 원장 진료 철학 문구는 원장님 확인 전이라 비워 둠
- 맥미니 자동 실행 · 11/25 21:22~22:50 · 원장님 지정 7~10번 글, 새 글 10편(4-1 새 원칙 전에 쓴 것 — 이후 새 글 중단), 글 보강 40편(4-3 기준·원천자료 연결: 핵심 안내 5·장비 5·노량진 수험생 5·추나·진맥 5·장비·검사·사고 5·오래된 수면 5·11/27 예정 5·11/30 진맥 예정 5), 안내 그림 15, 본문 그림 20편 60장. 다음 맥 실행: 티로 새 강의·강연 노트 1개(4-0-1), 원장님 지정 11·12, 예정 글(bulk-cards-a·bulk-tiro-c·bulk-pulse-a 나머지) 발행 전 보강
- 윈도우 PC · 11/25 · 네이버·구글·AEO·GEO 400점 달성, 배포 전 점수 검사(site_audit --local --compare), 정식 상호 legalName, 빙·IndexNow, 진맥 페이지·사진, Ollama 위임 계획
- 윈도우 PC · 11/25 · 장기기억 동기화 스크립트와 이 공유판 추가

## 윈도우 PC만 할 수 있는 일
- 이 PC 안의 원본 자료: images 폴더 원본 사진(환자정보 확인 필요), 티로·지피티 자료 정리, Chrome 연결(구글·빙·네이버 관리 화면)
