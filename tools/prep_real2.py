#!/usr/bin/env python3
"""2024 의료진 촬영 사진(KakaoTalk_20240920_*)과 2026 치료실·장비 사진(KakaoTalk_20261122_*)을 웹용으로 만든다.
images/real/<이름>.jpg(1600) + <이름>-sm.jpg(1024) + images/thumb/real_<이름>.jpg(640x360)
제외: 화장실, 공사 중 사진, '초음파 리프팅' 포스터가 보이는 사진(의료광고), 워터마크 그림, 만족도·1위 표현 그림, 대화 캡처."""
import os
from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = None

A = "images/KakaoTalk_20240920_100119723{}.jpg"
B = "images/KakaoTalk_20261122_204635836{}.jpg"
def a(n): return A.format("" if n == 0 else f"_{n:02d}")
def b(n): return B.format("" if n == 0 else f"_{n:02d}")

PICK = {
    # 의료진 함께
    "team-tray": a(0), "team-smile": a(1), "team-arms": a(2), "team-herbset": a(3), "team-talk-herb": a(4),
    "team-stand": a(5), "team-tv": a(6), "team-talk": a(7), "team-tray2": a(29),
    # 추나·치료
    "chuna-neck1": a(8), "chuna-shoulder": a(10), "chuna-neck2": a(11), "chuna-hip": a(14), "chuna-leg": a(15),
    "chuna-neck3": a(16), "chuna-neck4": a(17), "chuna-press": a(19), "treat-check": a(23),
    # 상담·설명
    "consult-tablet": a(13), "explain-spine": a(18), "explain-model": a(20), "explain-xray": a(21),
    "explain-monitor1": a(24), "explain-monitor2": a(25), "explain-anatomy": a(26),
    # 한 사람씩
    "doc-wst": a(9), "doc-room": a(12), "doc-stand": a(22), "doc-library": a(27), "doc-smile": a(28),
    # 치료실·장비(2026)
    "room-device1": b(0), "room-device2": b(1), "room-hall1": b(2), "room-bed-hall": b(3), "room-device3": b(4),
    "room-chuna-table": b(5), "room-entrance": b(9), "room-bed1": b(10), "room-bed2": b(11), "room-consult3": b(12),
    "room-bed3": b(13), "room-hall2": b(14), "room-desk": b(18),
}
os.makedirs("images/real", exist_ok=True)
os.makedirs("images/thumb", exist_ok=True)
ok = 0
for name, f in PICK.items():
    if not os.path.exists(f):
        print("없음", f); continue
    im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    big = im.copy(); big.thumbnail((1600, 1600)); big.save(f"images/real/{name}.jpg", quality=80, optimize=True, progressive=True)
    sm = im.copy(); sm.thumbnail((1024, 1024)); sm.save(f"images/real/{name}-sm.jpg", quality=74, optimize=True, progressive=True)
    t = ImageOps.fit(im, (640, 360), centering=(0.5, 0.35)); t.save(f"images/thumb/real_{name}.jpg", quality=74, optimize=True, progressive=True)
    ok += 1
print("done", ok)
