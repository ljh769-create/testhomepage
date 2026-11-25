#!/usr/bin/env python3
"""배포된 홈페이지를 네이버 SEO · 구글 SEO · AEO(답변엔진) · GEO(생성형엔진) 네 영역으로 점검한다.
사용: python tools/site_audit.py [--base https://gooddreamclinic.com] [--html 결과.html] [--tag 이름]
- 결과는 content/_audit.json 에 회차별로 쌓인다(같은 tag 는 덮어씀). --html 을 주면 전/후 비교 보고서를 만든다.
- 각 항목: 잘됨(ok) / 주의(warn) / 개선필요(fail) / 미확인(unk) / 해당없음(na). 점수 = 잘됨 ÷ (잘됨+주의+개선필요) × 100.
- 100점도 검색 순위를 보장하지 않습니다. 확인 가능한 기술·콘텐츠 구조만 봅니다."""
import argparse, datetime, html, json, os, random, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; GoodDreamSiteAudit/1.0)"
CLINIC = "좋은꿈참사랑한의원"
PHONE = "02-815-7510"
ADDR = "만양로2길 2"
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended", "Bingbot", "Yeti"]


def fetch(url, method="GET"):
    # 한글 등 ASCII 밖 글자가 든 주소는 urllib 가 못 보내 상태 0이 나오므로 퍼센트 인코딩한다.
    url = urllib.parse.quote(url, safe=":/?&=#%~+.,;@!$'()*-_")
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            body = r.read() if method == "GET" else b""
            return {"status": r.status, "url": r.geturl(), "body": body.decode("utf-8", "replace"), "bytes": len(body),
                    "headers": dict(r.headers), "ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "url": url, "body": "", "bytes": 0, "headers": dict(e.headers or {}), "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": 0, "url": url, "body": "", "bytes": 0, "headers": {}, "ms": 0, "err": str(e)}


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.metas, self.links, self.imgs, self.heads, self.anchors, self.ld = "", [], [], [], [], [], []
        self.lang, self._in, self._buf, self.text, self.tables, self.lists, self.details = "", None, "", [], 0, 0, 0
        self.scripts_src, self.styles, self.paras = [], [], []

    def handle_starttag(self, t, a):
        a = dict(a)
        if t == "html": self.lang = a.get("lang", "")
        elif t == "title": self._in, self._buf = "title", ""
        elif t == "meta": self.metas.append(a)
        elif t == "link": self.links.append(a)
        elif t == "img": self.imgs.append(a)
        elif t in ("h1", "h2", "h3", "h4"): self._in, self._buf, self._h = t, "", t
        elif t == "a": self.anchors.append(a.get("href", ""))
        elif t == "script":
            if a.get("type") == "application/ld+json": self._in, self._buf = "ld", ""
            elif a.get("src"): self.scripts_src.append(a)
        elif t == "table": self.tables += 1
        elif t in ("ul", "ol"): self.lists += 1
        elif t == "details": self.details += 1
        elif t == "p" and self._in is None: self._in, self._buf = "p", ""

    def handle_endtag(self, t):
        if self._in == "title" and t == "title": self.title, self._in = self._buf.strip(), None
        elif self._in in ("h1", "h2", "h3", "h4") and t == self._in: self.heads.append((t, self._buf.strip())); self._in = None
        elif self._in == "ld" and t == "script": self.ld.append(self._buf); self._in = None
        elif self._in == "p" and t == "p": self.paras.append(self._buf.strip()); self._in = None

    def handle_data(self, d):
        if self._in: self._buf += d
        self.text.append(d)

    def meta(self, key):
        for m in self.metas:
            if m.get("name", "").lower() == key or m.get("property", "").lower() == key:
                return m.get("content", "")
        return None

    def link(self, rel):
        for l in self.links:
            if rel in (l.get("rel") or "").lower().split():
                return l.get("href")
        return None


def parse(body):
    p = P()
    try:
        p.feed(body)
    except Exception:
        pass
    p.alltext = re.sub(r"\s+", " ", " ".join(p.text))
    lds = []
    for raw in p.ld:
        try:
            lds.append(json.loads(raw.replace("<\\/", "</")))
        except Exception:
            lds.append({"__error__": True})
    p.ldobjs = lds
    return p


def ld_types(p):
    out = []
    def walk(o):
        if isinstance(o, dict):
            t = o.get("@type")
            if isinstance(t, list): out.extend(t)
            elif t: out.append(t)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    for o in p.ldobjs: walk(o)
    return out


def ld_find(p, typ):
    res = []
    def walk(o):
        if isinstance(o, dict):
            t = o.get("@type")
            if t == typ or (isinstance(t, list) and typ in t): res.append(o)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    for o in p.ldobjs: walk(o)
    return res


def hangul_len(s):
    return len(re.findall(r"[가-힣]", s))


# ---------------------------------------------------------------- 수집
def collect(base):
    base = base.rstrip("/")
    posts = json.load(open(os.path.join(ROOT, "data", "posts.json"), encoding="utf-8"))
    random.seed(7)
    sample_posts = [x["u"] for x in random.sample(posts, min(10, len(posts)))]
    cats = sorted({x["u"].split("/")[1] for x in posts})
    sample_cats = [f"guide/{c}/index.html" for c in random.sample(cats, min(3, len(cats)))]
    pages = {"home": "/", "about": "/about.html", "first": "/first.html", "faq": "/faq.html", "visit": "/visit.html", "herbal": "/herbal-room.html"}
    for c in sample_cats: pages["cat:" + c] = "/" + c
    for u in sample_posts: pages["post:" + u] = "/" + u
    data = {"base": base, "pages": {}, "files": {}}
    for k, path in pages.items():
        r = fetch(base + path)
        r["path"] = path
        data["pages"][k] = r
    for f in ("robots.txt", "sitemap.xml", "llms.txt", "llms-full.txt", "feed.xml", "manifest.webmanifest", "favicon.ico"):
        data["files"][f] = fetch(f"{base}/{f}")
    data["files"]["404"] = fetch(f"{base}/이런페이지는없음-{int(time.time())}.html")
    data["files"]["http"] = fetch(base.replace("https://", "http://") + "/")
    data["files"]["www"] = fetch(base.replace("https://", "https://www.") + "/")
    return data


# ---------------------------------------------------------------- 점검 항목
def run_checks(data):
    pg = {k: dict(v, P=parse(v["body"])) for k, v in data["pages"].items() if v["status"] == 200}
    F = data["files"]
    home = pg.get("home")
    posts = {k: v for k, v in pg.items() if k.startswith("post:")}
    allp = list(pg.values())
    R = {"naver": [], "google": [], "aeo": [], "geo": []}

    def add(area, name, status, why):
        R[area].append({"name": name, "status": status, "why": why})

    def ratio(pages, fn):
        if not pages: return 0, 0
        ok = sum(1 for p in pages if fn(p))
        return ok, len(pages)

    def frac(area, name, pages, fn, good=1.0, warn=0.7, why=""):
        ok, n = ratio(pages, fn)
        if n == 0:
            add(area, name, "unk", "표본 페이지를 받지 못함"); return
        r = ok / n
        st = "ok" if r >= good else ("warn" if r >= warn else "fail")
        add(area, name, st, f"{ok}/{n} 페이지 {why}".strip())

    P_ = lambda p: p["P"]
    # ---------------- 공통(네이버·구글 모두)
    for area in ("naver", "google"):
        frac(area, "응답 상태 200", list(data["pages"].values()), lambda p: p["status"] == 200, why="정상 응답")
        frac(area, "페이지 제목(title) 있음", allp, lambda p: bool(P_(p).title))
        frac(area, "제목 길이 15~60자", allp, lambda p: 15 <= len(P_(p).title) <= 60, warn=0.6)
        frac(area, "제목에 한의원 이름", allp, lambda p: CLINIC in P_(p).title)
        frac(area, "설명(description) 있음", allp, lambda p: bool(P_(p).meta("description")))
        frac(area, "설명 길이 50~160자", allp, lambda p: 50 <= len(P_(p).meta("description") or "") <= 160, warn=0.6)
        frac(area, "canonical 지정", allp, lambda p: bool(P_(p).link("canonical")))
        frac(area, "canonical 이 자기 주소", allp, lambda p: (P_(p).link("canonical") or "").rstrip("/").endswith(p["path"].rstrip("/")) or p["path"] == "/")
        frac(area, "og:title", allp, lambda p: bool(P_(p).meta("og:title")))
        frac(area, "og:description", allp, lambda p: bool(P_(p).meta("og:description")))
        frac(area, "og:image (절대 주소)", allp, lambda p: (P_(p).meta("og:image") or "").startswith("https://"))
        frac(area, "og:url", allp, lambda p: bool(P_(p).meta("og:url")))
        frac(area, "og:type", allp, lambda p: bool(P_(p).meta("og:type")))
        frac(area, "og:locale ko_KR", allp, lambda p: (P_(p).meta("og:locale") or "") == "ko_KR")
        frac(area, "og:image:alt", allp, lambda p: bool(P_(p).meta("og:image:alt")), warn=0.5)
        frac(area, "twitter:card", allp, lambda p: bool(P_(p).meta("twitter:card")))
        frac(area, "robots 메타가 noindex 아님", allp, lambda p: "noindex" not in (P_(p).meta("robots") or ""))
        frac(area, "모바일 viewport", allp, lambda p: "width=device-width" in (P_(p).meta("viewport") or ""))
        frac(area, "H1 하나", allp, lambda p: sum(1 for h in P_(p).heads if h[0] == "h1") == 1)
        frac(area, "H1 내용 있음", allp, lambda p: any(h[0] == "h1" and len(h[1]) >= 4 for h in P_(p).heads))
        frac(area, "H2 소제목 사용", allp, lambda p: sum(1 for h in P_(p).heads if h[0] == "h2") >= 2, warn=0.6)
        frac(area, "제목 단계 건너뜀 없음(H1→H3)", allp, lambda p: not (any(h[0] == "h3" for h in P_(p).heads) and not any(h[0] == "h2" for h in P_(p).heads)))
        frac(area, "모든 이미지에 alt 속성", allp, lambda p: all("alt" in i for i in P_(p).imgs))
        frac(area, "내용 이미지 alt 채움", allp, lambda p: sum(1 for i in P_(p).imgs if (i.get("alt") or "").strip()) >= max(1, len(P_(p).imgs) // 3), warn=0.6)
        frac(area, "장식 이미지 aria-hidden", allp, lambda p: all(i.get("aria-hidden") == "true" for i in P_(p).imgs if i.get("alt", None) == ""), warn=0.6)
        frac(area, "한글 본문 600자 이상", allp, lambda p: hangul_len(P_(p).alltext) >= 600)
        frac(area, "내부 링크 10개 이상", allp, lambda p: sum(1 for a in P_(p).anchors if a and not a.startswith(("http", "tel:", "mailto:")) or a.startswith(data["base"])) >= 10)
        frac(area, "페이지 크기 300KB 이하", list(pg.values()), lambda p: p["bytes"] <= 300_000, warn=0.6)
        frac(area, "응답 시간 1.5초 이하", list(pg.values()), lambda p: p["ms"] <= 1500, warn=0.6)
        titles = [P_(p).title for p in allp]
        dup = len(titles) - len(set(titles))
        add(area, "제목 중복 없음", "ok" if dup == 0 else "warn", f"표본 {len(titles)}쪽 중 중복 {dup}")
        descs = [P_(p).meta("description") for p in allp]
        dd = len(descs) - len(set(descs))
        add(area, "설명 중복 없음", "ok" if dd == 0 else "warn", f"표본 중 중복 {dd}")
        add(area, "lang=ko", "ok" if all(P_(p).lang.startswith("ko") for p in allp) else "fail", "html lang 속성")
        add(area, "charset utf-8", "ok" if all(re.search(r'<meta charset="?utf-8', p["body"], re.I) for p in allp) else "warn", "문자 인코딩 선언")
        add(area, "favicon", "ok" if F["favicon.ico"]["status"] == 200 else "fail", f"favicon.ico {F['favicon.ico']['status']}")
        add(area, "웹앱 매니페스트", "ok" if F["manifest.webmanifest"]["status"] == 200 else "warn", "manifest.webmanifest")
        add(area, "HTTPS 사용", "ok" if data["base"].startswith("https://") else "fail", data["base"])
        hs = F["http"]
        add(area, "http → https 이동", "ok" if hs["status"] == 200 and hs["url"].startswith("https://") else ("unk" if hs["status"] == 0 else "warn"), f"최종 {hs['url'][:40]}")
        mixed = [k for k, p in pg.items() if re.search(r'(src|href)="http://', p["body"])]
        add(area, "혼합 콘텐츠(http) 없음", "ok" if not mixed else "fail", f"{len(mixed)}쪽")
        add(area, "404 페이지가 404 응답", "ok" if F["404"]["status"] == 404 else "warn", f"없는 주소 응답 {F['404']['status']}")
        rb = F["robots.txt"]
        add(area, "robots.txt 있음", "ok" if rb["status"] == 200 else "fail", f"{rb['status']}")
        add(area, "robots.txt 에 Sitemap", "ok" if "sitemap:" in rb["body"].lower() else "fail", "Sitemap 줄")
        add(area, "robots.txt 전체 차단 아님", "ok" if not re.search(r"(?im)^user-agent:\s*\*\s*$[\s\S]*?^disallow:\s*/\s*$", rb["body"]) else "fail", "Disallow: / 여부")
        sm = F["sitemap.xml"]
        n_url = sm["body"].count("<loc>")
        add(area, "sitemap.xml 있음", "ok" if sm["status"] == 200 and n_url > 50 else "fail", f"주소 {n_url}개")
        add(area, "sitemap lastmod", "ok" if "<lastmod>" in sm["body"] else "warn", "lastmod 표시")
        add(area, "RSS(feed.xml)", "ok" if F["feed.xml"]["status"] == 200 and "<item>" in F["feed.xml"]["body"] else "warn", f"{F['feed.xml']['status']}")
        add(area, "구조화 데이터 파싱 오류 없음", "ok" if all("__error__" not in o for p in allp for o in P_(p).ldobjs) else "fail", "JSON-LD 전부 파싱")

    # ---------------- 네이버 전용
    nv = home and home["P"].meta("naver-site-verification")
    add("naver", "네이버 서치어드바이저 인증", "ok" if nv else "fail", "naver-site-verification 메타")
    add("naver", "네이버 예약 링크", "ok" if home and "booking.naver.com" in home["body"] else "warn", "홈에서 네이버 예약 연결")
    add("naver", "전화 링크(tel:)", "ok" if home and "tel:" in home["body"] else "fail", "모바일 전화 걸기")
    add("naver", "주소 텍스트 노출", "ok" if home and ADDR in home["P"].alltext else "fail", ADDR)
    add("naver", "네이버 지도 링크", "ok" if home and ("map.naver.com" in home["body"] or "naver.me" in home["body"]) else "warn", "지도 연결")
    add("naver", "블로그 등 외부 채널 연결", "ok" if home and "blog.naver.com" in home["body"] else "warn", "네이버 블로그 링크")
    add("naver", "카카오 채널 연결", "ok" if home and "pf.kakao.com" in home["body"] else "warn", "카카오톡 상담")
    add("naver", "한글 키워드: 지역명", "ok" if home and all(w in home["P"].alltext for w in ("상도", "노량진", "동작")) else "warn", "상도·노량진·동작")
    add("naver", "RSS 글 20편 이상", "ok" if F["feed.xml"]["body"].count("<item>") >= 20 else "warn", f"{F['feed.xml']['body'].count('<item>')}편")
    add("naver", "글 발행일 표기", "ok" if all(re.search(r"발행 \d{4}-\d{2}-\d{2}", p["body"]) for p in posts.values()) else "warn", "글마다 발행일")
    add("naver", "글 수정일 표기", "ok" if all("수정" in p["body"] for p in posts.values()) else "warn", "수정일")
    add("naver", "본문 이미지 포함", "ok" if all(len(p["P"].imgs) >= 2 for p in posts.values()) else "warn", "글마다 그림")
    add("naver", "의료광고 금지어 없음", "ok" if not any(re.search(r"완치|100%|최고의|유일한|부작용 없", p["P"].alltext) for p in allp) else "fail", "완치·100%·최고의·유일한")
    add("naver", "'노량진점' 표기 없음", "ok" if not any("노량진점" in re.sub(r'"legalName": ?"좋은꿈참사랑한의원 노량진점"', "", p["body"]) for p in allp) else "fail", "지점명 정리")

    # ---------------- 구글 전용
    t_home = ld_types(home["P"]) if home else []
    add("google", "MedicalClinic 구조화", "ok" if "MedicalClinic" in t_home else "fail", "홈 JSON-LD")
    clinic = (ld_find(home["P"], "MedicalClinic") or [{}])[0] if home else {}
    add("google", "주소(PostalAddress)", "ok" if clinic.get("address") else "fail", "address")
    add("google", "전화(telephone)", "ok" if clinic.get("telephone") else "fail", "telephone")
    add("google", "진료시간(openingHoursSpecification)", "ok" if clinic.get("openingHoursSpecification") else "fail", "시간")
    add("google", "좌표(geo)", "ok" if clinic.get("geo") else "warn", "위도·경도")
    add("google", "지도(hasMap)", "ok" if clinic.get("hasMap") else "warn", "hasMap")
    add("google", "대표 이미지(image)", "ok" if clinic.get("image") else "warn", "image")
    add("google", "의료진(employee)", "ok" if clinic.get("employee") else "warn", "employee")
    add("google", "FAQPage(홈)", "ok" if "FAQPage" in t_home else "warn", "홈 FAQ 구조화")
    frac("google", "글: MedicalWebPage/Article", list(posts.values()), lambda p: any(t in ("MedicalWebPage", "Article", "BlogPosting") for t in ld_types(p["P"])))
    frac("google", "글: datePublished·dateModified", list(posts.values()), lambda p: '"datePublished"' in p["body"] and '"dateModified"' in p["body"])
    frac("google", "글: reviewedBy(감수자)", list(posts.values()), lambda p: '"reviewedBy"' in p["body"])
    frac("google", "글: BreadcrumbList", list(posts.values()), lambda p: "BreadcrumbList" in ld_types(p["P"]))
    frac("google", "Breadcrumb item 주소", list(posts.values()), lambda p: all("item" in x for b in ld_find(p["P"], "BreadcrumbList") for x in b.get("itemListElement", [])), warn=0.5)
    frac("google", "글: FAQPage", list(posts.values()), lambda p: "FAQPage" in ld_types(p["P"]))
    frac("google", "글: 저자(author)", list(posts.values()), lambda p: '"author"' in p["body"])
    frac("google", "글: 이미지(image) 구조화", list(posts.values()), lambda p: any(o.get("image") for o in ld_find(p["P"], "MedicalWebPage")), warn=0.5)
    frac("google", "첫 화면 이미지 fetchpriority", allp, lambda p: 'fetchpriority="high"' in p["body"] or "fetchpriority='high'" in p["body"], warn=0.6)
    frac("google", "이미지 width·height 지정", allp, lambda p: sum(1 for i in P_(p).imgs if i.get("width") and i.get("height")) >= len(P_(p).imgs) * 0.7, warn=0.5)
    frac("google", "아래쪽 이미지 lazy 로딩", allp, lambda p: sum(1 for i in P_(p).imgs if i.get("loading") == "lazy") >= max(0, len(P_(p).imgs) - 3), warn=0.6)
    frac("google", "WebP 이미지 사용", allp, lambda p: any((i.get("src") or "").endswith(".webp") for i in P_(p).imgs), warn=0.5)
    frac("google", "렌더링 차단 외부 CSS 없음", allp, lambda p: not re.search(r'<link[^>]+rel="stylesheet"[^>]+fonts\.googleapis[^>]*>(?![^<]*onload)', p["body"]) or "media=\"print\"" in p["body"])
    frac("google", "스크립트 defer/async 또는 하단", allp, lambda p: all(s.get("defer") is not None or s.get("async") is not None or p["body"].rfind(s.get("src", "")) > len(p["body"]) * 0.7 for s in P_(p).scripts_src), warn=0.6)
    add("google", "www 주소 처리", "ok" if F["www"]["status"] in (200, 301, 308) else ("unk" if F["www"]["status"] == 0 else "warn"), f"www 응답 {F['www']['status']}")
    add("google", "구글 서치콘솔 인증 태그", "ok" if home and home["P"].meta("google-site-verification") else "unk", "DNS·파일 인증이면 태그 없어도 됨(원장님 확인)")
    add("google", "GA4 설치", "ok" if home and "G-" in home["body"] and "googletagmanager" in home["body"] else "warn", "분석 도구")
    add("google", "sitemap 주소가 https", "ok" if "<loc>http://" not in F["sitemap.xml"]["body"] else "fail", "loc 프로토콜")
    add("google", "글 내부 관련 글 링크", "ok" if all(p["body"].count("guide/") >= 5 for p in posts.values()) else "warn", "관련 글 연결")
    add("google", "의료 YMYL: 진단 대체 안내문", "ok" if all("진단" in p["P"].alltext and "대신" in p["P"].alltext for p in posts.values()) else "warn", "면책 문구")

    # ---------------- AEO
    frac("aeo", "글 제목이 질문형", list(posts.values()), lambda p: any(h[0] == "h1" and (h[1].endswith("?") or h[1].endswith("나요") or h[1].endswith("까요")) for h in p["P"].heads), warn=0.6)
    frac("aeo", "한 줄 답변 상자", list(posts.values()), lambda p: 'class="answer"' in p["body"])
    def first_answer_len(p):
        m = re.search(r'<div class="answer">(.*?)</div>', p["body"], re.S)
        if not m: return 0
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        return len(t.split())
    frac("aeo", "첫 답변 20~70어절", list(posts.values()), lambda p: 20 <= first_answer_len(p) <= 70, warn=0.5)
    frac("aeo", "요약 카드(한눈에 보기)", list(posts.values()), lambda p: "glance" in p["body"])
    frac("aeo", "FAQ 블록", list(posts.values()), lambda p: p["P"].details >= 2)
    frac("aeo", "FAQ 블록과 FAQPage 개수 일치", list(posts.values()), lambda p: (lambda f: (not f) or len(f[0].get("mainEntity", [])) == p["P"].details or len(f[0].get("mainEntity", [])) >= p["P"].details - 1)(ld_find(p["P"], "FAQPage")))
    frac("aeo", "질문형 소제목(H2)", list(posts.values()), lambda p: sum(1 for h in p["P"].heads if h[0] == "h2" and ("?" in h[1] or h[1].endswith("나요") or h[1].endswith("까요"))) >= 1, warn=0.5)
    frac("aeo", "목록(ul/ol) 사용", list(posts.values()), lambda p: p["P"].lists >= 3)
    frac("aeo", "표(table) 사용", list(posts.values()), lambda p: p["P"].tables >= 1, good=0.5, warn=0.2)
    frac("aeo", "감수자 표기(본문)", list(posts.values()), lambda p: "감수" in p["P"].alltext)
    frac("aeo", "감수자 자격(한의사)", list(posts.values()), lambda p: "한의사" in p["P"].alltext)
    frac("aeo", "발행·수정일 본문 표기", list(posts.values()), lambda p: "발행" in p["P"].alltext and "수정" in p["P"].alltext)
    frac("aeo", "'먼저 확인이 필요한' 안전 구역", list(posts.values()), lambda p: "먼저 확인" in p["P"].alltext)
    frac("aeo", "원인 설명 구역", list(posts.values()), lambda p: any(h[1].startswith("왜") for h in p["P"].heads), warn=0.6)
    frac("aeo", "기록·준비 안내 구역", list(posts.values()), lambda p: "기록" in p["P"].alltext)
    frac("aeo", "진료 흐름 설명", list(posts.values()), lambda p: CLINIC in p["P"].alltext)
    frac("aeo", "안내 그림(인포그래픽)", list(posts.values()), lambda p: "images/info/post-" in p["body"], good=0.8, warn=0.4)
    frac("aeo", "근거·출처 표현", list(posts.values()), lambda p: re.search(r"알려져 있|권고|가이드라인|기준|참고", p["P"].alltext) is not None, warn=0.4)
    frac("aeo", "숫자·구체 기준 포함", list(posts.values()), lambda p: len(re.findall(r"\d+\s*(분|시간|일|주|개월|도|%|회|cm|mm)", p["P"].alltext)) >= 2, warn=0.5)
    frac("aeo", "단락 길이 적정(200자 이하 위주)", list(posts.values()), lambda p: sum(1 for x in p["P"].paras if len(x) <= 200) >= len(p["P"].paras) * 0.8, warn=0.6)
    frac("aeo", "관련 글 3편 이상", list(posts.values()), lambda p: p["body"].count("postcard") >= 3, warn=0.5)
    frac("aeo", "분류 허브 페이지 링크", list(posts.values()), lambda p: "index.html" in p["body"])
    cats = [v for k, v in pg.items() if k.startswith("cat:")]
    frac("aeo", "분류 허브: 답변형 첫 문단", cats, lambda p: "hublead" in p["body"])
    frac("aeo", "분류 허브: FAQ 구조화", cats, lambda p: "FAQPage" in ld_types(p["P"]))
    frac("aeo", "분류 허브: 안내 그림", cats, lambda p: "images/info/" in p["body"])
    add("aeo", "FAQ 페이지 별도", "ok" if "faq" in pg else "fail", "/faq.html")
    add("aeo", "FAQ 페이지 질문 10개 이상", "ok" if "faq" in pg and pg["faq"]["P"].details >= 10 else "warn", f"{pg['faq']['P'].details if 'faq' in pg else 0}개")
    add("aeo", "의료 안전 안내(응급실·109)", "ok" if any("응급실" in p["P"].alltext for p in posts.values()) else "warn", "응급 안내")

    # ---------------- GEO
    lt = F["llms.txt"]
    add("geo", "llms.txt 있음", "ok" if lt["status"] == 200 else "fail", f"{lt['status']}")
    add("geo", "llms.txt 5KB 이하", "ok" if 0 < lt["bytes"] <= 6000 else "warn", f"{lt['bytes']}바이트")
    add("geo", "llms.txt 제목(#)", "ok" if lt["body"].startswith("# ") else "warn", "첫 줄 제목")
    add("geo", "llms.txt 요약(>)", "ok" if "\n> " in lt["body"] else "warn", "인용 블록 요약")
    add("geo", "llms.txt 링크 목록", "ok" if lt["body"].count("](") >= 5 else "warn", f"링크 {lt['body'].count('](')}개")
    add("geo", "llms-full.txt 있음", "ok" if F["llms-full.txt"]["status"] == 200 else "warn", f"{F['llms-full.txt']['status']}")
    add("geo", "llms.txt → llms-full 연결", "ok" if "llms-full.txt" in lt["body"] else "warn", "전체본 링크")
    rbody = F["robots.txt"]["body"]
    blocked_all = re.search(r"(?im)^user-agent:\s*\*\s*$\s*^disallow:\s*/\s*$", rbody)
    for bot in AI_BOTS:
        sec = re.search(rf"(?ims)^user-agent:\s*{re.escape(bot)}\s*$(.*?)(?=^user-agent:|\Z)", rbody)
        if sec and re.search(r"(?im)^disallow:\s*/\s*$", sec.group(1)):
            add("geo", f"{bot} 허용", "fail", "robots 에서 차단")
        else:
            add("geo", f"{bot} 허용", "fail" if blocked_all else "ok", "전체 허용(*)" if not sec else "개별 규칙 허용")
    names = sum(1 for p in allp if CLINIC in p["P"].alltext)
    add("geo", "이름(N) 일관", "ok" if names == len(allp) else "warn", f"{names}/{len(allp)}쪽")
    phones = sum(1 for p in allp if PHONE in p["P"].alltext or "028157510" in p["body"])
    add("geo", "전화(P) 일관", "ok" if phones >= len(allp) * 0.9 else "warn", f"{phones}/{len(allp)}쪽")
    addr_pages = [p for p in (home, pg.get("visit"), pg.get("about")) if p]
    add("geo", "주소(A) 일관", "ok" if all(ADDR in p["P"].alltext for p in addr_pages) else "warn", "홈·오시는 길·소개")
    hrs = all(re.search(r"09:30\s*~\s*20:00", p["P"].alltext) and re.search(r"09:30\s*~\s*15:00", p["P"].alltext) for p in addr_pages)
    add("geo", "진료시간 일관(홈·오시는 길·소개)", "ok" if hrs else "warn", "평일 09:30~20:00 / 주말 09:30~15:00")
    add("geo", "llms.txt 진료시간", "ok" if "09:30~20:00" in lt["body"] and "09:30~15:00" in lt["body"] else "warn", "시간 표기")
    add("geo", "alternateName", "ok" if clinic.get("alternateName") else "warn", str(clinic.get("alternateName"))[:40])
    add("geo", "sameAs(외부 프로필)", "ok" if clinic.get("sameAs") else "warn", f"{len(clinic.get('sameAs') or [])}개")
    add("geo", "areaServed(지역)", "ok" if clinic.get("areaServed") else "warn", "상도동·노량진·동작구")
    emp = clinic.get("employee") or []
    lee = [e for e in emp if isinstance(e, dict) and e.get("name") == "이종호"]
    add("geo", "대표원장 자격 정보(hasCredential·alumniOf)", "ok" if lee and lee[0].get("hasCredential") and lee[0].get("alumniOf") else "warn", "JSON-LD Person")
    add("geo", "지역 신호(상도동·노량진·동작구)", "ok" if home and all(w in home["P"].alltext for w in ("상도동", "노량진", "동작구")) else "warn", "홈 본문")
    add("geo", "지역 글 묶음(local)", "ok" if any("guide/local" in p["body"] for p in allp) else "warn", "동네 글")
    frac("geo", "인용 가능한 짧은 단락", list(posts.values()), lambda p: sum(1 for x in p["P"].paras if 40 <= len(x) <= 220) >= 3, warn=0.5)
    frac("geo", "글마다 '한 줄 답변'", list(posts.values()), lambda p: "한 줄 답변" in p["P"].alltext)
    add("geo", "네트워크 소속 설명", "ok" if home and "좋은꿈 네트워크" in home["P"].alltext else "warn", "parentOrganization")
    add("geo", "의료광고 규칙(효과 단정 없음)", "ok" if not any(re.search(r"완치|효과를 보장|100% ", p["P"].alltext) for p in allp) else "fail", "AI 인용 시 위험 표현")
    add("geo", "AI 이미지 표시", "ok" if any("AI로 만든" in p["P"].alltext for p in allp) else "warn", "AI 그림 투명성")
    return R


def score(items):
    ok = sum(1 for i in items if i["status"] == "ok")
    den = sum(1 for i in items if i["status"] in ("ok", "warn", "fail"))
    return round(ok / den * 100) if den else 0


AREA = {"naver": "네이버 SEO", "google": "구글 SEO", "aeo": "AEO 답변엔진", "geo": "GEO 생성형엔진"}
LABEL = {"ok": "잘됨", "warn": "주의", "fail": "개선필요", "unk": "미확인", "na": "해당없음"}
COLOR = {"ok": "#34d399", "warn": "#fbbf24", "fail": "#f87171", "unk": "#94a3b8", "na": "#64748b"}


def render(runs, path, todo):
    last = runs[-1]
    prev = runs[-2] if len(runs) > 1 else None
    allitems = [i for a in AREA for i in last["result"][a]]
    cnt = {k: sum(1 for i in allitems if i["status"] == k) for k in LABEL}
    fails = [(AREA[a], i) for a in AREA for i in last["result"][a] if i["status"] == "fail"]
    warns = [(AREA[a], i) for a in AREA for i in last["result"][a] if i["status"] == "warn"]
    E = html.escape
    cards = ""
    for a in AREA:
        it = last["result"][a]
        s = score(it)
        ps = f"<span class='prev'>이전 {score(prev['result'][a])}</span>" if prev else ""
        c = {k: sum(1 for i in it if i["status"] == k) for k in ("ok", "warn", "fail")}
        cards += (f"<div class='card'><div class='k'>{AREA[a]}<span>{len(it)}항목 점검</span></div><div class='big'>{s}<small>/100</small>{ps}</div>"
                  f"<div class='dots'><i style='color:{COLOR['ok']}'>●</i> 잘됨 {c['ok']} <i style='color:{COLOR['warn']}'>●</i> 주의 {c['warn']} <i style='color:{COLOR['fail']}'>●</i> 개선필요 {c['fail']}</div></div>")
    fix = "".join(f"<li><b>[{E(a)}]</b> {E(i['name'])} — <span>{E(i['why'])}</span></li>" for a, i in fails) or "<li>개선필요 항목이 없습니다.</li>"
    warnl = "".join(f"<li><b>[{E(a)}]</b> {E(i['name'])} — <span>{E(i['why'])}</span></li>" for a, i in warns[:40])
    tables = ""
    for a in AREA:
        rows = "".join(f"<tr><td>{E(i['name'])}</td><td style='color:{COLOR[i['status']]}'>{LABEL[i['status']]}</td><td>{E(i['why'])}</td></tr>" for i in last["result"][a])
        tables += f"<h3>{AREA[a]} 세부 ({len(last['result'][a])}항목)</h3><table><tr><th>항목</th><th>결과</th><th>근거</th></tr>{rows}</table>"
    hist = "".join(f"<tr><td>{E(r['tag'])}</td><td>{E(r['time'])}</td>" + "".join(f"<td>{score(r['result'][a])}</td>" for a in AREA) + "</tr>" for r in runs)
    todo_html = "".join(f"<li>{E(t)}</li>" for t in todo)
    doc = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>홈페이지 진단 | {CLINIC}</title><style>
body{{margin:0;background:#0b0d12;color:#e5e7eb;font-family:'Noto Sans KR','Malgun Gothic',sans-serif;line-height:1.6}}
.w{{max-width:1180px;margin:0 auto;padding:28px 18px 60px}}.top{{display:grid;grid-template-columns:2fr 1fr;gap:14px}}
.box{{background:#151922;border:1px solid #262c38;border-radius:14px;padding:18px 20px}}.lab{{font-size:12px;color:#94a3b8;letter-spacing:.2em}}
.hero{{background:#1b2030;border:1px solid #2a3142;border-radius:16px;padding:26px 28px;margin:14px 0}}.hero h1{{margin:6px 0 14px;font-size:30px}}
.pill{{display:inline-block;background:#232a38;border-radius:10px;padding:6px 12px;margin-right:8px;font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card{{background:#151922;border:1px solid #3b2a5a;border-radius:14px;padding:16px}}
.k{{color:#c084fc;font-weight:700;font-size:14px;display:flex;justify-content:space-between}}.k span{{color:#94a3b8;font-weight:400;font-size:12px}}
.big{{font-size:44px;font-weight:800;margin:6px 0}}.big small{{font-size:14px;color:#94a3b8;font-weight:400}}.prev{{font-size:13px;color:#94a3b8;margin-left:10px;font-weight:400}}
.dots{{font-size:13px;color:#cbd5e1}}.dots i{{font-style:normal}}ul{{padding-left:18px}}li span{{color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 22px}}td,th{{border-bottom:1px solid #262c38;padding:7px 8px;text-align:left;vertical-align:top}}th{{color:#94a3b8}}
h2,h3{{margin:26px 0 8px}}@media(max-width:860px){{.grid{{grid-template-columns:1fr 1fr}}.top{{grid-template-columns:1fr}}}}
</style></head><body><div class="w">
<div class="top"><div class="box"><div class="lab">점검 대상</div><div style="font-size:20px;font-weight:700">{E(last['base'])}/</div><div>{CLINIC}</div></div>
<div class="box"><div class="lab">응답 코드</div><div style="font-size:20px;font-weight:700">{last['home_status']}</div><div>점검 시각 {E(last['time'])}</div></div></div>
<div class="hero"><div class="lab" style="color:#c084fc">이번 진단에서 확인한 내용</div><h1>먼저 고칠 점 {cnt['fail']}개, 살펴볼 점 {cnt['warn']}개</h1>
<span class="pill">잘된 점 <b style="color:#34d399">{cnt['ok']}</b></span><span class="pill">주의 <b style="color:#fbbf24">{cnt['warn']}</b></span><span class="pill">개선필요 <b style="color:#f87171">{cnt['fail']}</b></span>
<p style="color:#cbd5e1">네이버·구글·GEO는 기술 항목, AEO는 확인 가능한 콘텐츠 구조 항목의 충족도입니다. 100점도 검색 순위를 보장하지 않습니다. 미확인·해당없음은 점수 계산에서 뺐습니다.</p>
<p style="color:#94a3b8">미확인 {cnt['unk']}개 · 해당없음 {cnt['na']}개 · 배포된 사이트를 직접 받아 홈·대표 페이지·분류 3곳·글 10편 표본으로 점검했습니다.</p></div>
<div class="grid">{cards}</div>
<h2>먼저 고칠 점</h2><ul>{fix}</ul>
<h2>원장님이 하실 일</h2><ul>{todo_html}</ul>
<h2>살펴볼 점(주의)</h2><ul>{warnl}</ul>
<h2>회차별 점수</h2><table><tr><th>회차</th><th>시각</th>{''.join(f'<th>{AREA[a]}</th>' for a in AREA)}</tr>{hist}</table>
{tables}</div></body></html>"""
    open(path, "w", encoding="utf-8").write(doc)


TODO = [
    "구글 서치콘솔에서 HTML 태그 인증 코드를 받아 주시면 site.json 의 google_site_verification 에 넣겠습니다(이미 DNS로 인증하셨다면 할 일 없음).",
    "네이버 스마트플레이스 업체 정보에 홈페이지 주소 https://gooddreamclinic.com 을 등록해 주세요.",
    "구글 비즈니스 프로필·카카오 채널·네이버 플레이스 주소를 알려 주시면 sameAs(외부 프로필 연결)에 넣겠습니다.",
    "네이버 블로그 주소를 알려 주시면 홈 바닥글에 연결하겠습니다.",
    "네이버 서치어드바이저와 구글 서치콘솔에 sitemap.xml·feed.xml 제출 상태를 한 번 확인해 주세요.",
    "환자 후기는 의료법상 싣지 않습니다. 대신 지도 앱 리뷰는 원장님 계정에서 답글로 관리해 주세요.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://gooddreamclinic.com")
    ap.add_argument("--html", default="")
    ap.add_argument("--tag", default="진단")
    a = ap.parse_args()
    data = collect(a.base)
    res = run_checks(data)
    run = {"tag": a.tag, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "base": a.base.rstrip("/"),
           "home_status": data["pages"]["home"]["status"], "result": res,
           "score": {k: score(v) for k, v in res.items()}}
    jp = os.path.join(ROOT, "content", "_audit.json")
    runs = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else []
    runs = [r for r in runs if r["tag"] != a.tag] + [run]
    json.dump(runs, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.html:
        render(runs, a.html, TODO)
    print(json.dumps({k: f"{score(v)} ({len(v)}항목, 개선필요 {sum(1 for i in v if i['status']=='fail')}, 주의 {sum(1 for i in v if i['status']=='warn')})" for k, v in res.items()}, ensure_ascii=False))
    for ar, v in res.items():
        for i in v:
            if i["status"] == "fail":
                print("개선필요", AREA[ar], "|", i["name"], "|", i["why"])


if __name__ == "__main__":
    main()
