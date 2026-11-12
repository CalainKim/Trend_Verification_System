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


# 폰 배치. 원본은 넓은 화면용 세 칸 구성이라 폰에서는 왼쪽 아이콘 줄이 72px 을
# 차지하고, 아래 상태 줄과 열린 패널이 본문을 찌그러뜨린다. 원본이 인라인 스타일로
# 그리므로 고정된 기준점(nav 의 aria-label, PillNavV 의 클래스)으로 고른다.
#   아이콘 줄      화면 아래 탭 막대로. 그룹 이름과 로고, 명령 창 버튼은 숨긴다
#   아래 상태 줄   숨긴다
#   탐색 패널      본문을 밀지 않고 위에 겹쳐 뜨는 판으로
NAV = 'nav[aria-label="작업 공간"]'
MOBILE_CSS = """
<style id="tc-musinsa-mobile">
@media (max-width:760px){
  div:has(> div > @NAV){grid-template-rows:minmax(0,1fr)!important}
  div:has(> div > @NAV) > div:nth-child(2){display:none!important}

  @NAV{
    position:fixed!important;left:0;right:0;bottom:0;z-index:30;
    width:auto!important;height:calc(64px + env(safe-area-inset-bottom))!important;
    padding:0 6px env(safe-area-inset-bottom)!important;
    flex-direction:row!important;align-items:center!important;justify-content:center!important;
    border-right:0!important;border-top:1px solid var(--color-hairline)!important;
    background:rgba(250,250,250,.84)!important;
    -webkit-backdrop-filter:blur(22px) saturate(170%);backdrop-filter:blur(22px) saturate(170%);
  }
  @NAV > img, @NAV > span, @NAV > button{display:none!important}
  @NAV .pnv{flex-direction:row;width:100%}
  @NAV .pnv__bar{width:100%;padding:0;background:transparent;box-shadow:none}
  @NAV .pnv__list{flex-direction:row;justify-content:space-around;align-items:center;gap:0}
  @NAV .pnv__grp, @NAV .pnv__sep, @NAV .pnv__glide{display:none!important}
  @NAV .pnv__item{width:44px;height:44px;overflow:hidden}
  @NAV .pnv__item[aria-current="page"]{background:var(--color-ink);color:#fff}
  @NAV + div, @NAV ~ div{padding-bottom:calc(64px + env(safe-area-inset-bottom))}

  div:has(> @NAV) > aside{
    position:fixed!important;left:0;top:0;bottom:calc(64px + env(safe-area-inset-bottom));z-index:28;
    width:min(86vw,340px)!important;max-width:none!important;
    background:rgba(250,250,250,.9)!important;
    -webkit-backdrop-filter:blur(26px) saturate(160%);backdrop-filter:blur(26px) saturate(160%);
    box-shadow:0 24px 70px rgba(0,0,0,.28);
  }
  /* 본문 뒤에 오는 패널(오른쪽 속성)은 오른쪽에서 뜬다 */
  div:has(> @NAV) > div ~ aside{left:auto!important;right:0}
}
</style>
""".replace("@NAV", NAV)

# 홈 화면 앱(PWA) 설치 정보. 랜딩과 로그인에도 같은 것이 들어 있다
PWA_HEAD = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#f5f5f5">
<link rel="apple-touch-icon" href="/assets/pwa/apple-touch-icon.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="TrendCheck">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<script>
if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
</script>
"""

VIEWPORT_OLD = '<meta name="viewport" content="width=device-width, initial-scale=1">'
VIEWPORT_NEW = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'


def apply(html: str) -> tuple[str, dict]:
    """디자인 HTML 의 색을 모니터 테마 색으로 바꾸고 테마 CSS 를 넣는다. 이미 바꾼 파일이면 그대로 둔다."""
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
    html = html[:i] + THEME_CSS + MOBILE_CSS + PWA_HEAD + html[i:]
    # 아이폰 아래쪽 홈 막대 영역까지 쓰려면 viewport-fit=cover 가 있어야 한다
    html = html.replace(VIEWPORT_OLD, VIEWPORT_NEW, 1)
    stats["css"] = 1
    return html, stats


def main(argv: list[str]) -> int:
    """파일 하나를 받아 테마를 입히고 몇 곳을 바꿨는지 알려 준다."""
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
