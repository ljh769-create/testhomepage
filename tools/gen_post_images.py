#!/usr/bin/env python3
"""글마다 고유 그림: 실제 사람이 나오는 자연스러운 사진 + 3D 인체 그림. 분류별 30장.
images/post/<cat>-NN.jpg. 키: ~/magnific-key.txt. 있는 파일은 건너뛴다. 개수 제한: python gen_post_images.py 4"""
import io, json, os, sys, time, urllib.request
from PIL import Image

KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()
PHOTO = ("natural candid lifestyle photography, realistic Korean person, soft natural window light, "
         "subtle sky-blue and white color grading, shallow depth of field, high-end Korean clinic advertisement look, "
         "anatomically correct hands, no text, no letters, no logos")
RENDER = ("high-end 3D medical illustration, translucent glass-like anatomy glowing in sky blue, "
          "deep navy background with soft light, clean and elegant, no text, no letters, no labels")
WHO = ["a Korean woman in her 30s", "a Korean man in his 40s", "a Korean woman in her 50s",
       "a Korean man in his 60s", "a Korean young adult in their 20s"]
KID = ["a Korean mother and her young child", "a Korean father and his elementary-school child",
       "a Korean grandmother and grandchild", "a Korean teenage student", "a Korean young child with a parent"]
ANGLES = ["front view", "side view", "close-up", "three-quarter view", "wide view"]
S = {
    "insomnia": ["{w} sitting on the edge of a bed at night unable to sleep, hand on forehead", "{w} lying awake in bed looking at the ceiling in blue night light", "{w} yawning tiredly at a desk in the morning", "R:a translucent human brain with soft glowing waves", "{w} holding a warm cup of tea before bed in a calm bedroom", "{w} stretching gently beside a bright window after waking"],
    "mental": ["{w} sitting by a window looking pensive", "{w} taking a slow deep breath with eyes closed in a calm room", "{w} writing in a journal at a quiet cafe table", "R:a translucent human head with glowing calm neural lights", "{w} walking alone in a quiet park in the morning", "{w} resting their head on their hand at an office desk, tired"],
    "neuro": ["{w} pressing their temples with a headache at work", "{w} rubbing tired eyes in front of a laptop", "{w} holding their head feeling dizzy while standing", "R:glowing blue neurons connected by fibers", "{w} shaking a numb hand at a desk", "{w} with a hand on the back of the neck looking tense"],
    "pain": ["{w} holding the lower back while standing up from a chair", "{w} rubbing a stiff shoulder at a desk", "{w} holding a sore knee while climbing stairs", "R:a translucent human spine and pelvis glowing blue", "{w} stretching the neck slowly in a bright room", "{w} massaging a sore wrist after typing"],
    "chuna": ["{w} with poor posture hunched at a laptop", "{w} checking posture in a mirror", "{w} lying face down on a clean treatment table with a white sheet, relaxed", "R:a translucent human spine with aligned vertebrae glowing blue", "{w} doing a gentle back stretch on a mat", "{w} sitting upright on an ergonomic chair"],
    "ultrasound": ["{w} pointing to a sore shoulder in a bright clinic room", "{w} sitting on a clean examination couch waiting calmly", "{w} holding an aching elbow", "R:a translucent shoulder joint with tendons glowing blue", "{w} with a hand on a sore heel sitting on a bench", "{w} looking at a medical monitor screen with interest"],
    "accident": ["{w} holding the back of the neck after a car ride", "{w} sitting in a parked car looking shaken", "{w} rubbing their lower back beside a car", "R:a translucent cervical spine glowing blue", "{w} resting on a sofa with a neck pillow", "{w} walking carefully with a hand on the hip"],
    "shockwave": ["{w} holding a sore heel in the morning", "{w} rubbing an aching elbow", "{w} with a hand on a stiff shoulder", "R:a translucent foot and heel bones glowing blue", "{w} stretching the calf against a wall", "{w} sitting and massaging a knee"],
    "digestion": ["{w} holding their stomach after a meal at a dining table", "{w} eating a warm bowl of porridge slowly", "{w} with a hand on the chest feeling heartburn", "R:a translucent human stomach and intestines glowing blue", "{w} drinking warm water in a bright kitchen", "{w} looking uncomfortable after a late-night snack"],
    "metabolic": ["{w} stepping on a bathroom scale looking thoughtful", "{w} preparing a healthy salad in a bright kitchen", "{w} walking briskly in a park in the morning", "R:translucent blood vessels and heart glowing blue", "{w} measuring their waist with a tape measure", "{w} checking blood pressure at home with a cuff"],
    "herbal": ["{w} holding a pouch of herbal medicine at home", "{w} drinking warm herbal tea from a ceramic cup", "dried medicinal herbs in bowls on handmade paper", "R:translucent human body silhouette with soft blue energy flow", "a clay pot with herbal medicine and steam", "{w} reading a medication instruction note at a table"],
    "women": ["{w} holding a hot water bottle on the lower belly on a sofa", "{w} resting with a warm blanket feeling tired", "{w} fanning themselves during a hot flash", "R:a translucent female pelvis glowing softly in blue", "{w} doing gentle yoga at home", "{w} smiling calmly with a cup of tea by a window"],
    "pediatric": ["{w} reading a book together on a sofa", "{w} at a dining table with a small bowl of rice", "{w} at bedtime with the child yawning", "R:a translucent child silhouette with soft blue light", "{w} doing homework together at a desk", "{w} walking to school with a backpack"],
    "respiratory": ["{w} sneezing into a tissue at home", "{w} coughing with a scarf in cold weather", "{w} breathing in fresh air by an open window", "R:translucent human lungs glowing blue", "{w} using a humidifier in a bedroom", "{w} holding a mug of warm tea with a stuffy nose"],
    "skin": ["{w} applying moisturizer to dry hands", "{w} scratching an itchy arm", "{w} looking at their skin in a bathroom mirror", "R:translucent layers of human skin glowing blue", "{w} washing their face gently", "{w} with a soft towel after a shower"],
    "first-visit": ["{w} filling out a form at a bright clinic reception desk", "{w} talking with a doctor in a white coat across a desk", "{w} sitting in a calm clinic waiting area", "R:a soft blue abstract clinic hallway with light", "{w} arriving at a clinic entrance holding an umbrella", "{w} reading a small notebook of symptoms before a visit"],
    "diagnosis": ["a Korean doctor in a white coat gently checking the pulse on the wrist of {w}", "{w} showing the tongue to a doctor in a white coat", "a Korean doctor in a white coat listening to {w} in a consultation room", "R:a translucent human body with glowing blue meridian lines", "a traditional wooden herb cabinet in a bright clinic", "{w} answering questions in a calm consultation room"],
    "local": ["{w} walking on a Seoul neighborhood street with ginkgo trees", "{w} coming out of a subway station in the morning", "{w} sitting on a bench in a small neighborhood park", "R:a soft blue stylized city map at night", "{w} waiting at a bus stop on a calm street", "{w} looking at the Han river at sunset"],
}


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


jobs = []
for cat, subs in S.items():
    n = 0
    who = KID if cat == "pediatric" else WHO
    for s in subs:
        for w in who:
            n += 1
            name = f"{cat}-{n:02d}"
            if os.path.exists(f"images/post/{name}.jpg"):
                continue
            if s.startswith("R:"):
                prompt = f"{s[2:]}, {ANGLES[(n - 1) % 5]}, {RENDER}"
            else:
                prompt = f"{s.format(w=w)}, {PHOTO}"
            jobs.append((name, prompt))
limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
if limit:
    jobs = jobs[:limit]
print("to make", len(jobs), flush=True)
ok = fail = 0
for b in range(0, len(jobs), 20):
    batch = jobs[b:b + 20]
    tasks = {}
    for name, prompt in batch:
        for attempt in range(3):
            try:
                tasks[name] = call("https://api.magnific.com/v1/ai/mystic",
                                   {"prompt": prompt, "aspect_ratio": "widescreen_16_9", "resolution": "1k"})["data"]["task_id"]
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
