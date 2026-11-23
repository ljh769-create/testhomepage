#!/usr/bin/env python3
"""매그니픽(Mystic) 2K 대표 이미지 생성: 홈 + 분류 18개. 하늘색·파란색·흰색 통일. 키: ~/magnific-key.txt"""
import io, json, os, sys, time, urllib.request
from PIL import Image
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
STYLE = ("premium cinematic hero image, color palette strictly deep navy blue, sky blue and white with soft luminous highlights, "
         "ultra clean high-end medical brand look, wide 16:9 composition with calm open space in the center for a title, "
         "no text, no letters, no logos, no people")
SCENES = {
    "home": "a soft sunrise above a calm sea of clouds in sky blue and white, a faint crescent moon still visible, hopeful and expansive",
    "insomnia": "a glowing crescent moon above a calm night sky with soft clouds and translucent blue light",
    "mental": "a single warm lantern reflected on a still blue lake at twilight with light mist",
    "neuro": "luminous blue neurons connected by glowing fibers floating in deep blue space, glass-like 3D render",
    "pain": "a translucent glass-like 3D human spine glowing softly in blue on a white to sky-blue gradient background",
    "chuna": "a balanced stack of smooth river stones on still water at dawn in cool blue tones",
    "ultrasound": "concentric blue light ripples spreading like sound waves across deep blue water",
    "accident": "a calm empty road at dawn under a clear sky-blue gradient with soft light",
    "shockwave": "soft blue waves rolling onto a quiet shore at sunrise",
    "digestion": "a white ceramic bowl of warm porridge with rising steam against a soft sky-blue backdrop, bright clean photography",
    "metabolic": "fresh fruits and vegetables on a white table against a sky-blue backdrop, bright clean photography",
    "herbal": "dried medicinal herbs in white ceramic bowls on a pale blue-grey slate surface in soft natural light",
    "women": "white and pale blue hydrangea and peonies in soft window light",
    "pediatric": "small white paper boats floating on calm sky-blue water with soft cloud reflections",
    "respiratory": "a misty pine forest in cool blue morning light giving a feeling of a deep fresh breath",
    "skin": "macro of fresh water droplets on a green leaf with sky-blue bokeh",
    "first-visit": "a bright white clinic hallway with a wooden door open to soft sky-blue light, premium interior",
    "diagnosis": "a traditional wooden herb cabinet with many small drawers lit by soft blue light, premium still life",
    "local": "a Seoul neighborhood at blue hour with a gentle hill and ginkgo trees, calm skyline",
}
def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))
only = sys.argv[1:] or list(SCENES)
tasks = {}
for cat in only:
    r = call("https://api.magnific.com/v1/ai/mystic", {"prompt": f"{SCENES[cat]}, {STYLE}", "aspect_ratio": "widescreen_16_9", "resolution": "2k"})
    tasks[cat] = r["data"]["task_id"]; print("created", cat, flush=True)
done = {}
for _ in range(150):
    for cat, tid in list(tasks.items()):
        if cat in done: continue
        d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
        if d["status"] == "COMPLETED" and d.get("generated"):
            img = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
            im = Image.open(io.BytesIO(img)).convert("RGB"); im.thumbnail((2000, 1125))
            im.save(f"images/hero-{cat}.jpg", quality=82, optimize=True, progressive=True)
            done[cat] = 1; print("saved", cat, im.size, flush=True)
        elif d["status"] in ("FAILED", "ERROR"):
            done[cat] = 0; print("FAILED", cat, d.get("error"), flush=True)
    if len(done) == len(tasks): break
    time.sleep(8)
print("done", sum(1 for v in done.values() if v), "of", len(tasks))
