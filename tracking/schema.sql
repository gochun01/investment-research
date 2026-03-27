-- ============================================
-- 투자 분석 파이프라인 — PostgreSQL Schema
-- Docker Linux: psql -U postgres -d pipeline -f schema.sql
-- ============================================

-- 1. TC 카드
CREATE TABLE tc_cards (
    tc_id               VARCHAR(10) PRIMARY KEY,
    title               TEXT NOT NULL,
    created             DATE NOT NULL,
    updated             DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'archived')),
    phase               INTEGER NOT NULL DEFAULT 1
                        CHECK (phase BETWEEN 0 AND 5),
    issue_summary       TEXT NOT NULL,
    pre_read            JSONB NOT NULL,
    scenarios           JSONB NOT NULL,
    tracking_indicators JSONB,
    phase_log           JSONB,
    rm_watches          JSONB,
    cross_card_links    JSONB,
    source              VARCHAR(30),
    close_condition     TEXT,
    tags                TEXT[]
);

CREATE INDEX idx_tc_status ON tc_cards(status);
CREATE INDEX idx_tc_phase ON tc_cards(phase);
CREATE INDEX idx_tc_tags ON tc_cards USING GIN(tags);

-- 2. SD 카드
CREATE TABLE sd_cards (
    sd_id               VARCHAR(10) PRIMARY KEY,
    title               TEXT NOT NULL,
    created             DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'watching'
                        CHECK (status IN ('watching', 'promoted', 'archived')),
    appearance_count    INTEGER NOT NULL DEFAULT 1,
    last_seen           DATE NOT NULL,
    source              TEXT,
    next_check          DATE,
    note                TEXT,
    close_condition     TEXT,
    promoted_to         VARCHAR(10) REFERENCES tc_cards(tc_id)
);

-- 3. TC <-> SA 관계 (다:다)
CREATE TABLE tc_analysis_links (
    tc_id               VARCHAR(10) REFERENCES tc_cards(tc_id),
    analysis_id         VARCHAR(30) NOT NULL,
    PRIMARY KEY (tc_id, analysis_id)
);

-- 4. Watch
CREATE TABLE watches (
    watch_id            VARCHAR(40) PRIMARY KEY,
    created             DATE NOT NULL,
    subject             TEXT NOT NULL,
    watch_type          VARCHAR(30) NOT NULL
                        CHECK (watch_type IN (
                            'event_tracking', 'data_check',
                            'threshold_watch', 'policy_watch'
                        )),
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'resolved', 'expired')),
    schedule            JSONB NOT NULL,
    original_context    JSONB NOT NULL,
    check_template      JSONB NOT NULL,
    close_condition     TEXT,
    source_report       TEXT,
    source_uq           VARCHAR(20),
    completed_checks    JSONB,
    closed_at           TIMESTAMP,
    close_reason        TEXT
);

CREATE INDEX idx_watch_status ON watches(status);
CREATE INDEX idx_watch_type ON watches(watch_type);

-- 5. Watch <-> TC 관계 (다:다)
CREATE TABLE watch_tc_links (
    watch_id            VARCHAR(40) REFERENCES watches(watch_id),
    tc_id               VARCHAR(10) REFERENCES tc_cards(tc_id),
    PRIMARY KEY (watch_id, tc_id)
);

-- 6. Prediction
CREATE TABLE predictions (
    pred_id             VARCHAR(30) PRIMARY KEY,
    source_analysis     VARCHAR(30) NOT NULL,
    pred_date           DATE NOT NULL,
    tc_id               VARCHAR(10) REFERENCES tc_cards(tc_id),
    pred_type           VARCHAR(30) NOT NULL,
    claim               TEXT NOT NULL,
    scenario            VARCHAR(5) NOT NULL,
    probability         VARCHAR(10) NOT NULL,
    trigger_condition   TEXT NOT NULL,
    deadline            DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open', 'hit', 'miss', 'partial', 'expired'
                        )),
    outcome             VARCHAR(20),
    outcome_date        DATE,
    lesson              TEXT
);

CREATE INDEX idx_pred_status ON predictions(status);
CREATE INDEX idx_pred_tc ON predictions(tc_id);
CREATE INDEX idx_pred_deadline ON predictions(deadline);

-- 7. SA History
CREATE TABLE sa_history (
    sa_id               VARCHAR(30) PRIMARY KEY,
    sa_date             DATE NOT NULL,
    title               TEXT NOT NULL,
    pipeline            TEXT,
    pre_read            JSONB NOT NULL,
    core_finding        TEXT,
    layer_summary       JSONB,
    scenarios           JSONB,
    uncertainty         JSONB,
    feedback            JSONB,
    prior_context       JSONB,
    quality_score       NUMERIC(4,3)
                        CHECK (quality_score BETWEEN 0 AND 1),
    tags                TEXT[],
    related_ids         TEXT[]
);

CREATE INDEX idx_sa_date ON sa_history(sa_date);
CREATE INDEX idx_sa_tags ON sa_history USING GIN(tags);
CREATE INDEX idx_sa_quality ON sa_history(quality_score);

-- 8. Learning Log
CREATE TABLE learning_log (
    rule_id             VARCHAR(10) PRIMARY KEY,
    created             DATE NOT NULL,
    pattern             TEXT NOT NULL,
    correction          TEXT NOT NULL,
    pred_type           VARCHAR(30),
    hit_rate_before     NUMERIC(4,3),
    hit_rate_after      NUMERIC(4,3),
    source_predictions  TEXT[]
);

-- ============================================
-- 집계 뷰
-- ============================================

-- 9. 품질 추이 (이동평균 포함)
CREATE VIEW v_quality_trend AS
SELECT
    sa_date,
    sa_id,
    title,
    quality_score,
    AVG(quality_score) OVER (
        ORDER BY sa_date
        ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) AS moving_avg_10
FROM sa_history
WHERE quality_score IS NOT NULL
ORDER BY sa_date;

-- 10. 예측 적중률 (유형별)
CREATE VIEW v_prediction_hit_rate AS
SELECT
    pred_type,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'hit') AS hits,
    COUNT(*) FILTER (WHERE status = 'miss') AS misses,
    COUNT(*) FILTER (WHERE status = 'partial') AS partials,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'hit')::NUMERIC /
        NULLIF(COUNT(*) FILTER (
            WHERE status IN ('hit', 'miss', 'partial')
        ), 0), 3
    ) AS hit_rate
FROM predictions
GROUP BY pred_type;

-- 11. 대시보드 (활성 TC)
CREATE VIEW v_dashboard AS
SELECT
    tc_id,
    title,
    status,
    phase,
    (pre_read->>'scp')::INTEGER AS scp,
    pre_read->>'urgency' AS urgency,
    created,
    updated
FROM tc_cards
WHERE status = 'active'
ORDER BY phase DESC, updated DESC;

-- 12. Watch 만기 (오늘 이후 가장 가까운)
CREATE VIEW v_watch_due AS
SELECT
    watch_id,
    subject,
    watch_type,
    (schedule->>'next_check')::DATE AS next_check,
    status
FROM watches
WHERE status = 'active'
ORDER BY (schedule->>'next_check')::DATE;
