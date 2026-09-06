-- 트렌드 시그널 검증 시스템 · 공통 저장 스키마
--
-- 시점 컬럼이 두 개인 이유(중요):
--   observed_at  : 지표가 실제로 가리키는 시점. 역추적 실험의 누수 차단 기준.
--   collected_at : 우리가 그 값을 가져온 시점. 재현성·감사(audit) 용도.
-- 과거 구간을 소급 조회하는 API(네이버 데이터랩 등)는 오늘 수집해도
-- observed_at 이 과거다. 둘을 한 컬럼으로 합치면 T_cut 필터가 무의미해진다.

CREATE TABLE IF NOT EXISTS signal_raw (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at  TEXT    NOT NULL,              -- 'YYYY-MM-DD' 또는 ISO8601 datetime
    collected_at TEXT    NOT NULL,              -- ISO8601 UTC
    channel      TEXT    NOT NULL,              -- musinsa_rank / naver_datalab / naver_shopping / gtrends / news
    keyword_raw  TEXT    NOT NULL,              -- 수집 당시 원문 표현 (정규화 전)
    entity       TEXT    NOT NULL DEFAULT '',   -- 행을 구분하는 하위 차원: 상품ID, 'f_20', 카테고리코드 등
    metric_type  TEXT    NOT NULL,              -- rank / search_index / click_index / review_count / mention_count
    metric_value REAL    NOT NULL,
    metadata     TEXT    NOT NULL DEFAULT '{}', -- JSON: 브랜드, URL, 카테고리 등
    run_id       TEXT,                          -- 같은 수집 실행을 묶는 키
    UNIQUE (channel, keyword_raw, entity, metric_type, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_raw_observed  ON signal_raw (observed_at);
CREATE INDEX IF NOT EXISTS idx_raw_channel   ON signal_raw (channel, observed_at);
CREATE INDEX IF NOT EXISTS idx_raw_keyword   ON signal_raw (keyword_raw, observed_at);

-- 동의어 클러스터링 결과: 흩어진 표현 -> 하나의 후보
CREATE TABLE IF NOT EXISTS signal_candidate (
    candidate_id      TEXT PRIMARY KEY,
    canonical_keyword TEXT NOT NULL,
    first_detected_at TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    notes             TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS candidate_keyword_map (
    candidate_id  TEXT NOT NULL REFERENCES signal_candidate(candidate_id) ON DELETE CASCADE,
    signal_raw_id INTEGER NOT NULL REFERENCES signal_raw(id) ON DELETE CASCADE,
    similarity    REAL,
    PRIMARY KEY (candidate_id, signal_raw_id)
);

-- 검증 단계(팀원)로 넘어가는 후보별 채널 요약
CREATE TABLE IF NOT EXISTS candidate_summary (
    candidate_id              TEXT NOT NULL REFERENCES signal_candidate(candidate_id) ON DELETE CASCADE,
    date                      TEXT NOT NULL,
    musinsa_rank_change       REAL,
    review_growth_rate        REAL,
    naver_search_index_change REAL,
    demographic_distribution  TEXT,   -- JSON
    gtrends_lead_days         REAL,
    channel_count             INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (candidate_id, date)
);

-- 역추적 케이스. label 은 여기에만 두고 검증팀 산출물에는 절대 내보내지 않는다.
CREATE TABLE IF NOT EXISTS trend_case (
    case_id      TEXT PRIMARY KEY,
    keyword      TEXT NOT NULL,
    t_peak       TEXT NOT NULL,
    t_cut        TEXT NOT NULL,
    label        TEXT NOT NULL CHECK (label IN ('real', 'noise')),
    label_reason TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);
