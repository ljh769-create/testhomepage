#!/usr/bin/env python3
"""매그니픽(Mystic)으로 분류별 배너 일러스트를 만든다. 키는 ~/magnific-key.txt (저장소 밖)."""
import io, json, os, sys, time, urllib.request
from PIL import Image
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
STYLE = ("soft sky-blue and cream watercolor illustration, calm and comforting mood, gentle morning light, "
         "wide empty space on the left side for a title, minimal, clean, no text, no letters, no people, no faces")
SCENES = {
    "insomnia": "a calm crescent moon over a quiet bedroom window at dawn, soft clouds",
    "mental": "a still lake at dusk with a single warm lantern glowing, light mist",
    "neuro": "a calm stream with smooth stones under a clear sky, gentle breeze",
    "pain": "a balanced stack of smooth river stones beside calm water",
    "chuna": "a row of smooth stones aligned along a gently curved path in soft light",
    "ultrasound": "gentle concentric ripples spreading on calm water, soft light",
    "accident": "a quiet tree-lined road at early morning with long soft shadows",
    "shockwave": "soft waves rolling onto a quiet shore at sunrise",
    "digestion": "a warm bowl of rice porridge with gentle steam on a wooden table",
    "metabolic": "fresh seasonal vegetables and fruit on a light wooden table, seen from above",
    "herbal": "dried medicinal herbs in small bowls on handmade paper, warm natural light",
    "women": "soft pastel peonies in a glass vase by a bright window",
    "pediatric": "a small school backpack and pencil case on a sunny bench, no child",
    "respiratory": "fresh morning air with light mist over pine trees, a feeling of a deep breath",
    "skin": "fresh dew drops on green leaves, close up, soft light",
    "first-visit": "an open wooden door letting warm light into a bright quiet reception room",
    "diagnosis": "a traditional wooden herb cabinet with many small drawers in soft light",
    "local": "a quiet Seoul neighborhood street in morning light with ginkgo trees and a gentle hill",
}
def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))
only = sys.argv[1:] or list(SCENES)
tasks = {}
for cat in only:
    r = call("https://api.magnific.com/v1/ai/mystic", {"prompt": f"{SCENES[cat]}, {STYLE}", "aspect_ratio": "widescreen_16_9", "resolution": "1k"})
    tasks[cat] = r["data"]["task_id"]; print("created", cat, flush=True)
done = {}
for _ in range(120):
    for cat, tid in list(tasks.items()):
        if cat in done: continue
        d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
        if d["status"] == "COMPLETED" and d.get("generated"):
            img = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
            im = Image.open(io.BytesIO(img)).convert("RGB"); im.thumbnail((1600, 900))
            im.save(f"images/ai-banner-{cat}.jpg", quality=84, optimize=True, progressive=True)
            done[cat] = 1; print("saved", cat, im.size, flush=True)
        elif d["status"] in ("FAILED", "ERROR"):
            done[cat] = 0; print("FAILED", cat, d.get("error"), flush=True)
    if len(done) == len(tasks): break
    time.sleep(8)
print("done", sum(1 for v in done.values() if v), "of", len(tasks))
