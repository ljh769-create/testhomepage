// 사용: node shot-vp.mjs <출력폴더> <폭> <페이지.html>... (첫 화면과 맨 아래 화면 캡처)
import { chromium } from "playwright";
import path from "path";
import { pathToFileURL } from "url";
const [out, w, ...pages] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
for (const [i, p] of pages.entries()) {
  const pg = await b.newPage({ viewport: { width: +w, height: 844 } });
  await pg.goto(pathToFileURL(path.resolve("..", p)).href);
  await pg.waitForTimeout(1200);
  await pg.screenshot({ path: path.join(out, `vp-${i}-top.png`) });
  await pg.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await pg.waitForTimeout(800);
  await pg.screenshot({ path: path.join(out, `vp-${i}-bottom.png`) });
  const r = await pg.evaluate(() => ({ sw: document.documentElement.scrollWidth, bar: !!document.querySelector(".actbar"), n: document.querySelectorAll(".actbar a").length }));
  console.log(p, JSON.stringify(r));
  await pg.close();
}
await b.close();
