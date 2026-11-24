// cards.mjs — 설명 카드 이미지(PNG) 생성기
// 사용: node cards.mjs <slug>      → cards/<slug>.json 을 읽어 images/<slug>/01.png, 02.png … 생성
// 카드 종류: cover(표지) / list(체크리스트) / steps(단계) / warn(병원 먼저) / note(핵심 한 줄) / compare(비교 2열)
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const slug = process.argv[2];
if (!slug) { console.error('사용: node cards.mjs <slug>'); process.exit(1); }
const spec = JSON.parse(fs.readFileSync(path.join(__dirname, 'cards', `${slug}.json`), 'utf8'));
const outDir = path.join(__dirname, 'images', slug);
fs.mkdirSync(outDir, { recursive: true });

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// 카드 하단 왼쪽 문구. JSON 에 "footer" 를 주면 그 값(빈 문자열이면 표시 안 함), 없으면 한의원 이름.
const CLINIC = typeof spec.footer === 'string' ? spec.footer : '좋은꿈참사랑한의원';

const THEMES = {
  sky:   { bg: '#EAF4FB', card: '#FFFFFF', main: '#1F6FA8', soft: '#D3E8F6', text: '#1D2B36', sub: '#5A6B78' },
  mint:  { bg: '#EAF6F1', card: '#FFFFFF', main: '#2A8068', soft: '#CFEBE0', text: '#1D2B36', sub: '#5A6B78' },
  warm:  { bg: '#FBF3E8', card: '#FFFFFF', main: '#B26A1F', soft: '#F5E1C4', text: '#2B2218', sub: '#6B5E50' },
  warn:  { bg: '#FDF0EE', card: '#FFFFFF', main: '#B5412F', soft: '#F8D8D2', text: '#2B1D1A', sub: '#6B5450' },
  night: { bg: '#18283A', card: '#223650', main: '#8CC4F0', soft: '#2E4868', text: '#F2F7FB', sub: '#A9BCCF' },
};

function html(card, idx, total) {
  const t = THEMES[card.theme || (card.type === 'warn' ? 'warn' : 'sky')];
  let body = '';
  if (card.type === 'cover') {
    body = `<div class="kicker">${esc(card.kicker || '건강 이야기')}</div>
            <h1>${esc(card.title)}</h1>
            ${card.sub ? `<p class="lead">${esc(card.sub)}</p>` : ''}`;
  } else if (card.type === 'list') {
    body = `<h2>${esc(card.title)}</h2><ul>${card.items.map((x) => `<li><span class="dot"></span><span>${esc(x)}</span></li>`).join('')}</ul>`;
  } else if (card.type === 'steps') {
    body = `<h2>${esc(card.title)}</h2><ol>${card.items.map((x, i) => `<li><span class="num">${i + 1}</span><span>${esc(x)}</span></li>`).join('')}</ol>`;
  } else if (card.type === 'warn') {
    body = `<div class="kicker">${esc(card.kicker || '먼저 병원 진료를 권합니다')}</div><h2>${esc(card.title)}</h2><ul>${card.items.map((x) => `<li><span class="dot"></span><span>${esc(x)}</span></li>`).join('')}</ul>`;
  } else if (card.type === 'note') {
    body = `<div class="kicker">${esc(card.kicker || '기억해 두세요')}</div><p class="big">${esc(card.title)}</p>${card.sub ? `<p class="lead">${esc(card.sub)}</p>` : ''}`;
  } else if (card.type === 'compare') {
    body = `<h2>${esc(card.title)}</h2><div class="cols">${card.cols.map((c) => `<div class="col"><h3>${esc(c.head)}</h3><ul>${c.items.map((x) => `<li><span class="dot"></span><span>${esc(x)}</span></li>`).join('')}</ul></div>`).join('')}</div>`;
  }
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{width:1200px;height:800px;background:${t.bg};font-family:'Malgun Gothic','맑은 고딕','Apple SD Gothic Neo',sans-serif;color:${t.text};display:flex;align-items:center;justify-content:center}
  .card{width:1080px;height:680px;background:${t.card};border-radius:36px;padding:56px 72px;position:relative;box-shadow:0 8px 30px rgba(0,0,0,.08);display:flex;flex-direction:column;justify-content:center;border-top:14px solid ${t.main}}
  .kicker{display:inline-block;align-self:flex-start;background:${t.soft};color:${t.main};font-weight:700;font-size:26px;padding:8px 22px;border-radius:999px;margin-bottom:26px}
  h1{font-size:66px;line-height:1.28;font-weight:800;letter-spacing:-1.5px;word-break:keep-all}
  h2{font-size:48px;line-height:1.3;font-weight:800;margin-bottom:30px;color:${t.main};word-break:keep-all}
  h3{font-size:32px;margin-bottom:16px;color:${t.main}}
  .lead{font-size:32px;line-height:1.55;color:${t.sub};margin-top:26px;word-break:keep-all}
  .big{font-size:56px;line-height:1.4;font-weight:800;word-break:keep-all}
  ul,ol{list-style:none;display:flex;flex-direction:column;gap:18px}
  li{display:flex;align-items:flex-start;gap:18px;font-size:33px;line-height:1.45;word-break:keep-all}
  .dot{flex:none;width:16px;height:16px;border-radius:50%;background:${t.main};margin-top:17px}
  .num{flex:none;width:48px;height:48px;border-radius:50%;background:${t.main};color:#fff;font-weight:800;font-size:28px;display:flex;align-items:center;justify-content:center;margin-top:2px}
  .cols{display:flex;gap:36px}.col{flex:1;background:${t.soft};border-radius:24px;padding:28px 30px}.col li{font-size:29px}
  .foot{position:absolute;left:72px;right:72px;bottom:28px;display:flex;justify-content:space-between;font-size:21px;color:${t.sub}}
  </style></head><body><div class="card">${body}<div class="foot"><span>${esc(CLINIC)}</span><span>${idx} / ${total}</span></div></div></body></html>`;
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 1 });
for (let i = 0; i < spec.cards.length; i++) {
  await page.setContent(html(spec.cards[i], i + 1, spec.cards.length), { waitUntil: 'load' });
  const file = path.join(outDir, String(i + 1).padStart(2, '0') + '.png');
  await page.screenshot({ path: file });
}
await browser.close();
console.log(`✅ ${spec.cards.length}장 생성: ${outDir}`);
