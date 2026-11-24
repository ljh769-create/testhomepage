# -*- coding: utf-8 -*-
"""바탕 화면에 '홈페이지_작업현황.txt'를 만든다. 5분마다 작업 스케줄러가 실행."""
import os, subprocess, glob, time, datetime, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESK = os.path.join(os.path.expanduser('~'), 'OneDrive', '바탕 화면')
OUT = os.path.join(DESK, '홈페이지_작업현황.txt')
now = time.time()

def git(*a):
    try:
        return subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout.strip()
    except Exception:
        return ''

# 최근 10분 안에 바뀐 파일 수 (작업 중인지 판단)
recent = 0
latest = 0
for pat in ['images/info/*.svg', 'content/posts/*.md', 'content/*.json', 'index.html', 'build.py', 'guide/*/*.html']:
    for f in glob.glob(os.path.join(ROOT, pat)):
        m = os.path.getmtime(f)
        latest = max(latest, m)
        if now - m < 600:
            recent += 1

log = git('log', '-8', '--format=%ad  %s', '--date=format:%m/%d %H:%M')
last_ts = git('log', '-1', '--format=%ct')
mins = int((now - int(last_ts)) / 60) if last_ts else -1

info = len(glob.glob(os.path.join(ROOT, 'images/info/post-*.svg')))
posts = 0
try:
    d = json.load(open(os.path.join(ROOT, 'data/posts.json'), encoding='utf-8'))
    posts = len(d) if isinstance(d, list) else len(d.get('posts', []))
except Exception:
    pass

limit = os.path.exists(os.path.join(ROOT, 'tools', '.limit_flag'))
if limit:
    state = '⏸ 사용 한도 때문에 잠시 멈춤 — 한도가 풀리면 15분 안에 자동으로 다시 시작합니다'
elif recent > 0:
    state = f'✅ 작업 중 (최근 10분 동안 파일 {recent}개가 바뀜)'
elif mins >= 0 and mins < 30:
    state = '✅ 작업 중 (30분 안에 배포함)'
else:
    state = f'⚠ 최근 {max(mins,0)}분 동안 변화 없음 — Claude 창에 "시작"이라고 입력해 주세요'

txt = f"""좋은꿈참사랑한의원 홈페이지 작업 현황
확인 시각: {datetime.datetime.now():%Y-%m-%d %H:%M}  (5분마다 자동으로 새로 씁니다)

지금 상태: {state}
마지막 배포: {mins}분 전

발행된 글: {posts}편 / 글 안내 그림: {info}장

최근 배포 8건:
{log}

홈페이지: https://gooddreamclinic.com/
배포 기록(인터넷으로 보기): https://github.com/ljh769-create/testhomepage/commits/main
"""
open(OUT, 'w', encoding='utf-8-sig').write(txt)
