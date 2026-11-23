#!/usr/bin/env python3
"""카드용 작은 이미지(640x360)를 images/thumb/ 에 만든다. 빌드(CI)에는 Pillow 가 없어서 미리 만들어 커밋한다."""
import glob, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
srcs = (glob.glob("images/pool/*.jpg") + glob.glob("images/ai-banner-*.jpg") + glob.glob("images/banner-*.jpg")
        + glob.glob("images/clinic-*.jpg") + glob.glob("images/gallery/*.jpg") + glob.glob("images/hero-*.jpg"))
n = 0
for s in srcs:
    rel = s.replace("\\", "/").split("images/", 1)[1]
    out = "images/thumb/" + rel.replace("/", "_")
    if os.path.exists(out): continue
    im = Image.open(s).convert("RGB"); W, H = im.size; th = int(W * 9 / 16)
    if th < H: im = im.crop((0, (H - th) // 2, W, (H - th) // 2 + th))
    else:
        tw = int(H * 16 / 9); im = im.crop(((W - tw) // 2, 0, (W - tw) // 2 + tw, H))
    im.thumbnail((640, 360)); im.save(out, quality=78, optimize=True, progressive=True); n += 1
print("thumbs made", n)
