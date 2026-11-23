#!/usr/bin/env python3
"""매그니픽으로 분류별 추가 이미지(카드·본문용)를 만든다. images/pool/<cat>-<n>.jpg. 키: ~/magnific-key.txt"""
import io, json, os, sys, time, urllib.request
from PIL import Image
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
STYLE = ("soft premium photography, palette of sky blue, deep blue and white with gentle light, calm and clean, "
         "16:9 composition, no text, no letters, no logos, no faces")
S = {
 "insomnia": ["a neatly made white bed with a pale blue blanket in soft night light", "a bedside lamp glowing beside a closed book at night", "a window with sheer curtains and blue moonlight on the floor", "a cup of warm herbal tea on a nightstand in blue dusk light"],
 "mental": ["a calm path through a misty blue forest at dawn", "a single paper lantern floating on a still lake", "an open notebook and pen on a quiet desk by a window, blue morning light", "soft clouds drifting over calm water at twilight"],
 "neuro": ["abstract soft blue light trails like gentle nerve paths on a dark navy background", "a calm blue-tinted forest path with sunlight beams", "close-up of hands resting on a white desk near a window, soft blue light", "abstract glowing blue dots connected by thin lines, calm network"],
 "pain": ["a yoga mat and a towel on a light wooden floor in blue morning light", "an ergonomic chair at a tidy white desk by a window", "a pair of walking shoes on a sunlit path with blue sky", "a smooth white pillow and folded towel in soft light"],
 "chuna": ["a clean treatment table with a white sheet in a bright calm room", "a row of smooth white stones aligned in a gentle curve on blue cloth", "soft morning light on a wooden floor with a rolled exercise mat", "a minimal white room with a large window and blue curtains"],
 "ultrasound": ["soft concentric light rings on calm blue water", "a clean modern clinic room with soft blue lighting, no people", "gentle blue sound-wave lines on a white background", "a drop falling into still blue water creating ripples"],
 "accident": ["a quiet city crosswalk at dawn with soft blue light, no cars", "a car seat with a neatly folded blanket, soft daylight", "a calm riverside walking path in the early morning", "a blue sky over a quiet road with tall trees"],
 "shockwave": ["gentle blue waves under a clear sky", "a calm beach with soft foam lines at sunrise", "abstract smooth blue wave shapes", "a quiet harbor with blue water at dawn"],
 "digestion": ["a white teapot and cups on a light wooden table with blue linen", "a bowl of warm soup with steam in soft daylight", "fresh green herbs and a ceramic bowl on white marble", "a simple breakfast of rice and soup on a blue tray"],
 "metabolic": ["a glass of water with lemon slices on a sunny table", "a walking path through a park in clear blue morning", "a balanced meal on a white plate with blue placemat, top view", "a measuring tape and fresh vegetables on a light table"],
 "herbal": ["dried roots and herbs on handmade paper with blue ceramic bowls", "a brass scale with small piles of herbs in soft light", "a clay pot simmering herbs with gentle steam", "wrapped herbal pouches tied with string on a wooden tray"],
 "women": ["a warm cup of tea and a soft blanket on a sofa by a window", "pale blue flowers in a white vase in morning light", "a calm bathroom with white towels and blue tiles", "a cozy reading corner with cushions and soft daylight"],
 "pediatric": ["colorful children's books on a low white shelf in soft light", "a small pair of sneakers by a door with blue sky outside", "crayons and drawing paper on a sunny table", "a kite flying in a clear blue sky over a green field"],
 "respiratory": ["a humidifier releasing soft mist in a bright bedroom", "an open window with fresh air and blue sky, curtains moving", "a pine forest trail in cool morning mist", "a scarf and mask hanging by a door in winter light"],
 "skin": ["a white towel and moisturizer jar on a clean bathroom shelf", "fresh water droplets on a white flower petal", "soft cotton fabric folded on a bed in daylight", "a glass of water and a green leaf on a white surface"],
 "first-visit": ["a bright clinic reception desk with plants and soft blue light, no people", "a notepad and pen for writing symptoms on a clean table", "a calm waiting area with comfortable chairs and a window", "an open door into a sunlit hallway"],
 "diagnosis": ["a wooden herb cabinet with labeled small drawers in soft light", "a traditional pulse cushion on a white table", "an old medical book open on a desk with blue light", "a clean consultation desk with a notebook and tea cup"],
 "local": ["a quiet Seoul alley with ginkgo trees in autumn morning", "a subway entrance in early morning blue light, no people", "a small neighborhood park with benches at dawn", "a Han river view with bridges at blue hour"],
}
def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))
tasks = {}
for cat, scenes in S.items():
    for i, sc in enumerate(scenes, 1):
        name = f"{cat}-{i}"
        if os.path.exists(f"images/pool/{name}.jpg"): continue
        try:
            r = call("https://api.magnific.com/v1/ai/mystic", {"prompt": f"{sc}, {STYLE}", "aspect_ratio": "widescreen_16_9", "resolution": "1k"})
            tasks[name] = r["data"]["task_id"]
        except Exception as e:
            print("create fail", name, e, flush=True)
        time.sleep(0.5)
print("created", len(tasks), flush=True)
done = {}
for _ in range(200):
    for name, tid in list(tasks.items()):
        if name in done: continue
        try: d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
        except Exception: continue
        if d["status"] == "COMPLETED" and d.get("generated"):
            img = urllib.request.urlopen(urllib.request.Request(d["generated"][0], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
            im = Image.open(io.BytesIO(img)).convert("RGB"); im.thumbnail((1400, 788))
            im.save(f"images/pool/{name}.jpg", quality=80, optimize=True, progressive=True); done[name] = 1
        elif d["status"] in ("FAILED", "ERROR"): done[name] = 0
    if len(done) == len(tasks): break
    time.sleep(8)
print("done", sum(done.values()), "of", len(tasks), flush=True)
