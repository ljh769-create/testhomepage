"""안내 그림(1200x675 SVG) 생성기 — 기존 images/info/post-*.svg 와 같은 모양.
사용: python3 tools/info_svg.py <spec.json> <출력 루트>   (spec.json = [{...}, ...], <출력 루트>/images/info/post-<slug>.svg 로 저장)
눈 확인: bash tools/render_sheet.sh <모아보기.png> <svg...>  (크롬 headless 로 2열 모아 보기 렌더 → Read 로 확인)
본보기 spec: 2026-11-26 기둥 글 15장(손목터널·이석증 등) — images/info/post-carpal-tunnel.svg 등
spec 항목:
  slug, title(22자 이하), subtitle, card_title, icon(hand|drops|gauge|thermo|belly|cloud|cycle|spine|elbow|spiral|skin|walk|note),
  steps: [[제목, 설명], ...] 3~4개, records: [문장, 문장, 문장], flags: [문장, ...] 3~6개, flag_note(선택: 주황 상자 아래 안전 문장)
  줄을 직접 나누려면 문장 안에 | 를 넣는다(예: "동작 중 뚝 소리와 함께|갑자기 통증이 생길 때").
글자는 폭을 재서 자동 줄바꿈하고, 칸을 넘으면 오류로 멈춘다(넘침 방지).
"""
import json, sys
from html import escape
from pathlib import Path

SERIF = "'Nanum Myeongjo','Noto Serif KR','Malgun Gothic',serif"
SANS = "'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif"


def tw(s, size):
    w = 0.0
    for ch in s:
        if ch == ' ':
            w += 0.3
        elif ord(ch) < 128:
            w += 0.58 if ch.isalnum() else 0.42
        else:
            w += 1.0
    return w * size


def wrap(s, size, width, max_lines, where):
    if '|' in s:  # 쓰는 사람이 직접 줄을 나눈 경우(자연스러운 끊김)
        out = []
        for part in s.split('|'):
            out += wrap(part.strip(), size, width, max_lines, where)
        if len(out) > max_lines:
            raise SystemExit(f"!! 줄 수 초과({where}, {len(out)}>{max_lines}): {s}")
        return out
    words = s.split(' ')
    lines, cur = [], ''
    for wd in words:
        cand = (cur + ' ' + wd) if cur else wd
        if tw(cand, size) <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = wd
            if tw(cur, size) > width:
                raise SystemExit(f"!! 낱말이 칸보다 김({where}): {wd}")
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        raise SystemExit(f"!! 줄 수 초과({where}, {len(lines)}>{max_lines}): {s}")
    for ln in lines:
        if len(ln.replace(' ', '')) > 22:
            raise SystemExit(f"!! 줄당 22자 초과({where}): {ln}")
    return lines


def text(x, y, lines, size, weight, fill, anchor='start', fam=SANS, lh=None):
    lh = lh or int(size * 1.4)
    sp = ''.join(f'<tspan x="{x}" dy="{0 if i == 0 else lh}">{escape(l)}</tspan>' for i, l in enumerate(lines))
    return f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{sp}</text>'


D, M, L, O = '#1F3552', '#38608F', '#90B2DD', '#E8A33D'


def icon(kind):
    # 왼쪽 그림 칸: x 100~400, y 215~440
    g = []
    if kind == 'hand':
        g.append(f'<rect x="190" y="300" width="130" height="120" rx="40" fill="{L}"/>')
        for i, (x, h) in enumerate([(192, 90), (222, 110), (252, 112), (282, 98)]):
            g.append(f'<rect x="{x}" y="{300 - h + 30}" width="26" height="{h}" rx="13" fill="{L}"/>')
        g.append(f'<rect x="150" y="330" width="60" height="26" rx="13" transform="rotate(-35 180 343)" fill="{L}"/>')
        g.append(f'<rect x="215" y="415" width="80" height="30" rx="8" fill="{M}"/>')
        for cx, cy in [(235, 250), (265, 236), (295, 262)]:
            g.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{O}"/>')
    elif kind == 'drops':
        for cx, cy, s in [(200, 300, 1.0), (290, 260, 0.8), (300, 360, 1.15)]:
            g.append(f'<path d="M{cx} {cy - 55 * s} C{cx + 40 * s} {cy - 5 * s} {cx + 35 * s} {cy + 35 * s} {cx} {cy + 35 * s} C{cx - 35 * s} {cy + 35 * s} {cx - 40 * s} {cy - 5 * s} {cx} {cy - 55 * s} Z" fill="{L}" stroke="{D}" stroke-width="3"/>')
        g.append(f'<rect x="130" y="415" width="240" height="12" rx="6" fill="{L}"/>')
    elif kind == 'gauge':
        g.append(f'<path d="M140 400 A110 110 0 0 1 360 400" fill="none" stroke="{L}" stroke-width="26" stroke-linecap="round"/>')
        g.append(f'<path d="M300 318 A110 110 0 0 1 360 400" fill="none" stroke="{O}" stroke-width="26" stroke-linecap="round"/>')
        g.append(f'<path d="M250 400 L305 335" stroke="{D}" stroke-width="8" stroke-linecap="round"/><circle cx="250" cy="400" r="14" fill="{D}"/>')
    elif kind == 'thermo':
        g.append(f'<rect x="150" y="250" width="34" height="140" rx="17" fill="#FFFFFF" stroke="{D}" stroke-width="5"/><circle cx="167" cy="400" r="28" fill="{M}" stroke="{D}" stroke-width="5"/><rect x="160" y="320" width="14" height="70" fill="{M}"/>')
        g.append(f'<rect x="240" y="300" width="110" height="90" rx="34" fill="{L}"/>')
        for i in range(4):
            g.append(f'<rect x="{242 + i * 27}" y="250" width="24" height="70" rx="12" fill="{L}"/>')
        for cx, cy in [(380, 260), (395, 300), (372, 330)]:
            g.append(f'<path d="M{cx - 8} {cy} L{cx + 8} {cy} M{cx} {cy - 8} L{cx} {cy + 8}" stroke="{M}" stroke-width="3" stroke-linecap="round"/>')
    elif kind == 'belly':
        g.append(f'<path d="M180 230 Q160 330 185 440 L315 440 Q340 330 320 230 Z" fill="{L}"/>')
        g.append(f'<circle cx="250" cy="345" r="40" fill="none" stroke="{D}" stroke-width="5" stroke-dasharray="10 8"/><circle cx="250" cy="345" r="7" fill="{O}"/>')
    elif kind == 'cloud':
        g.append(f'<circle cx="300" cy="260" r="36" fill="#FBE78A"/>')
        g.append(f'<path d="M150 380 Q145 320 205 322 Q220 270 280 290 Q335 285 340 335 Q385 340 375 380 Z" fill="{L}" stroke="{D}" stroke-width="4"/>')
        for x in (190, 240, 290):
            g.append(f'<path d="M{x} 405 L{x - 8} 430" stroke="{M}" stroke-width="5" stroke-linecap="round"/>')
    elif kind == 'cycle':
        g.append(f'<circle cx="250" cy="330" r="95" fill="none" stroke="{L}" stroke-width="18"/>')
        for i in range(12):
            import math
            a = math.radians(i * 30 - 90)
            fill = O if i in (0, 1) else D
            g.append(f'<circle cx="{250 + 95 * math.cos(a):.0f}" cy="{330 + 95 * math.sin(a):.0f}" r="9" fill="{fill}"/>')
        g.append(f'<path d="M250 330 L250 270 M250 330 L295 345" stroke="{D}" stroke-width="7" stroke-linecap="round"/>')
    elif kind == 'spine':
        for i in range(6):
            y = 225 + i * 36
            g.append(f'<rect x="{215 + (i % 2) * 6}" y="{y}" width="70" height="26" rx="9" fill="{L}" stroke="{D}" stroke-width="3"/>')
        g.append(f'<path d="M330 300 Q350 360 335 430" stroke="{O}" stroke-width="4" fill="none" stroke-dasharray="7 7"/>')
    elif kind == 'elbow':
        g.append(f'<path d="M140 260 L250 350 L370 300" stroke="{L}" stroke-width="34" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        g.append(f'<circle cx="250" cy="350" r="26" fill="none" stroke="{O}" stroke-width="5"/>')
    elif kind == 'spiral':
        g.append(f'<path d="M250 330 m0 -10 a10 10 0 1 1 -10 10 a22 22 0 1 1 22 22 a36 36 0 1 1 -36 -36 a52 52 0 1 1 52 52" fill="none" stroke="{M}" stroke-width="8" stroke-linecap="round"/>')
        g.append(f'<path d="M140 250 Q250 190 360 250" fill="none" stroke="{O}" stroke-width="4" stroke-dasharray="8 7"/><path d="M350 238 L362 252 L345 258" fill="none" stroke="{O}" stroke-width="4"/>')
    elif kind == 'skin':
        g.append(f'<rect x="140" y="240" width="220" height="190" rx="30" fill="#F6E7DA" stroke="{D}" stroke-width="3"/>')
        for cx, cy, r in [(200, 300, 26), (290, 290, 18), (250, 370, 30), (320, 380, 14)]:
            g.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#FFFFFF" stroke="{M}" stroke-width="3" stroke-dasharray="4 4"/>')
    elif kind == 'walk':
        g.append(f'<circle cx="200" cy="250" r="18" fill="{D}"/><path d="M200 270 L195 340 L170 410 M195 340 L230 405 M198 290 L165 320 M198 290 L235 315" stroke="{D}" stroke-width="10" fill="none" stroke-linecap="round"/>')
        g.append(f'<rect x="280" y="360" width="110" height="14" rx="6" fill="{M}"/><path d="M292 374 L292 415 M378 374 L378 415" stroke="{M}" stroke-width="8"/>')
        g.append(f'<path d="M245 300 Q265 330 250 360" stroke="{O}" stroke-width="4" fill="none" stroke-dasharray="6 6"/>')
    elif kind == 'nose':
        g.append(f'<rect x="150" y="300" width="200" height="120" rx="18" fill="{L}"/><path d="M200 300 Q250 240 300 300" fill="#FFFFFF" stroke="{D}" stroke-width="4"/>')
        for cx, cy in [(330, 250), (355, 280), (310, 225)]:
            g.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{O}"/>')
    else:  # note
        g.append(f'<rect x="160" y="230" width="180" height="200" rx="14" fill="#FFFFFF" stroke="{D}" stroke-width="4"/>')
        for i in range(5):
            g.append(f'<rect x="185" y="{265 + i * 30}" width="{130 - (i % 2) * 40}" height="8" rx="4" fill="{L}"/>')
        g.append(f'<circle cx="345" cy="410" r="30" fill="#FFFFFF" stroke="{M}" stroke-width="5"/><path d="M345 410 L345 392 M345 410 L360 418" stroke="{M}" stroke-width="5" stroke-linecap="round"/>')
    g.append(text(140, 455, ['※ 단순 그림'], 12, 500, '#4A5D75', 'middle'))
    return ''.join(g)


def build(sp):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="1200" height="675">',
           '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F4F8FC"/><stop offset="1" stop-color="#DCE8F5"/></linearGradient>',
           '<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="6" stdDeviation="9" flood-color="#1F3552" flood-opacity="0.12"/></filter></defs>',
           '<rect width="1200" height="675" fill="url(#bg)"/>',
           '<circle cx="1120" cy="70" r="120" fill="#38608F" opacity="0.10"/><circle cx="60" cy="640" r="90" fill="#90B2DD" opacity="0.18"/>']
    s = sp['slug']
    out.append(text(60, 76, wrap(sp['title'], 40, 1080, 1, s + ' 제목'), 40, 800, D, fam=SERIF))
    out.append(text(60, 114, wrap(sp['subtitle'], 20, 1080, 1, s + ' 부제'), 20, 400, M))
    out.append(f'<rect x="60" y="130" width="64" height="5" rx="2.5" fill="{M}"/>')
    # 왼쪽 흰 카드
    out.append(f'<rect x="60" y="160" width="700" height="320" rx="22" fill="#FFFFFF" filter="url(#sh)"/>')
    out.append(text(90, 200, wrap(sp['card_title'], 19, 640, 1, s + ' 카드 제목'), 19, 800, D))
    out.append(icon(sp.get('icon', 'note')))
    steps = sp['steps']
    if not 3 <= len(steps) <= 4:
        raise SystemExit(f'!! steps 3~4개({s})')
    gap = 56 if len(steps) == 4 else 70
    for i, (lab, desc) in enumerate(steps):
        y = 242 + i * gap
        out.append(f'<circle cx="484" cy="{y}" r="15" fill="{M}"/>')
        out.append(text(484, y + 6, [str(i + 1)], 16, 800, '#FFFFFF', 'middle'))
        out.append(text(508, y - 4, wrap(lab, 15, 236, 1, s + ' 단계'), 15, 800, D))
        out.append(text(508, y + 18, wrap(desc, 13, 236, 1, s + ' 단계 설명'), 13, 400, '#4A5D75'))
    # 아래 남색 카드: 기록
    out.append(f'<rect x="60" y="500" width="700" height="126" rx="22" fill="{D}" filter="url(#sh)"/>')
    out.append(text(90, 536, ['이렇게 기록해 오세요'], 18, 800, '#FBE78A'))
    recs = sp['records']
    if len(recs) != 3:
        raise SystemExit(f'!! records 3개({s})')
    for i, r in enumerate(recs):
        x = 96 + i * 220
        out.append(f'<circle cx="{x}" cy="566" r="5" fill="#FBE78A"/>')
        out.append(text(x + 14, 572, wrap(r, 15, 196, 2, s + ' 기록'), 15, 500, '#FFFFFF', lh=20))
    # 오른쪽 주황 상자
    out.append(f'<rect x="790" y="160" width="350" height="466" rx="22" fill="#FFF7EA" stroke="{O}" stroke-width="2" filter="url(#sh)"/>')
    out.append(f'<circle cx="820" cy="194" r="12" fill="{O}"/>')
    out.append(text(820, 200, ['!'], 17, 800, '#FFFFFF', 'middle'))
    out.append(text(842, 201, ['먼저 확인이 필요한 신호'], 19, 800, '#8A5A12'))
    y = 240
    flags = sp['flags']
    if not 3 <= len(flags) <= 6:
        raise SystemExit(f'!! flags 3~6개({s})')
    for f in flags:
        ls = wrap(f, 15, 286, 3, s + ' 신호')
        out.append(f'<circle cx="820" cy="{y - 6}" r="4.5" fill="{O}"/>')
        out.append(text(834, y, ls, 15, 500, '#5E4520', lh=21))
        y += 21 * len(ls) + 16
    if sp.get('flag_note'):  # 주황 상자 아래쪽 안전 문장(선택)
        ls = wrap(sp['flag_note'], 14, 290, 4, s + ' 안전 문장')
        ny = max(y + 6, 600 - 20 * (len(ls) - 1))
        out.append(f'<rect x="812" y="{ny - 26}" width="306" height="2" fill="{O}" opacity="0.5"/>')
        out.append(text(816, ny, ls, 14, 500, '#8A5A12', lh=20))
        y = ny + 20 * len(ls)
    if y - 16 > 612:
        raise SystemExit(f'!! 주황 상자 넘침({s}): 끝 y={y - 16}')
    out.append(text(600, 652, ['좋은꿈참사랑한의원 · 02-815-7510 · 일반 건강 정보이며 진단·치료를 대신하지 않습니다'], 14, 400, '#5B6E86', 'middle'))
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    specs = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    root = Path(sys.argv[2])
    for sp in specs:
        svg = build(sp)
        (root / 'images/info' / f"post-{sp['slug']}.svg").write_text(svg, encoding='utf-8')
        print('저장', sp['slug'])
