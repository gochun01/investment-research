-- ============================================================
-- schema-v2-views.sql — JSONB 구조화 뷰
-- ============================================================
-- tc_cards.scenarios / tracking_indicators JSONB를 SQL로 펼쳐서
-- 전이 경로의 시간·거리·임계 판정을 쿼리 가능하게 만든다.
--
-- 사용법:
--   cat schema-v2-views.sql | docker exec -i invest-ontology-db psql -U investor -d invest_ontology
-- ============================================================


-- ============================================================
-- 1. v_scenario_detail — 시나리오 JSONB 완전 펼치기
-- ============================================================
DROP VIEW IF EXISTS v_scenario_detail CASCADE;
CREATE VIEW v_scenario_detail AS
SELECT
    tc.tc_id,
    tc.title,
    tc.phase,
    (tc.pre_read->>'scp')::INTEGER AS scp,
    tc.pre_read->>'type' AS issue_type,
    sk.key AS scenario,
    sk.value->>'label' AS label,
    sk.value->>'probability' AS probability,
    sk.value->>'current_status' AS current_status,

    -- trigger (dict 내부)
    sk.value->'trigger'->>'condition' AS trigger_condition,
    sk.value->'trigger'->>'source' AS trigger_source,
    sk.value->'trigger'->>'distance' AS trigger_distance,
    sk.value->'trigger'->>'recalibration' AS recalibration,

    -- kc (3-band + action)
    sk.value->'kc'->>'watch' AS kc_watch,
    sk.value->'kc'->>'alert' AS kc_alert,
    sk.value->'kc'->>'hard' AS kc_hard,
    sk.value->'kc'->>'action' AS kc_action,

    -- base case 여부
    COALESCE((sk.value->>'base')::BOOLEAN, false) AS is_base_case

FROM tc_cards tc,
     jsonb_each(tc.scenarios) AS sk
WHERE tc.status = 'active'
ORDER BY tc.tc_id, sk.key;


-- ============================================================
-- 2. v_tracking_indicators — 추적 지표 펼치기
-- ============================================================
DROP VIEW IF EXISTS v_tracking_indicators CASCADE;
CREATE VIEW v_tracking_indicators AS
SELECT
    tc.tc_id,
    ti->>'indicator' AS indicator,
    ti->>'symbol' AS symbol,
    ti->>'current' AS current_value,
    ti->>'threshold' AS threshold,
    (ti->>'next_check')::DATE AS next_check,
    (ti->>'last_check')::DATE AS last_check,
    CURRENT_DATE - (ti->>'next_check')::DATE AS overdue_days
FROM tc_cards tc,
     jsonb_array_elements(tc.tracking_indicators) AS ti
WHERE tc.status = 'active'
  AND tc.tracking_indicators IS NOT NULL
ORDER BY (ti->>'next_check')::DATE;


-- ============================================================
-- 3. v_next_gates — 다음 분기점 (날짜순 임계값 접근)
-- ============================================================
DROP VIEW IF EXISTS v_next_gates CASCADE;
CREATE VIEW v_next_gates AS
SELECT
    tc_id,
    indicator,
    symbol,
    current_value,
    threshold,
    next_check,
    overdue_days,
    CASE
        WHEN overdue_days > 0 THEN 'OVERDUE'
        WHEN overdue_days >= -3 THEN 'IMMINENT'
        WHEN overdue_days >= -7 THEN 'THIS_WEEK'
        WHEN overdue_days >= -30 THEN 'THIS_MONTH'
        ELSE 'LATER'
    END AS urgency
FROM v_tracking_indicators
ORDER BY next_check;


-- ============================================================
-- 4. v_trigger_proximity — 시나리오 trigger까지 거리
-- ============================================================
DROP VIEW IF EXISTS v_trigger_proximity CASCADE;
CREATE VIEW v_trigger_proximity AS
SELECT
    tc_id,
    scenario,
    label,
    probability,
    trigger_condition,
    trigger_distance,
    trigger_source,
    recalibration,
    kc_action,
    current_status,
    -- 거리가 있는 것만 (NULL이면 정성적 trigger)
    CASE
        WHEN trigger_distance IS NOT NULL AND trigger_distance != '' THEN 'QUANTIFIED'
        ELSE 'QUALITATIVE'
    END AS distance_type
FROM v_scenario_detail
WHERE trigger_distance IS NOT NULL AND trigger_distance != ''
ORDER BY tc_id, scenario;


-- ============================================================
-- 5. v_prediction_timeline — 예측 deadline 분포
-- ============================================================
DROP VIEW IF EXISTS v_prediction_timeline CASCADE;
CREATE VIEW v_prediction_timeline AS
SELECT
    p.pred_id,
    p.tc_id,
    p.scenario,
    p.probability,
    p.claim,
    p.trigger_condition,
    p.deadline,
    p.status,
    p.deadline - CURRENT_DATE AS days_remaining,
    CASE
        WHEN p.status != 'open' THEN 'RESOLVED'
        WHEN p.deadline < CURRENT_DATE THEN 'EXPIRED'
        WHEN p.deadline - CURRENT_DATE <= 7 THEN 'THIS_WEEK'
        WHEN p.deadline - CURRENT_DATE <= 30 THEN 'THIS_MONTH'
        WHEN p.deadline - CURRENT_DATE <= 90 THEN 'THIS_QUARTER'
        ELSE 'LATER'
    END AS time_bucket,
    -- deadline 월별 그룹
    TO_CHAR(p.deadline, 'YYYY-MM') AS deadline_month
FROM predictions p
ORDER BY p.deadline;


-- ============================================================
-- 6. v_prediction_deadline_distribution — 월별 deadline 집계
-- ============================================================
DROP VIEW IF EXISTS v_prediction_deadline_distribution CASCADE;
CREATE VIEW v_prediction_deadline_distribution AS
SELECT
    TO_CHAR(deadline, 'YYYY-MM') AS month,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
    COUNT(*) FILTER (WHERE status IN ('hit','miss','partial')) AS resolved_count,
    MIN(deadline) AS earliest,
    MAX(deadline) AS latest
FROM predictions
GROUP BY TO_CHAR(deadline, 'YYYY-MM')
ORDER BY month;


-- ============================================================
-- 7. v_th_timeline — TH 전이 가설 시간축 (target_date 계산)
-- ============================================================
DROP VIEW IF EXISTS v_th_full_timeline CASCADE;
CREATE VIEW v_th_full_timeline AS
SELECT
    th.th_id,
    th.hypothesis,
    th.from_regime,
    th.to_regime,
    th.confidence,
    th.horizon,
    th.created AS start_date,
    -- target_date: horizon에서 계산
    CASE th.horizon
        WHEN 'short' THEN th.created + INTERVAL '3 months'
        WHEN 'mid'   THEN th.created + INTERVAL '6 months'
        WHEN 'long'  THEN th.created + INTERVAL '12 months'
        ELSE th.created + INTERVAL '6 months'
    END AS target_date,
    -- 남은 일수
    (CASE th.horizon
        WHEN 'short' THEN th.created + INTERVAL '3 months'
        WHEN 'mid'   THEN th.created + INTERVAL '6 months'
        WHEN 'long'  THEN th.created + INTERVAL '12 months'
        ELSE th.created + INTERVAL '6 months'
    END)::DATE - CURRENT_DATE AS days_remaining,
    -- 경과 비율
    ROUND(
        (CURRENT_DATE - th.created)::NUMERIC /
        NULLIF(((CASE th.horizon
            WHEN 'short' THEN th.created + INTERVAL '3 months'
            WHEN 'mid'   THEN th.created + INTERVAL '6 months'
            WHEN 'long'  THEN th.created + INTERVAL '12 months'
            ELSE th.created + INTERVAL '6 months'
        END)::DATE - th.created), 0), 3
    ) AS elapsed_ratio,
    -- 수렴 멤버 수
    (SELECT count(*) FROM th_tc_links WHERE th_id = th.th_id) AS member_count,
    -- 인과 경로 활성 비율
    (SELECT count(*) FILTER (WHERE is_active) FROM th_link_path WHERE th_id = th.th_id) AS active_path_steps,
    (SELECT count(*) FROM th_link_path WHERE th_id = th.th_id) AS total_path_steps,
    -- 연결된 prediction 수
    (SELECT count(*)
     FROM predictions p
     JOIN th_tc_links tl ON p.tc_id = tl.tc_id
     WHERE tl.th_id = th.th_id AND p.status = 'open'
    ) AS open_predictions,
    -- 가장 가까운 prediction deadline
    (SELECT min(p.deadline)
     FROM predictions p
     JOIN th_tc_links tl ON p.tc_id = tl.tc_id
     WHERE tl.th_id = th.th_id AND p.status = 'open'
    ) AS nearest_prediction_deadline,
    th.status
FROM th_cards th
WHERE th.status = 'active'
ORDER BY th.confidence DESC;


-- ============================================================
-- 8. v_kc_status_board — KC 밴드 현황판
-- ============================================================
DROP VIEW IF EXISTS v_kc_status_board CASCADE;
CREATE VIEW v_kc_status_board AS
SELECT
    sd.tc_id,
    sd.scenario,
    sd.label,
    sd.probability,
    sd.trigger_distance,
    sd.kc_watch,
    sd.kc_alert,
    sd.kc_hard,
    sd.kc_action,
    -- tc_scenario_history에서 최근 kc_status
    COALESCE(
        (SELECT tsh.kc_status
         FROM tc_scenario_history tsh
         WHERE tsh.tc_id = sd.tc_id AND tsh.scenario = sd.scenario
         ORDER BY tsh.snapshot_date DESC LIMIT 1),
        'normal'
    ) AS last_kc_status,
    sd.current_status
FROM v_scenario_detail sd
ORDER BY
    CASE COALESCE(
        (SELECT tsh.kc_status
         FROM tc_scenario_history tsh
         WHERE tsh.tc_id = sd.tc_id AND tsh.scenario = sd.scenario
         ORDER BY tsh.snapshot_date DESC LIMIT 1),
        'normal')
        WHEN 'hard' THEN 1
        WHEN 'alert' THEN 2
        WHEN 'watch' THEN 3
        ELSE 4
    END,
    sd.tc_id, sd.scenario;


-- ============================================================
-- 9. v_transition_readiness — 전이 준비도 종합
-- ============================================================
DROP VIEW IF EXISTS v_transition_readiness CASCADE;
CREATE VIEW v_transition_readiness AS
SELECT
    th.th_id,
    th.hypothesis,
    th.confidence,
    th.days_remaining,
    th.elapsed_ratio,
    -- 인과 경로 활성 비율
    CASE WHEN th.total_path_steps > 0
         THEN ROUND(th.active_path_steps::NUMERIC / th.total_path_steps, 2)
         ELSE 0 END AS path_activation_ratio,
    th.member_count,
    th.open_predictions,
    th.nearest_prediction_deadline,
    th.nearest_prediction_deadline - CURRENT_DATE AS days_to_nearest_test,
    -- KC watch 이상 시나리오 수 (멤버 TC 중)
    (SELECT count(DISTINCT (tsh.tc_id, tsh.scenario))
     FROM tc_scenario_history tsh
     JOIN th_tc_links tl ON tsh.tc_id = tl.tc_id
     WHERE tl.th_id = th.th_id
       AND tsh.kc_status IN ('watch','alert','hard')
       AND tsh.snapshot_date = (SELECT max(snapshot_date) FROM tc_scenario_history)
    ) AS scenarios_in_kc_band,
    -- 레짐
    (SELECT regime FROM ont_regime_log ORDER BY log_date DESC LIMIT 1) AS current_regime,
    (SELECT keystone_direction FROM ont_regime_log ORDER BY log_date DESC LIMIT 1) AS keystone_direction
FROM v_th_full_timeline th;
