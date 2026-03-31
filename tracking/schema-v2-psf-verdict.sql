-- ============================================================
-- schema-v2-psf-verdict.sql
-- 14개 PSF 속성 전부에 판정 로직 부여
-- ============================================================

DROP VIEW IF EXISTS v_psf_dashboard CASCADE;
DROP VIEW IF EXISTS v_macro_to_ontology CASCADE;

-- ============================================================
-- v_macro_to_ontology — 14속성 완전 판정
-- ============================================================
CREATE VIEW v_macro_to_ontology AS
SELECT
    dm.snapshot_date,
    m.metric_id,
    m.property_id,
    p.name AS property_name,
    o.layer,
    m.name AS metric_name,
    m.macro_id,
    -- 현재 값 추출
    CASE m.macro_id
        WHEN 'A1' THEN dm.core_pce_yoy
        WHEN 'B1' THEN dm.tips_10y_real
        WHEN 'B2' THEN dm.dxy_index
        WHEN 'B3' THEN dm.usd_jpy
        WHEN 'B5' THEN dm.hy_oas
        WHEN 'C1' THEN dm.vix
        WHEN 'C2' THEN dm.move_index
        WHEN 'C3' THEN dm.yield_spread
        WHEN 'C5' THEN dm.ism_pmi
        WHEN 'C7' THEN dm.brent_crude
        WHEN 'C8' THEN dm.bei_10y
        WHEN 'C10' THEN dm.fed_funds_rate
        WHEN 'D5' THEN dm.fed_balance_sheet
        WHEN 'D6' THEN dm.sofr_rate
        WHEN 'D8' THEN dm.term_premium
        ELSE NULL
    END AS current_value,
    -- ━━━━ 14속성 판정 ━━━━
    CASE m.property_id
        -- ── 판(Pan) ──
        WHEN 'P1' THEN  -- 중앙은행 방향: Core PCE + Fed Funds Rate
            CASE WHEN dm.core_pce_yoy > 3.0 THEN 'hawkish_urgent'
                 WHEN dm.core_pce_yoy > 2.5 THEN 'hawkish'
                 WHEN dm.core_pce_yoy < 2.0 THEN 'dovish'
                 ELSE 'neutral' END
        WHEN 'P2' THEN  -- 관세: TC 관여 수로 대리 판정
            CASE WHEN (SELECT count(*) FROM tc_ont_links WHERE link_id = 'L2') >= 5 THEN 'high_pressure'
                 WHEN (SELECT count(*) FROM tc_ont_links WHERE link_id = 'L2') >= 3 THEN 'moderate'
                 ELSE 'low' END
        WHEN 'P3' THEN  -- 지정학: Brent 유가
            CASE WHEN dm.brent_crude > 120 THEN 'crisis'
                 WHEN dm.brent_crude > 110 THEN 'elevated'
                 WHEN dm.brent_crude > 90 THEN 'tension'
                 ELSE 'calm' END
        WHEN 'P4' THEN  -- 규제: TC 관여로 대리
            CASE WHEN (SELECT count(*) FROM tc_ont_links tol
                       JOIN tc_cards tc ON tol.tc_id = tc.tc_id
                       WHERE tc.pre_read->>'type' LIKE '%POLICY%') >= 3 THEN 'active'
                 ELSE 'quiet' END
        -- ── 구조(Structure) ──
        WHEN 'S1' THEN  -- 실질금리: TIPS 10Y
            CASE WHEN dm.tips_10y_real > 2.5 THEN 'restrictive'
                 WHEN dm.tips_10y_real > 2.0 THEN 'tight'
                 WHEN dm.tips_10y_real > 1.5 THEN 'elevated'
                 WHEN dm.tips_10y_real > 0.5 THEN 'neutral'
                 ELSE 'accommodative' END
        WHEN 'S2' THEN  -- 신용 스프레드: HY OAS
            CASE WHEN dm.hy_oas > 800 THEN 'crisis'
                 WHEN dm.hy_oas > 500 THEN 'stress'
                 WHEN dm.hy_oas > 400 THEN 'widening'
                 WHEN dm.hy_oas > 350 THEN 'caution'
                 ELSE 'normal' END
        WHEN 'S3' THEN  -- SOFR 스프레드: SOFR vs Fed Funds
            CASE WHEN dm.sofr_rate IS NOT NULL AND dm.fed_funds_rate IS NOT NULL
                 THEN CASE WHEN ABS(dm.sofr_rate - dm.fed_funds_rate) > 0.10 THEN 'stress'
                           WHEN ABS(dm.sofr_rate - dm.fed_funds_rate) > 0.05 THEN 'elevated'
                           ELSE 'normal' END
                 ELSE 'unknown' END
        WHEN 'S4' THEN  -- 실물 확인: ISM PMI
            CASE WHEN dm.ism_pmi > 55 THEN 'expansion'
                 WHEN dm.ism_pmi > 50 THEN 'growth'
                 WHEN dm.ism_pmi > 45 THEN 'slowdown'
                 ELSE 'contraction' END
        WHEN 'S5' THEN  -- 텀프리미엄: 10Y-2Y + term premium
            CASE WHEN dm.yield_spread < 0 THEN 'inverted'
                 WHEN dm.yield_spread < 0.2 THEN 'flat'
                 WHEN dm.term_premium > 0.8 THEN 'steep_premium'
                 WHEN dm.yield_spread > 0.5 THEN 'normal'
                 ELSE 'neutral' END
        -- ── 흐름(Flow) ──
        WHEN 'F1' THEN  -- DXY
            CASE WHEN dm.dxy_index > 108 THEN 'very_strong'
                 WHEN dm.dxy_index > 103 THEN 'strong'
                 WHEN dm.dxy_index > 100 THEN 'firm'
                 WHEN dm.dxy_index > 97 THEN 'neutral'
                 WHEN dm.dxy_index < 95 THEN 'weak'
                 ELSE 'neutral' END
        WHEN 'F2' THEN  -- 자산군 플로우: MMF 잔고 (있으면) 또는 VIX 대리
            CASE WHEN dm.mmf_balance IS NOT NULL
                 THEN CASE WHEN dm.mmf_balance > 6000 THEN 'risk_off_heavy'
                           WHEN dm.mmf_balance > 5500 THEN 'cautious'
                           ELSE 'risk_on' END
                 ELSE CASE WHEN dm.vix > 30 THEN 'risk_off'
                           WHEN dm.vix > 25 THEN 'cautious'
                           ELSE 'risk_on' END END
        WHEN 'F3' THEN  -- DM-EM: USD/JPY + DXY 조합으로 대리
            CASE WHEN dm.dxy_index > 103 AND dm.usd_jpy > 155 THEN 'dm_dominant'
                 WHEN dm.dxy_index < 97 THEN 'em_recovering'
                 ELSE 'neutral' END
        WHEN 'F4' THEN  -- 크립토 유동성: 데이터 없으면 VIX 대리
            CASE WHEN dm.vix > 30 THEN 'risk_off'
                 WHEN dm.vix < 18 THEN 'risk_on_strong'
                 ELSE 'neutral' END
        WHEN 'F5' THEN  -- VIX
            CASE WHEN dm.vix > 40 THEN 'panic'
                 WHEN dm.vix > 30 THEN 'fear'
                 WHEN dm.vix > 25 THEN 'elevated'
                 WHEN dm.vix > 18 THEN 'normal'
                 WHEN dm.vix < 13 THEN 'complacent'
                 ELSE 'calm' END
        ELSE 'unknown'
    END AS property_verdict,
    -- ━━━━ 방향 판정 ━━━━
    CASE m.property_id
        WHEN 'P1' THEN CASE WHEN dm.core_pce_yoy > 2.5 THEN 'worsening' ELSE 'improving' END
        WHEN 'P2' THEN CASE WHEN (SELECT count(*) FROM tc_ont_links WHERE link_id = 'L2') >= 5 THEN 'worsening' ELSE 'stable' END
        WHEN 'P3' THEN CASE WHEN dm.brent_crude > 100 THEN 'worsening' WHEN dm.brent_crude > 80 THEN 'tension' ELSE 'improving' END
        WHEN 'P4' THEN 'stable'
        WHEN 'S1' THEN CASE WHEN dm.tips_10y_real > 2.0 THEN 'tightening' ELSE 'easing' END
        WHEN 'S2' THEN CASE WHEN dm.hy_oas > 400 THEN 'worsening' WHEN dm.hy_oas > 350 THEN 'caution' ELSE 'stable' END
        WHEN 'S3' THEN CASE WHEN ABS(COALESCE(dm.sofr_rate,0) - COALESCE(dm.fed_funds_rate,0)) > 0.05 THEN 'stress' ELSE 'normal' END
        WHEN 'S4' THEN CASE WHEN dm.ism_pmi > 50 THEN 'expanding' ELSE 'contracting' END
        WHEN 'S5' THEN CASE WHEN dm.yield_spread < 0.2 THEN 'flattening' WHEN dm.term_premium > 0.8 THEN 'steepening' ELSE 'stable' END
        WHEN 'F1' THEN CASE WHEN dm.dxy_index > 100 THEN 'strengthening' ELSE 'weakening' END
        WHEN 'F2' THEN CASE WHEN dm.vix > 25 THEN 'risk_off' ELSE 'risk_on' END
        WHEN 'F3' THEN CASE WHEN dm.dxy_index > 103 THEN 'dm_dominant' ELSE 'neutral' END
        WHEN 'F4' THEN CASE WHEN dm.vix > 25 THEN 'risk_off' ELSE 'neutral' END
        WHEN 'F5' THEN CASE WHEN dm.vix > 25 THEN 'worsening' ELSE 'stable' END
        ELSE 'unknown'
    END AS direction
FROM ont_metric m
JOIN ont_property p ON m.property_id = p.property_id
JOIN ont_object o ON p.object_id = o.object_id
CROSS JOIN (SELECT * FROM daily_macro ORDER BY snapshot_date DESC LIMIT 1) dm
-- 속성당 대표 지표 1개만 (중복 방지)
WHERE m.metric_id IN (
    'P1.a',  -- Core PCE → P1
    'P2.a',  -- 유효관세율 → P2
    'P3.b',  -- Brent → P3
    'P4.a',  -- 규제 → P4
    'S1.a',  -- TIPS → S1
    'S2.a',  -- HY OAS → S2
    'S3.a',  -- SOFR → S3
    'S4.a',  -- ISM PMI → S4
    'S5.a',  -- 10Y-2Y → S5
    'F1.a',  -- DXY → F1
    'F2.a',  -- MMF → F2
    'F3.a',  -- EEM/SPY → F3
    'F4.a',  -- 스테이블 → F4
    'F5.a'   -- VIX → F5
)
ORDER BY
    CASE o.layer WHEN 'pan' THEN 1 WHEN 'structure' THEN 2 WHEN 'flow' THEN 3 END,
    p.property_id;


-- ============================================================
-- v_psf_dashboard 재생성 (14속성 완전 판정 기반)
-- ============================================================
CREATE VIEW v_psf_dashboard AS
SELECT
    o.layer,
    o.name AS object_name,
    p.property_id,
    p.name AS property_name,
    mo.current_value,
    mo.property_verdict,
    mo.direction,
    -- 임계값 돌파 수
    (SELECT count(*) FROM v_threshold_check tc
     WHERE tc.property_id = p.property_id AND tc.breached) AS thresholds_breached,
    -- TC 관여 수
    (SELECT count(DISTINCT tol.tc_id) FROM tc_ont_links tol
     JOIN ont_link ol ON tol.link_id = ol.link_id
     WHERE ol.source_object = o.object_id OR ol.target_object = o.object_id) AS tc_involvement,
    -- 인과 링크 활성
    (SELECT count(*) FROM ont_link ol
     WHERE (ol.source_object = o.object_id OR ol.target_object = o.object_id) AND ol.is_active) AS active_links,
    -- ont_status_log 최신 verdict
    (SELECT verdict FROM ont_status_log sl
     WHERE sl.property_id = p.property_id
     ORDER BY sl.snapshot_date DESC LIMIT 1) AS last_logged_verdict
FROM ont_property p
JOIN ont_object o ON p.object_id = o.object_id
LEFT JOIN v_macro_to_ontology mo ON mo.property_id = p.property_id
ORDER BY
    CASE o.layer WHEN 'pan' THEN 1 WHEN 'structure' THEN 2 WHEN 'flow' THEN 3 END,
    p.property_id;
