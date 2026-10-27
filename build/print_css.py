#!/usr/bin/env python3
"""LibreOffice 가 내보낸 HTML 에 인쇄용 스타일을 주입한다.

본문 여백과 정렬은 LibreOffice 가 인라인으로 넣어 두므로 덮어쓰지 않는다.
글꼴만 파일 경로로 직접 지정한다. 이 환경의 LibreOffice 는 한글 글꼴을
전혀 잡지 못해 PDF 본문이 통째로 비어 나오기 때문이다.
"""
from pathlib import Path
import sys

F = "/Users/kim_doeun/Library/Fonts"
CSS = f"""
<style>
@font-face {{ font-family: "RPT"; font-weight: 400;
  src: url("file://{F}/NanumGothic-Regular.ttf") format("truetype"); }}
@font-face {{ font-family: "RPT"; font-weight: 700;
  src: url("file://{F}/NanumGothic-Bold.ttf") format("truetype"); }}
@page {{ size: A4; margin: 23mm 25mm; }}
html, body, p, td, th, li, div, span, h1, h2, h3, h4, b, strong, i, em, font {{
  font-family: "RPT", sans-serif !important; }}
html, body {{ font-size: 10pt; line-height: 1.55; color: #15181d; }}
p[align="center"] {{ text-align: center !important; }}
p[align="right"]  {{ text-align: right !important; }}
h1 {{ font-size: 15pt; page-break-after: avoid; }}
h2 {{ font-size: 12.5pt; page-break-after: avoid; }}
h3 {{ font-size: 11pt; page-break-after: avoid; }}
img {{ max-width: 100%; height: auto; page-break-inside: avoid; }}
table {{ border-collapse: collapse; width: 100%; page-break-inside: avoid; font-size: 9pt; }}
td, th {{ border: 1px solid #c9c6c0; padding: 5pt 7pt; vertical-align: top; }}
p {{ orphans: 2; widows: 2; }}
</style>
"""

def main(html_dir="build/html"):
    h = next(Path(html_dir).glob("*.html"))
    s = h.read_text(encoding="utf-8")
    if "RPT" not in s:
        h.write_text(s.replace("</head>", CSS + "</head>"), encoding="utf-8")
    print(f"스타일 주입: {h}")
    return h

if __name__ == "__main__":
    main(*sys.argv[1:])
