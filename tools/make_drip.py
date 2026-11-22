#!/usr/bin/env python3
"""content/drip.json 을 만듭니다. 지금 바로 공개할 글(LIVE)을 뺀 나머지를 분류가 골고루 섞이게 줄 세워
하루 site.json 의 drip.per_day 편씩 자동 발행되게 합니다. 불면·대사 글은 비중을 두 배로 둡니다."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = """knee-stairs-down metabolic-before-visit first-visit-guide shockwave-guide ultrasound-guide chuna-correction-guide
insomnia-guide digestion-guide joint-pain-ultrasound waking-at-dawn bloating-after-meals shoulder-pain-ultrasound
accident-neck-back-pain night-urination-sleep heartburn-acid-reflux before-sleep-reading guilt-after-eating
reading-checkup-results snoring-sleep-apnea salty-food-blood-pressure how-to-keep-sleep-diary prediabetes-meal-order
how-to-note-symptoms prepare-medication-list sleep-onset-difficulty late-night-eating
vivid-dreams-unrefreshed burnout-exhaustion""".split()

posts = []
for f in sorted((ROOT / "content" / "posts").glob("*.md")):
    for part in re.split(r"\n={5,}\n", f.read_text(encoding="utf-8").replace("\r\n", "\n").strip()):
        m = re.search(r"^slug:\s*(.+)$", part, re.M)
        c = re.search(r"^category:\s*(.+)$", part, re.M)
        if m and c:
            posts.append((m.group(1).strip(), c.group(1).strip()))

queue = {}
for slug, cat in posts:
    if slug not in LIVE:
        queue.setdefault(cat, []).append(slug)

cycle = ["insomnia", "metabolic", "pain", "insomnia", "metabolic", "digestion", "insomnia", "metabolic", "neuro",
         "women", "insomnia", "metabolic", "pediatric", "accident", "respiratory", "skin", "mental", "chuna",
         "shockwave", "ultrasound", "first-visit"]
order = []
while any(queue.values()):
    for cat in cycle:
        if queue.get(cat):
            order.append(queue[cat].pop(0))
(ROOT / "content" / "drip.json").write_text(json.dumps({"order": order}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"즉시 공개 {len(posts) - len(order)}편, 예약 {len(order)}편")
