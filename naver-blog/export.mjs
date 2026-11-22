/* eslint-disable no-console */
/**
 * 내 블로그 글 전부를 텍스트 파일로 내려받기 (로컬 전용, 공개·커밋 금지)
 *   node export.mjs --blogId=dream7510            # 글 목록만 (세션 확인용)
 *   node export.mjs --blogId=dream7510 --all      # 목록 + 본문 전부
 * 결과: exports/<글번호>.txt  (첫 줄 제목, 둘째 줄 날짜, 셋째 줄 주소, 그 뒤 본문)
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, 'exports');
const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  return m ? [m[1], m[2] ?? true] : [a, true];
}));
const PROFILE = path.join(__dirname, args.fresh ? '.export-profile' : '.chrome-profile');
const blogId = args.blogId || process.env.NAVER_BLOG_ID;
if (!blogId) { console.error('블로그 아이디가 필요합니다: --blogId=아이디'); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome', headless: false, locale: 'ko-KR', viewport: null,
    args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
    ignoreDefaultArgs: ['--enable-automation'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  // 1) 글 번호 목록 수집 (제목 목록 API 를 쪽별로)
  const logNos = new Map();
  await page.goto(`https://m.blog.naver.com/${blogId}`, { waitUntil: 'domcontentloaded' });
  await sleep(1500);
  for (let pg = 1; pg <= 500; pg++) {
    const u = `https://blog.naver.com/PostTitleListAsync.naver?blogId=${blogId}&viewdate=&currentPage=${pg}&categoryNo=0&parentCategoryNo=&countPerPage=30`;
    const r = await page.request.get(u, { headers: { Referer: `https://m.blog.naver.com/${blogId}` } });
    let list = [];
    try { list = JSON.parse((await r.text()).replace(/\\'/g, "'")).postList || []; } catch { /* 빈 쪽 */ }
    const before = logNos.size;
    list.forEach((x) => { if (!logNos.has(x.logNo)) logNos.set(x.logNo, decodeURIComponent((x.title || '').replace(/\+/g, ' '))); });
    console.log(`목록 ${pg}쪽: 새로 ${logNos.size - before}개 (누적 ${logNos.size})`);
    if (list.length === 0 || logNos.size === before) break;
    await sleep(400);
  }
  fs.writeFileSync(path.join(OUT, '_index.json'), JSON.stringify([...logNos].map(([n, t]) => ({ logNo: n, title: t })), null, 1), 'utf8');
  console.log(`글 목록 저장: exports/_index.json (${logNos.size}개)`);

  if (!args.all) { await ctx.close(); return; }

  // 2) 본문 내려받기
  let n = 0;
  for (const [logNo, title] of logNos) {
    const file = path.join(OUT, `${logNo}.txt`);
    if (fs.existsSync(file)) { n++; continue; }
    const url = `https://blog.naver.com/PostView.naver?blogId=${blogId}&logNo=${logNo}`;
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await sleep(1500);
      const frame = page.frames().find((f) => f.url().includes('PostView')) || page.mainFrame();
      const body = await frame.evaluate(() => {
        const el = document.querySelector('.se-main-container') || document.querySelector('#postViewArea') || document.querySelector('.post_ct') || document.body;
        return el.innerText;
      });
      const date = await frame.evaluate(() => (document.querySelector('.se_publishDate, .blog2_series, .date')?.textContent || '').trim()).catch(() => '');
      fs.writeFileSync(file, `${title}\n${date}\n${url}\n\n${body.trim()}\n`, 'utf8');
      n++;
      if (n % 25 === 0) console.log(`본문 ${n}/${logNos.size} 저장`);
    } catch (e) {
      console.log(`실패 ${logNo}: ${e.message.split('\n')[0]}`);
    }
  }
  console.log(`완료: 본문 ${n}/${logNos.size}개 → exports/`);
  await ctx.close();
})().catch((e) => { console.error('오류:', e.message); process.exit(1); });
