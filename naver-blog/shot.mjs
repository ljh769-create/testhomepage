// 사용: node shot.mjs <출력폴더> <페이지.html>... (모바일 390px 전체 화면)
import { chromium } from "playwright";
import path from "path";
const [out, ...pages] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
const pg = await b.newPage({ viewport: { width: 390, height: 844 } });
for (const p of pages) {
  await pg.goto("file:///" + path.resolve("..", p).replace(/\\/g, "/"));
  await pg.waitForTimeout(800);
  await pg.screenshot({ path: path.join(out, "sub-" + p.replace(".html", "") + ".png"), fullPage: true });
}
await b.close();
