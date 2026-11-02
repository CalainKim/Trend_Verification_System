#!/usr/bin/env python3
"""화면을 파일 하나로 묶는다.

받는 사람이 더블클릭만 하면 열리게 만든다. 서버도, 설치도, 로그인도,
네트워크도 필요 없다. 검증 파트와 지도교수께 보일 때 쓴다.

    ./scripts/bundle_design.py v9.html --assets <자산 폴더> -o 트렌드모니터.html

바깥 파일을 안 남기려고 전부 집어넣는다. CSS 와 JS 는 글자 그대로, 폰트는
base64 로 바꿔 CSS 안에 넣는다. 폰트가 2.8MB 라 결과 파일의 대부분을 차지한다.

심층 검증은 Claude Design 런타임이 부모 창으로 대신 호출해 주는 기능이라
파일 하나로 떼어내면 쓸 수 없다. 버튼을 지우지 않고, 눌렀을 때 왜 안 되는지
말해 주도록 바꾼다. 아무 말 없이 실패하면 고장 난 것으로 보인다.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path

MIME = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
        ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml"}

OFFLINE_NOTE = (
    "이 파일은 내려받아 혼자 열어 보는 사본입니다. 심층 검증은 Claude Design "
    "안에서만 돌아갑니다. 나머지 화면은 모두 실제 수집 자료입니다."
)

# 화면은 추론이 실패하면 "다시 실행해 주세요" 라고 적는다. 사본에서는 몇 번을
# 눌러도 되지 않으므로 이유를 적어 준다. 문구는 마크업에 두 번 들어 있다.
GENERIC_ERROR = "추론 요청이 실패했습니다. 다시 실행해 주세요."


def inline_fonts(css: str, css_dir: Path) -> tuple[str, int]:
    """CSS 의 url(...) 을 base64 로 바꾼다."""
    n = 0

    def swap(m):
        nonlocal n
        raw = m.group(1).strip("\"'")
        if raw.startswith(("data:", "http")):
            return m.group(0)
        f = (css_dir / raw).resolve()
        if not f.exists():
            print(f"  경고. {raw} 를 찾지 못해 그대로 둔다")
            return m.group(0)
        mime = MIME.get(f.suffix.lower(), "application/octet-stream")
        n += 1
        b64 = base64.b64encode(f.read_bytes()).decode()
        return f"url(data:{mime};base64,{b64})"

    return re.sub(r"url\(([^)]+)\)", swap, css), n


def bundle(html: str, assets: Path) -> tuple[str, dict]:
    stats = {"css": 0, "js": 0, "font": 0}

    def css_tag(m):
        href = m.group(1)
        f = (assets / href).resolve()
        if not f.exists():
            print(f"  경고. {href} 가 없다. 링크를 남긴다")
            return m.group(0)
        css, nf = inline_fonts(f.read_text(encoding="utf-8"), f.parent)
        stats["css"] += 1
        stats["font"] += nf
        return f"<style>\n{css}\n</style>"

    html = re.sub(r'<link rel="stylesheet" href="([^"]+)">', css_tag, html)

    def js_tag(m):
        src = m.group(1)
        f = (assets / src.lstrip("./")).resolve()
        if not f.exists():
            print(f"  경고. {src} 가 없다. 태그를 남긴다")
            return m.group(0)
        stats["js"] += 1
        # </script> 가 글자로 들어 있으면 거기서 태그가 닫힌다.
        body = f.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
        return f"<script>\n{body}\n</script>"

    html = re.sub(r'<script src="([^"]+)"></script>', js_tag, html)
    return html, stats


def soften_llm(html: str) -> tuple[str, int]:
    """심층 검증이 조용히 실패하지 않고 이유를 말하게 한다."""
    call = "const text = await window.claude.complete("
    if call not in html:
        raise SystemExit("심층 검증 호출 자리를 찾지 못했다")
    guard = ("const text = await (window.claude && window.claude.complete "
             "? window.claude.complete : () => { throw new Error("
             + repr(OFFLINE_NOTE) + ") })(")
    html = html.replace(call, guard)

    n = html.count(GENERIC_ERROR)
    if n == 0:
        raise SystemExit("추론 실패 문구를 찾지 못했다. 화면 구조가 바뀌었다")
    html = html.replace(GENERIC_ERROR, OFFLINE_NOTE)
    return html, n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="패치가 끝난 .html")
    ap.add_argument("--assets", type=Path, required=True,
                    help="support.js 와 _ds 가 있는 폴더")
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)

    html = args.source.read_text(encoding="utf-8")
    before = len(html.encode())
    html, stats = bundle(html, args.assets)
    html, n_err = soften_llm(html)

    left = re.findall(r'(?:src|href)="(?!data:|http|#)([^"]+)"', html)
    if left:
        print(f"  주의. 아직 바깥 파일을 가리킨다: {sorted(set(left))[:5]}")

    args.out.write_text(html, encoding="utf-8")
    size = len(html.encode())
    print(f"CSS {stats['css']}개, JS {stats['js']}개, 폰트 {stats['font']}개를 넣었다")
    print(f"심층 검증 오류 문구 {n_err}곳을 사본용 설명으로 교체")
    print(f"{before / 1024:.0f}KB -> {size / 1024 / 1024:.1f}MB")
    print(f"\n{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
