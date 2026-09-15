"""텍스트 임베딩.

모델은 로컬에서 돌린다. API 키도 비용도 없고 오프라인에서 재현되므로,
지도교수·팀원이 같은 코드를 받아 같은 결과를 얻을 수 있다.

E5 계열은 입력에 용도 접두사를 요구한다. 'query: ' 와 'passage: ' 를 빼먹으면
성능이 눈에 띄게 떨어지는데 오류가 나지 않아 조용히 나빠진다. 그래서
호출부가 직접 붙이지 않고 이 모듈이 강제한다.
"""

from __future__ import annotations

import re
import struct
from typing import Iterable, List, Optional, Sequence

#: 상품명이 한영 혼용('Cut Off Raglan Long Sleeve', '베이직 긴팔 티셔츠')이라
#: 한국어 전용 모델보다 다국어 모델이 맞다.
DEFAULT_MODEL = "intfloat/multilingual-e5-base"
EMBED_DIM = 768

#: 상품명에서 유사도를 왜곡하는 군더더기. 프로모션 태그와 배송 차수가
#: 남아 있으면 "[29EDITION X ...]" 같은 공통 접두사만으로 서로 다른 품목이 묶인다.
_NOISE_PATTERNS = (
    re.compile(r"\[[^\]]*\]"),          # [29CM 단독], [BLACK], [LC263TS04MC]
    re.compile(r"\([^)]*\)"),            # (3color), (라벤더)
    re.compile(r"\d+\s*차[_\s]?\d*/?\d*"),  # 2차, 11차 10/6
    re.compile(r"\b\d+(st|nd|rd|th)\b", re.I),
    re.compile(r"\b\d{1,2}/\d{1,2}\b"),   # 9/14
    re.compile(r"\b\d+\s*color[s]?\b", re.I),
    re.compile(r"\b[A-Z]{2,}\d[A-Z0-9-]*\b"),  # TG3-TS09, LC263TS12MT
)

#: 뒤에 붙는 색상 표기. 상품 자체가 아니라 변형을 가리킨다.
_COLOR_WORDS = (
    "black", "white", "ivory", "beige", "navy", "grey", "gray", "charcoal",
    "blue", "red", "green", "brown", "pink", "yellow", "melange", "oatmeal",
    "cream", "olive", "lavender", "mint", "sky", "ecru",
    "블랙", "화이트", "아이보리", "베이지", "네이비", "그레이", "차콜",
    "블루", "레드", "그린", "브라운", "핑크", "옐로우", "크림", "라벤더",
)


def normalize_for_embedding(text: str) -> str:
    """임베딩에 넣기 전에 상품명에서 군더더기를 걷어낸다.

    프로모션 태그·배송 차수·품번·색상은 상품이 무엇인지와 관계가 없는데,
    그대로 두면 이것들이 유사도를 지배해 엉뚱한 묶음이 생긴다.
    원문은 signal_raw 에 그대로 남으므로 되돌릴 수 있다.
    """
    out = text
    for pat in _NOISE_PATTERNS:
        out = pat.sub(" ", out)
    out = re.sub(r"[_/,]+", " ", out)
    tokens = [t for t in out.split() if t]
    while tokens and tokens[-1].lower().strip("-") in _COLOR_WORDS:
        tokens.pop()
    cleaned = " ".join(tokens).strip(" -")
    return cleaned or text.strip()


_model = None
_model_name: Optional[str] = None


def load_model(name: str = DEFAULT_MODEL):
    """모델을 한 번만 올려 재사용한다. 최초 호출 때 내려받는다."""
    global _model, _model_name
    if _model is None or _model_name != name:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(name)
        _model_name = name
    return _model


def encode_passages(texts: Sequence[str], model_name: str = DEFAULT_MODEL) -> List[List[float]]:
    """색인 대상(상품명, 키워드)을 벡터로."""
    return _encode([f"passage: {t}" for t in texts], model_name)


def encode_query(text: str, model_name: str = DEFAULT_MODEL) -> List[float]:
    """검색어를 벡터로. 색인과 다른 접두사를 쓴다."""
    return _encode([f"query: {text}"], model_name)[0]


def _encode(prefixed: Sequence[str], model_name: str) -> List[List[float]]:
    model = load_model(model_name)
    # 정규화해 두면 코사인 유사도를 내적으로 계산할 수 있다.
    vectors = model.encode(
        list(prefixed), normalize_embeddings=True, show_progress_bar=False
    )
    return [list(map(float, v)) for v in vectors]


def pack(vector: Iterable[float]) -> bytes:
    """sqlite-vec 이 받는 float32 바이트열."""
    values = list(vector)
    return struct.pack(f"{len(values)}f", *values)


def unpack(blob: bytes) -> List[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))
