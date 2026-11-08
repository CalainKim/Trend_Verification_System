"""묶은 모니터(build/web/app/index.html)에 랜딩과 같은 무신사 색감을 입힌다.

    python scripts/apply_monitor_theme.py build/web/app/index.html

모니터 원본(design/Trend Monitor v9.dc.html)은 Claude Design 에서 다시 받아오는
파일이라 손으로 고치면 다음에 받을 때 되돌아간다. 그래서 가운뎃점을 지우고
모델을 바꾸는 것과 같은 이유로 빌드할 때 덧씌운다.

하는 일은 둘이다.
  1. 디자인 시스템 토큰(--color-*)을 무신사 흑백으로 다시 정의한다.
     모니터는 거의 모든 색을 이 토큰으로 쓰므로 여기서 대부분이 바뀐다.
  2. 토큰을 거치지 않고 박혀 있는 따뜻한 회색과 주황을 같은 계열로 바꾼다.

색 체계는 랜딩과 같다.
  바탕과 글자   중립 흑백. 노란기 도는 회색을 쓰지 않는다
  버튼         검정. 주황 버튼을 쓰지 않는다
  확정, 긍정   무신사 파랑 #245eff
  상승, 오류   무신사 할인 빨강 #f31110
  질감         바탕에 옅은 빛을 깔고 카드와 패널을 반투명 간유리로
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MARK = 'id="tc-musinsa-theme"'

# 런타임이 디자인 시스템 스타일을 나중에 넣어도 이기도록 html:root 로 한 단계 높인다
THEME_CSS = """
<style id="tc-musinsa-theme">
html:root{
  --color-primary:#111111;
  --color-primary-active:#000000;
  --color-on-primary:#ffffff;
  --color-canvas:rgba(245,245,245,.78);
  --color-canvas-soft:rgba(250,250,250,.62);
  --color-surface-card:rgba(255,255,255,.72);
  --color-surface-strong:#ebebeb;
  --color-hairline:rgba(0,0,0,.08);
  --color-hairline-soft:rgba(0,0,0,.05);
  --color-hairline-strong:rgba(0,0,0,.16);
  --color-ink:#111111;
  --color-body:#454545;
  --color-body-strong:#111111;
  --color-muted:#767676;
  --color-muted-soft:#9e9e9e;
  --color-timeline-thinking:#cfcfcf;
  --color-timeline-grep:#b8b8b8;
  --color-timeline-read:#a0a0a0;
  --color-timeline-edit:#c6c6c6;
  --color-timeline-done:#245eff;
  --color-semantic-success:#245eff;
  --color-semantic-error:#f31110;
}
/* 유리 뒤에 비칠 옅은 빛. 화면에 붙어 있어 스크롤해도 움직이지 않는다 */
html{background:#f3f3f3}
html::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:
    radial-gradient(600px 420px at 8% 12%,rgba(36,94,255,.10),transparent 70%),
    radial-gradient(700px 520px at 92% 88%,rgba(0,0,0,.06),transparent 70%),
    radial-gradient(520px 400px at 70% 10%,rgba(200,210,255,.18),transparent 70%);}
body{background:transparent!important}
/* 카드와 패널: 반투명 간유리. 원본이 인라인 스타일로 칠하므로 그 글자로 고른다 */
[style*="background:var(--color-surface-card)"],[style*="background: var(--color-surface-card)"]{
  -webkit-backdrop-filter:blur(14px) saturate(160%);backdrop-filter:blur(14px) saturate(160%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 1px 2px rgba(0,0,0,.04);
}
[style*="background:var(--color-canvas-soft)"],[style*="background: var(--color-canvas-soft)"]{
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%);
}
/* 투명도를 줄여 달라는 설정이면 유리 대신 단색으로 */
@media (prefers-reduced-transparency:reduce){
  html:root{--color-canvas:#f5f5f5;--color-canvas-soft:#fafafa;--color-surface-card:#ffffff}
}
</style>
"""

# 토큰을 거치지 않고 박혀 있는 색. 따뜻한 회색은 중립 회색으로, 주황과 초록은 무신사 색으로
HEX_MAP = {
    "#f54e00": "#111111", "#d04200": "#000000",
    "#2b67c2": "#245eff", "#cf2d56": "#f31110", "#1f8a65": "#245eff",
    "#f3f1ec": "#f2f2f2", "#f7f7f4": "#f5f5f5", "#fafaf7": "#fafafa", "#e6e5e0": "#ebebeb",
    "#cfcdc4": "#d4d4d4", "#bdb8ae": "#bdbdbd", "#a09c92": "#a0a0a0", "#9fc9a2": "#b8b8b8",
    "#8f8a80": "#8a8a8a", "#807d72": "#767676", "#5a5852": "#454545", "#3b3935": "#333333",
    "#33312d": "#2a2a2a", "#26251e": "#111111", "#252421": "#1a1a1a", "#1b1a18": "#111111",
}
RGB_MAP = {
    "rgba(38,37,30,": "rgba(0,0,0,",
    "rgba(90,88,82,": "rgba(80,80,80,",
    "rgba(31,138,101,": "rgba(36,94,255,",
    "rgba(245,78,0,": "rgba(17,17,17,",
}


def apply(html: str) -> tuple[str, dict]:
    stats = {"hex": 0, "rgba": 0, "css": 0}
    if MARK in html:
        return html, stats
    for a, b in HEX_MAP.items():
        n = len(re.findall(re.escape(a), html, flags=re.I))
        if n:
            html = re.sub(re.escape(a), b, html, flags=re.I)
            stats["hex"] += n
    for a, b in RGB_MAP.items():
        n = html.count(a)
        html = html.replace(a, b)
        stats["rgba"] += n
    i = html.lower().rfind("</head>")
    if i == -1:
        raise SystemExit("</head> 를 찾지 못했다. 테마를 넣을 자리가 없다")
    html = html[:i] + THEME_CSS + html[i:]
    stats["css"] = 1
    return html, stats


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    p = Path(argv[1])
    html, stats = apply(p.read_text(encoding="utf-8"))
    p.write_text(html, encoding="utf-8")
    print(f"  색 바꿈 {stats['hex']}곳, 반투명 색 {stats['rgba']}곳, 테마 {'넣음' if stats['css'] else '이미 있음'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
