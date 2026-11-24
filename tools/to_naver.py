#!/usr/bin/env python3
"""홈페이지 한방가이드 글을 네이버 블로그 원고로 바꾼다(naver-blog/posts/<slug>.md + images/<slug>/ + tags/<slug>.txt).
사용: python tools/to_naver.py <slug> [<slug> ...]
- 사진: 01 = 글 대표 그림(실제 한약 사진 또는 글 제목에 맞춘 그림), 02 = 좋은꿈참사랑한의원 실제 진료 사진
- 끝에 진료시간·주소·예약 안내와 홈페이지 원문 링크(utm_source=naver_blog)를 붙인다.
- 의료광고 규칙은 원문과 같다(효과 단정·후기·가격 없음)."""
import os, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import build  # noqa: E402

posts = {p["slug"]: p for p in build.load_posts()}
build.assign_post_images(list(posts.values()) + build.UPCOMING)
LOCAL_TAGS = ["노량진한의원", "상도동한의원", "상도역한의원", "동작구한의원", "좋은꿈참사랑한의원"]
CAT_TAGS = {"insomnia": ["불면", "수면"], "metabolic": ["대사증후군", "식습관"], "pain": ["통증", "생활습관"], "chuna": ["추나", "자세"],
            "shockwave": ["체외충격파", "통증"], "ultrasound": ["초음파", "통증"], "accident": ["교통사고", "교통사고한의원"], "digestion": ["소화", "위장"],
            "women": ["여성건강", "생리통"], "pediatric": ["소아", "성장"], "respiratory": ["비염", "호흡기"], "skin": ["피부", "가려움"],
            "neuro": ["두통", "어지럼"], "mental": ["스트레스", "불안"], "first-visit": ["한의원처음", "진료안내"], "herbal": ["한약", "한약상담"],
            "diagnosis": ["진맥", "설진"], "local": ["노량진", "상도동"]}


def md_body(p):
    raw = p.get("body_md") or p.get("body") or ""
    return raw


def convert(slug):
    p = posts[slug]
    src = open(p["_file"], encoding="utf-8").read() if p.get("_file") else None
    # 원문 마크다운을 파일에서 다시 찾는다
    text = None
    for fn in os.listdir("content/posts"):
        t = open(os.path.join("content/posts", fn), encoding="utf-8").read()
        for ch in re.split(r"^=====\s*$", t, flags=re.M):
            if re.search(rf"^slug:\s*{re.escape(slug)}\s*$", ch, re.M):
                text = ch
                break
        if text:
            break
    body = re.split(r"^---\s*$", text, flags=re.M)[-1].strip()
    faq = ""
    m = re.search(r"^:::\s*faq\s*$(.*?)^:::\s*$", body, re.M | re.S)
    if m:
        qa = re.findall(r"^Q:\s*(.+?)\s*$\s*^A:\s*(.+?)\s*$", m.group(1), re.M)
        faq = "\n\n## 자주 묻는 질문\n\n" + "\n\n".join(f"**Q. {q}**\n{a}" for q, a in qa)
        body = body[:m.start()].rstrip()
    # 사진 자리: 첫 문단 뒤에 01, '한의원에서' 구역 앞에 02
    paras = body.split("\n\n")
    body = paras[0] + "\n\n![](01.jpg)\n\n" + "\n\n".join(paras[1:])
    body = re.sub(r"(^## 한의원에서[^\n]*$)", r"![](02.jpg)\n*좋은꿈참사랑한의원 진료 모습*\n\n\1", body, count=1, flags=re.M)
    url = f"https://gooddreamclinic.com/{build.post_url(p)}?utm_source=naver_blog&utm_medium=blog&utm_campaign=guide&utm_content={slug}"
    tail = (f"{faq}\n\n## 좋은꿈참사랑한의원 안내\n\n"
            "- 주소: 서울 동작구 만양로2길 2 신성빌딩 3층·5층 (7호선 상도역 3번 출구)\n"
            "- 진료시간: 평일 09:30~20:00 (점심 13:00~14:00) · 토·일·공휴일 09:30~15:00\n"
            "- 전화: 02-815-7510 · 네이버 예약 · 카카오톡 상담\n"
            f"- 홈페이지 원문: {url}\n\n"
            "*이 글은 일반적인 건강 정보이며 개인의 진단이나 치료를 대신하지 않습니다. 증상이 있거나 복용 중인 약이 있다면 진료를 통해 확인하세요. "
            + ("첫 번째 그림은 AI로 만든 이미지입니다.*" if (build.post_img(p) or "").startswith("post") else "사진은 좋은꿈참사랑한의원에서 직접 찍은 사진입니다.*"))
    tags = CAT_TAGS.get(p["category"], []) + LOCAL_TAGS
    os.makedirs("naver-blog/posts", exist_ok=True)
    with open(f"naver-blog/posts/{slug}.md", "w", encoding="utf-8") as f:
        f.write(f"---\ntitle: {p['title']}\ntags: [{', '.join(tags)}]\nreview: auto\n---\n\n{body}\n{tail}\n")
    d = f"naver-blog/images/{slug}"
    os.makedirs(d, exist_ok=True)
    first = build.post_img(p)
    if first:
        shutil.copy(f"images/{first}", f"{d}/01.jpg")
    real = [n for n in build.REAL_BY_CAT.get(p["category"], build.REAL_BY_CAT["first-visit"]) if os.path.exists(f"images/real/{n}.jpg")]
    if real:
        shutil.copy(f"images/real/{real[build._h(slug) % len(real)]}.jpg", f"{d}/02.jpg")
    os.makedirs("naver-blog/tags", exist_ok=True)
    extra = [w for w in re.findall(r"[가-힣]{2,6}", p["title"]) if w not in ("어떻게", "살피나요", "때는", "있나요", "무엇을", "하나요")][:6]
    with open(f"naver-blog/tags/{slug}.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(dict.fromkeys(tags + extra)) + "\n")
    return slug


if __name__ == "__main__":
    done = [convert(s) for s in sys.argv[1:] if s in posts]
    print("converted", len(done))
