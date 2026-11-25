#!/usr/bin/env python3
"""그림 파일의 가로·세로를 파일 머리만 읽어 알아낸다(PIL 없이 — GitHub Actions 빌드에는 PIL 이 없다).
지원: JPEG, PNG, GIF, WebP(VP8·VP8L·VP8X), SVG(width/height 또는 viewBox). 못 읽으면 None."""
import os, re, struct


def _svg(path):
    head = open(path, encoding="utf-8", errors="replace").read(4000)
    m = re.search(r"<svg\b[^>]*>", head, re.S)
    svg = m.group(0) if m else ""
    w = re.search(r'\swidth="([\d.]+)(px)?"', svg)
    h = re.search(r'\sheight="([\d.]+)(px)?"', svg)
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    if w and h:
        return round(float(w.group(1))), round(float(h.group(1)))
    if vb:
        return round(float(vb.group(1))), round(float(vb.group(2)))
    return None


def _jpeg(f):
    f.seek(2)
    while True:
        b = f.read(1)
        while b and b != b"\xff":
            b = f.read(1)
        while b == b"\xff":
            b = f.read(1)
        if not b:
            return None
        marker = b[0]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        seg = f.read(2)
        if len(seg) < 2:
            return None
        ln = struct.unpack(">H", seg)[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            d = f.read(5)
            h, w = struct.unpack(">HH", d[1:5])
            return w, h
        f.seek(ln - 2, 1)


def size(path):
    try:
        if path.lower().endswith(".svg"):
            return _svg(path)
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                kind = head[12:16]
                if kind == b"VP8 ":
                    w, h = struct.unpack("<HH", head[26:30])
                    return w & 0x3FFF, h & 0x3FFF
                if kind == b"VP8L":
                    b = head[21:25]
                    w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                    h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                    return w, h
                if kind == b"VP8X":
                    w = 1 + int.from_bytes(head[24:27], "little")
                    h = 1 + int.from_bytes(head[27:30], "little")
                    return w, h
                return None
            if head[:2] == b"\xff\xd8":
                return _jpeg(f)
    except Exception:
        pass
    return None


def size_with_fallback(path):
    """파일이 없거나 못 읽으면 같은 이름의 다른 형식(.webp↔.jpg/.jpeg/.png)에서 크기를 가져온다."""
    if os.path.isfile(path):
        wh = size(path)
        if wh:
            return wh
    stem, ext = os.path.splitext(path)
    for alt in (".jpg", ".jpeg", ".png", ".webp"):
        if alt != ext.lower() and os.path.isfile(stem + alt):
            wh = size(stem + alt)
            if wh:
                return wh
    return None
