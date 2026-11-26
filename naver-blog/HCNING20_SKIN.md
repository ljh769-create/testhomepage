# hcning20 블로그 꾸미기 — 윈도우 PC Claude 에게 넘기는 일 (2026-11-26, 맥미니 대화 세션)

원장님이 고른 방법: **윈도우 PC 의 Claude 가 자동화 브라우저(playwright, login.mjs 와 같은 고정 프로필)로 직접 적용.**
Claude in Chrome 확장은 네이버 블로그 사이트가 안전 제한으로 막혀서 못 씀.

## 확인된 사실
- hcning20 = 원장님 본인 아이디(원장님 확인). 지금 블로그 이름 "ㅇㅇㅇ", 별명 "중인배", 공개 글 0, 네이버 기본 초록 잎사귀 스킨.
- 역할: "이종호 원장의 진료실" — 원장님 1인칭 개인 블로그. 원장님 얼굴 사진 사용 허락.
- 시안(원장님 확인용): https://claude.ai/artifact/EskPVc9txrRa5Urr3ztaEQ

## 적용할 것 (그림은 skin/hcning20/, 다시 만들려면 `node blogskin.mjs`)
1. 블로그 이름: 이종호 원장의 진료실 / 별명: 이종호 원장
2. 소개 문구: 상도동 한의사 이종호가 직접 씁니다. 좋은꿈참사랑한의원 대표원장 · 02-815-7510
3. 프로필 사진: skin/hcning20/profile.png
4. 스킨: 아이보리 단색 배경(#F7F2EA), 타이틀 직접 등록 = skin/hcning20/title.png (966×520)
5. 카테고리(기존 「낙서장」「포토로그」는 숨김): 진료실 이야기 / 잘 먹고·소화 / 잘 자고·수면 / 마음·몸 온도 / 통증·추나 / 원장 소개 / 오시는 길
6. 상단 메뉴: 위 카테고리 연결. menu.png·icons.png 는 위젯이나 공지 글 위쪽 그림으로 쓰고, 누르면 카테고리로 가게 링크(가능한 범위에서)
7. 관리 화면 조작 도구는 아직 없음 → login.mjs 의 고정 프로필로 admin.blog.naver.com 을 여는 스크립트를 새로 만들 것. 로그인은 원장님이 그 창에서 직접(비밀번호는 Claude 가 입력하지 않음).

## 견본 글(프리미엄 플러스 기준)
- posts/hcning20-five-basics.md + cards-premium/hcning20-five-basics.json → `node premium.mjs hcning20-five-basics` 로 그림 23장 생성(사진은 images/real/).
- 원장님 기준: 블로그 6,000~8,000자·그림 18~25장, 홈페이지 기둥 글 1만 자·그림 20장 이상. 의료광고 점검(tools/ad_check.py) 통과 필수.
- 발행은 B안: 네이버 예약 발행으로 일주일 치 몰아 걸기(post.mjs 에 예약 기능 추가 필요, 아직 안 함). 오래 멈춘 블로그라 1주차 2편부터 천천히.
