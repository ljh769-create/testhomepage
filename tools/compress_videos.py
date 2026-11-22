#!/usr/bin/env python3
"""images/output/*.mp4 를 웹용(720p)으로 압축하고 대표 이미지를 만듭니다. 결과: 두 번째 인자 폴더의 vNN.mp4, NN.jpg 와 index.json"""
import glob, json, os, subprocess, sys
import imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe()
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
files = sorted(glob.glob('images/**/*.mp4', recursive=True), key=os.path.getsize)
idx = []
for n, f in enumerate(files, 1):
    key = f"{n:02d}"
    mp4, jpg = f"{out}/v{key}.mp4", f"{out}/{key}.jpg"
    link = f"{out}/src{key}.mp4"   # ffmpeg 가 한글 경로를 못 읽어서 영문 이름의 하드링크를 쓴다
    if not os.path.exists(link):
        try: os.link(f, link)
        except OSError:
            import shutil; shutil.copy(f, link)
    if not os.path.exists(mp4):
        subprocess.run([ff, '-y', '-i', link, '-vf', 'scale=-2:720', '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast',
                        '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', mp4], capture_output=True)
    if not os.path.exists(jpg):
        subprocess.run([ff, '-y', '-ss', '4', '-i', mp4, '-frames:v', '1', '-vf', 'scale=640:-2', '-q:v', '4', jpg], capture_output=True)
    if os.path.exists(link): os.remove(link)
    idx.append({'key': key, 'src': os.path.basename(f), 'mb': os.path.getsize(mp4) // 2**20 if os.path.exists(mp4) else 0})
    print(key, os.path.basename(f), idx[-1]['mb'], 'MB', flush=True)
    json.dump(idx, open(f"{out}/index.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
