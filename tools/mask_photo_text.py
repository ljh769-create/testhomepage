#!/usr/bin/env python3
"""실사진 속 광고성 포스터(가격·'본원만의 특별한'·상품 광고·'완치' 문구)를 흐리게 가린다 (의료광고 검수 2026-11-25).
좌표는 사진 가로·세로를 10으로 나눈 값. 같은 사진을 새로 넣거나 다시 만들면 한 번 다시 실행한다(여러 번 돌려도 모양은 같다)."""
import os, sys
from PIL import Image, ImageDraw, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def R(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
MASKS = {
    "consult": [R(4.22, 2.3, 5.8, 5.35), R(4.65, 5.3, 5.9, 7.75)],
    "chuna-neck1": [R(1.75, 1.5, 5.68, 4.7)],
    "chuna-neck2": [R(0, 2.05, 3.98, 7.25)],
    "chuna-shoulder": [[(0.6, 0), (5.95, 0), (5.95, .85), (4.95, 1.35), (4.55, 2.4), (4.45, 4.0), (.6, 4.0)]],
    "consult-tablet": [[(1.3, .85), (5.48, .85), (5.48, 4.15), (3.55, 4.15), (3.4, 2.7), (3.22, 2.0), (2.85, 1.65), (2.4, 1.7), (1.98, 2.6), (1.92, 4.15), (1.3, 4.15)]],
    "doc-wst": [[(.2, 3.65), (3.6, 3.65), (3.2, 5.0), (2.88, 6.5), (.2, 6.5)]],
    "doc-room": [[(1.3, 3.65), (5.05, 3.65), (4.75, 4.4), (4.05, 5.05), (1.3, 5.05)]],
    "team-herbset": [R(8.92, 2.4, 10, 6.4), R(7.62, .4, 8.35, 2.9)],
    "treat-vice1": [R(8.18, 0, 10, 3.1)],
    "vice-desk": [R(8.35, 5.65, 10, 9.35)],
    "director-desk": [R(8.35, 5.0, 10, 8.85)],
    "room-device1": [R(0, 0, 3.3, 2.8)],
    "room-device2": [R(0, 0, 3.65, 2.7), R(5.35, 0, 7.35, 2.25), R(3.6, 0, 5.4, .48), R(3.95, 1.95, 6.05, 2.45)],
    "room-entrance": [R(5.75, 2.7, 7.95, 4.2), R(6.35, 5.1, 8.55, 6.95)],
}
# images/ 바로 아래·gallery 의 사진 (.jpg·.webp). 다시 가린 뒤에는 해당 images/thumb/ 파일을 지우고 tools/make_thumbs.py 실행.
OTHER = {
    "banner-herbroom-1": [R(8.5, 1.8, 10, 10)],
    "banner-herbroom-2": [R(4.9, 0, 8.25, 10)],
    "banner-herbroom-3": [R(2.35, 0, 5.65, 10)],
    "clinic-herbroom": [R(5.15, .6, 7.35, 7.4)],
    "gallery/entrance1": MASKS["room-entrance"],
}
def apply(path, polys):
    im = Image.open(path).convert("RGB"); w, h = im.size
    m = Image.new("L", im.size, 0); d = ImageDraw.Draw(m)
    for p in polys: d.polygon([(x * w / 10, y * h / 10) for x, y in p], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w / 300))
    soft = im.resize((max(1, w // 40), max(1, h // 40)), Image.BILINEAR).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(w / 110))
    out = Image.composite(soft, im, m)
    out.save(path, quality=88) if path.endswith(".jpg") else out.save(path, "WEBP", quality=84, method=6)
if __name__ == "__main__":
    n = 0
    for k, polys in ({} if "--other" in sys.argv else MASKS).items():
        for suf in (".jpg", "-sm.jpg", ".webp", "-sm.webp"):
            p = os.path.join(ROOT, "images", "real", k + suf)
            if os.path.exists(p): apply(p, polys); n += 1
    for k, polys in OTHER.items():
        for suf in (".jpg", ".webp"):
            p = os.path.join(ROOT, "images", k + suf)
            if os.path.exists(p) and "--other" in sys.argv: apply(p, polys); n += 1
    print("가린 파일", n)
