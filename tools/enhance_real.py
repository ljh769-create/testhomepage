#!/usr/bin/env python3
"""실제 한의원 사진을 매그니픽 정밀 업스케일(내용은 그대로, 선명도·결만 살림)로 다듬는다.
사용: python3 tools/enhance_real.py images/real/r4-herb-cabinet.jpg ...  (같은 이름 .jpg/.webp/-sm 을 덮어씀, 원본은 *.orig.jpg 로 보관)"""
import base64, io, json, os, sys, time, urllib.request
from pathlib import Path
from PIL import Image
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
EP = "https://api.magnific.com/v1/ai/image-upscaler-precision"

def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))

tasks = {}
for f in sys.argv[1:]:
    p = Path(f); orig = p.with_suffix(".orig.jpg")
    if not orig.exists(): orig.write_bytes(p.read_bytes())
    im = Image.open(orig); im.thumbnail((1200, 1200)); b = io.BytesIO(); im.save(b, "JPEG", quality=92)
    tasks[p] = call(EP, {"image": base64.b64encode(b.getvalue()).decode(), "sharpen": 7, "smart_grain": 5, "ultra_detail": 25})["data"]["task_id"]
    print("주문", p.name, flush=True)
done = {}
for _ in range(120):
    for p, t in tasks.items():
        if p in done: continue
        d = call(f"{EP}/{t}")["data"]
        if d["status"] == "COMPLETED" and d.get("generated"):
            raw = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
            im = Image.open(io.BytesIO(raw)).convert("RGB"); base = str(p)[:-4]
            big = im.copy(); big.thumbnail((1600, 1600)); big.save(base + ".jpg", quality=86, optimize=True, progressive=True); big.save(base + ".webp", quality=82)
            sm = im.copy(); sm.thumbnail((800, 800)); sm.save(base + "-sm.jpg", quality=80, optimize=True); sm.save(base + "-sm.webp", quality=78)
            done[p] = 1; print("저장", p.name, flush=True)
        elif d["status"] in ("FAILED", "ERROR"):
            done[p] = 0; print("실패", p.name, flush=True)
    if len(done) == len(tasks): break
    time.sleep(8)
print(f"완료 {sum(done.values())}/{len(tasks)}")
