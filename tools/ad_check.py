#!/usr/bin/env python3
"""의료광고·개인정보 자동 검수. 사람 승인 대신 발행 전에 이 검사를 통과해야 한다.

사용:  python3 tools/ad_check.py            # content/posts, naver-blog/posts 전부
       python3 tools/ad_check.py 파일.md ...  # 지정한 파일만
       --quiet  통과 시 출력 없음   --json  결과를 JSON 으로
종료 코드: 0 = 통과(경고만 있어도 통과), 1 = 차단 항목 있음.

규칙 근거: tools/auto_prompt.md '반드시 지킬 것'. 단어 목록은 아래 BLOCK / WARN 에서 고친다.
같은 문장에 "않/아닙니다/없습니다/어렵" 같은 부정 표현이 있으면 '약속하지 않는다'는 안내로 보고 경고로 낮춘다.
"""
import glob, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLINIC_PHONE = "02-815-7510"

# (패턴, 설명) — 걸리면 발행 차단
BLOCK = [
    (r"완치|완쾌|치료\s*보장|효과\s*보장|보장합니다|100\s*%|백\s*퍼센트", "효과 단정·보장"),
    (r"최고|최초|(?<!이)유일|국내\s*1|1\s*위|특효|(?<![가-힣])명의(?![가-힣])|최상|독보적", "최상급·비교 표현"),  # (?<!이): '다른 이유일 수' 오탐 방지(11/26)
    (r"전문\s*병원|전문\s*분야", "전문병원·전문 분야 표현"),
    (r"부작용\s*(이|은)?\s*없(?!나요|는지|을까|냐|는 ?건|는가)|(?<![가-힣])안\s*아픈\s*(충격파|치료|시술|침|한의원)|통증\s*없(이|는)\s*(치료|시술|진료|침|충격파)|(?<![가-힣])무통|근본\s*치료|근본적\s*치료", "부작용·통증 없음·근본 치료 단정"),
    (r"치료\s*후기|체험\s*담|환자\s*후기|리얼\s*후기|비포\s*애프터|전후\s*사진", "후기·체험담·전후 사진"),
    (r"할인|이벤트|무료\s*(상담|체험|진료)|프로모션|특가|\d[\d,]*\s*만?\s*원\b", "가격·할인·이벤트"),
    (r"노량진점", "금지된 지점명 '노량진점'"),
    (r"\d{6}\s*-\s*[1-4]\d{6}", "주민등록번호 형태"),
    (r"[가-힣]{2,4}\s*(환자|님)\s*(은|는|이|가)?\s*\d{1,2}\s*(세|살)", "환자 이름·나이 노출 의심"),
]
# 걸려도 차단하지 않고 사람이 나중에 볼 수 있게 경고만
WARN = [
    (r"낫습니다|낫는다|좋아집니다|개선됩니다|효과가\s*있", "효과 단정으로 읽힐 수 있음(조건·가능성 표현 권장)"),
    (r"치료\s*전후", "치료 전후 표현(사진·사례 공개로 읽히지 않는지 확인)"),
    (r"다른\s*(병원|한의원)보다|타\s*(병원|한의원)", "다른 병원과 비교"),
    (r"반드시\s*낫|확실히|틀림없이|무조건", "단정 표현"),
]
NEGATION = re.compile(r"않|없는지|아닙니다|아닌|없습니다|어렵|금지|드리지|하지\s*못|할\s*수\s*없|따로|확인이\s*필요")
PHONE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")


def targets(args):
    if args:
        return [a for a in args if os.path.isfile(a)]
    pats = ["content/posts/*.md", "naver-blog/posts/*.md"]
    out = []
    for p in pats:
        out += glob.glob(os.path.join(ROOT, p))
    return sorted(set(out))


def sentences(text):
    return re.split(r"(?<=[.!?。])\s+|\n+", text)


def check(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except Exception as e:
        return [("block", f"읽기 실패: {e}", "")]
    body = re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.S)  # 프론트매터는 제외(제목은 별도)
    title = re.search(r"^title:\s*(.+)$", raw, re.M)
    text = (title.group(1) + "\n" if title else "") + body
    hits = []
    for s in sentences(text):
        if not s.strip():
            continue
        for pat, why in BLOCK:
            m = re.search(pat, s)
            if m:
                level = "warn" if (NEGATION.search(s) and why in ("효과 단정·보장", "최상급·비교 표현", "부작용·통증 없음·근본 치료 단정", "후기·체험담·전후 사진", "가격·할인·이벤트", "전문병원·전문 분야 표현")) else "block"
                hits.append((level, why, s.strip()[:80]))
        for pat, why in WARN:
            if re.search(pat, s):
                hits.append(("warn", why, s.strip()[:80]))
        for ph in PHONE.findall(s):
            if ph != CLINIC_PHONE:
                hits.append(("block", f"원장 번호 외 전화번호 {ph}", s.strip()[:80]))
    return hits


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet, as_json = "--quiet" in sys.argv, "--json" in sys.argv
    files = targets(argv)
    report, blocked = {}, 0
    for f in files:
        hits = check(f)
        if hits:
            report[os.path.relpath(f, ROOT)] = hits
            blocked += sum(1 for h in hits if h[0] == "block")
    if as_json:
        print(json.dumps({"files": len(files), "blocked": blocked, "report": report}, ensure_ascii=False, indent=1))
    else:
        for f, hits in report.items():
            for level, why, s in hits:
                if level == "block" or not quiet:
                    print(f"[{'차단' if level == 'block' else '경고'}] {f} - {why}: {s}")
        if not quiet or blocked:
            print(f"검사 {len(files)}개, 차단 {blocked}건, 경고 {sum(1 for h in report.values() for x in h if x[0] == 'warn')}건")
    sys.exit(1 if blocked else 0)


if __name__ == "__main__":
    main()
