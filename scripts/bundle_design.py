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
import json
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
          // 생각 분량도 max_tokens 에서 깎인다. effort 를 넘기지 않으면 모델이
          // 알아서 길게 생각하다 한도에 걸려 본문이 한 글자도 안 나온다.
          output_config: req.output_config || { effort: 'low' },
          system: req.system, messages: req.messages
        })
      });
      if (res.status === 401) {
        try { localStorage.removeItem(KEY); } catch (e) {}
        throw new Error('API 키가 거부됐습니다. 버튼을 다시 눌러 새 키를 넣어 주세요.');
      }
      if (!res.ok) {
        // 이유를 적지 않으면 화면이 "다시 실행해 주세요" 만 적고 끝난다.
        // 실제로 모델 이름이 사라져 404 가 나던 것을 그래서 못 찾았다.
        var err = await res.json().catch(function () { return {}; });
        var why = (err.error || {}).message || '';
        if (res.status === 404) {
          throw new Error('모델을 찾지 못했습니다 (' + req.model + '). ' + why);
        }
        throw new Error('API 호출이 실패했습니다 (HTTP ' + res.status + '). ' + why);
      }
      var data = await res.json();
      if (data.stop_reason === 'refusal') throw new Error('모델이 응답을 거절했습니다.');
      // 한도에 걸리면 본문이 잘린 채로 온다. 그대로 넘기면 부르는 쪽에서
      // JSON 파싱이 깨지고, 원인이 "JSON 이 이상하다" 로 보여서 못 찾는다.
      if (data.stop_reason === 'max_tokens') {
        throw new Error('응답이 max_tokens(' + req.max_tokens + ')에서 잘렸습니다.');
      }
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
  // window.CASES 는 x-dc 스크립트가 런타임에 의해 비동기로 평가된 뒤에 생긴다.
  // body 끝에서 바로 읽으면 아직 없어서 패널이 설치되지 않는다. 생길 때까지
  // 기다린다. 30초 안에 안 생기면 Claude Design 쪽이거나 문제지가 없는 것이다.
  var CASES = null;
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
    var bad = [], run_of_bad = 0;
    for (var i = 0; i < todo.length; i++) {
      var c = todo[i];
      btn.textContent = (i + 1) + '/' + todo.length;
      try {
        var text = await window.claude.complete({
          model: 'claude-opus-5-5', max_tokens: 4096,
          output_config: { effort: 'low' }, system: SYS,
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
        // 한 건이 실패해도 배치를 멈추지 않는다. 멈추면 다음에 눌러도 같은
        // 케이스부터 다시 시작해서 같은 자리에서 또 멈춘다. 되풀이해서
        // 실패하는 케이스 하나가 나머지 전부를 영영 막는다.
        bad.push(c.case_id + ': ' + e.message);
        run_of_bad++;
        if (run_of_bad >= 3) {
          alert('연달아 3건이 실패해 멈춥니다. 마지막 오류: ' + e.message +
                String.fromCharCode(10) +
                '받은 만큼은 저장됐습니다. 다시 누르면 이어서 합니다.');
          break;
        }
        continue;
      }
      run_of_bad = 0;
    }
    if (bad.length) {
      console.warn('판정하지 못한 케이스 ' + bad.length + '건', bad);
    }
    render();
  }

  // 런타임이 마운트하면서 body 를 갈아끼우면 붙여 둔 패널이 날아간다. 순서를
  // 맞추려 하기보다 떨어졌는지 보고 다시 붙인다. 상대가 언제 무엇을 바꿀지
  // 모르므로 이쪽이 단단하다. documentElement 에 붙여 body 교체를 피한다.
  // 런타임이 마운트하면서 body 를 갈아끼우면 붙여 둔 패널이 날아간다. 순서를
  // 맞추려 하기보다 떨어졌는지 보고 다시 붙인다. 상대가 언제 무엇을 바꿀지
  // 모르므로 이쪽이 단단하다. documentElement 에 붙여 body 교체를 피한다.
  function attach() {
    if (!box.isConnected) {
      document.documentElement.appendChild(box);
      render();
    }
  }
  var waited = 0;
  var timer = setInterval(function () {
    if (!CASES) {
      CASES = (window.CASES && window.CASES.length) ? window.CASES : null;
      waited += 300;
      if (!CASES) {
        if (waited > 30000) clearInterval(timer);
        return;
      }
    }
    attach();
  }, 300);
})();
</script>
"""


def inline_remote_images(html: str, timeout: float = 15.0) -> tuple[str, int]:
    """화면에 박힌 29CM 사진 주소를 base64 로 바꾼다.

    주소를 그대로 두면 파일이 인터넷 없이는 사진을 못 띄운다. 미팅에서 와이파이가
    안 될 수 있으므로 안에 넣는다. 240px webp 는 한 장에 2.8KB 라 196장을 넣어도
    0.7MB 다. 받다가 실패한 장은 주소를 남겨 둔다. 그 자리는 인터넷이 있으면
    뜨고 없으면 비는데, 통째로 깨지는 것보다 낫다.
    """
    import requests

    urls = sorted(set(re.findall(r'"(https://img\.29cm\.co\.kr/[^"]+)"', html)))
    if not urls:
        return html, 0
    print(f"  사진 {len(urls)}장을 받는다")
    s = requests.Session()
    done = fail = 0
    blobs: dict = {}
    for i, u in enumerate(urls, 1):
        try:
            r = s.get(u, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(r.status_code)
        except Exception:
            fail += 1
            continue
        mime = r.headers.get("content-type", "image/webp").split(";")[0]
        blobs[u] = f"data:{mime};base64," + base64.b64encode(r.content).decode()
        done += 1
        if i % 50 == 0 or i == len(urls):
            print(f"    {i}/{len(urls)}")
    if fail:
        print(f"  주의. {fail}장은 받지 못해 주소로 남겼다")
    if not blobs:
        return html, 0

    # 같은 사진이 여러 자리에 나온다. 상품 하나가 여러 속성에 걸려 P 에 중복으로
    # 들어가기 때문이다. 자리마다 base64 를 복사하면 196장이 428장 분량이 된다.
    # 사진은 한 번만 담고 자리에는 번호만 둔 뒤, 화면이 그릴 때 번호로 찾게 한다.
    index = {u: i for i, u in enumerate(sorted(blobs))}
    table = [blobs[u] for u in sorted(blobs)]
    for u, i in index.items():
        html = html.replace(f'"{u}"', f'"img:{i}"')
    lookup = (
        "\n<script>\n"
        "// 사진은 아래 표에 한 번만 담는다. 자리에는 img:번호 만 있고, 화면이\n"
        "// 그릴 때 이 함수가 바꿔 준다. 자리마다 복사하면 같은 사진이 두 번\n"
        "// 넘게 들어가 파일이 두 배가 된다.\n"
        "window.__IMG = " + json.dumps(table) + ";\n"
        "(function () {\n"
        "  function fix(el) {\n"
        "    var s = el.getAttribute('src') || '';\n"
        "    if (s.indexOf('img:') !== 0) return;\n"
        "    var v = window.__IMG[parseInt(s.slice(4), 10)];\n"
        "    if (v) el.setAttribute('src', v);\n"
        "  }\n"
        "  function sweep() { document.querySelectorAll('img[src^=\"img:\"]').forEach(fix); }\n"
        "  new MutationObserver(sweep).observe(document.documentElement,\n"
        "    { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });\n"
        "  sweep();\n"
        "})();\n</script>\n"
    )
    html = html.replace("</head>", lookup + "</head>", 1)
    return html, done


def bundle(html: str, assets: Path) -> tuple[str, dict]:
    stats = {"css": 0, "js": 0, "font": 0}

    # helmet은 DC가 다시 컴파일하는 템플릿이다. 그 안에 JS를 인라인하면
    # encodeCase가 코드의 camelCase까지 속성 이름으로 바꿔 실행을 깨뜨린다.
    # 외부 스크립트는 문서 head로 순서대로 옮긴 뒤 인라인한다.
    hoisted = []

    def move_script(m):
        hoisted.append(m.group(0))
        return ""

    html = re.sub(
        r"<helmet(?:\s[^>]*)?>.*?</helmet>",
        lambda m: re.sub(r'<script src="([^"]+)"></script>', move_script, m.group(0)),
        html, flags=re.S,
    )
    if hoisted:
        if "</head>" not in html:
            raise SystemExit("helmet 스크립트를 옮길 head 닫는 태그가 없다")
        html = html.replace("</head>", "\n".join(hoisted) + "\n</head>", 1)

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
        # DC 런타임은 현재 HTML을 다시 읽고 첫 <x-dc>부터 템플릿을 찾는다.
        # 외부 support.js를 인라인으로 옮기면 오류 문구 속 태그가 먼저
        # 잡힌다. JS 문자열/정규식에서 같은 문자로 해석되는 이스케이프로
        # 바꿔, 런타임 코드를 화면 템플릿으로 오인하지 않게 한다.
        body = re.sub(r"<(?=/?x-dc(?:\s|>))", lambda _: r"\x3c", body)
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
    ap.add_argument("--embed-key", action="store_true",
                    help="환경변수 ANTHROPIC_API_KEY 를 파일에 넣는다. 내 컴퓨터에서 "
                         "바로 쓰려는 사본에만 쓴다. 이 파일은 절대 남에게 보내지 "
                         "않는다. 파일 이름에 로컬 이 들어가야 한다")
    ap.add_argument("--skip-images", action="store_true",
                    help="상품 사진을 다운로드하지 않는다. 숫자와 화면은 오프라인으로 "
                         "만들고 사진은 원래 URL로 남긴다")
    args = ap.parse_args(argv)

    if args.embed_key:
        import os

        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key.startswith("sk-ant-"):
            raise SystemExit("ANTHROPIC_API_KEY 가 없거나 모양이 다르다. "
                             "set -a && . ./.env && set +a 로 불러와라")
        # 이름으로 구분하지 않으면 보낼 파일과 섞인다. 5.9MB 짜리를 카톡에 올릴
        # 때 둘 중 어느 것인지 파일 이름만 보고 알 수 있어야 한다.
        if "로컬" not in args.out.name:
            raise SystemExit("--embed-key 로 만드는 파일은 이름에 '로컬' 이 "
                             "들어가야 한다. 보낼 파일과 섞이면 키가 샌다")

    html = args.source.read_text(encoding="utf-8")
    before = len(html.encode())
    html, stats = bundle(html, args.assets)
    html, n_err = soften_llm(html)
    if args.skip_images:
        n_img = 0
        print("상품 사진 다운로드 생략 (--skip-images)")
    else:
        html, n_img = inline_remote_images(html)

    # {{ }} 는 화면이 그릴 때 채우는 자리표시자지 바깥 파일이 아니다.
    left = [u for u in re.findall(r'(?:src|href)="(?!data:|http|#)([^"]+)"', html)
            if "{{" not in u]
    remote_img = re.findall(r'src="(https://img\.29cm\.co\.kr/[^"]+)"', html)
    if remote_img:
        print(f"  주의. 사진 {len(remote_img)}장은 주소로 남아 인터넷이 있어야 뜬다")
    if left:
        print(f"  주의. 아직 바깥 파일을 가리킨다: {sorted(set(left))[:5]}")

    if args.embed_key:
        # shim 이 묻지 않고 바로 쓰도록 키를 심는다. 지우려면 브라우저 저장소를
        # 비우면 되고, 그러면 다시 묻는다.
        import os

        key = os.environ["ANTHROPIC_API_KEY"].strip()
        seed = ("\n<script>\n"
                "// 내 컴퓨터 전용 사본이다. 키가 들어 있으므로 남에게 보내지 않는다.\n"
                "try { localStorage.setItem('trendcheck-anthropic-key', "
                + json.dumps(key) + "); } catch (e) {}\n"
                "</script>\n")
        html = html.replace("</head>", seed + "</head>", 1)

    args.out.write_text(html, encoding="utf-8")
    if args.embed_key:
        print()
        print("  주의. 이 파일에는 API 키가 들어 있다. 카톡이나 메일로 보내지 마라.")
        print("  보낼 파일은 --embed-key 없이 따로 만든 것이다.")
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
