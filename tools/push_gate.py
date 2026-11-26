"""푸시 간격 관리 — 원장님 지시(2026-11-26): "커밋·푸시도 3시간마다".

일 하나가 끝날 때마다 커밋은 그때그때 하되(로컬), 푸시(=배포)는 3시간에 한 번만 한다.
  python3 tools/push_gate.py check   → 푸시할 때면 종료 코드 0, 아직이면 1 (남은 시간 출력)
  python3 tools/push_gate.py done    → 방금 푸시했다고 기록
예외: tools/handoff.md(공유판)만 바뀐 커밋은 배포를 일으키지 않으므로(워크플로 paths-ignore) 언제든 바로 푸시해도 된다.
기록 파일 tools/.last_push 는 컴퓨터마다 따로 둔다(.gitignore).
"""
import pathlib
import sys
import time

INTERVAL = 3 * 60 * 60
STAMP = pathlib.Path(__file__).resolve().parent / ".last_push"


def last():
    try:
        return float(STAMP.read_text().strip())
    except Exception:
        return 0.0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    now = time.time()
    if cmd == "done":
        STAMP.write_text(str(now))
        print("푸시 시각 기록")
    else:
        left = INTERVAL - (now - last())
        if left <= 0:
            print("지금 푸시할 때입니다 (마지막 푸시 후 3시간 지남)")
            sys.exit(0)
        print(f"아직 푸시하지 않습니다 — {int(left // 3600)}시간 {int(left % 3600 // 60)}분 뒤 (그동안 커밋만)")
        sys.exit(1)
