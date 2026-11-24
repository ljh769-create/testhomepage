#!/usr/bin/env python3
"""지시서 8번 마지막 점검: '노량진점' 0건, 의료진 '전문 분야' 0건, JSON-LD 파싱, 진료시간 일치, 페이지당 H1 1개."""
import glob, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
pages = glob.glob("*.html") + glob.glob("guide/**/*.html", recursive=True)
txt = pages + ["llms.txt", "llms-full.txt"]
c1 = sum(open(f, encoding="utf-8").read().count("노량진점") for f in txt)
c2 = sum(len(re.findall(r"전문 분야", open(f, encoding="utf-8").read())) for f in txt)
bad_ld, n_ld = [], 0
h1_bad = []
for f in pages:
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        n_ld += 1
        try:
            json.loads(m.group(1).replace("<\\/", "</"))
        except Exception as e:
            bad_ld.append((f, str(e)[:80]))
    h = len(re.findall(r"<h1\b", s))
    if h != 1 and not f.endswith(("admin.html", "queue.html")):
        h1_bad.append((f, h))
# 진료시간 대조
def hours(s):
    return {"평일": bool(re.search(r"09:30\s*~\s*20:00", s)), "주말": bool(re.search(r"09:30\s*~\s*15:00", s))}
idx = open("index.html", encoding="utf-8").read()
faq = open("faq.html", encoding="utf-8").read()
llms = open("llms.txt", encoding="utf-8").read()
ld_ok = '"opens": "09:30"' in idx and '"closes": "20:00"' in idx and '"closes": "15:00"' in idx
print(json.dumps({"노량진점": c1, "전문 분야": c2, "JSON-LD 블록": n_ld, "JSON-LD 오류": bad_ld[:5],
                  "H1 1개 아닌 페이지": h1_bad[:10], "H1 문제 수": len(h1_bad),
                  "진료시간 홈": hours(idx), "진료시간 FAQ": hours(faq), "진료시간 llms": hours(llms), "진료시간 JSON-LD": ld_ok},
                 ensure_ascii=False, indent=1))
