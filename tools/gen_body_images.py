#!/usr/bin/env python3
"""글 본문 중간 그림(실사 화보 느낌) 만들기.
주문서 content/body-images.json → images/body/<slug>-<번호>.jpg (+ -sm.jpg).
매그니픽(Mystic) 사용. 키: ~/magnific-key.txt. 이미 있는 파일은 건너뛴다.
사용: python3 tools/gen_body_images.py               # 주문서 전체
      python3 tools/gen_body_images.py <slug> <slug>  # 일부 글만
"""
import io, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("BODY_OUT") or (ROOT / "images" / "body"))  # 검수 전 그림은 BODY_OUT=images/body-pending 으로 따로 받는다
KEY = open(os.path.expanduser("~/magnific-key.txt")).read().strip()

# 참고: 고급 한의원 사이트처럼 '광고 화보' 느낌. 얼굴 없이 손·몸 일부·사물을 가까이, 차분한 톤.
STYLE = ("high-end editorial commercial photography, photorealistic, shot on a medium format camera with an 80mm lens, "
         "minimal and uncluttered composition, soft directional natural window light, gentle shadows, "
         "muted neutral tones of white, warm grey and beige with subtle cool sky-blue accents, "
         "fine natural skin and fabric texture, shallow depth of field, calm and premium mood, "
         "if any hand appears it is anatomically correct with five fingers, no visible face, "
         "no text, no letters, no numbers, no logos, no watermark")


PEOPLE = re.compile(r"\b(person|people|woman|women|man|men|someone|girl|boy|child|kid|teen|student|worker|driver|rider|commuter|cook|chef|designer|developer|patient|mother|father|mom|dad|parent|grandparent|grandmother|grandfather|elderly|senior|couple|nurse|hairdresser|adult|he|she|his|her|their|figure|silhouette)\b", re.I)
SAFE = re.compile(r"(from behind|back view|cropped|out of frame|hands only|only (the )?hands|close-up of (a |the )?(hand|hands|feet|foot|legs|knee|wrist|back|shoulder|belly|abdomen))", re.I)


def faceless(scene):
    """매그니픽은 '얼굴 금지'를 자주 무시한다(11/25 검수에서 확인). 사람이 나오는 장면은 '손과 물건만 가까이' 구도로 바꾼다."""
    scene = re.sub(r"\b(child|kid|boy|girl|teen(ager)?|student)\b", "adult", scene, flags=re.I)
    # 'no people, no faces' 같은 금지 문구 속 단어는 사람 장면으로 보지 않는다(11/26 사물 장면 교체용)
    if PEOPLE.search(re.sub(r"\bno [a-z]+(, )?", "", scene, flags=re.I)):
        return ("tight close-up still life photograph of only hands and the objects they are using, framed below the shoulders, "
                "no head, no face, no hair, no neck in frame, no bare skin except hands, everyday clothing sleeves only; the scene: " + scene)
    return "still life photograph with no people in the frame: " + scene


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
    auto = ROOT / "content" / "body-images-auto.json"
    if auto.exists():
        for k, v in json.loads(auto.read_text(encoding="utf-8")).items():
            plan.setdefault(k, v)
    only = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = {}
    for slug, items in plan.items():
        if slug.startswith("_") or (only and slug not in only):
            continue
        for n, it in enumerate(items, 1):
            dest = OUT / f"{slug}-{n}.jpg"
            if dest.exists() or it.get("skip") or (ROOT / "images" / "body" / f"{slug}-{n}.jpg").exists():  # skip: 여러 번 검수 탈락해 다시 만들지 않기로 한 자리
                continue
            tasks[dest] = create(f"{faceless(it['scene'])}, {STYLE}")
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
