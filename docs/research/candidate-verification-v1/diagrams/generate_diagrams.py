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
W, H = 1800, 1490
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
        self.text("eyebrow", 60, 20, 1300, "CANDIDATE VERIFICATION  /  " + number, 17, "#9DD7D1", True)
        self.text("title", 60, 55, 1680, title, 36, "#FFFFFF", True)
        self.text("subtitle", 60, 111, 1680, subtitle, 20, "#CEDBEB")


def architecture():
    p = Page("01 후보 검증 구조", "candidate-architecture")
    p.header("01", "초기 신호에서 근거 검토와 판정 수정까지", "한국 20대 남성 상의 스타일  ·  candidate-verification-v1  ·  AI 권고와 사람의 최종 판단을 구분")
    p.text("section-input", 80, 184, 900, "근거 준비  |  시계열과 인터뷰 가설을 함께 검토", 23, TEAL, True)
    xs = [80, 650, 1220]
    p.card("signal", 80, 260, 500, 210, "01  시계열 초기 신호", ["관심 변화·지속·약화의 관측", "네이버·SNS 등에서 후보 발견", "시계열은 이후 판단의 실질적 근거"], TEAL)
    p.card("candidate", 650, 260, 500, 210, "02  후보와 판단 범위", ["스타일 정의·동의어·대상 집단", "판단 시점과 관측 범위 고정", "확인할 주장과 미확인 조건 명시"], TEAL)
    p.card("evidence", 1220, 260, 500, 210, "03  근거와 검수된 가설", ["시계열·과거 기록·원출처 묶음", "인터뷰 가설의 원문·출처 검수", "판단 시점의 검색 자료 묶음 고정"], TEAL)
    p.edge("signal-candidate", [(580,365),(642,365)],TEAL)
    p.edge("candidate-evidence", [(1150,365),(1212,365)],TEAL)
    p.edge("evidence-provisional",[(1470,470),(1470,515),(50,515),(50,710),(72,710)],TEAL)
    p.rect("frozen-note-bg",650,496,500,38,BG,BG,0)
    p.text("frozen-note",676,500,448,"미래 자료 제외 · 근거 ID와 버전 보존",20,TEAL,True)

    p.text("section-review",80,548,950,"검증 과정  |  질문과 반증을 거쳐 판단을 수정",23,BLUE,True)
    p.card("provisional",80,590,500,245,"04  잠정 판단",["현재 근거가 지지하는 설명 정리","관측 사실과 해석을 구분","판정의 전제와 불확실성 기록","검수된 가설도 반박 가능하게 사용"],BLUE,"#EEF3FB")
    p.card("questions",650,590,500,245,"05  AI의 추가 확인",["판단을 바꿀 수 있는 질문 선택","고정된 자료 묶음 안에서 검색","질문·선택 이유·검색 결과 기록","찾지 못한 사실은 미확인으로 유지"],BLUE,"#EEF3FB")
    p.card("counter",1220,590,500,245,"06  별도 반증 검토",["잠정 판단과 다른 설명을 점검","캠페인·재게시·대상 혼동 검토","누락된 반대 근거와 논리 비약 확인","수정할 주장과 남는 쟁점 기록"],PURPLE,"#F6F1FB")
    p.edge("provisional-questions",[(580,710),(642,710)],BLUE)
    p.edge("questions-counter",[(1150,710),(1212,710)],BLUE)
    p.edge("counter-recommendation",[(1470,835),(1470,884),(50,884),(50,1112),(72,1112)],PURPLE)
    p.rect("revision-note-bg",675,864,450,39,BG,BG,0)
    p.text("revision-note",697,868,406,"반증 수용 여부와 수정 이유를 보존",20,PURPLE,True)

    p.text("section-output",80,938,950,"권고와 결정  |  판단 결과와 변경 이력을 분리",23,BLUE,True)
    p.card("recommendation",80,990,500,245,"07  AI 검증 권고",["CONFIRM / HOLD / REJECT","근거·반증·부족한 정보와 연결","잠정 판단에서 바뀐 부분과 이유","추가 관측 시 재검토할 조건 제시"],BLUE)
    p.card("human",650,990,500,245,"08  사람의 최종 판단",["원자료와 AI의 설명을 대조","AI 권고 수용·수정 여부 기록","최종 판단과 이유를 별도 저장","AI의 동의를 시장 정답으로 삼지 않음"],PURPLE)
    p.card("new-cutoff",1220,990,500,245,"새 자료와 새 판단 시점",["후속 관측은 새 시점의 입력으로 등록","이전 근거·권고·사람 판단을 보존","새 판정과 변경 사유를 추가 기록","이전 결론을 덮어쓰지 않음"],TEAL,"#EAF7F4")
    p.edge("recommendation-human",[(580,1112),(642,1112)],BLUE)
    p.edge("human-new-cutoff",[(1150,1112),(1212,1112)],TEAL)
    p.edge("new-cutoff-loop",[(1470,1235),(1470,1273),(1760,1273),(1760,225),(900,225),(900,252)],TEAL)
    p.text("loop-label",1210,185,520,"새 시점의 후보 검토로 다시 연결",20,TEAL,True)

    p.rect("status",80,1312,1640,112,"#EEF3FB","#C6D4E6",16)
    p.text("demo-status",104,1333,780,"구현 확인 대상: 데모 흐름과 기록 연결",22,INK,True)
    p.text("effect-status",944,1333,748,"연구 검증 대상: 방법론과 판단 논리",22,INK,True)
    p.text("demo-detail",104,1373,780,"질문 선택·검색·반증·수정 이력이 남는지 확인",20,MUTED)
    p.text("effect-detail",944,1373,748,"실제 자료에서의 효과는 아직 측정하지 않음",20,MUTED)
    p.text("footer",80,1450,1640,"권고는 확보한 근거와 판단 시점에 조건부다. 근거가 부족하면 보류하며, 새로운 관측은 다음 판단 기록으로 연결한다.",19,MUTED)
    return p


def evaluation():
    p = Page("02 방법론과 논리 검증", "candidate-evaluation")
    p.header("02", "인터뷰 가설의 기여와 검증 과정의 논리를 비교", "같은 후보·같은 자료 묶음·같은 검증 흐름  ·  모델의 설명과 실제 근거를 대조")
    p.text("comparison-label",80,184,1600,"비교 설계  |  인터뷰 가설 제공 여부를 모델별로 비교",23,TEAL,True)
    p.card("controls",80,260,500,290,"공통으로 고정하는 것",["후보의 정의·대상·판단 시점","초기 근거와 추가 검색 자료 묶음","질문 선택·검색·반증·수정 절차","모델 내 실행 조건과 출력 형식","선택한 질문과 실제 검색 결과 보존"],TEAL)
    p.rect("matrix",650,260,1070,290,"#FFFFFF","#C6D4E6")
    p.text("matrix-label-provided",878,280,350,"인터뷰 가설 제공",24,BLUE,True)
    p.text("matrix-label-withheld",1294,280,360,"인터뷰 가설 미제공",24,PURPLE,True)
    for idx,(name,y) in enumerate([("Claude",338),("Qwen",441)]):
        p.text("model-"+str(idx),682,y+23,170,name,26,INK,True)
        p.rect("provided-"+str(idx),862,y,392,84,"#EEF3FB","#C7D6EB",12)
        p.text("provided-text-"+str(idx),886,y+26,344,"검수된 가설 + 공통 근거",21,BLUE)
        p.rect("withheld-"+str(idx),1270,y,420,84,"#F6F1FB","#D2C5E6",12)
        p.text("withheld-text-"+str(idx),1294,y+26,372,"같은 근거 · 가설 설명은 제외",21,PURPLE)

    p.rect("workflow",80,590,1640,103,"#EAF7F4","#C5E5DB",14)
    p.text("workflow-title",104,606,1590,"모든 조건에서 같은 검증 흐름을 수행",22,TEAL,True)
    p.text("workflow-body",104,646,1590,"잠정 판단 → AI의 추가 질문·검색 → 별도 반증 검토 → 수정된 CONFIRM / HOLD / REJECT 권고",24,INK)
    p.text("review-label",80,729,1640,"사람 평가  |  근거 기준표는 모델 출력을 보기 전에 작성",23,BLUE,True)
    p.card("reference",80,777,500,240,"사전 근거 기준표",["확인 가능한 사실·중요 반대 근거","미확인 정보와 허용할 해석의 범위","질문이 해결해야 할 쟁점을 정리","최초 기준표와 합의 기준표를 보존"],TEAL)
    p.card("blind-review",650,777,500,240,"두 명의 독립 검토",["모델명·인터뷰 제공 조건을 가림","서로의 평가를 보기 전에 판독","동일 원자료에서 주장과 이유 확인","가림만으로 완전한 맹검을 주장하지 않음"],BLUE)
    p.card("consensus",1220,777,500,240,"불일치와 합의 기록",["최초 평가와 합의 결과를 분리","불일치를 근거와 논리로 대조","합의되지 않은 쟁점도 보존","모델 답변 자체를 정답으로 채택하지 않음"],PURPLE)
    p.edge("reference-blind",[(580,896),(642,896)],TEAL)
    p.edge("blind-consensus",[(1150,896),(1212,896)],BLUE)

    p.text("checks-label",80,1054,1640,"검증하는 것  |  사실·반증·질문·수정의 연결을 확인",23,BLUE,True)
    checks=[("사실과 출처","주장·수치·시점·대상이 원자료와 맞는가"),("반대 근거","다른 설명과 불리한 관측을 다루었는가"),("추가 질문","판단을 바꿀 쟁점을 묻고 근거를 찾았는가"),("수정 논리","반증을 수용·기각한 이유가 일관적인가")]
    for i,(title,body) in enumerate(checks):
        x=80+i*420
        p.rect("check-"+str(i),x,1101,380,174,"#FFFFFF","#C6D4E6",16)
        p.text("check-title-"+str(i),x+22,1123,336,title,25,INK,True)
        if i==0: lines=["주장·수치·시점·대상이","원자료와 맞는가"]
        elif i==1: lines=["다른 설명과 불리한 관측을","다루었는가"]
        elif i==2: lines=["판단을 바꿀 쟁점을 묻고","근거를 찾았는가"]
        else: lines=["반증을 수용·기각한 이유가","일관적인가"]
        p.text("check-body-"+str(i),x+22,1170,336,lines,22,MUTED)
    p.rect("status",80,1320,1640,106,"#EEF3FB","#C6D4E6",14)
    p.text("status-title",104,1338,1590,"데모 동작 확인과 실제 연구 효과를 구분",23,INK,True)
    p.text("status-body",104,1378,1590,"흐름과 기록이 연결되어도 방법의 효과가 입증된 것은 아니다. 실제 자료의 비교·독립 평가 결과는 미측정이다.",22,MUTED)
    p.text("footer",80,1450,1640,"기술 실패·보류·미평가를 구분한다. 사실 확인, 반증, 질문 선택, 판정 수정의 근거를 함께 검토한다.",19,MUTED)
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
    ET.ElementTree(file).write(OUT/"candidate-verification-v1.drawio",encoding="UTF-8",xml_declaration=True)


if __name__ == "__main__":
    pages = [architecture(), evaluation()]
    for page in pages:
        verify_layout(page)
        export_preview(page)
    export_drawio(pages)
    print("Created 2 editable draw.io pages and 4 matching SVG/PNG previews.")
