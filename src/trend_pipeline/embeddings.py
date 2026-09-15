"""텍스트 임베딩.

모델은 로컬에서 돌린다. API 키도 비용도 없고 오프라인에서 재현되므로,
지도교수·팀원이 같은 코드를 받아 같은 결과를 얻을 수 있다.

E5 계열은 입력에 용도 접두사를 요구한다. 'query: ' 와 'passage: ' 를 빼먹으면
성능이 눈에 띄게 떨어지는데 오류가 나지 않아 조용히 나빠진다. 그래서
호출부가 직접 붙이지 않고 이 모듈이 강제한다.
"""

from __future__ import annotations

import struct
from typing import Iterable, List, Optional, Sequence

#: 상품명이 한영 혼용('Cut Off Raglan Long Sleeve', '베이직 긴팔 티셔츠')이라
#: 한국어 전용 모델보다 다국어 모델이 맞다.
DEFAULT_MODEL = "intfloat/multilingual-e5-base"
EMBED_DIM = 768

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
