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
sys.path.insert(0, str(ROOT / "tools"))
import imgsize as _imgsize  # 그림 가로·세로(PIL 없이)

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
    # 하루 발행 수를 바꿀 때: change_from 전까지는 예전 속도(per_day), 그날부터는 새 속도(per_day_after).
    # 이미 발행된 글의 날짜가 뒤로 밀려 사라지지 않게 하기 위함.
    cf = d.get("change_from")
    per2 = max(1, int(d.get("per_day_after", per)))
    out, day, used = {}, start, 0
    for slug in order:
        cur = per2 if (cf and day >= date.fromisoformat(cf)) else per
        if used >= cur:
            day += timedelta(days=1); used = 0
            cur = per2 if (cf and day >= date.fromisoformat(cf)) else per
        out[slug] = day.isoformat()
        DRIP_SLOT[slug] = (used, cur)
        used += 1
    return out


DRIP_SLOT = {}  # slug → (그날 몇 번째, 그날 총 편수)
DRIP = drip_dates()
NOW_HOUR = int(os.environ.get("BUILD_HOUR") or (datetime.now(timezone.utc) + timedelta(hours=9)).hour)


def drip_due_today(slug):
    """원장님 지시(2026-11-25 '종일 계속 올려'): 오늘 몫은 한꺼번에 말고 하루 동안 시간에 맞춰 나눠 공개한다."""
    i, n = DRIP_SLOT.get(slug, (0, 1))
    return i < -(-n * (NOW_HOUR + 1) // 24)


# ---------- 간단한 마크다운 ----------
PARA_MAX = 200  # 한 단락 최대 글자 수(검색·답변엔진이 인용하기 좋은 길이). 넘으면 문장 경계에서 나눈다(글자는 그대로).


def _plain_len(md):
    t = re.sub(r"\[([^\]]+)\]\([^)\s]*\)", r"\1", md)
    return len(t.replace("**", "").replace("<br>", ""))


def split_para(md, limit=PARA_MAX):
    """마크다운 한 단락을 문장 경계에서 limit 글자 이하 묶음들로 나눈다. 문장 하나가 limit 보다 길면 그대로 둔다.
    굵게(**)·링크가 문장 사이에 걸치면 나누지 않는다. 낱말은 하나도 바꾸지 않는다."""
    if _plain_len(md) <= limit:
        return [md]
    sents = [x for x in re.split(r"(?<=[.!?。…])\s+(?=\S)", md) if x]
    out, cur = [], ""
    for sn in sents:
        cand = (cur + " " + sn) if cur else sn
        if cur and _plain_len(cand) > limit and cur.count("**") % 2 == 0 and cur.count("[") == cur.count("]"):
            out.append(cur)
            cur = sn
        else:
            cur = cand
    if cur:
        out.append(cur)
    # 너무 짧은 꼬리(40자 미만)는 앞 묶음에 붙인다(단, 붙여도 limit 를 넘지 않을 때만)
    if len(out) > 1 and _plain_len(out[-1]) < 40 and _plain_len(out[-2] + " " + out[-1]) <= limit:
        out[-2:] = [out[-2] + " " + out[-1]]
    return out


def paras_html(md, fmt=None):
    fmt = fmt or inline
    return "".join("<p>" + fmt(x) + "</p>" for x in split_para(md))


def inline(s):
    s = E(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(((?:https?://|/|\.|#)[^)\s]*)\)", r'<a href="\2">\1</a>', s)
    # [글 제목](slug) 처럼 slug 만 적은 링크: 발행된 글이면 그 글로, 아니면 글자만 남긴다
    s = re.sub(r"\[([^\]]+)\]\(([a-z0-9][a-z0-9-]*)\)",
               lambda m: (f'<a href="/{SLUG_URL[m.group(2)]}">{m.group(1)}</a>' if m.group(2) in SLUG_URL else m.group(1)), s)
    return s


def render_doc(text):
    """원장님 원고(content/director/*.md) → HTML. ## 소제목, ### 작은 소제목, > 인용, | 표 |, - 목록, 빈 줄 문단."""
    out, blk = [], []
    lines = [l.rstrip() for l in re.sub(r"<!--.*?-->", "", text, flags=re.S).split("\n")]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:])}</h3>"); i += 1; continue
        if ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>"); i += 1; continue
        if ln.startswith("> "):
            out.append(f"<blockquote class='dquote'><p>{inline(ln[2:])}</p></blockquote>"); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            head = "".join(f"<th scope='col'>{inline(c)}</th>" for c in rows[0])
            body = "".join("<tr>" + "".join((f"<th scope='row'>{inline(c)}</th>" if j == 0 else f"<td>{inline(c)}</td>") for j, c in enumerate(r)) + "</tr>" for r in rows[1:])
            out.append(f"<div class='tablewrap'><table class='doctable'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"); continue
        if ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:]); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>"); continue
        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", ">", "|", "- ")):
            para.append(lines[i]); i += 1
        out.append(paras_html(" ".join(para), lambda x: inline(x).replace("&lt;br&gt;", "<br>")))
    return "".join(out)


SLUG_URL = {}


def render_body(text):
    """returns (html, faq_list)"""
    out, faq, para, ul = [], [], [], []
    lines = text.split("\n")
    i = 0

    def flush():
        nonlocal para, ul
        if para:
            out.append(paras_html(" ".join(para)))
            para = []
        if ul:
            out.append("<ul class='plain'>" + "".join(f"<li>{inline(x)}</li>" for x in ul) + "</ul>")
            ul = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.strip() == "::: clinic":  # '원장님 진료실에서' 상자
            flush()
            i += 1
            box = []
            while i < len(lines) and lines[i].strip() != ":::":
                box.append(lines[i])
                i += 1
            inner, _ = render_body("\n".join(box))
            out.append("<aside class='clinicnote' aria-label='원장님 진료실에서'><p class='cnhead'>원장님 진료실에서</p>" + inner + "</aside>")
            i += 1
            continue
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
                out.append(f"<details class='qa'><summary>{E(q)}</summary>{paras_html(a)}</details>")
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
            meta["updated"] = max(meta.get("updated", ""), meta["date"])  # 보강한 글은 frontmatter updated 유지
        meta.setdefault("updated", meta["date"])
        meta["reviewed"] = CFG.get("reviewed_default", False) or meta.get("reviewed", "").lower() in ("yes", "true", "1")
        if meta["date"] > TODAY or (meta["date"] == TODAY and meta["slug"] in DRIP and not drip_due_today(meta["slug"])):  # 아직 발행 전
            UPCOMING.append(meta)
            continue
        meta["body"], meta["faq"] = render_body(m.group(2).strip())
        posts.append(meta)
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


# ---------- 상단 메뉴 (분류별 펼침 메뉴) ----------
G = "guide/"
NAV = [
    ("진료안내", "treatments.html", None),
    ("오늘의 리듬", "today.html", None),
    ("한의원 소개", None, [("인사와 소개", "about.html"), ("처음 오시나요?", "first.html"), ("다시 오시나요?", "again.html"), ("진맥 이야기", "pulse.html"), ("원장 칼럼: 두 손목 이야기", "column-pulse.html"), ("공진단 이야기", "gongjindan.html"), ("원장 칼럼: 낙상과 걷기", "column-fall-walking.html"), ("원장 칼럼: 양생 이야기", "column-keep-health.html"),
                        ("우리가 말하는 회복", "about.html#recovery"), ("진료 공간 둘러보기", "gallery.html"), ("방송·영상 보기", "videos.html"), ("지역 건강 강연", "lectures.html"), ("나의 회복지도", "again.html#map"),
                        ("자주 묻는 질문", "faq.html"), ("예약·오시는 길", "visit.html"), ("원내 탕전 기록", "herbal-room.html"), ("좋은꿈 네트워크 지점", "network.html")]),
    ("불면·수면", "sleep.html", [("불면·수면 안내", "sleep.html"), ("잠들기가 어려울 때", G + "insomnia/sleep-onset-difficulty.html"),
                              ("새벽에 깰 때", G + "insomnia/waking-at-dawn.html"), ("자도 개운하지 않을 때", G + "insomnia/vivid-dreams-unrefreshed.html"),
                              ("자다가 소변으로 깰 때", G + "insomnia/night-urination-sleep.html"), ("코골이·수면무호흡", G + "insomnia/snoring-sleep-apnea.html"),
                              ("수면제를 줄이고 싶을 때", G + "insomnia/reducing-sleeping-pills.html"), ("수면 일기 쓰는 법", G + "insomnia/how-to-keep-sleep-diary.html"),
                              ("자기 전에 읽는 글", G + "insomnia/before-sleep-reading.html"), ("불면 글 전체", G + "insomnia/index.html")]),
    ("대사·식욕", "diet.html", [("대사증후군·식욕 안내", "diet.html"), ("인바디 이야기", "inbody.html"), ("짠 음식과 혈압", G + "metabolic/salty-food-blood-pressure.html"),
                              ("당뇨 전단계 식사", G + "metabolic/prediabetes-meal-order.html"), ("콜레스테롤과 걷기", G + "metabolic/cholesterol-start-walking.html"),
                              ("검진 결과지 읽는 법", G + "metabolic/reading-checkup-results.html"), ("야식을 끊기 어려울 때", G + "metabolic/late-night-eating.html"),
                              ("먹고 나서 자책이 들 때", G + "metabolic/guilt-after-eating.html"), ("잠과 대사의 관계", G + "metabolic/sleep-and-metabolism.html"),
                              ("당뇨 전단계·혈당", G + "metabolic/prediabetes-blood-sugar.html"), ("고혈압 생활", G + "metabolic/high-blood-pressure-daily.html"), ("지방간", G + "metabolic/fatty-liver-checkup.html"),
                              ("대사 글 전체", G + "metabolic/index.html")]),
    ("통증·추나", G + "pain/index.html", [("통증 글 전체", G + "pain/index.html"), ("침 치료·사암침", "acupuncture.html"), ("교정추나", G + "chuna/chuna-correction-guide.html"),
                                      ("체외충격파", G + "shockwave/shockwave-guide.html"), ("초음파 진단", G + "ultrasound/ultrasound-guide.html"),
                                      ("허리 통증", G + "pain/low-back-pain-sitting.html"), ("목·어깨", G + "pain/forward-head-neck-stiffness.html"),
                                      ("무릎", G + "pain/knee-stairs-down.html"), ("발바닥", G + "pain/heel-pain-first-steps.html"),
                                      ("목디스크·팔 저림", G + "pain/neck-arm-numbness.html"), ("척추관 협착증", G + "pain/spinal-stenosis.html"), ("손목터널증후군", G + "pain/carpal-tunnel.html"), ("팔꿈치 통증", G + "pain/tennis-elbow.html"),
                                      ("추나 글 전체", G + "chuna/index.html"), ("충격파 글 전체", G + "shockwave/index.html"), ("초음파 글 전체", G + "ultrasound/index.html")]),
    ("교통사고 후", G + "accident/index.html", [("교통사고 글 전체", G + "accident/index.html"), ("목·허리 통증", G + "accident/accident-neck-back-pain.html"),
                                           ("목이 삔 경우", G + "accident/accident-neck-sprain.html"), ("어깨와 팔", G + "accident/accident-shoulder-arm.html"),
                                           ("어지럼과 두통", G + "accident/accident-dizziness-headache.html"), ("불안과 잠", G + "accident/accident-anxiety-sleep.html")]),
    ("소화", G + "digestion/index.html", [("소화 글 전체", G + "digestion/index.html"), ("식후 더부룩함", G + "digestion/bloating-after-meals.html"),
                                       ("속쓰림·신물", G + "digestion/heartburn-acid-reflux.html"), ("변비", G + "digestion/chronic-constipation.html"),
                                       ("설사·복통", G + "digestion/diarrhea-after-meals.html"), ("입맛이 없을 때", G + "digestion/loss-of-appetite.html"), ("과민성 장", G + "digestion/irritable-bowel.html")]),
    ("두통·어지럼", G + "neuro/index.html", [("두통·어지럼·저림 전체", G + "neuro/index.html"), ("긴장성 두통", G + "neuro/tension-headache.html"),
                                          ("편두통", G + "neuro/migraine-daily-record.html"), ("일어설 때 어지럼", G + "neuro/dizziness-on-standing.html"), ("빙빙 도는 어지럼·이석증", G + "neuro/vertigo-spinning-bppv.html"),
                                          ("이명", G + "neuro/tinnitus.html"), ("손발 저림", G + "neuro/hands-feet-numbness.html"), ("만성피로", G + "neuro/chronic-fatigue.html")]),
    ("여성·소아", G + "women/index.html", [("여성 건강 전체", G + "women/index.html"), ("생리통", G + "women/menstrual-pain.html"), ("갱년기", G + "women/menopause-transition.html"),
                                        ("임신 준비", G + "women/preparing-for-pregnancy.html"), ("생리불순", G + "women/irregular-periods.html"), ("산후 회복", G + "women/postpartum-recovery.html"),
                                        ("수족냉증", G + "women/cold-hands-feet.html"), ("다낭성 난소", G + "women/pcos-cycle.html"), ("소아·성장 전체", G + "pediatric/index.html"),
                                        ("아이 키 걱정", G + "pediatric/child-short-stature.html"), ("아이 잠", G + "pediatric/child-sleep-troubles.html"),
                                        ("아이 식욕·편식", G + "pediatric/child-picky-eating.html"), ("잦은 감기", G + "pediatric/child-frequent-colds.html"), ("야뇨", G + "pediatric/child-bedwetting.html"), ("아이 복통", G + "pediatric/child-tummy-ache-where-when-notes.html")]),
    ("비염·피부", G + "respiratory/index.html", [("호흡기 글 전체", G + "respiratory/index.html"), ("재채기·콧물", G + "respiratory/morning-sneezing-runny-nose.html"),
                                              ("오래가는 기침", G + "respiratory/chronic-cough.html"), ("축농증·코막힘", G + "respiratory/chronic-sinusitis.html"), ("쉰 목소리", G + "respiratory/hoarse-voice-overuse.html"), ("피부 글 전체", G + "skin/index.html"),
                                              ("아토피 가려움", G + "skin/atopic-itching-daily-care.html"), ("두드러기", G + "skin/sudden-hives.html"), ("여드름", G + "skin/recurrent-acne.html"), ("건선", G + "skin/psoriasis.html"), ("한포진", G + "skin/dyshidrotic-eczema.html"), ("지루성 두피", G + "skin/scalp-oily-washing-habit.html")]),
    ("스트레스·불안", G + "mental/index.html", [("스트레스·불안 전체", G + "mental/index.html"), ("가슴 두근거림", G + "mental/palpitations-anxiety.html"),
                                            ("번아웃", G + "mental/burnout-exhaustion.html"), ("스트레스와 장", G + "mental/stress-gut-symptoms.html"), ("공황 같은 발작", G + "mental/panic-like-episodes.html"), ("우울감", G + "mental/low-mood-depression.html"), ("화병", G + "mental/held-in-anger-chest-heat-rising.html")]),
    ("한방가이드", G + "index.html", [("한방가이드 전체", G + "index.html"), ("공진단 이야기", "gongjindan.html"), ("처음 오시는 분", G + "first-visit/index.html"),
                                    ("복용 약 정리하기", G + "first-visit/prepare-medication-list.html"), ("증상 메모하는 법", G + "first-visit/how-to-note-symptoms.html"),
                                    ("한약 먹기 전 알릴 것", G + "first-visit/before-taking-herbal-medicine.html")]),
    ("오시는 길", "index.html#visit", None),
]


PUB = set()   # 지금 실제로 발행된 guide/ 페이지 (메뉴에서 아직 없는 글로 가는 링크를 빼기 위함)


def add_utm(url, medium, content):
    """내부 링크에는 UTM을 붙이지 않는다(GA4가 새 세션을 만들고 실제 유입 경로를 덮어씀).
    위치 구분은 <a>의 data-link-location 속성 → comfort.js가 link_location 이벤트 파라미터로 보낸다.
    호출부 호환을 위해 이름은 남겨 두고 URL을 그대로 돌려준다."""
    return url


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
                bar.append(f'<a class="mi" data-link-location="nav" href="{href_utm}">{E(label)}</a>')
            continue
        if kids:
            bar.append(f'<button type="button" class="mi has" data-panel="p{i}" aria-expanded="false" aria-controls="p{i}">{E(label)} ▾</button>')
            lis = "".join(f'<li><a data-link-location="nav" href="{add_utm(up + h, "nav", t)}">{E(t)}</a></li>' for t, h in kids)
            panels.append(f'<div class="panel" id="p{i}" hidden><ul>{lis}</ul></div>')
        else:
            href_utm = add_utm(f"{up}{href}", "nav", label)
            bar.append(f'<a class="mi" data-link-location="nav" href="{href_utm}">{E(label)}</a>')
    home_href = add_utm(f"{up}index.html", "nav", "홈")
    return ('<nav class="menu" aria-label="메뉴"><div class="menubar"><a class="mi" data-link-location="nav" href="' + home_href + '">홈</a>' + "".join(bar) +
            '</div><div class="panels">' + "".join(panels) + '</div></nav>')


def inject_gsv():
    """구글 서치콘솔 인증 코드: site.json 의 google_site_verification 한 곳에서만 관리. 비어 있으면 태그를 넣지 않는다."""
    code = CFG.get("google_site_verification", "")
    for name in ("index.html", "sleep.html", "diet.html"):
        f = ROOT / name
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")
        new = re.sub(r'<meta name="google-site-verification" content="[^"]*">\n?', "", src)
        if code:
            new = new.replace("<meta charset=\"utf-8\">", f"<meta charset=\"utf-8\">\n<meta name=\"google-site-verification\" content=\"{code}\">", 1)
        if new != src:
            f.write_text(new, encoding="utf-8")


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
FOOT_LINKS = ('<p class="note"><a href="https://booking.naver.com/booking/13/bizes/1043468" target="_blank" rel="noopener">네이버 예약</a>'
              ' · <a href="https://pf.kakao.com/_UWxnvb/chat" target="_blank" rel="noopener">카카오톡 상담</a>'
              ' · <a href="https://blog.naver.com/cham_sr" target="_blank" rel="noopener">네이버 블로그(cham_sr)</a>'
              ' · <a href="https://blog.naver.com/dream7510" target="_blank" rel="noopener">네이버 블로그(dream7510)</a>'
              ' · <a href="/privacy.html">개인정보처리방침</a> · <a href="/terms.html">이용약관</a></p>')


# 사업자등록상 정식 이름(네이버 플레이스와 같음). 화면에는 쓰지 않고 구조화 데이터 legalName 에만 넣는다(2026-11-25 원장님).
LEGAL_NAME = "좋은꿈참사랑한의원 노량진점"


def clinic_ld(fn, title, desc, kind="WebPage", extra=None):
    """메인의 MedicalClinic(@id #clinic)을 참조하는 구조화 데이터. visit 는 주소·영업시간·전화까지 넣는다."""
    cid = (BASE or "") + "/#clinic"
    node = {"@type": "MedicalClinic", "@id": cid, "name": CFG["clinic_name"], "legalName": LEGAL_NAME, "url": (BASE or "") + "/", "telephone": "+82-2-815-7510"}
    if kind == "visit":
        try:
            src = (ROOT / "index.html").read_text(encoding="utf-8")
            m = re.search(r'<script type="application/ld\+json">(.*?)</script>', src, flags=re.S)
            g = json.loads(m.group(1).replace("<\\/", "</"))
            for n in g.get("@graph", [g]):
                if str(n.get("@id", "")).endswith("#clinic"):
                    for k in ("address", "openingHoursSpecification", "geo", "hasMap"):
                        if k in n:
                            node[k] = n[k]
        except Exception:
            node["address"] = {"@type": "PostalAddress", "streetAddress": "만양로2길 2 신성빌딩 3층·5층", "addressLocality": "동작구", "addressRegion": "서울특별시", "addressCountry": "KR"}
    page = {"@type": "FAQPage" if kind == "faq" else "WebPage", "@id": (BASE or "") + "/" + fn, "url": (BASE or "") + "/" + fn,
            "name": title, "description": desc, "inLanguage": "ko", "about": {"@id": cid}, "publisher": {"@id": cid}}
    if extra:
        page.update(extra)
    return jsonld({"@context": "https://schema.org", "@graph": [node, page]})


def faq_entities(html):
    out = []
    for q, a in re.findall(r'<details class=["\']qa["\']><summary>(.*?)</summary>(.*?)</details>', html, flags=re.S):
        t = lambda x: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x.replace("</p><p>", " "))).strip()
        out.append({"@type": "Question", "name": t(q), "acceptedAnswer": {"@type": "Answer", "text": t(a)}})
    return out

def jsonld(obj):
    return '<script type="application/ld+json">\n' + json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/") + "\n</script>"


GA_HEAD = (f'<meta name="google-site-verification" content="{CFG.get("google_site_verification", "")}">\n' if CFG.get("google_site_verification") else "") + '''
<script>window.addEventListener("load",function(){var id="G-EL426GZ3ED";if(id.indexOf("XXXX")>-1)return;setTimeout(function(){var s=document.createElement("script");s.async=1;s.src="https://www.googletagmanager.com/gtag/js?id="+id;document.head.appendChild(s)},1500)});</script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-EL426GZ3ED');</script>'''


FAV_HEAD = '''<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" media="print" onload="this.media='all'">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="alternate" type="application/rss+xml" title="좋은꿈참사랑한의원 한방가이드" href="/feed.xml">
<meta name="theme-color" content="#1F3552">'''


def quick_actions(up, pos):
    """전화·네이버 예약·오시는 길 한 줄 버튼(페이지 위·끝). data-cta 는 예약·전화 클릭(GA4 booking_click·call_click)의 위치,
    data-link-location 은 오시는 길(내부 링크) 클릭 위치로 쓰인다(comfort.js). 하단 고정 바(.actbar)와 이름이 겹치지 않게 한다."""
    tel = re.sub(r"[^0-9+]", "", CFG["phone"])
    loc = f"quick_{pos}"
    return (f"<div class='quickacts qa-{pos}' data-cta='{loc}' role='group' aria-label='전화·네이버 예약·오시는 길 바로가기'>"
            f"<a class='qbtn qtel' href='tel:{tel}' data-link-location='{loc}'>전화<span class='qnum'> {E(CFG['phone'])}</span></a>"
            f"<a class='qbtn qbook' href='{BOOK_URL}' target='_blank' rel='noopener' data-link-location='{loc}'>네이버 예약</a>"
            f"<a class='qbtn qmap' href='{up}visit.html' data-link-location='{loc}'>오시는 길</a></div>")


def with_actions(body, up, actions):
    """본문 맨 위(경로 표시 바로 아래, 또는 <!--quick--> 자리)와 맨 끝에 바로가기 줄을 넣는다.
    actions: True(위·끝), "top"(위만 — 글 페이지는 끝에 예약 상자가 이미 있음), False(넣지 않음)."""
    if not actions or "<!--noquick-->" in body:  # 글 페이지: 하단 고정 예약 바가 있어 맨 위 버튼 줄은 생략
        return body
    top = quick_actions(up, "top")
    if "<!--quick-->" in body:
        body = body.replace("<!--quick-->", top, 1)
    else:
        m = re.match(r"\s*<nav class='crumbs'[^>]*>.*?</nav>", body, flags=re.S)
        body = (body[:m.end()] + top + body[m.end():]) if m else top + body
    if actions != "top":
        body += quick_actions(up, "end")
    return body


TITLE_ENDS = [  # 긴 질문형 글 제목의 끝말을 같은 뜻의 짧은 꼴로(검색 결과 제목 60자 안). 본문 H1·og:title 은 원래 제목 그대로.
    (r"때는? 어떻게 살피나요\?$", "때 살펴볼 점"),
    (r"(추나|체외충격파) 상담은 어떻게 하나요\?$", r"\1 상담 안내"),
    (r"때는? 어떻게 하나요\?$", "때 할 일"),
    (r"때는? 무엇을 먼저 살피나요\?$", "때 먼저 살필 것"),
]


def post_title_tag(p, limit=60):
    """글의 <title>. 15~60자 안에 한의원 이름이 들어가게 한다.
    머리말에 seo_title 이 있으면 그것을 쓰고, 없으면 원래 제목 + 이름 → 짧은 이름 꼬리 → 끝말 줄이기 → 낱말 경계 말줄임 순."""
    name = CFG["clinic_name"]
    s1, s2 = f" — {name} 한방가이드", f" | {name}"
    t = (p.get("seo_title") or p["title"]).strip()
    if name in t and len(t) <= limit:
        return t
    if len(t) + len(s1) <= limit:
        return t + s1
    room = limit - len(s2)
    for pat, rep in TITLE_ENDS:
        if len(t) <= room:
            break
        t = re.sub(pat, rep, t)
    if len(t) <= room:
        return t + s2
    return t[:room - 1].rsplit(" ", 1)[0].rstrip(",") + "…" + s2


def meta_desc(desc, body=""):
    """검색 설명(meta description)을 50~160자로. 길면 문장(없으면 낱말) 경계에서 자르고,
    짧으면 본문의 첫 실제 문장을 이어 붙인다(글에 있는 문장만 쓴다)."""
    d = re.sub(r"\s+", " ", html.unescape(desc or "")).strip()
    if len(d) < 50 and body:
        txt = " ".join(html.unescape(re.sub(r"<[^>]+>", "", m)) for m in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S))
        for sn in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", txt)):
            sn = sn.strip()
            if len(sn) >= 15 and sn not in d and not re.search(r"AI로 만든|이미지입니다|©|Copyright", sn):
                d = (d.rstrip(" .") + ". " if d else "") + sn
                if len(d) >= 50:
                    break
    if len(d) > 160:
        cut = d[:160]
        ends = [m.end() for m in re.finditer(r"[.!?。](?=\s|$)", cut)]
        if ends and ends[-1] >= 50:
            d = cut[:ends[-1]].strip()
        else:
            sp = cut[:159].rfind(" ")
            d = (cut[:sp] if sp >= 50 else cut[:159]).rstrip(" ,·") + "…"
    return d


def shell(title, desc, depth, body, head_extra="", canonical_path=None, og_type="article",
          robots="index,follow,max-snippet:-1,max-image-preview:large", extra_js="", hero="", og_image=None, actions=True, og_title=None):
    up = "../" * depth
    body = with_actions(body, up, actions)
    og_img = (BASE + "/images/clinic-room1.jpg") if BASE else up + "images/hero.jpg"
    if og_image and BASE and not og_image.endswith(".svg"):  # 글 대표 사진(SVG는 SNS 미리보기가 안 되므로 기본 사진)
        og_img = f"{BASE}/images/{og_image}"
    canon = f'<link rel="canonical" href="{E(BASE + "/" + canonical_path)}">' if BASE and canonical_path else ""
    og_url = f'<meta property="og:url" content="{E(BASE + "/" + canonical_path)}">' if BASE and canonical_path else ""
    desc = meta_desc(desc, body)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(short_title(title))}</title>
<meta name="description" content="{E(desc)}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{E(og_title or title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="{og_img}">
<meta property="og:image:alt" content="좋은꿈참사랑한의원 진료 공간">
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
    <div><b>좋은꿈참사랑한의원</b><br><span>상도역 · 한방가이드</span></div>
    <a class="call" id="top-call" href="tel:{re.sub(r'[^0-9+]', '', CFG['phone'])}">전화 문의</a>
  </div>
  {nav_html(up)}
</header>
{hero}
<main class="wrap article">
{body}
</main>
<footer class="wrap foot"><p class="note">{E(CFG['clinic_name'])} · {E(CFG['address'])} · {E(CFG['phone'])}</p>{FOOT_LINKS}</footer>
<script src="{up}app-lite.js"></script>
<script src="{up}comfort.js"></script>
<script src="{up}extras.js" defer></script>
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


def summary_table(body):
    """글의 네 구역(여쭙는 것·생활에서 해 볼 것·함께 살필 것·먼저 확인)을 표 한 장으로 정리한다. 글에 있는 문장만 쓴다."""
    parts = re.split(r"(?=<h2>)", body)
    rows = []
    for key, title, _ico, _cls in GLANCE:
        sec = next((x for x in parts if x.startswith("<h2>") and key in re.sub(r"<[^>]+>", "", x.split("</h2>")[0])), None)
        if not sec:
            continue
        lis = [re.sub(r"<[^>]+>", "", m).strip() for m in re.findall(r"<li>(.*?)</li>", sec, re.S)][:2]
        lis = [t for t in lis if t]
        if lis:
            rows.append(f"<tr><th scope='row'>{E(title)}</th><td>{'<br>'.join(E(t) for t in lis)}</td></tr>")
    if len(rows) < 3:
        return ""
    return ("<section class='sumtable' aria-label='한눈에 보는 표'><h2>한눈에 보는 표</h2><table><caption>이 글의 핵심을 구역별로 정리했습니다</caption>"
            "<thead><tr><th scope='col'>구분</th><th scope='col'>핵심</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>")


def _sec_points(sec, n=3):
    """소제목 구역에서 요점 문장: 목록(li)이 있으면 그것, 없으면 단락의 앞 문장들(글에 있는 문장 그대로)."""
    lis = [re.sub(r"<[^>]+>", "", m).strip() for m in re.findall(r"<li>(.*?)</li>", sec, re.S)]
    lis = [t for t in lis if t]
    if not lis:
        body = sec.split("</h2>", 1)[-1]
        txt = " ".join(re.sub(r"<[^>]+>", "", m).strip() for m in re.findall(r"<p>(.*?)</p>", body, re.S))
        txt = html.unescape(txt)
        lis = [x.strip() for x in re.split(r"(?<=[.!?])\s+", txt) if len(x.strip()) >= 8]
    return [(t[:46].rstrip() + "…") if len(t) > 48 else t for t in lis[:n]]


def summary_card(body, up):
    """'한눈에 보기' 카드. 글이 어떤 형식이든 항상 만든다(네 구역이 모자라면 다른 소제목 구역의 문장으로 채움)."""
    parts = re.split(r"(?=<h2>)", body)
    h2t = lambda x: re.sub(r"<[^>]+>", "", x.split("</h2>")[0])
    panels, used = [], set()
    for key, title, ico, cls in GLANCE:
        idx = next((k for k, x in enumerate(parts) if x.startswith("<h2>") and key in h2t(x)), None)
        if idx is None:
            continue
        lis = _sec_points(parts[idx])
        if lis:
            used.add(idx)
            panels.append(f"<div class='gl{cls}'><img src='{up}icons/{ico}.svg' alt='' width='44' height='44'><p class='glt'>{title}</p><ul>" + "".join(f"<li>{E(t)}</li>" for t in lis) + "</ul></div>")
    if len(panels) < 2:  # 형식이 다른 긴 글: 앞쪽 소제목 구역들로 채운다(제목·문장은 글에 있는 그대로)
        for k, x in enumerate(parts):
            if len(panels) >= 4:
                break
            if k in used or not x.startswith("<h2>") or re.search(r"함께 읽으면|자주 묻는|FAQ", h2t(x)):
                continue
            lis = _sec_points(x, 2)
            if lis:
                panels.append(f"<div class='gl'><img src='{up}icons/consult.svg' alt='' width='44' height='44'><p class='glt'>{E(html.unescape(h2t(x)))}</p><ul>" + "".join(f"<li>{E(t)}</li>" for t in lis) + "</ul></div>")
    if not panels:
        return ""
    return "<section class='glance' aria-label='한눈에 보기'>" + "".join(panels) + "</section>"


GENERIC_IMGS = None


def _imgs(pattern):
    return sorted(str(x.relative_to(ROOT / "images")).replace("\\", "/") for x in (ROOT / "images").glob(pattern))


def cat_pool(cat):
    """분류별 그림 목록(대표 이미지 hero-* 는 맨 위에 쓰이므로 제외) + 공용 그림."""
    global GENERIC_IMGS
    if GENERIC_IMGS is None:
        GENERIC_IMGS = [g for g in _imgs("gallery/*.jpg") + _imgs("clinic-*.jpg") if "entrance" not in g and "herbroom" not in g] + [f for f in _imgs("banner-*.jpg")]
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
    # 글 대표 사진: 분류에 맞는 실제 한의원 사진을 slug 순으로 돌려 쓴다(같은 사진이 이웃 글에 연달아 오지 않게)
    for cat, slugs in by.items():
        pool = real_pool(cat)
        if pool:
            for i, sl in enumerate(sorted(set(slugs))):
                REAL_ASSIGN[sl] = pool[i % len(pool)]


CLINIC_PHOTO_CATS = {"chuna", "shockwave", "ultrasound", "first-visit", "diagnosis"}  # 실제 한의원 사진이 주제와 맞는 분류
HERB_ASSIGN = {}
REAL_ASSIGN = {}
# 분류 사진이 적을 때 함께 돌려 쓰는 한의원 공간·상담 사진(실제 사진)
REAL_EXTRA = ["room-hall1", "room-hall2", "room-bed-hall", "room-therapy1", "room-therapy2", "room-consult1", "room-consult2",
              "room-consult3", "room-desk", "consult", "consult-tablet", "explain-model", "doc-library", "doc-room"]


def real_pool(cat):
    """분류별 실제 사진 목록(12장보다 적으면 공간·상담 사진을 더해 반복을 줄인다)."""
    names = list(REAL_BY_CAT.get(cat, REAL_BY_CAT["first-visit"]))
    if len(names) < 12:
        names = list(dict.fromkeys(names + REAL_EXTRA))
    return [f"real/{n}.jpg" for n in names if (ROOT / "images" / "real" / f"{n}.jpg").exists()]


def herb_photos():
    f = ROOT / "images" / "herbpub" / "_list.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def post_img(p):
    """글 대표 그림(원장님 지시 2026-11-25: AI 사람 그림은 쓰지 않는다).
    ① 실제 사진(한약 글은 원장님이 찍은 한약 사진, 그 밖에는 분류에 맞는 한의원 사진) ② 글 안내 그림 ③ 분류 안내 그림."""
    # 원장님 지시(2026-11-25 밤): "주제랑 안 맞는 실사로 도배하지 말고 매그니픽으로 글마다 그려라"
    # ① 그 글 전용 그림(images/body/<slug>-1.jpg) ② 한약 글은 원장님이 찍은 한약 사진 ③ 한의원 진료 자체가 주제인 분류만 실제 한의원 사진 ④ 안내 그림
    if not p["slug"].startswith("dr-") and (ROOT / "images" / "body" / f"{p['slug']}-1.jpg").exists():  # 의료진 소개 글은 AI 그림 금지
        return f"body/{p['slug']}-1.jpg"
    if p["slug"] in HERB_ASSIGN:
        return HERB_ASSIGN[p["slug"]]
    if p["slug"] in REAL_ASSIGN and p["category"] in CLINIC_PHOTO_CATS:
        return REAL_ASSIGN[p["slug"]]
    for svg in (f"info/post-{p['slug']}.svg", f"info/{p['category']}.svg"):
        if (ROOT / "images" / svg).exists():
            return svg
    return None


def _card_img(p, i):
    own = post_img(p)
    if own:
        if own.startswith("real/") and (ROOT / "images" / (own[:-4] + "-sm.jpg")).exists():
            return own[:-4] + "-sm.jpg"
        return thumb_of(own)
    pool = cat_pool(p["category"])
    k = (_h(p["slug"]) if i is None else i) % len(pool)
    return thumb_of(pool[k])


def card(p, up, i=None):
    card_href = add_utm(f"{up}{post_url(p)}", "card", p['title'])
    return (f"<a class='card postcard has-thumb' data-link-location='card' href='{card_href}'><img class='cthumb' src='{up}images/{_card_img(p, i)}' alt='{E(p["title"])}' width='640' height='360' loading='lazy'><div>"
            f"<span class='sig'>{E(CATS[p['category']])}</span><br>"
            f"<b>{E(p['title'])}</b><br><span class='note'>{E(p['summary'])}</span><br>"
            f"<span class='note'>수정 {E(p['updated'])}</span></div></a>")


def reviewer_person():
    person = {"@type": "Person", "@id": (BASE or "") + "/doctor-lee.html#person", "url": (BASE or "") + "/doctor-lee.html",
              "name": REV["name"], "jobTitle": REV["title"], "honorificSuffix": "한의사",
              "hasOccupation": {"@type": "Occupation", "name": "한의사"},
              "alumniOf": {"@type": "CollegeOrUniversity", "name": "원광대학교 한의과대학"},
              "worksFor": {"@type": "MedicalClinic", "name": CFG["clinic_name"]}}
    if REV.get("license"):
        person["identifier"] = f"한의사 면허번호 {REV['license']}"
    return person


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------- 페이지 만들기 ----------
# 분류 대표 그림: 실제 사진이 어울리는 분류는 좋은꿈참사랑한의원에서 찍은 사진을 쓴다(사람 얼굴이 가운데 오지 않는 사진 위주)
REAL_HERO = {"first-visit": "real/room-hall1.jpg", "diagnosis": "real/explain-xray.jpg", "herbal": "herbpub/herb-018.jpg",
             "chuna": "real/chuna-press.jpg", "ultrasound": "real/explain-monitor1.jpg", "accident": "real/consult-tablet.jpg",
             "pain": "real/chuna-hip.jpg",
             # 2026-11-25: 남은 분류도 AI 그림 대신 실제 한의원 사진(원장님 지시: AI 느낌 줄이기)
             "insomnia": "real/room-therapy2.jpg", "metabolic": "real/exam-monitor.jpg", "digestion": "real/consult-tablet.jpg",
             "neuro": "real/explain-anatomy.jpg", "women": "real/room-consult2.jpg", "pediatric": "real/room-consult1.jpg",
             "respiratory": "real/nose-check.jpg", "skin": "real/room-consult3.jpg", "mental": "real/room-bed-hall.jpg",
             "shockwave": "real/room-device2.jpg", "local": "real/room-entrance.jpg"}


# 분류 페이지(guide/<분류>/) 맨 위 안내 그림 아래에 넣는 실제 사진 (content/photo_candidates.md 추천 위치)
HUB_REAL = {
    "ultrasound": [("r3-ultrasound-logiq-1.webp", "진료실 한쪽에 놓인 초음파 진단기 본체", 1600, 1485),
                   ("r3-ultrasound-console-1.webp", "초음파 진단기 조작판과 여러 종류의 탐촉자", 1024, 743)],
    "herbal": [("r3-herb-storage-trays-1.webp", "약재 이름표를 붙여 정리한 약재 보관함", 1200, 1600),
               ("r3-herb-weighing-1.webp", "약재를 저울에 달아 정량을 확인하는 모습", 1050, 1400),
               ("r3-herb-pouch-box-1.webp", "상자에 가지런히 담긴 한약 파우치", 1200, 1600)],
    "first-visit": [("r3-treatment-room-beds-1.webp", "침상이 놓인 밝은 치료실과 안쪽 복도", 1200, 1600),
                    ("r3-lockers-1.webp", "치료 전 소지품을 넣는 번호 보관함", 1277, 1600)],
}


def real_figs(items, up):
    return "".join(f"<figure><img src='{up}images/real/{E(f)}' alt='{E(a)}' width='{w}' height='{h}' loading='lazy'><figcaption>{E(a)}</figcaption></figure>"
                   for f, a, w, h in items if (ROOT / "images" / "real" / f).exists())


def short_title(t):
    """검색 결과 제목은 60자 안으로, 한의원 이름은 항상 남긴다: 길면 꼬리(— … 한방가이드 등)를 ' | 한의원 이름'으로 줄이고,
    그래도 길면 앞부분을 낱말 경계에서 줄인다."""
    if len(t) <= 60:
        return t
    name = CFG.get("clinic_name", "좋은꿈참사랑한의원")
    head = re.split(r" \| | — ", t)[0].strip()
    tail = " | " + name
    if len(head + tail) <= 60:
        return head + tail
    room = 60 - len(tail) - 1
    cut = head[:room]
    sp = cut.rfind(" ")
    cut = cut[:sp] if sp >= room * 0.6 else cut
    return cut.rstrip(" ,·—") + "…" + tail


_WH = {}


def img_wh(src):
    """그림 파일의 가로·세로를 읽어 width·height 속성으로(화면 밀림 방지·검사 항목)."""
    if src not in _WH:
        wh = _imgsize.size_with_fallback(str(ROOT / src))  # PIL 없이(GitHub Actions 빌드에도 PIL 이 없음)
        _WH[src] = f"width='{wh[0]}' height='{wh[1]}'" if wh else ""
    return _WH[src]


def hero_html(depth, slug, title, sub="", ai_note=True, img=None):
    """가로 전체를 덮는 큰 이미지 영역. images/hero-<slug>.jpg 가 있으면 그것을, 없으면 배너 사진을 쓴다."""
    up = "../" * depth
    cand = ([img] if img else []) + ([REAL_HERO[slug]] if slug in REAL_HERO else []) + [f"hero-{slug}.jpg", f"ai-banner-{slug}.jpg", CAT_PHOTO.get(slug, "clinic-room1.jpg")]
    name = next((c for c in cand if (ROOT / "images" / c).exists()), "clinic-room1.jpg")
    is_ai = name.startswith(("hero-", "ai-banner-", "post/", "post2/", "pool/", "body/"))
    note = "<span class='phero-note'>이미지는 AI로 만든 이미지입니다</span>" if (is_ai and ai_note) else ""
    subp = f"<p class='phero-sub'>{E(sub)}</p>" if sub else ""
    ext = ".jpg"
    if name.endswith(".jpg") and (ROOT / "images" / (name[:-4] + ".webp")).exists() and (ROOT / "images" / (name[:-4] + "-sm.webp")).exists():
        ext = ".webp"; name = name[:-4] + ".webp"  # 실사진은 WebP 로(검사: WebP 사용)
    return (f"<section class='phero'><img src='{up}images/{name}' " + (f"srcset='{up}images/{name[:-len(ext)]}-sm{ext} 1024w, {up}images/{name} 2000w' sizes='100vw' " if name.startswith(('hero-', 'real/')) and (ROOT / 'images' / (name[:-len(ext)] + '-sm' + ext)).exists() else '') + f"alt='{E(re.sub(r'<[^>]+>', '', title))} 대표 그림' width='2000' height='1125' fetchpriority='high'>"
            f"<div class='phero-in'><h1>{re.sub(r' *· *', ' · ', E(title))}</h1>{subp}</div>{note}</section>")


_P = ["treat-director1", "treat-director2", "treat-vice1", "treat-vice2", "leg-check", "room-therapy1", "room-therapy2",
      "chuna-neck1", "chuna-shoulder", "chuna-neck2", "chuna-hip", "chuna-leg", "chuna-neck3", "chuna-neck4", "chuna-press", "treat-check",
      "room-chuna-table", "room-bed1", "room-bed2", "room-bed3", "room-device1", "room-device3"]
_C = ["consult", "room-consult1", "room-consult2", "exam-monitor",
      "consult-tablet", "explain-spine", "explain-model", "explain-xray", "explain-monitor1", "explain-monitor2", "explain-anatomy", "room-consult3", "room-desk"]
_T = ["duo1", "duo2", "duo4", "team-tray", "team-smile", "team-arms", "team-stand", "team-tv", "team-talk", "doc-wst", "doc-room", "doc-stand", "doc-library", "doc-smile"]
_H = ["r4-herb-cabinet", "herbs", "team-herbset", "team-talk-herb", "team-tray2"]
REAL_BY_CAT = {"pain": _P + ["explain-xray", "explain-spine"], "chuna": _P + ["doc-wst"], "accident": _P + ["consult", "explain-xray", "consult-tablet"],
               "shockwave": _P + ["room-device2", "r4-devices-microwave-magnetic"], "ultrasound": ["r4-ultrasound-books", "exam-monitor", "treat-vice1", "treat-vice2", "explain-monitor1", "explain-monitor2", "explain-xray", "room-device2"],
               "diagnosis": _C + ["nose-check"], "first-visit": _C + _T + ["room-therapy1", "room-entrance", "room-hall1", "room-hall2"],
               "herbal": _H + ["consult"], "digestion": ["consult", "herbs", "room-consult1", "consult-tablet", "explain-anatomy"] + _H,
               "metabolic": ["consult", "exam-monitor", "herbs", "consult-tablet", "explain-monitor1"],
               "respiratory": ["nose-check", "consult", "room-consult2", "consult-tablet"], "insomnia": ["consult", "room-consult1", "room-consult2", "room-therapy2", "consult-tablet", "doc-library"],
               "mental": ["consult", "room-consult1", "room-consult2", "director-portrait", "consult-tablet", "doc-library"],
               "neuro": ["consult", "exam-monitor", "treat-director1", "explain-anatomy", "chuna-neck1", "explain-monitor2"],
               "women": ["consult", "room-consult2", "room-therapy2", "herbs", "consult-tablet", "room-bed1"], "pediatric": ["consult", "nose-check", "room-consult1", "consult-tablet"],
               "skin": ["consult", "nose-check", "room-consult2", "consult-tablet"], "local": _T + ["room-entrance", "room-hall1"]}


try:
    BODY_PLAN = json.loads((ROOT / "content" / "body-images.json").read_text(encoding="utf-8"))
    _auto = ROOT / "content" / "body-images-auto.json"  # 로컬 AI 장면 초안(tools/plan_scenes.py) — 다른 작업과 덮어쓰지 않게 따로 둠
    if _auto.exists():
        for _k, _v in json.loads(_auto.read_text(encoding="utf-8")).items():
            BODY_PLAN.setdefault(_k, _v)
except (OSError, ValueError):
    BODY_PLAN = {}


def own_body_images(body, slug):
    """content/body-images.json 에 이 글 전용 그림이 있고 파일이 만들어져 있으면, 지정한 소제목 앞에 넣는다.
    하나라도 넣었으면 True — 이때는 분류 공용 그림을 쓰지 않는다."""
    items = [(n, it) for n, it in enumerate(BODY_PLAN.get(slug, []), 1)
             if (ROOT / "images" / "body" / f"{slug}-{n}.jpg").exists()]
    if len(items) > 1 and items[0][0] == 1:
        items = items[1:]  # 1번 그림은 글 맨 위 대표 그림으로 쓰이므로 본문에서는 겹치지 않게 뺀다
    if not items:
        return body, False
    parts = re.split(r"(?=<h2>)", body)
    used = set()
    for n, it in items:
        for i, part in enumerate(parts):
            head = re.sub(r"<[^>]+>", "", part.split("</h2>")[0]) if part.startswith("<h2>") else ""
            if i not in used and it.get("before") and it["before"] in head:
                f = f"body/{slug}-{n}.jpg"
                parts[i] = (f"<figure class='bodyimg'><img src='../../images/{f}' srcset='../../images/{f[:-4]}-sm.jpg 1024w, ../../images/{f} 1600w' "
                            f"sizes='(min-width:900px) 860px, 100vw' alt='{E(it.get('alt') or head)} 관련 그림' width='1600' height='900' loading='lazy'>"
                            f"<figcaption>AI로 만든 이미지입니다</figcaption></figure>") + part
                used.add(i)
                break
    return "".join(parts), bool(used)


def body_images(body, cat, slug=""):
    """본문 h2 사이사이에 큰 이미지를 넣어 한 화면마다 그림이 보이게 한다."""
    body, has_own = own_body_images(body, slug)
    # 글 전용 그림이 없으면 주제와 무관한 공용 사진을 끼워 넣지 않는다(원장님 지시 2026-11-25 밤)
    return body
    pool = cat_pool(cat)[:8]
    if not pool:
        return body
    off = _h(slug)
    parts = re.split(r"(?=<h2>)", body)
    real = [f"real/{n}.jpg" for n in REAL_BY_CAT.get(cat, REAL_BY_CAT["first-visit"]) if (ROOT / "images" / "real" / f"{n}.jpg").exists()]
    if len(real) > 1 and REAL_ASSIGN.get(slug) in real:  # 맨 위 대표 사진과 같은 사진은 본문에서 빼기
        real.remove(REAL_ASSIGN[slug])
    out, k = [], 0
    for i, part in enumerate(parts):
        if part.startswith("<h2>") and i >= 2 and (i % 2 == 0):
            if k == 0 and real:  # 첫 그림은 실제 한의원 사진(윤작가 촬영)
                r = real[off % len(real)]
                out.append(f"<figure class='bodyimg'><img src='../../images/{r}' srcset='../../images/{r[:-4]}-sm.jpg 1024w, ../../images/{r} 1600w' sizes='(min-width:900px) 860px, 100vw' alt='좋은꿈참사랑한의원 진료 모습' {img_wh('images/' + r)} loading='lazy'></figure>")
                k += 1
                out.append(part)
                continue
            out.append(f"<figure class='bodyimg'><img src='../../images/{pool[(off + k) % len(pool)]}' alt='{E(CATS.get(cat, cat))} 한방가이드 그림' {img_wh('images/' + pool[(off + k) % len(pool)])} loading='lazy'></figure>")
            k += 1
        out.append(part)
    return "".join(out)


BOOK_URL = "https://booking.naver.com/booking/13/bizes/1043468"
KAKAO_URL = "https://pf.kakao.com/_UWxnvb/chat"


def cta_box(cat_name, pos, up="../../"):
    """예약 상자. pos(mid/bottom: 글, hub: 분야 페이지, list: 한방가이드 목록)는 data-cta 로 남아 GA4 클릭 기록(comfort.js)에서 위치로 쓰인다.
    의료광고 기준: 효과 약속 없이 '상담·예약 방법'만 안내한다."""
    tel = re.sub(r"[^0-9+]", "", CFG["phone"])
    head = (f"{E(cat_name)} 고민, 직접 여쭤보고 싶으신가요?" if pos in ("mid", "hub") and cat_name
            else "읽어 보신 내용, 진료실에서 이어서 여쭙겠습니다" if pos == "bottom"
            else "궁금한 점은 직접 여쭤보셔도 됩니다")
    return (f"<aside class='ctabox' data-cta='{pos}' aria-label='예약·상담'><p class='ctahead'>{head}</p>"
            f"<p class='ctasub'>지금 상태를 먼저 여쭙고, 한의원에서 함께 살필 수 있는지 안내해 드립니다.</p>"
            f"<div class='ctabtns'><a class='btn primary' href='{BOOK_URL}' target='_blank' rel='noopener'>네이버 예약</a>"
            f"<a class='btn kakao' href='{KAKAO_URL}' target='_blank' rel='noopener'>카카오톡 상담</a>"
            f"<a class='btn' href='tel:{tel}'>전화 {E(CFG['phone'])}</a>"
            + (f"<a class='btn' data-link-location='cta_{pos}' href='{up}visit.html'>오시는 길</a>" if pos == "bottom" else "")
            + "</div></aside>")


def build_post(p, posts):
    cat = CATS[p["category"]]
    related = [x for x in posts if x["category"] == p["category"] and x["slug"] != p["slug"]][:4]
    idx = [x["slug"] for x in posts].index(p["slug"])
    newer = posts[idx - 1] if idx > 0 else None
    older = posts[idx + 1] if idx + 1 < len(posts) else None
    hero = hero_html(2, p["category"], p["title"], f"{cat} · 좋은꿈참사랑한의원 한방가이드", img=(post_img(p) if (post_img(p) or "").endswith((".jpg", ".webp")) else None))
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
    # 연관 질문: 같은 분야의 다른 글 제목(대부분 질문형)을 내부 링크로. 카드 4편과 겹치지 않게, 글마다 다른 위치에서 고른다.
    pool = [x for x in posts if x["category"] == p["category"] and x["slug"] != p["slug"] and x not in related]
    rq = []
    if pool:
        st = _h(p["slug"]) % len(pool)
        rq = (pool[st:] + pool[:st])[:6]
    rq_html = "".join(f"<li><a data-link-location='related_q' href='../../{post_url(x)}'>{E(x['title'])}</a></li>" for x in rq)
    rq_html += f"<li><a data-link-location='related_q' href='../../visit.html'>상도역 근처에서 {E(cat)} 상담은 어디서 받을 수 있나요?</a></li>"
    relq = f"<section class='relq'><h2>연관 질문</h2><ul>{rq_html}</ul></section>"
    facts = (f"<section class='clinicfacts'><h2>어디서 상담받을 수 있나요?</h2>"
             f"<p>{E(CFG['clinic_name'])}은 {E(CFG['address'])}(서울 동작구 상도동, 7호선 상도역 3번 출구 근처)에 있습니다. "
             f"한의사 3명(이종호 대표원장, 조영기 수석진료원장, 정원영 진료원장)이 진료합니다. "
             f"진료시간은 평일 09:30~20:00(점심 13:00~14:00), 토·일·공휴일 09:30~15:00이며, 방문 전 전화로 확인을 권합니다. "
             f"예약은 네이버 예약, 카카오톡 상담, 전화 {E(CFG['phone'])}로 받습니다.</p></section>")
    rel = ""
    if related:
        rel = "<section><h2>같은 주제의 글</h2><div class='cardgrid'>" + "".join(card(x, "../../", j + _h(p["slug"])) for j, x in enumerate(related)) + "</div></section>"
    nav_newer = f"<a class='btn' data-link-location='prev_next' href='{add_utm('../../' + post_url(newer), 'button', '최신-글')}'>← 최신 글</a>" if newer else ""
    nav_older = f"<a class='btn' data-link-location='prev_next' href='{add_utm('../../' + post_url(older), 'button', '이전-글')}'>이전 글 →</a>" if older else ""
    nav = "<div class='pn'>" + nav_newer + nav_older + "</div>"
    # 읽기 먼저(2026-11-25 원장님 "보기도 힘들어, 이쁘게"): 답 → 차례 → 본문. 정리 카드·그림·상담 상자는 본문 뒤에.
    toc, story = with_toc(safety_box(body_images(p['body'], p['category'], p['slug'])))
    toc = toc.replace("<nav class='toc' aria-label='이 글의 차례'><b>이 글의 차례</b>", "<details class='toc'><summary>이 글의 차례</summary>").replace("</nav>", "</details>")
    svg = ROOT / 'images' / 'info' / f"post-{p['slug']}.svg"
    info = (f"<figure class='hubinfo'><a href='../../images/info/post-{p['slug']}.svg' target='_blank' rel='noopener'><img src='../../images/info/post-{p['slug']}.svg' alt='{E(p['title'])} 안내 그림' width='1200' height='675' loading='lazy'></a>"
            "<figcaption>그림을 누르면 크게 볼 수 있습니다</figcaption></figure>") if svg.exists() else ''
    who = (f"<b><a href='../../doctor-lee.html' data-link-location='byline'>{E(REV['name'])} 한의사 감수</a></b><span>{E(CFG['clinic_name'])} {E(REV['title'])}{lic}</span>" if p['reviewed']
           else f"<b>{E(CFG['author_label'])} 작성</b>")
    face = "<img src='../../images/real/director-portrait-sm.webp' alt='' width='56' height='56' loading='lazy'>" if p['reviewed'] else ''
    body = f"""{crumbs}<!--noquick-->
<article class="story">
<div class="answer"><span class="sr">한 줄 답변: </span>{E(p['summary'])}</div>
<div class="writer">{face}<p>{who}<span>발행 {E(p['date'])} · 수정 {E(p['updated'])}</span></p></div>
{todo}
{toc}
{story}
{info}
<div class="recap">{summary_card(p['body'], '../../')}{summary_table(p['body'])}</div>
{faq_block}
{cta_box(cat, 'bottom')}
<p class="closing">{E(CFG['clinic_name'])}은 재진 때 지난번 이야기부터 이어서 여쭙니다. 진료시간과 예약은 <a href="../../index.html#visit">오시는 길</a>에서 확인하세요.</p>
{facts}
<p class="disclaimer">{E(CFG['disclaimer'])}</p>
<p class="note">작성 기준: 일반적으로 알려져 있는 건강 정보를 참고해 정리했습니다{'(대표원장 감수)' if p['reviewed'] else ''}. 증상 기록은 1~2주 동안 하루 1회, 비슷한 시간에 적어 오시면 지난 상태와 비교하기 쉽습니다.</p>
</article>
{relq}
{rel}
{nav}"""
    graph = [
        {"@type": "MedicalWebPage", "name": p["title"], "headline": p["title"], "description": p["summary"],
         "inLanguage": "ko", "datePublished": p["date"], "dateModified": p["updated"],
         "author": {"@type": "MedicalClinic", "name": CFG["clinic_name"]},
         "publisher": {"@type": "MedicalClinic", "name": CFG["clinic_name"], "telephone": "+82-" + CFG["phone"].lstrip("0")},
         "isPartOf": {"@type": "CollectionPage", "name": "한방가이드"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "한방가이드", "item": f"{BASE}/guide/index.html"},
            {"@type": "ListItem", "position": 3, "name": cat, "item": f"{BASE}/guide/{p['category']}/index.html"},
            {"@type": "ListItem", "position": 4, "name": p["title"], "item": f"{BASE}/{post_url(p)}"}]},
    ]
    if p["reviewed"]:
        graph[0]["reviewedBy"] = reviewer_person()
        graph[0]["lastReviewed"] = p["updated"]
    if BASE:
        graph[0]["url"] = f"{BASE}/{post_url(p)}"
        _img = post_img(p)
        if _img:
            graph[0]["image"] = f"{BASE}/images/{_img}"
            graph[0]["primaryImageOfPage"] = {"@type": "ImageObject", "url": f"{BASE}/images/{_img}"}
    if p["faq"]:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\*\*|\[|\]\([^)]*\)", "", a)}} for q, a in p["faq"]]})
    write(ROOT / post_url(p),
          shell(post_title_tag(p), p["summary"], 2, body,
                jsonld({"@context": "https://schema.org", "@graph": graph}), post_url(p), hero=hero, og_image=post_img(p), actions="top",
                og_title=f"{p['title']} — {CFG['clinic_name']} 한방가이드"))


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
                    f"<p><a class='btn' data-link-location='hub_more' href='{btn_href}'>{E(name)} 전체 보기</a></p></section>"
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
            real_html = (f"<div class='gallery'>{real_figs(HUB_REAL[slug], '../../')}</div>" if slug in HUB_REAL else "")
            hub_html = (f"<p class='lead hublead'>{inline(hub['lead'])}</p>" + info_html + cta_box(name, "hub") + real_html + secs
                        + (f"<h2>상도동·노량진에서</h2><p>{inline(hub['local'])}</p>" if hub.get("local") else "")
                        + (f"<section class='faqblock' id='faq'><h2>자주 묻는 질문</h2>{faq}</section>" if faq else "")
                        + f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호 · 마지막 확인 {TODAY} · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다.</p>"
                        + f"<h2>{E(name)} 글 모아 보기 ({len(items)}편)</h2>")
            hub_ld = jsonld({"@context": "https://schema.org", "@type": "FAQPage",
                             "mainEntity": [{"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in hub.get("faq", [])]})
            title = f"{hub.get('title', name)} | {CFG['clinic_name']}"
            desc = re.sub(r"\s+", " ", hub["lead"])[:150]
        cbody = (f"<nav class='crumbs'><a href='../../index.html'>홈</a> › <a href='../../treatments.html'>진료안내</a> › <a href='../index.html'>한방가이드</a></nav>"
                 + (hub_html or cta_box(name, "hub")) + "<div class='cardgrid'>" + "".join(card(x, "../../", j) for j, x in enumerate(items)) + "</div>")
        write(ROOT / "guide" / slug / "index.html",
              shell(title, desc, 2, cbody,
                    hub_ld, f"guide/{slug}/index.html", "website", hero=hero_html(2, slug, hub.get("title", name) if hub else name, f"{name}에 대한 한방가이드 {len(items)}편")))
    body = ("<nav class='crumbs'><a href='../index.html'>홈</a> › 한방가이드</nav>"
            ""
            "<p>일상의 말로 쓴 한방 건강 정보입니다. 모든 글은 일반적인 정보이며 진단이나 치료를 대신하지 않습니다.</p>"
            f"<p class='note'>글 {len(posts)}편</p>" + cta_box("", "list") + sections +
            "<p class='note imgnote'>이 페이지의 사진은 AI로 만든 예시 이미지입니다.</p>")
    itemlist = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "한방가이드",
                "hasPart": [{"@type": "WebPage", "name": p["title"]} for p in posts]}
    write(ROOT / "guide" / "index.html",
          shell(f"한방가이드 — {CFG['clinic_name']}", "좋은꿈참사랑한의원 한방가이드입니다. 불면·통증·추나·체외충격파·초음파·소화·대사·여성·소아·교통사고 등 분야별 건강 정보를 일상의 말로 정리했고, 모든 글은 이종호 대표원장이 감수합니다.", 1, body,
                jsonld(itemlist), "guide/index.html", "website", hero=hero_html(1, "home", "한방가이드", f"일상의 말로 쓴 한방 건강 정보 {len(posts)}편")))


def build_sitemap(posts):
    path = ROOT / "sitemap.xml"
    if not BASE:
        print("[안내] site.json 의 base_url 이 비어 있어 sitemap.xml 은 만들지 않았습니다.")
        return
    urls = [("index.html", TODAY, "1.0"), ("today.html", TODAY, "0.9"), ("sleep.html", TODAY, "0.9"), ("diet.html", TODAY, "0.9"), ("gallery.html", TODAY, "0.7"), ("videos.html", TODAY, "0.7"),
            ("about.html", TODAY, "0.8"), ("first.html", TODAY, "0.8"), ("again.html", TODAY, "0.7"), ("faq.html", TODAY, "0.8"), ("visit.html", TODAY, "0.9"), ("network.html", TODAY, "0.6"), ("lectures.html", TODAY, "0.7"), ("herbal-room.html", TODAY, "0.7"), ("pulse.html", TODAY, "0.8"), ("column-pulse.html", TODAY, "0.7"), ("gongjindan.html", TODAY, "0.8"), ("inbody.html", TODAY, "0.7"), ("explain.html", TODAY, "0.7"), ("column-fall-walking.html", TODAY, "0.7"), ("column-keep-health.html", TODAY, "0.7"), ("acupuncture.html", TODAY, "0.8"), ("treatments.html", TODAY, "0.9"), ("doctor-lee.html", TODAY, "0.8"), ("doctor-jo.html", TODAY, "0.7"), ("doctor-jeong.html", TODAY, "0.6"), ("privacy.html", TODAY, "0.3"), ("terms.html", TODAY, "0.3"),
            ("guide/index.html", max([p["updated"] for p in posts] or [TODAY]), "0.9")]
    urls += [(f"guide/{c}/index.html", max(p["updated"] for p in posts if p["category"] == c), "0.7")
             for c in CATS if any(p["category"] == c for p in posts)]
    urls += [(post_url(p), p["updated"], "0.7") for p in posts]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f"  <url><loc>{E(BASE + '/' + u)}</loc><lastmod>{lm}</lastmod><priority>{pr}</priority></url>\n" for u, lm, pr in urls) + "</urlset>\n"
    write(path, xml)


def build_llms(posts):
    """llms.txt = 짧은 요약(content/llms-short.md, 5KB 안), llms-full.txt = 전체 안내(content/llms-base.md) + 글 목록"""
    base = (ROOT / "content" / "llms-base.md").read_text(encoding="utf-8").rstrip() + "\n\n"
    lines = ["## 한방가이드 글", "인용 시 출처: 좋은꿈참사랑한의원. 일반 건강 정보이며 진단·치료를 대신하지 않습니다. 새 글이 꾸준히 올라옵니다.", ""]
    for p in posts:
        lines.append(f"- [{p['title']}]({post_url(p)}): {p['summary']} (수정 {p['updated']})")
    write(ROOT / "llms-full.txt", base + "\n".join(lines) + "\n")
    short = (ROOT / "content" / "llms-short.md").read_text(encoding="utf-8").rstrip() + "\n"
    counts = {}
    for x in posts:
        counts[x["category"]] = counts.get(x["category"], 0) + 1
    cnt = " · ".join(f"[{CATS[k]}]({BASE}/guide/{k}/index.html) {n}편" for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    short += (f"\n## 한방가이드 분야별 글 수 ({TODAY} 기준, 총 {len(posts)}편)\n{cnt}\n"
              f"\n## 인용 안내\n이 사이트의 내용을 인용하실 때는 출처를 \"좋은꿈참사랑한의원(대표원장 이종호 한의사 감수), gooddreamclinic.com\"으로, "
              f"가능하면 해당 글의 주소와 함께 표기해 주세요.\n")
    write(ROOT / "llms.txt", short)


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


TODAY_DESC = ("상도동 좋은꿈참사랑한의원 대표원장이 전하는 오늘의 리듬입니다. 매일 바뀌는 달·서울 일출·일몰·절기, "
              "잠·식욕·위로 한 줄과 오늘 많이 읽는 한방가이드 글을 한 화면에 모았습니다.")


def build_today(posts):
    tc = lambda ico, title, inner, cls="": (f"<div class='tcard {cls}'><h2 class='h2ico'>{icon_img(ico, '', 'ico sm')}{title}</h2>{inner}</div>")
    guide_href = add_utm('guide/index.html', 'button', '한방가이드-전체-보기')
    pop = [("guide/insomnia/before-sleep-reading.html", "오늘 밤은 잘 자려고 하지 않으셔도 됩니다", "잠자리에 들기 전에 천천히 읽는 글"),
           ("guide/digestion/bloating-after-meals.html", "식사 뒤 더부룩함, 속쓰림과는 어떻게 다른가요?", "식후 불편함을 나눠 살피는 법"),
           ("guide/metabolic/late-night-eating.html", "야식을 끊기 어려울 때 먼저 살펴볼 것", "밤 식욕과 하루 리듬"),
           ("guide/accident/index.html", "교통사고 뒤 진료 안내", "상도동·노량진에서 사고 뒤 몸이 불편할 때"),
           ("guide/neuro/index.html", "두통·어지럼·저림 안내", "먼저 확인이 필요한 신호와 진료 흐름")]
    pop_li = "".join(f"<li><a data-link-location='today_popular' href='{u}'>{E(t)}</a> <span class='note'>— {E(d)}</span></li>"
                     for u, t, d in pop if (ROOT / u).exists())
    popular = f"<section class='todaypop'><h2>오늘 많이 읽는 글</h2><ol>{pop_li}</ol></section>" if pop_li else ""
    body = f"""<nav class='crumbs'><a href='index.html'>홈</a> › 오늘의 리듬</nav>
<h1 class='atitle'>오늘의 리듬</h1>
<!--quick-->
<div class='todayintro'>
<p>안녕하세요, 상도동 좋은꿈참사랑한의원 대표원장 이종호입니다. 진료실에서 맥을 짚다 보면 같은 분이라도 날마다 몸의 리듬이 조금씩 다르다는 걸 느낍니다. 잠을 설친 다음 날, 끼니를 거른 날, 계절이 바뀌는 무렵에는 몸도 마음도 평소와 다르게 움직이지요.</p>
<p>'오늘의 리듬'은 그런 하루를 잠깐 돌아보시라고 만든 페이지입니다. 매일 자정(한국 시간)에 오늘의 달 모양, 서울의 해 뜨고 지는 시각, 지금 절기, 그리고 잠·식욕·마음에 건네는 한 줄이 바뀝니다. 한방가이드에 새로 올라온 글도 이곳에 모입니다.</p>
<p>아침 출근길에 한 번, 잠들기 전에 한 번 들러 보세요. 오늘의 한 줄을 읽다가 마음에 걸리는 것이 있으면 아래 '오늘 많이 읽는 글'로 이어서 읽으시면 됩니다. 불편함이 며칠씩 이어진다면 혼자 견디지 마시고, 진료실에서 지난 이야기부터 차근차근 여쭙겠습니다.</p>
</div>
{popular}
<div class='todaygrid' data-today data-up=''>
{tc('clock', '오늘', "<div id='t-date'></div>", 'wide')}
{tc('moon', '오늘의 달', "<div id='t-moon' class='moonrow'></div>")}
{tc('warm', '오늘의 해 (서울)', "<div id='t-sun'></div><p class='note' id='t-sunnote'></p>")}
{tc('insomnia', '오늘의 잠', "<p class='tline' id='t-sleep'></p>")}
{tc('metabolic', '오늘의 식욕', "<p class='tline' id='t-appetite'></p>")}
{tc('mental', '오늘의 위로', "<p class='tline' id='t-comfort'></p>")}
{tc('first-visit', '이 절기에', "<div id='t-term'></div>")}
{tc('first-visit', '오늘의 글', "<div id='t-posts'></div>", 'wide')}
{tc('clock', '최근 올라온 글 (<span id=\"t-count\"></span> 누적)', "<ul id='t-new' class='newlist'></ul><p><a class='btn' data-link-location='today_guide' href='" + guide_href + "'>한방가이드 전체 보기</a></p>", 'wide')}
</div>
<p class='note'>달 모양, 일출·일몰, 절기는 날짜로 계산한 값이며 해마다 하루, 몇 분 정도 차이가 날 수 있습니다. 오늘의 한 줄은 일반적인 생활 안내이며 진단이나 치료를 대신하지 않습니다.</p>"""
    write(ROOT / "today.html",
          shell(f"오늘의 리듬 — 달·해·절기와 오늘의 한 줄 | {CFG['clinic_name']}",
                TODAY_DESC, 0, body,
                clinic_ld("today.html", "오늘의 리듬", TODAY_DESC), "today.html", "website", extra_js="<script src='today.js'></script>"))


GALLERY_FAQ = [  # 사이트에 이미 있는 사실(오시는 길·자주 묻는 질문·처음 오시나요)만
    ("처음 오면 어디로 가면 되나요?",
     "신성빌딩 3층·5층이 한의원입니다. 오시면 직원이 접수를 안내해 드리고, 성함과 불편한 곳을 간단히 적어 주시면 상담과 진맥으로 이어집니다. 어느 층으로 가야 할지 헷갈리시면 02-815-7510으로 전화 주세요."),
    ("진료 공간은 몇 층인가요?",
     "한의원은 서울 동작구 만양로2길 2 신성빌딩 3층과 5층을 함께 씁니다. 이 페이지의 진료실·치료실 사진은 두 층의 공간을 함께 담았습니다."),
    ("엘리베이터가 있나요? 주차는 할 수 있나요?",
     "건물에 엘리베이터가 있습니다. 주차는 방문 전 02-815-7510으로 전화하시면 안내해 드립니다."),
    ("상도역이나 노량진역에서는 어떻게 오나요?",
     "7호선 상도역 3번 출구에서 약 200m 직진해 오거리에서 우회전한 뒤 약 200m 올라오시면 됩니다. 1·9호선 노량진역에서는 3번 출구 근처 KEB하나은행 앞 정류장에서 마을버스 동작01을 타고 신동아리버파크 정류장에서 내리시면 건너편 3층에 한의원이 보입니다."),
]


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
        figs = "".join(f"<figure><img src='{E(i['src'])}' alt='{E(i['alt'])}' {img_wh(i['src'])} loading='lazy'><figcaption>{E(i['alt'])}</figcaption></figure>" for i in items if i["cat"] == c)
        sections += f"<section><h2>{E(c)}</h2><div class='gallery'>{figs}</div></section>"
    faq = "".join(f"<details class='qa'><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in GALLERY_FAQ)
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 진료 공간 둘러보기</nav>"
            "<p>좋은꿈참사랑한의원은 서울 동작구 만양로2길 2 신성빌딩 3층·5층(상도동)에 있습니다. 7호선 상도역 3번 출구에서 걸어오실 수 있고, "
            "노량진역에서는 3번 출구 근처에서 마을버스 동작01을 타고 신동아리버파크 정류장에서 내리시면 됩니다.</p>"
            "<p>처음 오시는 길이 낯설지 않도록 건물 입구부터 진료실, 치료실, 원내 약제실, 의료진의 모습까지 실제 사진을 모았습니다. "
            "어디에서 이야기를 나누고 어디에서 쉬다 가시는지 미리 둘러보세요.</p>" + sections
            + f"<section class='faqblock'><h2>자주 묻는 질문</h2>{faq}</section>"
            + "<p class='note'>자세한 길 안내와 진료시간은 <a data-link-location='gallery_visit' href='visit.html'>예약·오시는 길</a>에서 보실 수 있습니다.</p>")
    gdesc = ("상도역 3번 출구 근처 좋은꿈참사랑한의원(동작구 상도동 신성빌딩 3층·5층)의 진료실·치료실·원내 약제실·의료진·입구 실제 사진입니다. "
             "처음 오시기 전에 미리 둘러보세요.")
    write(ROOT / "gallery.html", shell(f"진료 공간 둘러보기 | {CFG['clinic_name']}", gdesc, 0, body, clinic_ld("gallery.html", "진료 공간 둘러보기", gdesc, "faq", {"mainEntity": faq_entities(body)}), "gallery.html", "website", hero=hero_html(0, "first-visit", "진료 공간 둘러보기", "오시기 전에 한의원의 모습을 미리 보세요", False)))


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
        ld.append({"@type": "VideoObject", "name": v["title"], "description": "좋은꿈참사랑한의원 영상. 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다.",
                   "thumbnailUrl": f"{BASE}/{v['poster']}", "contentUrl": f"{BASE}/{v['file']}", "uploadDate": TODAY, "inLanguage": "ko"})
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 방송·영상 보기</nav>"
            "<p>방송 출연 영상과 한의원 소개 영상입니다. 일반적인 건강 정보이며 진단이나 치료를 대신하지 않습니다.</p>"
            f"<h2>영상 모아 보기</h2><div class='vidgrid'>{cards}</div>"
            "<h2>영상을 보실 때</h2><p>영상 속 설명은 일반적인 건강 정보입니다. 내 몸에 맞는지는 진맥과 상담으로 함께 살펴 드립니다. 궁금한 점은 02-815-7510으로 물어봐 주세요.</p>")
    write(ROOT / "videos.html", shell("방송·영상 보기 | " + CFG["clinic_name"], "좋은꿈참사랑한의원 방송·영상 모음입니다. 대표원장의 방송 출연 영상과 한의원 소개 영상을 한곳에서 보실 수 있습니다. 오시기 전에 한의원의 분위기를 미리 살펴보세요.", 0, body,
                                     jsonld({"@context": "https://schema.org", "@graph": ld}), "videos.html", "website", hero=hero_html(0, "home", "방송·영상 보기", "방송 출연과 한의원 소개 영상")))


SUBPAGES = [  # (파일, 제목, 설명, 대표그림 분류, 부제, 홈에서 가져올 구역 id)
    ("about.html", "한의원 소개", "상도역 좋은꿈참사랑한의원 대표원장 인사말과 의료진, 진료 원칙을 소개합니다. 모두 맥부터 짚고, 지난 이야기를 이어서 묻고, 생활과 마음까지 함께 살피는 진료와 우리가 말하는 회복을 담았습니다.", "home",
     "인사말 · 의료진 · 진료 원칙", ["greeting", "about", "pillars", "recovery"]),
    ("first.html", "처음 오시나요?", "좋은꿈참사랑한의원 첫 방문 안내입니다. 이야기 듣기와 진맥부터 시작하는 상담 순서, 챙겨 오시면 좋은 검사 결과·복용 약 목록, 진료 장비와 편안히 쉬다 가실 수 있는 공간을 미리 알려 드립니다.", "first-visit",
     "첫 방문 순서와 준비하면 좋은 것", ["first", "equip", "comfort"]),
    ("again.html", "다시 오시나요?", "좋은꿈참사랑한의원 재진 안내입니다. 다시 오시면 지난번 이야기와 그사이 몸의 변화를 이어서 여쭙고, 맥과 생활 기록을 함께 보며 다음 방향을 정합니다. 나의 회복지도 예시도 함께 보실 수 있습니다.", "diagnosis",
     "지난 이야기부터 이어서 살핍니다", ["again", "map"]),
    ("faq.html", "자주 묻는 질문", "좋은꿈참사랑한의원 자주 묻는 질문 모음입니다. 네이버 예약과 전화 예약, 평일·주말 진료시간, 주차와 찾아오는 길, 교통사고 진료, 원내 탕전 한약과 진료 과정에 대한 질문에 답합니다.", "first-visit",
     "예약·진료시간·주차·진료 과정", ["faq"]),
    ("visit.html", "예약·오시는 길", "좋은꿈참사랑한의원 예약·오시는 길: 서울 동작구 만양로2길 2 신성빌딩 3층·5층(상도역 3번 출구). 평일 09:30~20:00, 토·일·공휴일 09:30~15:00. 네이버 예약과 전화 02-815-7510으로 문의하실 수 있습니다.", "local",
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
        if fn == "faq.html" and (ROOT / "content" / "faq_worries.html").exists():  # 진료 전 걱정 Q&A(일반 안내, faq.html에만)
            parts.append((ROOT / "content" / "faq_worries.html").read_text(encoding="utf-8"))
        html = "\n".join(parts)
        html = re.sub(r'href="#([\w-]+)"', lambda m: f'href="{"" if where.get(m.group(1)) == fn else where.get(m.group(1), "index.html")}#{m.group(1)}"', html)
        html = html.replace('class="reveal"', 'class="reveal in"')
        if html.count("<h2") < 2:  # 구역 하나뿐인 단독 페이지(예약·오시는 길): 소제목을 H2로 올린다(모양은 h2.subh 로 h3와 같게)
            html = re.sub(r'<h3 class="([^"]*)">', r'<h2 class="\1 subh">', html)
            html = html.replace("<h3>", '<h2 class="subh">').replace("</h3>", "</h2>")
        body = f"<nav class='crumbs'><a href='index.html'>홈</a> › {E(title)}</nav>\n{html}"
        kind = {"faq.html": "faq", "visit.html": "visit"}.get(fn, "WebPage")
        ld = clinic_ld(fn, f"{title} | {CFG['clinic_name']}", desc, kind, {"mainEntity": faq_entities(html)} if kind == "faq" else None)
        write(ROOT / fn, shell(f"{title} | {CFG['clinic_name']}", desc, 0, body, ld, fn, "website",
                               extra_js='<script src="config.js"></script><script src="app.js"></script>',
                               hero=hero_html(0, cat, title, sub, False)))


BRANCHES = [  # (이름, 주소, 전화, 메모) — 공개된 지점 홈페이지·의료정보 사이트 기준(2026-11 확인)
    ("좋은꿈참사랑한의원", "서울 동작구 만양로2길 2 신성빌딩 3층·5층 (상도동)", "02-815-7510", "이 홈페이지의 지점. 네트워크 안에서 심리요법 교육을 맡고 있습니다."),
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
            "<h2>좋은꿈 네트워크</h2><p>좋은꿈참사랑한의원은 <b>좋은꿈 네트워크</b>의 한의원입니다. 네트워크 지점들은 불면, 추나, 본초, 처방, 심리요법 등 분야를 나누어 서로 공부하고 진료 경험을 나눕니다. "
            "지점마다 운영하는 클리닉과 진료시간이 다르니 방문 전 해당 지점에 직접 확인해 주세요.</p>"
            "<figure class='hubinfo'><img src='images/info/network-map.svg' alt='좋은꿈 네트워크 지점 개략도' width='1200' height='675' loading='lazy'></figure>"
            f"<img class='photo soft wide' src='images/real/duo2.jpg' alt='좋은꿈참사랑한의원 원장들' " + img_wh('images/real/duo2.jpg') + " loading='lazy'>"
            f"<h2>지점별 주소와 연락처</h2><div class='grid'>{rows}</div>"
            "<p class='note'>지점 정보는 각 지점 홈페이지와 공개된 의료기관 정보를 바탕으로 정리했으며, 바뀔 수 있습니다. 진료 문의: 02-815-7510</p>")
    ld = {"@context": "https://schema.org", "@type": "Organization", "name": "좋은꿈 네트워크",
          "member": [{"@type": "MedicalClinic", "name": n, **({"address": a} if a else {}), **({"telephone": t} if t else {})} for n, a, t, _m in BRANCHES]}
    write(ROOT / "network.html", shell(f"좋은꿈 네트워크 지점 안내 | {CFG['clinic_name']}", "좋은꿈한의원·좋은꿈참사랑한의원 네트워크 지점(노량진·서초·DMC·광명·마들·분당·수지·인덕원 등) 주소와 연락처", 0, body,
                                      jsonld(ld), "network.html", "website", hero=hero_html(0, "local", "좋은꿈 네트워크 지점", "함께 공부하고 진료를 나누는 한의원들", False)))


LECTURES = [  # 외부 건강 강연 기록. 참석자 얼굴이 정면으로 보이는 사진은 쓰지 않는다. 만족도 조사지 원본(손글씨·이름)은 올리지 않는다.
    {"date": "2026-11-17", "date_ko": "2026년 11월 17일(화)", "title": "양생법과 한의학적 항노화",
     "place": "강감찬관악종합사회복지관", "region": "서울 관악구", "survey_n": 16,
     "survey": [("특강 전반에 만족", 16), ("내용이 이해하기 쉬웠다", 16), ("건강관리에 도움이 될 것 같다", 15)]},
]


def build_lectures():
    L = LECTURES[0]
    fig = lambda f, alt, cap: (f"<figure class='bodyimg lect'><img src='images/real/{f}.jpg' srcset='images/real/{f}-sm.jpg 1024w, images/real/{f}.jpg 1600w' "
                               f"sizes='(min-width:900px) 860px, 100vw' alt='{E(alt)}' width='1600' height='1200' loading='lazy'><figcaption>{E(cap)}</figcaption></figure>")
    pillars = [("食", "식생활", "끼니의 시간과 양, 식사 뒤의 움직임"), ("動", "활동", "무리하지 않는 꾸준한 움직임"),
               ("心", "마음", "스트레스 관리와 정서적 안정"), ("藥", "한약", "필요할 때 진료로 체질과 상태를 살핀 뒤의 처방")]
    pill = "".join(f"<div class='card pillar'><b style='font-size:1.6rem'>{a}</b> <b>{E(b)}</b><br><span class='note'>{E(c)}</span></div>" for a, b, c in pillars)
    surv = "".join(f"<li>{E(q)}: {n}명 / {L['survey_n']}명</li>" for q, n in L["survey"])
    voices = ["염증이 무조건 나쁜 건 줄만 알았는데, 아니었네요!",
              "숙면이 중요하다고만 알고 있었는데, 새롭게 숙면이 항노화임을 배웠습니다.",
              "식사 후 10분간은 움직이고, 걷기는 20~30분 천천히 걸으라는 말이 기억에 남습니다.",
              "식습관과 생활규칙에 대해서 많은 도움을 받았습니다."]
    voice = "".join(f"<li>“{E(v)}”</li>" for v in voices)
    wants = "치매·합병증·당뇨 예방, 수면, 갱년기, 건망증, 실제 진료 이야기, 그리고 ‘쉬운 AI 사용하기’까지"
    body = (f"<nav class='crumbs'><a href='index.html'>홈</a> › 지역 건강 강연</nav>"
            f"<h2>진료실 밖에서도 어르신 곁에</h2>"
            f"<p>이종호 대표원장은 2013년 상도동에서 문을 연 뒤로 13년째 이 동네 어르신들을 뵙고 있습니다. 진료실에서 “기력이 없다”는 말씀을 들을 때마다, "
            f"일상에서 스스로 해 볼 수 있는 방법을 더 많은 분께 알려 드리고 싶었습니다. 그래서 복지관과 지역 기관을 찾아가 건강 강연을 합니다.</p>"
            f"<h2>{E(L['date_ko'])} · {E(L['place'])}</h2>"
            f"<p><b>「{E(L['title'])}」</b> 특강을 {E(L['region'])} {E(L['place'])}에서 열었습니다. 어렵지 않은 말로, 오늘부터 해 볼 수 있는 작은 습관을 중심으로 이야기했습니다. "
            f"궁금한 점은 그 자리에서 편하게 여쭤보시고, 진료실에서도 다시 여쭤보시라고 말씀드렸습니다.</p>"
            + fig("lecture-intro", "이종호 대표원장이 복지관 강의실에서 강연을 시작하는 모습", "강의를 시작하며: “오늘 나누는 작은 습관들이 여러분의 하루하루를 더 가볍게 해드리길 바랍니다”")
            + "<h3>강연에서 나눈 네 가지: 식(食)·동(動)·심(心)·약(藥)</h3>"
            + f"<div class='grid'>{pill}</div>"
            + "<p>먹는 것, 움직이는 것, 마음을 다루는 것이 먼저이고, 한약은 그다음에 필요할 때 진료로 살펴서 정하는 것이라는 순서를 함께 이야기했습니다. "
              "식사 뒤 10분 정도 가볍게 움직이기, 20~30분 천천히 걷기, 잠을 회복의 시간으로 지키기처럼 집에서 바로 해 볼 수 있는 것들을 나눴습니다.</p>"
            + fig("lecture-pillars", "식·동·심·약 네 가지를 설명하는 강연 슬라이드", "식(食)·동(動)·심(心)·약(藥), 생활 속 항노화의 네 기둥")
            + fig("lecture-room", "복지관 강의실에서 강연을 듣는 지역 주민들", "강감찬관악종합사회복지관 강의실")
            + "<h3>참석하신 분들이 남겨 주신 말씀</h3>"
            + f"<p>강연이 끝난 뒤 만족도 조사지 {L['survey_n']}장을 받았습니다.</p><ul>{surv}</ul>"
            + f"<p>가장 도움이 된 내용으로는 이런 말씀을 적어 주셨습니다.</p><ul>{voice}</ul>"
            + f"<p>다음에 듣고 싶은 주제로는 {E(wants)} 적어 주셨습니다. 주신 의견은 다음 강연과 홈페이지 한방가이드 글에 반영하겠습니다.</p>"
            + "<p class='note'>조사지 원본에는 손글씨와 개인 정보가 있어 올리지 않고, 문장만 옮겼습니다. 강연 내용은 일반적인 건강 정보이며 개인의 진단이나 치료를 대신하지 않습니다.</p>"
            + "<h3>강감찬관악종합사회복지관과 업무협약</h3>"
            + "<p>강연과 함께 강감찬관악종합사회복지관과 지역 주민 건강 지원을 위한 업무협약을 맺었습니다. 앞으로도 복지관과 함께 어르신들의 건강 이야기를 이어 가겠습니다.</p>"
            + fig("lecture-mou", "좋은꿈참사랑한의원 이종호 대표원장과 강감찬관악종합사회복지관 관장의 업무협약", "강감찬관악종합사회복지관과 업무협약")
            + "<h3>건강 강연을 요청하시려면</h3>"
            + "<p>복지관, 경로당, 주민센터, 학교 등에서 어르신 건강·수면·생활습관 강연을 원하시면 전화로 문의해 주세요. "
              "<a href='tel:028157510'>02-815-7510</a></p>"
            + "<p>이종호 대표원장이 주로 강의하는 주제: 어르신 낙상 예방과 생활 안전, 양생법·항노화 건강관리, 치매 예방과 기억력 관리, 당뇨·대사증후군과 체중 관리, 불면증·만성 소화불량 등 생활 한방 건강관리.</p>")
    ld = {"@context": "https://schema.org", "@type": "EducationEvent", "name": f"{L['title']} 건강 특강",
          "startDate": L["date"], "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
          "location": {"@type": "Place", "name": L["place"], "address": {"@type": "PostalAddress", "addressLocality": "관악구", "addressRegion": "서울", "addressCountry": "KR"}},
          "organizer": {"@type": "MedicalClinic", "name": CFG["clinic_name"], "url": f"{BASE}/"},
          "performer": {"@type": "Person", "name": "이종호", "jobTitle": "대표원장 (한의사)"},
          "image": [f"{BASE}/images/real/lecture-intro.jpg"], "description": "생활 속 항노화의 네 기둥 식(食)·동(動)·심(心)·약(藥)을 주제로 한 어르신 건강 특강"}
    write(ROOT / "lectures.html", shell(f"지역 건강 강연 | {CFG['clinic_name']}", "좋은꿈참사랑한의원 이종호 대표원장의 복지관 건강 특강(양생법과 한의학적 항노화)과 강감찬관악종합사회복지관 업무협약 기록", 0, body,
                                       jsonld(ld), "lectures.html", "website", hero=hero_html(0, "home", "지역 건강 강연", "진료실 밖에서도 어르신 곁에", False)))


HERB_FAQ = [  # content/pages_draft.md 9번(맞춤 한약) 원고 + 이 페이지의 탕전 과정 설명
    ("한약은 한의원에서 직접 달이나요?",
     "네. 진찰과 상담을 거쳐 처방이 정해지면 원내에서 약재를 한 첩 분량씩 저울에 달아 확인하고, 대표원장이 검수한 뒤 달여 파우치에 담아 드립니다."),
    ("양약과 한약을 같이 먹어도 되나요?",
     "많은 경우 가능하지만, 복용 중인 약을 모두 알려 주셔야 상호작용을 확인할 수 있습니다. 보통 시간 간격을 두고 드시도록 안내합니다."),
    ("한약은 얼마나 먹어야 하나요?",
     "증상과 처방 목적, 복용 후 상태에 따라 다릅니다. 복용 중간에 몸의 변화를 확인하고 조절합니다."),
    ("한약을 먹으면 간이 나빠지나요?",
     "간 질환이 있거나 걱정되시면 미리 알려 주세요. 처방할 때 간·신장 상태를 고려하며, 복용 중 이상이 있으면 복용을 멈추고 바로 연락해 주시면 됩니다."),
    ("임신 중이나 수유 중에도 먹을 수 있나요?",
     "약재마다 안전성을 따로 검토해야 합니다. 임신 중이거나 수유 중이시면 진료 때 꼭 말씀해 주세요."),
]


def build_herbroom():
    items = herb_photos()
    if not items:
        return
    def figs(kind, n, cap):
        sel = [x for x in items if x["kind"] == kind][:n]
        return "".join(f"<figure><img src='images/{E(x['file'])}' alt='{E(cap)}' loading='lazy' width='1400' height='756'><figcaption>{E(cap)}</figcaption></figure>" for x in sel)
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 원내 탕전 기록</nav>"
            "<h2>원내 탕전 기록</h2>"
            "<div class='herbintro'><div>"
            "<p>상도역 좋은꿈참사랑한의원의 한약은 원내에서 준비합니다. 진료실에서 맥을 짚고 이야기를 들은 뒤 처방을 정하는데, 그 처방이 어떤 약재로, "
            "어떤 분량으로 담기는지까지 제 눈으로 확인하고 싶어서입니다. 같은 병명이라도 사람마다 몸이 다르고, 그래서 한약도 달라집니다.</p>"
            "<p>처방하기 전에는 주된 증상과 함께 소화, 수면, 체온, 대소변, 복용 중인 약, 간·신장 상태까지 여쭙습니다. 처방이 정해지면 약재를 한 첩 분량씩 "
            "저울에 달아 확인하고, 녹용처럼 따로 살펴야 하는 약재는 한 번 더 들여다봅니다. 그다음 대표원장인 제가 검수한 뒤에 달입니다.</p>"
            "<p>저는 식품의약품안전처장이 위촉한 한약 관능검사 전문가로도 활동하고 있습니다. 약재의 품질을 살피는 일을 가볍게 여기지 않으려 합니다. "
            "아래 사진은 2026년 7월부터 11월까지 실제 조제 과정에서 찍은 기록입니다.</p>"
            "<p class='byline'>— 대표원장 이종호(한의사 면허 19769)</p></div>"
            "<figure><img src='images/real/r4-herb-cabinet.webp' alt='지실·감초·소목·우슬·황금 등 한약재를 담아 둔 원내 약재 진열장' " + img_wh('images/real/r4-herb-cabinet.webp') + " loading='lazy'>"
            "<figcaption>원내 약재 진열장</figcaption></figure></div>"
            "<figure class='hubinfo'><img src='images/info/herbal-room-flow.svg' alt='진단·상담, 처방, 약재 계량·검수, 원내 탕전 4단계 안내 그림' width='1200' height='675' loading='lazy'></figure>"
            "<p class='note'>사진 속 약재 구성은 환자분마다 다르며, 같은 처방을 권하는 것이 아닙니다. 환자분의 이름과 조제일이 적힌 이름표는 보이지 않도록 잘라 냈습니다.</p>"
            "<h2>약재를 펼쳐 확인합니다</h2><div class='gallery herbgal'>" + figs("herb", 30, "처방에 맞춰 준비한 약재") + "</div>"
            "<h2>녹용은 따로 살핍니다</h2><div class='gallery herbgal'>" + figs("antler", 8, "조제 전에 확인하는 녹용 절편") + "</div>"
            "<h2>무게를 달아 기록합니다</h2><div class='gallery herbgal'>" + figs("scale", 8, "처방 분량을 저울로 확인") + "</div>"
            "<h2>약재를 정리해 두고, 정량을 다시 확인합니다</h2><div class='gallery'>" + real_figs([
                ("r3-herb-storage-trays-1.webp", "약재 이름표를 붙여 정리한 약재 보관함", 1200, 1600),
                ("r3-herbs-in-cloth-1.webp", "면포에 담아 달이기 전 준비한 약재", 1050, 1400),
                ("r3-herb-weighing-1.webp", "약재를 저울에 달아 정량을 확인하는 모습", 1050, 1400),
                ("r3-herb-weighing-2.webp", "디지털 저울로 약재 무게를 재는 모습", 1200, 1600)], "") + "</div>"
            "<h2>달인 뒤에는 파우치에 담아 포장합니다</h2><div class='gallery'>" + real_figs([
                ("r3-herb-pouch-box-1.webp", "상자에 가지런히 담긴 한약 파우치", 1200, 1600),
                ("r3-herb-pouch-1.webp", "한의원 한약 파우치", 1080, 1440),
                ("r3-herb-pouch-2.webp", "두 가지 디자인의 한약 파우치", 1080, 1440),
                ("r3-herb-pouch-3.webp", "분홍색 한약 파우치", 1080, 1440),
                ("r3-herb-gift-box-1.webp", "한의원 로고가 찍힌 한약 상자", 1600, 1235),
                ("r3-herb-gift-wrap-1.webp", "금색 보자기로 싼 한약 꾸러미", 1600, 993),
                ("r3-herb-gift-wrap-2.webp", "보자기로 싼 한약 꾸러미", 1600, 1200)], "") + "</div>"
            "<p>한약은 진단과 상담을 거친 뒤에 처방합니다. 복용 중인 약이 있으면 꼭 알려 주세요. 문의 02-815-7510</p>"
            "<h2>한약에 대해 더 읽어 보기</h2><ul>"
            "<li><a data-link-location='herbroom_more' href='gongjindan.html'>공진단 이야기 — 대표원장이 설명하는 공진단</a></li>"
            "<li><a data-link-location='herbroom_more' href='guide/herbal/index.html'>한약·공진단 한방가이드 글 모두 보기</a></li></ul>"
            "<section class='faqblock'><h2>자주 묻는 질문</h2>"
            + "".join(f"<details class='qa'><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in HERB_FAQ) + "</section>"
            f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 마지막 확인 {TODAY} · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다.</p>")
    ld = {"@context": "https://schema.org", "@type": "ImageGallery", "name": "좋은꿈참사랑한의원 원내 탕전 기록",
          "about": "한약 조제 과정(약재 확인·계량·검수)", "image": [f"{BASE}/images/{x['file']}" for x in items[:20]]}
    desc = ("상도역 좋은꿈참사랑한의원 원내 탕전 기록입니다. 진맥·상담 뒤 처방한 약재를 한 첩씩 저울로 확인하고 대표원장이 검수해 달이는 과정을 "
            "실제 사진과 자주 묻는 질문으로 안내합니다.")
    faq_ld = clinic_ld("herbal-room.html", f"원내 탕전 기록 | {CFG['clinic_name']}", desc, "faq", {"mainEntity": faq_entities(body)})
    write(ROOT / "herbal-room.html", shell(f"원내 탕전 기록 — 대표원장이 약재를 검수합니다 | {CFG['clinic_name']}", desc, 0, body,
                                          faq_ld + "\n" + jsonld(ld), "herbal-room.html", "website", hero=hero_html(0, "herbal", "원내 탕전 기록", "약재를 펼치고, 달아 보고, 확인합니다", False, img="herbpub/herb-018.jpg")))


PULSE_FAQ = [
    ("정말 모든 환자에게 진맥을 하나요?",
     "네. 좋은꿈참사랑한의원에서는 처음 오신 분, 다시 오신 분, 통증으로 오신 분, 교통사고 뒤 오신 분 모두 진맥을 합니다. 아픈 곳이 어디든 몸 전체의 상태를 함께 살피기 위해서입니다."),
    ("허리나 어깨가 아파서 왔는데도 맥을 보나요?",
     "네. 같은 통증이라도 잠을 설치거나 소화가 무겁거나 몸이 많이 긴장된 상태라면 살필 점이 달라질 수 있습니다. 맥은 아픈 부위만이 아니라 그날의 몸 상태를 함께 보는 단서입니다."),
    ("진맥은 얼마나 걸리고 아프지는 않나요?",
     "양쪽 손목에 손가락을 가볍게 대어 살피며, 길지 않습니다. 누르는 힘이 불편하면 바로 말씀해 주세요. 손목에 상처나 깁스가 있으면 미리 알려 주시면 됩니다."),
    ("진맥 전에 무엇을 피하면 좋나요?",
     "도착하시면 5분쯤 앉아 숨을 고르신 뒤 맥을 보는 것이 좋습니다. 진료 직전의 커피 같은 카페인 음료, 격한 운동, 과식은 맥을 평소와 다르게 만들 수 있으니 피하시고, 그랬다면 그대로 말씀해 주세요."),
    ("맥만 짚어 보면 병을 알 수 있나요?",
     "아니요. 진맥만으로 모든 질환을 진단하지는 않습니다. 말씀해 주신 이야기, 혀와 배의 상태, 필요할 때는 초음파나 검사 결과를 함께 모아 판단하며, 다른 의료기관의 검사가 필요하다고 판단되면 먼저 안내해 드립니다."),
    ("다시 올 때마다 맥을 또 보는 이유가 있나요?",
     "지난 진료 때의 맥과 오늘의 맥을 비교하기 위해서입니다. 그사이 잠, 소화, 통증이 어떻게 달라졌는지 여쭙는 말씀과 함께 보고 오늘 치료를 다시 정합니다."),
    ("스마트워치로 재는 맥박과 진맥은 같은 건가요?",
     "다릅니다. 스마트워치나 혈압계는 1분에 몇 번 뛰는지를 숫자로 알려 줍니다. 진맥은 빠르기와 함께 맥이 느껴지는 깊이, 힘, 모양, 양손의 차이를 손끝으로 살핍니다. 맥박 수가 계속 지나치게 빠르거나 느리면 내과 등 진료를 권합니다."),
    ("심장 질환이 있거나 혈압약을 먹고 있어도 진맥을 받아도 되나요?",
     "네, 받으실 수 있습니다. 다만 복용 중인 약이 맥에 영향을 줄 수 있어 약 이름을 알려 주시면 함께 고려합니다. 복용 중인 약은 처방한 의사와 상의 없이 줄이거나 끊지 마세요."),
]


def build_pulse():
    """진맥 이야기(pulse.html): 대표원장의 진맥 원칙을 쉬운 말로 소개하는 단독 페이지."""
    faq = "".join(f"<details class='qa'><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in PULSE_FAQ)
    more = [("pulse-diagnosis-what-is-it", "한의원에서 손목 맥을 짚는 진맥은 무엇인가요?"),
            ("pulse-diagnosis-what-we-check", "맥진은 어떻게 하고 손목에서 무엇을 살피나요?"),
            ("why-pulse-diagnosis-for-pain-patients", "통증 때문에 왔는데 진맥은 왜 하나요?"),
            ("before-pulse-check-preparation", "맥을 짚기 전에 운동이나 카페인은 어떻게 하면 되나요?"),
            ("pulse-recheck-on-return-visit", "다시 올 때마다 맥을 또 짚는 이유는 무엇인가요?"),
            ("pulse-fast-weak-meaning", "맥이 빠르다, 약하다는 말은 무슨 뜻인가요?")]
    more_html = "".join(f"<li>{inline(f'[{t}]({s})')}</li>" for s, t in more)
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='about.html'>한의원 소개</a> › 진맥 이야기</nav>"
            "<section class='pulsepage'>"
            + render_doc((ROOT / "content" / "director" / "pulse-guide.md").read_text(encoding="utf-8")) +
            "<p class='note'>— 좋은꿈참사랑한의원 대표원장 이종호(한의사 면허 19769)</p>"
            "<figure class='hubinfo'><img src='images/real/pulse-hands-1.webp' alt='대표원장이 손목 받침대 위에서 맥을 짚는 모습' width='1600' height='788' loading='lazy'><figcaption>모든 진료는 진맥에서 시작합니다.</figcaption></figure><figure class='hubinfo'><img src='images/info/pulse-flow.svg' alt='쉬고 앉기, 양손 맥 짚기, 함께 보기, 치료와 다음 진료로 이어지는 진맥 4단계 안내 그림' width='1200' height='675' loading='lazy'></figure>"
            "<p class='morecol'><a href='column-pulse.html'>원장 이야기 더 보기 — 제가 환자분께 두 손목을 내어 달라고 하는 이유 →</a></p>"
            "<h2>진맥 전에 이렇게 해 주세요</h2>"
            "<ul>"
            "<li>도착하시면 대기실에서 <b>5분쯤 앉아 숨을 고른 뒤</b> 맥을 봅니다. 서둘러 걸어오셨거나 계단을 오르셨다면 더 그렇습니다.</li>"
            "<li>진료 직전의 <b>커피 같은 카페인 음료, 격한 운동, 과식</b>은 피해 주세요. 이미 드셨거나 운동을 하셨다면 그대로 말씀해 주시면 됩니다.</li>"
            "<li>손목시계나 팔찌, 꽉 끼는 소매는 미리 풀어 두면 편합니다.</li>"
            "<li>복용 중인 약(혈압약·심장약·갑상선약 등)이 있으면 이름을 알려 주세요. 약에 따라 맥이 달라질 수 있습니다.</li>"
            "</ul>"
            "<h2>진맥으로 할 수 없는 것</h2>"
            "<p>진맥은 몸 상태를 살피는 중요한 단서이지만, <b>진맥만으로 모든 질환을 진단하지는 않습니다.</b> 심전도, 혈액 검사, 영상 검사를 대신하지도 않습니다. "
            "말씀과 다른 진찰, 필요할 때는 초음파나 검사 결과를 함께 모아 판단하며, 다른 의료기관의 검사나 진료가 필요하다고 판단되면 그 내용을 먼저 권해 드립니다.</p>"
            "<p>맥이 매우 불규칙하면서 가슴 통증, 숨참, 어지럼, 실신이 함께 있다면 한의원보다 <b>응급실</b>이 먼저입니다. 복용 중인 약은 처방한 의사와 상의 없이 줄이거나 끊지 마세요.</p>"
            "<h2>진맥에 대해 더 읽어 보기</h2>"
            f"<ul>{more_html}<li><a href='guide/diagnosis/index.html'>진찰 방법 안내 전체 보기</a></li></ul>"
            f"<section class='faqblock'><h2>자주 묻는 질문</h2>{faq}</section>"
            f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 마지막 확인 {TODAY} · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 문의 02-815-7510</p>"
            "</section>")
    title = "진맥 이야기"
    desc = "좋은꿈참사랑한의원은 모든 분께 진맥을 합니다. 왜 맥을 보는지, 손끝으로 무엇을 살피는지, 치료·재진과 어떻게 이어지는지, 진맥 전 준비와 한계를 쉬운 말로 안내합니다."
    ld = clinic_ld("pulse.html", f"{title} | {CFG['clinic_name']}", desc, "faq", {"mainEntity": faq_entities(body)})
    write(ROOT / "pulse.html", shell(f"{title} — 모든 분께 진맥을 합니다 | {CFG['clinic_name']}", desc, 0, body, ld, "pulse.html", "website",
                                     hero=hero_html(0, "diagnosis", title, "진맥(診脈): 손끝으로 읽는 몸의 이야기", False, img="real/pulse-director-consult-1.webp")))


SAFE_HEAD = re.compile(r"먼저 (?:다른 의료기관에서 )?확인이 필요|바로 진료|바로 확인|바로 연락|먼저 확인할 것|응급실|지켜보고")


def safety_box(html):
    """'이런 증상은 먼저 확인이 필요합니다' 같은 안전 단락을 부드러운 안내 상자로(원장님 "보기좋게 이쁘게" 2026-11-25).
    109 는 누르면 전화가 걸리는 둥근 표시, '가까운 응급실' 은 굵게."""
    def deco(t):
        t = re.sub(r"(?<![\d>/:-])109(?![\d<])", "<a class='hotline' href='tel:109' data-link-location='safety_109'>☎ 109</a>", t)
        t = re.sub(r"(?<!<b>)(가까운 응급실)", r"<b>\1</b>", t)
        return t
    KEY = re.compile(r"응급실|109|119|병원|의료기관|의학과|복용|약은|검사|바로 (?:진료|확인|연락|가)|지켜보|즉시|당일|진료를 받")
    def wrap(m):
        parts = re.findall(r"(<(?:p|ul|ol)\b.*?</(?:p|ul|ol)>)", m.group(2), re.S)
        last = max((i for i, b in enumerate(parts) if KEY.search(re.sub(r"<[^>]+>", "", b))), default=len(parts) - 1)
        inside, rest = "".join(parts[:last + 1]), "".join(parts[last + 1:])
        if not inside:
            return m.group(0)
        return ("<section class='safety' aria-label='먼저 확인이 필요한 경우'><h2>" + m.group(1) + "</h2>"
                + deco(inside) + "</section>" + rest)
    pat = re.compile(r"<h2>((?:(?!</h2>).)*?)</h2>((?:(?!<h2[ >]|<figure|<aside|<details).)*)", re.S)
    return pat.sub(lambda m: wrap(m) if SAFE_HEAD.search(re.sub(r"<[^>]+>", "", m.group(1))) else m.group(0), html)


def with_toc(html, label="이 글의 차례"):
    """<h2> 에 id 를 달고, 소제목이 4개 이상이면 앞에 붙일 목차를 돌려준다."""
    heads = []
    def mark(m):
        heads.append(re.sub(r"<[^>]+>", "", m.group(1)))
        return f"<h2 id='s{len(heads)}'>{m.group(1)}</h2>"
    html = re.sub(r"<h2>(.*?)</h2>", mark, html, flags=re.S)
    if len(heads) < 4:
        return "", html
    items = "".join(f"<li><a href='#s{i}'>{t}</a></li>" for i, t in enumerate(heads, 1))
    return f"<nav class='toc' aria-label='{label}'><b>{label}</b><ol>{items}</ol></nav>", html


LECTURE_COLUMNS = [
    ("column-fall-walking.html", "column-fall-walking.md", "넘어지지 않는 몸, 작게 오래 걷는 이야기", "pain",
     "이종호 대표원장의 낙상 예방 강연. 천천히 오래 걷기, 보폭 줄이기, 다리 힘과 재활, 약과 집 안 환경, 넘어졌을 때 할 일.", "원장 칼럼: 낙상과 걷기"),
    ("column-keep-health.html", "column-keep-health.md", "받은 건강을 단단히 지키는 일: 양생 이야기", "herbal",
     "이종호 대표원장의 양생 강연. 생명을 기른다는 뜻, 잘 쉬고 치료하고 움직이기, 편안한 치료, 진맥 상담, 한약재를 고르는 마음.", "원장 칼럼: 양생 이야기"),
]


def build_lecture_columns():
    """티로에 기록된 원장님 강연을 바탕으로 한 긴 칼럼(content/director/*.md)."""
    for fn, md, title, cat, desc, _menu in LECTURE_COLUMNS:
        toc, doc = with_toc(render_doc((ROOT / "content" / "director" / md).read_text(encoding="utf-8")))
        others = "".join(f"<li><a href='{f}'>{E(t)}</a></li>" for f, _m, t, *_r in LECTURE_COLUMNS if f != fn)
        body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='about.html'>한의원 소개</a> › 원장 칼럼</nav>"
                "<article class='pulsepage column'><p class='byline'>좋은꿈참사랑한의원 대표원장 이종호</p>" + toc + doc +
                f"<h3>이어서 읽기</h3><ul>{others}<li><a href='column-pulse.html'>제가 환자분께 두 손목을 내어 달라고 하는 이유</a></li></ul>"
                f"<p class='note'>글: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 동네 어르신 대상 강연 기록(2022년)을 바탕으로 정리하며 건강 정보는 보완했습니다. 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 문의 02-815-7510</p></article>")
        ld = clinic_ld(fn, f"{title} | {CFG['clinic_name']}", desc, "WebPage",
                       {"@type": "Article", "headline": title, "datePublished": "2026-11-25", "author": {"@type": "Person", "name": "이종호", "jobTitle": "대표원장 한의사"}})
        write(ROOT / fn, shell(f"{title} | {CFG['clinic_name']}", desc, 0, body, ld, fn, "article",
                               hero=hero_html(0, cat, title, "원장 칼럼 · 대표원장 이종호", False, img="real/pulse-director-consult-1.webp")))


def build_column_pulse():
    """원장 칼럼(column-pulse.html): 원장님 게시 승인 1인칭 수필(2026-11-25)."""
    title = "제가 환자분께 두 손목을 내어 달라고 하는 이유"
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='about.html'>한의원 소개</a> › <a href='pulse.html'>진맥 이야기</a> › 원장 칼럼</nav>"
            "<article class='pulsepage column'>"
            "<p class='byline'>좋은꿈참사랑한의원 대표원장 이종호</p>"
            + "".join(with_toc(render_doc((ROOT / "content" / "director" / "column-pulse-two-wrists.md").read_text(encoding="utf-8")))) +
            "<p class='morecol'><a href='pulse.html'>← 진맥 이야기: 어디를, 어떻게 짚고 무엇을 보는지</a></p>"
            f"<p class='note'>글: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 2026-11-25 · 진료실 이야기는 특정 환자를 알아볼 수 없게 일반적인 내용으로 썼습니다. 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 문의 02-815-7510</p>"
            "</article>")
    desc = "좋은꿈참사랑한의원 이종호 대표원장의 칼럼. 추나를 하던 손으로 진맥을 배운 이야기, 손목 위에서 살피는 것, 어깨가 아파 오신 분께 잠을 묻는 까닭, 다시 오실 때마다 맥을 짚는 이유."
    ld = clinic_ld("column-pulse.html", f"{title} | {CFG['clinic_name']}", desc, "WebPage",
                   {"@type": "Article", "headline": title, "datePublished": "2026-11-25", "author": {"@type": "Person", "name": "이종호", "jobTitle": "대표원장 한의사"}})
    write(ROOT / "column-pulse.html", shell(f"{title} — 원장 칼럼 | {CFG['clinic_name']}", desc, 0, body, ld, "column-pulse.html", "article",
                                            hero=hero_html(0, "diagnosis", title, "원장 칼럼 · 대표원장 이종호", False, img="real/pulse-director-consult-1.webp")))


def build_gongjindan():
    """공진단 이야기(gongjindan.html): 원장님 1인칭 공진단 전용 안내(유래·구성·세 가지 공진단·사향·연구·복용·주의·FAQ). 가격 없음."""
    title = "공진단 이야기"
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='guide/herbal/index.html'>한약·공진단</a> › 공진단 이야기</nav>"
            "<article class='pulsepage column'>"
            "<p class='byline'>좋은꿈참사랑한의원 대표원장 이종호</p>"
            + render_doc((ROOT / "content" / "director" / "gongjindan.md").read_text(encoding="utf-8")) +
            "<p class='morecol'><a href='guide/herbal/index.html'>한약·공진단 글 모두 보기 →</a></p>"
            f"<p class='note'>글: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 2026-11-25 · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 공진단은 진찰과 상담 뒤 체질과 상태에 맞을 때 처방합니다. 문의 02-815-7510</p>"
            "</article>")
    desc = "공진단이 무엇인지, 원방 구성과 사향 이야기, 한의원 처방·일반의약품·식품의 차이, 연구가 어디까지 왔는지, 복용·보관과 먼저 상담이 필요한 경우를 대표원장이 설명합니다."
    ld = clinic_ld("gongjindan.html", f"{title} | {CFG['clinic_name']}", desc, "WebPage",
                   {"@type": "Article", "headline": "공진단 이야기: 대표원장이 설명하는 공진단", "datePublished": "2026-11-25", "author": {"@type": "Person", "name": "이종호", "jobTitle": "대표원장 한의사"}})
    write(ROOT / "gongjindan.html", shell(f"{title} — 대표원장이 설명하는 공진단 | {CFG['clinic_name']}", desc, 0, body, ld, "gongjindan.html", "article",
                                          hero=hero_html(0, "herbal", title, "진맥 먼저, 맞는 분께만 · 대표원장 이종호", False, img="real/r4-herb-cabinet.jpg")))


def build_inbody():
    """인바디 이야기(inbody.html): 결과지 읽는 법·비교하는 법·진료실에서 쓰는 법(일반 정보, 환자 자료·전후 비교 없음 — 의료법 56조)."""
    title = "인바디 이야기"
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='diet.html'>대사·식욕</a> › 인바디 이야기</nav>"
            "<article class='pulsepage column'>"
            "<p class='byline'>좋은꿈참사랑한의원 대표원장 이종호</p>"
            "<figure class='hubinfo'><img src='images/info/inbody-example.svg' alt='인바디 결과지를 읽는 순서를 보여 주는 예시 그림(실제 환자 자료 아님)' width='1200' height='675' loading='lazy'></figure>"
            + render_doc((ROOT / "content" / "director" / "inbody.md").read_text(encoding="utf-8")) +
            "<p class='morecol'><a href='guide/metabolic/index.html'>대사·식욕 글 모두 보기 →</a></p>"
            f"<p class='note'>글: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 2026-11-25 · 그림의 숫자는 설명을 위한 예시이며 실제 환자 자료가 아닙니다. 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 문의 02-815-7510</p>"
            "</article>")
    desc = "인바디 결과지를 위에서부터 읽는 법, 측정 전에 지킬 것, 두 장을 비교할 때 보는 것, 진료실에서 진맥과 함께 참고하는 방식을 대표원장이 설명합니다(예시 그림, 실제 환자 자료 없음)."
    ld = clinic_ld("inbody.html", f"{title} | {CFG['clinic_name']}", desc, "WebPage",
                   {"@type": "Article", "headline": "인바디 이야기: 결과지 읽는 법과 진료실에서 쓰는 법", "datePublished": "2026-11-25", "author": {"@type": "Person", "name": "이종호", "jobTitle": "대표원장 한의사"}})
    write(ROOT / "inbody.html", shell(f"{title} — 결과지 읽는 법 | {CFG['clinic_name']}", desc, 0, body, ld, "inbody.html", "article",
                                      hero=hero_html(0, "metabolic", title, "숫자 한 장보다 흐름을 봅니다 · 대표원장 이종호", False)))


def build_explain(posts):
    """진료실 설명판(explain.html): 원장님이 진료실 화면에서 환자에게 병을 설명할 때 쓰는 목록(11/26 원장님: '평소에 홈피를 설명용으로').
    분류별로 긴 설명 글(기둥 글)부터, 위 검색 칸으로 바로 찾기. 글 링크에 ?big 을 붙여 큰 글씨·버튼 숨김으로 엽니다(extras.js)."""
    title = "진료실 설명판"
    groups = []
    for c, name in CATS.items():
        ps = [p for p in posts if p["category"] == c]
        if not ps:
            continue
        ps.sort(key=lambda p: -len(re.sub(r"<[^>]+>", "", p["body"])))
        items = "".join(
            f"<li data-k='{E(p['title'].lower())}'><a href='{post_url(p)}?big' data-link-location='explain'>{E(p['title'])}</a>"
            + (" <span class='xp-pillar'>자세히</span>" if len(re.sub(r"<[^>]+>", "", p["body"])) >= 5000 else "") + "</li>"
            for p in ps)
        groups.append(f"<section class='xp-cat' id='x-{c}'><h2>{E(name)} <small>{len(ps)}편</small></h2><ol>{items}</ol></section>")
    chips = "".join(f"<a href='#x-{c}'>{E(n)}</a>" for c, n in CATS.items() if any(p["category"] == c for p in posts))
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 진료실 설명판</nav>"
            "<article class='xp'><h1>진료실 설명판</h1>"
            "<p class='lead'>진료실에서 화면을 함께 보며 설명할 때 쓰는 목록입니다. 병 이름이나 증상을 입력하면 바로 찾을 수 있고, 글을 누르면 큰 글씨로 열립니다. 환자분은 같은 글을 휴대폰에서 다시 읽으실 수 있습니다.</p>"
            "<form class='xp-find' onsubmit='return false'><label for='xpq' class='sr'>병 이름이나 증상</label>"
            "<input id='xpq' type='search' placeholder='예: 오십견, 역류성 식도염, 어지럼, 생리통' autocomplete='off'></form>"
            f"<nav class='xp-chips' aria-label='분류 바로가기'>{chips}</nav>"
            + "".join(groups) +
            "<p class='note'>각 글은 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 진료는 진찰 뒤 필요한 것만 고릅니다. 문의 02-815-7510</p>"
            "</article>"
            "<script>(function(){var q=document.getElementById('xpq');if(!q)return;q.addEventListener('input',function(){var v=q.value.trim().toLowerCase().replace(/\\s+/g,'');"
            "document.querySelectorAll('.xp-cat').forEach(function(s){var n=0;s.querySelectorAll('li').forEach(function(li){var ok=!v||li.getAttribute('data-k').replace(/\\s+/g,'').indexOf(v)>-1;li.hidden=!ok;if(ok)n++;});s.hidden=n===0;});});})();</script>")
    desc = "진료실에서 환자분께 병과 증상을 설명할 때 쓰는 목록입니다. 분류별 설명 글을 병 이름·증상으로 바로 찾고 큰 글씨로 열 수 있습니다."
    ld = clinic_ld("explain.html", f"{title} | {CFG['clinic_name']}", desc, "CollectionPage")
    write(ROOT / "explain.html", shell(f"{title} — 병과 증상 설명 글 모음 | {CFG['clinic_name']}", desc, 0, body, ld, "explain.html", "article"))


ACU_FAQ = [  # content/pages_draft.md 8번 원고의 자주 묻는 질문
    ("허리가 아픈데 왜 손발에 침을 놓나요?",
     "한의학에서는 경락으로 연결된 먼 부위를 자극해 몸을 조절하는 방법을 씁니다. 필요하면 아픈 부위 치료와 함께 진행합니다."),
    ("침은 많이 맞을수록 좋은가요?",
     "아닙니다. 상태에 맞는 자리와 자극이 중요합니다."),
    ("침을 맞고 나서 주의할 점이 있나요?",
     "당일 과음이나 무리한 운동은 피하시고, 시술 부위에 붓기나 열감이 계속되면 연락해 주세요."),
    ("혈액을 묽게 하는 약을 먹고 있어도 되나요?",
     "대부분 가능하지만 멍이 들기 쉬울 수 있어 미리 알려 주셔야 합니다."),
]


def build_acupuncture():
    """침 치료·사암침 안내(acupuncture.html): 원장님 원고 8번을 그대로 옮긴 단독 페이지."""
    faq = "".join(f"<details class='qa'><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in ACU_FAQ)
    more = [("pain/acupuncture-before-first-treatment", "침 치료를 처음 받기 전에 무엇을 알려 주면 되나요?"),
            ("first-visit/afraid-of-needles-tell-clinic-how", "침이 무서울 때는 한의원에 어떻게 말하면 되나요?"),
            ("first-visit/eating-before-acupuncture-meal-timing", "침 치료를 받기 전에 식사는 어떻게 하면 되나요?"),
            ("first-visit/after-acupuncture-daily-life-cautions", "침 치료를 받은 날에는 샤워나 운동을 해도 되나요?"),
            ("first-visit/acupuncture-bruise-soreness-what-to-know", "침을 맞은 자리에 멍이 들거나 뻐근한 느낌이 남는 것은 괜찮은가요?"),
            ("pain/pharmacopuncture-overview", "약침은 무엇이고 시술 전에 무엇을 알려야 하나요?")]
    more_html = "".join(f"<li><a href='guide/{s}.html'>{E(t)}</a></li>" for s, t in more if (ROOT / "guide" / f"{s}.html").exists())
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › <a href='guide/pain/index.html'>통증·추나</a> › 침 치료·사암침</nav>"
            "<section class='pulsepage'>"
            "<h2>지금 이 환자에게 필요한 침</h2>"
            "<p class='lead'>침 치료는 아픈 부위에 직접 놓기도 하고, 한의학적 변증에 따라 손발처럼 떨어진 곳에 놓기도 합니다. "
            "침의 개수나 자극의 세기가 치료의 질을 정하지 않습니다. 지금 이 몸에 필요한 자리와 자극량을 고르는 것이 중요합니다.</p>"
            "<img class='photo soft wide' src='images/real/r3-treatment-room-beds-1.webp' alt='침상이 놓인 밝은 치료실과 안쪽 복도' width='1200' height='1600' loading='lazy'>"
            "<h2>사암침</h2>"
            "<p>사암침은 오행과 경락의 원리로 혈자리를 고르는 조선시대부터 전해 온 침법입니다. 아픈 부위만 보지 않고 체온, 소화, 수면, 배설 같은 전신 상태를 함께 고려합니다. "
            "저희는 국소 치료와 전신 치료를 상황에 맞게 함께 씁니다. 전통 이론에 따른 설명과 현대 연구로 확인된 내용은 구분해서 말씀드립니다.</p>"
            "<p>어느 자리에 침을 놓을지는 진찰에서 정합니다. 좋은꿈참사랑한의원은 모든 분께 진맥을 하고, 잠·소화·몸의 온기·대소변을 함께 여쭌 뒤 그날의 자리와 자극을 고릅니다. "
            "<a href='pulse.html'>진맥 이야기</a>에서 진찰 흐름을 볼 수 있습니다.</p>"
            "<h2>침 치료에 대해 더 읽어 보기</h2>"
            f"<ul>{more_html}<li><a href='guide/pain/index.html'>통증 글 전체 보기</a></li></ul>"
            f"<section class='faqblock'><h2>자주 묻는 질문</h2>{faq}</section>"
            f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 마지막 확인 {TODAY} · 일반적인 건강 정보이며 진단·치료를 대신하지 않습니다. 문의 02-815-7510</p>"
            "</section>")
    title = "침 치료·사암침"
    desc = "좋은꿈참사랑한의원의 침 치료 안내: 아픈 부위와 손발처럼 떨어진 자리, 사암침, 지금 몸에 맞는 자리와 자극량을 고르는 방법과 침 맞은 뒤 주의할 점."
    ld = clinic_ld("acupuncture.html", f"{title} | {CFG['clinic_name']}", desc, "faq", {"mainEntity": faq_entities(body)})
    write(ROOT / "acupuncture.html", shell(f"{title} 안내 | {CFG['clinic_name']}", desc, 0, body, ld, "acupuncture.html", "website",
                                           hero=hero_html(0, "pain", title, "지금 이 몸에 필요한 자리와 자극량을 고릅니다", False, img="real/room-bed1.jpg")))


def _hub_bullets(cat, n=4):
    """분야 안내(hubs.json)에서 '이런 분께' → '자주 듣는' 순으로 증상 목록을 가져온다."""
    secs = HUBS.get(cat, {}).get("sections", [])
    for key in ("이런 분께", "자주 듣는", "흔히 듣는", "상담에서 자주"):
        for s in secs:
            if key in s["h2"] and s.get("bullets"):
                return s["bullets"][:n]
    return []


def build_treatments(posts):
    """진료안내 허브(treatments.html): 주력 진료 → 증상별 진료 → 치료 방법(개요·진행·주의) → 진료 흐름 → 먼저 다른 진료가 필요한 신호 → FAQ.
    원고는 content/treatments.json, 증상·FAQ 수·글 수는 hubs.json 과 발행 글에서 자동으로 맞춘다."""
    f = ROOT / "content" / "treatments.json"
    if not f.exists():
        return
    T = json.loads(f.read_text(encoding="utf-8"))
    count = {}
    for p in posts:
        count[p["category"]] = count.get(p["category"], 0) + 1

    def tcard(it, big=False):
        cat = it["cat"]
        hub = f"guide/{cat}/index.html"
        href = it.get("href") or hub
        if not (ROOT / href).exists() and href.startswith("guide/"):
            return ""
        line = it.get("line") or re.split(r"(?<=\.)\s", HUBS.get(cat, {}).get("lead", ""))[0]
        bl = _hub_bullets(cat, 4 if big else 3)
        nfaq = len(HUBS.get(cat, {}).get("faq", []))
        links = f"<a class='btn primary' data-link-location='treat_{cat}' href='{href}'>자세히 보기</a>"
        if nfaq and (ROOT / hub).exists():
            links += f"<a class='btn' data-link-location='treat_faq_{cat}' href='{hub}#faq'>자주 묻는 질문 {nfaq}</a>"
        if count.get(cat) and href != hub:
            links += f"<a class='btn' data-link-location='treat_posts_{cat}' href='{hub}'>관련 글 {count[cat]}편</a>"
        elif count.get(cat):
            links += f"<span class='tcount'>관련 글 {count[cat]}편</span>"
        badge = f"<p class='tbadge'>{E(it['badge'])}</p>" if it.get("badge") else ""
        return (f"<article class='tcard{' big' if big else ''}' id='t-{cat}'><div class='thead'>{icon_img(cat, '')}<h3>{E(it['name'])}</h3></div>"
                f"{badge}<p>{inline(line)}</p>"
                + ("<ul class='tsym'>" + "".join(f"<li>{inline(b)}</li>" for b in bl) + "</ul>" if bl else "")
                + f"<div class='tlinks'>{links}</div></article>")

    jump = "".join(f"<li><a href='#t-{it['cat']}'>{E(it['name'])}</a></li>" for it in T["featured"] + T["symptoms"])
    feat = "".join(tcard(it, True) for it in T["featured"])
    sym = "".join(tcard(it) for it in T["symptoms"])
    methods = "".join(
        f"<article class='tmethod' id='m-{m['id']}'><h3>{E(m['name'])}</h3><dl>"
        f"<dt>무엇인가요</dt><dd>{inline(m['what'])}</dd><dt>이렇게 진행합니다</dt><dd>{inline(m['how'])}</dd>"
        f"<dt>먼저 알려 주세요</dt><dd>{inline(m['care'])}</dd></dl>"
        + (f"<p><a data-link-location='method_{m['id']}' href='{m['href']}'>{E(m['name'])} 더 보기 →</a></p>" if (ROOT / m["href"].split("#")[0]).exists() else "")
        + "</article>" for m in T["methods"])
    flow = "".join(f"<li><div><b>{E(a)}</b><br>{inline(b)}</div></li>" for a, b in T["flow"])
    red = "".join(f"<li>{inline(x)}</li>" for x in T["redflags"])
    faq = "".join(f"<details class='qa'><summary>{E(q['q'])}</summary><p>{inline(q['a'])}</p></details>" for q in T["faq"])
    body = ("<nav class='crumbs'><a href='index.html'>홈</a> › 진료안내</nav>"
            f"<section class='treatpage'><p class='lead'>{inline(T['lead'])}</p>"
            f"<nav class='tjump' aria-label='진료 바로가기'><ul class='chips'>{jump}</ul></nav>"
            f"<h2>주력 진료</h2><div class='tgrid feat'>{feat}</div>"
            f"<h2>증상으로 찾기</h2><div class='tgrid'>{sym}</div></section>"
            f"<section class='treatpage'><h2>치료 방법 안내</h2><p>모든 치료를 모든 분께 하지 않습니다. 진찰 후 필요한 것만 고르고, 치료 전에 무엇을 왜 하는지 말씀드립니다.</p>"
            f"<div class='tgrid'>{methods}</div></section>"
            f"<section class='treatpage'><h2>통증 진료는 이렇게 흐릅니다</h2><ol class='steps'>{flow}</ol></section>"
            "<section class='treatpage'><p class='note'>갑자기 시작된 심한 증상(극심한 두통·마비·가슴 통증 등)은 한의원보다 가까운 응급실을 먼저 찾으세요.</p></section>"  # 11/26 원장님: 응급 안내는 최소한으로
            f"<section class='faqblock treatpage' id='faq'><h2>진료안내 자주 묻는 질문</h2>{faq}"
            "<p><a class='btn' href='faq.html'>전체 자주 묻는 질문 보기</a></p></section>"
            + cta_box("", "list", "")
            + f"<p class='note'>감수: {E(CFG['clinic_name'])} 대표원장 이종호(한의사 면허 19769) · 마지막 확인 {TODAY} · "
              "치료 효과와 횟수는 사람마다 다르며, 이 페이지는 일반적인 안내로 진단·치료를 대신하지 않습니다.</p>")
    title = "진료안내"
    desc = ("좋은꿈참사랑한의원(상도역) 진료안내: 체외충격파, 추나요법, 초음파 진단·약침, 불면·수면, 통증, 교통사고, 소화, 대사, "
            "여성·소아 진료와 침·약침·추나·한약·물리치료의 진행 방식과 주의사항을 한곳에 정리했습니다.")
    items = [{"@type": "ListItem", "position": i + 1, "name": it["name"],
              "url": (BASE or "") + "/" + (it.get("href") or f"guide/{it['cat']}/index.html")}
             for i, it in enumerate(T["featured"] + T["symptoms"])]
    ld = clinic_ld("treatments.html", f"{title} | {CFG['clinic_name']}", desc, "faq",
                   {"mainEntity": faq_entities(body), "hasPart": {"@type": "ItemList", "name": "진료 항목", "itemListElement": items}})
    write(ROOT / "treatments.html", shell(f"{title} — 증상별 진료와 치료 방법 | {CFG['clinic_name']}", desc, 0, body, ld, "treatments.html", "website",
                                          hero=hero_html(0, "pain", "진료안내", "증상으로 찾고, 치료 방법으로 확인하세요", False, img="real/chuna-neck1.jpg")))


DOCTORS = [  # (파일, 이름, 직함, 사진, 사진 설명, 주요 진료 분야, 한 줄, 약력, 진료 장면 사진, 관련 분류) — index.html 의료진 카드와 같은 사실만
    ("doctor-lee.html", "이종호", "대표원장", "doc-library", "책장 앞에 선 이종호 대표원장",
     ["뇌기능 재활·공진단", "당뇨·대사증후군·다이어트", "불면증·만성 소화불량·치료 한약"],
     "몸의 증상을 그 사람의 생활과 마음까지 함께 이어서 살핍니다.",
     ["원광대학교 한의과대학 졸업, 한의사 면허번호 19769", "2013년 상도동 개원", "중국 중의학대학 해부학·침도학 연수",
      "식품의약품안전처장 위촉 한약 관능검사 전문가 (대한한의사회, 2026.08~2028.08)", "동작구 노인 치매관리사업 주치의",
      "동작구 어르신 치매예방사업·찾아가는 실버한방케어·한의약 난임치료 지원사업 지정 한의사",
      "은로초등학교·중대부중학교·숭의여자중학교 교의", "상도은빛복지관 후원 진료",
      "강감찬관악종합사회복지관 건강 특강·업무협약 (2026)",
      "방송 고정 패널: MBN 「건강한의사」(2021)·「한방이 답이다」(2022), EBC 「여의보감」(2023)"],
     ("explain-monitor2", "이종호 대표원장 · 영상 자료를 보며 설명"), ["insomnia", "metabolic", "diagnosis", "herbal"]),
    ("doctor-jo.html", "조영기", "수석진료원장", "doc-stand", "진료실에 선 조영기 수석진료원장",
     ["척추관절 기능검사", "기능조율 추나요법", "만성통증·만성피로"], "",
     ["한의학박사, 한방내과 전문의", "현 좋은꿈참사랑한의원 수석진료원장", "현 좋은꿈 네트워크 추나의학 학술이사",
      "전 강남 광동한방병원 통증재활과 진료원장", "전 종로 춘원당한방병원 신경내과 진료원장",
      "육군특수전사령부 제1공수특전여단 군의관", "원광대학교 부속 전주한방병원 임상조교수·내과 전문의",
      "원광대학교 한의과대학원 한의학 박사"],
     ("explain-model", "조영기 수석진료원장 · 척추 모형으로 설명"), ["chuna", "pain", "accident", "shockwave"]),
    ("doctor-jeong.html", "정원영", "진료원장", "doc-room", "치료실에 선 정원영 진료원장",
     ["체형분석·스포츠 손상", "관절재활 추나요법", "내장복부 추나요법"], "",
     ["동신대학교 한의과대학 졸업", "현 좋은꿈참사랑한의원 진료원장", "현 대한스포츠한의학회 회원",
      "전 365매일한방병원 진료원장", "전 수유 늘찬한의원 진료원장",
      "척추신경추나학회 정규과정 수료", "시리악스 정형의학회 정규과정 수료", "대한스포츠한의학회 팀닥터 과정 수료"],
     ("chuna-neck1", "정원영 진료원장 · 추나 치료"), ["chuna", "pain"]),
]

LEE_WRITINGS = [("pulse.html", "진맥 이야기 — 모든 분께 진맥을 합니다"), ("column-pulse.html", "원장 칼럼: 제가 환자분께 두 손목을 내어 달라고 하는 이유"),
                ("inbody.html", "인바디 이야기 — 결과지 읽는 법"), ("gongjindan.html", "공진단 이야기"), ("acupuncture.html", "침 치료·사암침 안내"),
                ("column-fall-walking.html", "원장 칼럼: 넘어지지 않는 몸, 작게 오래 걷는 이야기"),
                ("column-keep-health.html", "원장 칼럼: 받은 건강을 단단히 지키는 일(양생 이야기)"), ("lectures.html", "지역 건강 강연")]


def build_doctors(posts):
    """원장님별 소개 페이지(doctor-*.html): 약력·주요 진료 분야·쓴 글·감수한 글. ProfilePage + Person 구조화 데이터로
    글의 감수자(reviewedBy)와 같은 @id 를 써서 AI·검색이 '누가 쓴 글인가'를 한 사람으로 이어 보게 한다. 사실은 index.html 의료진 카드와 같게."""
    counts = {}
    for x in posts:
        if x.get("reviewed"):
            counts[x["category"]] = counts.get(x["category"], 0) + 1
    total = sum(counts.values())
    for fn, name, title, img, alt, fields, philo, career, (wimg, walt), cats in DOCTORS:
        person = {"@type": "Person", "@id": (BASE or "") + f"/{fn}#person", "url": (BASE or "") + f"/{fn}",
                  "name": name, "jobTitle": title, "honorificSuffix": "한의사",
                  "image": (BASE or "") + f"/images/real/{img}.webp",
                  "hasOccupation": {"@type": "Occupation", "name": "한의사"},
                  "worksFor": {"@id": (BASE or "") + "/#clinic"}}
        if fields:
            person["knowsAbout"] = fields
        if fn == "doctor-lee.html":
            person["alumniOf"] = {"@type": "CollegeOrUniversity", "name": "원광대학교 한의과대학"}
            person["identifier"] = "한의사 면허번호 19769"
            person["description"] = philo
        if fn == "doctor-jo.html":
            person["alumniOf"] = {"@type": "CollegeOrUniversity", "name": "원광대학교 한의과대학원"}
            person["hasCredential"] = {"@type": "EducationalOccupationalCredential", "credentialCategory": "degree", "name": "한의학박사"}
        full = f"{name} {title}"
        field_html = (("<ul class='dp-fields' aria-label='주요 진료 분야'>" + "".join(f"<li>{E(f)}</li>" for f in fields) + "</ul>") if fields
                      else "<p class='note'>진료원장으로 진료합니다. 진료 분야와 진료 요일은 방문 전 전화(02-815-7510)로 확인해 주세요.</p>")
        philo_html = f"<p class='say'>{E(philo)}</p>" if philo else ""
        career_html = ("<h2 data-mo>약력</h2><ul class='plain' data-mo='stagger'>" + "".join(f"<li>{E(c)}</li>" for c in career) + "</ul>") if career else ""
        cards = lambda items: "<ul class='dp-cards' data-mo='stagger'>" + "".join(items) + "</ul>"
        catcards = cards(f"<li><a href='guide/{c}/index.html'>{E(CATS[c])}</a></li>" for c in cats if c in CATS)
        if fn == "doctor-lee.html":
            extra = ("<h2 data-mo>진료실에서 지키는 것</h2><ul class='plain' data-mo='stagger'>"
                     "<li>오시는 분 모두 맥부터 짚습니다. <a href='pulse.html'>진맥 이야기 →</a></li>"
                     "<li>다시 오시면 지난번 이야기와 그사이 몸의 변화를 이어서 여쭙니다. <a href='again.html'>다시 오시나요? →</a></li>"
                     "<li>아픈 곳 하나보다 잠·식욕·소화·마음까지 몸 전체의 리듬을 함께 봅니다.</li>"
                     "<li>치료로 할 수 있는 것과 할 수 없는 것을 솔직하게 말씀드립니다.</li>"
                     "<li>한약은 매주 들어오는 약재를 대표원장이 직접 확인하고 원내에서 달입니다. <a href='herbal-room.html'>원내 탕전 기록 →</a></li></ul>"
                     "<h2 data-mo>직접 쓴 글</h2>" + cards(f"<li><a href='{f}'>{E(t)}</a></li>" for f, t in LEE_WRITINGS)
                     + "<h2 data-mo>감수한 한방가이드</h2>"
                     f"<p class='dp-total' data-mo><b data-n='{total}'>{total}</b><span>편, 모두 이종호 대표원장이 읽고 감수했습니다.</span></p>"
                     "<p class='note'>글마다 맨 위에 감수자와 수정 날짜를 적어 둡니다.</p>"
                     + cards(f"<li><a href='guide/{c}/index.html'><span>{E(CATS[c])}</span><b data-n='{n}'>{n}</b><small>편</small></a></li>"
                             for c, n in sorted(counts.items(), key=lambda kv: -kv[1])).replace("class='dp-cards'", "class='dp-cards nums'", 1))
        else:
            extra = "<h2 data-mo>함께 읽으면 좋은 글</h2>" + catcards
        body = (f"<nav class='crumbs'><a href='index.html'>홈</a> › <a href='about.html'>한의원 소개</a> › {E(full)}</nav>"
                "<article class='pulsepage column'>"
                "<div class='dp-top'><span class='dp-orb a' aria-hidden='true'></span><span class='dp-orb b' aria-hidden='true'></span>"
                f"<div class='dp-glass' data-mo='left'><h2>{E(full)}</h2>{field_html}{philo_html}"
                f"<p class='note'>{E(CFG['clinic_name'])} · {E(CFG['address'])} · 상도역 3번 출구 근처</p></div>"
                f"<div class='tilt' data-mo='right'><img src='images/real/{img}.webp' srcset='images/real/{img}-sm.webp 1024w, images/real/{img}.webp 1600w' sizes='(min-width:900px) 360px, 100vw' alt='{E(alt)}' width='1067' height='1600' loading='lazy'></div></div>"
                f"{career_html}"
                f"<figure class='cine' data-mo='zoom'><img src='images/real/{wimg}.webp' srcset='images/real/{wimg}-sm.webp 1024w, images/real/{wimg}.webp 1600w' sizes='100vw' alt='{E(walt)}' width='1600' height='1067' loading='lazy'><figcaption>{E(walt)}</figcaption></figure>"
                f"{extra}"
                "<h2 data-mo>다른 의료진</h2>" + cards([f"<li><a href='{f}'>{E(n)} {E(t)}</a></li>" for f, n, t, *_r in DOCTORS if f != fn] + ["<li><a href='about.html'>한의원 소개</a></li>"])
                + "<p class='note'>의료진 소개는 확인된 약력과 주요 진료 분야만 적었습니다. 진료 일정은 원장마다 다를 수 있으니 방문 전 전화로 확인해 주세요. "
                "평일 09:30~20:00(점심 13:00~14:00), 토·일·공휴일 09:30~15:00.</p>"
                "</article>")
        desc = (f"좋은꿈참사랑한의원 {full} 소개: " + (f"주요 진료 분야 {', '.join(fields)}. " if fields else "")
                + ("약력과 진료 원칙, 직접 쓴 글과 감수한 한방가이드 글을 모았습니다." if fn == "doctor-lee.html"
                   else "약력과 진료 장면, 함께 읽으면 좋은 글을 모았습니다." if career else "진료 장면과 진료 안내를 모았습니다.")
                + " 서울 동작구 상도역 3번 출구 근처.")
        ld = clinic_ld(fn, f"{full} | {CFG['clinic_name']}", desc, "WebPage",
                       {"@type": "ProfilePage", "mainEntity": person})
        write(ROOT / fn, shell(f"{full} 소개 | {CFG['clinic_name']}", desc, 0, body, ld + '<link rel="stylesheet" href="motion.css">', fn, "profile",
                               extra_js='<script src="motion.js" defer></script>',
                               hero=hero_html(0, "home", full, "의료진 소개 · 좋은꿈참사랑한의원", False, img="real/room-consult1.jpg")))


def build_queue():
    items = sorted(UPCOMING, key=lambda p: (p["date"], p["slug"]))
    rows = "".join(f"<tr><td>{E(p['date'])}</td><td>{E(CATS[p['category']])}</td><td>{E(p['title'])}</td></tr>" for p in items)
    body = (f"<h1 class='atitle'>발행 예정 목록</h1><p class='note'>오늘({TODAY}) 이후에 자동으로 올라갈 글입니다. 하루 {CFG.get('drip', {}).get('per_day', 1)}편씩 순서대로 발행됩니다. "
            f"(원장님 확인용, 검색에 노출되지 않는 페이지)</p><p><b>예정 {len(items)}편</b></p>"
            f"<div class='tablewrap'><table class='qtable'><thead><tr><th>발행일</th><th>분류</th><th>제목</th></tr></thead><tbody>{rows}</tbody></table></div>")
    write(ROOT / "queue.html", shell(f"발행 예정 목록 | {CFG['clinic_name']}", "발행 예정 글 목록", 0, body, "", None, "website", robots="noindex,nofollow", actions=False))


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
    rules = ["Allow: /", "Disallow: /admin.html", "Disallow: /queue.html"]
    # AI 검색·답변 봇을 이름으로 명시해 허용한다. 이름별 그룹은 * 의 규칙을 물려받지 않으므로 같은 Disallow 를 함께 적는다.
    ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "anthropic-ai",
               "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "Bingbot", "Yeti",
               "Meta-ExternalAgent", "Amazonbot", "DuckAssistBot", "cohere-ai", "MistralAI-User"]
    lines = ["# 검색·AI 답변 서비스의 수집을 환영합니다. 인용 시 출처: 좋은꿈참사랑한의원(gooddreamclinic.com)", ""]
    lines += [f"User-agent: {b}" for b in ai_bots] + rules + [""]
    lines += ["User-agent: *"] + rules + [""]
    if BASE:
        lines += ["", f"Sitemap: {BASE}/sitemap.xml"]
        write(ROOT / "CNAME", BASE.split("//", 1)[-1] + "\n")
    write(ROOT / "robots.txt", "\n".join(lines) + "\n")


_HREF_RE = re.compile(r"""(href=)(["'])(.*?)\2""", re.S)


def _drop_utm(url):
    """내부 링크(상대 경로 또는 gooddreamclinic.com)에서 utm_* 매개변수만 뺀다. 외부 링크는 그대로."""
    if "utm_" not in url:
        return url
    low = url.lower()
    if low.startswith(("http://", "https://", "//")) and "gooddreamclinic.com" not in low.split("/")[2 if not low.startswith("//") else 2]:
        return url
    base, hash_, frag = url.partition("#")
    path, q, query = base.partition("?")
    if not q:
        return url
    amp = "&amp;" if "&amp;" in query else "&"
    keep = [kv for kv in query.split(amp) if kv and not kv.lower().startswith("utm_")]
    return path + ("?" + amp.join(keep) if keep else "") + hash_ + frag


def strip_internal_utm():
    """안전장치: 자동 글·수작업 페이지 어디에 들어가 있든 내부 링크의 UTM을 빌드 마지막에 지운다.
    (내부 링크 UTM은 GA4 세션을 끊고 실제 유입 경로를 덮어씀. 위치 구분은 data-link-location 사용)"""
    skip = {"node_modules", ".git", "_site", "naver-blog", ".chrome-profile", "chrome-profile"}
    n_files = n_links = 0
    for f in ROOT.rglob("*.html"):
        if skip & set(f.relative_to(ROOT).parts):
            continue
        src = f.read_text(encoding="utf-8")
        if "utm_" not in src:
            continue
        cnt = 0
        def sub(m):
            nonlocal cnt
            new = _drop_utm(m.group(3))
            if new != m.group(3):
                cnt += 1
            return m.group(1) + m.group(2) + new + m.group(2)
        new_src = _HREF_RE.sub(sub, src)
        if new_src != src:
            f.write_text(new_src, encoding="utf-8")
            n_files += 1; n_links += cnt
    if n_links:
        print(f"내부 링크 UTM 제거: {n_files}개 파일, {n_links}개 링크")


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
    inject_gsv()
    build_subpages()
    build_network()
    build_lectures()
    build_herbroom()
    build_pulse()
    build_column_pulse()
    build_gongjindan()
    build_inbody()
    build_explain(posts)
    build_lecture_columns()
    build_acupuncture()
    build_treatments(posts)
    build_doctors(posts)
    inject_latest(posts)
    inject_cards("sleep.html", "posts-sleep", {"insomnia"}, posts)
    inject_cards("diet.html", "posts-metabolic", {"metabolic"}, posts)
    import subprocess, sys as _sys
    subprocess.run([_sys.executable, str(ROOT / 'tools' / 'post_html.py')], check=False)
    strip_internal_utm()
    print(f"완료({TODAY}): 발행 {len(posts)}편, 예정 {len(UPCOMING)}편 → guide/, today.html, data/posts.json, llms.txt" + (", sitemap.xml, feed.xml, CNAME" if BASE else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
