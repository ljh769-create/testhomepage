#!/usr/bin/env python3
"""한방가이드 글 빌더.

사용법:  python build.py
- content/posts/*.md 를 읽어 guide/ 아래에 글 페이지, 목록, 카테고리 페이지를 만들고
  sitemap.xml(base_url이 있을 때), llms.txt 의 글 목록을 갱신합니다.
- 새 글은 content/posts/ 에 .md 파일 하나만 추가하고 이 스크립트를 다시 실행하세요.
"""
import html, json, os, re, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = CFG.get("base_url", "").rstrip("/")
CATS = {c["slug"]: c["name"] for c in CFG["categories"]}
REV = CFG["reviewer"]
E = html.escape

# 오늘(한국 시간). 시험용으로 BUILD_DATE=2026-12-01 처럼 지정할 수 있습니다.
TODAY = os.environ.get("BUILD_DATE") or (datetime.now(timezone.utc) + timedelta(hours=9)).date().isoformat()
UPCOMING = []          # 아직 발행일이 안 된 글 (queue.html 에 표시)


def drip_dates():
    """content/drip.json 의 순서대로 하루 per_day 편씩 발행일을 자동으로 정합니다."""
    f = ROOT / "content" / "drip.json"
    if not f.exists():
        return {}
    order = json.loads(f.read_text(encoding="utf-8")).get("order", [])
    d = CFG.get("drip", {})
    start = date.fromisoformat(d.get("start", TODAY))
    per = max(1, int(d.get("per_day", 1)))
    return {slug: (start + timedelta(days=i // per)).isoformat() for i, slug in enumerate(order)}


DRIP = drip_dates()


# ---------- 간단한 마크다운 ----------
def inline(s):
    s = E(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(((?:https?://|/|\.|#)[^)\s]*)\)", r'<a href="\2">\1</a>', s)
    return s


def render_body(text):
    """returns (html, faq_list)"""
    out, faq, para, ul = [], [], [], []
    lines = text.split("\n")
    i = 0

    def flush():
        nonlocal para, ul
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if ul:
            out.append("<ul class='plain'>" + "".join(f"<li>{inline(x)}</li>" for x in ul) + "</ul>")
            ul = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.strip() == "::: faq":
            flush()
            i += 1
            q = a = None
            items = []
            while i < len(lines) and lines[i].strip() != ":::":
                t = lines[i].strip()
                if t.startswith("Q:"):
                    if q is not None:
                        items.append((q, a or ""))
                    q, a = t[2:].strip(), ""
                elif t.startswith("A:"):
                    a = t[2:].strip()
                elif t and a is not None:
                    a += " " + t
                i += 1
            if q is not None:
                items.append((q, a or ""))
            for q, a in items:
                faq.append((q, a))
                out.append(f"<details class='qa'><summary>{E(q)}</summary><p>{inline(a)}</p></details>")
        elif ln.startswith("## "):
            flush()
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            flush()
            out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("- "):
            if para:
                flush()
            ul.append(ln[2:])
        elif ln.strip() == "":
            flush()
        else:
            if ul:
                flush()
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out), faq


# ---------- 글 읽기 ----------
def load_posts():
    posts = []
    chunks = []
    for f in sorted((ROOT / "content" / "posts").glob("*.md")):
        # 한 파일에 여러 글을 넣을 때는 글 사이에 ===== 한 줄을 둡니다
        for i, part in enumerate(re.split(r"\n={5,}\n", f.read_text(encoding="utf-8").replace("\r\n", "\n").strip())):
            chunks.append((f"{f.name}#{i + 1}", part.strip() + "\n"))
    for name, raw in chunks:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            print(f"[건너뜀] {name}: 머리말(---)이 없습니다"); continue
        meta = {}
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        for req in ("title", "category", "slug", "date", "summary"):
            if not meta.get(req):
                print(f"[건너뜀] {name}: '{req}' 가 없습니다"); meta = None; break
        if meta is None:
            continue
        if meta["category"] not in CATS:
            print(f"[건너뜀] {name}: 알 수 없는 category '{meta['category']}' (site.json 확인)"); continue
        if meta.get("draft", "").lower() in ("true", "yes", "1"):
            print(f"[초안] {name} 은 발행하지 않습니다"); continue
        if meta["slug"] in DRIP:                    # 예약 발행: 순서에 따라 발행일이 정해집니다
            meta["date"] = DRIP[meta["slug"]]
            meta["updated"] = meta["date"]
        meta.setdefault("updated", meta["date"])
        meta["reviewed"] = CFG.get("reviewed_default", False) or meta.get("reviewed", "").lower() in ("yes", "true", "1")
        if meta["date"] > TODAY:                    # 아직 발행일 전
            UPCOMING.append(meta)
            continue
        meta["body"], meta["faq"] = render_body(m.group(2).strip())
        posts.append(meta)
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


# ---------- 상단 메뉴 (분류별 펼침 메뉴) ----------
G = "guide/"
NAV = [
    ("오늘의 리듬", "today.html", None),
    ("한의원 소개", None, [("인사와 소개", "index.html#about"), ("처음 오시나요?", "index.html#first"), ("다시 오시나요?", "index.html#again"),
                        ("우리가 말하는 회복", "index.html#recovery"), ("진료 공간 둘러보기", "gallery.html"), ("방송·영상 보기", "videos.html"), ("나의 회복지도", "index.html#map"), ("자주 묻는 질문", "index.html#faq")]),
    ("불면·수면", "sleep.html", [("불면·수면 안내", "sleep.html"), ("잠들기가 어려울 때", G + "insomnia/sleep-onset-difficulty.html"),
                              ("새벽에 깰 때", G + "insomnia/waking-at-dawn.html"), ("자도 개운하지 않을 때", G + "insomnia/vivid-dreams-unrefreshed.html"),
                              ("자다가 소변으로 깰 때", G + "insomnia/night-urination-sleep.html"), ("코골이·수면무호흡", G + "insomnia/snoring-sleep-apnea.html"),
                              ("수면제를 줄이고 싶을 때", G + "insomnia/reducing-sleeping-pills.html"), ("수면 일기 쓰는 법", G + "insomnia/how-to-keep-sleep-diary.html"),
                              ("자기 전에 읽는 글", G + "insomnia/before-sleep-reading.html"), ("불면 글 전체", G + "insomnia/index.html")]),
    ("대사·식욕", "diet.html", [("대사증후군·식욕 안내", "diet.html"), ("짠 음식과 혈압", G + "metabolic/salty-food-blood-pressure.html"),
                              ("당뇨 전단계 식사", G + "metabolic/prediabetes-meal-order.html"), ("콜레스테롤과 걷기", G + "metabolic/cholesterol-start-walking.html"),
                              ("검진 결과지 읽는 법", G + "metabolic/reading-checkup-results.html"), ("야식을 끊기 어려울 때", G + "metabolic/late-night-eating.html"),
                              ("먹고 나서 자책이 들 때", G + "metabolic/guilt-after-eating.html"), ("잠과 대사의 관계", G + "metabolic/sleep-and-metabolism.html"),
                              ("대사 글 전체", G + "metabolic/index.html")]),
    ("통증·추나", G + "pain/index.html", [("통증 글 전체", G + "pain/index.html"), ("교정추나", G + "chuna/chuna-correction-guide.html"),
                                      ("체외충격파", G + "shockwave/shockwave-guide.html"), ("초음파 진단", G + "ultrasound/ultrasound-guide.html"),
                                      ("허리 통증", G + "pain/low-back-pain-sitting.html"), ("목·어깨", G + "pain/forward-head-neck-stiffness.html"),
                                      ("무릎", G + "pain/knee-stairs-down.html"), ("발바닥", G + "pain/heel-pain-first-steps.html"),
                                      ("추나 글 전체", G + "chuna/index.html"), ("충격파 글 전체", G + "shockwave/index.html"), ("초음파 글 전체", G + "ultrasound/index.html")]),
    ("교통사고 후", G + "accident/index.html", [("교통사고 글 전체", G + "accident/index.html"), ("목·허리 통증", G + "accident/accident-neck-back-pain.html"),
                                           ("목이 삔 경우", G + "accident/accident-neck-sprain.html"), ("어깨와 팔", G + "accident/accident-shoulder-arm.html"),
                                           ("어지럼과 두통", G + "accident/accident-dizziness-headache.html"), ("불안과 잠", G + "accident/accident-anxiety-sleep.html")]),
    ("소화", G + "digestion/index.html", [("소화 글 전체", G + "digestion/index.html"), ("식후 더부룩함", G + "digestion/bloating-after-meals.html"),
                                       ("속쓰림·신물", G + "digestion/heartburn-acid-reflux.html"), ("변비", G + "digestion/chronic-constipation.html"),
                                       ("설사·복통", G + "digestion/diarrhea-after-meals.html"), ("입맛이 없을 때", G + "digestion/loss-of-appetite.html")]),
    ("두통·어지럼", G + "neuro/index.html", [("두통·어지럼·저림 전체", G + "neuro/index.html"), ("긴장성 두통", G + "neuro/tension-headache.html"),
                                          ("편두통", G + "neuro/migraine-daily-record.html"), ("일어설 때 어지럼", G + "neuro/dizziness-on-standing.html"),
                                          ("이명", G + "neuro/tinnitus.html"), ("손발 저림", G + "neuro/hands-feet-numbness.html"), ("만성피로", G + "neuro/chronic-fatigue.html")]),
    ("여성·소아", G + "women/index.html", [("여성 건강 전체", G + "women/index.html"), ("생리통", G + "women/menstrual-pain.html"), ("갱년기", G + "women/menopause-transition.html"),
                                        ("임신 준비", G + "women/preparing-for-pregnancy.html"), ("소아·성장 전체", G + "pediatric/index.html"),
                                        ("아이 키 걱정", G + "pediatric/child-short-stature.html"), ("아이 잠", G + "pediatric/child-sleep-troubles.html"),
                                        ("아이 식욕·편식", G + "pediatric/child-picky-eating.html")]),
    ("비염·피부", G + "respiratory/index.html", [("호흡기 글 전체", G + "respiratory/index.html"), ("재채기·콧물", G + "respiratory/morning-sneezing-runny-nose.html"),
                                              ("오래가는 기침", G + "respiratory/chronic-cough.html"), ("피부 글 전체", G + "skin/index.html"),
                                              ("아토피 가려움", G + "skin/atopic-itching-daily-care.html"), ("두드러기", G + "skin/sudden-hives.html")]),
    ("스트레스·불안", G + "mental/index.html", [("스트레스·불안 전체", G + "mental/index.html"), ("가슴 두근거림", G + "mental/palpitations-anxiety.html"),
                                            ("번아웃", G + "mental/burnout-exhaustion.html"), ("스트레스와 장", G + "mental/stress-gut-symptoms.html")]),
    ("한방가이드", G + "index.html", [("한방가이드 전체", G + "index.html"), ("처음 오시는 분", G + "first-visit/index.html"),
                                    ("복용 약 정리하기", G + "first-visit/prepare-medication-list.html"), ("증상 메모하는 법", G + "first-visit/how-to-note-symptoms.html"),
                                    ("한약 먹기 전 알릴 것", G + "first-visit/before-taking-herbal-medicine.html")]),
    ("오시는 길", "index.html#visit", None),
]


PUB = set()   # 지금 실제로 발행된 guide/ 페이지 (메뉴에서 아직 없는 글로 가는 링크를 빼기 위함)


def add_utm(url, medium, content):
    """URL에 UTM 매개변수 추가 (내부 링크만)"""
    if not url or url.startswith("#") or url.startswith("tel:") or url.startswith("javascript:"):
        return url
    base, hash_, frag = url.partition("#")
    sep = "&" if "?" in base else "?"
    content_encoded = content.replace(" ", "-").replace("/", "-")
    return f"{base}{sep}utm_source=gooddreamclinic&utm_campaign=homepage&utm_medium={medium}&utm_content={content_encoded}{hash_}{frag}"


def _exists(h):
    h = h.split("#")[0]
    return not h.startswith("guide/") or h in PUB


def nav_html(up):
    bar, panels = [], []
    for i, (label, href, kids) in enumerate(NAV):
        if kids:
            kids = [(t, h) for t, h in kids if _exists(h)]
        if kids is not None and not kids:
            if href and _exists(href):
                href_utm = add_utm(f"{up}{href}", "nav", label)
                bar.append(f'<a class="mi" href="{href_utm}">{E(label)}</a>')
            continue
        if kids:
            bar.append(f'<button type="button" class="mi has" data-panel="p{i}" aria-expanded="false" aria-controls="p{i}">{E(label)} ▾</button>')
            lis = "".join(f'<li><a href="{add_utm(up + h, "nav", t)}">{E(t)}</a></li>' for t, h in kids)
            panels.append(f'<div class="panel" id="p{i}" hidden><ul>{lis}</ul></div>')
        else:
            href_utm = add_utm(f"{up}{href}", "nav", label)
            bar.append(f'<a class="mi" href="{href_utm}">{E(label)}</a>')
    home_href = add_utm(f"{up}index.html", "nav", "홈")
    return ('<nav class="menu" aria-label="메뉴"><div class="menubar"><a class="mi" href="' + home_href + '">홈</a>' + "".join(bar) +
            '</div><div class="panels">' + "".join(panels) + '</div></nav>')


def inject_nav():
    for name in ("index.html", "sleep.html", "diet.html"):
        f = ROOT / name
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")
        block = "<!--nav-->" + nav_html("") + "<!--/nav-->"
        if "<!--nav-->" in src:
            new = re.sub(r"<!--nav-->.*?<!--/nav-->", lambda m: block, src, flags=re.S)
        else:
            new = re.sub(r'<nav class="menu" aria-label="메뉴">.*?</nav>', lambda m: block, src, flags=re.S)
        if new != src:
            f.write_text(new, encoding="utf-8")


# ---------- 공통 틀 ----------
def jsonld(obj):
    return '<script type="application/ld+json">\n' + json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/") + "\n</script>"


GA_HEAD = '''<meta name="google-site-verification" content="">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-XXXXXXXXXX');</script>'''


FAV_HEAD = '''<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700;800&family=Noto+Sans+KR:wght@400;500;700&display=swap">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#1F3552">'''


def shell(title, desc, depth, body, head_extra="", canonical_path=None, og_type="article",
          robots="index,follow,max-snippet:-1,max-image-preview:large", extra_js="", hero=""):
    up = "../" * depth
    og_img = (BASE + "/images/clinic-room1.jpg") if BASE else up + "images/hero.jpg"
    canon = f'<link rel="canonical" href="{E(BASE + "/" + canonical_path)}">' if BASE and canonical_path else ""
    og_url = f'<meta property="og:url" content="{E(BASE + "/" + canonical_path)}">' if BASE and canonical_path else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="{og_img}">
<meta name="twitter:card" content="summary_large_image">
{og_url}{canon}
{head_extra}
{GA_HEAD}
{FAV_HEAD}
<link rel="stylesheet" href="{up}style.css">
<script>document.documentElement.className+=" js";</script>
</head>
<body>
<header class="top">
  <div class="bar">
    <a href="{up}index.html" class="brandlink"><svg class="logo" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22" fill="#1F3552"/><path d="M30 12a13 13 0 1 0 6 21A11 11 0 0 1 30 12z" fill="#FBE78A"/><path d="M8 33c4-6 8-6 12 0s8 6 12 0 6-4 8-2" fill="none" stroke="#90B2DD" stroke-width="2.4" stroke-linecap="round"/></svg></a>
    <div><b>좋은꿈참사랑한의원</b><br><span>노량진점 · 한방가이드</span></div>
    <a class="call" id="top-call" href="tel:{re.sub(r'[^0-9+]', '', CFG['phone'])}">전화 문의</a>
  </div>
  {nav_html(up)}
</header>
{hero}
<main class="wrap article">
{body}
</main>
<footer class="wrap foot"><p class="note">{E(CFG['clinic_name'])} · {E(CFG['address'])} · {E(CFG['phone'])}</p></footer>
<script src="{up}app-lite.js"></script>
<script src="{up}comfort.js"></script>
{extra_js}
</body>
</html>
"""


def post_url(p):
    return f"guide/{p['category']}/{p['slug']}.html"


def icon_img(cat, up, cls="ico"):
    return f"<img class='{cls}' src='{up}icons/{cat}.svg' alt='' width='64' height='64' loading='lazy'>"


CAT_PHOTO = {"insomnia": "banner-room2-1.jpg", "mental": "banner-room2-2.jpg", "neuro": "banner-room2-3.jpg", "pain": "banner-therapy1-1.jpg", "chuna": "banner-therapy2-1.jpg", "ultrasound": "banner-therapy1-2.jpg", "accident": "banner-therapy2-2.jpg", "shockwave": "banner-therapy1-3.jpg", "digestion": "banner-herbs-1.jpg", "metabolic": "banner-herbs-2.jpg", "herbal": "banner-herbs-3.jpg", "women": "banner-room1-1.jpg", "pediatric": "banner-room1-2.jpg", "respiratory": "banner-room1-3.jpg", "skin": "banner-herbroom-2.jpg", "first-visit": "banner-therapy2-3.jpg", "diagnosis": "banner-herbroom-1.jpg", "local": "banner-herbroom-3.jpg"}
GLANCE = [("먼저 이렇게 여쭙니다", "여쭙는 것", "consult", ""), ("일상에서 먼저 해 볼 수 있는 것", "생활에서 해 볼 것", "home", ""),
          ("한의원에서 함께 살필 수 있는 경우", "한의원에서 함께 살필 것", "treat", ""), ("먼저 확인이 필요", "먼저 확인이 필요한 신호", "exam", " check")]


def summary_card(body, up):
    parts = re.split(r"(?=<h2>)", body)
    panels = []
    for key, title, ico, cls in GLANCE:
        sec = next((x for x in parts if x.startswith("<h2>") and key in re.sub(r"<[^>]+>", "", x.split("</h2>")[0])), None)
        if not sec:
            continue
        lis = [re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<li>(.*?)</li>", sec, re.S)][:3]
        lis = [(t[:46].rstrip() + "…") if len(t) > 48 else t for t in lis if t.strip()]
        if lis:
            panels.append(f"<div class='gl{cls}'><img src='{up}icons/{ico}.svg' alt='' width='44' height='44'><h3>{title}</h3><ul>" + "".join(f"<li>{E(t)}</li>" for t in lis) + "</ul></div>")
    if len(panels) < 2:
        return ""
    return "<section class='glance' aria-label='한눈에 보기'>" + "".join(panels) + "</section>"


def card(p, up):
    card_href = add_utm(f"{up}{post_url(p)}", "card", p['title'])
    return (f"<a class='card postcard has-ico' href='{card_href}'>{icon_img(p['category'], up)}<div>"
            f"<span class='sig'>{E(CATS[p['category']])}</span><br>"
            f"<b>{E(p['title'])}</b><br><span class='note'>{E(p['summary'])}</span><br>"
            f"<span class='note'>수정 {E(p['updated'])}</span></div></a>")


def reviewer_person():
    person = {"@type": "Person", "name": REV["name"], "jobTitle": REV["title"]}
    if REV.get("license"):
        person["identifier"] = f"한의사 면허번호 {REV['license']}"
    return person


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------- 페이지 만들기 ----------
def hero_html(depth, slug, title, sub="", ai_note=True):
    """가로 전체를 덮는 큰 이미지 영역. images/hero-<slug>.jpg 가 있으면 그것을, 없으면 배너 사진을 쓴다."""
    up = "../" * depth
    cand = [f"hero-{slug}.jpg", f"ai-banner-{slug}.jpg", CAT_PHOTO.get(slug, "clinic-room1.jpg")]
    name = next((c for c in cand if (ROOT / "images" / c).exists()), "clinic-room1.jpg")
    is_ai = name.startswith(("hero-", "ai-banner-"))
    note = "<span class='phero-note'>이미지는 AI로 만든 이미지입니다</span>" if (is_ai and ai_note) else ""
    subp = f"<p class='phero-sub'>{E(sub)}</p>" if sub else ""
    return (f"<section class='phero'><img src='{up}images/{name}' alt='' width='2000' height='1125' fetchpriority='high'>"
            f"<div class='phero-in'><h1>{E(title)}</h1>{subp}</div>{note}</section>")


def build_post(p, posts):
    cat = CATS[p["category"]]
    related = [x for x in posts if x["category"] == p["category"] and x["slug"] != p["slug"]][:4]
    idx = [x["slug"] for x in posts].index(p["slug"])
    newer = posts[idx - 1] if idx > 0 else None
    older = posts[idx + 1] if idx + 1 < len(posts) else None
    hero = hero_html(2, p["category"], p["title"], f"{cat} · 좋은꿈참사랑한의원 노량진점 한방가이드")
    lic = f" (한의사 면허번호 {E(REV['license'])})" if REV.get("license") else ""
    todo = "" if REV.get("license") else "<!-- 입력 필요: site.json 의 reviewer.license (면허번호) -->"
    crumbs = (f"<nav class='crumbs' aria-label='현재 위치'><a href='../../index.html'>홈</a> › "
              f"<a href='../index.html'>한방가이드</a> › <a href='index.html'>{E(cat)}</a></nav>")
    faq_block = ""
    if p["faq"]:
        faq_block = "<section class='faqblock'><h2>자주 묻는 질문</h2>" + "".join(
            f"<details class='qa'><summary>{E(q)}</summary><p>{inline(a)}</p></details>" for q, a in p["faq"]) + "</section>"
        # 본문 안에 faq 블록이 이미 렌더되어 있으면 중복 방지
        p["body"] = re.sub(r"(<details class='qa'>.*?</details>\s*)+", "", p["body"], flags=re.S)
    rel = ""
    if related:
        rel = "<section><h2>같은 주제의 글</h2>" + "".join(card(x, "../../") for x in related) + "</section>"
    nav_newer = f"<a class='btn' href='{add_utm('../../' + post_url(newer), 'button', '최신-글')}'>← 최신 글</a>" if newer else ""
    nav_older = f"<a class='btn' href='{add_utm('../../' + post_url(older), 'button', '이전-글')}'>이전 글 →</a>" if older else ""
    nav = "<div class='pn'>" + nav_newer + nav_older + "</div>"
    body = f"""{crumbs}
<article>
<p class="meta">작성 {E(CFG['author_label'])}{(' · 감수 ' + E(REV['name']) + ' ' + E(REV['title']) + lic) if p['reviewed'] else ''}<br>발행 {E(p['date'])} · 수정 {E(p['updated'])}</p>
{todo}
<div class="answer"><b>한 줄 답변</b><br>{E(p['summary'])}</div>
{summary_card(p['body'], '../../')}
{p['body']}
{faq_block}
<p class="disclaimer">{E(CFG['disclaimer'])}</p>
<div class="card pillar"><b>지난 이야기부터 이어서 묻습니다</b><br>{E(CFG['clinic_name'])}은 재진 때 지난번 이야기부터 이어서 여쭙니다. 진료시간과 예약은 <a href="../../index.html#visit">오시는 길</a>에서 확인하세요.</div>
</article>
{rel}
{nav}"""
    graph = [
        {"@type": "MedicalWebPage", "name": p["title"], "headline": p["title"], "description": p["summary"],
         "inLanguage": "ko", "datePublished": p["date"], "dateModified": p["updated"],
         "author": {"@type": "MedicalClinic", "name": CFG["clinic_name"]},
         "publisher": {"@type": "MedicalClinic", "name": CFG["clinic_name"], "telephone": "+82-" + CFG["phone"].lstrip("0")},
         "isPartOf": {"@type": "CollectionPage", "name": "한방가이드"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈"},
            {"@type": "ListItem", "position": 2, "name": "한방가이드"},
            {"@type": "ListItem", "position": 3, "name": cat},
            {"@type": "ListItem", "position": 4, "name": p["title"]}]},
    ]
    if p["reviewed"]:
        graph[0]["reviewedBy"] = reviewer_person()
        graph[0]["lastReviewed"] = p["updated"]
    if BASE:
        graph[0]["url"] = f"{BASE}/{post_url(p)}"
    if p["faq"]:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\*\*|\[|\]\([^)]*\)", "", a)}} for q, a in p["faq"]]})
    write(ROOT / post_url(p),
          shell(f"{p['title']} — {CFG['clinic_name']} 한방가이드", p["summary"], 2, body,
                jsonld({"@context": "https://schema.org", "@graph": graph}), post_url(p), hero=hero))


def build_lists(posts):
    up = "../"
    sections = ""
    for slug, name in CATS.items():
        items = [p for p in posts if p["category"] == slug]
        if not items:
            continue
        btn_href = add_utm(f"{slug}/index.html", "button", f"{name}-전체-보기")
        sections += f"<section><div class='h2ico'>{icon_img(slug, up)}<h2>{E(name)}</h2></div>" + "".join(card(p, up) for p in items[:6]) + \
                    f"<p><a class='btn' href='{btn_href}'>{E(name)} 전체 보기</a></p></section>"
        cbody = (f"<nav class='crumbs'><a href='../../index.html'>홈</a> › <a href='../index.html'>한방가이드</a></nav>"
                 "" + "".join(card(p, "../../") for p in items))
        write(ROOT / "guide" / slug / "index.html",
              shell(f"{name} — 한방가이드 | {CFG['clinic_name']}", f"{name}에 대한 한방가이드 글 모음", 2, cbody,
                    "", f"guide/{slug}/index.html", "website", hero=hero_html(2, slug, name, f"{name}에 대한 한방가이드 {len(items)}편")))
    body = ("<nav class='crumbs'><a href='../index.html'>홈</a> › 한방가이드</nav>"
            ""
            "<p>일상의 말로 쓴 한방 건강 정보입니다. 모든 글은 일반적인 정보이며 진단이나 치료를 대신하지 않습니다.</p>"
            f"<p class='note'>글 {len(posts)}편</p>" + sections +
            "<p class='note imgnote'>이 페이지의 사진은 AI로 만든 예시 이미지입니다.</p>")
    itemlist = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "한방가이드",
                "hasPart": [{"@type": "WebPage", "name": p["title"]} for p in posts]}
    write(ROOT / "guide" / "index.html",
          shell(f"한방가이드 — {CFG['clinic_name']}", "통증·추나, 다이어트·대사 등 일상의 말로 쓴 한방 건강 정보 모음", 1, body,
                jsonld(itemlist), "guide/index.html", "website", hero=hero_html(1, "home", "한방가이드", f"일상의 말로 쓴 한방 건강 정보 {len(posts)}편")))


def build_sitemap(posts):
    path = ROOT / "sitemap.xml"
    if not BASE:
        print("[안내] site.json 의 base_url 이 비어 있어 sitemap.xml 은 만들지 않았습니다.")
        return
    urls = [("index.html", TODAY, "1.0"), ("today.html", TODAY, "0.9"), ("sleep.html", TODAY, "0.9"), ("diet.html", TODAY, "0.9"), ("gallery.html", TODAY, "0.7"), ("videos.html", TODAY, "0.7"),
            ("guide/index.html", max([p["updated"] for p in posts] or [TODAY]), "0.9")]
    urls += [(f"guide/{c}/index.html", max(p["updated"] for p in posts if p["category"] == c), "0.7")
             for c in CATS if any(p["category"] == c for p in posts)]
    urls += [(post_url(p), p["updated"], "0.7") for p in posts]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f"  <url><loc>{E(BASE + '/' + u)}</loc><lastmod>{lm}</lastmod><priority>{pr}</priority></url>\n" for u, lm, pr in urls) + "</urlset>\n"
    write(path, xml)


def build_llms(posts):
    path = ROOT / "llms.txt"
    base = path.read_text(encoding="utf-8") if path.exists() else ""
    base = base.split("## 한방가이드 글")[0].rstrip() + "\n\n"
    lines = ["## 한방가이드 글", "인용 시 출처: 좋은꿈참사랑한의원 노량진점. 일반 건강 정보이며 진단·치료를 대신하지 않습니다. 매일 새 글이 올라옵니다.", ""]
    for p in posts:
        lines.append(f"- [{p['title']}]({post_url(p)}): {p['summary']} (수정 {p['updated']})")
    write(path, base + "\n".join(lines) + "\n")


def inject_latest(posts):
    f = ROOT / "index.html"
    src = f.read_text(encoding="utf-8")
    cards = "".join(card(p, "") for p in posts[:5])
    new = re.sub(r"<!--latest-->.*?<!--/latest-->", lambda m: "<!--latest-->\n" + cards + "\n  <!--/latest-->", src, flags=re.S)
    if new != src:
        f.write_text(new, encoding="utf-8")


def inject_cards(filename, marker, cats, posts):
    """sleep.html, diet.html 같은 대표 페이지 안의 <!--posts-이름--> 자리에 분류별 글 카드를 채웁니다."""
    f = ROOT / filename
    if not f.exists():
        return
    src = f.read_text(encoding="utf-8")
    items = [p for p in posts if p["category"] in cats]
    cards = "".join(card(p, "") for p in items)
    new = re.sub(rf"<!--{marker}-->.*?<!--/{marker}-->", lambda m: f"<!--{marker}-->\n{cards}\n  <!--/{marker}-->", src, flags=re.S)
    if new != src:
        f.write_text(new, encoding="utf-8")


def write_posts_json(posts):
    data = [{"t": p["title"], "u": post_url(p), "c": p["category"], "n": CATS[p["category"]], "d": p["date"]} for p in posts]
    write(ROOT / "data" / "posts.json", json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def build_today(posts):
    tc = lambda ico, title, inner, cls="": (f"<div class='tcard {cls}'><h3 class='h2ico'>{icon_img(ico, '', 'ico sm')}{title}</h3>{inner}</div>")
    body = f"""<nav class='crumbs'><a href='index.html'>홈</a> › 오늘의 리듬</nav>
<h1 class='atitle'>오늘의 리듬</h1>
<p>매일 자정(한국 시간)에 바뀌는 달·해·절기, 오늘의 한 줄, 새로 올라온 글을 한 화면에 모았습니다. 한방가이드에는 매일 새 글이 올라옵니다.</p>
<div class='todaygrid' data-today data-up=''>
{tc('clock', '오늘', "<div id='t-date'></div>", 'wide')}
{tc('moon', '오늘의 달', "<div id='t-moon' class='moonrow'></div>")}
{tc('warm', '오늘의 해 (서울)', "<div id='t-sun'></div><p class='note' id='t-sunnote'></p>")}
{tc('insomnia', '오늘의 잠', "<p class='tline' id='t-sleep'></p>")}
{tc('metabolic', '오늘의 식욕', "<p class='tline' id='t-appetite'></p>")}
{tc('mental', '오늘의 위로', "<p class='tline' id='t-comfort'></p>")}
{tc('first-visit', '이 절기에', "<div id='t-term'></div>")}
{tc('first-visit', '오늘의 글', "<div id='t-posts'></div>", 'wide')}
{tc('clock', '최근 올라온 글 (<span id=\"t-count\"></span> 누적)', "<ul id='t-new' class='newlist'></ul><p><a class='btn' href='{add_utm('guide/index.html', 'button', '한방가이드-전체-보기')}'>한방가이드 전체 보기</a></p>", 'wide')}
</div>
<p class='note'>달 모양, 일출·일몰, 절기는 날짜로 계산한 값이며 해마다 하루, 몇 분 정도 차이가 날 수 있습니다. 오늘의 한 줄은 일반적인 생활 안내이며 진단이나 치료를 대신하지 않습니다.</p>"""
    write(ROOT / "today.html",
          shell(f"오늘의 리듬 — 달·해·절기와 오늘의 한 줄 | {CFG['clinic_name']}",
                "매일 바뀌는 오늘의 달, 서울 일출·일몰, 절기, 오늘의 잠·식욕·위로 한 줄과 새로 올라온 한방가이드 글", 0, body,
                "", "today.html", "website", extra_js="<script src='today.js'></script>"))


def build_gallery():
    f = ROOT / "content" / "gallery.json"
    if not f.exists():
        return
    items = json.loads(f.read_text(encoding="utf-8"))
    cats = []
    for it in items:
        if it["cat"] not in cats:
            cats.append(it["cat"])
    sections = ""
    for c in cats:
        figs = "".join(f"<figure><img src='{E(i['src'])}' alt='{E(i['alt'])}' loading='lazy'><figcaption>{E(i['alt'])}</figcaption></figure>" for i in items if i["cat"] == c)
        sections += f"<section><h2>{E(c)}</h2><div class='gallery'>{figs}</div></section>"
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 진료 공간 둘러보기</nav>"
            "<p>오시기 전에 한의원의 모습을 미리 보실 수 있게 실제 사진을 모았습니다.</p>" + sections)
    write(ROOT / "gallery.html", shell(f"진료 공간 둘러보기 | {CFG['clinic_name']}", "좋은꿈참사랑한의원 노량진점의 진료실, 치료실, 약제실, 의료진, 입구 사진", 0, body, "", "gallery.html", "website", hero=hero_html(0, "first-visit", "진료 공간 둘러보기", "오시기 전에 한의원의 모습을 미리 보세요", False)))


def build_videos():
    f = ROOT / "content" / "videos.json"
    if not f.exists():
        return
    items = json.loads(f.read_text(encoding="utf-8"))
    cards = ""
    ld = []
    for i, v in enumerate(items):
        cards += (f"<figure class='vid'><video controls preload='none' playsinline poster='{E(v['poster'])}'>"
                  f"<source src='{E(v['file'])}' type='video/mp4'></video><figcaption>{E(v['title'])}</figcaption></figure>")
        ld.append({"@type": "VideoObject", "name": v["title"], "description": "좋은꿈참사랑한의원 노량진점 영상. 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다.",
                   "thumbnailUrl": f"{BASE}/{v['poster']}", "contentUrl": f"{BASE}/{v['file']}", "uploadDate": TODAY, "inLanguage": "ko"})
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 방송·영상 보기</nav>"
            "<p>방송 출연 영상과 한의원 소개 영상입니다. 일반적인 건강 정보이며 진단이나 치료를 대신하지 않습니다.</p>"
            f"<div class='vidgrid'>{cards}</div>")
    write(ROOT / "videos.html", shell("방송·영상 보기 | " + CFG["clinic_name"], "좋은꿈참사랑한의원 노량진점의 방송 출연 영상과 소개 영상", 0, body,
                                     jsonld({"@context": "https://schema.org", "@graph": ld}), "videos.html", "website", hero=hero_html(0, "home", "방송·영상 보기", "방송 출연과 한의원 소개 영상")))


def build_queue():
    items = sorted(UPCOMING, key=lambda p: (p["date"], p["slug"]))
    rows = "".join(f"<tr><td>{E(p['date'])}</td><td>{E(CATS[p['category']])}</td><td>{E(p['title'])}</td></tr>" for p in items)
    body = (f"<h1 class='atitle'>발행 예정 목록</h1><p class='note'>오늘({TODAY}) 이후에 자동으로 올라갈 글입니다. 하루 {CFG.get('drip', {}).get('per_day', 1)}편씩 순서대로 발행됩니다. "
            f"(원장님 확인용, 검색에 노출되지 않는 페이지)</p><p><b>예정 {len(items)}편</b></p>"
            f"<div class='tablewrap'><table class='qtable'><thead><tr><th>발행일</th><th>분류</th><th>제목</th></tr></thead><tbody>{rows}</tbody></table></div>")
    write(ROOT / "queue.html", shell(f"발행 예정 목록 | {CFG['clinic_name']}", "발행 예정 글 목록", 0, body, "", None, "website", robots="noindex,nofollow"))


def build_feed(posts):
    if not BASE:
        return
    items = "".join(
        f"<item><title>{E(p['title'])}</title><link>{E(BASE + '/' + post_url(p))}</link><guid>{E(BASE + '/' + post_url(p))}</guid>"
        f"<pubDate>{datetime.fromisoformat(p['date']).strftime('%a, %d %b %Y 06:00:00 +0900')}</pubDate><description>{E(p['summary'])}</description></item>"
        for p in posts[:30])
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{E(CFG["clinic_name"])} 한방가이드</title>'
           f'<link>{E(BASE)}/</link><description>매일 올라오는 한방 건강 정보</description><language>ko</language>{items}</channel></rss>\n')
    write(ROOT / "feed.xml", xml)


def build_site_files():
    """robots.txt, CNAME(사용자 지정 도메인)"""
    lines = ["User-agent: *", "Allow: /", "Disallow: /admin.html", "Disallow: /queue.html", ""]
    for bot in ("GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        lines += [f"User-agent: {bot}", "Allow: /"]
    if BASE:
        lines += ["", f"Sitemap: {BASE}/sitemap.xml"]
        write(ROOT / "CNAME", BASE.split("//", 1)[-1] + "\n")
    write(ROOT / "robots.txt", "\n".join(lines) + "\n")


def main():
    posts = load_posts()
    if not posts:
        print("발행할 글이 없습니다."); return 1
    slugs = [p["slug"] for p in posts]
    dup = {s for s in slugs if slugs.count(s) > 1}
    if dup:
        print("slug 중복:", dup); return 1
    PUB.update(post_url(p) for p in posts)
    PUB.add("guide/index.html")
    PUB.update(f"guide/{c}/index.html" for c in {p["category"] for p in posts})
    # 발행 전(예약) 글의 페이지가 남아 있지 않도록 guide/ 는 매번 새로 만듭니다.
    import shutil
    if (ROOT / "guide").exists():
        shutil.rmtree(ROOT / "guide")
    for p in posts:
        build_post(p, posts)
    build_lists(posts)
    build_sitemap(posts)
    build_llms(posts)
    write_posts_json(posts)
    build_today(posts)
    build_queue()
    build_gallery()
    build_videos()
    build_feed(posts)
    build_site_files()
    inject_nav()
    inject_latest(posts)
    inject_cards("sleep.html", "posts-sleep", {"insomnia"}, posts)
    inject_cards("diet.html", "posts-metabolic", {"metabolic"}, posts)
    print(f"완료({TODAY}): 발행 {len(posts)}편, 예정 {len(UPCOMING)}편 → guide/, today.html, data/posts.json, llms.txt" + (", sitemap.xml, feed.xml, CNAME" if BASE else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
