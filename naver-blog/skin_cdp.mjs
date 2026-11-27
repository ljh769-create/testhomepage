// skin_cdp.mjs — skin_browser.mjs 로 띄운 크롬을 한 단계씩 조작/확인.
// node skin_cdp.mjs shot <파일.png> | goto <url> | text | eval "<js>" | click "<selector>" | fill "<selector>" "<값>" | upload "<selector>" <파일>
import { chromium } from 'playwright';
const [cmd, a, b] = process.argv.slice(2);
const br = await chromium.connectOverCDP(`http://127.0.0.1:${process.env.PORT || 9333}`);
const ctx = br.contexts()[0];
const all = ctx.pages().filter((p) => !p.url().startsWith('devtools'));
// PAGE=<주소 일부> 로 창(팝업 포함) 고르기
const page = (process.env.PAGE && all.find((p) => p.url().includes(process.env.PAGE))) || all.at(-1);
// FRAME=<주소 일부> 를 주면 그 iframe 안에서 조작(네이버 관리 화면은 iframe 안에 폼이 있음)
const F = process.env.FRAME ? (page.frames().find((f) => f.url().includes(process.env.FRAME)) || page) : page;
try {
  if (cmd === 'goto') { await page.goto(a, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000); console.log(page.url()); }
  else if (cmd === 'shot') { await page.screenshot({ path: a }); console.log('shot', page.url()); }
  else if (cmd === 'text') { console.log(page.url()); console.log((await F.innerText('body')).slice(0, 4000)); }
  else if (cmd === 'eval') { console.log(JSON.stringify(await F.evaluate(a), null, 1)?.slice(0, 6000)); }
  else if (cmd === 'click') { await F.click(a, { timeout: 8000 }); await page.waitForTimeout(1500); console.log('clicked', page.url()); }
  else if (cmd === 'fill') { await F.fill(a, b, { timeout: 8000 }); console.log('filled'); }
  else if (cmd === 'upload') { await F.setInputFiles(a, b); await page.waitForTimeout(2000); console.log('uploaded'); }
  else if (cmd === 'choose') { // 누르면 파일 선택창이 뜨는 버튼: 클릭 → 파일 지정(새 창이 뜨면 그 주소를 알려줌)
    const pop = ctx.waitForEvent('page', { timeout: 6000 }).catch(() => null);
    const fc = page.waitForEvent('filechooser', { timeout: 6000 }).catch(() => null);
    await F.click(a, { timeout: 8000 });
    const [c, w] = await Promise.all([fc, pop]);
    if (c) { await c.setFiles(b); await page.waitForTimeout(2500); console.log('chosen'); }
    else console.log('no chooser', w ? 'popup: ' + w.url() : '');
  }
  else if (cmd === 'pages') { console.log(ctx.pages().map((p) => p.url())); console.log(page.frames().map((f) => f.url())); }
} finally { process.exit(0); }
