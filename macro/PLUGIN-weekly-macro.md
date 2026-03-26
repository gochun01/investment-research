# 주간 매크로 점검 — 플러그인

## 명령어: /macro-weekly

## 역할
매주 월요일 실행. discovery-protocol.md의 개방형 프로토콜에 따라 실행한다.
아래 Step 1~10은 참고 순서. 실제 실행은 discovery-protocol.md가 우선.
Step 1(L7/L8)만 고정. 나머지는 변화가 큰 것부터.

---

## 실행 순서

### Step 1: L7/L8 최우선 확인

```
→ FRED: BAMLH0A0HYM2 (HY OAS)
→ Yahoo: ^VIX, ^MOVE
→ FRED: SOFR
→ L7 공식 적용:
  L7 = 0.30×((HY−250)/(800−250)) + 0.25×((VIX−12)/(45−12))
     + 0.20×((SOFR갭)/50bp) + 0.15×((MOVE−80)/(200−80)) + 0.10×TED
→ L8 공식 적용 (데이터 가용 시)
→ 판정: 🟢(<0.60) / 🟡(L7≥0.60) / 🔴(L7+L8≥0.60)
→ 🔴이면 여기서 중단. 위기 보고서 발행. 이하 단계 생략.
```

### Step 2: Layer A 수집 (근본 2개)

```
→ FRED: PCEPILFE (Core PCE) — 최신 발표값 + YoY
→ 웹검색: "중국 신규 위안화 대출 최신" 또는 "PBOC credit impulse"
→ 키스톤 상태 판정:
  A1 < 2.2% → Fed 인하 임박 (키스톤 해소 접근)
  A1 2.2~2.5% → Fed Pause (현재)
  A1 > 2.5% → Fed 인하 차단 (역방향)
  실업률 5%+ → 키스톤 전환 (고용 바인딩)
```

### Step 3: Layer B 수집 (전달 5개)

```
→ FRED: DFII10 (B1 실질금리)
→ Yahoo: DX-Y.NYB (B2 DXY)
→ Yahoo: JPY=X (B3 USD/JPY)
→ FRED: WALCL (B4 계산용)
→ 웹검색: TGA 최신값 (Treasury Daily Statement)
→ B4 Net Liquidity 계산: WALCL − TGA − RRP(D3에서)
→ FRED: BAMLH0A0HYM2 (B5, Step 1에서 수집 완료)

→ 각 지표: 현재값 + 전주 대비 변화 + 방향(↑↓→)
→ "위험자산 방향" 판정:
  B1 하락 추세 = ✓   B2 하락 추세 = ✓   B3 안정 = ✓
  B4 상승 추세 = ✓   B5 축소 추세 = ✓
→ 5개 중 위험자산 방향 수 → 레짐 초안
```

### Step 4: 이벤트 식별 + 인과 체인

```
→ Layer B 5개 중 전주 대비 유의미 변화 식별
  기준: B1 ±20bp, B2 ±2%, B3 ±3%, B4 ±2%, B5 ±50bp

→ 변화 있으면:
  웹검색: "글로벌 금융시장 이번 주 핵심 이벤트"
  웹검색: "[변화 지표] 원인 [날짜]"

→ 이벤트 → 지표 인과 경로 매핑:
  어떤 경로가 활성화됐는가?
  ├── 정상 1 (Fed): A1→B1→B4→B2→B5
  ├── 정상 2 (중국): A2→C4→B2
  ├── 교란 1 (엔캐리): B3 급변 → Override
  ├── 교란 2 (유가): C7→C8→A1 역전
  └── 교란 3 (재정): D7→D8→B1 상충

→ 3~5문장 서사 작성

→ 변화 없으면:
  "주요 이벤트 없음. [지배 경로] 유지. [가장 큰 점진 변화] 중."
```

### Step 5: Layer C 교차 검증 (10개)

```
→ FRED: T10Y2Y, WM2NS, UNRATE, T10YIE, DFF
→ Yahoo: ^VIX(Step 1), ^MOVE(Step 1), CL=F, CNY=X
→ 웹검색: ISM PMI (월간 발표 시에만)

→ Layer B와 방향 교차:
  일치 → "[C지표] B[X] 확인" 한 줄
  불일치 → ⚠️ 플래그 + 상세 분석
  불일치 3개+ → 교란 경로 의심 → Step 4 재검토
```

### Step 6: Layer D 배경 체크 (10개)

```
→ FRED: WRESBAL, RRPONTSYD, WALCL, SOFR (Step 1/3에서 일부 수집)
→ 웹검색: CFTC JPY, FedWatch (해당 주에 변동 있으면)

→ 대부분 "전주 유지"
→ 변동 있는 것만 상세:
  D1 SLOOS: 분기 발표 시에만
  D8 텀 프리미엄: 월간 변동 시
  D10 FedWatch: FOMC 전후
```

### Step 6.5: Layer AUX 보조 프록시 수집 (23개, PSF 매핑용)

```
→ PSF에서 이관된 보조 프록시. Macro가 유일한 수집자.
→ PSF가 이 데이터를 읽어서 15 Property로 매핑한다.

FRED 일괄 (8개):
  DGS10, DFII5, BAMLC0A0CM, MANEMP, INDPRO, RSAFS, T10Y3M, CIVPART

Yahoo 일괄 (10개):
  CL=F, NG=F, HYG, LQD, GC=F, TLT, EEM, SPY, SOXX, BTC-USD

CoinGecko (1개):
  get_global_market_data → stablecoin_market_cap 추출

DeFiLlama (맥락 기반 — 크립토 신호 감지 시):
  get_global_tvl → DeFi TVL 총액 + 7일 변화
  get_stablecoins → 스테이블코인 상세 (USDT, USDC, USD1, BUIDL 등)

blockchain-com (맥락 기반 — BTC 네트워크 점검 시):
  blockchain_macro_context → 해시레이트, 활성 주소, 수수료

Link 트리거 시계열:
  Yahoo get_historical_stock_prices: ^VIX (5일), BZ=F (30일)
  Yahoo get_current_stock_price: SPY, TLT (CorrFlip 당일)

→ indicators/latest.json의 layer_aux 섹션에 기록
→ 실패 시: ⚠️ 플래그 + null 유지. PSF에 "[미수집]" 태깅.
```

### Step 7: 레짐 판정

```
→ L7/L8 상태 (Step 1)
→ Layer B 위험자산 방향 수 (Step 3)
→ 인과 체인 + 경로 상태 (Step 4)
→ Layer C 불일치 수 (Step 5)

→ 레짐 판정:
  4+ 위험자산 → 🟢 팽창기
  2~3 → 🟡 Transition
  4+ 안전자산 → 🔴 수축기
  팽창 + VIX<12 → 🟡 과열기

→ 전주 대비 변경 여부 + 변경 사유
→ 내러티브 상태: 최근 경제 데이터 발표 후 주가 반응으로 판별
```

### Step 8: 검증

```
→ Layer 1: MCP 수집값 vs 입력값 일치 확인
→ Layer 2: 레짐 판정 ↔ 인과 체인 일관성
→ B↔C 불일치 개수 기록
→ 검증 상태: ✅ / ⚠️
```

### Step 9: 보고서 생성 + PSF용 JSON 갱신

```
→ TEMPLATE-macro-report.md 형식에 따라 MD 파일 생성
→ 파일명: [YYYY-MM-DD]_macro-weekly.md
→ 저장: macro/reports/
→ 첫 줄: 핵심 결론 1문장 (이벤트 서사 포함)

→ ★ PSF용 JSON 갱신 (보고서와 동시):
  indicators/latest.json을 최신 데이터로 덮어쓴다.
  구조: date, regime, A1~D10 (각각 name/value/unit/prev/change/direction/status/source/note)
  PSF가 이 파일을 읽어서 3층(판-구조-흐름)으로 매핑한다.
  → 별도 주기 없음. macro가 실행될 때마다 자동 갱신.
  → 정기(/macro-weekly), 비정기(CPI, FOMC, 이벤트) 모두 포함.
```

### Step 10: Notion 아카이브

```
→ Notion DB ee345e95에 저장
  분석 날짜: 오늘
  다음 업데이트: 1주 후
  핵심 결론: Step 9의 첫 줄
  레짐: Step 7 판정
  데이터 기준일: 명시
```

---

## MCP 호출 최적화

```
1차 (fred 일괄, 21개 = 핵심 13 + 보조 8):
  핵심: PCEPILFE, DFII10, BAMLH0A0HYM2, T10Y2Y, WM2NS,
        UNRATE, T10YIE, DFF, WALCL, RRPONTSYD, WRESBAL, SOFR
  보조: DGS10, DFII5, BAMLC0A0CM, MANEMP, INDPRO, RSAFS, T10Y3M, CIVPART

2차 (yahoo-finance 일괄, 16개 = 핵심 6 + 보조 10):
  핵심: DX-Y.NYB, JPY=X, ^VIX, ^MOVE, CL=F, CNY=X
  보조: NG=F, HYG, LQD, GC=F, TLT, EEM, SPY, SOXX, BTC-USD, BZ=F(30일 시계열)

3차 (firecrawl 크롤링, 3개):
  D4 TGA: https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/
  D10 FedWatch: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
  D9 CFTC JPY: https://www.cftc.gov/dea/futures/deacmesf.htm

4차 (tavily-mcp 검색, 3개):
  A2 중국 Credit: "China new yuan loans [최근월] PBOC"
  C5 ISM PMI: "ISM manufacturing PMI [최근월] 2026"
  D7 재정적자: "US budget deficit GDP ratio CBO 2026"

5차 (계산):
  Net Liquidity = WALCL − TGA − RRP
  L7/L8 공식 적용

6차 (이벤트 탐색):
  tavily: "global financial market key events this week [날짜]"

7차 (Notion):
  아카이브 저장

firecrawl 실패 시: tavily 폴백
tavily 실패 시: 일반 웹검색 폴백
모든 MCP 실패 시: 보고서에 "⚠️ [지표] 미수집" 표시 + 직전 값 유지
```

---

## 비정기 실행 트리거

```
FOMC 후: Step 2(A1) + Step 3(B1,B4) + Step 7 재판정
CPI/PCE 발표: Step 2(A1) + 키스톤 재판정
USD/JPY 3%+ 급변: Step 1(L7) + Step 3(B3) + 교란 1 점검
VIX 30+ 돌파: Step 1 즉시 → L7/L8 긴급 판정
Brent 15%+ 급등: Step 5(C7,C8) + 교란 2 점검
```

---

## 이상 탐지 (자동 플래그)

```
Layer B 3개+ 동시 방향 전환 → 레짐 전환 경고
Layer B↔C 불일치 3개+ → 교란 경로 활성 경고
L7 Score 0.40 접근 → 경계 모드 전환
VIX 30+ → Override 경고
USD/JPY 주간 3%+ → 엔캐리 경보
```

---

## 실패 패턴과 방어 (Step 6: FAIL)

/macro-weekly 실행 중 반복되는 실패 패턴. 보고서 제출 전 전수 확인.

| ID | 실패 패턴 | 결과 | 방어 |
|----|----------|------|------|
| F-01 | L7/L8 확인 누락 | 위기 게이트 미작동. 🔴 상태에서 정규 보고서 발행. | Step 1을 반드시 최초 실행. 🔴이면 즉시 중단. |
| F-02 | 키스톤 판정 누락 | A1 Core PCE 상태 불명. Fed 경로 판정 불가. | Step 2에서 A1 수집 직후 키스톤 상태(해소/미해소/역방향/전환) 판정. |
| F-03 | B1~B5 방향 불일치 방치 | 위험자산 방향 수 오산. 레짐 오판정. | RULES.md §1 기준으로 각 지표 ✓/✗/△ 판정 + 근거 서술. 5개 전수. |
| F-04 | 인과 체인에 은유 사용 | "경로가 포위됨", "물이 막힘" 같은 서술이 분석을 대체. | CLAUDE.md §인과추적범위 기준. 은유 제거 후 의미 전달 테스트. |
| F-05 | prev_date 미명시 | "전주 대비" 비교의 기준 불명. 재현 불가. | 모든 "전주 대비" 서술에 "prev X.XX (MM/DD)" 형식 병기. |
| F-06 | 보조 지표 전수 미확인 | Layer AUX 23개 미수집. PSF 매핑 불완전. Link 트리거 누락. | Step 6.5 전수 실행. 실패 시 ⚠️ + null + "[미수집]" 태깅. |
| F-07 | 신뢰도 태깅 누락 | MCP 수집(🟢) vs 웹검색(🟡) vs 미확인(🔴) vs 미수집(⚫) 구분 불가. | 모든 수치에 출처 + 🟢🟡🔴⚫ 태깅 필수. |
| F-08 | latest.json date 미갱신 | PSF가 stale 판정. 중복 수집 또는 데이터 누락. | Step 9에서 latest.json 갱신 시 date를 오늘 날짜로 반드시 변경. |

---

## 진화 규칙 (Step 7: EVOLVE)

### Self-Audit (매 실행 후 자기 점검)

| # | 질문 | 기준 |
|---|------|------|
| Q1 | 27개 핵심 지표 전수 수집했는가? | A1~A2, B1~B5, C1~C10, D1~D10 모두 값 또는 ⚫ 태깅. |
| Q2 | B1~B5 위험자산 방향 판정이 수치와 일치하는가? | RULES.md §1 기준. ✓/✗/△ 각각 수치 근거 서술 존재. |
| Q3 | 인과 체인에서 "은유/의인화를 제거해도 의미 전달되는가?" | 은유 0개 = PASS. 1개+ = 재서술 후 PASS. |
| Q4 | 레짐 판정이 전주와 같을 때, 근거를 재검증했는가? (관성 방어) | "유지 근거" 서술 존재. "변화 없음"만으로는 FAIL. |
| Q5 | 양측 최강 논거를 제시한 후 판정했는가? | 팽창 논거 + 수축 논거 모두 기술. 한 방향만이면 FAIL. |

### Invariant Rules (불변 규칙, 6개)

```
IR-01: L7/L8은 항상 Step 1. 예외 없음.
IR-02: 레짐 판정은 RULES.md §6 의사결정 트리를 따른다. 직관 판정 금지.
IR-03: 인과 체인은 데이터로 뒷받침되는 경로만 기술한다. 해석/예측 금지.
IR-04: prev_date 없는 "전주 대비"는 금지. 기준 불명 = 비교 무효.
IR-05: latest.json은 모든 실행(정기/비정기) 후 반드시 갱신한다.
IR-06: PSF state.json을 macro가 직접 수정하지 않는다.
```

### 7-Step Protocol Score

매 실행 후 각 Step 이행 여부를 채점한다.

| Step | 항목 | 점수 |
|------|------|------|
| 1 | L7/L8 최우선 확인 | /1 |
| 2 | Layer A 수집 + 키스톤 판정 | /1 |
| 3 | Layer B 전수 판정 (5개 ✓/✗/△) | /1 |
| 4 | 이벤트 인과 체인 (데이터 근거) | /1 |
| 5 | Layer C 교차 검증 (불일치 기록) | /1 |
| 6 | FAIL 패턴 전수 확인 (F-01~F-08) | /1 |
| 7 | Self-Audit Q1~Q5 통과 | /1 |
| **합계** | | **/7** |

```
7/7: 완전 이행
6/7: 경미한 누락 → errors.md에 기록
5/7 이하: 보고서 재검토 필요
4/7 이하: 보고서 재작성
```
