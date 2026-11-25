#!/usr/bin/env python3
"""자동 작업 속도·지능 조절 + 이용률 최적화지수 (원장님 지시 2026-11-25).

지시: "다음 토큰 충전 시간(5시간 한도 리셋)에 맞춰 100% 다 쓰되, 너무 빨리 끝내서 다른 일을 못 보게 하지 말 것.
       지능(생각 깊이)도 거기에 맞춰 쓸 것. 이용률 최적화지수 점수 추적."

원리 (실측 방식):
- `claude -p /usage` 로 실제 사용률을 읽는다(세션 % · 리셋 시각, 이번 주 % · 리셋 시각). 약 3초, 토큰 안 씀.
- 이상적인 사용량 = 창에서 지난 시간 비율(리셋 2.5시간 전이면 50%). 실제가 이보다 앞서 있으면 쉰다, 뒤처져 있으면 일한다.
  → 원장님이 직접 대화하며 쓴 양도 실측에 포함되므로, 자동 작업이 알아서 그만큼 덜 쓴다.
- 이번 주 한도도 같은 방식으로 본다(주간 사용률이 주간 경과 비율보다 앞서면 쉼). 5시간을 매번 100% 쓰다 주간 한도에
  막혀 며칠 멈추는 일을 막기 위해서다.
- 실측을 못 읽으면 예전 방식(걸린 시간 × r 만큼 쉼)으로 돌아간다.

이용률 최적화지수 (5시간 창마다 0~100점):
- 창이 끝날 때(리셋 시각이 바뀔 때) 마지막 실측 사용률 = 점수 (100% 다 썼으면 100점).
- 한도를 너무 일찍 다 써서 남은 시간을 놀았다면 감점: 창의 f 지점에서 소진 → 100 × f / 0.95 점.
- 기록: tools/.pace.json 의 windows, 바탕화면 '이용률_점수.txt', '자동작업_기록.txt'.

지능(생각 깊이 --effort: medium/high/xhigh/max):
- 창 점수가 85점 미만이고 일찍 소진한 것도 아니면(덜 씀) → 한 단계 올림.
- 일찍 소진했거나(창 70% 전) 주간 한도 때문에 자주 쉬었으면 → 한 단계 내림.

사용법:
  python3 tools/pace.py gate      # 지금 돌려도 되면 종료코드 0, 쉬어야 하면 1
  python3 tools/pace.py record <시작epoch> <끝epoch> <출력파일>
  python3 tools/pace.py effort    # 이번 실행에 쓸 생각 깊이
  python3 tools/pace.py status    # 현재 상태 + 최근 점수
"""
import json, re, sys, time, datetime, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT / ".pace.json"
SCORE_TXT = pathlib.Path.home() / "Desktop" / "이용률_점수.txt"
WINDOW = 5 * 3600
WEEK = 7 * 86400
TARGET = 0.99              # 리셋 직전에 100% 소진이 목표
AHEAD_SLACK = 5            # 이상적 사용량보다 5%p 넘게 앞서면 쉼
WEEK_SLACK = 3             # 주간은 3%p
WEEK_GUARD = False         # 주간 한도 보호 끔(원장님 지시 2026-11-25). True 로 바꾸면 주간 사용량이 앞서갈 때 쉼
R_MIN, R_MAX = 0.0, 8.0
EFFORTS = ["medium", "high", "xhigh", "max"]
DEFAULT = {"effort": "xhigh", "r": 0.6, "next_allowed": 0, "hit_until": 0, "last_hit": 0,
           "cur": None, "windows": [], "week_rests": 0, "log": []}


def load():
    try:
        return {**DEFAULT, **json.loads(STATE.read_text(encoding="utf-8"))}
    except Exception:
        return json.loads(json.dumps(DEFAULT))


def save(s):
    s["log"] = s.get("log", [])[-40:]
    s["windows"] = s.get("windows", [])[-60:]
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def note(s, msg):
    s.setdefault("log", []).append(f"{datetime.datetime.now():%m-%d %H:%M} {msg}")


def parse_reset(text, now):
    """'resets 5:10pm' / 'resets Nov 26 at 12:20am' → epoch (지금 이후 가장 가까운 그 시각)"""
    m = re.search(r"resets\s+(?:([A-Z][a-z]{2})\s+(\d{1,2})\s+at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if not m:
        return None
    h = int(m.group(3)) % 12 + (12 if m.group(5).lower() == "pm" else 0)
    mi = int(m.group(4) or 0)
    base = datetime.datetime.fromtimestamp(now)
    if m.group(1):
        mon = datetime.datetime.strptime(m.group(1)[:3].title(), "%b").month
        t = base.replace(month=mon, day=int(m.group(2)), hour=h, minute=mi, second=0, microsecond=0)
        if t.timestamp() < now - 86400 * 30:
            t = t.replace(year=t.year + 1)
        return t.timestamp()
    t = base.replace(hour=h, minute=mi, second=0, microsecond=0)
    if t.timestamp() < now - 60:
        t += datetime.timedelta(days=1)
    return t.timestamp()


def parse_usage(out, now):
    ms = re.search(r"Current session:\s*(\d+)% used\s*·\s*(resets[^\n]*)", out)
    mw = re.search(r"Current week \(all models\):\s*(\d+)% used\s*·\s*(resets[^\n]*)", out)
    if not ms:
        return None
    u = {"t": now, "s": int(ms.group(1)), "s_reset": parse_reset(ms.group(2), now)}
    if mw:
        u["w"], u["w_reset"] = int(mw.group(1)), parse_reset(mw.group(2), now)
    return u if u["s_reset"] else None


def read_usage(now):
    """실측: {'s': 세션%, 's_reset': epoch, 'w': 주간%, 'w_reset': epoch} 또는 None"""
    try:
        out = subprocess.run(["claude", "-p", "/usage"], capture_output=True, text=True, timeout=60,
                             cwd=str(ROOT)).stdout
    except Exception:
        return None
    return parse_usage(out, now)


def score_window(cur):
    used = min(100, cur.get("last_s", 0))
    hit_f = cur.get("hit_f")
    if hit_f is not None and hit_f < 0.95:
        return round(100 * hit_f / 0.95), used
    return used, used


def finish_window(s, cur):
    sc, used = score_window(cur)
    start = datetime.datetime.fromtimestamp(cur["reset"] - WINDOW)
    end = datetime.datetime.fromtimestamp(cur["reset"])
    rec = {"start": f"{start:%m-%d %H:%M}", "end": f"{end:%H:%M}", "score": sc, "used": used,
           "hit_f": cur.get("hit_f"), "effort": s["effort"], "week_rests": s.get("week_rests", 0)}
    s["windows"].append(rec)
    why = f"창 {rec['start']}~{rec['end']}: 이용률 최적화지수 {sc}점 (최종 사용률 {used}%"
    why += f", 창의 {cur['hit_f']:.0%} 지점에서 소진)" if cur.get("hit_f") is not None else ")"
    note(s, why)
    # 지능 조절
    i = EFFORTS.index(s["effort"]) if s["effort"] in EFFORTS else 2
    early = cur.get("hit_f") is not None and cur["hit_f"] < 0.7
    if (early or s.get("week_rests", 0) >= 6) and i > 0:
        s["effort"] = EFFORTS[i - 1]
        note(s, f"{'너무 일찍 소진' if early else '주간 한도 때문에 자주 쉼'} → 지능 {EFFORTS[i]} → {s['effort']}")
    elif sc < 85 and not early and s.get("week_rests", 0) < 2 and i < len(EFFORTS) - 1:
        s["effort"] = EFFORTS[i + 1]
        note(s, f"한도를 덜 씀({sc}점) → 지능 {EFFORTS[i]} → {s['effort']} (더 깊게)")
    s["week_rests"] = 0
    write_score_txt(s)
    return rec


def write_score_txt(s):
    ws = s.get("windows", [])
    if not ws:
        return
    recent = ws[-6:]
    avg = round(sum(w["score"] for w in recent) / len(recent))
    lines = ["이용률 최적화지수 (5시간 창마다 0~100점, 100 = 리셋 직전에 한도를 딱 다 씀)", "",
             f"최근 {len(recent)}개 창 평균: {avg}점   현재 지능: {s['effort']}", ""]
    for w in reversed(ws[-30:]):
        extra = f" · 창의 {w['hit_f']:.0%}에서 소진" if w.get("hit_f") is not None else ""
        lines.append(f"{w['start']}~{w['end']}  {w['score']:>3}점  (사용 {w['used']}%{extra}, 지능 {w['effort']})")
    try:
        SCORE_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def track(s, u):
    """실측 한 건 반영: 창이 바뀌었으면 이전 창 점수 확정."""
    cur = s.get("cur")
    if cur and abs(cur["reset"] - u["s_reset"]) > 600:
        finish_window(s, cur)
        cur = None
    if not cur:
        cur = {"reset": u["s_reset"]}
    cur["last_s"] = max(cur.get("last_s", 0), u["s"])
    cur["last_t"] = u["t"]
    s["cur"] = cur
    s["last_usage"] = u


def decide(s, u, now):
    """실측 기준으로 쉴지 결정. (쉼 여부, 메시지)"""
    elapsed = 1 - (u["s_reset"] - now) / WINDOW
    ideal = max(0.0, min(100.0, elapsed * 100))
    if u["s"] > ideal + AHEAD_SLACK:
        wait = int((u["s"] - ideal - AHEAD_SLACK) / 100 * WINDOW / 60)
        return True, f"쉬는 중: 세션 {u['s']}% 사용, 지금 적정 {ideal:.0f}% → 약 {wait}분 뒤 다시 (지능 {s['effort']})"
    if WEEK_GUARD and "w" in u and u.get("w_reset"):
        w_ideal = (1 - (u["w_reset"] - now) / WEEK) * 100
        if u["w"] > w_ideal + WEEK_SLACK:
            s["week_rests"] = s.get("week_rests", 0) + 1
            return True, f"쉬는 중(주간 한도 보호): 이번 주 {u['w']}% 사용, 지금 적정 {w_ideal:.0f}% (지능 {s['effort']})"
    return False, ""


def gate():
    s, now = load(), time.time()
    if s.get("cur") and now > s["cur"]["reset"] + 60:   # 창이 끝났는데 아직 확정 안 됨
        finish_window(s, s["cur"]); s["cur"] = None
    if now < s.get("hit_until", 0):
        save(s)
        print(f"한도 소진, {int((s['hit_until'] - now) / 60)}분 뒤 리셋 (지능 {s['effort']})")
        return 1
    u = read_usage(now)
    if not u:   # 실측 실패 → 예전 방식
        save(s)
        if now < s["next_allowed"]:
            print(f"쉬는 중(실측 실패, 예전 방식): {int((s['next_allowed'] - now) / 60)}분 뒤")
            return 1
        return 0
    track(s, u)
    rest, msg = decide(s, u, now)
    save(s)
    if rest:
        print(msg)
        return 1
    return 0


def record(start, end, outfile):
    s, now = load(), time.time()
    p = pathlib.Path(outfile)
    out = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    dur = max(60.0, end - start)
    if re.search(r"hit your .*limit|usage limit|rate limit|\b429\b", out, re.I):
        reset = parse_reset(out, now)
        if reset:
            frac = (now - (reset - WINDOW)) / WINDOW
            cur = s.get("cur") or {"reset": reset}
            if abs(cur["reset"] - reset) > 600:
                finish_window(s, cur); cur = {"reset": reset}
            if cur.get("hit_f") is None:
                cur["hit_f"] = round(max(0.0, min(1.0, frac)), 3)
            cur["last_s"] = 100
            s["cur"] = cur
            s["hit_until"] = reset
            # 예전 방식용 r 도 함께 조정(실측 실패 대비)
            if s["last_hit"] < reset - WINDOW and 0 < frac < 0.93:
                duty = 1 / (1 + s["r"]) * frac / TARGET
                s["r"] = round(min(R_MAX, max(R_MIN, 1 / max(duty, 1e-3) - 1)), 2)
            note(s, f"창의 {frac:.0%} 지점에서 한도 소진")
        else:
            s["hit_until"] = now + 15 * 60
        s["last_hit"] = now
        save(s)
        return
    s["next_allowed"] = end + dur * s["r"]   # 실측 실패 시에만 쓰임
    u = read_usage(now)
    if u:
        track(s, u)
        note(s, f"{int(dur / 60)}분 작업 끝 · 세션 {u['s']}% · 이번 주 {u.get('w', '?')}%")
    else:
        note(s, f"{int(dur / 60)}분 작업 끝 (실측 실패)")
    save(s)


def status():
    s = load()
    u = s.get("last_usage") or {}
    line = f"지능 {s['effort']}"
    if u:
        line += f", 세션 {u['s']}% (실측 {datetime.datetime.fromtimestamp(u['t']):%H:%M}), 이번 주 {u.get('w', '?')}%"
    ws = s.get("windows", [])
    if ws:
        recent = ws[-6:]
        line += f", 최적화지수 최근 {round(sum(w['score'] for w in recent) / len(recent))}점"
    print(line)
    for w in ws[-6:]:
        print(f"  {w['start']}~{w['end']} {w['score']}점 (사용 {w['used']}%, 지능 {w['effort']})")
    for l in s.get("log", [])[-6:]:
        print(" ", l)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "gate":
        sys.exit(gate())
    elif cmd == "record":
        record(float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
    elif cmd == "effort":
        e = load().get("effort")
        print(e if e in EFFORTS else "xhigh")
    else:
        status()
