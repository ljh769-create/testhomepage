// blogskin.mjs — hcning20 블로그 꾸미기 그림 생성(대문·메뉴줄·주제 아이콘·프로필)
// 사용: node blogskin.mjs   → skin/hcning20/*.png
// 네이버 블로그 타이틀 가로 966px 기준.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.join(__dirname, '..', 'images', 'real');
const BLOG = process.argv[2] || 'hcning20';
const out = path.join(__dirname, 'skin', BLOG);
fs.mkdirSync(out, { recursive: true });
const img = (f) => `data:image/jpeg;base64,${fs.readFileSync(path.join(REAL, f)).toString('base64')}`;
const C = { ivory: '#F7F2EA', paper: '#FFFDF9', ink: '#1F2A37', sub: '#6A6358', gold: '#A8834A', navy: '#22334A' };
// 블로그별 문구·사진·포인트 색(사실은 auto_prompt.md 사실 목록과 같게)
const CFG = {
  hcning20: { photo: 'director-portrait.jpg', pos: 'center 18%', kick: '상도동 한의사의 진료실 이야기', h1: '양손 한번<br>올려 보세요.', s: '맥을 짚으며 잠과 식사와 마음까지 여쭙는<br>대표원장 이종호가 직접 씁니다.', chips: ['잘 먹고', '잘 싸고', '잘 자고', '마음 편하고', '몸 따뜻하게'], who: '대표원장 이종호', accent: C.navy },
  dream7510: { photo: 'team-stand.jpg', pos: 'center 30%', kick: '좋은꿈참사랑한의원 공식 블로그', h1: '건강한 리듬,<br>행복한 기억.', s: '상도역 3번 출구 · 모든 분의 맥부터 짚고<br>잠·식사·통증을 함께 살핍니다.', chips: ['통증·추나', '교통사고', '불면·수면', '소화·대사', '원장 칼럼'], who: '상도역 3번 출구', accent: '#2A5C4E' },
  dreampass7510: { photo: 'director-desk.jpg', pos: 'center 35%', kick: '노량진·상도 수험생 한방 클리닉', h1: '열심히 사는 당신을<br>응원합니다.', s: '시험 기간의 잠·집중·소화·자세를<br>진맥과 상담으로 함께 살핍니다.', chips: ['수험생 집중', '시험 전 잠', '소화·두통', '자세·목어깨', '체력'], who: '대표원장 이종호', accent: '#6B4A2B' },
};
const K = CFG[BLOG];
const base = `*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Apple SD Gothic Neo',sans-serif;color:${C.ink};word-break:keep-all;-webkit-font-smoothing:antialiased}.serif{font-family:'AppleMyungjo',serif}`;

// 선 아이콘(먹고·싸고·자고·마음·따뜻)
const ico = {
  eat: '<path d="M8 30h48c0 14-10 22-24 22S8 44 8 30z"/><path d="M20 22c0-4 4-4 4-8M32 22c0-4 4-4 4-8M44 22c0-4 4-4 4-8"/>',
  flow: '<path d="M32 8c10 14 16 22 16 30a16 16 0 0 1-32 0c0-8 6-16 16-30z"/><path d="M26 40a7 7 0 0 0 7 6"/>',
  sleep: '<path d="M44 10a22 22 0 1 0 10 30A18 18 0 0 1 44 10z"/><path d="M48 16h8l-8 8h8"/>',
  mind: '<path d="M32 52S10 39 10 24a11 11 0 0 1 22-3 11 11 0 0 1 22 3c0 15-22 28-22 28z"/>',
  warm: '<circle cx="32" cy="32" r="10"/><path d="M32 8v6M32 50v6M8 32h6M50 32h6M15 15l4 4M45 45l4 4M15 49l4-4M45 19l4-4"/>',
};
const svg = (k, c, s = 64) => `<svg width="${s}" height="${s}" viewBox="0 0 64 64" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">${ico[k]}</svg>`;

const pages = {
  // 1) 대문(타이틀) 966×520
  title: [966, 520, `<style>${base}
    body{width:966px;height:520px;background:${C.ivory};position:relative;overflow:hidden}
    .ph{position:absolute;right:0;top:0;width:520px;height:520px;background:url(${img(K.photo)}) ${K.pos}/cover}
    .fade{position:absolute;right:0;top:0;width:520px;height:520px;background:linear-gradient(90deg,${C.ivory} 0%,rgba(247,242,234,.85) 18%,rgba(247,242,234,.35) 38%,rgba(247,242,234,0) 60%)}
    .tx{position:absolute;left:64px;top:78px;width:470px}
    .k{font-size:17px;letter-spacing:4px;color:${C.gold};font-weight:700}
    h1{font-size:50px;line-height:1.28;margin-top:22px;letter-spacing:-1px}
    .s{font-size:19px;line-height:1.7;color:${C.sub};margin-top:22px}
    .five{display:flex;gap:8px;margin-top:26px;flex-wrap:wrap}.five span{font-size:15px;padding:6px 13px;border:1.5px solid ${C.gold};border-radius:99px;color:${C.gold};font-weight:700}
    .call{position:absolute;left:64px;bottom:46px;display:flex;gap:14px;align-items:center}
    .tel{background:${K.accent};color:#fff;font-size:24px;font-weight:800;padding:13px 26px;border-radius:99px;letter-spacing:.5px}
    .bk{border:2px solid ${K.accent};color:${K.accent};font-size:18px;font-weight:700;padding:12px 22px;border-radius:99px}
    .nm{position:absolute;right:36px;bottom:30px;text-align:right;color:#fff;text-shadow:0 1px 8px rgba(0,0,0,.45)}
    .nm small{font-size:15px;display:block}.nm b{font-size:22px}</style>
    <div class="ph"></div><div class="fade"></div>
    <div class="tx"><div class="k">${K.kick}</div>
    <h1 class="serif">${K.h1}</h1>
    <div class="s">${K.s}</div>
    <div class="five">${K.chips.map((x) => `<span>${x}</span>`).join('')}</div></div>
    <div class="call"><div class="tel">02-815-7510</div><div class="bk">네이버 예약 · 카톡 상담</div></div>
    <div class="nm"><small>좋은꿈참사랑한의원</small><b>${K.who}</b></div>`],
  // 2) 메뉴 줄 966×64
  menu: [966, 64, `<style>${base}body{width:966px;height:64px;background:${K.accent};display:flex;align-items:center;justify-content:space-around;color:#fff;font-size:19px;font-weight:600;letter-spacing:.5px}
    i{width:1px;height:18px;background:rgba(255,255,255,.25)}</style>
    <span>원장 소개</span><i></i><span>진료실 이야기</span><i></i><span>잠·수면</span><i></i><span>소화·식사</span><i></i><span>통증·추나</span><i></i><span>오시는 길</span>`],
  // 3) 주제 아이콘 5칸 966×250
  icons: [966, 250, `<style>${base}body{background:${C.ivory}}.w{width:966px;height:250px;display:flex;gap:12px;padding:22px 18px}
    .c{flex:1;background:${C.paper};border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;box-shadow:0 2px 0 rgba(0,0,0,.04)}
    .c b{font-size:20px}.c small{font-size:14px;color:${C.sub}}</style>
    <div class="w">${[['eat', '잘 먹고', '식사·소화', C.gold], ['flow', '잘 싸고', '장·화장실', '#5C7A68'], ['sleep', '잘 자고', '불면·수면', C.navy], ['mind', '마음 편하고', '스트레스·불안', '#8A6A8E'], ['warm', '몸 따뜻하게', '냉증·순환', '#A6402F']]
      .map(([k, t, s, c]) => `<div class="c">${svg(k, c, 58)}<b>${t}</b><small>${s}</small></div>`).join('')}</div>`],
  // 3-1) 진료시간·주소 띠 966×150
  hours: [966, 150, `<style>${base}body{background:${K.accent}}.w{width:966px;height:150px;display:flex;align-items:center;gap:36px;padding:0 48px;color:#fff}
    .t{font-size:18px;color:#E8D9BE;font-weight:700;letter-spacing:2px;width:90px;flex:none}.r{font-size:19px;line-height:1.75}.r b{color:#F3E6CC;margin-right:10px}
    .v{width:1px;height:90px;background:rgba(255,255,255,.25)}</style>
    <div class="w"><div class="t">진료시간</div><div class="r"><b>평일</b>09:30~20:00 (점심 13:00~14:00)<br><b>토·일·공휴일</b>09:30~15:00 (점심시간 없음)</div><div class="v"></div>
    <div class="r"><b>전화</b>02-815-7510<br><b>주소</b>동작구 만양로2길 2 신성빌딩 3층·5층<br><b>오시는 길</b>상도역 3번 출구</div></div>`],
  // 4) 프로필 400×400
  profile: [400, 400, `<style>${base}body{background:url(${img(K.photo)}) ${K.pos}/cover}</style>`],
};

const b = await chromium.launch({ channel: 'chrome', headless: true });
for (const [name, [w, h, html]] of Object.entries(pages)) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.setContent(`<!doctype html><meta charset="utf-8">${html}`, { waitUntil: 'load' });
  await p.waitForTimeout(150);
  await p.screenshot({ path: path.join(out, `${name}.png`) });
  await p.close();
}
await b.close();
console.log('✅', fs.readdirSync(out).join(', '));
