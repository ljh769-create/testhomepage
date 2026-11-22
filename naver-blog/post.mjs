/* eslint-disable no-console */
/**
 * 2단계: 저장된 세션으로 네이버 블로그 글쓰기 에디터에 제목·본문 자동 입력
 * ----------------------------------------------------------------------------
 * 기본 동작은 "채워만 두고 멈춤" — 사장님이 브라우저에서 직접 확인하고
 * 이미지 넣고 '발행' 버튼을 누르는 반자동 방식입니다. (가장 안전)
 *
 * 실행 예:
 *   npm run login                       # 최초 1회(또는 세션 만료 시) 로그인
 *   npm run post -- --slug=color-sense-test
 *   npm run post -- --file=/경로/글.md
 *   npm run post -- --slug=color-sense-test --publish   # (실험적) 발행까지 시도
 *
 * 옵션:
 *   --slug=<이름>   src/content/blog/<이름>.md 를 사용
 *   --file=<경로>   임의의 .md 파일 사용
 *   --blogId=<id>   블로그 아이디(필수, 또는 환경변수 NAVER_BLOG_ID)
 *   --publish       발행 버튼까지 자동 클릭 시도(실험적, 실패 가능)
 *
 * 에디터(스마트에디터 ONE)는 네이버가 수시로 바꿉니다. 셀렉터가 안 맞아
 * 실패하면, 그 시점 브라우저는 열린 채 멈추니 화면을 캡처해서 알려주세요.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import fs from 'fs';
import path from 'path';
import readline from 'readline';
import { parseMarkdown, toHtml, pasteHtml, fillBodyWithImages, componentOrder } from './md.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SESSION = path.join(__dirname, 'naver-session.json');
const BLOG_DIR = path.join(__dirname, 'posts');   // 원고 폴더: posts/<이름>.md

/* ---------- 인자 파싱 ---------- */
const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  return m ? [m[1], m[2] === undefined ? true : m[2]] : [a, true];
}));
const blogId = args.blogId || process.env.NAVER_BLOG_ID;
if (!blogId) { console.error('❌ 블로그 아이디가 필요합니다: --blogId=<아이디> 또는 환경변수 NAVER_BLOG_ID'); process.exit(1); }
const doPublish = !!args.publish;

/* ---------- 글 파일 찾기 ---------- */
let mdPath = args.file;
if (!mdPath && args.slug) mdPath = path.join(BLOG_DIR, `${args.slug}.md`);
if (!mdPath || !fs.existsSync(mdPath)) {
  console.error('❌ 글 파일을 찾을 수 없습니다.');
  try {
    const list = fs.readdirSync(BLOG_DIR).filter((f) => f.endsWith('.md')).map((f) => f.replace(/\.md$/, ''));
    console.error('   사용 가능한 --slug 목록:\n   - ' + list.join('\n   - '));
  } catch (e) { /* ignore */ }
  process.exit(1);
}
if (!fs.existsSync(SESSION)) {
  console.error('❌ 세션이 없습니다. 먼저 `npm run login` 으로 로그인하세요.');
  process.exit(1);
}

/* ---------- 마크다운 → 제목 + 본문(평문) ---------- */
function fmArray(fm, key) {
  const mm = fm.match(new RegExp(`^${key}:\\s*(.*)$`, 'm'));
  if (!mm) return [];
  const v = mm[1].trim();
  if (v.startsWith('[') && v.endsWith(']')) {
    return v.slice(1, -1).split(',').map((s) => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
  }
  return v ? [v] : [];
}
function parse(md) {
  const m = md.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  const fm = m ? m[1] : '';
  const body = m ? m[2] : md;
  const titleMatch = fm.match(/^title:\s*(.*)$/m);
  const title = titleMatch ? titleMatch[1].trim().replace(/^["']|["']$/g, '') : (args.slug || 'untitled');
  const tags = fmArray(fm, 'tags');
  const relatedApps = fmArray(fm, 'relatedApps');
  const text = body
    .replace(/^!\[[^\]]*\]\([^)]*\)[ \t]*\n(?:\*[^*\n][^\n]*\*[ \t]*\n)?/gm, '') // 자사 블로그용 이미지 줄+캡션 제거(네이버는 images/<slug>/ 로 올림)
    .replace(/^#{1,6}\s+/gm, '')                 // 헤딩 기호 제거
    .replace(/\*\*(.+?)\*\*/g, '$1')             // 굵게
    .replace(/\*(.+?)\*/g, '$1')                 // 기울임
    .replace(/`([^`]+)`/g, '$1')                 // 인라인 코드
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)') // 링크 → 텍스트 (url)
    .replace(/^>\s?/gm, '')                       // 인용
    .replace(/^[-*]\s+/gm, '• ')                  // 불릿
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return { title, text, tags, relatedApps };
}
const slug = args.slug || path.basename(mdPath, '.md');
const { title, text, tags, relatedApps } = parse(fs.readFileSync(mdPath, 'utf8'));

/* 앱 카탈로그 로드 (링크·스크린샷용) */
let mobileApps = [];
try { mobileApps = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', '..', 'src', 'data', 'apps.json'), 'utf8')).mobileApps; } catch (e) { /* */ }
const relApps = relatedApps.map((k) => mobileApps.find((x) => x.icon === k)).filter(Boolean);

/* 앱 설치 링크를 본문 끝에 자동 추가 (홍보 목적) — 안드로이드/iOS 각각 */
let finalText = text;
// 앱당 설치링크 1개만(안드로이드·아이폰 통합, 깨끗한 URL이라 자동링크됨). URL 줄 수를 최소화해 병합 지점을 줄임.
const appBlocks = relApps.map((a) => {
  const link = a.installPath ? `https://hasegi.co.kr${a.installPath}` : (a.playUrl || a.appleUrl || '');
  return link ? `▪ ${a.name} (무료): ${link}` : null;
}).filter(Boolean);
// 링크마다 뒤에 빈 줄 하나씩(줄바꿈 안정 + 가독성). 이미지는 이 뒤(맨 끝)에 붙음.
const appTail = appBlocks.length
  ? `\n📱 소개한 앱 — 무료 설치 (안드로이드·아이폰)\n\n${appBlocks.join('\n\n')}\n\n더 많은 앱: https://hasegi.co.kr/projects/`
  : '';
finalText += appTail;

// 본문 서식용 HTML (소제목 굵게 19px·기울임·문단 여백)
// 이미지 줄(![](..))이 있고 images/<slug>/ 의 사진 수와 같으면 본문 속 그 자리에 올린다(아래 inlineImages).
// 아니면 예전처럼 글 맨 끝에 한꺼번에 올리므로, 그때는 이미지 캡션도 본문에서 뺀다.
const blocks = parseMarkdown(mdPath);
const imgBlocks = blocks.filter((b) => b.kind === 'image');
const bodyHtml = toHtml(blocks.filter((b) => b.kind !== 'caption'));

console.log(`\n📝 글: ${title}\n   본문 ${finalText.length}자 · 태그 ${tags.length}개 · 앱 ${appBlocks.length}개\n`);

/* ---------- 구글플레이 스크린샷 추출 ---------- */
async function playScreenshots(pkg, max = 3) {
  try {
    const res = await fetch(`https://play.google.com/store/apps/details?id=${pkg}&hl=ko&gl=kr`, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    const html = await res.text();
    const cut = html.search(/비슷한 앱|유사한 앱|Similar apps/);
    const head = cut > 0 ? html.slice(0, cut) : html;
    const urls = [...head.matchAll(/https:\/\/play-lh\.googleusercontent\.com\/[A-Za-z0-9_-]+=w\d+-h\d+[^"\\ ]*/g)].map((m) => m[0]);
    const seen = new Set(); const shots = [];
    for (const u of urls) {
      const w = +(u.match(/=w(\d+)/) || [])[1];
      const base = u.split('=')[0];
      if (u.includes('-pc0xffffff')) continue;      // 피처그래픽(배너) 제외
      if (w >= 500 && !seen.has(base)) { seen.add(base); shots.push(base + '=w1080'); } // 원본 큰 사이즈
    }
    return shots.slice(0, max);
  } catch (e) { return []; }
}
async function download(url, dest) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(dest, buf);
}

/* ---------- 이미지 준비: images/<slug>/ (없으면 플레이 스크린샷 → 없으면 아이콘) ---------- */
async function prepareImages() {
  const dir = path.join(__dirname, 'images', slug);
  fs.mkdirSync(dir, { recursive: true });
  let files = fs.readdirSync(dir).filter((f) => /\.(png|jpe?g|webp)$/i.test(f)).sort().map((f) => path.join(dir, f));
  if (files.length) return { dir, files };            // 이미 사진이 있으면 그대로(폰 스크린샷 우선)

  const iconDir = path.resolve(__dirname, '..', '..', 'public', 'app-icons');
  // 앱이 많으면 이미지 총량이 과해짐 → 앱당 장수 상한(1앱=3, 2앱=2, 3+앱=1)
  const perApp = relApps.length <= 1 ? 3 : relApps.length === 2 ? 2 : 1;
  for (const a of relApps) {
    const pkg = (a.playUrl || '').match(/id=([^&]+)/)?.[1];
    let got = 0;
    if (pkg) {
      const shots = await playScreenshots(pkg, perApp);
      for (let i = 0; i < shots.length; i++) {
        try { const dst = path.join(dir, `${a.icon}-${i + 1}.png`); await download(shots[i], dst); files.push(dst); got++; } catch (e) { /* */ }
      }
    }
    if (!got) { // 스크린샷 실패 시 아이콘 폴백
      const src = path.join(iconDir, `${a.icon}.png`);
      if (fs.existsSync(src)) { const dst = path.join(dir, `${a.icon}.png`); fs.copyFileSync(src, dst); files.push(dst); }
    } else {
      console.log(`🖼️ ${a.name} 구글플레이 스크린샷 ${got}장 내려받음`);
    }
  }
  if (files.length) console.log(`   (images/${slug}/ 에 저장 — 폰 스크린샷을 넣으면 다음부터 그게 우선 사용됩니다)`);
  return { dir, files };
}
const IMG = await prepareImages();
const inlineImages = !args['no-images'] && imgBlocks.length > 0 && IMG.files.length === imgBlocks.length;
let inlineDone = false;
if (imgBlocks.length && !inlineImages && !args['no-images']) {
  console.log(`⚠️ 원고 이미지 ${imgBlocks.length}개 ≠ images/${slug}/ 사진 ${IMG.files.length}장 — 본문 속 위치 삽입 대신 글 맨 끝에 올립니다.`);
}

function waitForEnter(msg) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(msg, () => { rl.close(); resolve(); });
  });
}
async function firstWorking(scope, selectors, timeout = 4000) {
  for (const sel of selectors) {
    try {
      const el = scope.locator(sel).first();
      await el.waitFor({ state: 'visible', timeout });
      return el;
    } catch (e) { /* 다음 셀렉터 시도 */ }
  }
  return null;
}

/* ---------- 실행 ---------- */
/* 네이버는 자동화 브라우저를 감지하면 로그인·글쓰기를 막는다(2026-09-23 확인).
   그래서 login.mjs 와 "같은 고정 프로필 + 실제 크롬" 으로 띄운다.
   프로필이 아직 없으면 예전 방식(저장 세션)으로 폴백한다. */
const PROFILE = path.join(__dirname, '.chrome-profile');
const LAUNCH = {
  headless: false,
  locale: 'ko-KR',
  viewport: null,
  permissions: ['clipboard-read', 'clipboard-write'],
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
  ignoreDefaultArgs: ['--enable-automation'],
};
let ctx;
if (fs.existsSync(PROFILE)) {
  try {
    ctx = await chromium.launchPersistentContext(PROFILE, { ...LAUNCH, channel: 'chrome' });
  } catch {
    ctx = await chromium.launchPersistentContext(PROFILE, LAUNCH);
  }
} else {
  const b = await chromium.launch({ headless: false, args: LAUNCH.args, ignoreDefaultArgs: LAUNCH.ignoreDefaultArgs });
  ctx = await b.newContext({ storageState: SESSION, locale: 'ko-KR', permissions: ['clipboard-read', 'clipboard-write'] });
}
await ctx.addInitScript(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
});
const browser = { close: () => ctx.close() };
const MOD = process.platform === 'darwin' ? 'Meta' : 'Control';
const page = ctx.pages()[0] ?? (await ctx.newPage());

console.log('→ 글쓰기 에디터 여는 중...');
await page.goto(`https://blog.naver.com/${blogId}?Redirect=Write`, { waitUntil: 'domcontentloaded' });

// 로그인 만료 감지
if (/nid\.naver\.com/.test(page.url())) {
  console.error('❌ 세션이 만료된 것 같습니다. `npm run login` 으로 다시 로그인하세요.');
  await browser.close();
  process.exit(1);
}

// 에디터는 iframe(#mainFrame) 안에 있음
let frame = page;
try {
  const fEl = await page.waitForSelector('iframe#mainFrame', { timeout: 8000 });
  frame = await fEl.contentFrame();
  console.log('→ 에디터 iframe 진입');
} catch (e) {
  console.log('⚠️ mainFrame 을 못 찾음 — 페이지 자체에서 시도합니다.');
}

/* 에디터 위에 뜨는 것들을 닫는다 — 복구 알림 / 코치마크 / **우측 도움말 측면시트**.
   ※ 측면시트는 iframe 밖(page)에 붙는 경우가 있다. frame 안에서만 찾다가 안 닫혀서
      사람이 매번 우상단 X 를 눌러야 했다(2026-09-15). 그래서 frame·page 양쪽을 훑는다. */
const OVERLAY_SEL = [
  '.se-popup-alert-confirm .se-popup-button-cancel',
  '.se-popup-button-cancel',
  '.se-popup-alert button:has-text("취소")',
  // 도움말 측면시트 — 우측에서 밀려 나오고 우상단에 X 가 있다
  '.se-help-panel-close', '.se-help-close', 'button.se-help-close',
  '.se-sidebar-close', '.se-panel-close', '.se-help-panel button[class*="close"]',
  '[class*="help"] button[class*="close"]',
  '[class*="Help"] button[class*="close"]',
  '[class*="sidebar"] button[class*="close"]',
  '[class*="side_panel"] button[class*="close"]',
  '[class*="sidePanel"] button[class*="close"]',
  'button[aria-label="닫기"]', 'button[aria-label*="닫기"]', 'button[title*="닫기"]',
  '.container__HW_tc button',
];
async function dismissOverlays(label) {
  for (let i = 0; i < 4; i++) {
    let acted = false;
    for (const scope of [frame, page]) {
      for (const sel of OVERLAY_SEL) {
        try {
          const el = scope.locator(sel).first();
          if (await el.isVisible({ timeout: 300 }).catch(() => false)) {
            await el.click({ force: true }).catch(() => {});
            acted = true; await page.waitForTimeout(350);
          }
        } catch (e) { /* */ }
      }
    }
    try { await page.keyboard.press('Escape'); } catch (e) { /* */ }
    if (!acted) break;
    await page.waitForTimeout(300);
  }
  if (label) console.log(label);
}

/* 그래도 우측에 큰 패널이 남아 있으면 정체를 찍어 둔다 — 다음 실행에 선택자를 확정하려고. */
async function reportStuckPanel() {
  for (const [where, scope] of [['iframe', frame], ['page', page]]) {
    try {
      const found = await scope.evaluate(() => {
        const out = [];
        document.querySelectorAll('div,aside,section').forEach((el) => {
          const r = el.getBoundingClientRect();
          const st = getComputedStyle(el);
          if (r.width > 200 && r.width < 700 && r.height > 300
              && r.right > window.innerWidth - 40 && r.left > window.innerWidth * 0.4
              && st.display !== 'none' && st.visibility !== 'hidden') {
            out.push(`${el.tagName}.${(el.className || '').toString().trim().slice(0, 80)} ${Math.round(r.width)}x${Math.round(r.height)}`);
          }
        });
        return out.slice(0, 4);
      });
      if (found && found.length) {
        console.log(`⚠️ 우측에 안 닫힌 패널 (${where}):`);
        found.forEach((s) => console.log('     ' + s));
      }
    } catch (e) { /* */ }
  }
}

await page.waitForTimeout(1500);
// 복구 팝업("이어서 작성?")은 로드 몇 초 뒤에 뜰 수 있으므로, 뜰 때까지 ~9초간 끈질기게 폴링하며 취소.
{
  let cancelled = false;
  for (let i = 0; i < 18; i++) {
    for (const scope of [frame, page]) {
      for (const sel of OVERLAY_SEL) {
        try {
          const el = scope.locator(sel).first();
          if (await el.isVisible({ timeout: 150 }).catch(() => false)) {
            await el.click({ force: true }).catch(() => {});
            if (/cancel|취소/.test(sel)) cancelled = true;
            await page.waitForTimeout(350);
          }
        } catch (e) { /* */ }
      }
    }
    await page.waitForTimeout(300);
  }
  console.log(cancelled ? '→ 이전 글 복구 팝업: 취소(새 글로 시작)' : '→ 팝업·측면시트 정리 완료');
  await reportStuckPanel();
}
await page.waitForTimeout(500);

/* 제목 입력 */
const titleEl = await firstWorking(frame, [
  '.se-section-documentTitle .se-text-paragraph',
  '.se-documentTitle .se-text-paragraph',
  '.se-placeholder__document-title',
  'span.se-placeholder',
]);
if (titleEl) {
  try {
    await titleEl.click({ force: true });
    await page.waitForTimeout(250);
    await page.keyboard.type(title, { delay: 15 });
    await page.waitForTimeout(300);
    // 실제 제목 내용이 들어갔는지 검증 → 안 됐으면 재시도(간헐적 포커스/팝업 실패 대응)
    const probe = title.slice(0, 8);
    let landed = await titleEl.evaluate((el, p) => (el.innerText || '').includes(p), probe).catch(() => true);
    if (!landed) {
      const t2 = await firstWorking(frame, ['.se-section-documentTitle .se-text-paragraph', '.se-documentTitle .se-text-paragraph'], 2000);
      if (t2) { await t2.click({ force: true }); await page.waitForTimeout(500); await page.keyboard.type(title, { delay: 15 }); await page.waitForTimeout(400); }
      landed = await titleEl.evaluate((el, p) => (el.innerText || '').includes(p), probe).catch(() => true);
    }
    console.log(landed ? '✅ 제목 입력 완료' : '⚠️ 제목 입력 실패 — 직접 입력 필요');
  } catch (e) { console.log('⚠️ 제목 입력 실패:', e.message.split('\n')[0]); }
} else {
  console.log('⚠️ 제목 입력칸을 못 찾음 — 브라우저에서 직접 제목을 넣어주세요.');
}

/* 본문 입력 — 기사 → 이미지 → 앱링크 순서 */
// 한 줄씩 입력(URL 줄은 실제 타이핑+변환대기, 나머지 insertText). leadingEnter: 시작 전 Enter로 구분.
async function typeLines(str, leadingEnter) {
  if (leadingEnter) { await page.keyboard.press('Enter'); await page.waitForTimeout(80); }
  const lines = str.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    const isUrl = /https?:\/\//.test(ln);
    // URL 줄은 실제 타이핑(인라인 자동링크 인식) + 변환대기, 나머지는 빠른 insertText.
    if (ln) {
      if (isUrl) { await page.keyboard.type(ln, { delay: 2 }); await page.waitForTimeout(850); }
      else await page.keyboard.insertText(ln);
    }
    if (i < lines.length - 1 || isUrl) { await page.keyboard.press('Enter'); await page.waitForTimeout(isUrl ? 500 : 60); }
  }
}
// 이미지 삽입: 파일선택창을 전역 핸들러로 가로채 여러 장 한 번에(네이티브 Finder 안 뜸). 커서 위치에 삽입됨.
async function insertImages() {
  if (!IMG.files.length || args['no-images']) return;
  console.log(`→ 이미지 ${IMG.files.length}장 삽입(한 장씩 = 배치선택창 없이 세로 배치)...`);
  // 한 장씩 올림: 여러 장 동시 업로드 시 네이버가 "배치 유형" 선택창을 띄우므로 회피.
  const queue = [...IMG.files];
  const chooserHandler = async (chooser) => {
    const f = queue.shift();
    try { await chooser.setFiles(f ? [f] : []); } catch (e) { /* */ }
  };
  page.on('filechooser', chooserHandler);
  const imgBtn = await firstWorking(frame, [
    'button.se-toolbar-button-image', 'button[data-name="image"]', 'button[data-log="dot.image"]',
    '.se-toolbar-item-image button', 'button:has-text("사진")',
  ], 4000);
  if (imgBtn) {
    for (let k = 0; k < IMG.files.length; k++) {
      await imgBtn.click({ force: true }).catch(() => {});
      await page.waitForTimeout(2800); // 각 이미지 업로드·삽입 대기
      console.log(`   🖼️ ${k + 1}/${IMG.files.length}`);
    }
  } else console.log('⚠️ 이미지 버튼을 못 찾음 — 이미지는 직접 넣어주세요. (폴더:', IMG.dir, ')');
  page.off('filechooser', chooserHandler);
}

// 장소(지도) 삽입: --map="검색어" 일 때. 본문 맨 끝에 네이버 지도 컴포넌트를 넣는다. 실패해도 발행 흐름은 계속.
async function insertPlaceMap(query) {
  try {
    console.log(`→ 지도 삽입 시도: ${query}`);
    const last = frame.locator('.se-component.se-text .se-text-paragraph').last();
    await last.click({ force: true }); await page.keyboard.press(`${MOD}+End`); await page.keyboard.press('Enter');
    const btn = await firstWorking(frame, [
      'button.se-toolbar-button-map', 'button[data-name="map"]', 'button[data-log="dot.map"]',
      '.se-toolbar-item-map button', 'button:has-text("장소")',
    ], 4000);
    if (!btn) throw new Error('장소 버튼을 못 찾음');
    await btn.click({ force: true }); await page.waitForTimeout(1500);
    const input = await firstWorking(frame, ['input[placeholder*="장소"]', 'input[placeholder*="검색"]', '.se-popup-map input', 'input[type="text"]'], 5000);
    if (!input) throw new Error('장소 검색칸을 못 찾음');
    await input.click(); await input.fill(query); await page.keyboard.press('Enter'); await page.waitForTimeout(2500);
    const item = await firstWorking(frame, ['.se-map-search-result li button', '.se-popup-map li button', '[class*="map"] li button', '[class*="place"] li button', 'li:has-text("노량진") button'], 5000);
    if (!item) throw new Error('검색 결과를 못 찾음');
    await item.click({ force: true }); await page.waitForTimeout(1000);
    const ok = await firstWorking(frame, ['button:has-text("추가")', 'button:has-text("확인")', '.se-popup-button-confirm'], 4000);
    if (!ok) throw new Error('추가 버튼을 못 찾음');
    await ok.click({ force: true }); await page.waitForTimeout(2500);
    const has = await frame.evaluate(() => !!document.querySelector('.se-component.se-placesMap, .se-module-map, [class*="placesMap"]'));
    console.log(has ? '✅ 지도 삽입 완료' : '⚠️ 지도 삽입 여부 불확실 — 화면 확인');
  } catch (e) { console.log('⚠️ 지도 삽입 실패:', String(e.message).slice(0, 80), '— 장소 버튼으로 직접 넣어주세요'); }
}

const bodyEl = await firstWorking(frame, [
  '.se-component.se-text .se-text-paragraph',
  '.se-section-text .se-text-paragraph',
  '.se-content .se-text-paragraph',
]);
if (bodyEl) {
  try {
    await bodyEl.click({ force: true });
    await page.waitForTimeout(200);
    // 본문은 HTML 붙여넣기로 서식(소제목 굵게·기울임·문단 여백)까지 한 번에 넣는다.
    // 키보드 토글(Cmd+B)로 넣으면 에디터가 Enter·툴바 클릭에서 서식을 초기화해 들쭉날쭉해진다.
    let pasted = false;
    try {
      if (inlineImages) {
        const r = await fillBodyWithImages(page, frame, blocks, IMG.files, MOD);
        inlineDone = r.placed > 0;                      // 일부라도 올라갔으면 끝에 다시 올리지 않는다
        console.log(`→ 사진 ${r.placed}/${imgBlocks.length}장을 본문 속 위치에 삽입 · 구성: ${await componentOrder(frame)}`);
      } else {
        await pasteHtml(page, frame, bodyHtml, text, MOD);
      }
      const html = await frame.$eval('.se-content', (e) => e.innerHTML);
      pasted = /<(b|strong)\b/i.test(html) || /font-weight\s*:\s*(bold|[6-9]00)/i.test(html);
      console.log(pasted ? '✅ 서식 본문 붙여넣기 완료' : '⚠️ 서식이 안 붙음 — 평문 입력으로 대체');
    } catch (e) { console.log('⚠️ 붙여넣기 실패:', e.message.split('\n')[0]); }

    if (!pasted) {
      await bodyEl.click({ force: true }); await page.waitForTimeout(400);
      await typeLines(text);
    }

    // 앱 설치 링크는 자동링크가 걸려야 하므로 타이핑으로 이어 붙인다
    if (appTail) {
      await page.keyboard.press('Enter');
      await typeLines(appTail);
    }

    // 본문이 실제로 들어갔는지 검증 → 안 들어갔으면(이미지만 되던 문제) 재클릭 후 재입력
    const bodyLanded = await frame.evaluate(() => ((document.querySelector('.se-component.se-text, .se-content') || document.body).innerText || '').replace(/\s/g, '').length > 80).catch(() => true);
    if (!bodyLanded) {
      console.log('⚠️ 본문 미입력 감지 — 재시도');
      await bodyEl.click({ force: true }); await page.waitForTimeout(500);
      await typeLines(finalText);
    }
    if (!inlineDone) await insertImages();
    if (typeof args.map === 'string' && args.map) await insertPlaceMap(args.map);
    // 포커스를 제목으로 옮겨 URL 자동링크 확정
    try {
      const t = frame.locator('.se-section-documentTitle .se-text-paragraph, .se-documentTitle .se-text-paragraph').first();
      await t.click({ force: true, timeout: 2000 });
      await page.waitForTimeout(600);
    } catch (e) { /* */ }
    // 줄 병합 자체 검증
    try {
      // 한 문단(.se-text-paragraph) 안에 URL이 2개 이상이면 = 실제 줄 병합
      const merged = await frame.evaluate(() => [...document.querySelectorAll('.se-text-paragraph')]
        .some((p) => ((p.innerText || '').match(/https?:\/\//g) || []).length >= 2));
      // 링크가 카드로 변환되면 URL 텍스트가 사라지므로, 도메인/앱이름/href 로도 폭넓게 확인(오탐 감소)
      const hasFooter = await frame.evaluate(() => {
        const root = document.querySelector('.se-content') || document.body;
        const txt = root.innerText || '';
        const hrefs = [...root.querySelectorAll('a')].map((a) => a.getAttribute('href') || a.href || '').join(' ');
        return /hasegi\.co\.kr|소개한 앱/.test(txt) || /hasegi\.co\.kr|apps\.apple|play\.google/.test(hrefs);
      });
      console.log(merged ? '⚠️ 줄 병합 의심 — 발행 전 그 줄만 Enter로 분리하세요' : '✅ 줄바꿈/링크 OK');
      console.log(hasFooter ? '✅ 앱 링크 포함됨' : '⚠️ 앱 링크 누락 — 확인 필요');
    } catch (e) { console.log('✅ 본문 입력 완료'); }
  } catch (e) { console.log('⚠️ 본문 입력 실패:', e.message.split('\n')[0]); }
} else {
  console.log('⚠️ 본문 입력칸을 못 찾음 — 브라우저에서 직접 본문을 붙여주세요.');
}

/* ---------- 발행 팝업: 카테고리 선택 + 태그 입력 ----------
   태그는 붙여넣으면 띄어쓰기가 뭉치므로 반드시 한 개씩 치고 Enter 로 확정한다.
   확장 태그는 tags/<slug>.txt 가 있으면 그것을 쓴다(원고 프론트매터를 건드리면
   자사 블로그 표시까지 바뀌므로 발행용으로만 분리해 둔다).
   발행 버튼은 --publish 없이는 누르지 않는다 — 최종 확인은 사람이 한다. */
const extraPath = args.slug ? path.join(__dirname, 'tags', `${args.slug}.txt`) : null;
let finalTags = tags;
if (extraPath && fs.existsSync(extraPath)) {
  const fromFile = fs.readFileSync(extraPath, 'utf8').split('\n')
    .map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));
  if (fromFile.length) {
    finalTags = [...new Set(fromFile)].slice(0, 30);   // 네이버 상한 30개
    console.log(`→ 확장 태그 사용: tags/${args.slug}.txt (${finalTags.length}개)`);
  }
}
const wantCategory = typeof args.category === 'string' ? args.category.trim() : null;

if (wantCategory || finalTags.length) {
  try {
    await dismissOverlays();
    const openBtn = await firstWorking(frame,
      ['button[data-click-area="tpb.publish"]', 'button.publish_btn__m9KHH', 'button:has-text("발행")'], 6000);
    if (!openBtn) throw new Error('발행 팝업 버튼을 못 찾음');
    await openBtn.click({ force: true });
    await page.waitForTimeout(1800);

    if (wantCategory) {
      const sel = await firstWorking(frame,
        ['button.selectbox_button__jb1Dt', '[class*="selectbox_button"]', 'button:has-text("카테고리")'], 4000);
      if (sel) {
        await sel.click();
        await page.waitForTimeout(700);
        const opt = await firstWorking(frame,
          [`label:has-text("${wantCategory}")`, `span:text-is("${wantCategory}")`,
           `[class*="option"] :text-is("${wantCategory}")`], 3500);
        if (opt) { await opt.click(); console.log(`✅ 카테고리 지정: ${wantCategory}`); }
        else console.log(`⚠️ 카테고리 「${wantCategory}」를 목록에서 못 찾음 — 직접 골라주세요.`);
      } else console.log('⚠️ 카테고리 선택칸을 못 찾음 — 직접 골라주세요.');
    }

    if (finalTags.length) {
      const tagBox = await firstWorking(frame,
        ['#tag-input', 'input[placeholder*="태그"]', '[class*="tag_input"] input', '.tag_input__rvUB5'], 4000);
      if (tagBox) {
        let put = 0;
        for (const t of finalTags) {
          await tagBox.click();
          await tagBox.type(t, { delay: 45 });
          await page.waitForTimeout(160);
          await page.keyboard.press('Enter');     // 한 개씩 확정 — 붙여넣으면 뭉친다
          await page.waitForTimeout(220);
          put += 1;
        }
        console.log(`✅ 태그 ${put}개 입력 완료`);
      } else console.log('⚠️ 태그 입력칸을 못 찾음 — 아래 목록을 직접 넣어주세요.');
    }
  } catch (e) {
    console.log('⚠️ 발행 팝업 자동화 실패:', e.message.split('\n')[0], '— 직접 넣어주세요.');
  }
}

/* --publish 시에만 발행까지 자동 시도(실험적). */
if (doPublish) {
  try {
    console.log('→ (실험적) 발행 시도...');
    await dismissOverlays();
    // 카테고리·태그 단계에서 발행 팝업이 이미 열려 있으면 위쪽 「발행」을 다시 누르면 팝업이 닫힌다.
    // 그래서 팝업 안의 최종 버튼을 먼저 찾고, 없을 때만 팝업을 연다.
    const FINAL = ['button[data-testid="seOnePublishBtn"]', 'button[class*="confirm_btn"]', '[class*="layer_btn_area"] button:has-text("발행")'];
    let p2 = await firstWorking(frame, FINAL, 2500);
    if (!p2) {
      const p1 = await firstWorking(frame, ['button[data-click-area="tpb.publish"]', 'button.publish_btn__m9KHH', 'button:has-text("발행")'], 5000);
      if (p1) { await p1.click({ force: true }); await page.waitForTimeout(2500); }
      p2 = await firstWorking(frame, FINAL, 4000);
    }
    if (p2) {
      const before = page.url();
      await p2.click();
      await page.waitForTimeout(6000);
      const after = page.url();
      console.log(after !== before && !/postwrite|Redirect=Write/i.test(after)
        ? `✅ 발행 완료 — ${after}` : `⚠️ 발행 버튼을 눌렀으나 주소가 그대로 — 브라우저에서 확인 (${after})`);
    } else {
      const names = await frame.locator('button').evaluateAll((bs) => bs.filter((b) => /발행/.test(b.textContent || ''))
        .map((b) => `${b.className}|${b.getAttribute('data-testid') || ''}|${(b.textContent || '').trim()}`));
      console.log('⚠️ 최종 발행 버튼 못 찾음 — 직접 눌러주세요. 「발행」 단추 후보:', JSON.stringify(names));
    }
  } catch (e) { console.log('⚠️ 자동 발행 실패:', e.message.split('\n')[0], '— 직접 발행해주세요.'); }
}

if (finalTags.length) {
  console.log('\n🏷️  태그 (자동 입력됨 — 팝업에서 확인하세요):');
  console.log('   ' + finalTags.map((t) => '#' + t).join(' '));
}
console.log('🖼️  이미지 폴더 (여기에 폰 스크린샷을 넣으면 다음부터 자동 업로드):');
console.log('   ' + IMG.dir);

console.log('\n────────────────────────────────────────────');
console.log('  발행 팝업이 열려 있고 카테고리·태그까지 채워져 있습니다.');
console.log('  내용을 확인한 뒤 직접 "발행" 버튼을 누르세요.');
console.log('  (발행 클릭만 사람 몫입니다)');
console.log('────────────────────────────────────────────\n');
if (args.close) {
  console.log('(--close: 6초 후 자동으로 닫습니다)');
  await page.waitForTimeout(6000);
} else {
  await waitForEnter('다 끝냈으면 Enter 를 눌러 브라우저를 닫습니다... ');
}
await browser.close();
process.exit(0);
