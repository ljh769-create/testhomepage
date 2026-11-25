#!/usr/bin/env python3
"""글 본문 중간 그림(실사 화보 느낌) 만들기.
주문서 content/body-images.json → images/body/<slug>-<번호>.jpg (+ -sm.jpg).
매그니픽(Mystic) 사용. 키: ~/magnific-key.txt. 이미 있는 파일은 건너뛴다.
사용: python3 tools/gen_body_images.py               # 주문서 전체
      python3 tools/gen_body_images.py <slug> <slug>  # 일부 글만
"""
import io, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "images" / "body"
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()

# 참고: 고급 한의원 사이트처럼 '광고 화보' 느낌. 얼굴 없이 손·몸 일부·사물을 가까이, 차분한 톤.
STYLE = ("high-end editorial commercial photography, photorealistic, shot on a medium format camera with an 80mm lens, "
         "minimal and uncluttered composition, soft directional natural window light, gentle shadows, "
         "muted neutral tones of white, warm grey and beige with subtle cool sky-blue accents, "
         "fine natural skin and fabric texture, shallow depth of field, calm and premium mood, "
         "if any hand appears it is anatomically correct with five fingers, no visible face, "
         "no text, no letters, no numbers, no logos, no watermark")


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-magnific-api-key": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


def create(prompt):
    base = {"prompt": prompt, "aspect_ratio": "widescreen_16_9", "resolution": "2k"}
    try:
        return call("https://api.magnific.com/v1/ai/mystic", {**base, "model": "realism"})["data"]["task_id"]
    except urllib.error.HTTPError:  # 'model' 을 안 받는 경우 기본값으로
        return call("https://api.magnific.com/v1/ai/mystic", base)["data"]["task_id"]


def save(url, dest):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    big = im.copy(); big.thumbnail((1600, 900)); big.save(dest, quality=84, optimize=True, progressive=True)
    sm = im.copy(); sm.thumbnail((1024, 576)); sm.save(str(dest)[:-4] + "-sm.jpg", quality=80, optimize=True, progressive=True)


def main():
    plan = json.loads((ROOT / "content" / "body-images.json").read_text(encoding="utf-8"))
    only = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = {}
    for slug, items in plan.items():
        if slug.startswith("_") or (only and slug not in only):
            continue
        for n, it in enumerate(items, 1):
            dest = OUT / f"{slug}-{n}.jpg"
            if dest.exists() or it.get("skip"):  # skip: 여러 번 검수 탈락해 다시 만들지 않기로 한 자리
                continue
            tasks[dest] = create(f"{it['scene']}, {STYLE}")
            print("주문", dest.name, flush=True)
    done = {}
    for _ in range(150):
        for dest, tid in tasks.items():
            if dest in done:
                continue
            d = call(f"https://api.magnific.com/v1/ai/mystic/{tid}")["data"]
            if d["status"] == "COMPLETED" and d.get("generated"):
                save(d["generated"][0], dest); done[dest] = 1; print("저장", dest.name, flush=True)
            elif d["status"] in ("FAILED", "ERROR"):
                done[dest] = 0; print("실패", dest.name, d.get("error"), flush=True)
        if len(done) == len(tasks):
            break
        time.sleep(8)
    print(f"완료 {sum(done.values())} / {len(tasks)}")


if __name__ == "__main__":
    main()
