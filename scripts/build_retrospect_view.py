#!/usr/bin/env python3
"""회고 화면을 파일 하나로 만든다.

    ./.venv/bin/python scripts/build_retrospect_view.py

build/retrospect.json 을 HTML 안에 넣어 혼자 도는 파일로 만든다. 받는 쪽은
더블클릭만 하면 되고 인터넷도 필요 없다.

화면이 하는 일은 하나다. 과거 한 시점으로 돌아가 그때 오르고 있던 검색어를
보여 주고, 결과를 가린 채 먼저 찍어 보게 한다. 그다음 펼친다.

가리는 것이 핵심이다. 결과를 같이 보여 주면 "그러네" 로 끝나고, 가리고 찍게
하면 자기가 틀리는 것을 본다. 설득은 그쪽이 세다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>그때 뭐가 떴나</title>
<style>
:root{
  --bg:#faf9f7; --card:#fff; --ink:#1a1a1a; --mute:#6b6b6b; --line:#e5e3df;
  --up:#1b6b4f; --down:#9a3126; --hit:#1b6b4f; --miss:#9a3126; --accent:#1a1a1a;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#17171a; --card:#1f1f23; --ink:#f2f1ef; --mute:#a0a0a8; --line:#33333a;
  --up:#5fcfa2; --down:#e8897c; --hit:#5fcfa2; --miss:#e8897c; --accent:#f2f1ef;
  color-scheme:dark;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",
  "Noto Sans KR",sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 72px}
h1{font-size:22px;line-height:1.3;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--mute);font-size:13px;margin:0 0 20px}
.chips{display:flex;gap:7px;overflow-x:auto;padding:2px 0 10px;
  scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;border:1px solid var(--line);background:var(--card);
  color:var(--ink);border-radius:999px;padding:7px 13px;font-size:13px;
  cursor:pointer;font-variant-numeric:tabular-nums}
.chip[aria-pressed=true]{background:var(--accent);
  color:var(--bg);border-color:var(--accent)}
.sumbar{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;margin:4px 0 16px}
.sumbar b{font-size:19px;font-variant-numeric:tabular-nums}
.sumrow{display:flex;flex-wrap:wrap;gap:18px}
.sumrow div{font-size:13px;color:var(--mute)}
.sumrow b{display:block;color:var(--ink)}
.tools{display:flex;gap:8px;margin:0 0 14px;flex-wrap:wrap}
.btn{border:1px solid var(--line);background:var(--card);color:var(--ink);
  border-radius:9px;padding:8px 13px;font-size:13px;cursor:pointer}
.btn:hover{border-color:var(--mute)}
.score{font-size:13px;color:var(--mute);margin:0 0 14px;
  font-variant-numeric:tabular-nums}
.row{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:13px 15px;margin-bottom:9px}
.head{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.kw{font-weight:650;font-size:16px;letter-spacing:-.01em}
.geo{font-size:12px;color:var(--mute)}
.rise{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:650;
  color:var(--up)}
.meta{font-size:12px;color:var(--mute);margin-top:5px;
  font-variant-numeric:tabular-nums}
.guess{display:flex;gap:7px;margin-top:11px}
.guess .btn{flex:1;text-align:center}
.guess .btn[aria-pressed=true]{background:var(--accent);color:var(--bg);
  border-color:var(--accent)}
.ans{margin-top:11px;padding-top:11px;border-top:1px solid var(--line)}
.verdict{font-weight:650}
.verdict.p{color:var(--up)} .verdict.f{color:var(--down)}
.mark{font-size:12px;font-weight:650;margin-left:7px}
.mark.hit{color:var(--hit)} .mark.miss{color:var(--miss)}
.spark{display:block;width:100%;height:46px;margin-top:9px;overflow:visible}
.cap{font-size:11px;color:var(--mute);margin-top:4px;
  display:flex;justify-content:space-between;gap:10px}
.note{font-size:12px;color:var(--mute);background:var(--card);
  border:1px solid var(--line);border-radius:10px;padding:12px 14px;
  margin-top:22px}
.note p{margin:0 0 7px} .note p:last-child{margin:0}
</style></head><body><div class="wrap">
<h1>그때 뭐가 떴나</h1>
<p class="sub">과거 한 시점으로 돌아간다. 그때 오르고 있던 검색어를 보고
버틸지 사라질지 먼저 찍어 본다. 그다음 결과를 펼친다.</p>
<div class="chips" id="chips" role="group" aria-label="시점"></div>
<div class="sumbar"><div class="sumrow" id="sum"></div></div>
<div class="tools">
  <button class="btn" id="reveal">결과 다 펼치기</button>
  <button class="btn" id="reset">내 답 지우기</button>
</div>
<p class="score" id="score"></p>
<div id="list"></div>
<div class="note">
  <p><b>상승은 비율로 잰다.</b> 검색 지수는 요청 창 안에서 최댓값이 100 이
  되게 정규화한 상대값이라 차이의 절대 크기에 뜻이 없다.</p>
  <p><b>결과는 자료가 정한다.</b> 사람이 고르지 않는다. 확인 구간 평균이
  상승분의 절반 이상을 지키면 지속이다.</p>
  <p><b>작년 대비(yoy)가 1 에 가까우면 계절성이다.</b> 해마다 반복되는
  움직임이라 올해만의 신호가 아니다.</p>
  <p><b>기준 평균이 작으면 상승률을 믿기 어렵다.</b> 바닥에서 조금만 올라도
  몇백 퍼센트가 된다. 그런 행에는 표시를 붙였다.</p>
</div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
var D = JSON.parse(document.getElementById('data').textContent);
var M = D.moments, cur = 0, shown = {}, mine = {};

function fmt(d){ return d.slice(2).replace(/-/g, '.'); }

function spark(before, after){
  var pts = before.concat(after), n = pts.length;
  var vs = pts.map(function(p){ return p.v; })
              .filter(function(v){ return v !== null; });
  if (!vs.length) return '';
  var hi = Math.max.apply(null, vs), lo = 0;
  var W = 300, H = 46, pad = 3, span = (hi - lo) || 1;
  var x = function(i){ return pad + i * (W - pad * 2) / (n - 1); };
  var y = function(v){ return H - pad - (v - lo) / span * (H - pad * 2); };
  var seg = [], cura = [];
  pts.forEach(function(p, i){
    if (p.v === null) { if (cura.length) { seg.push(cura); cura = []; } return; }
    cura.push(x(i) + ',' + y(p.v));
  });
  if (cura.length) seg.push(cura);
  var cut = x(before.length - 1);
  var lines = seg.map(function(s){
    return '<polyline points="' + s.join(' ') + '" fill="none" ' +
           'stroke="currentColor" stroke-width="1.6" ' +
           'stroke-linejoin="round" stroke-linecap="round"/>';
  }).join('');
  // 관측과 확인을 가르는 지점. 세로 장식선을 넣지 않고 점으로만 표시한다.
  var dot = '<circle cx="' + cut + '" cy="' + y(pts[before.length - 1].v || 0) +
            '" r="2.8" fill="currentColor"/>';
  return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H +
         '" preserveAspectRatio="none" aria-hidden="true">' +
         lines + dot + '</svg>';
}

function chips(){
  document.getElementById('chips').innerHTML = M.map(function(m, i){
    return '<button class="chip" data-i="' + i + '" aria-pressed="' +
           (i === cur) + '">' + fmt(m.t_cut) + '</button>';
  }).join('');
}

function summary(){
  var m = M[cur];
  document.getElementById('sum').innerHTML =
    '<div>그때 오르고 있던 것<b>' + m.n_rise + '건</b></div>' +
    '<div>' + m.base_from.slice(0, 7).replace('-', '년 ') + '월부터 본 구간' +
    '<b>' + fmt(m.base_from) + ' ~ ' + fmt(m.detect_to) + '</b></div>' +
    '<div>결과를 확인한 구간<b>' + fmt(m.detect_to) + ' ~ ' +
    fmt(m.hold_to) + '</b></div>';
}

function score(){
  var m = M[cur], n = 0, hit = 0;
  m.rows.forEach(function(r){
    var g = mine[r.case_id];
    if (!g) return;
    n++;
    if (g === r.outcome) hit++;
  });
  var el = document.getElementById('score');
  if (!n) { el.textContent =
    '찍어 보면 여기에 당신의 적중률이 나온다. 이 시점의 실제 지속률은 ' +
    Math.round(m.persist_rate * 100) + '% 다.'; return; }
  el.textContent = '당신 ' + hit + '/' + n + '건 적중 (' +
    Math.round(hit / n * 100) + '%). 전부 지속으로 찍으면 ' +
    Math.round(m.persist_rate * 100) + '%, 전부 소멸로 찍으면 ' +
    Math.round((1 - m.persist_rate) * 100) + '% 다.';
}

function answer(r){
  var p = r.outcome === 'persist', g = mine[r.case_id];
  var mark = g ? '<span class="mark ' + (g === r.outcome ? 'hit' : 'miss') +
    '">' + (g === r.outcome ? '맞혔다' : '틀렸다') + '</span>' : '';
  return '<div class="ans"><span class="verdict ' + (p ? 'p' : 'f') + '">' +
    (p ? '버텼다' : '사라졌다') + '</span>' + mark +
    '<div class="meta">확인 구간 평균 ' +
    (r.hold_mean === null ? '없음' : r.hold_mean.toFixed(1)) +
    ' (기준 ' + r.base_mean.toFixed(1) + ')</div>' +
    spark(r.before, r.after) +
    '<div class="cap"><span>' + fmt(r.before[0].d) + '</span>' +
    '<span>점에서 가렸다</span>' +
    '<span>' + fmt(r.after[r.after.length - 1].d) + '</span></div></div>';
}

function list(){
  var m = M[cur];
  document.getElementById('list').innerHTML = m.rows.map(function(r){
    var id = r.case_id, open = shown[id], g = mine[id];
    var thin = r.base_mean < 5 ? '. 기준값이 작아 상승률을 믿기 어렵다' : '';
    var h = '<div class="row"><div class="head">' +
      '<span class="kw">' + r.keyword + '</span>' +
      '<span class="geo">' + r.geo + '</span>' +
      '<span class="rise">' + (r.rise_pct > 0 ? '+' : '') +
      r.rise_pct.toFixed(0) + '%</span></div>' +
      '<div class="meta">지수 ' + r.base_mean.toFixed(1) + ' 에서 ' +
      r.detect_mean.toFixed(1) + ' 로' +
      (r.yoy_ratio === null ? ', 작년 자료 없음'
        : ', 작년 대비 ' + r.yoy_ratio.toFixed(2) + '배') + thin + '</div>';
    if (!open) {
      h += '<div class="guess">' +
        '<button class="btn" data-g="persist" data-id="' + id +
        '" aria-pressed="' + (g === 'persist') + '">버틴다</button>' +
        '<button class="btn" data-g="fade" data-id="' + id +
        '" aria-pressed="' + (g === 'fade') + '">사라진다</button>' +
        '<button class="btn" data-open="' + id + '">결과</button></div>';
    } else {
      h += answer(r);
    }
    return h + '</div>';
  }).join('');
}

function draw(){ chips(); summary(); score(); list(); }

document.addEventListener('click', function(e){
  var t = e.target;
  if (t.dataset.i !== undefined) { cur = +t.dataset.i; draw(); return; }
  if (t.dataset.g) {
    var id = t.dataset.id;
    mine[id] = mine[id] === t.dataset.g ? null : t.dataset.g;
    // 목록을 통째로 다시 그리면 89건짜리 시점에서 탭할 때마다 화면이 튀고
    // 스크롤 자리를 잃는다. 누른 행의 버튼만 고친다.
    t.parentNode.querySelectorAll('[data-g]').forEach(function(b){
      b.setAttribute('aria-pressed', mine[id] === b.dataset.g);
    });
    score(); return;
  }
  if (t.dataset.open) {
    shown[t.dataset.open] = true;
    var row = t.closest('.row');
    var r = M[cur].rows.filter(function(x){
      return x.case_id === t.dataset.open; })[0];
    row.querySelector('.guess').outerHTML = answer(r);
    score(); return;
  }
  if (t.id === 'reveal') {
    M[cur].rows.forEach(function(r){ shown[r.case_id] = true; });
    draw(); return;
  }
  if (t.id === 'reset') { mine = {}; shown = {}; draw(); return; }
});

draw();
</script></body></html>
"""


def main(argv=None) -> int:
    """회고 자료를 HTML 한 장에 넣어 열어 볼 수 있게 만든다."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="build/retrospect.json")
    p.add_argument("-o", "--out", default=None)
    args = p.parse_args(argv)

    data = Path(args.data).read_text(encoding="utf-8")
    d = json.loads(data)
    n = sum(len(m["rows"]) for m in d["moments"])

    # </script> 가 자료 안에 있으면 스크립트 태그가 먼저 닫힌다. 키워드에
    # 그런 문자열이 들어올 일은 없지만, 들어오면 화면이 통째로 죽는다.
    if "</script" in data.lower():
        raise SystemExit("자료에 </script 가 있다. 그대로 넣으면 화면이 깨진다")

    html = PAGE.replace("__DATA__", data)
    out = Path(args.out) if args.out else Path(
        f"build/그때 뭐가 떴나 ({d['moments'][-1]['t_cut']}).html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"시점 {len(d['moments'])}개, 상승 {n}건")
    print(f"{out}  {out.stat().st_size / 1024:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
