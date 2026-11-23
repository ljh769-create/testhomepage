#!/usr/bin/env python3
"""원장님이 직접 찍은 한약 사진(images/2026*.jpg)을 웹용으로 만든다: images/herb/h-NNN.jpg
- 환자 이름표(흰 카드: 이름·조제일)는 사진 위쪽 40% 안에 꽂혀 있다 → 위쪽 46%를 잘라 내 아예 남기지 않는다.
  (흐림 처리는 약재까지 뭉개 보기 흉해서 쓰지 않는다. 결과는 사람이 표본을 눈으로 확인한다.)
- 원본은 저장소에 올리지 않는다(.gitignore). 결과만 올린다.
- _report.tsv: 결과 이름, 촬영 묶음(원본 파일 이름 앞부분), 종류(herb=약재 사진, scale=저울 사진)
사용: python tools/prep_herb_photos.py"""
import glob, os, re
import numpy as np
from PIL import Image, ImageOps

os.makedirs("images/herb", exist_ok=True)
files = sorted(glob.glob("images/2026*.jp*g"))
report = []
for k, f in enumerate(files):
    im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    im.thumbnail((1400, 1400))
    im = im.crop((0, int(im.height * 0.46), im.width, im.height))
    a = np.asarray(im.resize((200, max(1, int(200 * im.height / im.width))))).astype(int)
    mn, mx = a.min(2), a.max(2)
    low = (mx - mn) < 30
    white = ((mn > 200) & low).mean()
    grey = ((a.mean(2) > 110) & (a.mean(2) < 205) & low).mean()
    kind = "scale" if (grey > 0.35 and white < 0.15) else "herb"
    name = f"h-{k:03d}"
    im.save(f"images/herb/{name}.jpg", quality=80, optimize=True, progressive=True)
    burst = re.sub(r"[ (].*$", "", os.path.splitext(os.path.basename(f))[0])
    report.append((name, burst, kind))
with open("images/herb/_report.tsv", "w", encoding="utf-8") as fp:
    for r in report:
        fp.write("\t".join(r) + "\n")
print("done", len(report), "herb", sum(1 for r in report if r[2] == "herb"), "scale", sum(1 for r in report if r[2] == "scale"))
