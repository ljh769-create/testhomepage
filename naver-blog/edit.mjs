/* eslint-disable no-console */
/**
 * 이미 발행된 글의 본문을 새 원고로 교체 (로컬 전용)
 * ----------------------------------------------------------------------------
 * 좋아요·댓글·조회수·URL 은 그대로 유지됩니다. 삭제가 아니라 수정입니다.
 *
 *   node edit.mjs --logNo=224374232825 --slug=novel-ghostwriter-01
 *
 * 소제목(굵게·19px)·굵게·기울임·문단 여백을 HTML 붙여넣기로 한 번에 넣습니다.
 * 제목·카테고리·태그는 건드리지 않고, 최종 "발행"은 사람이 누릅니다.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import { parseMarkdown, toHtml, toPlain, pasteHtml, summary, resolveMd, fillBodyWithImages, componentOrder } from './md.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SESSION = path.join(__dirname, 'naver-session.json');
const BLOG_DIR = path.join(__dirname, 'posts');   // 원고 폴더: posts/<이름>.md

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  return m ? [m[1], m[2] ?? true] : [a, true];
}));
const blogId = args.blogId || process.env.NAVER_BLOG_ID;
if (!blogId) { console.error('❌ 블로그 아이디가 필요합니다: --blogId=<아이디> 또는 환경변수 NAVER_BLOG_ID'); process.exit(1); }
const { logNo, slug } = args;

if (!logNo || !slug) { console.error('사용법: node edit.mjs --logNo=<글번호> --slug=<md파일명>'); process.exit(1); }
if (!fs.existsSync(SESSION)) { console.error('❌ 세션 없음. `npm run login` 먼저.'); process.exit(1); }

const blocks = parseMarkdown(resolveMd(BLOG_DIR, slug));
// 원고의 이미지 줄 수와 images/<slug>/ 사진 수가 같으면 본문 속 그 자리에 올린다. 아니면 이미지·캡션 없이 글만 교체.
const imgDir = path.join(__dirname, 'images', slug);
const imgFiles = fs.existsSync(imgDir)
  ? fs.readdirSync(imgDir).filter((f) => /\.(png|jpe?g|webp)$/i.test(f)).sort().map((f) => path.join(imgDir, f)) : [];
const imgBlocks = blocks.filter((b) => b.kind === 'image');
const inlineImages = imgBlocks.length > 0 && imgFiles.length === imgBlocks.length;
const textBlocks = inlineImages ? blocks : blocks.filter((b) => b.kind !== 'caption');
const html = toHtml(textBlocks);
const plain = toPlain(textBlocks);
console.log(`\n📝 ${slug} → 글번호 ${logNo}`);
console.log(`   ${summary(blocks)} · 이미지 ${imgBlocks.length}개(${inlineImages ? '본문 속 위치에 삽입' : '삽입 안 함'})\n`);

// post.mjs 와 같은 방식: 실제 크롬 + 고정 프로필(login.mjs 가 로그인해 둔 곳). 네이버는 자동화 크로미움을 막는다.
const PROFILE = path.join(__dirname, '.chrome-profile');
const LAUNCH = {
  headless: false, locale: 'ko-KR', viewport: null,
  permissions: ['clipboard-read', 'clipboard-write'],
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
  ignoreDefaultArgs: ['--enable-automation'],
};
let ctx;
try { ctx = await chromium.launchPersistentContext(PROFILE, { ...LAUNCH, channel: 'chrome' }); }
catch { ctx = await chromium.launchPersistentContext(PROFILE, LAUNCH); }
await ctx.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
const browser = { close: () => ctx.close() };
const page = ctx.pages()[0] ?? (await ctx.newPage());
page.on('dialog', async (d) => { await d.accept().catch(() => {}); });

console.log('→ 수정 화면 여는 중...');
await page.goto(`https://blog.naver.com/PostWriteForm.naver?blogId=${blogId}&logNo=${logNo}&Redirect=Update`, { waitUntil: 'domcontentloaded' });
if (/nid\.naver\.com/.test(page.url())) {
  console.error('❌ 세션이 만료됐습니다. `npm run login` 후 다시 시도하세요.');
  await browser.close(); process.exit(1);
}
await page.waitForTimeout(6000);

let frame = page;
const fEl = await page.$('iframe#mainFrame');
if (fEl) { const f = await fEl.contentFrame(); if (f && await f.$('.se-content')) { frame = f; console.log('→ iframe 진입'); } }
if (!(await frame.$('.se-content'))) { console.error('❌ 에디터를 못 찾았습니다.'); await browser.close(); process.exit(1); }

const before = await frame.$eval(".se-content", (e) => (e.innerText || "").length);
console.log(`→ 기존 본문 ${await frame.$eval('.se-content', (e) => (e.innerText || '').length)}자`);

// 전체 선택한 채로 붙여넣으면 에디터가 "선택 시작 지점의 서식"을 새 내용 전체에 입힌다.
// 기존 첫 줄이 기울임이면 본문 전체가 기울어진다. 그래서 ①지우고 ②서식을 끈 뒤 ③붙인다.
const mod = process.platform === 'darwin' ? 'Meta' : 'Control';
const editor = await frame.$('.se-content');

console.log('→ 기존 본문 비우는 중...');
for (let i = 0; i < 4; i++) {
  await editor.click();
  await page.waitForTimeout(400);
  await page.keyboard.press(`${mod}+a`);
  await page.waitForTimeout(250);
  await page.keyboard.press('Backspace');
  await page.waitForTimeout(700);
  const left = await frame.$eval('.se-content', (e) => (e.innerText || '').replace(/\s/g, '').length);
  const imgLeft = await frame.$$eval('.se-component', (els) => els.filter((e) => /se-image/.test(e.className)).length);
  if (left === 0 && imgLeft === 0) break;            // 글자뿐 아니라 사진도 지워졌는지
}

// 커서에 남아 있는 기울임/굵게를 끈다 (토글 버튼이 켜져 있으면 눌러서 해제)
await editor.click();
await page.waitForTimeout(400);
for (const sel of ['.se-italic-toolbar-button', '.se-bold-toolbar-button']) {
  const btn = await frame.$(sel);
  if (!btn) continue;
  // 켜진 단추의 표시는 se-is-selected 다(2026-10 실측). 예전 이름 se-is-activated 만 보다가
  // 기울임이 켜진 줄 모르고 지나쳐, 첫 줄이 기울임인 글은 본문 전체가 기울어졌다.
  const isOn = (e) => /se-is-(selected|activated)/.test(e.className);
  if (await btn.evaluate(isOn)) {
    await btn.click(); await page.waitForTimeout(400);
    const still = await btn.evaluate(isOn);
    console.log(`   (${sel.includes('italic') ? '기울임' : '굵게'} 해제${still ? ' 실패 — 발행하지 마세요' : ''})`);
  }
}

console.log('→ 서식 있는 본문 붙여넣는 중...');
if (inlineImages) {
  const r = await fillBodyWithImages(page, frame, blocks, imgFiles, mod, { focusFirst: false });
  console.log(`→ 사진 ${r.placed}/${imgBlocks.length}장을 본문 속 위치에 삽입 · 구성: ${await componentOrder(frame)}`);
} else {
  await pasteHtml(page, frame, html, plain, mod, { focus: false });
}

const outHtml = await frame.$eval('.se-content', (e) => e.innerHTML);
const after = await frame.$eval('.se-content', (e) => (e.innerText || '').length);
const boldN = (outHtml.match(/<(b|strong)\b/gi) || []).length;
const emN = (outHtml.match(/<(i|em)\b/gi) || []).length;
const emWant = (html.match(/<em>/g) || []).length;
console.log(`✅ 붙여넣기 완료 — ${after}자`);
console.log(`   굵게 ${boldN}곳 · 기울임 ${emN}곳 (원고 기준 ${emWant}곳)`);
if (!boldN) console.log('⚠️ 굵게가 안 들어갔습니다 — 서식 없이 붙었을 수 있습니다.');
if (emN > emWant * 2 + 3) console.log('⚠️ 기울임이 번졌습니다 — 발행하지 말고 알려주세요.');
if (after > before * 1.5) console.log(`⚠️ 기존 본문이 안 지워지고 덧붙은 것 같습니다(${before}자 → ${after}자) — 발행하지 마세요.`);

console.log('\n────────────────────────────────────────────');
console.log('  본문을 확인하고 우측 상단 "발행"(수정)을 누르세요.');
console.log('  제목·카테고리·태그는 건드리지 않았습니다.');
console.log('  좋아요·댓글·URL 은 그대로 유지됩니다.');
console.log('────────────────────────────────────────────\n');

await new Promise((resolve) => {
  process.stdout.write('다 끝났으면 Enter 를 눌러 브라우저를 닫습니다... ');
  process.stdin.resume();
  process.stdin.once('data', resolve);
});
await browser.close();
