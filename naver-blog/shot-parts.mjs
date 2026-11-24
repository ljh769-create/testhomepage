// 긴 페이지를 화면 높이만큼 나눠 찍는다(크롬은 16,384px 넘는 전체 캡처에서 위쪽이 되풀이됨).
// 사용: node shot-parts.mjs <출력폴더> <폭> <조각높이> <페이지.html>  → part-<폭>-NN.png
import { chromium } from "playwright";
import path from "path";
const [out, w, h, p] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
const pg = await b.newPage({ viewport: { width: +w, height: +h } });
await pg.goto("file:///" + path.resolve("..", p).replace(/\\/g, "/"));
await pg.addStyleTag({ content: "main section,.band{content-visibility:visible!important}.top{position:static!important}.fixed{display:none!important}html{scroll-behavior:auto!important}*{animation:none!important}" });
await pg.evaluate(async () => { document.querySelectorAll("img").forEach(i => i.loading = "eager");
  for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 50)); } window.scrollTo(0, 0); });
await pg.waitForTimeout(2000);
const total = await pg.evaluate(() => document.documentElement.scrollHeight);
let n = 0;
for (let y = 0; y < total; y += +h) {
  await pg.evaluate(yy => window.scrollTo(0, yy), y);
  await pg.waitForTimeout(250);
  await pg.screenshot({ path: path.join(out, `part-${w}-${String(n).padStart(2, "0")}.png`) });
  n++;
}
console.log(total, n);
await b.close();
