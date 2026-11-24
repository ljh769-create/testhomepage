#!/usr/bin/env python3
"""빌드 마지막 손질(지시서 6번):
- <img> 의 src/srcset 에서 같은 이름 .webp 가 있으면 .webp 로 바꾼다(공유 미리보기 og:image 는 JPG 유지).
- alt 가 빈 장식용 이미지에 aria-hidden="true" 를 붙인다.
사용: build.py 가 끝에서 부른다. 단독 실행: python tools/post_html.py"""
import glob, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fix_img(tag, base_dir):
    def sw(m):
        url = m.group(0)
        rel = url
        path = os.path.normpath(os.path.join(base_dir, rel)) if not rel.startswith("/") else os.path.join(ROOT, rel.lstrip("/"))
        if os.path.exists(path[:-4] + ".webp"):
            return url[:-4] + ".webp"
        return url
    tag = re.sub(r"[^\s'\",]+?images/[^\s'\",]+?\.jpg", sw, tag)
    if "loading=" not in tag and "fetchpriority" not in tag:
        tag = tag[:-1].rstrip("/").rstrip() + ' loading="lazy">'
    if re.search(r"""\balt=(""|'')""", tag) and "aria-hidden" not in tag:
        tag = tag[:-1].rstrip("/").rstrip() + ' aria-hidden="true">'
    return tag


def run():
    files = glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "guide", "**", "*.html"), recursive=True)
    n = 0
    for f in files:
        s = open(f, encoding="utf-8").read()
        t = re.sub(r"<img\b[^>]*>", lambda m: fix_img(m.group(0), os.path.dirname(f)), s)
        if t != s:
            open(f, "w", encoding="utf-8").write(t)
            n += 1
    return n


if __name__ == "__main__":
    print("pages fixed", run())
