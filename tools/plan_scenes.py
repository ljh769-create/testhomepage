#!/usr/bin/env python3
"""글 본문 그림 장면 설명을 맥미니 로컬 AI(ollama qwen3:8b)로 초안 작성 → content/body-images.json 에 추가.
원장님 사용량 원칙(2026-11-25): 초안은 로컬 AI, 검수는 Claude(그림을 눈으로 확인).
사용: python3 tools/plan_scenes.py [개수=20] [slug ...]
- 이미 주문이 있는 글은 건너뛴다. before 는 그 글의 실제 ## 소제목 글자에서 고른다(검증, 틀리면 버림).
"""
import json, re, subprocess, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "content" / "body-images-auto.json"  # 내 초안 전용 파일
MAIN = ROOT / "content" / "body-images.json"
NO = ", no people's faces, no text, no letters, no numbers, no logos"

def posts():
    pub = {p["u"].rsplit("/", 1)[-1][:-5] for p in json.loads((ROOT / "data" / "posts.json").read_text(encoding="utf-8"))} if (ROOT / "data" / "posts.json").exists() else None
    out = {}
    for f in sorted(glob.glob(str(ROOT / "content" / "posts" / "*.md"))):
        for blk in re.split(r"\n=====+\n", Path(f).read_text(encoding="utf-8")):
            m = re.search(r"^slug:\s*(\S+)", blk, re.M); t = re.search(r"^title:\s*(.+)", blk, re.M)
            if m and t and (pub is None or m.group(1) in pub):
                out[m.group(1)] = (t.group(1).strip(), [l[3:].strip() for l in blk.splitlines() if l.startswith("## ")])
    return out

def ask(title, heads):
    cand = [h for h in heads if not re.search(r"함께 읽|이런 증상은 먼저|자주 묻", h)][:12]
    prompt = (f"한의원 건강 글 제목: {title}\n소제목 목록:\n" + "\n".join(f"{i+1}. {h}" for i, h in enumerate(cand)) +
              "\n\n이 글 본문에 넣을 사진 3장을 정해라. 각 사진은 서로 다른 소제목 바로 앞에 들어간다. JSON 배열만 출력: "
              '[{"h": 소제목 번호(정수), "scene": "English photo description"}]. '
              "가장 중요한 규칙: 사진만 보고도 글 제목의 주제(증상·상황)가 바로 떠올라야 한다. 그 소제목 내용과도 맞아야 한다. "
              "좋은 예) 턱 여드름 글: 'a bathroom shelf with a gentle cleanser, a soft towel and a small mirror in morning light'; "
              "'a bathroom shelf with a gentle cleanser, a soft towel and a glass of water'. "
              "무릎 계단 글: 'an apartment stairwell with a sturdy handrail and a pair of walking shoes on the landing, soft daylight'. "
              "나쁜 예) 주제와 상관없는 목·어깨, 한약 그릇, 책상 자세 같은 일반 사진. "
              "규칙(11/26 원장님 재검토 뒤): 사람과 몸은 아예 넣지 말고 사물·음식·공간·풍경만으로 주제를 보여 줄 것(얼굴·턱·맨살·손글씨 노트 반복 금지), 아이·아기 금지, 피부 병변 그대로 그리기 금지, 달력·지도·화면 글자 금지, 병원 치료 장면·주사·피·수술·전후 비교 금지, 글자·숫자·상표 금지, 한국의 일상 공간. scene 은 구체적인 영어 한 문장(장소·물건·빛 포함).")
    r = subprocess.run(["/opt/homebrew/bin/ollama", "run", "qwen3:8b", "--think=false", prompt], capture_output=True, text=True, timeout=240)
    m = re.search(r"\[.*\]", r.stdout, re.S)
    arr = json.loads(m.group(0)) if m else []
    items, used = [], set()
    for a in arr:
        try:
            i = int(a["h"]) - 1; h = cand[i]
        except Exception:
            continue
        if i in used or not a.get("scene"):
            continue
        used.add(i)
        key = h[:8] if len(h) >= 4 else h
        items.append({"before": key, "scene": a["scene"].strip().rstrip(".") + NO, "still": True})
    return items[:3]

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20
    only = [a for a in sys.argv[1:] if not a.isdigit()]
    plan = json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {}
    main_plan = json.loads(MAIN.read_text(encoding="utf-8"))
    done = 0
    for slug, (title, heads) in posts().items():
        if (only and slug not in only) or (not only and (slug in plan or slug in main_plan)):
            continue
        if len(heads) < 3 or slug.startswith("dr-"):  # 의료진 소개 글은 실제 사진만(AI 그림 금지)
            continue
        try:
            items = ask(title, heads)
        except Exception as e:
            print("실패", slug, e, flush=True); continue
        if len(items) >= 2:
            plan = json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {}
            plan[slug] = items
            PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            print("주문", slug, [i["before"] for i in items], flush=True); done += 1
        if done >= n:
            break
    print("완료", done)

if __name__ == "__main__":
    main()
