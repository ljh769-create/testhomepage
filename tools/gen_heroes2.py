#!/usr/bin/env python3
"""대표(가로 전체) 이미지를 사람 사진·3D 인체 그림 스타일로 다시 만든다. images/hero-<cat>.jpg 덮어씀 (2K).
키: ~/magnific-key.txt"""
import io, json, os, sys, time, urllib.request
from PIL import Image

KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
PHOTO = ("natural cinematic lifestyle photography, realistic Korean person, soft natural light, "
         "sky-blue and white color grading, premium Korean clinic advertisement, wide 16:9 banner composition "
         "with calm open space in the center for a title, anatomically correct hands, no text, no logos")
RENDER = ("high-end 3D medical illustration, translucent glass-like anatomy glowing sky blue on a deep navy background, "
          "cinematic, elegant, wide 16:9 banner composition with open space in the center, no text, no labels")
SCENES = {
    "home": "P:a Korean woman waking up peacefully in a bright white bedroom with sky-blue morning light, stretching gently",
    "insomnia": "P:a Korean woman lying awake in bed at night in blue moonlight, calm but tired",
    "mental": "P:a Korean man sitting by a large window taking a deep breath, calm blue morning light",
    "neuro": "R:glowing blue neurons connected by luminous fibers floating in deep space",
    "pain": "R:a translucent human spine and shoulders glowing blue",
    "chuna": "R:a translucent human spine with aligned vertebrae and pelvis glowing blue, side view",
    "ultrasound": "R:a translucent shoulder joint with tendons and muscles glowing blue",
    "accident": "R:a translucent human neck and cervical spine glowing blue",
    "shockwave": "R:translucent foot and heel bones with tendons glowing blue",
    "digestion": "R:a translucent human stomach and intestines glowing blue",
    "metabolic": "R:translucent human heart and blood vessels glowing blue",
    "herbal": "P:dried medicinal herbs and a Korean doctor's hands preparing herbal medicine on a wooden table, soft blue light",
    "women": "P:a Korean woman in her 40s relaxing on a sofa with a cup of tea, soft window light",
    "pediatric": "P:a Korean mother and young child reading together on a sofa in a bright room",
    "respiratory": "R:translucent human lungs and airways glowing blue",
    "skin": "R:translucent layers of human skin with soft blue glow, macro",
    "first-visit": "P:a bright modern Korean clinic reception with a smiling receptionist in white, soft blue tones",
    "diagnosis": "P:a Korean doctor in a white coat gently checking the pulse on a patient's wrist, calm consultation room",
    "local": "P:a Seoul neighborhood street in Dongjak at blue hour with ginkgo trees and a subway entrance",
}


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


only = sys.argv[1:] or list(SCENES)
tasks = {}
for cat in only:
    sc = SCENES[cat]
    prompt = f"{sc[2:]}, {PHOTO if sc.startswith('P:') else RENDER}"
    for _ in range(3):
        try:
            tasks[cat] = call("https://api.magnific.com/v1/ai/mystic", {"prompt": prompt, "aspect_ratio": "widescreen_16_9", "resolution": "2k"})["data"]["task_id"]
            break
        except Exception:
            time.sleep(10)
print("created", len(tasks), flush=True)
done = {}
for _ in range(150):
    for cat, tid in tasks.items():
        if cat in done:
            continue
        try:
            d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
        except Exception:
            continue
        if d["status"] == "COMPLETED" and d.get("generated"):
            img = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
            im = Image.open(io.BytesIO(img)).convert("RGB")
            big = im.copy(); big.thumbnail((2000, 1125))
            big.save(f"images/hero-{cat}.jpg", quality=82, optimize=True, progressive=True)
            sm = im.copy(); sm.thumbnail((1024, 576))
            sm.save(f"images/hero-{cat}-sm.jpg", quality=74, optimize=True, progressive=True)
            done[cat] = 1
            print("saved", cat, flush=True)
        elif d["status"] in ("FAILED", "ERROR"):
            done[cat] = 0
            print("FAILED", cat, flush=True)
    if len(done) == len(tasks):
        break
    time.sleep(8)
print("done", sum(done.values()), "of", len(tasks))
