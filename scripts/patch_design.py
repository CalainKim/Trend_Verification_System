#!/usr/bin/env python3
"""Trend Monitor 화면에 파이프라인 연동에 필요한 수정을 넣는다.

Claude Design 에서 받은 .dc.html 을 받아 고친 사본을 낸다. 원본은 건드리지
않는다. 손으로 고치면 열두 군데를 빠뜨리기 쉬워서 스크립트로 둔다.

    ./scripts/patch_design.py v8.html -o v9.html

하는 일은 다섯이다.

1. 데이터 상수 교체
   G, P, LEDGER 를 build/frontend_data.js 내용으로 바꾸고 원본의 TYPE_SKIP
   선언을 지운다. 생성 파일이 같은 이름을 선언하므로 둘 다 두면 const 중복
   선언으로 스크립트가 통째로 죽는다.

2. 할인 효과와 해외 선행 단계 연결
   화면은 둘을 "연결 예정" 으로 비워 두었다. 자료는 있으므로 검사 결과를
   채우되 후보를 떨구지는 않는다. 할인 급증은 지속성과 무관함을 자체 검증으로
   확인했고(늘어난 상승 57.1% 유지, 변화 없던 상승 52.9% 유지), 해외 선행은
   신뢰 판정 열넷 가운데 여덟이 한국 선행이라 통과 조건으로 쓰면 진짜 상승의
   절반이 떨어진다. 그래서 측정만 하고 거르지 않는다.

3. 신선도 문턱을 WEEK 로 바꾼다
   G[a].last >= '2026-10-18' 비교가 여섯 군데 있다. 주가 바뀌는데 이 문자열이
   그대로면 지난 주 기준으로 신선도를 재게 된다.

4. 검증 기록 CSV 의 머리글과 파일명을 WEEK 로 바꾼다

5. 추론 설정 교체
   화면이 박아 둔 claude-sonnet-4-5 는 API 에서 사라져 404 가 난다. 모델과
   한도와 effort 를 채점에 쓴 설정과 같게 맞춘다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build" / "frontend_data.js"

# 화면이 추론에 쓰는 모델 이름. Claude Design 안에서는 런타임이 모델을 붙여
# 주지만, 파일 사본은 Anthropic API 를 직접 부른다. 거기서는 claude-sonnet-4-5
# 가 더 이상 제공되지 않아 404 not_found_error 가 났다. 화면은 catch 로 묶어
# "다시 실행해 주세요" 만 적으므로 몇 번을 눌러도 같은 자리에서 멈췄다.
#
# 채점한 모델과 같은 것을 쓴다. 검증 기록 화면이 보여 주는 성적은
# src/trend_poc/client.py 의 모델로 낸 값이라, 버튼이 다른 모델을 부르면
# 화면이 한 모델의 성적을 걸어 두고 다른 모델을 돌리는 꼴이 된다.
STALE_MODEL = "claude-sonnet-4-5"
MODEL = "claude-opus-5-5"
# 채점에 쓴 설정과 같은 값이다. src/trend_poc/review.py 를 보라. 화면이 보여
# 주는 성적은 이 설정으로 낸 것이라 버튼도 같은 설정으로 불러야 한다.
#
# effort 를 안 주면 모델이 알아서 길게 생각하고, 생각 분량이 max_tokens 에서
# 깎인다. 실제로 "유행 찾기" 는 생각에만 3,347 토큰을 쓰다 한도 3,000 에
# 걸려 본문이 한 글자도 안 나왔다.
MAX_TOKENS = 4096
EFFORT = "low"

# 화면이 각 상품에 붙이는 여섯 검사 가운데 넷째와 다섯째. 원본은 자리만 잡아
# 두고 "연결 예정" 으로 비워 두었다.
OLD_CHECKS = ("{ s: 'na', text: '[데이터 연결 예정] 정가와 할인율로 할인 때문에 오른 건지' }, "
              "{ s: 'na', text: '[데이터 연결 예정] 미국 검색과 해외 커머스에서 먼저 올랐는지' }")
NEW_CHECKS = "dc, ov"

# dc 와 ov 를 p.checks 앞에서 만든다. 둘 다 s 가 'pass' 나 'info' 라서 드롭
# 판정에 쓰이지 않는다. 드롭은 아래 [sr, br] 에서만 본다.
COMPUTE = """    const dUp = p.prevDisc == null ? null : (p.disc || 0) - p.prevDisc;
    const dc = p.disc == null ? { s: 'na', text: '할인율을 수집하지 못한 상품' }
      : dUp == null ? { s: 'info', text: `할인 ${p.disc}%, 지난주 TOP100 밖이라 비교할 값 없음` }
      : dUp >= 5 ? { s: 'info', text: `할인이 ${p.prevDisc}%에서 ${p.disc}%로 ${dUp}%p 늘며 올랐습니다. 자체 검증에서 할인 증가는 유지 여부와 차이가 없었으므로(57.1% 대 52.9%) 거르지 않고 표시만 합니다` }
      : { s: 'pass', text: dUp <= -5 ? `할인을 ${-dUp}%p 줄이고도 올랐습니다` : `할인 ${p.disc}%로 지난주와 같은 수준입니다` };
    const lead = p.attrs.map(a => G[a] && G[a].lead).find(Boolean);
    const ov = !lead ? { s: 'na', text: '선행 판정이 신뢰 문턱을 넘지 못했습니다' }
      : { s: 'info', text: lead.days > 0 ? `미국이 ${lead.days}일 앞섰습니다 (상관 ${lead.corr})`
          : lead.days < 0 ? `한국이 ${-lead.days}일 앞섰습니다 (상관 ${lead.corr}). 해외 선행 가설과 반대이고 신뢰 판정 다수가 이쪽이라 거르지 않습니다`
          : `한국과 미국이 같은 시점에 올랐습니다 (상관 ${lead.corr})` };
"""


def swap_data(src: str) -> str:
    lines = src.split("\n")
    if not DATA.exists():
        raise SystemExit(f"{DATA} 가 없다. ./scripts/export_frontend.py 를 먼저 돌려라")
    data_lines = DATA.read_text(encoding="utf-8").rstrip("\n").split("\n")

    # 생성 파일이 선언하는 이름을 모두 찾아, 화면 쪽의 같은 이름 선언을 지운다.
    # 둘 다 두면 const 중복 선언으로 스크립트가 통째로 죽는다. 화면이 새 상수를
    # 자리표시자로 먼저 선언해 두는 일이 잦아서, 이름을 손으로 관리하면
    # 빠뜨린다. 실제로 TYPE_SKIP 에 이어 TRACK 에서 같은 일이 났다.
    #
    # 선언이 여러 줄일 수 있다. 한 줄만 지우면 나머지가 고아로 남아 문법이
    # 깨진다. 여는 괄호와 닫는 괄호를 세어 선언 전체를 지운다.
    mine = {l.split()[1] for l in data_lines if l.startswith("const ")}
    removed = []
    for name in sorted(mine):
        hit = [i for i, l in enumerate(lines) if l.startswith(f"const {name} = ")]
        if len(hit) > 1:
            raise SystemExit(f"화면 쪽 {name} 선언이 {len(hit)}개다. 1개여야 한다")
        if not hit:
            continue
        start = hit[0]
        depth, end_i = 0, None
        for j in range(start, len(lines)):
            depth += lines[j].count("{") + lines[j].count("[")
            depth -= lines[j].count("}") + lines[j].count("]")
            if depth <= 0 and lines[j].rstrip().endswith(";"):
                end_i = j
                break
        if end_i is None:
            raise SystemExit(f"화면 쪽 {name} 선언의 끝을 찾지 못했다")
        removed.append(f"{name}({end_i - start + 1}줄)")
        del lines[start:end_i + 1]
    if removed:
        print(f"  화면 쪽 선언 제거: {', '.join(removed)}")
    # 선언을 지웠으니 넣을 자리를 다시 찾는다. 상수들이 모여 있던 블록의
    # 끝(const UP)을 기준으로 그 앞에 넣는다.
    try:
        at = next(i for i, l in enumerate(lines) if l.startswith("const UP = "))
    except StopIteration:
        raise SystemExit("상수 블록의 경계(const UP)를 찾지 못했다")
    # x-dc 스크립트 블록은 런타임이 자체 스코프에서 평가한다. 거기 선언한 const 는
    # 전역이 아니라, 번들 단계에서 붙이는 판정 패널이 볼 수 없다. 데이터를 다시
    # 넣으면 178KB 가 중복되므로 한 줄로 내보낸다.
    names = sorted(mine)
    bridge = ["", "// 번들의 판정 패널이 읽을 수 있게 전역으로 내보낸다.",
              "try { " + " ".join(f"window.{n} = {n};" for n in names)
              + " } catch (e) {}"]
    return "\n".join(lines[:at] + data_lines + bridge + lines[at:])


def wire_stages(src: str) -> str:
    # 단계 표에서 na 를 떼고 info 로 바꾼다. na 는 "자료 없음", info 는
    # "쟀지만 거르지 않음" 이다. 화면이 둘을 다르게 적어야 한다.
    for label in ("할인 효과", "해외 선행"):
        old = f"{{ label: '{label}', desc: "
        i = src.index(old)
        j = src.index("\n", i)
        line = src[i:j]
        if ", na: true }" not in line:
            raise SystemExit(f"{label} 단계가 na: true 가 아니다: {line}")
        src = src[:i] + line.replace(", na: true }", ", info: true }") + src[j:]

    old = ("desc: s.desc + (s.na ? ' (연결 예정, 지금은 통과)' : off ? ' (설정에서 꺼짐)' : '')")
    new = ("desc: s.desc + (s.info ? ' (측정함, 거르지 않음)' : s.na ? ' (연결 예정, 지금은 통과)' "
           ": off ? ' (설정에서 꺼짐)' : '')")
    if src.count(old) != 1:
        raise SystemExit("깔때기 설명 줄을 찾지 못했다")
    src = src.replace(old, new)

    # info 단계는 na 와 똑같이 아무도 떨구지 않는다.
    old = "const out = s.na ? 0 : det.filter(p => p.dropAt === i).length;"
    new = "const out = s.na || s.info ? 0 : det.filter(p => p.dropAt === i).length;"
    if src.count(old) != 1:
        raise SystemExit("깔때기 집계 줄을 찾지 못했다")
    src = src.replace(old, new)

    old = "funnel.push({ label: s.label, desc:"
    new = "funnel.push({ label: s.label, desc:"
    src = src.replace(
        "drop: s.na || off ? '–' : (out ? '−' + out : '0'), na: s.na || off, out });",
        "drop: s.na ? '–' : s.info ? '0' : off ? '–' : (out ? '−' + out : '0'), "
        "na: s.na || off, out });")

    if OLD_CHECKS not in src:
        raise SystemExit("연결 예정 검사 두 개를 찾지 못했다")
    src = src.replace(OLD_CHECKS, NEW_CHECKS)

    # 상품 하나를 훑는 루프 맨 앞에 dc, ov 계산을 끼운다.
    anchor = "    const com = { s: 'pass', text: p.prev == null ?"
    if src.count(anchor) != 1:
        raise SystemExit("검사 루프의 시작점을 찾지 못했다")
    src = src.replace(anchor, COMPUTE + anchor)

    # info 에 고유 마커를 준다. 안 주면 "–" 로 찍혀서 자료가 없는 것과 구별되지
    # 않는다. 쟀는데 안 보이면 측정한 의미가 없다. ○ 는 화면이 이미 "관찰" 판정에
    # 쓰는 기호라 "확인했으나 결론으로 쓰지 않음" 이라는 뜻이 그대로 통한다.
    old = ("m: c.s === 'pass' ? '✓' : c.s === 'fail' ? '✗' : '–', "
           "c: c.s === 'pass' ? OK : c.s === 'fail' ? BAD : MUTED })")
    new = ("m: c.s === 'pass' ? '✓' : c.s === 'fail' ? '✗' : c.s === 'info' ? '○' : '–', "
           "c: c.s === 'pass' ? OK : c.s === 'fail' ? BAD : c.s === 'info' ? INK : MUTED })")
    if src.count(old) != 1:
        raise SystemExit("검사 마커를 정하는 줄을 찾지 못했다")
    src = src.replace(old, new)

    # 할인율은 P 의 일곱째, 여덟째 값이다. 상품 객체를 만드는 자리에 붙인다.
    old = ("map[x[3]] = { name: x[3], brand: x[2], rank: x[0], prev: x[1], "
           "price: x[4], gender: x[5], attrs: [] };")
    new = ("map[x[3]] = { name: x[3], brand: x[2], rank: x[0], prev: x[1], "
           "price: x[4], gender: x[5], disc: x[6] ?? null, prevDisc: x[7] ?? null, attrs: [] };")
    if src.count(old) != 1:
        raise SystemExit("상품 객체를 만드는 줄을 찾지 못했다")
    return src.replace(old, new)


def fix_pending_text(src: str) -> int:
    """연결이 끝난 항목을 아직 연결 예정이라고 적은 문구를 고친다.

    문구를 안 고치면 화면이 자기가 가진 자료를 없다고 말한다. 보는 사람은
    글자를 믿지 마커를 세지 않는다.
    """
    swaps = [
        # 판매가 카드의 설명. 할인율은 필터 점검에 들어갔으므로 거기로 안내한다.
        ('data-tip="정가와 할인율은 [데이터 연결 예정]"',
         'data-tip="29CM 의 현재 판매가입니다. 할인율은 오른쪽 필터 점검의 할인에서 봅니다"'),
        # 발주 검토 요청서의 판매가 줄. 실제 할인율을 적는다.
        ("['판매가', rq.priceTxt + '원 (정가, 할인율 연결 예정)']",
         "['판매가', rq.priceTxt + '원' + (rq.disc ? ` (할인 ${rq.disc}%)` : ' (정가)')]"),
        # 설정 요약의 단계 수.
        ("['필터 단계', '검색 교차, 브랜드 분산 외 연결 예정 3단계']",
         "['필터 단계', '거르는 2단계, 측정만 2단계, 연결 예정 1단계']"),
        # 데이터 출처 표시에서 정가를 연결됨으로 옮긴다.
        ('연결됨: 29CM, Google 검색. 연결 예정: 일 단위 판매, 재고, 인플루언서, 해외 커머스, 정가',
         '연결됨: 29CM 순위, 정가와 할인율, Google 검색(한국, 미국). '
         '연결 예정: 일 단위 판매, 재고, 인플루언서, 해외 커머스'),
    ]
    swaps += [
        # 설정의 단계 토글. info 를 그냥 두면 거르지 않는데도 "켜짐" 으로 보이고
        # 끌 수 있는 것처럼 보인다. 끄고 켤 대상이 아니므로 토글을 막는다.
        ("const on = !x.na && s.stageOn[i] !== false; return { label: x.label, desc: x.desc, "
         "on, dis: !!x.na, op: x.na ? 0.55 : 1, sub: x.na ? '데이터 연결 예정' : on ? '켜짐' : '꺼짐', "
         "sw: sw(on), go: () => { if (x.na) return;",
         "const on = !x.na && !x.info && s.stageOn[i] !== false; return { label: x.label, "
         "desc: x.desc, on, dis: !!(x.na || x.info), op: x.na || x.info ? 0.55 : 1, "
         "sub: x.na ? '데이터 연결 예정' : x.info ? '측정만, 거르지 않음' : on ? '켜짐' : '꺼짐', "
         "sw: sw(on), go: () => { if (x.na || x.info) return;"),
        # 상태 줄의 연결 채널 수. 정가와 할인율이 연결됐으므로 하나 늘었다.
        ('cursor:help">채널 2/7</span>', 'cursor:help">채널 3/7</span>'),
    ]
    n = 0
    for old_s, new_s in swaps:
        if src.count(old_s) != 1:
            raise SystemExit(f"문구를 찾지 못했거나 여러 개다: {old_s[:40]}")
        src = src.replace(old_s, new_s)
        n += 1
    return src, n


def wire_images(src: str) -> str:
    """상품 사진을 실제로 띄운다.

    원래는 끌어다 놓는 자리(image-slot)만 있고 29CM 이미지는 연결 예정이었다.
    랭킹 API 가 imageUrl 을 주는데 수집기가 버리고 있었을 뿐이다. 사진이 있으면
    img 로 띄우고, 없으면 원래 자리표시자를 그대로 둔다.
    """
    # 상품 객체에 사진 주소를 싣는다. P 의 아홉째 값이다.
    old = "disc: x[6] ?? null, prevDisc: x[7] ?? null, attrs: [] };"
    new = "disc: x[6] ?? null, prevDisc: x[7] ?? null, img: x[8] ?? null, attrs: [] };"
    if src.count(old) != 1:
        raise SystemExit("상품 객체에 사진을 실을 자리를 찾지 못했다")
    src = src.replace(old, new)

    # 상세 화면이 읽는 자리에 넣는다.
    old = "        slotId: 'prod-' +"
    new = "        img: sel.img || null, noImg: !sel.img,\n        slotId: 'prod-' +"
    if src.count(old) != 1:
        raise SystemExit("상품 상세의 사진 자리를 찾지 못했다")
    src = src.replace(old, new)

    # 마크업. 사진이 있으면 img, 없으면 원래 자리표시자.
    old = ('<div data-tip="상품 사진을 끌어다 놓으세요. 29CM 이미지 자동 연결은 '
           '[데이터 연결 예정]" style="width:88px;height:110px;flex:none;'
           'border-radius:8px;overflow:hidden;background:var(--color-canvas)">'
           '<image-slot id="{{ pn.p.slotId }}" shape="rounded" radius="8" '
           'placeholder="사진"></image-slot></div>')
    new = ('<div data-tip="29CM 상품 사진" style="width:88px;height:110px;flex:none;'
           'border-radius:8px;overflow:hidden;background:var(--color-canvas)">'
           '<sc-if value="{{ pn.p.img }}" hint-placeholder-val="{{ true }}">'
           '<img src="{{ pn.p.img }}" alt="" loading="lazy" '
           'style="width:100%;height:100%;object-fit:cover;display:block"></sc-if>'
           '<sc-if value="{{ pn.p.noImg }}" hint-placeholder-val="{{ false }}">'
           '<image-slot id="{{ pn.p.slotId }}" shape="rounded" radius="8" '
           'placeholder="사진"></image-slot></sc-if></div>')
    if src.count(old) != 1:
        raise SystemExit("사진 자리 마크업을 찾지 못했다")
    return src.replace(old, new)


def fix_llm_prompt(src: str) -> tuple[str, int]:
    """LLM 에게 알려 주는 "없는 데이터" 목록에서 이제 있는 것을 뺀다.

    여기가 틀리면 LLM 이 "정가와 할인율이 없어 할인 효과를 판단할 수 없다" 같은
    사실과 다른 답을 낸다. 화면 문구보다 조용히 틀리는 자리라 꼭 맞춰야 한다.
    """
    n = 0
    for gone in ("'해외 선행 기간', ", "'정가와 할인율', ", ", '정가와 할인율'"):
        n += src.count(gone)
        src = src.replace(gone, "")
    # 날짜도 주마다 바뀐다.
    src = src.replace("오늘: '2026-11-02', 다음채점: '2026-11-08'",
                      "오늘: WEEK.holdISO, 다음채점: WEEK.nextISO")
    src = src.replace("오늘: '2026-11-02'", "오늘: WEEK.holdISO")
    return src, n


def wire_score(src: str) -> str:
    """검증 기록의 타일 네 개에 실제 채점 결과를 넣는다.

    화면이 최종 산출물이므로 여기가 비어 있으면 "채점을 했다" 는 말이 화면에
    없는 것과 같다. 원래는 value 가 '–' 로 박혀 있고 tip 에 "11/08 첫 채점"
    이라고 적혀 있었다.

    숫자만 넣으면 표본이 몇인지 안 보인다. SCORE.note 가 "답한 24건 기준,
    찍기보다 낫다고 하기엔 표본 부족" 을 담고 있어 tip 에 함께 넣는다.
    24건으로 70.8% 를 단정하면 과장이다.
    """
    old = ("{ label: '짚은 상품 중 실제로 남은 비율', value: '–', c: MUTED, "
           "tip: '11/08 첫 채점. 기준 비율 54.1%와 비교합니다' }, "
           "{ label: '실제 급등 중 미리 잡은 비율', value: '–', c: MUTED, "
           "tip: '놓친 급등까지 세야 계산됩니다' }, "
           "{ label: '기준 비율', value: '54.1%', c: INK, "
           "tip: '전부 남는다고 했을 때의 비율' }")
    new = ("{ label: '짚은 상품 중 실제로 남은 비율', "
           "value: SCORE && SCORE.precision != null ? "
           "Math.round(SCORE.precision * 1000) / 10 + '%' : '–', "
           "c: SCORE && SCORE.precision != null ? INK : MUTED, "
           "tip: SCORE ? '지속이라 말한 것 가운데 실제로 지속한 비율. ' + SCORE.note "
           ": '아직 채점하지 않았습니다' }, "
           "{ label: '실제 급등 중 미리 잡은 비율', "
           "value: SCORE && SCORE.recall != null ? "
           "Math.round(SCORE.recall * 1000) / 10 + '%' : '–', "
           "c: SCORE && SCORE.recall != null ? INK : MUTED, "
           "tip: SCORE ? '실제로 지속한 것 가운데 미리 짚은 비율. ' + SCORE.note "
           ": '놓친 급등까지 세야 계산됩니다' }, "
           "{ label: '기준 비율', "
           "value: SCORE ? Math.round(SCORE.base_rate * 1000) / 10 + '%' : '–', "
           "c: SCORE ? INK : MUTED, tip: SCORE ? "
           "(SCORE.base_side === 'fade' ? '전부 소멸한다고 ' : '전부 남는다고 ') "
           "+ '했을 때의 비율. 모델 성적은 이 값을 넘어야 뜻이 있습니다' "
           ": '아직 채점하지 않았습니다' }")
    if src.count(old) != 1:
        raise SystemExit("검증 기록 타일을 찾지 못했다")
    src = src.replace(old, new)

    # 맞힌 비율과 답한 비율은 타일에 자리가 없다. 머리글 옆 문구에 넣는다.
    old = ("<span style=\"font-size:26px;font-weight:400;"
           "letter-spacing:-0.325px\">검증 기록</span>")
    if src.count(old) != 1:
        raise SystemExit("검증 기록 제목을 찾지 못했다")
    # 제목 바로 아래에 한 줄을 붙인다. 다른 화면의 제목도 같은 모양이라
    # 제목 문구까지 포함해서 찾아야 한 곳만 바뀐다.
    src = src.replace(
        old,
        "<div style=\"display:flex;flex-direction:column;gap:6px\">" + old
        + "<span style=\"font-size:13px;color:var(--color-muted)\">"
          # 검증 기록 화면의 값은 pn 아래가 아니라 뷰모델 최상위에 있다.
          # 타일이 {{ ledgerTiles }} 로 닿으므로 여기도 접두사 없이 쓴다.
          "{{ scoreLine }}</span></div>")

    old = "      ledgerTiles: ["
    new = ("      scoreLine: SCORE ? `모델 판정 ${SCORE.n_answered}건 채점, "
           "맞힌 비율 ${Math.round(SCORE.accuracy * 1000) / 10}%, "
           "답한 비율 ${Math.round(SCORE.coverage * 1000) / 10}% "
           "(95% 구간 ${Math.round(SCORE.ci[0] * 1000) / 10}~"
           "${Math.round(SCORE.ci[1] * 1000) / 10}%)` : '아직 채점하지 않았습니다',\n"
           "      ledgerTiles: [")
    if src.count(old) != 1:
        raise SystemExit("ledgerTiles 선언을 찾지 못했다")
    return src.replace(old, new)


def wire_week(src: str) -> tuple[str, int]:
    # 신선도 문턱. 주가 바뀌면 같이 움직여야 한다.
    src, n = re.subn(r"'2026-10-18'", "WEEK.baseISO", src)
    # 검증 기록 CSV
    src = src.replace("csv('검증기록_1101.csv', ['상품', '10/18', '10/25', '11/01', '결과']",
                      "csv(`검증기록_${WEEK.hold.replace('/', '')}.csv`, "
                      "['상품', WEEK.base, WEEK.detect, WEEK.hold, '결과']")
    return src, n


def fix_model(src: str) -> tuple[str, int]:
    """사라진 모델 이름을 지금 부를 수 있는 것으로 바꾸고, 실패를 드러낸다.

    생각 분량이 max_tokens 에서 깎이므로 한도와 effort 도 같이 맞춘다. 안
    맞추면 호출은 200 으로 돌아오는데 본문이 비어 JSON 파싱에서 깨진다.

    화면의 네 추론은 전부 catch 안에서 끝나 브라우저 콘솔에도 아무것도 남지
    않았다. 다음에 또 막히면 원인을 못 찾으므로 콘솔에 적게 한다.
    """
    src, n = re.subn(
        rf"model: '{re.escape(STALE_MODEL)}', max_tokens: \d+,",
        f"model: '{MODEL}', max_tokens: {MAX_TOKENS}, "
        f"output_config: {{ effort: '{EFFORT}' }},", src)
    if not n:
        raise SystemExit(
            f"모델 이름 {STALE_MODEL} 을 찾지 못했다. 화면이 다른 이름을 쓰게 "
            f"바뀌었으면 scripts/patch_design.py 의 STALE_MODEL 을 고쳐라")
    # 일부만 바뀌면 안 바뀐 자리가 404 를 내는데, 그 기능을 눌러 보기 전에는
    # 모른다. 하나라도 남아 있으면 멈춘다.
    if STALE_MODEL in src:
        raise SystemExit(
            f"{n}곳을 바꿨는데 {STALE_MODEL} 이 아직 남아 있다. max_tokens 를 "
            f"적지 않은 호출이 있는지 보라")

    m = src.count("} catch (e) { upd(")
    if m != 4:
        raise SystemExit(f"추론 실패를 받는 자리가 넷이 아니라 {m} 개다")
    src = src.replace("} catch (e) { upd(",
                      "} catch (e) { console.error('추론 실패', e); upd(")
    return src, n


def fix_base_rate(src: str) -> tuple[str, str]:
    """화면과 프롬프트에 글자로 박힌 기준 비율을 지금 값으로 바꾼다.

    시안에는 "유지한 비율 54.1% (최근 확인분 25건 중 10건, 40.0%)" 가 네 군데
    적혀 있다. 문제지가 61건이던 때의 값이다. 지금 benchmark 는 139건이고
    지속 비율은 40.3% 다. 14%p 가 틀리면 모델이 넘어야 할 바가 통째로 달라진다.

    넷 가운데 하나는 "최근 확인분이 기준 비율보다 낮습니다" 라고 단정한다.
    숫자만 갈아 끼우면 41.2% 가 40.3% 보다 낮다는 거짓말이 된다. 비교까지
    다시 한다.

    바꿀 글이 하나라도 안 보이면 멈춘다. 조용히 지나가면 옛 숫자가 그대로
    교수님과 무신사 앞에 뜬다.
    """
    js = DATA.read_text(encoding="utf-8")

    def pick(name, open_c, close_c):
        m = re.search(r"const %s = (\%s.*?\%s);" % (name, open_c, close_c),
                      js, re.S)
        if not m:
            raise SystemExit(f"{DATA} 에서 {name} 을 못 찾았다")
        return json.loads(m.group(1))

    score, ledger = pick("SCORE", "{", "}"), pick("LEDGER", "[", "]")
    if not score:
        raise SystemExit("SCORE 가 비었다. export_frontend.py 를 --verdicts "
                         "와 함께 돌려야 기준 비율을 고칠 수 있다")

    # SCORE.base_rate 는 많은 쪽을 전부 찍었을 때의 비율이다. 화면이 말하는
    # "유지 비율" 은 지속 쪽이므로, 많은 쪽이 소멸이면 뒤집어야 한다.
    keep = 1 - score["base_rate"] if score["base_side"] == "fade" \
        else score["base_rate"]
    n_led = len(ledger)
    kept = sum(1 for r in ledger if r[4])
    recent = kept / n_led if n_led else 0.0
    K, R = f"{keep * 100:.1f}", f"{recent * 100:.1f}"
    cmp_word = ("높습니다" if recent > keep + 0.0005
                else "낮습니다" if recent < keep - 0.0005 else "같습니다")

    swaps = [
        ("기준 비율(전부 유지한다고 했을 때 54.1%, 최근 40.0%)과 비교해 판단한다.",
         f"기준 비율(전부 유지한다고 했을 때 {K}%, 최근 {R}%)과 비교해 판단한다."),
        ("기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
         "유지한 비율 54.1% (최근 확인분 25건 중 10건, 40.0%)'",
         f"기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
         f"유지한 비율 {K}% (최근 확인분 {n_led}건 중 {kept}건, {R}%)'"),
        ("기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
         "유지한 비율 54.1%'",
         f"기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
         f"유지한 비율 {K}%'"),
        ("'최근 확인분 유지 비율은 40.0%로 기준 비율 54.1%보다 낮습니다.'",
         f"'최근 확인분 유지 비율은 {R}%로 기준 비율 {K}%보다 {cmp_word}.'"),
    ]
    # 장부 머리말의 건수도 글자로 박혀 있다. 바로 아래 표는 LEDGER 를 그대로
    # 그리므로, 머리말만 옛 수로 남으면 한 화면 안에서 25건과 34건이 같이
    # 보인다. 보는 사람은 어느 쪽을 믿어야 할지 알 수 없다.
    swaps.append((
        ">25건 중 10건 남음 (40.0%)<",
        f">{n_led}건 중 {kept}건 남음 ({R}%)<"))
    # 이쪽은 LEDGER 가 눈앞에 있으니 계산식으로 바꾼다. 다음에 건수가 늘어도
    # 저절로 맞는다.
    swaps.append((
        "ledgerStepCounts: ['25건', ",
        "ledgerStepCounts: [LEDGER.length + '건', "))

    for old, new in swaps:
        if old not in src:
            raise SystemExit("기준 비율을 적어 둔 자리를 못 찾았다. 시안에서 "
                             f"문구가 바뀌었다:\n  {old[:60]}")
        src = src.replace(old, new)

    for stale in ("54.1%", "25건 중 10건"):
        if stale in src:
            raise SystemExit(f"{stale} 가 아직 남아 있다. 바꾸지 못한 자리가 있다")
    return src, f"유지 비율 {K}%, 최근 {n_led}건 중 {kept}건 {R}%"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="Claude Design 에서 받은 .dc.html")
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)

    src = args.source.read_text(encoding="utf-8")
    if "data-omelette-injected" in src.split("\n")[3]:
        # 미리보기로 받은 파일에는 주입 스크립트가 들어 있다. 원본에는 없다.
        lines = src.split("\n")
        del lines[3:6]
        src = "\n".join(lines)
        print("미리보기 주입 스크립트 3줄 제거")

    src = swap_data(src)
    print("데이터 상수 교체, 원본 TYPE_SKIP 선언 제거")
    src = wire_stages(src)
    print("할인 효과와 해외 선행 단계 연결 (측정만, 거르지 않음)")
    src = wire_images(src)
    print("상품 사진 연결")
    src = wire_score(src)
    print("검증 기록 타일에 채점 결과 연결")
    src, note = fix_base_rate(src)
    print(f"글자로 박힌 기준 비율 네 곳을 지금 값으로 교체 ({note})")
    src, n = wire_week(src)
    print(f"신선도 문턱 {n}곳과 검증 기록 CSV 를 WEEK 로 교체")
    src, n = fix_pending_text(src)
    print(f"연결이 끝났는데 연결 예정이라고 적힌 문구 {n}곳 수정")
    src, n = fix_llm_prompt(src)
    print(f"LLM 에게 알려 주는 없는 데이터에서 {n}곳 제거, 날짜를 WEEK 로 교체")
    src, n = fix_model(src)
    print(f"추론 {n}곳을 {MODEL}, max_tokens {MAX_TOKENS}, "
          f"effort {EFFORT} 로 교체하고 실패를 콘솔에 남김")

    args.out.write_text(src, encoding="utf-8")
    print(f"\n{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
