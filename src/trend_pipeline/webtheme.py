"""대시보드 공통 테마.

페이지가 둘 이상이 되면서 CSS 를 공유한다. 색은 명도·색각 대비 검증을 거친
값이라 임의로 바꾸지 않는다. 라이트/다크 각각 따로 고른 단계다.
"""

from __future__ import annotations

# 범주형 팔레트 슬롯 1~3 (light, dark). 전체 쌍 검증 통과한 조합.
SERIES = (("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"))

_LIGHT = """
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b; --up:#006300;
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a;
  --pos:#2a78d6; --neg:#d03b3b; --mid:#f0efec;
"""

_DARK = """
  color-scheme: dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b; --up:#0ca30c;
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
  --pos:#3987e5; --neg:#d03b3b; --mid:#383835;
"""

CSS = f""":root {{{_LIGHT}}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{{_DARK}}} }}
:root[data-theme="dark"] {{{_DARK}}}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--page); color:var(--ink);
  font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:1040px; margin:0 auto; padding:32px 20px 72px; }}
h1 {{ font-size:21px; margin:0 0 4px; letter-spacing:-0.01em; }}
h2 {{ font-size:15px; margin:0 0 2px; }}
h3 {{ font-size:14px; margin:0 0 8px; }}
.sub {{ color:var(--ink-2); font-size:13px; margin:0; }}
.note {{ color:var(--muted); font-size:12.5px; margin:6px 0 0; }}
section {{ margin-top:28px; }}
.card {{ background:var(--surface); border:1px solid var(--border);
  border-radius:10px; padding:18px 20px; margin-top:10px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:10px; margin-top:14px; }}
.kpi {{ background:var(--surface); border:1px solid var(--border);
  border-radius:10px; padding:14px 16px; }}
.kpi .label {{ color:var(--muted); font-size:12px; }}
.kpi .value {{ font-size:26px; line-height:1.2; margin-top:2px; }}
.kpi .value.warn {{ color:var(--critical); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; font-weight:600; color:var(--muted); font-size:12px;
  padding:0 10px 7px 0; border-bottom:1px solid var(--grid); white-space:nowrap; }}
td {{ padding:8px 10px 8px 0; border-bottom:1px solid var(--grid); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
td.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
.up {{ color:var(--up); }} .down {{ color:var(--critical); }}
.tag {{ font-size:11px; border:1px solid var(--border); border-radius:4px;
  padding:1px 5px; color:var(--ink-2); white-space:nowrap; }}
a {{ color:inherit; text-decoration:none; border-bottom:1px solid var(--border); }}
a:hover {{ border-bottom-color:var(--ink-2); }}
.scroll {{ overflow-x:auto; }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; margin:0 0 10px;
  font-size:12.5px; color:var(--ink-2); }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; }}
.swatch {{ width:14px; height:3px; border-radius:2px; flex:none; }}
.banner {{ border:1px solid var(--warning); border-left-width:3px; border-radius:8px;
  padding:10px 14px; margin-top:10px; font-size:13px; color:var(--ink-2);
  background:var(--surface); }}
.banner strong {{ color:var(--ink); }}
.nav {{ display:flex; gap:14px; margin:10px 0 0; font-size:13px; }}
.nav a {{ border:none; color:var(--ink-2); }}
.nav a.on {{ color:var(--ink); font-weight:600; }}
#tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
  background:var(--surface); color:var(--ink); border:1px solid var(--border);
  border-radius:7px; padding:7px 10px; font-size:12.5px; max-width:280px;
  box-shadow:0 4px 14px rgba(0,0,0,.12); z-index:20; }}
footer {{ margin-top:40px; color:var(--muted); font-size:12px; line-height:1.7; }}
"""

TOOLTIP_JS = """
(function () {
  var tip = document.getElementById('tip');
  if (!tip) return;
  function show(e, t) {
    tip.textContent = t; tip.style.opacity = 1;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + tip.offsetWidth > innerWidth - 8) x = e.clientX - tip.offsetWidth - 14;
    if (y + tip.offsetHeight > innerHeight - 8) y = e.clientY - tip.offsetHeight - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  document.querySelectorAll('[data-tip]').forEach(function (el) {
    el.addEventListener('pointerenter', function (e) { show(e, el.dataset.tip); });
    el.addEventListener('pointermove', function (e) { show(e, el.dataset.tip); });
    el.addEventListener('pointerleave', function () { tip.style.opacity = 0; });
  });
})();
"""


def nav(current: str) -> str:
    items = [("index.html", "수집 현황"), ("cases.html", "케이스 분석")]
    return '<div class="nav">' + "".join(
        f'<a href="{href}"{" class=\"on\"" if href == current else ""}>{label}</a>'
        for href, label in items) + "</div>"
