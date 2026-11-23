#!/usr/bin/env python3
"""글 제목에 맞춘 고유 그림: images/post2/<slug>.jpg
사용: python tools/gen_post2.py prompts1.json [prompts2.json ...]
각 json 은 {"slug": {"scene": "...", "kind": "photo|still|anatomy|illust"}} 형식. 있는 파일은 건너뛴다.
같은 느낌이 반복되지 않도록 색감·빛·렌즈를 글마다 바꾼다(글 이름으로 고정되어 다시 만들어도 같은 조합)."""
import hashlib, io, json, os, sys, time, urllib.request
from PIL import Image

KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
KOREA = ("ethnically Korean person with natural Korean facial features, contemporary Seoul setting, "
         "Korean apartment or Korean office details, realistic skin texture, candid unposed moment, anatomically correct hands")
GRADES = ["warm golden-hour light, soft amber tones", "clean bright daylight, neutral true-to-life colors",
          "soft overcast light, muted pastel tones", "evening indoor lamp light, cozy warm shadows",
          "crisp morning light, gentle cool blue tones", "natural window side light, filmic Kodak Portra colors",
          "bright high-key white interior, airy and fresh", "dusk blue hour city light, calm mood"]
LENS = ["35mm documentary photo", "50mm portrait photo with shallow depth of field", "wide-angle environmental photo",
        "close-up detail shot on hands and objects", "over-the-shoulder candid shot", "eye-level medium shot"]
KIND = {
    "photo": "{scene}, {lens}, {grade}, " + KOREA + ", editorial magazine photography, no text, no letters, no logos",
    "still": "{scene}, still life product-style photography, {grade}, carefully styled props on a real Korean home or clinic surface, no people, no text, no logos",
    "anatomy": "{scene}, premium 3D medical illustration, translucent anatomy with soft glow, clean studio background in sky blue and white, no text, no labels",
    "illust": "{scene}, warm hand-drawn gouache illustration, soft textured paper, gentle sky-blue and cream palette, Korean everyday life, no text, no letters",
}


def pick(seq, slug, salt):
    return seq[int(hashlib.md5((salt + slug).encode()).hexdigest(), 16) % len(seq)]


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


jobs = []
for f in sys.argv[1:]:
    for slug, v in json.load(open(f, encoding="utf-8")).items():
        if os.path.exists(f"images/post2/{slug}.jpg"):
            continue
        k = v.get("kind", "photo") if v.get("kind") in KIND else "photo"
        jobs.append((slug, KIND[k].format(scene=v["scene"], lens=pick(LENS, slug, "l"), grade=pick(GRADES, slug, "g"))))
os.makedirs("images/post2", exist_ok=True)
print("to make", len(jobs), flush=True)
ok = fail = 0
for b in range(0, len(jobs), 20):
    tasks = {}
    for slug, prompt in jobs[b:b + 20]:
        for _ in range(3):
            try:
                tasks[slug] = call("https://api.magnific.com/v1/ai/mystic", {"prompt": prompt, "aspect_ratio": "widescreen_16_9", "resolution": "1k"})["data"]["task_id"]
                break
            except Exception:
                time.sleep(10)
    done = {}
    for _ in range(90):
        for slug, tid in tasks.items():
            if slug in done:
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
                    im.save(f"images/post2/{slug}.jpg", quality=78, optimize=True, progressive=True)
                    done[slug] = 1; ok += 1
                except Exception:
                    done[slug] = 0; fail += 1
            elif d["status"] in ("FAILED", "ERROR"):
                done[slug] = 0; fail += 1
        if len(done) == len(tasks):
            break
        time.sleep(8)
    print(f"batch {b // 20 + 1}: ok {ok} fail {fail}", flush=True)
print("done ok", ok, "fail", fail)
