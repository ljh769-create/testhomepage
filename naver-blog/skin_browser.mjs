// skin_browser.mjs — 블로그 꾸미기용 크롬을 띄워 두고(로그인은 원장님이 직접) 제어 포트를 연다.
// 사용: node skin_browser.mjs <blogId>   (예: hcning20)  → 프로필 .chrome-profile-<blogId>, 제어 포트 9333
// 조작은 skin_cdp.mjs 로 단계마다(스크린샷 확인 뒤) 한다. 비밀번호는 자동으로 넣지 않는다.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const blogId = process.argv[2] || 'hcning20';
const PROFILE = path.join(__dirname, `.chrome-profile-${blogId}`);
fs.mkdirSync(PROFILE, { recursive: true });
for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) { try { fs.rmSync(path.join(PROFILE, f), { force: true }); } catch {} }
const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome', headless: false, locale: 'ko-KR', viewport: null,
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized', '--remote-debugging-port=9333'],
  ignoreDefaultArgs: ['--enable-automation'],
});
await ctx.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
const page = ctx.pages()[0] ?? (await ctx.newPage());
const target = `https://admin.blog.naver.com/${blogId}/config/blog`;
const authed = async () => { const c = await ctx.cookies('https://www.naver.com'); return c.some((x) => x.name === 'NID_AUT' && x.value); };
if (await authed()) { await page.goto(target); console.log('✅ 이미 로그인됨 — 관리 화면 열림'); }
else {
  await page.goto(`https://nid.naver.com/nidlogin.login?url=${encodeURIComponent(target)}`);
  console.log('⏳ 로그인 창을 띄웠습니다. 원장님이 직접 로그인해 주세요.');
  const t0 = Date.now();
  while (!(await authed())) { if (Date.now() - t0 > 3 * 3600e3) { console.log('⌛ 3시간 대기 끝'); break; } await new Promise((r) => setTimeout(r, 3000)); }
  if (await authed()) console.log('✅ 로그인 확인', new Date().toLocaleTimeString());
}
ctx.on('close', () => process.exit(0));
await new Promise(() => {}); // 창이 닫힐 때까지 유지
