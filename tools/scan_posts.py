#!/usr/bin/env python3
"""모든 글(content/posts/*.md)을 훑어 고쳐야 할 곳을 찾는다. 결과: content/_scan.json (파일별 → 글별 문제 목록)
- 의료광고 위험 표현, 진료시간·전화·주소 불일치, 지어낸 교통 정보, 빠진 구역, 너무 짧은 글, 제목 중복 의심"""
import json, os, re, sys, difflib, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "content", "posts")

BANNED = ["완치", "효과", "효능", "보장", "최고", "최초", "유일", "1위", "특효", "100%", "부작용 없", "부작용이 없", "확실히 낫", "즉시 낫",
          "반드시 낫", "후기", "만족도", "가격", "할인", "이벤트", "무료", "명의", "전문병원", "특화", "기적", "근본 치료", "근본적으로 치료"]
OK_CONTEXT = ["효과를 보장하지", "효과를 약속", "효과가 있다고 단정", "후기를 싣지", "가격은", "비용은"]
HOURS_BAD = [r"일요일\s*휴진", r"공휴일\s*휴진", r"토요일\s*0?9:?30\s*[~-]\s*1[34]:?00", r"평일\s*0?9:?00", r"평일\s*[^\n]{0,12}19:00", r"점심[^\n]{0,20}12:30"]
PHONE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")
BUS = re.compile(r"(마을버스|버스)\s*([가-힣A-Za-z]*\s*\d{1,4}[-번]?)")


def split_posts(text):
    for chunk in re.split(r"^=====\s*$", text, flags=re.M):
        m = re.search(r"^slug:\s*(\S+)", chunk, re.M)
        if m:
            yield m.group(1), chunk


out = {}
titles = {}
for f in sorted(os.listdir(D)):
    if not f.endswith(".md"):
        continue
    txt = open(os.path.join(D, f), encoding="utf-8").read()
    for slug, ch in split_posts(txt):
        probs = []
        body = ch
        for w in BANNED:
            for m in re.finditer(re.escape(w), body):
                ctx = body[max(0, m.start() - 25): m.end() + 25].replace("\n", " ")
                if not any(o in ctx for o in OK_CONTEXT):
                    probs.append(f"표현 '{w}': …{ctx}…")
        for pat in HOURS_BAD:
            for m in re.finditer(pat, body):
                probs.append(f"진료시간 확인: …{body[max(0, m.start()-15): m.end()+15].strip()}…")
        for m in PHONE.finditer(body):
            if m.group(0) != "02-815-7510":
                probs.append(f"전화번호 확인: {m.group(0)}")
        for m in BUS.finditer(body):
            if "동작01" not in m.group(0) and "01" not in m.group(2):
                probs.append(f"교통 정보 확인: {m.group(0)}")
        if "먼저 확인" not in body:
            probs.append("빠짐: '먼저 확인이 필요' 구역")
        if len(re.sub(r"\s", "", body)) < 1300:
            probs.append(f"짧음: 본문 {len(re.sub(r'\\s', '', body))}자")
        t = re.search(r"^title:\s*(.+)$", ch, re.M)
        if t:
            titles[slug] = (t.group(1).strip(), f)
        if probs:
            out.setdefault(f, {})[slug] = probs

# 제목 중복 의심(아주 비슷한 제목)
items = list(titles.items())
dups = []
norm = {s: re.sub(r"[^가-힣A-Za-z0-9]", "", t) for s, (t, _) in items}
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        a, b = norm[items[i][0]], norm[items[j][0]]
        if abs(len(a) - len(b)) > 12:
            continue
        r = difflib.SequenceMatcher(None, a, b).quick_ratio()
        if r > 0.86 and difflib.SequenceMatcher(None, a, b).ratio() > 0.86:
            dups.append([items[i][0], items[j][0], items[i][1][0], items[j][1][0]])
res = {"files": out, "dup_titles": dups,
       "summary": {"posts_with_issues": sum(len(v) for v in out.values()), "issues": sum(len(p) for v in out.values() for p in v.values()), "dup_pairs": len(dups)}}
json.dump(res, open(os.path.join(ROOT, "content", "_scan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
c = collections.Counter(p.split(":")[0].split(" '")[0] for v in out.values() for ps in v.values() for p in ps)
print(json.dumps(res["summary"], ensure_ascii=False), dict(c.most_common(12)))
