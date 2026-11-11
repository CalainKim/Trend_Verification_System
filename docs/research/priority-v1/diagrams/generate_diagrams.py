"""Generate editable diagrams.net XML and matching SVG/PNG previews.

Requires Pillow only for PNG export. All positions and text are shared by the
draw.io and preview exporters; no remote service or model call is used.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
from html import escape
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H = 1600, 1140
INK = "#172C45"
MUTED = "#53677F"
BG = "#F4F7FB"
LINE = "#A6B6CA"
TEAL = "#087F77"
BLUE = "#285DAB"
PURPLE = "#7057A3"
FONT = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


class Page:
    def __init__(self, name, slug):
        self.name, self.slug = name, slug
        self.items = []
        self.rect("background", 0, 0, W, H, BG, BG, 0)

    def rect(self, key, x, y, w, h, fill="#FFFFFF", stroke="#D4DEEB", radius=18):
        self.items.append(dict(kind="rect", key=key, x=x, y=y, w=w, h=h,
                               fill=fill, stroke=stroke, radius=radius))

    def text(self, key, x, y, w, lines, size=22, color=INK, bold=False, step=None):
        if isinstance(lines, str):
            lines = lines.split("\n")
        self.items.append(dict(kind="text", key=key, x=x, y=y, w=w,
                               h=len(lines) * (step or size * 1.55), lines=lines,
                               size=size, color=color, bold=bold, step=step or size * 1.55))

    def edge(self, key, points, color=LINE, dashed=False):
        self.items.append(dict(kind="edge", key=key, points=points, color=color, dashed=dashed))

    def card(self, key, x, y, w, h, title, body, accent=BLUE, fill="#FFFFFF"):
        self.rect(key, x, y, w, h, fill)
        self.rect(key+"-accent", x, y+20, 5, 35, accent, accent, 0)
        self.text(key+"-title", x+22, y+21, w-44, title, 26, INK, True)
        self.text(key+"-body", x+22, y+74, w-44, body, 22, MUTED)

    def header(self, number, title, subtitle):
        self.rect("header", 0, 0, W, 159, INK, INK, 0)
        self.text("eyebrow", 60, 20, 1300, "EVIDENCE PRIORITY  /  " + number, 17, "#9DD7D1", True)
        self.text("title", 60, 55, 1480, title, 36, "#FFFFFF", True)
        self.text("subtitle", 60, 111, 1480, subtitle, 20, "#CEDBEB")


def architecture():
    p = Page("01 시스템 구조", "priority-architecture")
    p.header("01", "트렌드 후보의 근거 검토와 관찰 우선순위", "대상: 한국 20대 남성 상의 스타일  ·  과제: 현재 근거의 해석과 판단  ·  evidence-priority-v1")
    p.text("input-label", 60, 184, 1480, "근거 준비  |  기존 수집·검색 경로를 재사용하고, 검수 규칙을 명시한다", 23, TEAL, True)
    xs = [60, 440, 820, 1200]
    titles = ["01  후보 등록", "02  수집·정제", "03  근거 검수", "04  묶음 고정"]
    bodies = [
        ["스타일 정의·동의어", "판단 시점·대상 집단", "관심 변화는 검토 트리거"],
        ["네이버·과거 기록", "확보 가능한 공개 자료", "원문·출처·수집 시각 보존"],
        ["시점·연령·성별·단위", "재게시와 원생산자 구분", "반대 관측도 보존"],
        ["근거 ID와 입력 해시", "동일 자료를 비교군에 제공", "미래 결과·사람 평가 제외"],
    ]
    for i, (x, title, body) in enumerate(zip(xs, titles, bodies)):
        p.card("input-"+str(i), x, 235, 340, 194, title, body, TEAL)
    for i in range(3):
        p.edge("prepare-"+str(i), [(xs[i]+340, 331), (xs[i+1]-8, 331)], TEAL)
    p.edge("frozen-to-method", [(1370, 429), (1370, 481), (408, 481), (408, 543)], TEAL)
    p.rect("frozen-caption-bg", 670, 459, 320, 38, BG, BG, 0)
    p.text("frozen-caption", 691, 462, 300, "같은 근거 · 같은 출력 형식", 20, TEAL, True)

    p.rect("reasoning-panel", 60, 551, 700, 271, "#EEF3FB", "#BACDE7")
    p.text("reasoning-title", 84, 568, 652, "05  리즈닝 비교  |  새 과제 설계", 26, BLUE, True)
    p.rect("method-direct", 84, 619, 307, 112, "#FFFFFF", "#C7D6EB", 12)
    p.text("method-direct-title", 104, 634, 267, "기본 판정", 24, BLUE, True)
    p.text("method-direct-body", 104, 674, 267, "근거 → 판정과 설명", 20, MUTED)
    p.rect("method-structured", 411, 619, 325, 112, "#F7F3FC", "#D2C5E6", 12)
    p.text("method-structured-title", 431, 634, 285, "구조적 검토", 24, PURPLE, True)
    p.text("method-structured-body", 431, 673, 285, ["대상·출처·지지·반증", "불확실성 → 판정"], 19, MUTED, step=25)
    p.text("models", 84, 750, 652, "각 방법을 Claude와 Qwen에서 수행", 22, INK, True)
    p.text("settings", 84, 787, 652, "모델 내 설정·출력 예산 동일  /  신규 호출은 이번 범위 밖", 17, MUTED)

    p.card("priority-card", 820, 551, 350, 271, "06  우선순위 카드", ["PRIORITIZE · 우선 관찰", "DEPRIORITIZE · 낮춤", "HOLD · 부족·충돌", "근거 ID + 판단 변경 조건"], BLUE)
    p.card("human-check", 1230, 551, 310, 271, "07  사람 검토", ["두 명의 독립 평가", "원자료와 출력 대조", "최초 평가·합의 보존", "모델 답을 정답화하지 않음"], PURPLE)
    p.edge("reasoning-to-card", [(760, 686), (812, 686)], BLUE)
    p.edge("card-to-review", [(1170, 686), (1222, 686)], BLUE)

    p.card("existing-status", 60, 879, 466, 166, "환경 연결 확인", ["Claude / A40 실행·저장 경로 있음", "새 과제의 의미상 수행은 미검증"], TEAL, "#EAF7F4")
    p.card("new-status", 566, 879, 468, 166, "이번 산출물은 설계와 문서", ["새 판정·평가 기준과 평가 양식", "새 과제의 실행기 연동·본 실험은 후속"], BLUE, "#EEF3FB")
    p.card("future-status", 1074, 879, 466, 166, "후속 반응은 별도 기록", ["보류·우선순위 낮춤 후보도 추적", "4주 내 미확산을 실패로 판정하지 않음"], PURPLE, "#F6F1FB")
    p.text("footer", 60, 1080, 1480, "유의: 트리거는 상승 예고가 아니다. SNS 자동 수집 확대·모델 학습·새 유료 호출은 이번 범위에 포함하지 않는다.", 19, MUTED)
    return p


def evaluation():
    p = Page("02 검증과 사람 평가", "priority-evaluation")
    p.header("02", "같은 근거로 비교하고, 두 사람이 독립적으로 검증", "검증 대상: 출력과 원자료의 관계  ·  미래 유행의 적중률이나 내부 사고 과정의 정확성을 뜻하지 않음")
    p.text("sequence-label", 60, 184, 1480, "평가 순서  |  기준표 작성이 모델 출력 열람보다 먼저다", 23, TEAL, True)
    p.card("reference", 60, 236, 450, 284, "01  사전 근거 기준표", ["평가자 A와 B가 각각 원자료 검토", "확인 가능한 사실 / 중요한 반대 근거", "알려지지 않은 정보를 표시", "최초 기록 보존 후 공통 기준표 고정"], TEAL)
    p.card("blinded", 575, 236, 450, 284, "02  비교와 익명화", ["기본 판정 ↔ 구조적 검토", "Claude / Qwen 각각 같은 입력 사용", "모델명·비교군 이름을 가림", "입력·설정·방법 버전은 별도 보관"], BLUE)
    p.card("independent", 1090, 236, 450, 284, "03  독립 평가와 합의", ["A와 B가 서로의 평가를 보지 않음", "출처·수치·반증·판정 사유 확인", "불일치를 기록하고 근거로 논의", "합의 전 평가와 합의 결과를 분리"], PURPLE)
    p.edge("reference-to-blind", [(510, 377), (567, 377)], TEAL)
    p.edge("blind-to-review", [(1025, 377), (1082, 377)], BLUE)
    p.edge("review-to-report", [(1315, 520), (1315, 585)], PURPLE)
    p.text("metrics-label", 60, 556, 1100, "04  결과표  |  여러 지표를 함께 제시하고 임의의 종합 점수를 만들지 않는다", 23, BLUE, True)
    p.rect("metric-panel", 60, 612, 930, 384, "#FFFFFF", "#C6D4E6")
    p.text("metric-title", 84, 632, 882, "근거와 판단의 품질", 26, INK, True)
    rows = [
        ("주장 근거 충실도", "뒷받침되는 사실 주장 ÷ 검토한 사실 주장"),
        ("반대 근거 반영률", "적절히 다룬 반대 근거 ÷ 기준표의 중요 반대 근거"),
        ("중대한 오류 발생률", "수치·시점·대상 오류 또는 과도한 단정 사례 ÷ 전체"),
        ("판정·보류 적절성", "판정 사유와 제공된 근거의 일치 여부"),
        ("평가자 일치도", "합의 전 항목별 일치율과 판정 일치표"),
        ("실행 비용", "사례당 시간·토큰·API / GPU 비용"),
    ]
    for i, (left, right) in enumerate(rows):
        y = 689+i*46
        if i % 2 == 0:
            p.rect("metric-row-bg-"+str(i), 78, y-5, 894, 42, "#F6F8FC", "#F6F8FC", 0)
        p.text("metric-left-"+str(i), 94, y, 235, left, 21, INK, True)
        p.text("metric-right-"+str(i), 335, y, 627, right, 20, MUTED)

    p.rect("outcome-panel", 1030, 612, 510, 384, "#EEF3FB", "#C6D4E6")
    p.text("outcome-title", 1054, 632, 462, "전체 사례의 처리 결과", 26, INK, True)
    p.text("outcome-body", 1054, 689, 462, ["우선 관찰 / 우선순위 낮춤 / 보류", "형식 오류 / API 실패를 별도로 집계", "미평가·판정 불가도 숨기지 않고 표시", "분모가 없으면 0점 대신 해당 없음", "답변을 줄이거나 보류를 늘려 얻는", "지표 상승을 다른 지표와 함께 해석"], 22, MUTED, step=43)
    p.rect("acceptance", 60, 1029, 1480, 67, "#EAF7F4", "#C5E5DB", 12)
    p.text("acceptance-text", 80, 1048, 1440, "필수 점검: 미래 자료 차단 · 재게시 중복 · 수치/단위/기간 · 대상 집단 · 반대 근거 · 기술 실패와 HOLD 분리 · 과제 버전 분리", 20, TEAL, True)
    return p


def font(size, bold=False):
    path = FONT / ("malgunbd.ttf" if bold else "malgun.ttf")
    if not path.exists():
        raise RuntimeError("Set FONT to a Korean-capable font directory before export")
    return ImageFont.truetype(str(path), round(size))


def verify_layout(p):
    for item in p.items:
        if item["kind"] == "text":
            f = font(item["size"], item["bold"])
            for line in item["lines"]:
                width = f.getlength(line)
                if width > item["w"] + 1:
                    raise ValueError(f"Text overflows: {p.slug} {item['key']} {width:.1f} > {item['w']}: {line}")
        if item["kind"] != "edge":
            if item["x"] < 0 or item["y"] < 0 or item["x"]+item["w"] > W+1 or item["y"]+item["h"] > H+1:
                raise ValueError(f"Outside page: {item['key']}")


def export_preview(p):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(p.name)}">',
           '<style>text{font-family:"Malgun Gothic","Noto Sans KR",sans-serif}</style>']
    for item in p.items:
        t = item["kind"]
        if t == "rect":
            x,y,w,h,r = (item[k] for k in ("x","y","w","h","radius"))
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{item["fill"]}" stroke="{item["stroke"]}" stroke-width="1.5"/>')
            d.rounded_rectangle((x,y,x+w,y+h), radius=r, fill=item["fill"], outline=item["stroke"], width=2)
        elif t == "text":
            for i, line in enumerate(item["lines"]):
                x,y = item["x"], item["y"]+i*item["step"]
                svg.append(f'<text x="{x}" y="{y+item["size"]}" font-size="{item["size"]}" fill="{item["color"]}" font-weight="{700 if item["bold"] else 400}">{escape(line)}</text>')
                d.text((x,y), line, font=font(item["size"], item["bold"]), fill=item["color"], anchor="lt")
        else:
            pts = item["points"]
            dash = ' stroke-dasharray="7 5"' if item["dashed"] else ""
            svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in pts)}" fill="none" stroke="{item["color"]}" stroke-width="3" stroke-linejoin="round"{dash}/>')
            d.line(pts, fill=item["color"], width=3, joint="curve")
            x,y = pts[-1]; px,py = pts[-2]
            angle = math.atan2(y-py, x-px)
            tri = [(x,y),(x-11*math.cos(angle)+5*math.sin(angle),y-11*math.sin(angle)-5*math.cos(angle)),(x-11*math.cos(angle)-5*math.sin(angle),y-11*math.sin(angle)+5*math.cos(angle))]
            d.polygon(tri, fill=item["color"])
            svg.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a,b in tri)}" fill="{item["color"]}"/>')
    svg.append("</svg>")
    (OUT / (p.slug+".svg")).write_text("\n".join(svg), encoding="utf-8")
    im.save(OUT / (p.slug+".png"), optimize=True)


def export_drawio(pages):
    file = ET.Element("mxfile", host="app.diagrams.net", type="device", version="26.0.0")
    for p in pages:
        diagram = ET.SubElement(file, "diagram", id=p.slug, name=p.name)
        model = ET.SubElement(diagram, "mxGraphModel", dx=str(W), dy=str(H), grid="1", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(W), pageHeight=str(H), math="0", shadow="0", background=BG)
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        for a in p.items:
            kind = a["kind"]
            if kind == "rect":
                style = f'rounded={int(a["radius"]>0)};arcSize=12;whiteSpace=wrap;html=0;fillColor={a["fill"]};strokeColor={a["stroke"]};strokeWidth=1.5;'
                cell = ET.SubElement(root, "mxCell", id=a["key"], value="", style=style, vertex="1", parent="1")
                ET.SubElement(cell, "mxGeometry", x=str(a["x"]), y=str(a["y"]), width=str(a["w"]), height=str(a["h"]), **{"as":"geometry"})
            elif kind == "text":
                # Separate native text cells retain explicit line positioning.
                for i,line in enumerate(a["lines"]):
                    style = f'text;html=0;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontFamily=Malgun Gothic;fontSize={a["size"]};fontColor={a["color"]};fontStyle={int(a["bold"])};spacing=0;'
                    cell = ET.SubElement(root, "mxCell", id=a["key"]+"-"+str(i), value=line, style=style, vertex="1", connectable="0", parent="1")
                    ET.SubElement(cell,"mxGeometry",x=str(a["x"]),y=str(a["y"]+i*a["step"]),width=str(a["w"]),height=str(a["step"]),**{"as":"geometry"})
            else:
                style = f'edgeStyle=none;rounded=1;html=0;strokeColor={a["color"]};strokeWidth=3;endArrow=block;endFill=1;'
                if a["dashed"]: style += "dashed=1;dashPattern=7 5;"
                cell = ET.SubElement(root, "mxCell", id=a["key"], style=style, edge="1", parent="1")
                geom = ET.SubElement(cell,"mxGeometry",relative="1",**{"as":"geometry"})
                for name,pt in [("sourcePoint",a["points"][0]),("targetPoint",a["points"][-1])]:
                    ET.SubElement(geom,"mxPoint",x=str(pt[0]),y=str(pt[1]),**{"as":name})
                if len(a["points"])>2:
                    arr = ET.SubElement(geom,"Array",**{"as":"points"})
                    for x,y in a["points"][1:-1]: ET.SubElement(arr,"mxPoint",x=str(x),y=str(y))
    ET.indent(file, space="  ")
    ET.ElementTree(file).write(OUT/"evidence-priority-v1.drawio",encoding="UTF-8",xml_declaration=True)


if __name__ == "__main__":
    pages = [architecture(), evaluation()]
    for page in pages:
        verify_layout(page)
        export_preview(page)
    export_drawio(pages)
    print("Created 2 editable draw.io pages and 4 matching SVG/PNG previews.")
