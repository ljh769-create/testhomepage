/* eslint-disable no-console */
/**
 * 마크다운 원고 → 네이버 에디터 붙여넣기용 HTML 변환
 * ----------------------------------------------------------------------------
 * 키보드 토글(Cmd+B)로 서식을 넣으면 에디터가 Enter·툴바 클릭에서 상태를 초기화해
 * 굵기가 들쭉날쭉해진다. 그래서 HTML 을 클립보드에 올리고 한 번에 붙여넣는다.
 *
 * 지원: 소제목(##) / 굵게(**…**) / 기울임(*…*) / 인용(>) / 불릿(-) / 구분선(---)
 */
import fs from 'fs';
import path from 'path';

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * 인라인 서식을 HTML 로. **굵게** 먼저 처리하고 남은 *기울임* 처리.
 *
 * 주의: 네이버 에디터는 한 문단이 통째로 <em> 이면 그 기울임을 뒤 문단들에 물려준다
 * (붙여넣기 한 번으로 본문 전체가 기울어짐). 그래서 줄 전체를 감싸는 기울임은
 * 아예 만들지 않고 평문으로 둔다. 문장 일부만 감싸는 기울임은 안전하다.
 */
function inline(text) {
  let s = esc(text);
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  const whole = s.match(/^\*([^*\n]+)\*$/);            // 줄 전체가 *…* 인 경우
  if (whole) s = whole[1];
  else s = s.replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');

  s = s.replace(/`([^`]+)`/g, '$1');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)');
  return s;
}

export function parseMarkdown(mdPath) {
  const raw = fs.readFileSync(mdPath, 'utf8');
  const fm = raw.match(/^---\n([\s\S]*?)\n---\n/);
  const body = fm ? raw.slice(fm[0].length) : raw;

  const blocks = [];
  let afterImage = false; // 이미지 줄(![](..)) 바로 뒤의 줄 전체 *기울임*은 그 이미지의 캡션
  for (let line of body.split('\n')) {
    line = line.replace(/\s+$/, '');
    if (!line.trim()) continue;
    const img = line.match(/^!\[([^\]]*)\]\(([^)]*)\)$/);
    if (img) { blocks.push({ kind: 'image', alt: img[1], src: img[2] }); afterImage = true; continue; }
    if (afterImage) {
      afterImage = false;
      if (/^\*[^*].*\*$/.test(line)) { blocks.push({ kind: 'caption', text: line.replace(/^\*|\*$/g, '') }); continue; }
    }
    if (/^(---|===|\*\*\*)\s*$/.test(line)) { blocks.push({ kind: 'divider' }); continue; }

    const h = line.match(/^#{1,6}\s+(.*)$/);
    if (h) { blocks.push({ kind: 'heading', text: h[1] }); continue; }

    if (/^>\s?/.test(line)) { blocks.push({ kind: 'quote', text: line.replace(/^>\s?/, '') }); continue; }
    if (/^[-*]\s+/.test(line)) { blocks.push({ kind: 'bullet', text: line.replace(/^[-*]\s+/, '') }); continue; }

    blocks.push({ kind: 'text', text: line });
  }
  return blocks;
}

/**
 * 붙여넣기용 HTML. 문단 사이 여백은 빈 문단으로 만든다
 * (네이버가 margin 을 잘 무시해서, 빈 줄이 가장 확실하다).
 * 소제목 앞은 두 줄, 뒤는 한 줄.
 */
export function toHtml(blocks, opts = {}) {
  const HEAD = opts.headingSize || '19px';
  const BODY = opts.bodySize || '16px';
  const out = [];
  const gap = () => out.push(`<p style="font-size:${BODY}"><br></p>`);
  blocks = blocks.filter((b) => b.kind !== 'image');   // 이미지는 HTML 이 아니라 업로드로 넣는다(fillBodyWithImages)

  blocks.forEach((b, i) => {
    const prev = blocks[i - 1];

    if (b.kind === 'caption') {                        // 이미지 바로 아래 작은 안내 글
      out.push(`<p style="font-size:13px;text-align:center;color:#777">${inline(b.text)}</p>`);
      if (blocks[i + 1] && blocks[i + 1].kind !== 'heading' && blocks[i + 1].kind !== 'divider') gap();
      return;
    }

    if (b.kind === 'divider') {
      if (prev) gap();
      out.push(`<p style="font-size:${BODY};text-align:center">· · ·</p>`);
      gap();
      return;
    }

    if (b.kind === 'heading') {
      if (prev) { gap(); gap(); gap(); }       // 소제목 앞 빈 줄 두 줄 (문단 여백 1 + 추가 2)
      out.push(`<p style="font-size:${HEAD}"><strong>${inline(b.text)}</strong></p>`);
      gap();                                    // 소제목 뒤 한 줄
      return;
    }

    if (b.kind === 'quote') {
      out.push(`<blockquote style="font-size:${BODY}">${inline(b.text)}</blockquote>`);
      gap();
      return;
    }

    if (b.kind === 'bullet') {
      out.push(`<p style="font-size:${BODY}">• ${inline(b.text)}</p>`);
      return;                                   // 불릿끼리는 붙임
    }

    out.push(`<p style="font-size:${BODY}">${inline(b.text)}</p>`);
    if (blocks[i + 1] && blocks[i + 1].kind !== 'heading' && blocks[i + 1].kind !== 'divider') gap();
  });
  if (opts.trailingGap) gap();                         // 바로 뒤에 이미지가 올 때 위쪽 여백

  return out.join('\n');
}

/** 서식 없는 평문(붙여넣기 실패 시 대비용) */
export function toPlain(blocks) {
  return blocks.filter((b) => b.kind !== 'image').map((b) => {
    if (b.kind === 'divider') return '· · ·';
    const t = b.text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1');
    return b.kind === 'bullet' ? `• ${t}` : t;
  }).join('\n\n');
}

/**
 * 클립보드에 HTML+평문을 올리고 에디터에 붙여넣는다.
 * opts.focus=false 면 클릭하지 않는다 — 이미 잡아둔 선택(전체 선택 등)을 유지해야 할 때.
 * (클릭하면 선택이 풀려서 덮어쓰기가 아니라 덧붙이기가 된다.)
 */
export async function pasteHtml(page, frame, html, plain, mod, opts = {}) {
  await page.evaluate(async ({ html, plain }) => {
    const item = new ClipboardItem({
      'text/html': new Blob([html], { type: 'text/html' }),
      'text/plain': new Blob([plain], { type: 'text/plain' }),
    });
    await navigator.clipboard.write([item]);
  }, { html, plain });

  if (opts.focus !== false) {
    const editor = await frame.$('.se-content');
    await editor.click();
    await page.waitForTimeout(500);
  }
  await page.keyboard.press(`${mod}+v`);
  await page.waitForTimeout(2500);
}

/** 이미지 블록 기준으로 본문을 조각낸다. segments.length === images.length + 1 */
export function splitByImages(blocks) {
  const segments = [[]];
  const images = [];
  for (const b of blocks) {
    if (b.kind === 'image') { images.push(b); segments.push([]); } else segments[segments.length - 1].push(b);
  }
  return { segments, images };
}

const IMAGE_BTN = [
  'button.se-toolbar-button-image', 'button[data-name="image"]', 'button[data-log="dot.image"]',
  '.se-toolbar-item-image button', 'button:has-text("사진")',
];

/** 커서 위치에 사진 한 장 업로드(파일선택창을 가로채 Finder 없이). 성공 여부 반환. */
export async function insertOneImage(page, frame, file) {
  let btn = null;
  for (const sel of IMAGE_BTN) {
    try { const el = frame.locator(sel).first(); await el.waitFor({ state: 'visible', timeout: 3000 }); btn = el; break; } catch (e) { /* 다음 셀렉터 */ }
  }
  if (!btn) return false;
  const chooser = page.waitForEvent('filechooser', { timeout: 8000 });
  await btn.click({ force: true }).catch(() => {});
  try { await (await chooser).setFiles([file]); } catch (e) { return false; }
  await page.waitForTimeout(3500);                     // 업로드·삽입 대기
  return true;
}

/**
 * 본문을 이미지 위치(마크다운의 ![](..) 줄)에 맞춰 조각조각 붙여넣고, 그 사이에 사진을 올린다.
 * 사진을 올리면 에디터가 그 아래 새 문단에 커서를 두므로, 다음 조각은 클릭 없이 바로 붙인다.
 * files 는 이미지 블록과 같은 순서·같은 개수여야 한다. opts.focusFirst=false 면 첫 조각도 클릭 없이 붙인다.
 * 반환: { ok, placed } — placed 는 실제로 올라간 사진 수.
 */
export async function fillBodyWithImages(page, frame, blocks, files, mod, opts = {}) {
  const { segments } = splitByImages(blocks);
  const log = opts.log || console.log;
  let placed = 0;
  for (let k = 0; k < segments.length; k++) {
    const seg = segments[k];
    const more = k < segments.length - 1;
    if (seg.length) {
      await pasteHtml(page, frame, toHtml(seg, { trailingGap: more }), toPlain(seg), mod,
        { focus: k === 0 ? opts.focusFirst !== false : false });
    }
    if (more) {
      const ok = await insertOneImage(page, frame, files[k]);
      if (ok) { placed += 1; log(`   🖼️ ${placed}/${segments.length - 1}`); }
      else { log(`⚠️ 사진 ${k + 1} 업로드 실패 — 그 자리에 직접 넣어주세요: ${files[k]}`); }
    }
  }
  return { ok: placed === segments.length - 1, placed };
}

/** 에디터 구성 요소 순서(검증용): 예) "T IMG T IMG T" */
export async function componentOrder(frame) {
  return frame.$$eval('.se-component', (els) => els.map((e) => (/se-image/.test(e.className) ? 'IMG' : /se-text/.test(e.className) ? 'T' : '?')).join(' '));
}

export function summary(blocks) {
  const n = (k) => blocks.filter((b) => b.kind === k).length;
  const chars = blocks.reduce((a, b) => a + (b.text || '').length, 0);
  return `${chars}자 · 소제목 ${n('heading')} · 문단 ${n('text')} · 인용 ${n('quote')}`;
}

export function resolveMd(blogDir, slug) {
  return path.join(blogDir, `${slug}.md`);
}
