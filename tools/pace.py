#!/usr/bin/env python3
"""자동 작업 속도 조절 (원장님 지시 2026-11-25: "다음 토큰 발행 시간(5시간 한도 리셋)에 맞춰 풀로 다 쓰되, 10분 만에 다 쓰지는 말 것").

원리: Claude 한 번 실행에 걸린 시간 D 만큼 일했으면 D × r 만큼 쉰다(r = 쉬는 비율).
- 한도에 리셋보다 일찍 걸리면(창의 90% 전에 소진) → 너무 빨랐다는 뜻이라 r 을 키운다.
- 한도에 한 번도 안 걸리고 5시간 창이 지나가면 → 덜 쓴 것이라 r 을 줄인다(더 빨리).
이렇게 창마다 스스로 맞춰서, 한도를 리셋 직전에 거의 다 쓰는 속도로 수렴한다.

사용법:
  python3 tools/pace.py gate                      # 지금 돌려도 되면 종료코드 0, 쉬는 중이면 1 (남은 분 출력)
  python3 tools/pace.py record <시작epoch> <끝epoch> <출력파일>   # 실행 결과를 보고 다음 실행 시각·r 조정
  python3 tools/pace.py status                    # 현재 상태 보기
"""
import json, re, sys, time, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT / ".pace.json"
WINDOW = 5 * 3600          # 5시간 한도 창
TARGET = 0.95              # 창의 95% 지점에서 한도에 닿는 것이 목표
R_MIN, R_MAX = 0.0, 8.0
# 2026-11-25 12:10 창: 쉬지 않고 돌려 약 2시간 7분(창의 42%)에 소진 → 일하는 비율 약 0.44 가 맞음 → r ≈ 1.3
DEFAULT = {"r": 1.3, "next_allowed": 0, "last_hit": 0, "last_decay": 0, "log": []}


def load():
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
        return {**DEFAULT, **s}
    except Exception:
        return dict(DEFAULT)


def save(s):
    s["log"] = s.get("log", [])[-30:]
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def note(s, msg):
    s.setdefault("log", []).append(f"{datetime.datetime.now():%m-%d %H:%M} {msg}")


def parse_reset(text, now):
    """'resets 5:10pm (Asia/Seoul)' / 'resets 12pm' → epoch (지금 이후 가장 가까운 그 시각)"""
    m = re.search(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    h = h % 12 + (12 if ap == "pm" else 0)
    base = datetime.datetime.fromtimestamp(now)
    t = base.replace(hour=h, minute=mi, second=0, microsecond=0)
    if t.timestamp() < now - 60:
        t += datetime.timedelta(days=1)
    return t.timestamp()


def gate():
    s, now = load(), time.time()
    # 한도에 한 번도 안 걸린 채로 창 하나(5.5시간)가 지나면 → 덜 쓴 것: 조금 더 빨리
    # 기준: 마지막으로 한도가 풀린 시각(리셋) 또는 마지막 조정 시각. 거기서 창 하나가 다 지나도록 안 걸렸으면 덜 쓴 것.
    ref = max(s.get("last_reset", 0) or s["last_hit"], s["last_decay"])
    if ref and now - ref > WINDOW * 1.05 and s["r"] > R_MIN:
        old = s["r"]; s["r"] = round(max(R_MIN, s["r"] * 0.7), 2); s["last_decay"] = now
        note(s, f"5시간 넘게 한도 안 걸림 → 쉬는 비율 {old} → {s['r']} (더 빨리)")
        save(s)
    if not ref:
        s["last_decay"] = now; save(s)
    if now < s["next_allowed"]:
        print(f"쉬는 중: {int((s['next_allowed'] - now) / 60)}분 뒤 다시 실행 (쉬는 비율 {s['r']})")
        return 1
    return 0


def record(start, end, outfile):
    s, now = load(), time.time()
    out = pathlib.Path(outfile).read_text(encoding="utf-8", errors="ignore") if pathlib.Path(outfile).exists() else ""
    dur = max(60.0, end - start)
    if re.search(r"hit your .*limit|usage limit|rate limit|\b429\b", out, re.I):
        reset = parse_reset(out, now)
        if reset:
            frac = (now - (reset - WINDOW)) / WINDOW   # 창의 몇 % 지점에서 소진됐나
            if s["last_hit"] < reset - WINDOW and 0 < frac < 0.9:   # 이 창에서 처음 걸린 것만 반영
                old = s["r"]
                duty = 1 / (1 + old) * frac / TARGET
                s["r"] = round(min(R_MAX, max(R_MIN, 1 / max(duty, 1e-3) - 1)), 2)
                note(s, f"창의 {frac:.0%} 지점에서 한도 소진 → 쉬는 비율 {old} → {s['r']} (더 천천히)")
            s["next_allowed"] = reset
            s["last_reset"] = reset
        else:
            s["next_allowed"] = now + 15 * 60
        s["last_hit"] = now
        save(s)
        return
    s["next_allowed"] = end + dur * s["r"]
    note(s, f"{int(dur / 60)}분 작업 → {int(dur * s['r'] / 60)}분 쉼")
    save(s)


def status():
    s = load(); now = time.time()
    left = max(0, int((s["next_allowed"] - now) / 60))
    print(f"쉬는 비율 r={s['r']} (일하는 비율 {1 / (1 + s['r']):.0%}), 다음 실행까지 {left}분")
    for line in s.get("log", [])[-8:]:
        print(" ", line)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "gate":
        sys.exit(gate())
    elif cmd == "record":
        record(float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
    else:
        status()
