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
    # [글 제목](slug) 처럼 slug 만 적은 링크: 발행된 글이면 그 글로, 아니면 글자만 남긴다
    s = re.sub(r"\[([^\]]+)\]\(([a-z0-9][a-z0-9-]*)\)",
               lambda m: (f'<a href="/{SLUG_URL[m.group(2)]}">{m.group(1)}</a>' if m.group(2) in SLUG_URL else m.group(1)), s)
    return s


SLUG_URL = {}


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
        elif ln.startswith("- ") or re.match(r"^\d{1,2}[.)] ", ln):
            if para:
                flush()
            ul.append(ln[2:] if ln.startswith("- ") else ln)
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
    ("한의원 소개", None, [("인사와 소개", "about.html"), ("처음 오시나요?", "first.html"), ("다시 오시나요?", "again.html"),
                        ("우리가 말하는 회복", "about.html#recovery"), ("진료 공간 둘러보기", "gallery.html"), ("방송·영상 보기", "videos.html"), ("나의 회복지도", "again.html#map"),
                        ("자주 묻는 질문", "faq.html"), ("예약·오시는 길", "visit.html"), ("원내 탕전 기록", "herbal-room.html"), ("좋은꿈 네트워크 지점", "network.html")]),
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
<script>window.addEventListener("load",function(){var id="G-EL426GZ3ED";if(id.indexOf("XXXX")>-1)return;setTimeout(function(){var s=document.createElement("script");s.async=1;s.src="https://www.googletagmanager.com/gtag/js?id="+id;document.head.appendChild(s)},1500)});</script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-EL426GZ3ED');</script>'''


FAV_HEAD = '''<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700;800&family=Noto+Sans+KR:wght@400;500;700&display=swap" media="print" onload="this.media='all'">
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
    <a href="{up}index.html" class="brandlink" aria-label="좋은꿈참사랑한의원 홈"><svg class="logo" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22" fill="#1F3552"/><path d="M30 12a13 13 0 1 0 6 21A11 11 0 0 1 30 12z" fill="#FBE78A"/><path d="M8 33c4-6 8-6 12 0s8 6 12 0 6-4 8-2" fill="none" stroke="#90B2DD" stroke-width="2.4" stroke-linecap="round"/></svg></a>
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
            panels.append(f"<div class='gl{cls}'><img src='{up}icons/{ico}.svg' alt='' width='44' height='44'><p class='glt'>{title}</p><ul>" + "".join(f"<li>{E(t)}</li>" for t in lis) + "</ul></div>")
    if len(panels) < 2:
        return ""
    return "<section class='glance' aria-label='한눈에 보기'>" + "".join(panels) + "</section>"


GENERIC_IMGS = None


def _imgs(pattern):
    return sorted(str(x.relative_to(ROOT / "images")).replace("\\", "/") for x in (ROOT / "images").glob(pattern))


def cat_pool(cat):
    """분류별 그림 목록(대표 이미지 hero-* 는 맨 위에 쓰이므로 제외) + 공용 그림."""
    global GENERIC_IMGS
    if GENERIC_IMGS is None:
        GENERIC_IMGS = _imgs("gallery/*.jpg") + _imgs("clinic-*.jpg") + [f for f in _imgs("banner-*.jpg")]
    own = _imgs(f"pool/{cat}-*.jpg") + [f for f in (f"ai-banner-{cat}.jpg", CAT_PHOTO.get(cat, "")) if f and (ROOT / "images" / f).exists()]
    return own + [g for g in GENERIC_IMGS if g not in own]


def thumb_of(rel):
    t = "thumb/" + rel.replace("/", "_")
    return t if (ROOT / "images" / t).exists() else rel


def _h(s):
    return sum(ord(c) * (i + 1) for i, c in enumerate(s))


ASSIGN = {}


def assign_post_images(all_posts):
    """분류별로 글을 slug 순으로 세우고 사진을 하나씩 배정한다(사진이 충분하면 글마다 모두 다르다)."""
    by = {}
    for x in all_posts:
        by.setdefault(x["category"], []).append(x["slug"])
    for cat, slugs in by.items():
        imgs = _imgs(f"post/{cat}-*.jpg")
        if imgs:
            for i, sl in enumerate(sorted(set(slugs))):
                ASSIGN[sl] = imgs[i % len(imgs)]
    hp = [x["file"] for x in herb_photos() if x["kind"] in ("herb", "antler")]
    if hp:
        for i, sl in enumerate(sorted(set(by.get("herbal", [])))):
            HERB_ASSIGN[sl] = hp[(i * 7) % len(hp)]


HERB_ASSIGN = {}


def herb_photos():
    f = ROOT / "images" / "herbpub" / "_list.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def post_img(p):
    """글마다 배정되는 사진. 한약 글은 원장님이 찍은 실제 한약 사진, 그 밖에는 글 제목에 맞춰 만든 images/post2/<slug>.jpg 를 먼저 쓴다."""
    if p["slug"] in HERB_ASSIGN:
        return HERB_ASSIGN[p["slug"]]
    own = f"post2/{p['slug']}.jpg"
    if (ROOT / "images" / own).exists():
        return own
    return ASSIGN.get(p["slug"])


def _card_img(p, i):
    own = post_img(p)
    if own:
        return thumb_of(own)
    pool = cat_pool(p["category"])
    k = (_h(p["slug"]) if i is None else i) % len(pool)
    return thumb_of(pool[k])


def card(p, up, i=None):
    card_href = add_utm(f"{up}{post_url(p)}", "card", p['title'])
    return (f"<a class='card postcard has-thumb' href='{card_href}'><img class='cthumb' src='{up}images/{_card_img(p, i)}' alt='' width='640' height='360' loading='lazy'><div>"
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
# 분류 대표 그림: 실제 사진이 어울리는 분류는 노량진점에서 찍은 사진을 쓴다(사람 얼굴이 가운데 오지 않는 사진 위주)
REAL_HERO = {"first-visit": "real/room-hall1.jpg", "diagnosis": "real/explain-xray.jpg", "herbal": "herbpub/herb-018.jpg",
             "chuna": "real/chuna-press.jpg", "ultrasound": "real/explain-monitor1.jpg", "accident": "real/consult-tablet.jpg",
             "pain": "real/chuna-hip.jpg"}


def hero_html(depth, slug, title, sub="", ai_note=True, img=None):
    """가로 전체를 덮는 큰 이미지 영역. images/hero-<slug>.jpg 가 있으면 그것을, 없으면 배너 사진을 쓴다."""
    up = "../" * depth
    cand = ([img] if img else []) + ([REAL_HERO[slug]] if slug in REAL_HERO else []) + [f"hero-{slug}.jpg", f"ai-banner-{slug}.jpg", CAT_PHOTO.get(slug, "clinic-room1.jpg")]
    name = next((c for c in cand if (ROOT / "images" / c).exists()), "clinic-room1.jpg")
    is_ai = name.startswith(("hero-", "ai-banner-", "post/", "post2/", "pool/"))
    note = "<span class='phero-note'>이미지는 AI로 만든 이미지입니다</span>" if (is_ai and ai_note) else ""
    subp = f"<p class='phero-sub'>{E(sub)}</p>" if sub else ""
    return (f"<section class='phero'><img src='{up}images/{name}' " + (f"srcset='{up}images/{name[:-4]}-sm.jpg 1024w, {up}images/{name} 2000w' sizes='100vw' " if name.startswith(('hero-', 'real/')) and (ROOT / 'images' / (name[:-4] + '-sm.jpg')).exists() else '') + "alt='' width='2000' height='1125' fetchpriority='high'>"
            f"<div class='phero-in'><h1>{re.sub(r' *· *', ' · ', E(title))}</h1>{subp}</div>{note}</section>")


_P = ["treat-director1", "treat-director2", "treat-vice1", "treat-vice2", "leg-check", "room-therapy1", "room-therapy2",
      "chuna-neck1", "chuna-shoulder", "chuna-neck2", "chuna-hip", "chuna-leg", "chuna-neck3", "chuna-neck4", "chuna-press", "treat-check",
      "room-chuna-table", "room-bed1", "room-bed2", "room-bed3", "room-device1", "room-device3"]
_C = ["consult", "director-desk", "vice-desk", "room-consult1", "room-consult2", "exam-monitor",
      "consult-tablet", "explain-spine", "explain-model", "explain-xray", "explain-monitor1", "explain-monitor2", "explain-anatomy", "room-consult3", "room-desk"]
_T = ["duo1", "duo2", "duo4", "team-tray", "team-smile", "team-arms", "team-stand", "team-tv", "team-talk", "doc-wst", "doc-room", "doc-stand", "doc-library", "doc-smile"]
_H = ["herbs", "team-herbset", "team-talk-herb", "team-tray2"]
REAL_BY_CAT = {"pain": _P + ["explain-xray", "explain-spine"], "chuna": _P + ["doc-wst"], "accident": _P + ["consult", "explain-xray", "consult-tablet"],
               "shockwave": _P + ["room-device2"], "ultrasound": ["exam-monitor", "treat-vice1", "treat-vice2", "director-desk", "explain-monitor1", "explain-monitor2", "explain-xray", "room-device2"],
               "diagnosis": _C + ["nose-check"], "first-visit": _C + _T + ["room-therapy1", "room-entrance", "room-hall1", "room-hall2"],
               "herbal": _H + ["consult", "director-desk"], "digestion": ["consult", "herbs", "room-consult1", "consult-tablet", "explain-anatomy"] + _H,
               "metabolic": ["consult", "exam-monitor", "herbs", "director-desk", "consult-tablet", "explain-monitor1"],
               "respiratory": ["nose-check", "consult", "room-consult2", "consult-tablet"], "insomnia": ["consult", "room-consult1", "room-consult2", "room-therapy2", "consult-tablet", "doc-library"],
               "mental": ["consult", "room-consult1", "room-consult2", "director-portrait", "consult-tablet", "doc-library"],
               "neuro": ["consult", "exam-monitor", "treat-director1", "explain-anatomy", "chuna-neck1", "explain-monitor2"],
               "women": ["consult", "room-consult2", "room-therapy2", "herbs", "consult-tablet", "room-bed1"], "pediatric": ["consult", "nose-check", "room-consult1", "consult-tablet"],
               "skin": ["consult", "nose-check", "room-consult2", "consult-tablet"], "local": _T + ["room-entrance", "room-hall1"]}


def body_images(body, cat, slug=""):
    """본문 h2 사이사이에 큰 이미지를 넣어 한 화면마다 그림이 보이게 한다."""
    pool = cat_pool(cat)[:8]
    if not pool:
        return body
    off = _h(slug)
    parts = re.split(r"(?=<h2>)", body)
    real = [f"real/{n}.jpg" for n in REAL_BY_CAT.get(cat, REAL_BY_CAT["first-visit"]) if (ROOT / "images" / "real" / f"{n}.jpg").exists()]
    out, k = [], 0
    for i, part in enumerate(parts):
        if part.startswith("<h2>") and i >= 2 and (i % 2 == 0):
            if k == 0 and real:  # 첫 그림은 실제 한의원 사진(윤작가 촬영)
                r = real[off % len(real)]
                out.append(f"<figure class='bodyimg'><img src='../../images/{r}' srcset='../../images/{r[:-4]}-sm.jpg 1024w, ../../images/{r} 1600w' sizes='(min-width:900px) 860px, 100vw' alt='좋은꿈참사랑한의원 노량진점 진료 모습' loading='lazy'></figure>")
                k += 1
                out.append(part)
                continue
            out.append(f"<figure class='bodyimg'><img src='../../images/{pool[(off + k) % len(pool)]}' alt='' loading='lazy'></figure>")
            k += 1
        out.append(part)
    return "".join(out)


def build_post(p, posts):
    cat = CATS[p["category"]]
    related = [x for x in posts if x["category"] == p["category"] and x["slug"] != p["slug"]][:4]
    idx = [x["slug"] for x in posts].index(p["slug"])
    newer = posts[idx - 1] if idx > 0 else None
    older = posts[idx + 1] if idx + 1 < len(posts) else None
    hero = hero_html(2, p["category"], p["title"], f"{cat} · 좋은꿈참사랑한의원 노량진점 한방가이드", img=post_img(p))
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
        rel = "<section><h2>같은 주제의 글</h2><div class='cardgrid'>" + "".join(card(x, "../../", j + _h(p["slug"])) for j, x in enumerate(related)) + "</div></section>"
    nav_newer = f"<a class='btn' href='{add_utm('../../' + post_url(newer), 'button', '최신-글')}'>← 최신 글</a>" if newer else ""
    nav_older = f"<a class='btn' href='{add_utm('../../' + post_url(older), 'button', '이전-글')}'>이전 글 →</a>" if older else ""
    nav = "<div class='pn'>" + nav_newer + nav_older + "</div>"
    body = f"""{crumbs}
<article>
<p class="meta">작성 {E(CFG['author_label'])}{(' · 감수 ' + E(REV['name']) + ' ' + E(REV['title']) + lic) if p['reviewed'] else ''}<br>발행 {E(p['date'])} · 수정 {E(p['updated'])}</p>
{todo}
<div class="answer"><b>한 줄 답변</b><br>{E(p['summary'])}</div>
{summary_card(p['body'], '../../')}{(f"<figure class='hubinfo'><img src='../../images/info/post-{p['slug']}.svg' alt='{E(p['title'])} 안내 그림' width='1200' height='675' loading='lazy'></figure>" if (ROOT / 'images' / 'info' / f"post-{p['slug']}.svg").exists() else '')}
{body_images(p['body'], p['category'], p['slug'])}
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


_hf = ROOT / "content" / "hubs.json"
HUBS = json.loads(_hf.read_text(encoding="utf-8")) if _hf.exists() else {}


def build_lists(posts):
    up = "../"
    sections = ""
    for ci, (slug, name) in enumerate(CATS.items()):
        items = [p for p in posts if p["category"] == slug]
        if not items:
            continue
        btn_href = add_utm(f"{slug}/index.html", "button", f"{name}-전체-보기")
        sections += f"<section><div class='h2ico'>{icon_img(slug, up)}<h2>{E(name)}</h2></div><div class='cardgrid'>" + "".join(card(x, up, ci * 7 + j) for j, x in enumerate(items[:6])) + "</div>" + \
                    f"<p><a class='btn' href='{btn_href}'>{E(name)} 전체 보기</a></p></section>"
        hub = HUBS.get(slug)
        hub_html, hub_ld, title, desc = "", "", f"{name} — 한방가이드 | {CFG['clinic_name']}", f"{name}에 대한 한방가이드 글 모음"
        if hub:
            secs = "".join(
                f"<h2>{E(s['h2'])}</h2>" + "".join(f"<p>{inline(x)}</p>" for x in s.get("paras", []))
                + ("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in s.get("bullets", [])) + "</ul>" if s.get("bullets") else "")
                for s in hub.get("sections", []))
            faq = "".join(f"<details class='qa'><summary>{E(q['q'])}</summary><p>{inline(q['a'])}</p></details>" for q in hub.get("faq", []))
            info = ROOT / "images" / "info" / f"{slug}.svg"
            info_html = (f"<figure class='hubinfo'><img src='../../images/info/{slug}.svg' alt='{E(name)} 진료 흐름과 먼저 확인할 신호를 정리한 안내 그림' width='1200' height='675' loading='lazy'></figure>"
                         if info.exists() else "")
            hub_html = (f"<p class='lead hublead'>{inline(hub['lead'])}</p>" + info_html + secs
                        + (f"<h2>상도동·노량진에서</h2><p>{inline(hub['local'])}</p>" if hub.get("local") else "")
                        + (f"<section class='faqblock'><h2>자주 묻는 질문</h2>{faq}</section>" if faq else "")
                        + f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호 · 마지막 확인 {TODAY} · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다.</p>"
                        + f"<h2>{E(name)} 글 모아 보기 ({len(items)}편)</h2>")
            hub_ld = jsonld({"@context": "https://schema.org", "@type": "FAQPage",
                             "mainEntity": [{"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in hub.get("faq", [])]})
            title = f"{hub.get('title', name)} | {CFG['clinic_name']}"
            desc = re.sub(r"\s+", " ", hub["lead"])[:150]
        cbody = (f"<nav class='crumbs'><a href='../../index.html'>홈</a> › <a href='../index.html'>한방가이드</a></nav>"
                 + hub_html + "<div class='cardgrid'>" + "".join(card(x, "../../", j) for j, x in enumerate(items)) + "</div>")
        write(ROOT / "guide" / slug / "index.html",
              shell(title, desc, 2, cbody,
                    hub_ld, f"guide/{slug}/index.html", "website", hero=hero_html(2, slug, hub.get("title", name) if hub else name, f"{name}에 대한 한방가이드 {len(items)}편")))
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
            ("about.html", TODAY, "0.8"), ("first.html", TODAY, "0.8"), ("again.html", TODAY, "0.7"), ("faq.html", TODAY, "0.8"), ("visit.html", TODAY, "0.9"), ("network.html", TODAY, "0.6"), ("herbal-room.html", TODAY, "0.7"),
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
    guide_href = add_utm('guide/index.html', 'button', '한방가이드-전체-보기')
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
{tc('clock', '최근 올라온 글 (<span id=\"t-count\"></span> 누적)', "<ul id='t-new' class='newlist'></ul><p><a class='btn' href='" + guide_href + "'>한방가이드 전체 보기</a></p>", 'wide')}
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


SUBPAGES = [  # (파일, 제목, 설명, 대표그림 분류, 부제, 홈에서 가져올 구역 id)
    ("about.html", "한의원 소개", "좋은꿈참사랑한의원 노량진점 대표원장 인사말, 의료진, 진료 원칙과 우리가 말하는 회복", "home",
     "인사말 · 의료진 · 진료 원칙", ["greeting", "about", "pillars", "recovery"]),
    ("first.html", "처음 오시나요?", "좋은꿈참사랑한의원 노량진점 첫 방문 안내: 상담 순서, 준비하면 좋은 것, 편안한 진료", "first-visit",
     "첫 방문 순서와 준비하면 좋은 것", ["first", "equip", "comfort"]),
    ("again.html", "다시 오시나요?", "재진 안내와 나의 회복지도 예시: 지난 이야기부터 이어서 살핍니다", "diagnosis",
     "지난 이야기부터 이어서 살핍니다", ["again", "map"]),
    ("faq.html", "자주 묻는 질문", "좋은꿈참사랑한의원 노량진점 자주 묻는 질문: 예약, 진료시간, 주차, 교통사고, 한약", "first-visit",
     "예약·진료시간·주차·진료 과정", ["faq"]),
    ("visit.html", "예약·오시는 길", "좋은꿈참사랑한의원 노량진점 위치, 진료시간, 네이버 예약, 전화 문의, 지도", "local",
     "진료시간 · 위치 · 예약", ["visit"]),
]


def build_subpages():
    """홈(index.html)의 구역을 메뉴별 단독 페이지로도 만든다(앵커 스크롤 대신 페이지 이동)."""
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    where = {sid: fn for fn, *_r, ids in SUBPAGES for sid in ids}
    for fn, title, desc, cat, sub, ids in SUBPAGES:
        parts = []
        for sid in ids:
            m = re.search(rf'<section id="{sid}"[^>]*>.*?</section>', src, flags=re.S)
            if m:
                parts.append(m.group(0))
        html = "\n".join(parts)
        html = re.sub(r'href="#([\w-]+)"', lambda m: f'href="{"" if where.get(m.group(1)) == fn else where.get(m.group(1), "index.html")}#{m.group(1)}"', html)
        html = html.replace('class="reveal"', 'class="reveal in"')
        body = f"<nav class='crumbs'><a href='index.html'>홈</a> › {E(title)}</nav>\n{html}"
        write(ROOT / fn, shell(f"{title} | {CFG['clinic_name']}", desc, 0, body, "", fn, "website",
                               extra_js='<script src="config.js"></script><script src="app.js"></script>',
                               hero=hero_html(0, cat, title, sub, False)))


BRANCHES = [  # (이름, 주소, 전화, 메모) — 공개된 지점 홈페이지·의료정보 사이트 기준(2026-11 확인)
    ("좋은꿈참사랑한의원 노량진점", "서울 동작구 만양로2길 2 신성빌딩 3층 (상도동)", "02-815-7510", "이 홈페이지의 지점. 네트워크 안에서 심리요법 교육을 맡고 있습니다."),
    ("좋은꿈한의원 서초본점", "서울 서초구 서초중앙로22길 8 행림빌딩 2층", "02-525-7535", "네트워크 본점. 처방·체형교정 교육."),
    ("좋은꿈참사랑한의원 DMC점", "서울 마포구 월드컵북로 230 성산현대상가 2층 203호", "", "운동치료 교육."),
    ("좋은꿈참사랑한의원 광명점", "경기 광명시 광덕산로 5 종합상가 2층", "02-2615-0005", "추나(WST) 교육."),
    ("좋은꿈참사랑한의원 마들점", "서울 노원구 동일로 1530 다모아상가 202호", "02-951-7510", "본초 교육."),
    ("좋은꿈한의원 분당점", "경기 성남시 분당구 성남대로779번길 17 1층", "031-709-2575", "수험생 불면 교육."),
    ("좋은꿈한의원 수지점", "경기 용인시 수지구 손곡로 95 306호", "031-895-5159", ""),
    ("인덕원 좋은꿈한의원", "경기 의왕시 안양판교로 99 스마일타워 4층 404호", "", ""),
    ("좋은꿈 네트워크 발산점", "", "", "수기치료 교육."),
    ("좋은꿈 네트워크 서현점", "", "", "소아 불면 교육."),
    ("좋은꿈 네트워크 양평점", "", "", "노인 불면 교육."),
]


def build_network():
    rows = ""
    for n, a, t, m in BRANCHES:
        tel = f"<br><a href='tel:{re.sub(r'[^0-9]', '', t)}'>{E(t)}</a>" if t else ""
        addr = f"<br>{E(a)}" if a else "<br><span class='note'>주소는 해당 지점에 확인해 주세요</span>"
        rows += f"<div class='card pillar'><b>{E(n)}</b>{addr}{tel}" + (f"<br><span class='note'>{E(m)}</span>" if m else "") + "</div>"
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 좋은꿈 네트워크 지점</nav>"
            "<h2>좋은꿈 네트워크</h2><p>좋은꿈참사랑한의원 노량진점은 <b>좋은꿈 네트워크</b>의 한의원입니다. 네트워크 지점들은 불면, 추나, 본초, 처방, 심리요법 등 분야를 나누어 서로 공부하고 진료 경험을 나눕니다. "
            "지점마다 운영하는 클리닉과 진료시간이 다르니 방문 전 해당 지점에 직접 확인해 주세요.</p>"
            "<figure class='hubinfo'><img src='images/info/network-map.svg' alt='좋은꿈 네트워크 지점 개략도' width='1200' height='675' loading='lazy'></figure>"
            f"<img class='photo soft wide' src='images/real/duo2.jpg' alt='좋은꿈참사랑한의원 노량진점 원장들' loading='lazy'>"
            f"<div class='grid'>{rows}</div>"
            "<p class='note'>지점 정보는 각 지점 홈페이지와 공개된 의료기관 정보를 바탕으로 정리했으며, 바뀔 수 있습니다. 노량진점 진료 문의: 02-815-7510</p>")
    ld = {"@context": "https://schema.org", "@type": "Organization", "name": "좋은꿈 네트워크",
          "member": [{"@type": "MedicalClinic", "name": n, **({"address": a} if a else {}), **({"telephone": t} if t else {})} for n, a, t, _m in BRANCHES]}
    write(ROOT / "network.html", shell(f"좋은꿈 네트워크 지점 안내 | {CFG['clinic_name']}", "좋은꿈한의원·좋은꿈참사랑한의원 네트워크 지점(노량진·서초·DMC·광명·마들·분당·수지·인덕원 등) 주소와 연락처", 0, body,
                                      jsonld(ld), "network.html", "website", hero=hero_html(0, "local", "좋은꿈 네트워크 지점", "함께 공부하고 진료를 나누는 한의원들", False)))


def build_herbroom():
    items = herb_photos()
    if not items:
        return
    def figs(kind, n, cap):
        sel = [x for x in items if x["kind"] == kind][:n]
        return "".join(f"<figure><img src='images/{E(x['file'])}' alt='{E(cap)}' loading='lazy' width='1400' height='756'><figcaption>{E(cap)}</figcaption></figure>" for x in sel)
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 원내 탕전 기록</nav>"
            "<h2>원내 탕전 기록</h2>"
            "<p>좋은꿈참사랑한의원 노량진점의 한약은 원내에서 준비합니다. 진찰과 상담을 거친 뒤 처방이 정해지면, 약재를 한 첩 분량씩 저울에 달아 확인하고 "
            "대표원장이 검수한 뒤 달입니다. 아래 사진은 2026년 7월부터 11월까지 실제 조제 과정에서 찍은 기록입니다.</p>"
            "<figure class='hubinfo'><img src='images/info/herbal-room-flow.svg' alt='진단·상담, 처방, 약재 계량·검수, 원내 탕전 4단계 안내 그림' width='1200' height='675' loading='lazy'></figure>"
            "<p class='note'>사진 속 약재 구성은 환자분마다 다르며, 같은 처방을 권하는 것이 아닙니다. 환자분의 이름과 조제일이 적힌 이름표는 보이지 않도록 잘라 냈습니다.</p>"
            "<h3>약재를 펼쳐 확인합니다</h3><div class='gallery herbgal'>" + figs("herb", 30, "처방에 맞춰 준비한 약재") + "</div>"
            "<h3>녹용은 따로 살핍니다</h3><div class='gallery herbgal'>" + figs("antler", 8, "조제 전에 확인하는 녹용 절편") + "</div>"
            "<h3>무게를 달아 기록합니다</h3><div class='gallery herbgal'>" + figs("scale", 8, "처방 분량을 저울로 확인") + "</div>"
            "<p>한약은 진단과 상담을 거친 뒤에 처방합니다. 복용 중인 약이 있으면 꼭 알려 주세요. 문의 02-815-7510</p>")
    ld = {"@context": "https://schema.org", "@type": "ImageGallery", "name": "좋은꿈참사랑한의원 노량진점 원내 탕전 기록",
          "about": "한약 조제 과정(약재 확인·계량·검수)", "image": [f"{BASE}/images/{x['file']}" for x in items[:20]]}
    write(ROOT / "herbal-room.html", shell(f"원내 탕전 기록 | {CFG['clinic_name']}", "좋은꿈참사랑한의원 노량진점 원내 탕전: 약재 확인, 계량, 대표원장 검수 과정을 실제 사진으로 보여 드립니다.", 0, body,
                                          jsonld(ld), "herbal-room.html", "website", hero=hero_html(0, "herbal", "원내 탕전 기록", "약재를 펼치고, 달아 보고, 확인합니다", False, img="herbpub/herb-018.jpg")))


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
    # 검색·AI 봇은 모두 위의 * 규칙을 따른다(이름별 그룹을 따로 두면 * 의 Disallow 가 적용되지 않음)
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
    assign_post_images(posts + UPCOMING)
    PUB.update(post_url(p) for p in posts)
    SLUG_URL.update({p["slug"]: post_url(p) for p in posts})
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
    build_subpages()
    build_network()
    build_herbroom()
    inject_latest(posts)
    inject_cards("sleep.html", "posts-sleep", {"insomnia"}, posts)
    inject_cards("diet.html", "posts-metabolic", {"metabolic"}, posts)
    print(f"완료({TODAY}): 발행 {len(posts)}편, 예정 {len(UPCOMING)}편 → guide/, today.html, data/posts.json, llms.txt" + (", sitemap.xml, feed.xml, CNAME" if BASE else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
