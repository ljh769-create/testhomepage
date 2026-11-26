// skin_cdp.mjs — skin_browser.mjs 로 띄운 크롬을 한 단계씩 조작/확인.
// node skin_cdp.mjs shot <파일.png> | goto <url> | text | eval "<js>" | click "<selector>" | fill "<selector>" "<값>" | upload "<selector>" <파일>
import { chromium } from 'playwright';
const [cmd, a, b] = process.argv.slice(2);
const br = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = br.contexts()[0];
const page = ctx.pages().filter((p) => !p.url().startsWith('devtools')).at(-1);
try {
  if (cmd === 'goto') { await page.goto(a, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000); console.log(page.url()); }
  else if (cmd === 'shot') { await page.screenshot({ path: a }); console.log('shot', page.url()); }
  else if (cmd === 'text') { console.log(page.url()); console.log((await page.innerText('body')).slice(0, 4000)); }
  else if (cmd === 'eval') { console.log(JSON.stringify(await page.evaluate(a), null, 1)?.slice(0, 6000)); }
  else if (cmd === 'click') { await page.click(a, { timeout: 8000 }); await page.waitForTimeout(1500); console.log('clicked', page.url()); }
  else if (cmd === 'fill') { await page.fill(a, b, { timeout: 8000 }); console.log('filled'); }
  else if (cmd === 'upload') { await page.setInputFiles(a, b); await page.waitForTimeout(2000); console.log('uploaded'); }
  else if (cmd === 'pages') { console.log(ctx.pages().map((p) => p.url())); }
} finally { process.exit(0); }
