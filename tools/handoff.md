# 두 Claude 사이 작업 공유판 (윈도우 PC ↔ 맥미니)

원장님 지시(2026-11-25): "실시간으로 서로 공유해야지."
**규칙:** 작업을 시작하기 전에 `git pull` 하고 이 파일을 읽는다. 시작할 때 "지금 하는 일"에 한 줄 적고 push, 끝나면 지우고 "최근 끝낸 일"로 옮긴다. 다른 쪽이 같은 파일을 만지고 있으면 그 파일은 건드리지 않는다. 장기기억은 `tools/sync_memory.sh`(맥) / `tools/sync_memory.ps1`(윈도우)로 비공개 저장소와 맞춘다. 두 쪽 모두 Remote Control 이 켜져 있으면 SendMessage 로 서로 직접 알릴 수 있다.

## 지금 하는 일 (누가 · 무엇 · 건드리는 파일 · 시작 시각)
- 클라우드 Claude(휴대폰 세션) · 11/26 06:00~ · 원장님 지시 '모든 질환 기둥글 작업' — 질환별 기둥 글 26편(새 글 19·짧은 글 보강 7~11). 건드리는 파일: 새 파일 content/posts/bulk-pillars-a~g.md, 보강 bulk-metabolic3.md(fatty-liver-checkup)·bulk-others3.md(neck-arm-numbness)·bulk-r2-a.md(panic-like-episodes)·bulk-r2-e.md(hoarse-voice-overuse)·bulk-women-pediatric.md(irregular-periods·child-frequent-colds·child-bedwetting)·bulk-r10-e.md(child-tummy-ache-where-when-notes)·bulk-respiratory-skin-neuro-mental.md(recurrent-acne)·bulk-r6-a.md(scalp-oily-washing-habit), 끝나면 content/drip.json(새 글 오늘 자리에 끼움)·review_ledger.json. 맥미니는 이 파일들 건드리지 말아 주세요
- 맥미니 자동 실행 · 11/26 04:14~ (05:20 한도 리셋 뒤 이어서) · 4-00 검수(보강한 메뉴 글 9편·한약·공진단·녹용 6편·의료진·한의원 안내 7편)·B5 보강(insomnia-guide·reducing-sleeping-pills·metabolic-before-visit·study-chair-desk-setup-back·exam-study-afternoon-slump·evening-visit-preparation) · 글은 /tmp/hanui-auto-0426/review3·review4·boost2·boost3 에 따로 떼어 고치는 중(파일 = 글 하나, .orig 와 비교) → `python3 /tmp/hanui-auto-0426/chunks.py merge <저장소> <폴더> <slug...>` 로 되돌려 넣음. 건드리는 파일: content/posts/bulk-herbal-1.md·bulk-clinic-1.md·bulk-r4-a.md·bulk-sleep-digestion.md·insomnia-guide.md·metabolic-before-visit.md·bulk-metabolic-accident-first.md·bulk-pain.md·bulk-metabolic2.md, content/review_ledger.json, content/drip.json(검수 끝난 메뉴 글 10편을 오늘 핵심 글 바로 뒤로 당길 예정), tools/auto_state.json. body-images.json·그림은 안 건드림

## 최근 끝낸 일
- 맥미니 자동 실행 · 11/26 00:31~01:55 · A·B 점검(AEO 96→100: '먼저 확인' 구역 빠진 11편·'왜' 소제목 없던 39편 고침), 전수 검수 62편(review_ledger), 오늘 앞당겨진 핵심 증상 글 20편 5,000자 보강(그림은 대화 세션), 예정 글 7편 보강, 원장님 지정 11·12번 새 글(drip 90·91), 안내 그림 5장, 교통사고 허브에 티로 상담 설명(통증과 후유증·젠가·골절과 염좌), pace.py FULL_SPEED 오류 수정. 배포는 /tmp worktree 에서 origin/main + 내 파일만으로 빌드·점검(이 폴더 미커밋 작업이 섞이지 않게). 다음 맥 실행: 4-00 검수 bulk-r3-e.md 부터, 티로 상담 기록(복지관 cUzZnt3LMeWGf) 글 마무리, 11/27·28 예정 글 길이 점검
- 클라우드 Claude(휴대폰 세션) · 11/25 밤 · 디자인 원칙 4-01 첫 적용: 원장님 소개 페이지 3개에 움직임(시네마틱 첫 화면·스크롤 나타나기·유리 카드·마우스 기울기 사진·숫자 올라가기). 공용 파일은 안 건드리고 새 파일 motion.css·motion.js(약 9KB, 라이브러리 없음, 움직임 줄이기 설정 존중) — 다른 페이지도 `<link rel="stylesheet" href="motion.css">` + `<script src="motion.js" defer>` 와 data-mo·tilt·cine·dp-glass·dp-cards·data-n 표시만 붙이면 같은 효과
- 클라우드 Claude(휴대폰 세션) · 11/25 밤 · 원장님 소개 페이지 doctor-lee·jo·jeong.html(ProfilePage, 글 감수자 표시·reviewedBy 를 doctor-lee.html#person 으로 연결, build.py build_doctors), 동네 질문 글 3편(content/posts/bulk-local-access.md: 일요일·공휴일 진료, 평일 퇴근길 저녁 진료, 숭실대·중앙대 시험 기간), 월 1회 AI 노출 점검(tools/ai_visibility.md·.py, 매뉴얼 F2). 조영기·정원영 원장 진료 철학 문구는 원장님 확인 전이라 비워 둠
- 맥미니 자동 실행 · 11/25 21:22~22:50 · 원장님 지정 7~10번 글, 새 글 10편(4-1 새 원칙 전에 쓴 것 — 이후 새 글 중단), 글 보강 40편(4-3 기준·원천자료 연결: 핵심 안내 5·장비 5·노량진 수험생 5·추나·진맥 5·장비·검사·사고 5·오래된 수면 5·11/27 예정 5·11/30 진맥 예정 5), 안내 그림 15, 본문 그림 20편 60장. 다음 맥 실행: 티로 새 강의·강연 노트 1개(4-0-1), 원장님 지정 11·12, 예정 글(bulk-cards-a·bulk-tiro-c·bulk-pulse-a 나머지) 발행 전 보강
- 윈도우 PC · 11/25 · 네이버·구글·AEO·GEO 400점 달성, 배포 전 점수 검사(site_audit --local --compare), 정식 상호 legalName, 빙·IndexNow, 진맥 페이지·사진, Ollama 위임 계획
- 윈도우 PC · 11/25 · 장기기억 동기화 스크립트와 이 공유판 추가

## 윈도우 PC만 할 수 있는 일
- 이 PC 안의 원본 자료: images 폴더 원본 사진(환자정보 확인 필요), 티로·지피티 자료 정리, Chrome 연결(구글·빙·네이버 관리 화면)
