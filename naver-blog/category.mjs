/* eslint-disable no-console */
/**
 * 네이버 블로그 카테고리 추가 (로컬 전용)
 * ----------------------------------------------------------------------------
 * 사용법:  node category.mjs --add="개발 이야기"
 *          node category.mjs --list
 *
 * 세션이 필요합니다. 만료됐으면 `npm run login` 을 먼저 돌리세요.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SESSION = path.join(__dirname, 'naver-session.json');

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  return m ? [m[1], m[2] ?? true] : [a, true];
}));
const blogId = args.blogId || process.env.NAVER_BLOG_ID;
if (!blogId) { console.error('❌ 블로그 아이디가 필요합니다: --blogId=<아이디> 또는 환경변수 NAVER_BLOG_ID'); process.exit(1); }
const name = typeof args.add === 'string' ? args.add.trim() : null;

if (!fs.existsSync(SESSION)) {
  console.error('❌ 세션이 없습니다. 먼저 `npm run login` 으로 로그인하세요.');
  process.exit(1);
}

const browser = await chromium.launch({ headless: false });
const ctx = await browser.newContext({ storageState: SESSION, locale: 'ko-KR' });
const page = await ctx.newPage();
// 네이버가 저장 시 confirm 창을 띄우는데, playwright 기본값은 '취소'라 반드시 수락 처리해야 합니다.
page.on('dialog', async (d) => { console.log(`   (대화상자: ${d.message().slice(0, 60)} → 확인)`); await d.accept().catch(() => {}); });

const ADMIN = `https://admin.blog.naver.com/AdminCategoryView.naver?blogId=${blogId}`;
const readTree = () => page.$$eval('#tree li span', (els) => els.map((e) => e.innerText.trim()).filter(Boolean));

await page.goto(ADMIN, { waitUntil: 'networkidle' }).catch(() => {});
await page.waitForTimeout(3000);

if (!(await page.$('#tree'))) {
  console.error('❌ 카테고리 화면을 못 찾음 — 세션 만료일 수 있습니다. `npm run login` 후 다시 시도하세요.');
  await browser.close();
  process.exit(1);
}

const before = await readTree();
console.log('현재 카테고리:', before.join(' / '));

if (!name) {
  console.log('\n(--add="이름" 을 주면 카테고리를 추가합니다)');
  await browser.close();
  process.exit(0);
}

if (before.some((c) => c.replace(/\s+/g, '') === name.replace(/\s+/g, ''))) {
  console.log(`✅ "${name}" 카테고리가 이미 있습니다. 아무것도 하지 않습니다.`);
  await browser.close();
  process.exit(0);
}

console.log(`→ "${name}" 추가 중...`);
await page.click('._addCategoryView');
await page.waitForTimeout(1200);

const input = await page.$('#category_name');
if (!input) { console.error('❌ 카테고리명 입력칸을 못 찾음'); await browser.close(); process.exit(1); }
await input.fill('');
await input.type(name, { delay: 40 });
await page.waitForTimeout(600);

console.log('입력 후 목록:', (await readTree()).join(' / '));

// 저장(확인)은 사람이 누릅니다. 자동 클릭은 네이버 확인창에 막혀 저장이 취소됩니다.
console.log('\n────────────────────────────────────────────');
console.log(`  "${name}" 이(가) 목록에 추가된 걸 확인하고,`);
console.log('  화면 아래 "확인" 버튼을 직접 눌러 저장하세요.');
console.log('────────────────────────────────────────────\n');

await new Promise((resolve) => {
  process.stdout.write('저장했으면 Enter 를 눌러 브라우저를 닫습니다... ');
  process.stdin.resume();
  process.stdin.once('data', resolve);
});
await browser.close();
process.exit(0);
