-- ============================================================
-- 투자 분석 파이프라인 — 통합 PostgreSQL Schema v2
-- 전체 DROP 후 재구축
-- Docker: docker exec invest-ontology-db psql -U investor -d invest_ontology -f /tmp/schema-v2.sql
-- ============================================================

-- ============================================================
-- PHASE 0: 전체 DROP (기존 32 테이블 + 14 뷰)
-- ============================================================

DROP VIEW IF EXISTS
    v_active_links, v_active_portfolio, v_active_watchlist,
    v_cross_issue_impacts, v_graph_node_usage, v_issue_scenarios,
    v_judgment_accuracy, v_latest_crypto, v_latest_issues,
    v_latest_macro, v_latest_market, v_metric_pipeline_map,
    v_ontology_status, v_recent_reports,
    v_quality_trend, v_prediction_hit_rate, v_dashboard,
    v_watch_due, v_tc_convergence, v_transition_dashboard,
    v_transition_path
    CASCADE;

DROP TABLE IF EXISTS
    -- 구버전 issue 분석
    issue_fact, issue_hedge, issue_impact, issue_position,
    issue_power_incentive, issue_timeline_event,
    issue_scenario_assumption, issue_scenario,
    issue_watchlist, issue_report,
    issue_graph_edge, issue_graph_node, issue_graph,
    issue_run,
    -- 구버전 기타
    judgment_track, analysis_report,
    filing_archive, portfolio_position,
    -- 시장 데이터
    daily_ont_status, daily_crypto, daily_market, daily_macro,
    news_archive,
    -- 온톨로지
    ont_status_log, ont_link_log, ont_regime_log,
    ont_threshold, ont_scenario, ont_metric,
    ont_property, ont_link, ont_object,
    -- tracking (혹시 남아있으면)
    th_evidence, th_link_path, th_tc_links, th_cards,
    tc_metric_links, tc_ont_links,
    watch_tc_links, tc_analysis_links,
    predictions, sa_history, learning_log,
    watches, sd_cards, tc_cards
    CASCADE;


-- ============================================================
-- PHASE 1: 온톨로지 코어 (PSF 기반)
-- ============================================================

-- 1-1. PSF 객체 (P/S/F 6개)
CREATE TABLE ont_object (
    object_id       VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    layer           VARCHAR(10) NOT NULL
                    CHECK (layer IN ('pan','structure','flow')),
    core_question   TEXT,
    current_state   VARCHAR(30),
    state_updated_at TIMESTAMP DEFAULT now()
);

-- 1-2. PSF 속성 (P1~P4, S1~S5, F1~F5 = 14개)
CREATE TABLE ont_property (
    property_id     VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    object_id       VARCHAR(10) NOT NULL REFERENCES ont_object(object_id),
    layer           VARCHAR(10) NOT NULL
                    CHECK (layer IN ('pan','structure','flow')),
    description     TEXT,
    trigger_links   TEXT[]
);

-- 1-3. 인과 링크 (L1~L8)
CREATE TABLE ont_link (
    link_id         VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    source_object   VARCHAR(10) NOT NULL REFERENCES ont_object(object_id),
    target_object   VARCHAR(10) NOT NULL REFERENCES ont_object(object_id),
    direction       VARCHAR(10) NOT NULL
                    CHECK (direction IN ('forward','reverse')),
    path_type       VARCHAR(10) NOT NULL
                    CHECK (path_type IN ('single','branch','parallel')),
    mechanism       TEXT,
    channels        TEXT,
    speed           VARCHAR(30),
    is_active       BOOLEAN DEFAULT false,
    activation_evidence TEXT,
    activated_at    TIMESTAMP,
    state_updated_at TIMESTAMP DEFAULT now()
);

-- 1-4. 지표 정의 (46개: macro 27 core + 19 aux)
CREATE TABLE ont_metric (
    metric_id       VARCHAR(10) PRIMARY KEY,
    property_id     VARCHAR(10) NOT NULL REFERENCES ont_property(property_id),
    name            VARCHAR(200) NOT NULL,
    data_source     VARCHAR(50),
    source_detail   VARCHAR(200),
    unit            VARCHAR(30),
    description     TEXT,
    macro_layer     VARCHAR(5),
    macro_id        VARCHAR(10)
);

-- 1-5. 임계값 (3중 밴드: Watch/Alert/Hard)
CREATE TABLE ont_threshold (
    id              SERIAL PRIMARY KEY,
    metric_id       VARCHAR(10) NOT NULL REFERENCES ont_metric(metric_id),
    link_id         VARCHAR(10) REFERENCES ont_link(link_id),
    band            VARCHAR(10) NOT NULL
                    CHECK (band IN ('watch','alert','hard')),
    condition_type  VARCHAR(30) NOT NULL,
    threshold_value NUMERIC(20,6),
    threshold_direction VARCHAR(10),
    duration_days   INTEGER,
    description     TEXT,
    source_type     VARCHAR(20)
                    CHECK (source_type IN ('structural','statistical','narrative')),
    is_active       BOOLEAN DEFAULT true,
    updated_at      TIMESTAMP DEFAULT now(),
    UNIQUE (metric_id, link_id, band, condition_type)
);

-- 1-6. 시나리오 (Base/Bull/Bear)
CREATE TABLE ont_scenario (
    id              SERIAL PRIMARY KEY,
    created_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    scenario_set_name VARCHAR(200) NOT NULL,
    current_regime  VARCHAR(20),
    pivot_property  VARCHAR(10) REFERENCES ont_property(property_id),
    pivot_question  TEXT,
    base_assumption TEXT,
    base_arrival    JSONB,
    base_asset_env  JSONB,
    bull_assumption TEXT,
    bull_arrival    JSONB,
    bull_asset_env  JSONB,
    bear_assumption TEXT,
    bear_arrival    JSONB,
    bear_asset_env  JSONB,
    key_divergence_axis TEXT,
    monitoring_triggers JSONB,
    next_check_date DATE,
    invalidation_condition TEXT,
    is_active       BOOLEAN DEFAULT true,
    invalidated_date DATE,
    invalidated_reason TEXT,
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_ont_sc_active ON ont_scenario(is_active);
CREATE INDEX idx_ont_sc_date ON ont_scenario(created_date DESC);

-- 1-7. 이력 테이블
CREATE TABLE ont_link_log (
    id              SERIAL PRIMARY KEY,
    link_id         VARCHAR(10) NOT NULL REFERENCES ont_link(link_id),
    log_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    prev_active     BOOLEAN,
    new_active      BOOLEAN,
    evidence        TEXT,
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_ont_ll_link ON ont_link_log(link_id);
CREATE INDEX idx_ont_ll_date ON ont_link_log(log_date);

CREATE TABLE ont_status_log (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    object_id       VARCHAR(10) NOT NULL REFERENCES ont_object(object_id),
    property_id     VARCHAR(10) NOT NULL REFERENCES ont_property(property_id),
    value           NUMERIC(20,6),
    text_value      TEXT,
    direction       VARCHAR(10),
    verdict         VARCHAR(20),
    created_at      TIMESTAMP DEFAULT now(),
    UNIQUE (snapshot_date, property_id)
);
CREATE INDEX idx_ont_sl_date ON ont_status_log(snapshot_date);
CREATE INDEX idx_ont_sl_obj ON ont_status_log(object_id);
CREATE INDEX idx_ont_sl_prop ON ont_status_log(property_id);

CREATE TABLE ont_regime_log (
    id              SERIAL PRIMARY KEY,
    log_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    regime          VARCHAR(30) NOT NULL,
    risk_asset_count VARCHAR(10),
    quadrant        VARCHAR(30),
    keystone_value  NUMERIC(6,3),
    keystone_direction VARCHAR(20),
    narrative       TEXT,
    l7_score        NUMERIC(4,3),
    l8_score        NUMERIC(4,3),
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_ont_rl_date ON ont_regime_log(log_date);
CREATE INDEX idx_ont_rl_regime ON ont_regime_log(regime);


-- ============================================================
-- PHASE 2: 시장 데이터
-- ============================================================

-- 2-1. 매크로 일별 스냅샷
CREATE TABLE daily_macro (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL UNIQUE,
    fed_funds_rate  NUMERIC(5,3),
    us_10y_yield    NUMERIC(5,3),
    us_2y_yield     NUMERIC(5,3),
    yield_spread    NUMERIC(5,3),
    yield_spread_10y3m NUMERIC(5,3),
    kr_base_rate    NUMERIC(5,3),
    dxy_index       NUMERIC(8,3),
    usd_krw         NUMERIC(8,2),
    usd_jpy         NUMERIC(8,3),
    m2_supply       NUMERIC(15,2),
    fed_balance_sheet NUMERIC(15,2),
    vix             NUMERIC(6,2),
    move_index      NUMERIC(6,2),
    wti_crude       NUMERIC(8,2),
    brent_crude     NUMERIC(8,2),
    gold_price      NUMERIC(8,2),
    tips_10y_real   NUMERIC(6,3),
    bei_10y         NUMERIC(6,3),
    hy_oas          NUMERIC(8,2),
    mmf_balance     NUMERIC(15,2),
    sofr_rate       NUMERIC(6,4),
    bank_reserves   NUMERIC(15,2),
    rrp_balance     NUMERIC(15,2),
    tga_balance     NUMERIC(15,2),
    core_pce_yoy    NUMERIC(5,3),
    ism_pmi         NUMERIC(5,1),
    term_premium    NUMERIC(6,3),
    source          VARCHAR(50) DEFAULT 'pipeline',
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_macro_date ON daily_macro(snapshot_date DESC);

-- 2-2. 시장 종목별 일별
CREATE TABLE daily_market (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    ticker          VARCHAR(20) NOT NULL,
    name            VARCHAR(100),
    close_price     NUMERIC(12,4),
    change_pct      NUMERIC(6,3),
    volume          BIGINT,
    market_cap      NUMERIC(20,2),
    ma_20           NUMERIC(12,4),
    ma_60           NUMERIC(12,4),
    ma_200          NUMERIC(12,4),
    rsi_14          NUMERIC(5,2),
    exchange        VARCHAR(20),
    asset_type      VARCHAR(20),
    source          VARCHAR(50) DEFAULT 'pipeline',
    created_at      TIMESTAMP DEFAULT now(),
    UNIQUE (snapshot_date, ticker)
);
CREATE INDEX idx_market_date ON daily_market(snapshot_date DESC);
CREATE INDEX idx_market_ticker ON daily_market(ticker);

-- 2-3. 크립토 일별
CREATE TABLE daily_crypto (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    coin_id         VARCHAR(30) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    name            VARCHAR(50),
    price_usd       NUMERIC(16,8),
    price_change_24h NUMERIC(8,4),
    price_change_7d  NUMERIC(8,4),
    market_cap_usd  NUMERIC(20,2),
    market_cap_rank INTEGER,
    total_volume_24h NUMERIC(20,2),
    dominance_pct   NUMERIC(5,3),
    source          VARCHAR(50) DEFAULT 'pipeline',
    created_at      TIMESTAMP DEFAULT now(),
    UNIQUE (snapshot_date, coin_id)
);
CREATE INDEX idx_crypto_date ON daily_crypto(snapshot_date DESC);
CREATE INDEX idx_crypto_symbol ON daily_crypto(symbol);


-- ============================================================
-- PHASE 3: TC/SD 카드 + Watch + Prediction (Tracking)
-- ============================================================

-- 3-1. TC 카드 (투자 이슈 추적)
CREATE TABLE tc_cards (
    tc_id           VARCHAR(10) PRIMARY KEY,
    title           TEXT NOT NULL,
    created         DATE NOT NULL,
    updated         DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','archived')),
    phase           INTEGER NOT NULL DEFAULT 1
                    CHECK (phase BETWEEN 0 AND 5),
    issue_summary   TEXT NOT NULL,
    pre_read        JSONB NOT NULL,
    scenarios       JSONB NOT NULL,
    tracking_indicators JSONB,
    phase_log       JSONB,
    rm_watches      JSONB,
    cross_card_links JSONB,
    source          VARCHAR(30),
    close_condition TEXT,
    tags            TEXT[]
);
CREATE INDEX idx_tc_status ON tc_cards(status);
CREATE INDEX idx_tc_phase ON tc_cards(phase);
CREATE INDEX idx_tc_tags ON tc_cards USING GIN(tags);

-- 3-2. SD 카드 (씨드 감시)
CREATE TABLE sd_cards (
    sd_id           VARCHAR(10) PRIMARY KEY,
    title           TEXT NOT NULL,
    created         DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'watching'
                    CHECK (status IN ('watching','promoted','archived')),
    appearance_count INTEGER NOT NULL DEFAULT 1,
    last_seen       DATE NOT NULL,
    source          TEXT,
    next_check      DATE,
    note            TEXT,
    close_condition TEXT,
    promoted_to     VARCHAR(10) REFERENCES tc_cards(tc_id)
);

-- 3-3. TC ↔ SA 연결 (다:다)
CREATE TABLE tc_analysis_links (
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    analysis_id     VARCHAR(30) NOT NULL REFERENCES sa_history(sa_id),
    PRIMARY KEY (tc_id, analysis_id)
);

-- 3-4. Watch (추적 감시)
CREATE TABLE watches (
    watch_id        VARCHAR(40) PRIMARY KEY,
    created         DATE NOT NULL,
    subject         TEXT NOT NULL,
    watch_type      VARCHAR(30) NOT NULL
                    CHECK (watch_type IN (
                        'event_tracking','data_check',
                        'threshold_watch','policy_watch'
                    )),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','resolved','expired')),
    schedule        JSONB NOT NULL,
    original_context JSONB NOT NULL,
    check_template  JSONB NOT NULL,
    close_condition TEXT,
    source_report   TEXT,
    source_uq       VARCHAR(20),
    completed_checks JSONB,
    closed_at       TIMESTAMP,
    close_reason    TEXT
);
CREATE INDEX idx_watch_status ON watches(status);
CREATE INDEX idx_watch_type ON watches(watch_type);

-- 3-5. Watch ↔ TC 연결 (다:다)
CREATE TABLE watch_tc_links (
    watch_id        VARCHAR(40) REFERENCES watches(watch_id),
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    PRIMARY KEY (watch_id, tc_id)
);

-- 3-6. Prediction (예측 원장)
CREATE TABLE predictions (
    pred_id         VARCHAR(30) PRIMARY KEY,
    source_analysis VARCHAR(30) NOT NULL,
    pred_date       DATE NOT NULL,
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    pred_type       VARCHAR(30) NOT NULL,
    claim           TEXT NOT NULL,
    scenario        VARCHAR(5) NOT NULL,
    probability     VARCHAR(10) NOT NULL,
    trigger_condition TEXT NOT NULL,
    deadline        DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','hit','miss','partial','expired')),
    outcome         TEXT,
    outcome_date    DATE,
    lesson          TEXT
);
CREATE INDEX idx_pred_status ON predictions(status);
CREATE INDEX idx_pred_tc ON predictions(tc_id);
CREATE INDEX idx_pred_deadline ON predictions(deadline);

-- 3-7. SA History (Stereo 분석 이력)
CREATE TABLE sa_history (
    sa_id           VARCHAR(30) PRIMARY KEY,
    sa_date         DATE NOT NULL,
    title           TEXT NOT NULL,
    pipeline        TEXT,
    pre_read        JSONB NOT NULL,
    core_finding    TEXT,
    layer_summary   JSONB,
    scenarios       JSONB,
    uncertainty     JSONB,
    feedback        JSONB,
    prior_context   JSONB,
    quality_score   NUMERIC(4,3)
                    CHECK (quality_score BETWEEN 0 AND 1),
    tags            TEXT[],
    related_ids     TEXT[]
);
CREATE INDEX idx_sa_date ON sa_history(sa_date);
CREATE INDEX idx_sa_tags ON sa_history USING GIN(tags);
CREATE INDEX idx_sa_quality ON sa_history(quality_score);

-- 3-8. Learning Log (학습 기록)
CREATE TABLE learning_log (
    rule_id         VARCHAR(10) PRIMARY KEY,
    created         DATE NOT NULL,
    pattern         TEXT NOT NULL,
    correction      TEXT NOT NULL,
    pred_type       VARCHAR(30),
    hit_rate_before NUMERIC(4,3),
    hit_rate_after  NUMERIC(4,3),
    source_predictions TEXT[]
);


-- ============================================================
-- PHASE 4: 브릿지 (온톨로지 ↔ 추적)
-- ============================================================

-- 4-1. TC ↔ ont_link 연결 (카드가 어떤 인과 체인에 관여하는가)
CREATE TABLE tc_ont_links (
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    link_id         VARCHAR(10) REFERENCES ont_link(link_id),
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('trigger','kc','impact','context')),
    note            TEXT,
    PRIMARY KEY (tc_id, link_id, role)
);

-- 4-2. TC ↔ ont_metric 연결 (카드가 어떤 지표를 추적하는가)
CREATE TABLE tc_metric_links (
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    metric_id       VARCHAR(10) REFERENCES ont_metric(metric_id),
    band            VARCHAR(10) CHECK (band IN ('watch','alert','hard')),
    threshold_value NUMERIC(20,6),
    threshold_direction VARCHAR(10),
    duration_days   INTEGER,
    PRIMARY KEY (tc_id, metric_id)
);


-- ============================================================
-- PHASE 5: 전이 예측 (Transition Hypothesis)
-- ============================================================

-- 5-1. TH 카드 (전이 가설)
CREATE TABLE th_cards (
    th_id           VARCHAR(10) PRIMARY KEY,
    hypothesis      TEXT NOT NULL,
    from_regime     VARCHAR(30),
    to_regime       VARCHAR(30),
    horizon         VARCHAR(10)
                    CHECK (horizon IN ('short','mid','long')),
    horizon_detail  TEXT,
    confidence      NUMERIC(4,3) DEFAULT 0
                    CHECK (confidence BETWEEN 0 AND 1),
    causal_chain    JSONB,
    convergence     JSONB,
    completion_triggers JSONB,
    kill_conditions JSONB,
    cascade         JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','realized','invalidated','expired')),
    created         DATE NOT NULL,
    next_review     DATE,
    realized_date   DATE,
    invalidated_date DATE,
    lesson          TEXT
);
CREATE INDEX idx_th_status ON th_cards(status);
CREATE INDEX idx_th_confidence ON th_cards(confidence DESC);

-- 5-2. TH ↔ TC 수렴 관계
CREATE TABLE th_tc_links (
    th_id           VARCHAR(10) REFERENCES th_cards(th_id),
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    role            VARCHAR(30) NOT NULL
                    CHECK (role IN ('convergence_member','cascade_target','evidence')),
    joined_date     DATE,
    PRIMARY KEY (th_id, tc_id)
);

-- 5-3. TH 증거 축적 이력
CREATE TABLE th_evidence (
    id              SERIAL PRIMARY KEY,
    th_id           VARCHAR(10) NOT NULL REFERENCES th_cards(th_id),
    ev_date         DATE NOT NULL,
    ev_type         VARCHAR(30) NOT NULL
                    CHECK (ev_type IN (
                        'completion_met','kill_met',
                        'tc_join','tc_leave',
                        'psf_accel','psf_decel','psf_reverse',
                        'macro_shift','manual'
                    )),
    description     TEXT,
    confidence_delta NUMERIC(4,3),
    confidence_after NUMERIC(4,3),
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_th_ev_th ON th_evidence(th_id);
CREATE INDEX idx_th_ev_date ON th_evidence(ev_date);

-- 5-4. TH ↔ ont_link 인과 경로 (전이의 인과 체인을 그래프로)
CREATE TABLE th_link_path (
    th_id           VARCHAR(10) REFERENCES th_cards(th_id),
    link_id         VARCHAR(10) REFERENCES ont_link(link_id),
    step_order      INTEGER NOT NULL,
    is_active       BOOLEAN DEFAULT false,
    note            TEXT,
    PRIMARY KEY (th_id, link_id)
);


-- ============================================================
-- PHASE 6: 뷰 (대시보드 + 분석)
-- ============================================================

-- 6-1. TC 대시보드
CREATE VIEW v_dashboard AS
SELECT
    tc_id, title, status, phase,
    (pre_read->>'scp')::INTEGER AS scp,
    pre_read->>'urgency' AS urgency,
    pre_read->>'type' AS issue_type,
    created, updated
FROM tc_cards
WHERE status = 'active'
ORDER BY phase DESC, updated DESC;

-- 6-2. Watch 만기
CREATE VIEW v_watch_due AS
SELECT
    w.watch_id, w.subject, w.watch_type,
    (w.schedule->>'next_check')::DATE AS next_check,
    w.status,
    array_agg(wtl.tc_id) AS linked_tc
FROM watches w
LEFT JOIN watch_tc_links wtl ON w.watch_id = wtl.watch_id
WHERE w.status = 'active'
GROUP BY w.watch_id, w.subject, w.watch_type, w.schedule, w.status
ORDER BY (w.schedule->>'next_check')::DATE;

-- 6-3. 예측 적중률
CREATE VIEW v_prediction_hit_rate AS
SELECT
    pred_type,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'hit') AS hits,
    COUNT(*) FILTER (WHERE status = 'miss') AS misses,
    COUNT(*) FILTER (WHERE status = 'partial') AS partials,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'hit')::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('hit','miss','partial')), 0), 3
    ) AS hit_rate
FROM predictions
GROUP BY pred_type;

-- 6-4. 품질 추이 (이동평균)
CREATE VIEW v_quality_trend AS
SELECT
    sa_date, sa_id, title, quality_score,
    AVG(quality_score) OVER (
        ORDER BY sa_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) AS moving_avg_10
FROM sa_history
WHERE quality_score IS NOT NULL
ORDER BY sa_date;

-- 6-5. TC 수렴 분석 (같은 인과 체인을 공유하는 카드 그룹)
CREATE VIEW v_tc_convergence AS
SELECT
    l.link_id,
    l.name AS chain_name,
    l.is_active AS chain_active,
    array_agg(DISTINCT tol.tc_id ORDER BY tol.tc_id) AS cards,
    count(DISTINCT tol.tc_id) AS card_count
FROM tc_ont_links tol
JOIN ont_link l ON tol.link_id = l.link_id
JOIN tc_cards t ON tol.tc_id = t.tc_id
WHERE t.status = 'active'
GROUP BY l.link_id, l.name, l.is_active
HAVING count(DISTINCT tol.tc_id) >= 2;

-- 6-6. 전이 예측 대시보드
CREATE VIEW v_transition_dashboard AS
SELECT
    th.th_id, th.hypothesis,
    th.from_regime, th.to_regime,
    th.confidence, th.horizon, th.horizon_detail,
    th.status, th.next_review,
    (SELECT count(*) FROM th_tc_links WHERE th_id = th.th_id) AS convergence_count,
    (SELECT max(ev_date) FROM th_evidence WHERE th_id = th.th_id) AS last_evidence_date
FROM th_cards th
WHERE th.status = 'active'
ORDER BY th.confidence DESC;

-- 6-7. 전이 인과 경로 (TH의 인과 체인을 ont_link로 전개)
CREATE VIEW v_transition_path AS
SELECT
    th.th_id, th.hypothesis, th.confidence,
    tlp.step_order,
    l.link_id, l.name AS link_name,
    l.is_active AS link_currently_active,
    o1.name AS from_obj, o2.name AS to_obj,
    l.speed
FROM th_link_path tlp
JOIN th_cards th ON tlp.th_id = th.th_id
JOIN ont_link l ON tlp.link_id = l.link_id
JOIN ont_object o1 ON l.source_object = o1.object_id
JOIN ont_object o2 ON l.target_object = o2.object_id
WHERE th.status = 'active'
ORDER BY th.th_id, tlp.step_order;

-- 6-8. 온톨로지 현황
CREATE VIEW v_ontology_status AS
SELECT
    o.object_id, o.name AS object_name, o.layer,
    o.current_state,
    p.property_id, p.name AS property_name,
    (SELECT count(*) FROM ont_metric m WHERE m.property_id = p.property_id) AS metric_count,
    (SELECT count(*) FROM ont_threshold t
     JOIN ont_metric m2 ON t.metric_id = m2.metric_id
     WHERE m2.property_id = p.property_id AND t.is_active) AS active_thresholds
FROM ont_object o
JOIN ont_property p ON o.object_id = p.object_id
ORDER BY o.object_id, p.property_id;

-- 6-9. 최신 매크로
CREATE VIEW v_latest_macro AS
SELECT * FROM daily_macro
ORDER BY snapshot_date DESC LIMIT 1;


-- ============================================================
-- PHASE 7: 시드 데이터 (온톨로지 코어)
-- ============================================================

-- 7-1. PSF 6객체
INSERT INTO ont_object VALUES
    ('OBJ-01', '정책 레짐',   'pan',       '중앙은행이 돈의 가격을 정한다'),
    ('OBJ-02', '룰 충격',     'pan',       '관세/지정학/규제가 룰을 바꾼다'),
    ('OBJ-03', '금리 구조',   'structure', '돈의 가격이 시장에 전달된다'),
    ('OBJ-04', '신용 구조',   'structure', '시스템이 충격을 견디는가'),
    ('OBJ-05', '유동성 방향', 'flow',      '돈이 어디로 가는가'),
    ('OBJ-06', '포지션 상태', 'flow',      '돈이 실제로 갔는가');

-- 7-2. PSF 14속성
INSERT INTO ont_property VALUES
    ('P1', '중앙은행 방향', 'OBJ-01', 'pan',       '정책금리와 유동성 공급 방향',           '{L1}'),
    ('P2', '관세',          'OBJ-02', 'pan',       '유효관세율과 대상국',                   '{L2,L3}'),
    ('P3', '지정학',        'OBJ-02', 'pan',       '분쟁 온도와 에너지/제재 영향',          NULL),
    ('P4', '규제',          'OBJ-02', 'pan',       '자산/금융/산업 규제 변경',              NULL),
    ('S1', '실질금리',      'OBJ-03', 'structure', 'TIPS 기반 실질금리',                    '{L4}'),
    ('S2', '신용 스프레드', 'OBJ-04', 'structure', 'HY/IG 스프레드로 본 신용 상태',         '{L2,L7}'),
    ('S3', 'SOFR 스프레드', 'OBJ-04', 'structure', '단기자금시장 스트레스',                 '{L5,L7,L8}'),
    ('S4', '실물 확인',     'OBJ-04', 'structure', 'L2 전파의 실물 확인 지표',              '{L2}'),
    ('S5', '텀프리미엄',    'OBJ-03', 'structure', '장단기 금리차',                          '{L1,L4}'),
    ('F1', 'DXY',           'OBJ-05', 'flow',      '달러 강약',                              '{L4,L6}'),
    ('F2', '자산군 플로우', 'OBJ-05', 'flow',      'MMF/주식 자금 흐름',                    '{L4,L6}'),
    ('F3', 'DM-EM',         'OBJ-05', 'flow',      '선진국/신흥국 자금 배분',               '{L6}'),
    ('F4', '크립토 유동성', 'OBJ-05', 'flow',      '스테이블/BTC ETF 흐름',                 '{L6}'),
    ('F5', 'VIX',           'OBJ-06', 'flow',      '공포지수',                              '{L7}');

-- 7-3. 인과 링크 L1~L8
INSERT INTO ont_link VALUES
    ('L1', '정책→금리',           'OBJ-01','OBJ-03','forward','single',   '기준금리 변경 → 단기금리 → 장기금리 전파','정책금리→SOFR→국채','즉시~1주',  false, NULL, NULL, now()),
    ('L2', '룰충격→신용',         'OBJ-02','OBJ-04','forward','parallel', '관세/지정학 충격 → 신용 스프레드 확대',     '관세→수입물가→기업이익→신용','1~4주',   false, NULL, NULL, now()),
    ('L3', '룰충격→금리',         'OBJ-02','OBJ-03','forward','branch',   '관세/에너지 충격 → 인플레 기대 → 금리',    '에너지가격→BEI→TIPS→명목금리','2~8주',   false, NULL, NULL, now()),
    ('L4', '금리→유동성',         'OBJ-03','OBJ-05','forward','single',   '실질금리 상승 → 유동성 위축',              '실질금리→달러강세→자금흐름','2~8주',   false, NULL, NULL, now()),
    ('L5', '신용→유동성(게이트)', 'OBJ-04','OBJ-05','forward','single',   '신용 경색 → 유동성 증발',                  'HY스프레드→MMF이동→유동성축소','즉시~1주', false, NULL, NULL, now()),
    ('L6', '유동성→포지션',       'OBJ-05','OBJ-06','forward','single',   '유동성 방향 → 포지션 조정',                '달러방향→자산군배분→포지션','1~4주',   false, NULL, NULL, now()),
    ('L7', '포지션→신용(역류)',   'OBJ-06','OBJ-04','reverse','parallel', '포지션 청산 → 신용 악화 (역류)',            'VIX급등→디레버리징→신용경색','즉시~2주', false, NULL, NULL, now()),
    ('L8', '신용→정책(역류)',     'OBJ-04','OBJ-01','reverse','single',   '신용 위기 → 정책 개입 (역류)',              'SOFR스파이크→긴급유동성→정책전환','즉시',    false, NULL, NULL, now());

-- 7-4. 지표 27개 (macro core)
INSERT INTO ont_metric VALUES
    ('P1.a', 'P1', '정책금리',           'FRED',       'DFF',       'pct',   '연방기금금리',               'A', 'A1'),
    ('P1.b', 'P1', '점도표',             'web_search', NULL,        NULL,    'FOMC 점도표 중앙값',         'A', NULL),
    ('P1.c', 'P1', '순유동성',           'FRED',       'WALCL-TGA-RRP', 'B USD', 'Fed B/S - TGA - RRP',  'D', 'D5'),
    ('P2.a', 'P2', '유효관세율',         'web_search', NULL,        'pct',   '미국 평균 유효관세율',       'A', NULL),
    ('P2.b', 'P2', '법적 권한',          'web_search', NULL,        NULL,    'Section 301/122/IEEPA 상태', 'A', NULL),
    ('P2.c', 'P2', '대상국',             'web_search', NULL,        NULL,    '관세 대상국 목록',           'A', NULL),
    ('P3.a', 'P3', '분쟁 온도',          'web_search', NULL,        'level', '지정학 분쟁 강도',           'A', NULL),
    ('P3.b', 'P3', '에너지 가격',        'Yahoo',      'BZ=F',      'USD',   'Brent 원유',                'C', 'C7'),
    ('P3.c', 'P3', 'SWIFT 제재',         'web_search', NULL,        NULL,    'SWIFT 제재 상태',           'A', NULL),
    ('P4.a', 'P4', '규제 변경',          'web_search', NULL,        NULL,    '주요 규제 변경 사항',       'A', NULL),
    ('S1.a', 'S1', '10Y TIPS 실질금리',  'FRED',       'DFII10',    'pct',   '10년 TIPS 실질금리',        'B', 'B1'),
    ('S1.b', 'S1', 'BEI 기대인플레',     'FRED',       'T10YIE',    'pct',   '10년 손익분기 인플레',      'C', 'C8'),
    ('S2.a', 'S2', 'HY OAS',             'FRED',       'BAMLH0A0HYM2', 'bps','HY 옵션조정 스프레드',     'B', 'B5'),
    ('S2.b', 'S2', 'HYG 가격',           'Yahoo',      'HYG',       'USD',   'HY 채권 ETF',              'B', NULL),
    ('S2.c', 'S2', 'LQD 가격',           'Yahoo',      'LQD',       'USD',   'IG 채권 ETF',              'B', NULL),
    ('S2.d', 'S2', 'HYG/IEF 비율',       'Yahoo',      'HYG/IEF',   'ratio', 'HY vs 국채 상대강도',      'B', NULL),
    ('S3.a', 'S3', 'SOFR-FF 갭',         'FRED',       'SOFR-DFF',  'bps',   'SOFR vs 연방기금 스프레드', 'D', 'D6'),
    ('S4.a', 'S4', '제조업 PMI',         'web_search', 'ISM',       'index', 'ISM 제조업 PMI',           'C', 'C5'),
    ('S5.a', 'S5', '10Y-2Y 스프레드',    'FRED',       'T10Y2Y',    'pct',   '장단기 금리차',            'C', 'C3'),
    ('S5.b', 'S5', '10Y-3M 스프레드',    'FRED',       'T10Y3M',    'pct',   '10년-3개월 스프레드',      'C', NULL),
    ('F1.a', 'F1', '달러지수',           'Yahoo',      'DX-Y.NYB',  'index', 'DXY',                      'B', 'B2'),
    ('F2.a', 'F2', 'MMF 잔고',           'FRED',       'WMMNS',     'B USD', 'MMF 총잔고',               'B', NULL),
    ('F2.b', 'F2', 'SPY 거래량',         'Yahoo',      'SPY',       'shares','S&P500 ETF 거래량',        'B', NULL),
    ('F3.a', 'F3', 'EEM/SPY 비율',       'Yahoo',      'EEM/SPY',   'ratio', 'EM vs DM 상대강도',        'B', NULL),
    ('F4.a', 'F4', '스테이블코인 시총',  'CoinGecko',  NULL,        'B USD', '스테이블코인 총 시가총액',  'B', NULL),
    ('F4.b', 'F4', 'BTC ETF',            'Yahoo',      'IBIT',      'USD',   'BTC ETF 가격',             'B', NULL),
    ('F5.a', 'F5', 'VIX 지수',           'Yahoo',      '^VIX',      'index', 'CBOE VIX',                 'C', 'C1');

-- 7-5. L7/L8 임계값 (10개)
INSERT INTO ont_threshold (metric_id, link_id, band, condition_type, threshold_value, threshold_direction, duration_days, description, source_type) VALUES
    ('F5.a', 'L7', 'alert', 'level',           30.000, 'above', NULL, 'VIX 30 이상 → L7 경고',           'statistical'),
    ('F5.a', 'L7', 'hard',  'daily_spike_pct',  40.000, 'above', 1,   'VIX 일일 40%+ 급등 → L7 경고',    'statistical'),
    ('S2.b', 'L7', 'hard',  'daily_drop_pct',   -5.000, 'below', 1,   'HYG 일일 -5% 이하 → L7 경고',     'structural'),
    ('S2.a', 'L7', 'alert', 'level',           500.000, 'above', NULL, 'HY OAS 500bps 이상 → L7 경고',    'structural'),
    ('S3.a', 'L8', 'watch', 'level',             0.050, 'above', NULL, 'SOFR-FF 갭 5bps 이상 → L8 경고',  'structural'),
    ('S2.c', 'L8', 'alert', 'daily_drop_pct',   -3.000, 'below', 1,   'LQD 일일 -3% 이하 → L8 경고',     'structural'),
    ('S2.a', 'L8', 'hard',  'level',           800.000, 'above', NULL, 'HY OAS 800bps 이상 → L8 경고',    'structural'),
    ('F5.a', NULL, 'watch', 'level_low',        15.000, 'below', NULL, 'VIX 15 이하 → 과도한 안심 경고',  'statistical'),
    ('S5.a', NULL, 'alert', 'inversion',         0.000, 'below', NULL, '10Y-2Y 역전 → 경기침체 신호',     'statistical'),
    ('S1.a', NULL, 'alert', 'level_high',        2.500, 'above', NULL, 'TIPS 실질금리 2.5%+ → 긴축 과도', 'structural');


-- ============================================================
-- 완료
-- ============================================================
-- 테이블: 26개
--   온톨로지 코어: 7 (ont_object, ont_property, ont_link, ont_metric, ont_threshold, ont_scenario + 3 logs)
--   시장 데이터:   3 (daily_macro, daily_market, daily_crypto)
--   추적:         8 (tc_cards, sd_cards, watches, predictions, sa_history, learning_log + 2 links)
--   브릿지:       2 (tc_ont_links, tc_metric_links)
--   전이 예측:    4 (th_cards, th_tc_links, th_evidence, th_link_path)
-- 뷰: 9개
-- 시드 데이터: ont_object(6), ont_property(14), ont_link(8), ont_metric(27), ont_threshold(10)
