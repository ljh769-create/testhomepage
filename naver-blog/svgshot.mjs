// 사용: node svgshot.mjs <출력폴더> <svg파일>... (1200x675 PNG로 그려 확인)
import { chromium } from "playwright";
import path from "path";
const [out, ...files] = process.argv.slice(2);
const b = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
const pg = await b.newPage({ viewport: { width: 1200, height: 675 } });
for (const f of files) {
  await pg.goto("file:///" + path.resolve(f).replace(/\\/g, "/"));
  await pg.waitForTimeout(300);
  await pg.screenshot({ path: path.join(out, path.basename(f).replace(".svg", ".png")) });
}
await b.close();
