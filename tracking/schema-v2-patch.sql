-- ============================================================
-- schema-v2-patch.sql — 누락 테이블/뷰 보강
-- ============================================================
-- 기존 schema-v2.sql에 없는 테이블/뷰를 추가.
-- 멱등성 보장: IF NOT EXISTS 사용.
--
-- 사용법:
--   docker exec invest-ontology-db psql -U investor -d invest_ontology -f /tmp/schema-v2-patch.sql
-- ============================================================


-- ============================================================
-- 1. tc_scenario_history (시나리오 확률 변화 이력)
-- cycle3, db_sync에서 사용. schema-v2에 누락.
-- ============================================================
CREATE TABLE IF NOT EXISTS tc_scenario_history (
    id              SERIAL PRIMARY KEY,
    tc_id           VARCHAR(10) NOT NULL REFERENCES tc_cards(tc_id),
    snapshot_date   DATE NOT NULL,
    scenario        VARCHAR(5) NOT NULL,
    probability     VARCHAR(10) NOT NULL,
    prev_probability VARCHAR(10),
    delta_reason    TEXT NOT NULL,
    source_analysis VARCHAR(30),
    trigger_distance TEXT,
    kc_status       VARCHAR(20) DEFAULT 'normal'
                    CHECK (kc_status IN ('normal','watch','alert','hard')),
    created_at      TIMESTAMP DEFAULT now(),
    UNIQUE (tc_id, snapshot_date, scenario)
);
CREATE INDEX IF NOT EXISTS idx_tsh_tc ON tc_scenario_history(tc_id);
CREATE INDEX IF NOT EXISTS idx_tsh_date ON tc_scenario_history(snapshot_date);


-- ============================================================
-- 2. quality_diagnostics (품질 진단 결과 축적)
-- quality_check.py에서 사용.
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_diagnostics (
    id              SERIAL PRIMARY KEY,
    run_date        DATE NOT NULL UNIQUE,
    total_checks    INTEGER NOT NULL,
    critical_count  INTEGER NOT NULL DEFAULT 0,
    warning_count   INTEGER NOT NULL DEFAULT 0,
    info_count      INTEGER NOT NULL DEFAULT 0,
    details         JSONB,
    fixed_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_qd_date ON quality_diagnostics(run_date DESC);


-- ============================================================
-- 3. v_transition_timeline (전이 타임라인 뷰)
-- cycle3, visualize_transition에서 사용. schema-v2에 누락.
-- ============================================================
CREATE OR REPLACE VIEW v_transition_timeline AS
SELECT
    th.th_id,
    th.hypothesis,
    th.from_regime,
    th.to_regime,
    th.horizon,
    th.confidence,
    th.status,
    th.created AS start_date,
    CASE th.horizon
        WHEN 'short' THEN th.created + INTERVAL '3 months'
        WHEN 'mid'   THEN th.created + INTERVAL '6 months'
        WHEN 'long'  THEN th.created + INTERVAL '12 months'
        ELSE th.created + INTERVAL '6 months'
    END AS target_date,
    (SELECT count(*) FROM th_tc_links WHERE th_id = th.th_id) AS convergence_count,
    (SELECT count(*) FROM th_evidence WHERE th_id = th.th_id) AS evidence_count,
    (SELECT AVG(confidence_delta)
     FROM (
         SELECT confidence_delta
         FROM th_evidence
         WHERE th_id = th.th_id AND confidence_delta IS NOT NULL
         ORDER BY ev_date DESC, id DESC
         LIMIT 5
     ) sub
    ) AS recent_delta_trend,
    (SELECT json_agg(json_build_object('tc_id', tc_id, 'role', role))
     FROM th_tc_links WHERE th_id = th.th_id
    ) AS members
FROM th_cards th
WHERE th.status = 'active'
ORDER BY th.confidence DESC;


-- ============================================================
-- 4. v_quality_summary (품질 추이 요약 뷰)
-- quality_check.py 대시보드용.
-- ============================================================
CREATE OR REPLACE VIEW v_quality_summary AS
SELECT
    run_date,
    total_checks,
    critical_count,
    warning_count,
    info_count,
    fixed_count,
    ROUND(
        (total_checks - critical_count - warning_count)::NUMERIC /
        NULLIF(total_checks, 0), 3
    ) AS health_score
FROM quality_diagnostics
ORDER BY run_date DESC
LIMIT 30;


-- ============================================================
-- 5. v_pipeline_health (파이프라인 건강 현황 뷰)
-- ============================================================
CREATE OR REPLACE VIEW v_pipeline_health AS
SELECT
    'TC Cards' AS component,
    (SELECT count(*) FROM tc_cards WHERE status = 'active') AS active_count,
    (SELECT count(*) FROM tc_cards WHERE status = 'active' AND phase >= 2) AS escalated_count,
    NULL::BIGINT AS overdue_count
UNION ALL
SELECT
    'SD Cards',
    (SELECT count(*) FROM sd_cards WHERE status = 'watching'),
    (SELECT count(*) FROM sd_cards WHERE status = 'watching' AND appearance_count >= 3),
    NULL
UNION ALL
SELECT
    'Watches',
    (SELECT count(*) FROM watches WHERE status = 'active'),
    NULL,
    (SELECT count(*) FROM watches
     WHERE status = 'active'
     AND (schedule->>'next_check')::date < CURRENT_DATE)
UNION ALL
SELECT
    'Predictions',
    (SELECT count(*) FROM predictions WHERE status = 'open'),
    (SELECT count(*) FROM predictions WHERE status IN ('hit','miss','partial')),
    (SELECT count(*) FROM predictions
     WHERE status = 'open' AND deadline < CURRENT_DATE)
UNION ALL
SELECT
    'TH Cards',
    (SELECT count(*) FROM th_cards WHERE status = 'active'),
    (SELECT count(*) FROM th_cards WHERE status = 'active' AND confidence >= 0.5),
    (SELECT count(*) FROM th_cards
     WHERE status = 'active' AND next_review < CURRENT_DATE);


-- ============================================================
-- 6. 기존 뷰 갱신 (안전: CREATE OR REPLACE)
-- ============================================================

-- v_watch_due에 overdue 일수 추가
CREATE OR REPLACE VIEW v_watch_due AS
SELECT
    w.watch_id, w.subject, w.watch_type,
    (w.schedule->>'next_check')::DATE AS next_check,
    CURRENT_DATE - (w.schedule->>'next_check')::DATE AS overdue_days,
    w.status,
    array_agg(wtl.tc_id) FILTER (WHERE wtl.tc_id IS NOT NULL) AS linked_tc,
    jsonb_array_length(COALESCE(w.completed_checks, '[]'::jsonb)) AS check_count
FROM watches w
LEFT JOIN watch_tc_links wtl ON w.watch_id = wtl.watch_id
WHERE w.status = 'active'
GROUP BY w.watch_id, w.subject, w.watch_type, w.schedule, w.status, w.completed_checks
ORDER BY (w.schedule->>'next_check')::DATE;
