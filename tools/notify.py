#!/usr/bin/env python3
"""폰 알림 보내기.  사용:  python3 tools/notify.py "메시지"
알림 주소는 저장소 밖 파일 ~/.gooddream_notify 한 줄에 둔다(커밋 금지):
  https://discord.com/api/webhooks/....   → 디스코드 채널로 전송
  ntfy:내가정한주제이름                    → ntfy.sh 앱(폰)으로 전송
파일이 없으면 아무것도 보내지 않고 조용히 끝난다. 환자 정보는 절대 메시지에 넣지 않는다.
"""
import json, os, sys, urllib.request

def send(msg: str) -> bool:
    cfg = os.environ.get("GOODDREAM_NOTIFY", "")
    if not cfg:
        p = os.path.expanduser("~/.gooddream_notify")
        if os.path.isfile(p):
            cfg = open(p, encoding="utf-8").read().strip()
    if not cfg:
        return False
    msg = msg[:1800]
    try:
        if cfg.startswith("https://discord.com/api/webhooks/") or cfg.startswith("https://discordapp.com/api/webhooks/"):
            req = urllib.request.Request(cfg, data=json.dumps({"content": msg}).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "User-Agent": "gooddream-notify"})
        elif cfg.startswith("ntfy:"):
            req = urllib.request.Request("https://ntfy.sh/" + cfg[5:], data=msg.encode("utf-8"),
                                         headers={"Title": "gooddream", "User-Agent": "gooddream-notify"})
        else:
            return False
        urllib.request.urlopen(req, timeout=15).read()
        return True
    except Exception as e:
        print("알림 전송 실패:", e, file=sys.stderr)
        return False

if __name__ == "__main__":
    ok = send(" ".join(sys.argv[1:]) or "테스트 알림")
    sys.exit(0 if ok else 1)
