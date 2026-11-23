#!/usr/bin/env python3
"""항목별 아이콘(SVG)을 icons/ 폴더에 만듭니다. 색을 바꾸려면 아래 팔레트만 고치고 다시 실행하세요."""
from pathlib import Path

N, B, L, Y, D, W, T = "#1F3552", "#4672AD", "#90B2DD", "#FBE78A", "#E5C23E", "#FFFFFF", "#E8F0F9"
OUT = Path(__file__).resolve().parent.parent / "icons"
OUT.mkdir(exist_ok=True)

ICONS = {
    # ---- 진료 분야 ----
    "insomnia": f'<circle cx="44" cy="52" r="24" fill="{Y}" stroke="{D}" stroke-width="2"/><circle cx="57" cy="44" r="21" fill="{T}"/>'
                f'<path d="M72 22l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5z" fill="{D}"/><path d="M24 26l1.6 4 4 1.6-4 1.6-1.6 4-1.6-4-4-1.6 4-1.6z" fill="{L}"/>'
                f'<path d="M64 58h11l-11 13h11" stroke="{N}" stroke-width="3.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "metabolic": f'<path d="M36 28c-4 4 4 6 0 10M48 24c-4 4 4 6 0 10M60 28c-4 4 4 6 0 10" stroke="{L}" stroke-width="3.5" fill="none" stroke-linecap="round"/>'
                 f'<path d="M24 52a24 18 0 0 1 48 0z" fill="{W}" stroke="{L}" stroke-width="2"/><path d="M16 52h64c0 18-13 30-32 30S16 70 16 52z" fill="{B}"/>'
                 f'<path d="M24 62h48" stroke="{Y}" stroke-width="3.5" stroke-linecap="round"/><path d="M72 28c11 0 15 8 13 17-10 0-17-5-13-17z" fill="{Y}" stroke="{D}" stroke-width="1.6"/>',
    "pain": f'<g transform="translate(48 48) scale(.64) translate(-48 -48)"><path d="M48 8l9 17 19-6-8 18 18 9-19 8 7 19-19-9-7 18-8-17-19 8 6-19-17-9 18-8-7-18 18 6z" fill="{Y}"/></g>'
            f'<g transform="rotate(-35 48 48)"><rect x="8" y="40" width="42" height="16" rx="8" fill="{B}"/><rect x="46" y="40" width="42" height="16" rx="8" fill="{L}"/><circle cx="48" cy="48" r="12" fill="{W}" stroke="{N}" stroke-width="3.2"/></g>',
    "shockwave": f'<circle cx="24" cy="48" r="11" fill="{D}"/><circle cx="24" cy="48" r="6" fill="{Y}"/>'
                 f'<path d="M42 34a20 20 0 0 1 0 28" stroke="{N}" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
                 f'<path d="M54 24a34 34 0 0 1 0 48" stroke="{B}" stroke-width="4.5" fill="none" stroke-linecap="round" opacity=".85"/>'
                 f'<path d="M66 14a48 48 0 0 1 0 68" stroke="{L}" stroke-width="4.5" fill="none" stroke-linecap="round" opacity=".8"/>',
    "ultrasound": f'<path d="M48 44L16 86h64z" fill="{L}" opacity=".6"/><path d="M48 44L30 86M48 44v42M48 44l18 42" stroke="{W}" stroke-width="2.4" opacity=".9"/>'
                  f'<rect x="37" y="8" width="22" height="36" rx="10" fill="{N}"/><rect x="39" y="38" width="18" height="9" rx="3.5" fill="{Y}"/>',
    "chuna": f'<rect x="39" y="10" width="18" height="13" rx="6.5" fill="{L}" stroke="{B}" stroke-width="2"/><rect x="39" y="27" width="18" height="13" rx="6.5" fill="{L}" stroke="{B}" stroke-width="2"/>'
             f'<rect x="39" y="44" width="18" height="13" rx="6.5" fill="{L}" stroke="{B}" stroke-width="2"/><rect x="39" y="61" width="18" height="13" rx="6.5" fill="{L}" stroke="{B}" stroke-width="2"/>'
             f'<rect x="4" y="44" width="34" height="20" rx="10" fill="{N}"/><rect x="58" y="44" width="34" height="20" rx="10" fill="{N}"/>'
             f'<path d="M42 48l4 6-4 6M54 48l-4 6 4 6" stroke="{D}" stroke-width="3.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="48" cy="84" r="4" fill="{Y}"/>',
    "digestion": f'<path d="M34 10v16" stroke="{N}" stroke-width="7" stroke-linecap="round"/>'
                 f'<path d="M34 24c-4 4-6 8-8 14-6 18 4 38 24 42 20 4 32-8 30-24-1-10-8-14-16-16-8-2-12-6-12-16z" fill="{L}" stroke="{B}" stroke-width="3.2" stroke-linejoin="round"/>'
                 f'<path d="M40 52c6 4 12 4 18 0" stroke="{B}" stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="44" cy="64" r="3.6" fill="{Y}"/><circle cx="58" cy="68" r="3.6" fill="{Y}"/><circle cx="36" cy="60" r="3" fill="{Y}"/><path d="M82 28a10 10 0 0 1-10 10" stroke="{N}" stroke-width="5" fill="none" stroke-linecap="round"/>',
    "accident": f'<path d="M14 64V53c0-4 3-8 8-9l8-14c2-4 5-6 9-6h14c4 0 7 2 9 6l8 14c5 1 8 5 8 9v11z" fill="{B}"/><path d="M33 44l5-11h20l5 11z" fill="{T}"/>'
                f'<circle cx="30" cy="66" r="9.5" fill="{N}"/><circle cx="30" cy="66" r="3.5" fill="{W}"/><circle cx="68" cy="66" r="9.5" fill="{N}"/><circle cx="68" cy="66" r="3.5" fill="{W}"/>'
                f'<circle cx="80" cy="55" r="4" fill="{Y}"/><path d="M6 50h11M3 60h11" stroke="{L}" stroke-width="3.4" stroke-linecap="round"/>',
    "women": f'<circle cx="46" cy="38" r="16" fill="none" stroke="{N}" stroke-width="6"/><path d="M46 54v26M34 68h24" stroke="{N}" stroke-width="6" stroke-linecap="round"/>'
             f'<path d="M72 22c0-5 7-6 8-1 1-5 8-4 8 1 0 6-8 11-8 11s-8-5-8-11z" fill="{D}"/>',
    "pediatric": f'<rect x="60" y="12" width="17" height="70" rx="5" fill="{B}"/><path d="M60 26h9M60 38h6M60 50h9M60 62h6M60 74h9" stroke="{W}" stroke-width="2.6" stroke-linecap="round"/>'
                 f'<path d="M32 84V50" stroke="{B}" stroke-width="5" stroke-linecap="round"/><path d="M32 56c-12 0-18-8-18-19 12 0 18 7 18 19z" fill="{Y}" stroke="{D}" stroke-width="1.6"/><path d="M32 48c10 0 16-6 16-17-10 0-16 6-16 17z" fill="{L}"/>',
    "respiratory": f'<path d="M48 12v24" stroke="{N}" stroke-width="5" stroke-linecap="round"/><path d="M48 34c-6 7-8 8-13 11M48 34c6 7 8 8 13 11" stroke="{N}" stroke-width="4" fill="none" stroke-linecap="round"/>'
                   f'<path d="M38 40c-12 2-21 20-21 35 0 7 6 9 11 6 9-4 13-11 13-22z" fill="{L}" stroke="{B}" stroke-width="2.4"/><path d="M58 40c12 2 21 20 21 35 0 7-6 9-11 6-9-4-13-11-13-22z" fill="{L}" stroke="{B}" stroke-width="2.4"/><circle cx="26" cy="64" r="3.4" fill="{Y}"/><circle cx="70" cy="64" r="3.4" fill="{Y}"/>',
    "skin": f'<path d="M46 12C32 33 24 43 24 56a22 22 0 0 0 44 0c0-13-8-23-22-44z" fill="{L}" stroke="{B}" stroke-width="3"/><path d="M36 57a10 10 0 0 0 8 10" stroke="{W}" stroke-width="4" fill="none" stroke-linecap="round"/>'
            f'<path d="M74 18l2.4 6 6 2.4-6 2.4-2.4 6-2.4-6-6-2.4 6-2.4z" fill="{D}"/><path d="M80 52l1.6 4 4 1.6-4 1.6-1.6 4-1.6-4-4-1.6 4-1.6z" fill="{Y}"/>',
    "neuro": f'<circle cx="37" cy="50" r="22" fill="{L}"/><circle cx="59" cy="50" r="22" fill="{L}"/><path d="M48 30v40" stroke="{B}" stroke-width="3"/>'
             f'<path d="M26 44c5 0 7 5 12 5M26 58c5 0 7-5 12-5M58 42c5 0 7 5 12 5M58 56c5 0 7-5 12-5" stroke="{B}" stroke-width="3" fill="none" stroke-linecap="round"/>'
             f'<circle cx="18" cy="22" r="4" fill="{Y}"/><circle cx="48" cy="14" r="3.4" fill="{D}"/><circle cx="78" cy="22" r="4" fill="{Y}"/>',
    "mental": f'<path d="M24 52a12 12 0 0 1 4-23 16 16 0 0 1 31-2 13 13 0 0 1 9 25z" fill="{W}" stroke="{L}" stroke-width="2.4"/><circle cx="74" cy="22" r="9" fill="{D}"/>'
              f'<path d="M48 86c-14-9-21-17-21-25 0-6 5-10 10-10 4 0 8 3 11 7 3-4 7-7 11-7 5 0 10 4 10 10 0 8-7 16-21 25z" fill="{B}"/>',
    "first-visit": f'<rect x="21" y="16" width="54" height="68" rx="9" fill="{W}" stroke="{B}" stroke-width="3.2"/><rect x="35" y="9" width="26" height="15" rx="5.5" fill="{N}"/>'
                   f'<path d="M31 40h34M31 52h22M31 64h16" stroke="{L}" stroke-width="4" stroke-linecap="round"/><path d="M54 66l6 6 12-14" stroke="{D}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    # ---- 진료 순서 ----
    "reception": f'<rect x="12" y="52" width="72" height="28" rx="9" fill="{B}"/><path d="M32 50a16 16 0 0 1 32 0z" fill="{Y}" stroke="{D}" stroke-width="2"/><rect x="28" y="50" width="40" height="6" rx="3" fill="{D}"/><circle cx="48" cy="30" r="3.6" fill="{D}"/>',
    "consult": f'<rect x="10" y="16" width="50" height="34" rx="13" fill="{B}"/><path d="M22 48l-6 14 16-10z" fill="{B}"/><rect x="36" y="40" width="50" height="34" rx="13" fill="{W}" stroke="{L}" stroke-width="2.6"/><path d="M74 72l6 12-16-9z" fill="{W}" stroke="{L}" stroke-width="2.6" stroke-linejoin="round"/>'
               f'<circle cx="25" cy="33" r="3.4" fill="{Y}"/><circle cx="35" cy="33" r="3.4" fill="{Y}"/><circle cx="45" cy="33" r="3.4" fill="{Y}"/>',
    "exam": f'<path d="M30 16v22a18 18 0 0 0 36 0V16" stroke="{N}" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M48 56v10a12 12 0 0 0 24 0" stroke="{N}" stroke-width="5" fill="none" stroke-linecap="round"/>'
            f'<circle cx="72" cy="62" r="10" fill="{Y}" stroke="{D}" stroke-width="3"/><circle cx="30" cy="14" r="5" fill="{B}"/><circle cx="66" cy="14" r="5" fill="{B}"/>',
    "treat": f'<path d="M62 36L78 20" stroke="{D}" stroke-width="10" stroke-linecap="round"/><path d="M62 36L20 78" stroke="{B}" stroke-width="3.4" stroke-linecap="round"/>'
             f'<circle cx="20" cy="78" r="9" fill="none" stroke="{L}" stroke-width="2.4"/><circle cx="20" cy="78" r="15" fill="none" stroke="{L}" stroke-width="2" opacity=".6"/><circle cx="76" cy="72" r="5" fill="{Y}"/><circle cx="26" cy="22" r="4" fill="{L}"/>',
    "home": f'<path d="M16 48L48 22l32 26v32H16z" fill="{B}"/><path d="M10 50L48 16l38 34" stroke="{N}" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/><rect x="39" y="56" width="18" height="24" rx="5" fill="{Y}"/><circle cx="52" cy="68" r="1.8" fill="{D}"/>',
    # ---- 기타 ----
    "pin": f'<path d="M48 10c-14 0-25 11-25 25 0 19 25 48 25 48s25-29 25-48c0-14-11-25-25-25z" fill="{B}"/><circle cx="48" cy="35" r="10.5" fill="{Y}"/>',
    "phone": f'<path d="M22 18c0 31 23 54 54 54l5-15-17-9-9 9c-8-4-15-11-19-19l9-9-9-17z" fill="{B}"/><path d="M58 18a24 24 0 0 1 20 20M58 30a12 12 0 0 1 8 8" stroke="{D}" stroke-width="4.5" fill="none" stroke-linecap="round"/>',
    "clock": f'<circle cx="48" cy="48" r="31" fill="{W}" stroke="{B}" stroke-width="5"/><path d="M48 28v21l13 8" stroke="{N}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="48" cy="49" r="4" fill="{D}"/>',
    "warm": f'<path d="M48 12c4 14 20 22 20 42a20 20 0 0 1-40 0c0-12 6-16 10-24 2 6 6 8 10 8-2-10 0-18 0-26z" fill="{D}"/><path d="M48 38c3 9 12 13 12 24a12 12 0 0 1-24 0c0-8 5-10 8-16 1 4 3 5 4 5z" fill="{Y}"/>',
    "water": f'<path d="M34 14C24 28 18 36 18 46a16 16 0 0 0 32 0c0-10-6-18-16-32z" fill="{L}" stroke="{B}" stroke-width="2.6"/><path d="M64 38C57 48 53 54 53 61a11 11 0 0 0 22 0c0-7-4-13-11-23z" fill="{B}"/><path d="M28 48a7 7 0 0 0 6 6" stroke="{W}" stroke-width="3.4" fill="none" stroke-linecap="round"/><circle cx="76" cy="24" r="4" fill="{Y}"/>',
    "tongue": f'<path d="M20 22h56c0 8-2 14-6 20-2 20-10 38-22 38S28 62 26 42c-4-6-6-12-6-20z" fill="{L}" stroke="{B}" stroke-width="3" stroke-linejoin="round"/><path d="M48 30v34" stroke="{B}" stroke-width="3.4" stroke-linecap="round"/><circle cx="36" cy="46" r="3" fill="{Y}"/><circle cx="60" cy="50" r="3" fill="{Y}"/><circle cx="40" cy="62" r="2.6" fill="{Y}"/>',
    "moon": f'<circle cx="44" cy="50" r="26" fill="{Y}" stroke="{D}" stroke-width="2.4"/><circle cx="58" cy="42" r="23" fill="{N}"/><path d="M70 18l2.6 6.4 6.4 2.6-6.4 2.6-2.6 6.4-2.6-6.4-6.4-2.6 6.4-2.6z" fill="{Y}"/>',
    "herbal": f'<path d="M20 52h56c0 18-12 30-28 30S20 70 20 52z" fill="{B}"/><path d="M16 52h64" stroke="{N}" stroke-width="4" stroke-linecap="round"/><path d="M48 50V26" stroke="{N}" stroke-width="3.6" stroke-linecap="round"/><path d="M48 36c-10 0-16-6-16-15 10 0 16 5 16 15z" fill="{Y}" stroke="{D}" stroke-width="1.6"/><path d="M48 32c9 0 14-5 14-13-9 0-14 5-14 13z" fill="{L}"/>',
    "diagnosis": None,
    "local": None,
}
ICONS["diagnosis"] = ICONS["tongue"]
ICONS["local"] = ICONS["pin"]

for name, glyph in ICONS.items():
    tile = N if name == "moon" else T
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96" role="img" aria-hidden="true">'
           f'<rect width="96" height="96" rx="28" fill="{tile}"/>{glyph}</svg>')
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
print(f"icons: {len(ICONS)}개 → {OUT}")
