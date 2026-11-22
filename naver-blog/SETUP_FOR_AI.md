# 네이버 블로그 자동 발행 세팅 안내 (AI 작업자용)

이 문서를 받은 AI는 아래 순서대로 이 PC에 네이버 블로그 자동 발행 환경을 만든다.
사람(사용자)이 직접 해야 하는 단계는 **[사람]** 으로 표시했다. 그 단계에서는 멈추고 사용자에게 요청한다.

---

## 0. 먼저 알아둘 것 — 왜 크롬 확장으로는 안 되나

- **Claude in Chrome(크롬 확장)으로는 네이버를 조작할 수 없다.** 확장 자체의 사이트 차단 목록에 `blog.naver.com` 이 들어 있어 접속부터 막힌다. 모바일 주소 등으로 우회하지 않는다.
- 대신 **이 PC에서 Node.js 스크립트(Playwright 라이브러리)를 터미널로 실행**한다. 스크립트가 PC에 설치된 구글 크롬을 직접 띄워 조작하므로 확장의 차단 목록과 무관하다.
- 따라서 이 작업은 **터미널 명령을 실행할 수 있는 환경**(Claude Code 터미널 / 데스크톱 앱 / VS Code 확장)에서만 가능하다. claude.ai 웹 채팅만으로는 불가.
- 로그인은 **처음 한 번 사람이 직접** 한다. 그 상태를 전용 크롬 프로필 폴더에 남겨 두고 재사용한다.

---

## 1. 사전 준비

1. Node.js 18 이상 설치 확인: `node -v`
2. 구글 크롬 설치 확인 (기본 경로에 설치되어 있어야 `channel: 'chrome'` 이 동작)
3. 작업 폴더 만들기 (위치는 사용자에게 확인. 예: `~/naver-blog` 또는 `C:\naver-blog`)

```bash
mkdir naver-blog && cd naver-blog
npm init -y
npm pkg set type=module
npm install playwright
npx playwright install chromium   # 크롬을 못 찾을 때의 예비용
```

4. `.gitignore` 를 만든다(저장소에 넣을 경우). 로그인 정보가 들어 있으므로 **절대 커밋·공유 금지**:
```
.chrome-profile/
node_modules/
```

---

## 2. 네이버 자동화 탐지 회피 — 반드시 지킬 설정

이게 빠지면 비밀번호가 맞아도 "비밀번호가 틀렸다"고 하거나 글쓰기가 막힌다.

| 설정 | 이유 |
|---|---|
| `channel: 'chrome'` | 기본 크로미움 대신 실제 설치된 크롬 사용 |
| `launchPersistentContext('./.chrome-profile', …)` | 매번 같은 프로필 → 네이버가 같은 기기로 인식, 로그인 유지 |
| `args: ['--disable-blink-features=AutomationControlled']` | 자동화 표식 제거 |
| `ignoreDefaultArgs: ['--enable-automation']` | "자동화 소프트웨어가 제어 중" 표식 제거 |
| `addInitScript` 로 `navigator.webdriver` 를 `undefined` 로 | 자동화 탐지 회피 |
| `headless: false` | 화면을 띄운 채 실행 |

---

## 3. login.mjs — 최초 1회 로그인

작업 폴더에 아래 파일을 만든다.

```js
// login.mjs — 사람이 직접 로그인. 로그인 쿠키가 생기면 자동 종료.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const PROFILE = './.chrome-profile';
// 앞선 실행이 비정상 종료해 남은 잠금 파일 제거
for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
  try { fs.rmSync(path.join(PROFILE, f), { force: true }); } catch {}
}

const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome', headless: false, locale: 'ko-KR', viewport: null,
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
  ignoreDefaultArgs: ['--enable-automation'],
});
await ctx.addInitScript(() => Object.defineProperty(navigator, 'webdriver', { get: () => undefined }));
const page = ctx.pages()[0] ?? await ctx.newPage();

const hasLogin = async () => {
  const c = await ctx.cookies('https://www.naver.com');
  return c.some(x => x.name === 'NID_AUT' && x.value) && c.some(x => x.name === 'NID_SES' && x.value);
};
if (await hasLogin()) { console.log('이미 로그인되어 있음'); await ctx.close(); process.exit(0); }

await page.goto('https://nid.naver.com/nidlogin.login');
// "로그인 상태 유지" 미리 켜기 — 안 켜면 며칠 만에 로그인이 풀린다
try {
  if (!(await page.locator('#loginStay').isChecked())) await page.locator('label[for="loginStay"]').first().click();
} catch {}
console.log('브라우저 창에서 직접 로그인하세요. (최대 30분 대기)');

for (let i = 0; i < 1800; i++) {
  if (await hasLogin()) { console.log('로그인 확인 — 프로필에 저장됨'); break; }
  await page.waitForTimeout(1000);
}
await ctx.close();
```

실행: `node login.mjs`
**[사람]** 뜬 크롬 창에서 아이디·비밀번호·캡차·2차 인증을 직접 입력한다. "로그인 상태 유지"가 켜져 있는지 확인. (비밀번호는 타이핑보다 복사·붙여넣기가 잘 통한다)

---

## 4. post.mjs — 제목·본문·태그 입력 후 발행

```js
// post.mjs
// 사용: node post.mjs "제목" 본문.html "태그1,태그2" [--publish]
// --publish 가 없으면 발행 팝업까지만 채우고 멈춘다(사람이 확인 후 클릭).
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BLOG_ID = '여기에_블로그아이디';            // blog.naver.com/<아이디>
const [title, bodyFile, tagArg = ''] = process.argv.slice(2).filter(a => !a.startsWith('--'));
const doPublish = process.argv.includes('--publish');
const bodyHtml = fs.readFileSync(bodyFile, 'utf8');
const tags = tagArg.split(',').map(s => s.trim()).filter(Boolean).slice(0, 30);
const MOD = process.platform === 'darwin' ? 'Meta' : 'Control';   // 윈도우는 Ctrl

const PROFILE = './.chrome-profile';
for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
  try { fs.rmSync(path.join(PROFILE, f), { force: true }); } catch {}
}
const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome', headless: false, locale: 'ko-KR', viewport: null,
  permissions: ['clipboard-read', 'clipboard-write'],
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
  ignoreDefaultArgs: ['--enable-automation'],
});
await ctx.addInitScript(() => Object.defineProperty(navigator, 'webdriver', { get: () => undefined }));
const page = ctx.pages()[0] ?? await ctx.newPage();

await page.goto(`https://blog.naver.com/${BLOG_ID}?Redirect=Write`, { waitUntil: 'domcontentloaded' });
if (page.url().includes('nid.naver.com')) {
  console.log('로그인 만료 — node login.mjs 를 다시 실행하세요'); await ctx.close(); process.exit(1);
}

// 글쓰기 에디터는 iframe#mainFrame 안에 있다
const frame = await (await page.waitForSelector('iframe#mainFrame', { timeout: 15000 })).contentFrame();

// 복구 팝업("이어서 작성?")·도움말 측면 패널 닫기 — 몇 초 뒤에 뜨기도 해서 반복 확인
const OVERLAYS = ['.se-popup-button-cancel', '.se-help-panel-close', 'button.se-help-close',
  'button[aria-label="닫기"]', 'button[aria-label*="닫기"]'];
for (let i = 0; i < 15; i++) {
  for (const scope of [frame, page]) for (const sel of OVERLAYS) {
    const el = scope.locator(sel).first();
    if (await el.isVisible({ timeout: 150 }).catch(() => false)) await el.click({ force: true }).catch(() => {});
  }
  await page.waitForTimeout(400);
}
await page.keyboard.press('Escape');

// 제목
await frame.locator('.se-documentTitle .se-text-paragraph').first().click();
await page.keyboard.type(title, { delay: 20 });
console.log('제목 입력 완료');

// 본문: 클립보드에 HTML 을 넣고 붙여넣기 (굵게·소제목 등 서식 유지)
await page.evaluate(async (html) => {
  await navigator.clipboard.write([new ClipboardItem({
    'text/html': new Blob([html], { type: 'text/html' }),
    'text/plain': new Blob([html.replace(/<[^>]+>/g, '')], { type: 'text/plain' }),
  })]);
}, bodyHtml);
await frame.locator('.se-content').first().click();
await page.waitForTimeout(500);
await page.keyboard.press(`${MOD}+v`);
await page.waitForTimeout(2500);
console.log('본문 입력 완료');

// 발행 팝업 열기 → 태그 (한 개씩 치고 Enter. 한꺼번에 붙여넣으면 뭉친다)
await frame.locator('button[data-click-area="tpb.publish"]').first().click({ force: true });
await page.waitForTimeout(1800);
if (tags.length) {
  const tagBox = frame.locator('#tag-input').first();
  for (const t of tags) {
    await tagBox.click();
    await tagBox.type(t, { delay: 40 });
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
  }
  console.log(`태그 ${tags.length}개 입력 완료`);
}

if (doPublish) {
  // 주의: 위쪽 「발행」 단추를 또 누르면 팝업이 닫힌다. 팝업 안의 최종 단추를 누른다.
  const before = page.url();
  await frame.locator('button[data-testid="seOnePublishBtn"], button[class*="confirm_btn"]').first().click();
  await page.waitForTimeout(6000);
  const after = page.url();
  console.log(after !== before && !/Redirect=Write|postwrite/i.test(after)
    ? `발행 완료: ${after}` : `발행 확인 필요 — 창을 보세요 (${after})`);
  await ctx.close();
} else {
  console.log('발행 팝업까지 채웠습니다. 사람이 확인 후 「발행」을 누르세요. (창은 열어 둡니다)');
  await new Promise(() => {});   // 사람이 끝낼 때까지 대기 — 이 프로세스를 먼저 끄면 글이 날아간다
}
```

### 원고(본문 HTML) 만드는 법
- 마크다운으로 쓴 원고가 있으면 HTML로 변환해서 `본문.html` 로 저장한다(소제목은 `<p><b>…</b></p>`, 문단은 `<p>…</p>`, 목록은 문단 앞에 `• `).
- `<h2>` 같은 태그는 네이버 에디터에서 서식이 깨질 수 있어, 굵은 문단으로 바꾸는 편이 안정적이다.

---

## 5. 실행 절차 (매번)

1. 원고 HTML 파일을 준비한다.
2. **[사람]** 처음이거나 "로그인 만료"가 뜨면 `node login.mjs` 로 다시 로그인.
3. 첫 몇 번은 `--publish` 없이 실행해 사람이 화면을 확인하고 직접 발행한다.
   ```bash
   node post.mjs "글 제목" 본문.html "태그1,태그2,태그3"
   ```
4. 화면이 문제없이 채워지는 것이 확인되고 사용자가 "자동 발행"을 원하면 `--publish` 를 붙인다.
   ```bash
   node post.mjs "글 제목" 본문.html "태그1,태그2,태그3" --publish
   ```
5. 발행 확인: 출력의 글 주소, 또는 `https://rss.blog.naver.com/<블로그아이디>.xml` 의 최신 글 제목.

### AI가 실행할 때 주의
- **발행이 확인되기 전에 실행 중인 프로세스를 끄지 않는다.** 브라우저가 닫히면서 쓰던 글이 사라진다.
- 같은 `.chrome-profile` 로 두 개를 동시에 띄우지 않는다.
- 실행 출력은 몇 줄 요약만 사용자에게 전한다.

---

## 6. 이미지·카테고리 (선택)

- **이미지**: 에디터 상단의 사진 단추를 누르기 직전에 파일 선택창을 가로챈다.
  ```js
  page.once('filechooser', fc => fc.setFiles(['./images/01.jpg']));
  await frame.locator('button[data-name="image"], button.se-image-toolbar-button').first().click();
  await page.waitForTimeout(4000);
  ```
  (선택자는 화면에서 확인 후 맞출 것)
- **카테고리**: 발행 팝업에서 카테고리 선택칸(`[class*="selectbox_button"]`)을 누른 뒤 `label:has-text("카테고리명")` 을 클릭.

---

## 7. 문제가 생기면

| 증상 | 원인·해결 |
|---|---|
| "기존 브라우저 세션에서 여는 중입니다" 후 바로 종료 | 앞선 실행의 잠금 파일이 남음, 또는 같은 프로필로 이미 크롬이 떠 있음. 남은 크롬을 끄고 `.chrome-profile/Singleton*` 삭제 후 재실행 (위 스크립트는 자동 삭제함) |
| 비밀번호가 맞는데 "틀렸다"고 함 | 2장의 탐지 회피 설정 누락. 실제 크롬(`channel: 'chrome'`)인지 확인 |
| 며칠 만에 로그인이 풀림 | "로그인 상태 유지"를 안 켬. `login.mjs` 다시 실행 |
| 제목·본문 칸을 못 찾음 | 네이버가 에디터 화면을 바꿈. 선택자를 화면에서 다시 찾아 수정 |
| 발행 최종 단추를 못 찾음 | 발행 팝업이 닫혀 있거나 단추 이름이 바뀜. 프레임 안 `button` 중 글자에 "발행"이 있는 것의 class·data-testid 를 출력해 선택자 갱신 |
| 윈도우에서 붙여넣기가 안 됨 | `MOD` 가 `Control` 인지 확인 |

---

## 8. 지켜야 할 것

- **본인 블로그·본인 글만, 낮은 빈도로.** 대량·반복 발행은 네이버 제재 대상이다.
- **캡차·2차 인증은 자동화하지 않는다.** 사람이 한다.
- `.chrome-profile/` 폴더에는 로그인 정보가 들어 있다. 공유·업로드·커밋 금지.
- 네이버 화면이 바뀌면 스크립트가 깨질 수 있다. 깨지면 무리하게 반복 시도하지 말고 사용자에게 화면을 보여 달라고 한 뒤 선택자를 고친다.
