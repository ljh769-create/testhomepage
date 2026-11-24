#!/usr/bin/env python3
"""사이트에 쓰는 JPG 옆에 같은 이름의 WebP(품질 78)를 만든다. 있는 파일은 건너뛴다.
대상: images/ 바로 아래와 real, herbpub, post, post2, pool, thumb, gallery 폴더(원본 촬영 폴더는 제외)."""
import glob, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SKIP = ("images/2", "images/1차", "images/KakaoTalk", "images/batch_", "images/Telegram", "images/herb/", "images/files", "images/참사랑", "images/KakaoTalk")
srcs = glob.glob("images/*.jpg") + [f for d in ("real", "herbpub", "post", "post2", "pool", "thumb", "gallery") for f in glob.glob(f"images/{d}/*.jpg")]
n = 0
for s in srcs:
    s2 = s.replace("\\", "/")
    if s2.startswith(SKIP):
        continue
    out = s[:-4] + ".webp"
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(s):
        continue
    try:
        Image.open(s).convert("RGB").save(out, "WEBP", quality=78, method=5)
        n += 1
    except Exception as e:
        print("skip", s, e)
print("webp made", n)
