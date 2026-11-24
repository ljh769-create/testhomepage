#!/usr/bin/env python3
"""지시서(2026-11-24) 1번: 사이트 전체에서 '노량진점' 지점 표기를 없앤다.
길 안내('노량진역 3번 출구' 등)와 slug(noryangjin-...)는 그대로 둔다. 사용: python tools/rename_branch.py [--dry]"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
DRY = "--dry" in sys.argv
FILES = (["build.py", "index.html", "sleep.html", "diet.html", "llms.txt", "site.json", "config.js", "manifest.webmanifest", "offline.html"]
         + glob.glob("privacy.html") + glob.glob("404.html") + glob.glob("content/*.json") + glob.glob("content/posts/*.md")
         + glob.glob("images/info/*.svg") + glob.glob("naver-blog/posts/*.md") + glob.glob("tools/*.py"))
RULES = [
    (r"좋은꿈참사랑\s?한의원\s*노량진\s?점", "좋은꿈참사랑한의원"),
    (r"좋은꿈\s?네트워크\s*노량진\s?점", "좋은꿈 네트워크 상도역 좋은꿈참사랑한의원"),
    (r"노량진\s?점\s*진료과목", "진료과목"),
    (r"노량진\s?점\s*·\s*(한방가이드|좋은꿈 네트워크)", r"상도역 · \1"),
    (r"노량진\s?점\s*진료원장", "진료원장"),
    (r"노량진\s?점\s*진료 문의", "진료 문의"),
    (r"노량진\s?점", "좋은꿈참사랑한의원"),
    (r"좋은꿈참사랑한의원(\s*)좋은꿈참사랑한의원", r"좋은꿈참사랑한의원"),
]
total = 0
for f in sorted(set(FILES)):
    if f.endswith("rename_branch.py") or not os.path.exists(f):
        continue
    s = open(f, encoding="utf-8").read()
    n0 = len(re.findall(r"노량진\s?점", s))
    if not n0:
        continue
    t = s
    for a, b in RULES:
        t = re.sub(a, b, t)
    total += n0
    if not DRY:
        open(f, "w", encoding="utf-8").write(t)
    print(f"{n0:4d}  {f}")
print("total", total, "(dry)" if DRY else "(applied)")
