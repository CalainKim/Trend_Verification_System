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
    "심층 검증을 쓰려면 Anthropic API 키가 필요합니다. 버튼을 다시 누르면 "
    "키를 물어봅니다. 키는 이 브라우저에만 저장되고 파일에는 들어가지 않습니다. "
    "나머지 화면은 키 없이도 모두 실제 수집 자료입니다."
)

# 화면은 Claude Design 런타임이 넣어 주는 window.claude.complete 를 부른다.
# 파일로 떼어내면 그 함수가 없다. 대신 브라우저가 Anthropic API 를 직접 부르게
# 한다. api.anthropic.com 은 anthropic-dangerous-direct-browser-access 헤더가
# 있으면 access-control-allow-origin: * 를 돌려주므로 file:// 에서도 된다.
#
# 키는 파일에 넣지 않는다. 이 파일은 남에게 보내는 것이라 키를 넣으면 받은 사람
# 누구나 꺼내 쓸 수 있고 과금은 파일을 만든 사람에게 간다. 보는 사람이 자기 키를
# 넣게 하고 그 브라우저에만 저장한다.
BROWSER_SHIM = """
<script>
(function () {
  if (window.claude && window.claude.complete) return;   // Claude Design 안이면 둔다
  var KEY = 'trendcheck-anthropic-key';
  function ask() {
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    if (saved) return saved;
    var k = window.prompt(
      ['심층 검증을 쓰려면 Anthropic API 키를 넣어 주세요.',
       'sk-ant- 로 시작합니다. 이 브라우저에만 저장되고 파일에는 들어가지 않습니다.',
       '지우려면 비워서 확인을 누르세요.'].join(String.fromCharCode(10)));
    if (k === null) return null;
    k = k.trim();
    try { k ? localStorage.setItem(KEY, k) : localStorage.removeItem(KEY); } catch (e) {}
    return k || null;
  }
  window.claude = {
    complete: async function (req) {
      var key = ask();
      if (!key) throw new Error('API 키가 없어 심층 검증을 실행하지 못했습니다.');
      var res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true'
        },
        body: JSON.stringify({
          model: req.model, max_tokens: req.max_tokens,
          system: req.system, messages: req.messages
        })
      });
      if (res.status === 401) {
        try { localStorage.removeItem(KEY); } catch (e) {}
        throw new Error('API 키가 거부됐습니다. 버튼을 다시 눌러 새 키를 넣어 주세요.');
      }
      if (!res.ok) throw new Error('API 호출이 실패했습니다 (HTTP ' + res.status + ').');
      var data = await res.json();
      if (data.stop_reason === 'refusal') throw new Error('모델이 응답을 거절했습니다.');
      // 생각 블록은 본문이 비어 있다. 글자가 있는 블록만 모은다.
      return (data.content || []).filter(function (b) { return b.type === 'text'; })
        .map(function (b) { return b.text; })
        .join(String.fromCharCode(10, 10));
    }
  };
})();
</script>
"""

# 화면은 추론이 실패하면 "다시 실행해 주세요" 라고 적는다. 사본에서는 몇 번을
# 눌러도 되지 않으므로 이유를 적어 준다. 문구는 마크업에 두 번 들어 있다.
GENERIC_ERRORS = ("추론 요청이 실패했습니다. 다시 실행해 주세요.",
                  "분석에 실패했습니다. 다시 실행해 주세요.")


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


# 검증 파트가 파일 하나로 판정을 만들어 보낼 수 있게 하는 패널. 화면 오른쪽
# 아래에 작은 버튼으로 붙는다. 디자인을 건드리지 않으려고 번들 단계에서 넣는다.
#
# 왜 필요한가. 화면의 급상승 목록은 이번 주 상품이고 벤치마크는 다른 주의
# 케이스다. 둘이 겹치지 않아 화면을 눌러서는 판정이 안 나온다. 그리고 화면의
# 사람 피드백은 그 브라우저에만 쌓여서 보낸 사람에게 돌아오지 않는다.
REVIEW_PANEL = r"""
<script>
(function () {
  var CASES = window.CASES;
  if (!CASES || !CASES.length) return;
  var KEY = 'trendcheck-verdicts';
  var SYS = [
    '너는 패션 후보의 관측 근거를 검토한다. 제공한 evidence 만 사실 근거로 쓴다.',
    '질문은 입력의 claim 에 적힌 것이다. 그 질문에만 답한다.',
    'WATCH 는 claim 이 묻는 일이 일어나겠다는 판단, NOT_SUPPORTED 는 일어나지',
    '않겠다는 판단, HOLD 는 어느 쪽도 고를 자료가 없다는 뜻이다. 관찰할 가치는',
    '있으나 유지 여부는 모르겠다는 WATCH 가 아니라 HOLD 다.',
    't_cut 이후 자료는 입력에 없다. 없는 기간을 추측하지 않는다.',
    '다른 말 없이 아래 JSON 만 출력한다.',
    '{"verdict":"WATCH 또는 HOLD 또는 NOT_SUPPORTED","summary":"한 문장"}'
  ].join(String.fromCharCode(10));

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } }
  function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} }

  var box = document.createElement('div');
  box.style.cssText = 'position:fixed;right:16px;bottom:44px;z-index:9999;' +
    'font-family:var(--font-sans),sans-serif;font-size:12px';
  function render() {
    var got = load(), n = Object.keys(got).length;
    box.innerHTML =
      '<div style="background:var(--color-surface-card,#fff);border:1px solid ' +
      'var(--color-hairline-strong,#ccc);border-radius:8px;padding:10px 12px;' +
      'box-shadow:0 2px 8px rgba(0,0,0,0.08);display:flex;gap:8px;align-items:center">' +
      '<span>판정 ' + n + '/' + CASES.length + '</span>' +
      '<button data-go style="border:1px solid var(--color-ink,#222);border-radius:6px;' +
      'background:var(--color-ink,#222);color:#fff;padding:4px 10px;cursor:pointer;' +
      'font:inherit">' + (n ? '이어서' : '판정 시작') + '</button>' +
      '<button data-dl style="border:1px solid var(--color-hairline-strong,#ccc);' +
      'border-radius:6px;background:transparent;padding:4px 10px;cursor:pointer;' +
      'font:inherit" ' + (n ? '' : 'disabled') + '>내려받기</button></div>';
    box.querySelector('[data-go]').onclick = run;
    box.querySelector('[data-dl]').onclick = download;
  }

  function download() {
    var blob = new Blob([JSON.stringify(load(), null, 1)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'verdicts.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function run() {
    var got = load();
    var todo = CASES.filter(function (c) { return !got[c.case_id]; });
    if (!todo.length) { alert('모든 케이스를 판정했습니다. 내려받아 보내 주세요.'); return; }
    var btn = box.querySelector('[data-go]');
    btn.disabled = true;
    for (var i = 0; i < todo.length; i++) {
      var c = todo[i];
      btn.textContent = (i + 1) + '/' + todo.length;
      try {
        var text = await window.claude.complete({
          model: 'claude-opus-5-5', max_tokens: 1000, system: SYS,
          messages: [{ role: 'user', content: JSON.stringify(c) }]
        });
        var m = text.match(/[{][^]*[}]/);
        var v = m ? JSON.parse(m[0]).verdict : null;
        if (['WATCH', 'HOLD', 'NOT_SUPPORTED'].indexOf(v) >= 0) {
          got[c.case_id] = v;
          save(got);
          render();
          btn = box.querySelector('[data-go]');
          btn.disabled = true;
          btn.textContent = (i + 1) + '/' + todo.length;
        }
      } catch (e) {
        alert('판정이 멈췄습니다: ' + e.message + String.fromCharCode(10) +
              '받은 만큼은 저장됐습니다. 다시 누르면 이어서 합니다.');
        break;
      }
    }
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { document.body.appendChild(box); render(); });
  } else { document.body.appendChild(box); render(); }
})();
</script>
"""


def inline_remote_images(html: str, timeout: float = 15.0) -> int:
    """화면에 박힌 29CM 사진 주소를 base64 로 바꾼다.

    주소를 그대로 두면 파일이 인터넷 없이는 사진을 못 띄운다. 미팅에서 와이파이가
    안 될 수 있으므로 안에 넣는다. 240px webp 는 한 장에 2.8KB 라 196장을 넣어도
    0.7MB 다. 받다가 실패한 장은 주소를 남겨 둔다. 그 자리는 인터넷이 있으면
    뜨고 없으면 비는데, 통째로 깨지는 것보다 낫다.
    """
    import requests

    urls = sorted(set(re.findall(r'"(https://img\.29cm\.co\.kr/[^"]+)"', html)))
    if not urls:
        return 0
    print(f"  사진 {len(urls)}장을 받는다")
    s = requests.Session()
    done = fail = 0
    for i, u in enumerate(urls, 1):
        try:
            r = s.get(u, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(r.status_code)
        except Exception:
            fail += 1
            continue
        mime = r.headers.get("content-type", "image/webp").split(";")[0]
        b64 = base64.b64encode(r.content).decode()
        html = html.replace(f'"{u}"', f'"data:{mime};base64,{b64}"')
        done += 1
        if i % 50 == 0 or i == len(urls):
            print(f"    {i}/{len(urls)}")
    if fail:
        print(f"  주의. {fail}장은 받지 못해 주소로 남겼다")
    return html, done


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
    # 브라우저가 API 를 직접 부를 수 있게 shim 을 넣는다. 화면 스크립트보다 먼저
    # 실행돼야 하므로 head 가 닫히기 전에 둔다.
    if "</head>" not in html:
        raise SystemExit("head 닫는 태그를 찾지 못했다. shim 을 넣을 자리가 없다")
    html = html.replace("</head>", BROWSER_SHIM + "</head>", 1)
    # 판정 패널은 CASES 와 window.claude 가 준비된 뒤에 돌아야 하므로 body 끝에 둔다.
    if "</body>" not in html:
        raise SystemExit("body 닫는 태그를 찾지 못했다. 판정 패널을 넣을 자리가 없다")
    html = html.replace("</body>", REVIEW_PANEL + "</body>", 1)

    n = sum(html.count(e) for e in GENERIC_ERRORS)
    if n == 0:
        raise SystemExit("추론 실패 문구를 찾지 못했다. 화면 구조가 바뀌었다")
    for e in GENERIC_ERRORS:
        html = html.replace(e, OFFLINE_NOTE)
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
    html, n_img = inline_remote_images(html)

    # {{ }} 는 화면이 그릴 때 채우는 자리표시자지 바깥 파일이 아니다.
    left = [u for u in re.findall(r'(?:src|href)="(?!data:|http|#)([^"]+)"', html)
            if "{{" not in u]
    remote_img = re.findall(r'src="(https://img\.29cm\.co\.kr/[^"]+)"', html)
    if remote_img:
        print(f"  주의. 사진 {len(remote_img)}장은 주소로 남아 인터넷이 있어야 뜬다")
    if left:
        print(f"  주의. 아직 바깥 파일을 가리킨다: {sorted(set(left))[:5]}")

    args.out.write_text(html, encoding="utf-8")
    size = len(html.encode())
    print(f"CSS {stats['css']}개, JS {stats['js']}개, 폰트 {stats['font']}개를 넣었다")
    print(f"심층 검증 오류 문구 {n_err}곳을 사본용 설명으로 교체")
    print("브라우저에서 API 를 직접 부르는 shim 을 넣었다 (키는 보는 사람이 입력)")
    print("판정 패널을 넣었다 (문제지를 돌리고 verdicts.json 으로 내려받기)")
    print(f"상품 사진 {n_img}장을 파일 안에 넣었다")
    print(f"{before / 1024:.0f}KB -> {size / 1024 / 1024:.1f}MB")
    print(f"\n{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
