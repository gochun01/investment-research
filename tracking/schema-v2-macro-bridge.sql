-- ============================================================
-- schema-v2-macro-bridge.sql
-- ont_metric macro_id 보강 + daily_macro 확장 + 판정 뷰
-- ============================================================

-- ============================================================
-- 1. ont_metric에 누락된 macro_id 부여 (16개)
-- ============================================================
-- F1.a(DXY)는 B2 유지. 건드리지 않는다.
-- 아래는 macro_id가 NULL인 것들.

-- layer_B 계열 (시장가격)
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'HYG'     WHERE metric_id = 'S2.b';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'LQD'     WHERE metric_id = 'S2.c';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'HYG_IEF' WHERE metric_id = 'S2.d';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'MMF'     WHERE metric_id = 'F2.a';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'SPY_VOL' WHERE metric_id = 'F2.b';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'EEM_SPY' WHERE metric_id = 'F3.a';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'STABLE'  WHERE metric_id = 'F4.a';
UPDATE ont_metric SET macro_layer = 'B', macro_id = 'IBIT'    WHERE metric_id = 'F4.b';
UPDATE ont_metric SET macro_layer = 'C', macro_id = 'C3b'     WHERE metric_id = 'S5.b';

-- layer_A 계열 (정성/서사)
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'DOT'     WHERE metric_id = 'P1.b';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'TARIFF'  WHERE metric_id = 'P2.a';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'AUTH'    WHERE metric_id = 'P2.b';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'TARGET'  WHERE metric_id = 'P2.c';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'GEO'     WHERE metric_id = 'P3.a';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'SWIFT'   WHERE metric_id = 'P3.c';
UPDATE ont_metric SET macro_layer = 'A', macro_id = 'REG'     WHERE metric_id = 'P4.a';


-- ============================================================
-- 2. daily_macro 테이블에 누락 컬럼 추가
-- ============================================================
-- 기존 27개 컬럼에 macro 46개 중 누락분 추가
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS usd_cny NUMERIC(8,4);
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS unemployment_rate NUMERIC(5,2);
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS us_m2 NUMERIC(15,2);
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS sloos TEXT;
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS fiscal_deficit_gdp NUMERIC(5,2);
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS cftc_jpy_net NUMERIC(12,0);
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS fed_watch TEXT;
ALTER TABLE daily_macro ADD COLUMN IF NOT EXISTS china_credit TEXT;


-- ============================================================
-- 3. v_macro_to_ontology — macro값 → 속성 상태 자동 판정
-- ============================================================
DROP VIEW IF EXISTS v_macro_to_ontology CASCADE;
CREATE VIEW v_macro_to_ontology AS
SELECT
    dm.snapshot_date,
    m.metric_id,
    m.property_id,
    p.name AS property_name,
    m.name AS metric_name,
    m.macro_id,
    -- 현재 값 추출 (macro_id → daily_macro 컬럼)
    CASE m.macro_id
        WHEN 'A1' THEN dm.core_pce_yoy
        WHEN 'B1' THEN dm.tips_10y_real
        WHEN 'B2' THEN dm.dxy_index
        WHEN 'B5' THEN dm.hy_oas
        WHEN 'C1' THEN dm.vix
        WHEN 'C3' THEN dm.yield_spread
        WHEN 'C5' THEN dm.ism_pmi
        WHEN 'C7' THEN dm.brent_crude
        WHEN 'C8' THEN dm.bei_10y
        WHEN 'D5' THEN dm.fed_balance_sheet
        WHEN 'D6' THEN dm.sofr_rate
        WHEN 'C10' THEN dm.fed_funds_rate
        WHEN 'D8' THEN dm.term_premium
        ELSE NULL
    END AS current_value,
    -- 속성 상태 판정
    CASE m.property_id
        WHEN 'P1' THEN  -- 중앙은행 방향
            CASE WHEN dm.core_pce_yoy > 2.5 THEN 'hawkish'
                 WHEN dm.core_pce_yoy < 2.0 THEN 'dovish'
                 ELSE 'neutral' END
        WHEN 'P3' THEN  -- 지정학
            CASE WHEN dm.brent_crude > 110 THEN 'elevated'
                 WHEN dm.brent_crude > 90 THEN 'tension'
                 ELSE 'calm' END
        WHEN 'S1' THEN  -- 실질금리
            CASE WHEN dm.tips_10y_real > 2.5 THEN 'restrictive'
                 WHEN dm.tips_10y_real > 1.5 THEN 'elevated'
                 ELSE 'accommodative' END
        WHEN 'S2' THEN  -- 신용 스프레드
            CASE WHEN dm.hy_oas > 500 THEN 'stress'
                 WHEN dm.hy_oas > 350 THEN 'widening'
                 ELSE 'normal' END
        WHEN 'S5' THEN  -- 텀프리미엄
            CASE WHEN dm.yield_spread < 0 THEN 'inverted'
                 WHEN dm.yield_spread < 0.3 THEN 'flat'
                 ELSE 'normal' END
        WHEN 'F1' THEN  -- DXY
            CASE WHEN dm.dxy_index > 105 THEN 'strong'
                 WHEN dm.dxy_index > 100 THEN 'firm'
                 WHEN dm.dxy_index < 95 THEN 'weak'
                 ELSE 'neutral' END
        WHEN 'F5' THEN  -- VIX
            CASE WHEN dm.vix > 35 THEN 'panic'
                 WHEN dm.vix > 25 THEN 'elevated'
                 WHEN dm.vix < 15 THEN 'complacent'
                 ELSE 'normal' END
        ELSE 'unknown'
    END AS property_verdict,
    -- 방향 판정
    CASE m.property_id
        WHEN 'P1' THEN CASE WHEN dm.core_pce_yoy > 2.5 THEN 'worsening' ELSE 'improving' END
        WHEN 'P3' THEN CASE WHEN dm.brent_crude > 100 THEN 'worsening' ELSE 'improving' END
        WHEN 'S1' THEN CASE WHEN dm.tips_10y_real > 2.0 THEN 'worsening' ELSE 'improving' END
        WHEN 'S2' THEN CASE WHEN dm.hy_oas > 350 THEN 'worsening' ELSE 'stable' END
        WHEN 'F5' THEN CASE WHEN dm.vix > 25 THEN 'worsening' ELSE 'stable' END
        ELSE 'unknown'
    END AS direction
FROM ont_metric m
JOIN ont_property p ON m.property_id = p.property_id
CROSS JOIN (SELECT * FROM daily_macro ORDER BY snapshot_date DESC LIMIT 1) dm
WHERE m.macro_id IS NOT NULL
  AND CASE m.macro_id
        WHEN 'A1' THEN dm.core_pce_yoy IS NOT NULL
        WHEN 'B1' THEN dm.tips_10y_real IS NOT NULL
        WHEN 'B2' THEN dm.dxy_index IS NOT NULL
        WHEN 'B5' THEN dm.hy_oas IS NOT NULL
        WHEN 'C1' THEN dm.vix IS NOT NULL
        WHEN 'C7' THEN dm.brent_crude IS NOT NULL
        WHEN 'C8' THEN dm.bei_10y IS NOT NULL
        ELSE false
    END
ORDER BY m.property_id, m.metric_id;


-- ============================================================
-- 4. v_threshold_check — 현재값 × 임계값 밴드 판정
-- ============================================================
DROP VIEW IF EXISTS v_threshold_check CASCADE;
CREATE VIEW v_threshold_check AS
SELECT
    t.metric_id,
    m.name AS metric_name,
    m.property_id,
    t.link_id,
    l.name AS link_name,
    t.band,
    t.threshold_value,
    t.threshold_direction,
    t.duration_days,
    t.source_type,
    -- 현재값
    CASE m.macro_id
        WHEN 'A1' THEN dm.core_pce_yoy
        WHEN 'B1' THEN dm.tips_10y_real
        WHEN 'B2' THEN dm.dxy_index
        WHEN 'B5' THEN dm.hy_oas
        WHEN 'C1' THEN dm.vix
        WHEN 'C3' THEN dm.yield_spread
        WHEN 'C7' THEN dm.brent_crude
        WHEN 'C8' THEN dm.bei_10y
        WHEN 'D6' THEN dm.sofr_rate
        ELSE NULL
    END AS current_value,
    -- 밴드 돌파 여부
    CASE
        WHEN t.threshold_direction = 'above' AND
             CASE m.macro_id
                WHEN 'B5' THEN dm.hy_oas WHEN 'C1' THEN dm.vix
                WHEN 'B1' THEN dm.tips_10y_real WHEN 'D6' THEN dm.sofr_rate
                ELSE NULL END >= t.threshold_value
            THEN true
        WHEN t.threshold_direction = 'below' AND
             CASE m.macro_id
                WHEN 'C1' THEN dm.vix WHEN 'C3' THEN dm.yield_spread
                ELSE NULL END <= t.threshold_value
            THEN true
        ELSE false
    END AS breached,
    -- 임계까지 거리
    ABS(COALESCE(
        CASE m.macro_id
            WHEN 'B5' THEN dm.hy_oas WHEN 'C1' THEN dm.vix
            WHEN 'B1' THEN dm.tips_10y_real WHEN 'C3' THEN dm.yield_spread
            WHEN 'D6' THEN dm.sofr_rate
            ELSE NULL END, 0
    ) - t.threshold_value) AS distance,
    dm.snapshot_date
FROM ont_threshold t
JOIN ont_metric m ON t.metric_id = m.metric_id
LEFT JOIN ont_link l ON t.link_id = l.link_id
CROSS JOIN (SELECT * FROM daily_macro ORDER BY snapshot_date DESC LIMIT 1) dm
WHERE t.is_active
ORDER BY
    CASE WHEN t.threshold_direction = 'above' AND
        CASE m.macro_id WHEN 'B5' THEN dm.hy_oas WHEN 'C1' THEN dm.vix
            WHEN 'B1' THEN dm.tips_10y_real ELSE NULL END >= t.threshold_value
        THEN 0
        WHEN t.threshold_direction = 'below' AND
        CASE m.macro_id WHEN 'C1' THEN dm.vix WHEN 'C3' THEN dm.yield_spread ELSE NULL END <= t.threshold_value
        THEN 0
        ELSE 1 END,
    ABS(COALESCE(CASE m.macro_id WHEN 'B5' THEN dm.hy_oas WHEN 'C1' THEN dm.vix
        WHEN 'B1' THEN dm.tips_10y_real WHEN 'C3' THEN dm.yield_spread ELSE NULL END, 0) - t.threshold_value);


-- ============================================================
-- 5. v_psf_dashboard — PSF 3층 상태 종합 (전이 판단 원스톱)
-- ============================================================
DROP VIEW IF EXISTS v_psf_dashboard CASCADE;
CREATE VIEW v_psf_dashboard AS
SELECT
    o.layer,
    o.name AS object_name,
    p.property_id,
    p.name AS property_name,
    -- 최신 macro 기반 판정
    mo.current_value,
    mo.property_verdict,
    mo.direction,
    -- 임계값 돌파 여부
    (SELECT count(*) FROM v_threshold_check tc
     WHERE tc.property_id = p.property_id AND tc.breached) AS thresholds_breached,
    -- TC 관여 수
    (SELECT count(DISTINCT tol.tc_id) FROM tc_ont_links tol
     JOIN ont_link ol ON tol.link_id = ol.link_id
     WHERE ol.source_object = o.object_id OR ol.target_object = o.object_id) AS tc_involvement,
    -- 인과 링크 활성 여부
    (SELECT count(*) FROM ont_link ol
     WHERE (ol.source_object = o.object_id OR ol.target_object = o.object_id) AND ol.is_active) AS active_links
FROM ont_property p
JOIN ont_object o ON p.object_id = o.object_id
LEFT JOIN LATERAL (
    SELECT current_value, property_verdict, direction
    FROM v_macro_to_ontology v
    WHERE v.property_id = p.property_id
    LIMIT 1
) mo ON true
ORDER BY
    CASE o.layer WHEN 'pan' THEN 1 WHEN 'structure' THEN 2 WHEN 'flow' THEN 3 END,
    p.property_id;
