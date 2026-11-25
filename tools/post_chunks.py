"""여러 글이 든 bulk 파일을 서브에이전트에게 나눠 맡길 때 쓰는 도구(같은 파일을 여럿이 동시에 고치면 덮어쓰기 사고가 남).
extract: content/posts 에서 slug 글 하나를 떼어 <폴더>/<slug>.md(+ .orig 원본)로 저장
merge  : <폴더>/<slug>.md 를 원래 자리에 되돌려 넣음. 그사이 원래 글이 바뀌었으면 건너뜀(남의 수정 보호)
사용: python3 tools/post_chunks.py extract|merge <저장소> <폴더> <slug...>"""
import re, sys
from pathlib import Path
SEP = re.compile(r"\n={5,}\n")

def parts(text):
    # 구분자 위치를 보존하며 나눔
    out, last = [], 0
    for m in SEP.finditer(text):
        out.append((last, m.start())); last = m.end()
    out.append((last, len(text)))
    return out

def find(root, slug):
    for f in sorted((root/'content/posts').glob('*.md')):
        t = f.read_text(encoding='utf-8')
        for a, b in parts(t):
            if re.search(r"^slug:\s*" + re.escape(slug) + r"\s*$", t[a:b], re.M):
                return f, a, b, t
    raise SystemExit(f"없음: {slug}")

cmd, root, out_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
out_dir.mkdir(parents=True, exist_ok=True)
for slug in sys.argv[4:]:
    f, a, b, t = find(root, slug)
    if cmd == 'extract':
        (out_dir/f"{slug}.md").write_text(t[a:b], encoding='utf-8')
        (out_dir/f"{slug}.orig").write_text(t[a:b], encoding='utf-8')
        print("extract", slug, f.name, len(t[a:b]))
    elif cmd == 'merge':
        new = (out_dir/f"{slug}.md").read_text(encoding='utf-8')
        orig = (out_dir/f"{slug}.orig").read_text(encoding='utf-8')
        if t[a:b] != orig:
            print("!! 원래 글이 그사이 바뀜 — 건너뜀:", slug, f.name); continue
        if new == orig:
            print("변경 없음", slug); continue
        # 앞뒤 공백 모양을 원래와 맞춤
        lead = orig[:len(orig)-len(orig.lstrip('\n'))]; trail = orig[len(orig.rstrip('\n')):]
        new = lead + new.strip('\n') + trail
        f.write_text(t[:a] + new + t[b:], encoding='utf-8')
        print("merge", slug, f.name, len(orig), "->", len(new))
