// 사용: node shot.mjs <출력폴더> <폭> <페이지.html>... (전체 화면 캡처)
import { chromium } from "playwright";
import path from "path";
const [out, w, ...pages] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
const pg = await b.newPage({ viewport: { width: +w, height: 900 } });
for (const p of pages) {
  await pg.goto("file:///" + path.resolve("..", p).replace(/\\/g, "/"));
  await pg.evaluate(() => document.querySelectorAll(".reveal").forEach(e => e.classList.add("in")));
  await pg.addStyleTag({ content: "main section,.band{content-visibility:visible!important}" });
  await pg.evaluate(async () => { document.querySelectorAll("img").forEach(i => i.loading = "eager");
    for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); });
  await pg.waitForTimeout(2500);
  await pg.screenshot({ path: path.join(out, `shot-${w}-` + p.replace(/[\/.]/g, "_") + ".png"), fullPage: true });
}
await b.close();
