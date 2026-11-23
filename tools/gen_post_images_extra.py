#!/usr/bin/env python3
"""분류별 글 수만큼 사진이 되도록 추가 생성한다(글마다 겹치지 않게). 장면 목록은 gen_post_images.py 에서 읽는다.
사용: python gen_post_images_extra.py <catcount.json>   (분류: 글 수)"""
import ast, io, json, os, sys, time, urllib.request
from PIL import Image

src = open(os.path.join(os.path.dirname(__file__), "gen_post_images.py"), encoding="utf-8").read()
G = {}
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("S", "PHOTO", "RENDER", "ANGLES"):
        G[node.targets[0].id] = ast.literal_eval(node.value)
S, PHOTO, RENDER, ANGLES = G["S"], G["PHOTO"], G["RENDER"], G["ANGLES"]
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
WHO2 = ["a Korean woman in her 20s", "a Korean man in his 30s", "a Korean woman in her 60s", "a Korean man in his 50s",
        "a Korean woman in her 70s", "a Korean man in his 20s", "a Korean office worker in her 40s", "a Korean office worker in his 30s"]
KID2 = ["a Korean mother and her toddler", "a Korean father and his teenage son", "a Korean family with two children",
        "a Korean high school student", "a Korean grandfather and grandchild", "a Korean mother and her daughter",
        "a Korean elementary-school child with a teacher", "a Korean middle-school student"]
PLACES = ["at home", "at the office", "outdoors in a quiet park", "in a cafe", "in the evening at home"]
target = json.load(open(sys.argv[1], encoding="utf-8"))


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


jobs = []
for cat, subs in S.items():
    need = target.get(cat, 0)
    if need <= 30:
        continue
    who = KID2 if cat == "pediatric" else WHO2
    combos = []
    for place in PLACES:
        for s in subs:
            for k, w in enumerate(who):
                if s.startswith("R:"):
                    combos.append(f"{s[2:]}, {ANGLES[k % 5]}, variation {place}, {RENDER}")
                else:
                    combos.append(f"{s.format(w=w)}, {place}, {PHOTO}")
    for n in range(31, need + 1):
        name = f"{cat}-{n:03d}"
        if not os.path.exists(f"images/post/{name}.jpg"):
            jobs.append((name, combos[(n - 31) % len(combos)]))
print("to make", len(jobs), flush=True)
ok = fail = 0
for b in range(0, len(jobs), 20):
    batch = jobs[b:b + 20]
    tasks = {}
    for name, prompt in batch:
        for _ in range(3):
            try:
                tasks[name] = call("https://api.magnific.com/v1/ai/mystic", {"prompt": prompt, "aspect_ratio": "widescreen_16_9", "resolution": "1k"})["data"]["task_id"]
                break
            except Exception:
                time.sleep(10)
    done = {}
    for _ in range(90):
        for name, tid in tasks.items():
            if name in done:
                continue
            try:
                d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
            except Exception:
                continue
            if d["status"] == "COMPLETED" and d.get("generated"):
                try:
                    img = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
                    im = Image.open(io.BytesIO(img)).convert("RGB")
                    im.thumbnail((1280, 720))
                    im.save(f"images/post/{name}.jpg", quality=78, optimize=True, progressive=True)
                    done[name] = 1
                    ok += 1
                except Exception:
                    done[name] = 0
                    fail += 1
            elif d["status"] in ("FAILED", "ERROR"):
                done[name] = 0
                fail += 1
        if len(done) == len(tasks):
            break
        time.sleep(8)
    print(f"batch {b // 20 + 1}: ok {ok} fail {fail}", flush=True)
print("done ok", ok, "fail", fail)
