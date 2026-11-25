#!/bin/bash
# 사용: render_sheet.sh <출력.png> <svg 파일...>  — 2열 모아 보기 한 장으로 렌더
OUT="$1"; shift
HTML="${OUT%.png}.html"
N=$#; ROWS=$(( (N + 1) / 2 )); H=$(( ROWS * 345 + 20 ))
{ echo '<html><body style="margin:0;background:#888"><div style="display:grid;grid-template-columns:600px 600px;gap:8px;padding:8px">'
  for f in "$@"; do echo "<div><img src=\"file://$f\" width=\"600\" height=\"337\"><div style='font:11px sans-serif;color:#fff'>$(basename $f)</div></div>"; done
  echo '</div></body></html>'; } > "$HTML"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="${TMPDIR:-/tmp}/info-svg-chrome" --allow-file-access-from-files --screenshot="$OUT" --window-size=1224,$H "file://$HTML" >/dev/null 2>&1
ls -la "$OUT"
