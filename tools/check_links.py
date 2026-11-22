#!/usr/bin/env python3
"""사이트 안의 내부 링크(href/src)가 실제 파일을 가리키는지 검사합니다. 끊긴 링크가 있으면 목록을 보여 주고 종료 코드 1."""
import re, sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", ".claude", ".agents", "naver-blog", "node_modules", "tools", "content", "_site"}
pages = [p for p in ROOT.rglob("*.html") if not (set(p.relative_to(ROOT).parts) & SKIP)]
bad = []
for p in pages:
    src = p.read_text(encoding="utf-8")
    for attr, url in re.findall(r"""(href|src)=['"]([^'"]+)['"]""", src):
        if re.match(r"^(https?:|mailto:|tel:|#|data:|javascript:)", url) or url.startswith("{"):
            continue
        path_part = unquote(url.split("#")[0].split("?")[0])
        target = ((ROOT / path_part.lstrip("/")) if path_part.startswith("/") else (p.parent / path_part)).resolve()
        if not url.split("#")[0]:
            continue
        if not target.exists():
            bad.append((str(p.relative_to(ROOT)), url))
# comfort.js 의 이동 링크
js = (ROOT / "comfort.js").read_text(encoding="utf-8")
for url in re.findall(r'h:"([^"#]+\.html)"', js):
    if not (ROOT / url).exists():
        bad.append(("comfort.js", url))
print(f"검사한 페이지 {len(pages)}개, 끊긴 링크 {len(bad)}개")
for page, url in bad[:40]:
    print("  ", page, "→", url)
sys.exit(1 if bad else 0)
