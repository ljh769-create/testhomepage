#!/usr/bin/env python3
"""sitemap.xml 에서 오늘 바뀐 주소를 IndexNow(네이버·빙 등)에 알립니다.
사용: python tools/indexnow.py [--all]   (--all 이면 사이트맵 전체)"""
import json, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "8c1f3a9d52e74b6a9d0e41c7b3f58a26"
HOST = "gooddreamclinic.com"
today = (datetime.now(timezone.utc) + timedelta(hours=9)).date().isoformat()
xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
pairs = re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", xml)
urls = [u for u, d in pairs if "--all" in sys.argv or d == today]
if not urls:
    print("오늘 바뀐 주소가 없어 알리지 않았습니다."); sys.exit(0)
payload = {"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls}
for endpoint in ("https://searchadvisor.naver.com/indexnow", "https://api.indexnow.org/indexnow"):
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(endpoint, r.status, f"{len(urls)}개 주소")
    except Exception as e:
        print(endpoint, "실패", getattr(e, "code", ""), e)
