#!/usr/bin/env python3
"""빌드 마지막 손질(지시서 6번):
- <img> 의 src/srcset 에서 같은 이름 .webp 가 있으면 .webp 로 바꾼다(공유 미리보기 og:image 는 JPG 유지).
- alt 가 빈 장식용 이미지에 aria-hidden="true" 를 붙인다.
- width·height 가 없는 <img> 에 실제 파일 크기(PIL, SVG 는 viewBox)를 넣는다(화면 밀림 방지. CSS 의 :where(img[height]){height:auto} 로 모양은 그대로).
사용: build.py 가 끝에서 부른다. 단독 실행: python tools/post_html.py"""
import glob, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_WH = {}


def file_wh(path):
    """그림 파일의 (가로, 세로). 못 읽으면 None."""
    if path not in _WH:
        _WH[path] = None
        try:
            if path.lower().endswith(".svg"):
                head = open(path, encoding="utf-8", errors="replace").read(4000)
                m = re.search(r"<svg\b[^>]*>", head, re.S)
                svg = m.group(0) if m else ""
                w = re.search(r'\swidth="([\d.]+)(px)?"', svg)
                h = re.search(r'\sheight="([\d.]+)(px)?"', svg)
                vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
                if w and h:
                    _WH[path] = (round(float(w.group(1))), round(float(h.group(1))))
                elif vb:
                    _WH[path] = (round(float(vb.group(1))), round(float(vb.group(2))))
            else:
                from PIL import Image
                with Image.open(path) as im:
                    _WH[path] = im.size
        except Exception:
            pass
    return _WH[path]


def add_wh(tag, base_dir):
    if re.search(r"\swidth=", tag) and re.search(r"\sheight=", tag):
        return tag
    m = re.search(r"""\ssrc=(["'])([^"']+)\1""", tag)
    if not m or m.group(2).startswith(("http:", "https:", "data:", "//")):
        return tag
    rel = m.group(2).split("?")[0].split("#")[0]
    path = os.path.join(ROOT, rel.lstrip("/")) if rel.startswith("/") else os.path.normpath(os.path.join(base_dir, rel))
    wh = file_wh(path) if os.path.isfile(path) else None
    if not wh:
        return tag
    tag = re.sub(r"""\s(width|height)=(["'])[^"']*\2""", "", tag)
    return tag[:-1].rstrip("/").rstrip() + f' width="{wh[0]}" height="{wh[1]}">'


def fix_img(tag, base_dir):
    def sw(m):
        url = m.group(0)
        rel = url
        path = os.path.normpath(os.path.join(base_dir, rel)) if not rel.startswith("/") else os.path.join(ROOT, rel.lstrip("/"))
        if os.path.exists(path[:-4] + ".webp"):
            return url[:-4] + ".webp"
        return url
    tag = re.sub(r"[^\s'\",]*?images/[^\s'\",]+?\.jpg", sw, tag)
    tag = add_wh(tag, base_dir)
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
