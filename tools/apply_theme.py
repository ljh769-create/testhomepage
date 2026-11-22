#!/usr/bin/env python3
"""하늘색 테마 적용: 루트 페이지(index/sleep/diet)의 로고·히어로 그림·항목 아이콘을 한 번에 바꿉니다. (한 번만 실행)"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW_LOGO = ('<svg class="logo" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22" fill="#1F3552"/>'
            '<path d="M30 12a13 13 0 1 0 6 21A11 11 0 0 1 30 12z" fill="#FBE78A"/>'
            '<path d="M8 33c4-6 8-6 12 0s8 6 12 0 6-4 8-2" fill="none" stroke="#90B2DD" stroke-width="2.4" stroke-linecap="round"/></svg>')


def ico(name, cls="ico"):
    return f'<img class="{cls}" src="icons/{name}.svg" alt="" width="64" height="64">'


def icon_for_href(href):
    m = {"sleep-onset-difficulty": "moon", "night-urination-sleep": "water", "waking-at-dawn": "clock", "vivid-dreams-unrefreshed": "insomnia"}
    for k, v in m.items():
        if k in href:
            return v
    if href == "sleep.html": return "insomnia"
    if href == "diet.html": return "metabolic"
    m2 = re.match(r"guide/([a-z\-]+)/", href)
    return m2.group(1) if m2 else "first-visit"


def card_links(s):
    """<a class="card ... postcard" href=X><span class="sig">..</span>... → 아이콘이 있는 카드로"""
    def sub(m):
        cls, href, inner = m.group(1), m.group(2), m.group(3)
        icon = icon_for_href(href)
        big = " big" if "pillar" in cls else ""
        return f'<a class="card{big} {cls} has-ico" href="{href}">{ico(icon, "ico lg" if big else "ico")}<div>{inner}</div></a>'
    return re.sub(r'<a class="card ((?:pillar )?postcard)" href="([^"]+)">(<span class="sig">.*?)</a>', sub, s, flags=re.S)


def steps(s, section_id, icons):
    m = re.search(rf'(<section id="{section_id}".*?<ol class="steps">)(.*?)(</ol>)', s, flags=re.S)
    if not m:
        return s
    items = re.findall(r"<li>(.*?)</li>", m.group(2), flags=re.S)
    out = "".join(f'<li>{ico(i)}<div>{t}</div></li>' for i, t in zip(icons, items))
    return s[:m.start(2)] + out + s[m.end(2):]


def has_ico_div(s, bold, icon, cls="card"):
    """<div class="card ..."><b>bold</b>... → 아이콘 카드"""
    pat = re.compile(rf'<div class="({cls}(?: pillar)?)"><b>{re.escape(bold)}</b>(.*?)</div>', re.S)
    def sub(m):
        return f'<div class="{m.group(1)} has-ico">{ico(icon)}<div><b>{bold}</b>{m.group(2)}</div></div>'
    return pat.sub(sub, s, count=1)


def hero_art(s, art, alt):
    new = f'<div class="artwrap"><img class="art" src="art/{art}.svg" alt="{alt}"></div>'
    return re.sub(r'<div class="photowrap">.*?</svg>\s*</div>', new, s, count=1, flags=re.S)


# ---------------- index.html ----------------
f = ROOT / "index.html"
s = f.read_text(encoding="utf-8")
s = re.sub(r'<svg class="logo".*?</svg>', NEW_LOGO, s, count=1, flags=re.S)
s = hero_art(s, "hero", "구름 위에서 잠든 달 캐릭터와 별, 잔잔한 물결")
s = card_links(s)
for bold, icon in [("수면·마음", "insomnia"), ("척추·관절·체형", "chuna"), ("성장·학습", "pediatric"), ("교통사고 후", "accident")]:
    s = has_ico_div(s, bold, icon)
s = steps(s, "first", ["reception", "consult", "exam", "treat", "home"])
s = steps(s, "chuna", ["consult", "exam", "treat", "first-visit"])
for bold, icon in [("진맥", "exam"), ("설진(혀 보기)", "tongue"), ("초음파", "ultrasound")]:
    s = has_ico_div(s, bold, icon)
s = has_ico_div(s, "체외충격파", "shockwave")
for bold, icon in [("증상 너머를 봅니다", "exam"), ("편안해야 회복이 시작됩니다", "mental"), ("온열은 매번 확인합니다", "warm"), ("작은 과정에도 정성", "treat")]:
    s = has_ico_div(s, bold, icon)
# 몸따삶잘 아이콘 행
body = ''.join(f'<div>{ico(i, "ico")}<span>{t}</span></div>' for i, t in
               [("warm", "몸<br>온기"), ("digestion", "소화"), ("insomnia", "잠"), ("water", "대소변"), ("pain", "통증과<br>생활")])
s = re.sub(r'<div class="icons">.*?</div>\s*<p><b>몸</b>', f'<div class="icons">{body}</div>\n    <p><b>몸</b>', s, count=1, flags=re.S)
s = s.replace("<h3>주소</h3>", f'<h3 class="h2ico">{ico("pin", "ico sm")}주소</h3>').replace("<h3>진료시간</h3>", f'<h3 class="h2ico">{ico("clock", "ico sm")}진료시간</h3>')
f.write_text(s, encoding="utf-8")

# ---------------- sleep.html ----------------
f = ROOT / "sleep.html"
s = f.read_text(encoding="utf-8")
s = re.sub(r'<svg class="logo".*?</svg>', NEW_LOGO, s, count=1, flags=re.S)
s = hero_art(s, "sleep", "별이 뜬 밤하늘 아래 포근한 침대와 달")
s = card_links(s)
s = steps(s, "ask", ["clock", "consult", "warm", "first-visit"])
s = s.replace("<h3>주소</h3>", f'<h3 class="h2ico">{ico("pin", "ico sm")}주소</h3>').replace("<h3>진료시간</h3>", f'<h3 class="h2ico">{ico("clock", "ico sm")}진료시간</h3>')
f.write_text(s, encoding="utf-8")

# ---------------- diet.html ----------------
f = ROOT / "diet.html"
s = f.read_text(encoding="utf-8")
s = re.sub(r'<svg class="logo".*?</svg>', NEW_LOGO, s, count=1, flags=re.S)
s = hero_art(s, "diet", "밥, 채소, 국이 차려진 소박한 한 끼와 아침 해")
s = card_links(s)
for bold, icon in [("배고픔의 시간", "clock"), ("배부름의 신호", "metabolic"), ("잠과의 관계", "insomnia"), ("스트레스와 허기", "mental"),
                   ("잠", "insomnia"), ("식사", "metabolic"), ("소화와 대변", "digestion"), ("활동과 몸의 온기", "warm"), ("복용 중인 약", "first-visit"), ("체중 변화", "pain")]:
    s = has_ico_div(s, bold, icon)
s = steps(s, "flow", ["consult", "exam", "treat", "first-visit"])
s = s.replace("<h3>주소</h3>", f'<h3 class="h2ico">{ico("pin", "ico sm")}주소</h3>').replace("<h3>진료시간</h3>", f'<h3 class="h2ico">{ico("clock", "ico sm")}진료시간</h3>')
f.write_text(s, encoding="utf-8")
print("테마 적용 완료")
