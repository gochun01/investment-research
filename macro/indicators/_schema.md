# indicators/ 스키마 정의

## 목적
46개 지표(핵심 27 + 보조 19)의 주간 스냅샷을 저장.
`SKILL-macro-indicators.md`(정적 문서)를 대체하지 않고, **데이터 이력**을 누적한다.

## 파일 규칙

```
파일명: YYYY-MM-DD.yaml
주기: 매주 월요일 /macro-weekly 실행 시 자동 생성
보존: 최소 52주 (1년)
```

## YAML 구조

```yaml
# 헤더
date: "2026-03-10"           # 스냅샷 날짜
data_as_of: "2026-03-07"     # 실제 데이터 기준일 (시장 마감 기준)
prev_date: "2026-03-03"      # 전주 스냅샷 날짜 ★ 개선: "전주 대비" 기준 명시
prev_basis: "전주 /macro-weekly 실행 기준"
regime: "TRANSITION"          # EXPANSION / TRANSITION / CONTRACTION / OVERHEATING / CRISIS
regime_change: false          # 전주 대비 레짐 변경 여부
l7: 0.18                     # L7 점수
l8: 0.02                     # L8 점수
risk_gate: "GREEN"            # GREEN / YELLOW / RED

# Layer A — 근본
layer_a:
  A1_core_pce:
    value: 2.4
    unit: "%"
    direction: "down"         # up / down / flat
    status: "partial"         # met / partial / unmet
    source: "FRED:PCEPILFE"
    confidence: "green"       # green / yellow / red / black
    note: ""
  A2_china_credit:
    value: "easing"           # 정량값 없을 시 정성 상태
    direction: "up"
    status: "met"
    source: "web:PBOC"
    confidence: "yellow"
    note: ""

# Layer B — 전달
layer_b:
  B1_real_rate:
    value: 1.80
    unit: "%"
    prev: 1.82               # 전주값 (delta 계산용)
    direction: "flat"
    risk_asset: false         # 위험자산 방향 여부
    source: "FRED:DFII10"
    confidence: "green"
  B2_dxy:
    value: 97.5
    prev: 98.2
    direction: "down"
    risk_asset: true
    source: "Yahoo:DX-Y.NYB"
    confidence: "green"
  B3_usdjpy:
    value: 150.0
    prev: 149.8
    direction: "flat"
    risk_asset: true          # 안정 = 위험자산 방향
    source: "Yahoo:JPY=X"
    confidence: "green"
  B4_net_liquidity:
    value: 5.71
    unit: "T USD"
    prev: 5.74
    direction: "down"
    risk_asset: false
    source: "FRED:WALCL-TGA-RRP"
    confidence: "green"
  B5_hy_oas:
    value: 340
    unit: "bp"
    prev: 338
    direction: "flat"
    risk_asset: false         # 축소 추세가 아니면 false
    source: "FRED:BAMLH0A0HYM2"
    confidence: "green"

# Layer C — 확인 (불일치 시에만 note 기록)
layer_c:
  C1_vix: { value: 19.2, cross: "B5", match: true }
  C2_move: { value: 100, cross: "B5", match: true }
  C3_t10y2y: { value: 0.22, unit: "%", cross: "B1", match: true }
  C4_global_m2: { value: 4.2, unit: "% YoY", cross: "B4", match: false, note: "M2↑ vs NL↓ 괴리" }
  C5_ism_pmi: { value: 52.6, cross: "A1", match: true }
  C6_unemployment: { value: 4.0, unit: "%", cross: "A1", match: true }
  C7_brent: { value: 72, unit: "USD", cross: "A1", match: true }
  C8_bei: { value: 2.3, unit: "%", cross: "B1", match: true }
  C9_usdcny: { value: 7.25, cross: "A2", match: true }
  C10_dff: { value: 3.625, unit: "%", cross: "B1", match: true }

# Layer D — 배경 (변동분만 note)
layer_d:
  D1_sloos: { value: "Moderate", changed: false }
  D2_reserves: { value: 3.28, unit: "T USD", changed: false }
  D3_rrp: { value: 0.098, unit: "T USD", changed: false }
  D4_tga: { value: 0.722, unit: "T USD", changed: false }
  D5_walcl: { value: 6.62, unit: "T USD", changed: false }
  D6_sofr: { value: 4.30, unit: "%", changed: false }
  D7_deficit_gdp: { value: 6.0, unit: "%+", changed: false }
  D8_term_premium: { value: 0.50, unit: "%", changed: false }
  D9_cftc_jpy: { value: "short_reducing", changed: false }
  D10_fedwatch: { value: "-50bp expected", changed: false }

# Layer AUX — 보조 프록시 (PSF 매핑용, 19개)
# PSF에서 이관. Macro가 유일한 수집자.
layer_aux:
  # FRED (8개)
  X1_dgs10: { value: null, unit: "%", source: "FRED:DGS10", psf: "P1 보조" }
  X2_dfii5: { value: null, unit: "%", source: "FRED:DFII5", psf: "S1 보조" }
  X3_ig_oas: { value: null, unit: "bp", source: "FRED:BAMLC0A0CM", psf: "S2 보조" }
  X4_manemp: { value: null, unit: "K", source: "FRED:MANEMP", psf: "S4 보조" }
  X5_indpro: { value: null, unit: "index", source: "FRED:INDPRO", psf: "S4 보조" }
  X6_rsafs: { value: null, unit: "M USD", source: "FRED:RSAFS", psf: "S4 보조" }
  X7_t10y3m: { value: null, unit: "%", source: "FRED:T10Y3M", psf: "S5 보조" }
  X8_civpart: { value: null, unit: "%", source: "FRED:CIVPART", psf: "P4 보조" }
  # Yahoo (10개)
  X9_wti: { value: null, unit: "USD", source: "Yahoo:CL=F", psf: "P5 보조" }
  X10_natgas: { value: null, unit: "USD", source: "Yahoo:NG=F", psf: "P5 보조" }
  X11_hyg: { value: null, unit: "USD", source: "Yahoo:HYG", psf: "S2 보조, L7" }
  X12_lqd: { value: null, unit: "USD", source: "Yahoo:LQD", psf: "S2 보조, L8" }
  X13_gold: { value: null, unit: "USD", source: "Yahoo:GC=F", psf: "F1 보조, P2" }
  X14_tlt: { value: null, unit: "USD", source: "Yahoo:TLT", psf: "F1 보조, CorrFlip" }
  X15_eem: { value: null, unit: "USD", source: "Yahoo:EEM", psf: "F3" }
  X16_spy: { value: null, unit: "USD", source: "Yahoo:SPY", psf: "F3, CorrFlip" }
  X17_soxx: { value: null, unit: "USD", source: "Yahoo:SOXX", psf: "P3 보조" }
  X18_btc: { value: null, unit: "USD", source: "Yahoo:BTC-USD", psf: "F4 보조" }
  # CoinGecko (1개)
  X19_stablecoin: { value: null, unit: "B USD", source: "CoinGecko:global", psf: "F4" }

  # Link 트리거 시계열 (현재값 외 기간 데이터)
  timeseries:
    vix_3d: { source: "Yahoo:^VIX", period: "3d", psf: "L7 급성" }
    vix_5d: { source: "Yahoo:^VIX", period: "5d", psf: "L7 만성" }
    brent_30d: { source: "Yahoo:BZ=F", period: "30d", psf: "L3.5" }
    spy_1d: { source: "Yahoo:SPY", period: "1d", psf: "CorrFlip" }
    tlt_1d: { source: "Yahoo:TLT", period: "1d", psf: "CorrFlip" }

# 이벤트 서사
events:
  - name: ""
    date: ""
    path: ""                  # fed / china / yen_carry / oil / fiscal
    impact: ""

# 경로 상태
causal_chain:
  dominant: "fed"             # 지배 경로
  disruptions: []             # 활성 교란 경로 목록
  conflicts: []               # 경로 간 상충
  keystone: "core_pce"        # 키스톤 상태
  narrative: "good_is_good"   # good_is_good / good_is_bad
```

## 활용

```
1. /macro-weekly 실행 시:
   → MCP 수집 완료 후 해당 주 YAML 자동 생성
   → 전주 YAML과 diff → 변화 자동 식별

2. 이력 조회:
   → indicators/ 폴더의 YAML 시계열로 추세 확인
   → 특정 지표의 n주 변화 추적

3. 비정기 트리거 시:
   → 최신 YAML을 기준으로 변동분만 갱신
   → 파일명: YYYY-MM-DD_trigger_[이벤트].yaml
```

## 전주 대비 변화 감지 기준

```
Layer B 유의미 변화:
  B1 실질금리: ±20bp
  B2 DXY: ±2%
  B3 USD/JPY: ±3%
  B4 Net Liquidity: ±2%
  B5 HY OAS: ±50bp

Layer C 불일치 기준:
  해당 Layer B 지표와 방향 불일치 시 match: false
  불일치 3개+ → 교란 경로 의심
```
