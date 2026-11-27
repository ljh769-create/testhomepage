// premium.mjs — 프리미엄 블로그 그림 생성기 (cards.mjs 는 그대로 두고 따로 씀)
// 사용: node premium.mjs <slug>   → cards-premium/<slug>.json → images/<slug>/01.png(jpg) …
// 종류: coverPhoto / photo / five / chapter / check / compare / quote / steps / warn / selfcheck / note / info
// 사진 src 는 hanui/images/real/ 기준 파일 이름(예: "director-portrait.jpg")
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.join(__dirname, '..', 'images', 'real');
const slug = process.argv[2];
if (!slug) { console.error('사용: node premium.mjs <slug>'); process.exit(1); }
const spec = JSON.parse(fs.readFileSync(path.join(__dirname, 'cards-premium', `${slug}.json`), 'utf8'));
const outDir = path.join(__dirname, 'images', slug);
fs.mkdirSync(outDir, { recursive: true });

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
const img = (f) => `data:image/jpeg;base64,${fs.readFileSync(path.join(REAL, f)).toString('base64')}`;
const BRAND = spec.brand || '좋은꿈참사랑한의원 · 대표원장 이종호';

const C = { ivory: '#F7F2EA', paper: '#FFFDF9', ink: '#1F2A37', sub: '#6A6358', gold: '#A8834A', goldSoft: '#EFE3CF',
  sage: '#5C7A68', sageSoft: '#E3ECE5', navy: '#22334A', red: '#A6402F', redSoft: '#F6E2DC' };
const ACC = { gold: [C.gold, C.goldSoft], sage: [C.sage, C.sageSoft], navy: [C.navy, '#DDE3EC'], red: [C.red, C.redSoft] };

const base = (w, h) => `*{box-sizing:border-box;margin:0;padding:0}
body{width:${w}px;height:${h}px;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:${C.ink};word-break:keep-all;-webkit-font-smoothing:antialiased}
.serif{font-family:'AppleMyungjo','Nanum Myeongjo',serif}
.brand{position:absolute;left:72px;bottom:40px;font-size:22px;letter-spacing:.5px;color:${C.sub}}
.pg{position:absolute;right:72px;bottom:40px;font-size:22px;color:${C.sub};letter-spacing:2px}
.kick{display:inline-block;font-size:24px;font-weight:700;letter-spacing:3px;padding:10px 22px;border-radius:999px}
.rule{width:64px;height:4px;margin:28px 0}`;

function page(card, i, n) {
  const [acc, soft] = ACC[card.accent || 'gold'];
  const W = 1080;
  const foot = `<div class="brand">${esc(BRAND)}</div><div class="pg">${String(i).padStart(2, '0')} / ${String(n).padStart(2, '0')}</div>`;
  const box = (inner, H = 1080, bg = C.ivory) => ({ W, H, html: `<style>${base(W, H)}
    .wrap{position:absolute;inset:0;background:${bg};padding:96px 88px}
    h2{font-size:56px;line-height:1.3;font-weight:800;letter-spacing:-1px}
    .lead{font-size:30px;line-height:1.6;color:${C.sub};margin-top:20px}
    ul{list-style:none;margin-top:44px;display:flex;flex-direction:column;gap:22px}
    li{display:flex;gap:22px;align-items:flex-start;font-size:34px;line-height:1.45;background:${C.paper};border-radius:22px;padding:24px 30px;box-shadow:0 2px 0 rgba(0,0,0,.04)}
    .n{flex:none;width:52px;height:52px;border-radius:50%;background:${acc};color:#fff;font-weight:800;font-size:28px;display:flex;align-items:center;justify-content:center}
    .bx{flex:none;width:40px;height:40px;border:4px solid ${acc};border-radius:10px;margin-top:4px}
    .dot{flex:none;width:14px;height:14px;border-radius:50%;background:${acc};margin-top:18px}
  </style><div class="wrap">${inner}</div>${foot}` });

  switch (card.type) {
    case 'coverPhoto': return { W, H: 1350, html: `<style>${base(W, 1350)}
      .bg{position:absolute;inset:0;background:url(${img(card.src)}) center ${card.pos || '30%'}/cover}
      .sh{position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,24,30,0) 30%,rgba(20,24,30,.55) 55%,rgba(20,24,30,.92) 100%)}
      .tx{position:absolute;left:80px;right:80px;bottom:150px;color:#fff}
      .kick{background:${C.gold};color:#fff}
      h1{font-size:72px;line-height:1.25;font-weight:800;letter-spacing:-1.5px;margin-top:30px}
      .s{font-size:34px;line-height:1.5;margin-top:26px;color:#EDE4D3}
      .brand,.pg{color:#D9CFBE}</style>
      <div class="bg"></div><div class="sh"></div><div class="tx"><span class="kick">${esc(card.kicker)}</span><h1>${esc(card.title)}</h1><div class="s">${esc(card.sub)}</div></div>${foot}` };
    case 'photo': return { W, H: 900, html: `<style>${base(W, 900)}
      body{background:${C.ivory}}
      .ph{position:absolute;left:0;top:0;width:${W}px;height:760px;background:url(${img(card.src)}) center ${card.pos || '50%'}/cover}
      .cap{position:absolute;left:72px;right:72px;top:790px;font-size:28px;line-height:1.4;color:${C.ink};display:flex;gap:18px;align-items:center}
      .cap:before{content:'';width:36px;height:3px;background:${C.gold};flex:none}
      .brand,.pg{bottom:22px;font-size:19px}</style>
      <div class="ph"></div><div class="cap">${esc(card.caption)}</div>${foot}` };
    case 'chapter': return { W, H: 1080, html: `<style>${base(W, 1080)}
      body{background:${C.navy};color:#fff}
      .ph{position:absolute;right:0;top:0;width:470px;height:1080px;background:url(${img(card.src)}) center/cover;opacity:.9}
      .fade{position:absolute;right:0;top:0;width:470px;height:1080px;background:linear-gradient(90deg,${C.navy},rgba(34,51,74,.1) 45%)}
      .tx{position:absolute;left:88px;top:200px;width:560px}
      .num{font-size:220px;line-height:1;color:${C.gold}}
      .lab{font-size:26px;letter-spacing:6px;color:#C9BBA2;margin-top:24px}
      h2{font-size:84px;line-height:1.2;font-weight:800;margin-top:40px;letter-spacing:-2px}
      .s{font-size:32px;line-height:1.6;color:#D6DCE4;margin-top:34px}
      .brand,.pg{color:#9FAFC2}</style>
      ${card.src ? '<div class="ph"></div><div class="fade"></div>' : ''}<div class="tx"><div class="num serif">${esc(card.num)}</div><div class="lab">${esc(card.label || 'CHAPTER')}</div><h2>${esc(card.title)}</h2><div class="s">${esc(card.sub)}</div></div>${foot}` };
    case 'five': return box(`<span class="kick" style="background:${soft};color:${acc}">${esc(card.kicker)}</span>
      <h2 style="margin-top:28px">${esc(card.title)}</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:48px">
      ${card.items.map((x, k) => `<div style="background:${C.paper};border-radius:26px;padding:30px 32px;${k === 4 ? 'grid-column:1/3;' : ''}display:flex;gap:24px;align-items:center">
        <div class="serif" style="flex:none;width:86px;height:86px;border-radius:50%;background:${[C.gold, C.sage, C.navy, '#8A6A8E', C.red][k]};color:#fff;font-size:40px;display:flex;align-items:center;justify-content:center">${k + 1}</div>
        <div><div style="font-size:38px;font-weight:800">${esc(x.t)}</div><div style="font-size:25px;color:${C.sub};margin-top:6px;line-height:1.4">${esc(x.d)}</div></div></div>`).join('')}
      </div>`);
    case 'check': case 'steps': case 'warn': {
      const warn = card.type === 'warn';
      const [a2] = warn ? ACC.red : [acc];
      const mark = (k) => card.type === 'steps' ? `<span class="n" style="background:${a2}">${k + 1}</span>` : card.type === 'check' ? '<span class="bx"></span>' : `<span class="dot" style="background:${a2}"></span>`;
      return box(`<span class="kick" style="background:${warn ? C.redSoft : soft};color:${a2}">${esc(card.kicker || (warn ? '먼저 병원 진료를 권합니다' : ''))}</span>
        <h2 style="margin-top:28px;${warn ? `color:${C.red}` : ''}">${esc(card.title)}</h2>${card.sub ? `<div class="lead">${esc(card.sub)}</div>` : ''}
        <ul>${card.items.map((x, k) => `<li>${mark(k)}<span>${esc(x)}</span></li>`).join('')}</ul>`, 1080, warn ? '#FBF1EE' : C.ivory);
    }
    case 'compare': return box(`<span class="kick" style="background:${soft};color:${acc}">${esc(card.kicker)}</span>
      <h2 style="margin-top:28px">${esc(card.title)}</h2>
      <div style="display:flex;flex-direction:column;gap:22px;margin-top:44px">${card.cols.map((c, k) => `
        <div style="background:${C.paper};border-radius:26px;padding:30px 36px;border-left:12px solid ${[C.gold, C.sage, C.navy][k % 3]}">
        <div style="font-size:36px;font-weight:800">${esc(c.head)}</div><div style="font-size:28px;color:${C.sub};margin-top:10px;line-height:1.5">${esc(c.body)}</div></div>`).join('')}</div>`);
    case 'selfcheck': return box(`<span class="kick" style="background:${soft};color:${acc}">${esc(card.kicker)}</span>
      <h2 style="margin-top:24px">${esc(card.title)}</h2>
      <div style="display:flex;flex-direction:column;gap:20px;margin-top:44px">${card.rows.map((r, k) => `
        <div style="background:${C.paper};border-radius:22px;padding:28px 32px;display:flex;gap:28px;align-items:center">
        <div style="flex:none;width:170px;font-size:40px;font-weight:800;color:${[C.gold, C.sage, C.navy, '#8A6A8E', C.red][k]}">${esc(r.head)}</div>
        <div style="display:flex;flex-direction:column;gap:12px">${r.items.map((x) => `<div style="font-size:32px;display:flex;gap:16px;align-items:center"><span style="flex:none;width:32px;height:32px;border:3px solid ${C.sub};border-radius:6px"></span>${esc(x)}</div>`).join('')}</div></div>`).join('')}</div>`, 1260);
    case 'quote': return { W, H: 1080, html: `<style>${base(W, 1080)}
      body{background:${C.ivory}}
      .ph{position:absolute;left:88px;top:110px;width:230px;height:230px;border-radius:50%;background:url(${img(card.src)}) center 20%/cover;border:8px solid ${C.paper};box-shadow:0 6px 24px rgba(0,0,0,.12)}
      .q{position:absolute;left:88px;right:88px;top:400px}
      .mk{font-size:160px;line-height:.6;color:${C.gold}}
      .t{font-size:54px;line-height:1.5;margin-top:10px}
      .w{font-size:28px;color:${C.sub};margin-top:44px}</style>
      <div class="ph"></div><div class="q serif"><div class="mk">“</div><div class="t">${esc(card.text)}</div><div class="w" style="font-family:'Apple SD Gothic Neo'">${esc(card.who)}</div></div>${foot}` };
    case 'note': return { W, H: 1080, html: `<style>${base(W, 1080)}
      body{background:${C.navy};color:#fff}
      .t{position:absolute;left:96px;right:96px;top:50%;transform:translateY(-55%)}
      .kick{background:${C.gold};color:#fff}
      .b{font-size:66px;line-height:1.45;margin-top:40px}
      .s{font-size:30px;line-height:1.6;color:#C9D2DD;margin-top:36px}
      .brand,.pg{color:#9FAFC2}</style>
      <div class="t"><span class="kick">${esc(card.kicker)}</span><div class="b serif">${esc(card.title)}</div><div class="s">${esc(card.sub)}</div></div>${foot}` };
    case 'info': return box(`<span class="kick" style="background:${soft};color:${acc}">${esc(card.kicker || '오시는 길 · 진료시간')}</span>
      <h2 style="margin-top:28px">${esc(card.title)}</h2>
      <div style="margin-top:44px;background:${C.paper};border-radius:28px;padding:20px 40px">${card.rows.map(([k, v], j) => `
        <div style="display:flex;gap:30px;padding:24px 0;${j ? 'border-top:2px solid #EEE6D8' : ''}"><div style="flex:none;width:170px;font-size:28px;font-weight:800;color:${acc}">${esc(k)}</div><div style="font-size:29px;line-height:1.5">${esc(v)}</div></div>`).join('')}</div>`, 1180);
    default: throw new Error('모르는 종류: ' + card.type);
  }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
// 카드마다 새 창 + 사진 디코딩·그리기 끝까지 기다림 (한 창에서 크기를 바꿔 가며 찍으면 사진이 캡션 위에 겹쳐 찍히는 일이 있었음, 2026-11-27)
const n = spec.cards.length;
for (let i = 0; i < n; i++) {
  const c = spec.cards[i];
  const { W, H, html } = page(c, i + 1, n);
  const pg = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: W, height: H } });
  await pg.setContent(`<!doctype html><html><head><meta charset="utf-8"></head><body>${html}</body></html>`, { waitUntil: 'load' });
  await pg.evaluate(async () => {
    await Promise.all([...document.images].map((im) => im.decode().catch(() => {})));
    const urls = [...document.querySelectorAll('*')].map((e) => getComputedStyle(e).backgroundImage).filter((b) => b.startsWith('url('));
    await Promise.all(urls.map((u) => new Promise((r) => { const im = new Image(); im.onload = im.onerror = r; im.src = u.slice(5, -2); })));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  });
  await pg.waitForTimeout(150);
  const isPhoto = ['photo', 'coverPhoto', 'chapter', 'quote'].includes(c.type);
  const file = path.join(outDir, String(i + 1).padStart(2, '0') + (c.type === 'photo' ? '.jpg' : '.png'));
  await pg.screenshot(c.type === 'photo' ? { path: file, type: 'jpeg', quality: 88 } : { path: file });
  await pg.close();
}
await browser.close();
console.log(`✅ ${n}장: ${outDir}`);
