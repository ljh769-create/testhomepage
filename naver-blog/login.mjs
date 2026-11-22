/* eslint-disable no-console */
/**
 * 1단계: 네이버 수동 로그인 → 세션 자동 저장
 * ----------------------------------------------------------------------------
 * 브라우저가 열리면 "사람이 직접" 로그인하세요 (아이디/비번/캡차/2차인증 전부 수동).
 * 로그인이 감지되면(네이버 로그인 쿠키 확인) 세션을 naver-session.json 에
 * 자동 저장하고 브라우저를 닫습니다. Enter 를 누를 필요가 없습니다.
 *
 * ※ 네이버는 자동화 브라우저(Playwright 기본 크로미움)를 감지하면
 *   비밀번호가 맞아도 "비밀번호가 틀렸다"고 돌려보냅니다. 그래서
 *   - 실제 설치된 구글 크롬(channel: chrome)을 쓰고
 *   - navigator.webdriver 등 자동화 표식을 지우고
 *   - 전용 프로필 폴더(.chrome-profile)를 고정해 "같은 기기"로 보이게 합니다.
 *
 * 세션은 시간이 지나면 만료됩니다. post.mjs 가 "로그인 필요" 라고 하면
 * 이 스크립트를 다시 돌려 세션을 갱신하세요.
 *
 * 실행:  npm run login
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SESSION = path.join(__dirname, 'naver-session.json');
const PROFILE = path.join(__dirname, '.chrome-profile'); // 기기 인증 유지용 고정 프로필
const TIMEOUT_MS = 60 * 60 * 1000; // 로그인 대기 최대 60분 (서두를 필요 없게)

fs.mkdirSync(PROFILE, { recursive: true });

const launchOpts = {
  headless: false,
  locale: 'ko-KR',
  viewport: null,
  args: [
    '--disable-blink-features=AutomationControlled',
    '--start-maximized',
  ],
  ignoreDefaultArgs: ['--enable-automation'],
};

/* 앞선 실행이 비정상 종료하면 .chrome-profile 에 Singleton* 락이 고아로 남고,
   다음 실행이 「기존 브라우저 세션에서 여는 중입니다」로 즉사한다(2026-09-24에 세 번 연속 그랬다).
   프로필 데이터는 건드리지 않고 락 링크만 걷어낸다 — 그 브라우저가 살아 있으면 어차피 다시 생긴다. */
for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
  try { fs.rmSync(path.join(PROFILE, f), { force: true }); } catch (e) { /* 없으면 그만 */ }
}

let ctx;
try {
  // 실제 설치된 구글 크롬 우선 (자동화 탐지에 가장 덜 걸림)
  ctx = await chromium.launchPersistentContext(PROFILE, { ...launchOpts, channel: 'chrome' });
  console.log('🌐 구글 크롬으로 실행합니다.');
} catch {
  ctx = await chromium.launchPersistentContext(PROFILE, launchOpts);
  console.log('🌐 크롬을 못 찾아 기본 크로미움으로 실행합니다. (탐지 가능성 있음)');
}

// 자동화 표식 지우기
await ctx.addInitScript(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
  Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
});

const page = ctx.pages()[0] ?? (await ctx.newPage());

/* 프로필에 이미 로그인이 남아 있으면 다시 로그인할 필요가 없다.
   (창이 닫혀도 로그인은 .chrome-profile 안에 남는다 — 2026-09-23) */
{
  const c = await ctx.cookies('https://www.naver.com');
  const hasAuth = c.some((x) => x.name === 'NID_AUT' && x.value) && c.some((x) => x.name === 'NID_SES' && x.value);
  if (hasAuth) {
    await ctx.storageState({ path: SESSION });
    console.log('✅ 프로필에 로그인이 이미 남아 있습니다 — 세션만 저장했습니다:', SESSION);
    console.log('   이제 npm run post -- --slug=<글slug> 로 바로 진행하세요.\n');
    await ctx.close();
    process.exit(0);
  }
}

await page.goto('https://nid.naver.com/nidlogin.login', { waitUntil: 'domcontentloaded' });

/* "로그인 상태 유지"를 미리 켜 둔다 — 안 켜면 NID_AUT/NID_SES 가 세션 쿠키로
   발급돼서 며칠 만에 세션이 죽는다(2026-09-15 저장분이 9/23 에 만료된 원인). */
try {
  const stay = page.locator('#loginStay');
  if ((await stay.count()) && !(await stay.isChecked())) {
    await page.locator('label[for="loginStay"]').first().click({ timeout: 3000 });
    console.log('☑️  "로그인 상태 유지" 를 켰습니다 (세션이 오래 유지됩니다).');
  }
} catch { console.log('ℹ️  "로그인 상태 유지" 자동 체크 실패 — 화면에서 직접 켜 주세요.'); }

console.log('\n────────────────────────────────────────────');
console.log('  브라우저 창에서 네이버에 직접 로그인하세요.');
console.log('  (아이디/비밀번호/캡차/2차인증 전부 수동)');
console.log('  ※ 비밀번호는 타이핑보다 "복사 → 붙여넣기"가 더 잘 통합니다.');
console.log('  로그인이 감지되면 자동으로 세션을 저장합니다. (최대 10분 대기)');
console.log('────────────────────────────────────────────\n');

const start = Date.now();
let ok = false;
while (Date.now() - start < TIMEOUT_MS) {
  const cookies = await ctx.cookies('https://www.naver.com');
  const auth = cookies.find((c) => c.name === 'NID_AUT' && c.value);
  const ses = cookies.find((c) => c.name === 'NID_SES' && c.value);
  if (auth && ses) { ok = true; break; }
  await page.waitForTimeout(3000).catch(() => {});
  process.stdout.write('.');
}
console.log('');

if (ok) {
  await ctx.storageState({ path: SESSION });
  console.log('✅ 로그인 감지 — 세션 저장 완료:', SESSION);
  console.log('   프로필도 유지됩니다:', PROFILE, '(다음엔 기기 인증이 덜 걸립니다)');
  console.log('   이제 npm run post -- --slug=<글slug> 로 글을 채울 수 있어요.\n');
  await ctx.close();
  process.exit(0);
} else {
  console.log('⚠️ 로그인이 감지되지 않아 창을 닫습니다.');
  console.log('   ※ 혹시 로그인까지 성공하셨다면 그 로그인은 프로필에 남아 있으니,');
  console.log('     `npm run login` 을 다시 실행하면 즉시 세션만 저장됩니다.');
  console.log('   같은 아이디/비번인데 계속 "비밀번호가 틀렸다"고 나오면,');
  console.log('   평소 쓰는 크롬에서 먼저 로그인이 되는지 확인해 주세요.');
  await ctx.close();
  process.exit(1);
}
