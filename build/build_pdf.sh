#!/bin/bash
# 중간보고서 Word 와 PDF 생성.
#
# PDF 는 Chrome 헤드리스로 뽑는다. LibreOffice 의 직접 PDF 변환은 이 환경에서
# 한글 글꼴을 전혀 잡지 못해 본문이 통째로 비어 나온다. LibreOffice 는 구조를
# HTML 로 꺼내는 데만 쓰고, 글꼴은 파일 경로로 직접 지정한다.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PY=./.venv/bin/python
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NAME="중간보고서_김도은_202220697"

echo "1/4  Word 생성 (맑은 고딕)"
$PY build/make_report.py >/dev/null

echo "2/4  PDF 용 사본 생성 (NanumGothic)"
REPORT_FONT=NanumGothic REPORT_OUT=_pdf_src.docx $PY build/make_report.py >/dev/null

echo "3/4  구조를 HTML 로 추출"
rm -rf build/html && mkdir -p build/html
soffice --headless --convert-to html --outdir build/html build/_pdf_src.docx >/dev/null 2>&1
$PY build/print_css.py >/dev/null

echo "4/4  Chrome 으로 PDF 출력"
HTML=$(ls build/html/*.html)
URL="file://$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$PWD/$HTML")"
"$CHROME" --headless --disable-gpu --no-sandbox --allow-file-access-from-files \
  --no-pdf-header-footer --print-to-pdf="build/$NAME.pdf" "$URL" 2>&1 | grep -i "bytes written" || true
rm -f build/_pdf_src.docx

$PY - <<'CHECK'
import re
p = "build/중간보고서_김도은_202220697.pdf"
d = open(p, "rb").read()
pages = len(re.findall(rb"/Type\s*/Page[^s]", d))
imgs = len(re.findall(rb"/Subtype\s*/Image", d))
fonts = sorted({f.decode("latin1").split("+")[-1] for f in re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-,\.]+)", d)})
print(f"완료  {pages}쪽, 그림 {imgs}장, 글꼴 {fonts}")
CHECK
