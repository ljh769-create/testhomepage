"""월 1회 AI 노출 점검 기록·비교 (사용법은 tools/ai_visibility.md).

  python3 tools/ai_visibility.py add <서비스> <질문번호> <mentioned> <cited> [url] [note]
  python3 tools/ai_visibility.py report
기록 파일: content/_ai_visibility.json  {"2026-12": {"chatgpt": {"1": {"mentioned": true, "cited": false, "url": "", "note": ""}}}}
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "content" / "_ai_visibility.json"
SERVICES = ["chatgpt", "perplexity", "gemini", "naver"]
NQ = 10


def load():
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}


def save(d):
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def yes(v):
    return str(v).lower() in ("1", "true", "yes", "y", "o", "예")


def add(args):
    if len(args) < 4:
        sys.exit("사용법: add <서비스> <질문번호> <mentioned> <cited> [url] [note]")
    svc, q = args[0].lower(), str(int(args[1]))
    if svc not in SERVICES:
        sys.exit(f"서비스는 {', '.join(SERVICES)} 중 하나")
    d = load()
    month = date.today().strftime("%Y-%m")
    d.setdefault(month, {}).setdefault(svc, {})[q] = {
        "mentioned": yes(args[2]), "cited": yes(args[3]),
        "url": args[4] if len(args) > 4 else "", "note": " ".join(args[5:]) if len(args) > 5 else ""}
    save(d)
    print(f"{month} {svc} 질문 {q} 기록")


def score(m):
    out = {}
    for svc in SERVICES:
        rows = m.get(svc, {})
        if rows:
            out[svc] = (sum(r["mentioned"] for r in rows.values()), sum(r["cited"] for r in rows.values()), len(rows))
    return out


def report():
    d = load()
    if not d:
        print("아직 기록이 없습니다. tools/ai_visibility.md 를 보고 이번 달 점검을 하세요."); return
    months = sorted(d)
    cur = months[-1]
    prev = months[-2] if len(months) > 1 else None
    sc, sp = score(d[cur]), score(d[prev]) if prev else {}
    print(f"## AI 노출 점검 {cur}" + (f" (지난 기록 {prev})" if prev else ""))
    print("| 서비스 | 이름 나옴 | 출처로 링크 | 지난번 |")
    print("|---|---|---|---|")
    for svc in SERVICES:
        if svc in sc:
            m, c, n = sc[svc]
            p = sp.get(svc)
            print(f"| {svc} | {m}/{n} | {c}/{n} | " + (f"{p[0]}/{p[2]} · {p[1]}/{p[2]}" if p else "-") + " |")
    miss = sorted({int(q) for svc in d[cur].values() for q, r in svc.items() if not r["mentioned"]})
    if miss:
        print(f"\n한 곳이라도 이름이 안 나온 질문: {', '.join(map(str, miss))} → tools/ai_visibility.md '결과로 할 일'")
    wrong = [(s, q, r["note"]) for s, rows in d[cur].items() for q, r in rows.items() if r.get("note")]
    for s, q, n in wrong:
        print(f"- 메모 {s} 질문 {q}: {n}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    add(sys.argv[2:]) if cmd == "add" else report()
