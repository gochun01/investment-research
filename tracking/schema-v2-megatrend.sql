-- ============================================================
-- schema-v2-megatrend.sql — 메가트렌드 축 + PSF 병렬 구조
-- ============================================================
-- PSF = "지금 돈이 어디로 가는가" (주~분기)
-- MT  = "5년 후 세상이 어떤 모양인가" (분기~년)
-- TC  = 양쪽에 걸침. PSF가 타이밍, MT가 방향.
-- ============================================================


-- ============================================================
-- 1. ont_megatrend — 메가트렌드 정의
-- ============================================================
CREATE TABLE IF NOT EXISTS ont_megatrend (
    mt_id           VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    hypothesis      TEXT NOT NULL,
    direction       VARCHAR(30) NOT NULL
                    CHECK (direction IN (
                        'accelerating','decelerating','inflecting',
                        'emerging','maturing','reversing'
                    )),
    confidence      NUMERIC(4,3) DEFAULT 0.5
                    CHECK (confidence BETWEEN 0 AND 1),
    horizon         VARCHAR(10) DEFAULT 'long'
                    CHECK (horizon IN ('mid','long','secular')),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('emerging','active','mature','declining','archived')),

    -- 검증 구조
    bull_case       TEXT,
    bear_case       TEXT,
    kill_condition  TEXT,

    -- PSF 연결 (어떤 PSF 속성에 영향을 주는가)
    psf_impact      TEXT[],

    -- 자산 함의
    asset_beneficiaries TEXT,
    asset_victims       TEXT,

    -- 시간
    created         DATE NOT NULL DEFAULT CURRENT_DATE,
    next_review     DATE,
    last_verified   DATE,
    lesson          TEXT,

    -- 메타
    tags            TEXT[]
);
CREATE INDEX IF NOT EXISTS idx_mt_status ON ont_megatrend(status);


-- ============================================================
-- 2. mt_indicators — MT 추적 지표 (PSF보다 느린 구조적 지표)
-- ============================================================
CREATE TABLE IF NOT EXISTS mt_indicators (
    id              SERIAL PRIMARY KEY,
    mt_id           VARCHAR(10) NOT NULL REFERENCES ont_megatrend(mt_id),
    name            VARCHAR(200) NOT NULL,
    current_value   TEXT,
    threshold       TEXT,
    direction       VARCHAR(20),
    data_source     VARCHAR(100),
    last_check      DATE,
    next_check      DATE,
    verdict         VARCHAR(30)
);
CREATE INDEX IF NOT EXISTS idx_mti_mt ON mt_indicators(mt_id);


-- ============================================================
-- 3. tc_mt_links — TC ↔ MT 연결
-- ============================================================
CREATE TABLE IF NOT EXISTS tc_mt_links (
    tc_id           VARCHAR(10) REFERENCES tc_cards(tc_id),
    mt_id           VARCHAR(10) REFERENCES ont_megatrend(mt_id),
    role            VARCHAR(30) NOT NULL
                    CHECK (role IN ('evidence','counter_evidence','catalyst','outcome')),
    note            TEXT,
    PRIMARY KEY (tc_id, mt_id)
);


-- ============================================================
-- 4. mt_status_log — MT 상태 이력 (분기별 검증)
-- ============================================================
CREATE TABLE IF NOT EXISTS mt_status_log (
    id              SERIAL PRIMARY KEY,
    mt_id           VARCHAR(10) NOT NULL REFERENCES ont_megatrend(mt_id),
    log_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    prev_direction  VARCHAR(30),
    new_direction   VARCHAR(30),
    prev_confidence NUMERIC(4,3),
    new_confidence  NUMERIC(4,3),
    evidence        TEXT,
    source          TEXT
);
CREATE INDEX IF NOT EXISTS idx_mtsl_mt ON mt_status_log(mt_id);


-- ============================================================
-- 5. th_mt_links — TH ↔ MT 연결 (전이가 어떤 메가트렌드와 정렬되는가)
-- ============================================================
CREATE TABLE IF NOT EXISTS th_mt_links (
    th_id           VARCHAR(10) REFERENCES th_cards(th_id),
    mt_id           VARCHAR(10) REFERENCES ont_megatrend(mt_id),
    alignment       VARCHAR(20) NOT NULL
                    CHECK (alignment IN ('aligned','counter','partial')),
    note            TEXT,
    PRIMARY KEY (th_id, mt_id)
);


-- ============================================================
-- 6. 시드 데이터 — 7개 메가트렌드
-- ============================================================
INSERT INTO ont_megatrend (mt_id, name, hypothesis, direction, confidence, horizon, status,
    bull_case, bear_case, kill_condition, psf_impact,
    asset_beneficiaries, asset_victims, next_review, tags)
VALUES
(
    'MT-01',
    'AI 인프라 사이클',
    '$700B capex가 수익으로 전환되는가. manufacturer(NVDA)→monetizer(MSFT/GOOGL) 가치 이전이 핵심. 전환 실패 시 capex 버블.',
    'inflecting',
    0.55,
    'long',
    'active',
    'AI 서비스 매출 YoY +50%. monetizer PER 확장. capex→수익 선순환 확인.',
    'ROI 4% 지속. HBM 수요 재설정(TurboQuant). 헬륨 병목으로 팹 차질.',
    'Big Tech capex YoY 감소 + AI 서비스 매출 역성장',
    '{S1,F5}',
    'monetizer(MSFT/GOOGL/META), 전력인프라, 쿨링, 데이터센터 리츠',
    'manufacturer(NVDA/AMD) — capex 피킹 시 멀티플 압축, HBM 과잉 시 메모리',
    '2026-06-30',
    '{AI,capex,반도체,헬륨,TurboQuant}'
),
(
    'MT-02',
    '에너지 질서 재편',
    '화석연료 지정학이 구조화. 호르무즈 톨부스, 이란 제재, OPEC+ 감산이 유가 바닥을 높인다. 에너지 안보 = 국가 안보.',
    'accelerating',
    0.65,
    'long',
    'active',
    '이란 톨부스 구조화. Brent $100+ 장기 지속. 에너지 안보 투자 확대.',
    '이란 정전 + 호르무즈 정상화. OPEC+ 증산. 셰일 생산 확대.',
    '이란 휴전 + Brent $70 이하 6개월 지속',
    '{P3,S1,F1}',
    '에너지 메이저(XOM/CVX), 방산, LNG 인프라, 원자력',
    '에너지 다소비 산업, 항공, 석유화학 하류',
    '2026-06-30',
    '{에너지,이란,호르무즈,OPEC,LNG}'
),
(
    'MT-03',
    '통화 질서 변화',
    '달러 패권이 점진적으로 약화. BRICS 결제, 디지털 위안, 금 비축 증가. 단, 대안 부재로 속도는 느림.',
    'emerging',
    0.35,
    'secular',
    'emerging',
    '금 중앙은행 매입 3년 연속 1000t+. CIPS 거래량 YoY +30%. mBridge 상용화.',
    '달러 결제 비중 40%+ 유지. 유로/위안 대안 신뢰 부족.',
    '달러 결제 비중 반등 + BRICS 결제 시스템 좌초',
    '{F1,F3,P2}',
    '금, 비달러 자산, 신흥국 로컬 채권',
    '달러 표시 자산 과대 비중 포트폴리오',
    '2026-09-30',
    '{달러,BRICS,금,CIPS,위안}'
),
(
    'MT-04',
    '인구 구조 전환',
    '선진국 고령화 + 중국 인구 감소가 노동시장, 인플레, 자산 배분을 구조적으로 바꾼다.',
    'accelerating',
    0.70,
    'secular',
    'mature',
    '일본형 장기 저성장 확산. 의료/시니어 시장 폭발. 이민 정책 완화.',
    '로봇/AI가 노동력 대체. 생산성 반등.',
    'AI 생산성 혁명이 인구 감소 효과를 상쇄',
    '{P1,S4}',
    '헬스케어, 시니어케어, 로봇/자동화, 연금/보험',
    '부동산(인구 감소 지역), 소비재(내수 축소)',
    '2026-12-31',
    '{고령화,인구,노동,이민,로봇}'
),
(
    'MT-05',
    '디커플링/리쇼어링',
    '미중 기술 분리 + 공급망 안보가 제조업 지도를 재편. friend-shoring, 보조금 경쟁, 반도체 자급.',
    'accelerating',
    0.60,
    'long',
    'active',
    'CHIPS Act 투자 집행. TSMC 미국 팹. 한국/일본 반도체 투자 확대.',
    '비용 압력으로 리쇼어링 지연. 기업 이익 악화로 투자 축소.',
    '미중 기술 협력 재개 + 관세 전면 철폐',
    '{P2,S4,F3}',
    '반도체 장비, 산업 자동화, 멕시코/인도/베트남 제조업',
    '중국 수출 의존 기업, 글로벌 공급망 최적화 기업',
    '2026-09-30',
    '{디커플링,리쇼어링,CHIPS,반도체,공급망}'
),
(
    'MT-06',
    '유럽 방산/안보 전환',
    '러시아 위협 + NATO 재편이 유럽 방산 지출을 구조적으로 확대. 자동차→방산 산업 전환.',
    'accelerating',
    0.60,
    'long',
    'active',
    'VW-라파엘 계약. 독일 방산 GDP 3%+. NATO 유럽 필러 확대.',
    '러시아 휴전. 방산 과열 조정. IG Metall 반대.',
    '러-우 평화 협정 + EU 방산 예산 삭감',
    '{P3,P4}',
    '유럽 방산(Rheinmetall, BAE), K-방산(한화/LIG), 방산 ETF',
    '유럽 자동차(순수 ICE), 평화 배당금 수혜 섹터',
    '2026-06-30',
    '{방산,NATO,유럽,VW,K-방산}'
),
(
    'MT-07',
    '통상 질서 재편',
    '자유무역 후퇴. 301/IEEPA/EU ACI가 새로운 관세 질서. 한국은 수출 모델→현지 생산 전환 압박.',
    'accelerating',
    0.65,
    'long',
    'active',
    'Section 301 한국 관세 확정. EU IAA 발효. 다자 FTA 약화.',
    '한미 합의 면제. WTO 개혁. 관세 전쟁 피로감.',
    '미국 관세 전면 철회 + 다자 무역 체제 복원',
    '{P2,S4,F1,F3}',
    '현지 생산 완료 기업(현대차 미국), 수입대체, 내수주',
    '수출 의존 중소형주, 관세 직격 섹터(자동차/반도체/철강)',
    '2026-06-30',
    '{관세,301,IEEPA,ACI,IAA,FTA,통상}'
);


-- ============================================================
-- 7. TC ↔ MT 시드 연결
-- ============================================================
INSERT INTO tc_mt_links (tc_id, mt_id, role, note) VALUES
    ('TC-010', 'MT-01', 'evidence', 'AI capex $700B + 양극화 + 헬륨 병목'),
    ('TC-003', 'MT-02', 'evidence', '이란 전쟁 + 호르무즈 톨부스 + Brent $112'),
    ('TC-001', 'MT-07', 'evidence', 'Section 301 관세 법체계 3단 진화'),
    ('TC-008', 'MT-07', 'evidence', '한국車 삼중 포위 — 관세+IAA+BYD'),
    ('TC-009', 'MT-07', 'evidence', 'EU 제3극 통상자율성 — ACI+IAA'),
    ('TC-005', 'MT-06', 'evidence', 'VW 방산 전환 — 유럽 자동차→방산'),
    ('TC-002', 'MT-03', 'catalyst', 'KRW 구조적 약세 — 달러 패권 하 신흥국 통화 압력'),
    ('TC-006', 'MT-05', 'evidence', 'SK하이닉스 ADR — 반도체 자급/밸류 재편'),
    ('TC-007', 'MT-02', 'outcome', '이란→유가→인플레→장기채 — 에너지 질서가 금리를 결정'),
    ('TC-004', 'MT-04', 'catalyst', 'ISA 807만 — 개인투자 구조 전환 (인구 고령화 대비 자산 축적)')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 8. TH ↔ MT 연결
-- ============================================================
INSERT INTO th_mt_links (th_id, mt_id, alignment, note) VALUES
    ('TH-001', 'MT-07', 'aligned', '통상 재편이 risk-off 전이의 핵심 동인'),
    ('TH-001', 'MT-02', 'aligned', '에너지 질서 재편이 인플레→금리 경로를 열어 risk-off 가속')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 9. v_mt_dashboard — 메가트렌드 대시보드
-- ============================================================
DROP VIEW IF EXISTS v_mt_dashboard CASCADE;
CREATE VIEW v_mt_dashboard AS
SELECT
    mt.mt_id,
    mt.name,
    mt.direction,
    mt.confidence,
    mt.horizon,
    mt.status,
    mt.asset_beneficiaries,
    mt.asset_victims,
    -- TC 관여 수
    (SELECT count(*) FROM tc_mt_links WHERE mt_id = mt.mt_id) AS tc_count,
    -- TC 목록
    (SELECT array_agg(tc_id ORDER BY tc_id) FROM tc_mt_links WHERE mt_id = mt.mt_id) AS linked_tcs,
    -- TH 정렬 수
    (SELECT count(*) FROM th_mt_links WHERE mt_id = mt.mt_id) AS th_aligned,
    -- PSF 연결 속성
    mt.psf_impact,
    -- 다음 검증
    mt.next_review,
    mt.next_review - CURRENT_DATE AS days_to_review
FROM ont_megatrend mt
WHERE mt.status != 'archived'
ORDER BY mt.confidence DESC;


-- ============================================================
-- 10. v_mt_psf_cross — MT ↔ PSF 교차 분석
-- ============================================================
DROP VIEW IF EXISTS v_mt_psf_cross CASCADE;
CREATE VIEW v_mt_psf_cross AS
SELECT
    mt.mt_id,
    mt.name AS mt_name,
    mt.direction AS mt_direction,
    mt.confidence AS mt_confidence,
    unnest(mt.psf_impact) AS psf_property_id,
    psf.property_verdict,
    psf.direction AS psf_direction,
    psf.current_value AS psf_value,
    -- 정렬 여부: MT가 악화 방향이고 PSF도 악화면 aligned
    CASE
        WHEN mt.direction IN ('accelerating','emerging') AND psf.direction IN ('worsening','tightening','risk_off')
            THEN 'MT↔PSF aligned (risk-off)'
        WHEN mt.direction IN ('decelerating','reversing') AND psf.direction IN ('improving','easing','risk_on')
            THEN 'MT↔PSF aligned (risk-on)'
        WHEN psf.direction IS NULL THEN 'PSF no data'
        ELSE 'MT↔PSF divergent'
    END AS alignment
FROM ont_megatrend mt
LEFT JOIN v_psf_dashboard psf ON psf.property_id = unnest(mt.psf_impact)
WHERE mt.status != 'archived';


-- ============================================================
-- 11. v_asset_map — MT 방향 → 자산 함의 종합
-- ============================================================
DROP VIEW IF EXISTS v_asset_map CASCADE;
CREATE VIEW v_asset_map AS
SELECT
    mt.mt_id,
    mt.name,
    mt.direction,
    mt.confidence,
    mt.asset_beneficiaries,
    mt.asset_victims,
    -- PSF 흐름 층 상태 (선점 타이밍 판단)
    (SELECT property_verdict FROM v_psf_dashboard WHERE property_id = 'F2') AS flow_verdict,
    (SELECT direction FROM v_psf_dashboard WHERE property_id = 'F2') AS flow_direction,
    -- TH 전이 방향과 정렬 여부
    (SELECT string_agg(tml.alignment, ', ')
     FROM th_mt_links tml
     JOIN th_cards th ON tml.th_id = th.th_id
     WHERE tml.mt_id = mt.mt_id AND th.status = 'active'
    ) AS th_alignment
FROM ont_megatrend mt
WHERE mt.status != 'archived'
ORDER BY mt.confidence DESC;
