#!/usr/bin/env python3
"""윤작가 2차 보정 사진을 웹용으로 줄여 images/real/ 에 넣는다(큰 1600px + 작은 1024px + 썸네일 640x360).
'명확한 효과' 현수막·공진단 효과 포스터가 보이는 사진은 의료광고 문제로 제외한다."""
import os
from PIL import Image, ImageOps

SRC = "images/2차윤작가사진수정복"
PICK = {  # 저장 이름: 원본 파일
    "director-desk": "2차 본원장님3.jpg", "vice-desk": "2차 부원장님4.jpg", "consult": "2차 코로나 후유증.jpg",
    "treat-director1": "본원장님 치료1.jpg", "treat-director2": "본원장님 치료2.jpg", "exam-monitor": "본원장님 치료3.jpg",
    "director-portrait": "본원장님1.jpg", "director-standing": "본원장님4.jpg",
    "treat-vice1": "부원장님 치료1.jpg", "treat-vice2": "부원장님 치료2.jpg", "vice-portrait": "부원장님1.jpg",
    "leg-check": "부원장님5.jpg", "herbs": "약제.jpg", "room-consult1": "진료실1.jpg", "room-consult2": "진료실2.jpg",
    "room-therapy1": "치료실1.jpg", "room-therapy2": "치료실2.jpg", "nose-check": "코로나 검사.jpg",
    "duo1": "투샷1.jpg", "duo2": "투샷2.jpg", "duo4": "투샷4.jpg", "team": "보너스.jpg",
}
os.makedirs("images/real", exist_ok=True)
os.makedirs("images/thumb", exist_ok=True)
for name, f in PICK.items():
    im = ImageOps.exif_transpose(Image.open(os.path.join(SRC, f))).convert("RGB")
    big = im.copy(); big.thumbnail((1600, 1600)); big.save(f"images/real/{name}.jpg", quality=80, optimize=True, progressive=True)
    sm = im.copy(); sm.thumbnail((1024, 1024)); sm.save(f"images/real/{name}-sm.jpg", quality=74, optimize=True, progressive=True)
    t = ImageOps.fit(im, (640, 360), centering=(0.5, 0.4)); t.save(f"images/thumb/real_{name}.jpg", quality=74, optimize=True, progressive=True)
print("done", len(PICK))
