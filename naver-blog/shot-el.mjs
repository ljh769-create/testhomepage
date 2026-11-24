// 사용: node shot-el.mjs <출력폴더> <폭> <페이지.html> <선택자>... (요소별 캡처)
import { chromium } from "playwright";
import path from "path";
const [out, w, page, ...sels] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
const pg = await b.newPage({ viewport: { width: +w, height: 900 } });
await pg.goto("file:///" + path.resolve("..", page).replace(/\\/g, "/"));
await pg.addStyleTag({ content: "main section,.band{content-visibility:visible!important}.reveal{opacity:1!important;transform:none!important}" });
await pg.evaluate(() => document.querySelectorAll("img").forEach(i => i.loading = "eager"));
await pg.waitForTimeout(2000);
let i = 0;
for (const s of sels) {
  const el = await pg.$(s);
  if (!el) { console.log("missing", s); continue; }
  await el.screenshot({ path: path.join(out, `el-${w}-${i++}.png`) });
}
await b.close();
