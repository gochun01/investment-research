# PSF 매핑 명세서

> Macro의 46개 지표(핵심 27 + 보조 19)를 PSF 3층(판-구조-흐름)으로 재배치하는 규칙.
> **PSF는 직접 수집하지 않는다.** Macro가 유일한 수집자.
> PSF는 Macro의 `indicators/latest.json`을 읽어서 매핑만 한다.
>
> macro 경로: `C:\Users\이미영\Downloads\에이전트\macro\`
> macro JSON: `indicators/latest.json` ← PSF가 읽는 정본
> macro 지표 시트: `SKILL-macro-indicators.md` ← 사람이 읽는 참조

---

## 매핑 규칙

```
1. macro의 SKILL-macro-indicators.md에서 데이터를 읽는다
2. 각 지표의 value(수치), 방향(↑/→/↓), 상태(✓/✗/△)를 추출한다
3. 아래 매핑 테이블에 따라 PSF Property에 배치한다
4. PSF 판정 기준으로 안정/긴장/균열 등을 판정한다
5. 보조 프록시는 Macro의 layer_aux에서 읽는다. PSF는 MCP를 직접 호출하지 않는다.
```

---

## 판 (Plate) — macro → PSF 매핑

### P-재정 (통화·재정 레짐)

| macro 소스 | PSF 역할 | 매핑 |
|---|---|---|
| **C10 DFF** (3.64%) | 대표 | 현재 금리 수준 |
| **A1 Core PCE** (2.4%) | 키스톤 참조 | Fed 행동의 결정 변수. "인하 가능한가?" |
| **C8 BEI** (T5YIE 2.34%) | 보조 | 인플레 기대 |
| D10 FedWatch | 참조 | 시장의 금리 전망 |

**PSF 판정:**
```
안정: DFF 변동 <25bp/분기 + Core PCE 추세 안정 + BEI 2.0~2.5%
변동: DFF 변동 중 또는 Core PCE 방향 전환 + BEI >2.5%
전환: 긴축→완화 또는 완화→긴축 방향 전환

방향 입력: macro A1 방향(↓ 둔화) + C10 값 + D10 기대
```

### P-지정학 (지정학·패권)

| macro 소스 | PSF 역할 | 매핑 |
|---|---|---|
| **C7 Brent** ($88+) | 보조 프록시 | 지정학 온도를 에너지로 프록시 |
| 뉴스 (Tavily) | 직접 | 분쟁·관세·동맹 정성 판단 |

**Macro AUX에서 읽기:** `GC=F` (금) — 지정학 온도계

### P-기술 (기술·AI)

macro에 직접 매핑 없음. **Macro AUX에서 읽기:** `SOXX` (반도체 ETF) + Tavily

### P-인구 (인구구조)

macro C6 실업률(`UNRATE` 4.4%)을 참조하되, P4는 장기 구조.
**Macro AUX에서 읽기:** `CIVPART` (경제활동참가율)

### P-자원 (에너지·자원·기후)

| macro 소스 | PSF 역할 |
|---|---|
| **C7 Brent** | 대표 |
| **C8 BEI** | 에너지→인플레 전파 확인 |

**Macro AUX에서 읽기:** `CL=F` (WTI), `NG=F` (천연가스)

---

## 구조 (Structure) — macro → PSF 매핑

### S1 실질금리

| macro 소스 | PSF 역할 |
|---|---|
| **B1 DFII10** (+1.80%) | 대표 |
| C8 BEI (T5YIE) | 인플레 기대 교차 |

**Macro AUX에서 읽기:** `DFII5` (5Y TIPS)

**판정:**
```
건전: B1 0~1.5% + 방향 안정/하락
긴장: B1 1.5~2.5% 또는 방향 상승
균열: B1 >2.5% 또는 월간 >100bp

★ 방향 보정: macro의 B1 "방향" 열을 직접 사용.
  ↓ = 한 단계 하향, ↑ = 한 단계 상향.
```

### S2 신용 스프레드

| macro 소스 | PSF 역할 |
|---|---|
| **B5 HY OAS** (319bp) | 대표 |
| C1 VIX | 교차 (불일치 감지) |

**Macro AUX에서 읽기:** `BAMLC0A0CM` (IG OAS), `HYG`, `LQD`

**판정:**
```
건전: B5 <300bp + IG OAS <120bp
긴장: B5 300~500bp 또는 IG 120~200bp
균열: B5 >500bp 또는 LQD 주간 -5%
```

### S3 단기 자금시장

| macro 소스 | PSF 역할 |
|---|---|
| **D6 SOFR** (3.65%) | 대표 |
| C10 DFF (3.64%) | SOFR-FF 갭 계산 |

**판정:**
```
건전: SOFR-FF 갭 <20bp (현재: 3.65-3.64 = +1bp = 건전)
긴장: 갭 20~50bp
균열: 갭 >50bp
```

### S4 실물 경기

| macro 소스 | PSF 역할 |
|---|---|
| **C5 ISM PMI** (52.6) | 대표 |
| C6 실업률 (4.4%) | 교차 |

**Macro AUX에서 읽기:** `MANEMP`, `INDPRO`, `RSAFS` (교차검증)

**판정:**
```
건전: PMI >50 + 실업률 안정
긴장: PMI 45~50 또는 실업률 상승 추세
균열: PMI <45 또는 실업률 >5%
```

### S5 금리 곡선

| macro 소스 | PSF 역할 |
|---|---|
| **C3 T10Y2Y** (+56bp) | 대표 |

**Macro AUX에서 읽기:** `T10Y3M`

**판정:**
```
건전: T10Y2Y >0.5%
긴장: 0~0.5%
균열: <0% (역전)
```

---

## 흐름 (Flow) — macro → PSF 매핑

### F1 달러·안전자산

| macro 소스 | PSF 역할 |
|---|---|
| **B2 DXY** (97.5) | 대표 |

**Macro AUX에서 읽기:** `GC=F` (금), `TLT` (장기국채)

**판정:**
```
정체: DXY 주간 <1% + 금·TLT 안정
이동: DXY 주간 1~3%
이탈: DXY 주간 >3% 또는 DXY+금 동반 급변

교차 패턴:
  DXY↓ + 금↑ = 정상 (인플레 헤지)
  DXY↓ + 금↓ = 비정상 (유동성 위기)
  DXY↑ + 금↑ = 비정상 (극단적 안전자산)
```

### F2 유동성·대기자금

| macro 소스 | PSF 역할 |
|---|---|
| **B4 Net Liquidity** ($5.91T) | 대표 (계산값) |
| D3 RRP — `RRPONTSYD` ($0.3B) | 구성요소 |
| D4 TGA — `WTREGEN` ($722B) | 구성요소 |
| D5 WALCL — `WALCL` ($6.62T) | 구성요소 |

**판정:**
```
정체: Net Liq 방향 안정(→)
이동: Net Liq 방향 전환(↑ 또는 ↓)
이탈: Net Liq 4주 MA 급변 (±5%)
```

### F3 선진국·신흥국

macro에 직접 매핑 없음. **Macro AUX에서 읽기:** `EEM`, `SPY` (비율 계산)

### F4 크립토·디지털

macro에 직접 매핑 없음. **Macro AUX에서 읽기:** CoinGecko `get_global_market_data`, `BTC-USD`

### F5 변동성·심리

| macro 소스 | PSF 역할 |
|---|---|
| **C1 VIX** (~24) | 대표 |
| **C2 MOVE** (~110) | 보조 |

**판정:**
```
안정: VIX <15 + MOVE <80
정상: VIX 15~25 + MOVE 80~100
경계: VIX 25~35 또는 MOVE >100
패닉: VIX >35 + MOVE >120
```

---

## Link 트리거 — macro 데이터 + PSF 보조 프록시

| Link | 조건 | macro 소스 | PSF 보조 |
|---|---|---|---|
| L3.5 공급충격 | Brent 30일 >30% | C7 | `BZ=F` 30일 시계열 |
| L7 급성 | VIX >30 3일 + HYG -1.5% | C1, B5 | `^VIX` 3일, `HYG` 주간 |
| L7 만성 | VIX >25 5일 + HYG -2% | C1, B5 | `^VIX` 5일, `HYG` 주간 |
| L8 위기 | LQD -5% + SOFR-FF >50bp | D6, C10 | `LQD` 주간 |
| CorrFlip | SPY <-1% + TLT <-1% | — | `SPY`, `TLT` 일간 |
| L3 에너지→인플레 | Brent↑ + BEI↑ + DFII10↑ | C7, C8, B1 | — |
| L5 지정학→에너지 | P2 변동 + Brent↑ | C7 + 뉴스 | — |

**Link 점검 시 시계열 필요한 것:**
```
L3.5: Brent 30일 → Macro layer_aux.timeseries.brent_30d에서 읽기
L7 급성: VIX 3일 → Macro layer_aux.timeseries.vix_3d에서 읽기
L7 만성: VIX 5일 → Macro layer_aux.timeseries.vix_5d에서 읽기
CorrFlip: SPY+TLT 당일 → Macro layer_aux.timeseries.spy_1d, tlt_1d에서 읽기

★ Link 트리거 시계열도 Macro가 수집. PSF는 읽기만.
```

---

## 보조 프록시 참조 (Macro에서 수집 — PSF는 읽기만)

> 아래 프록시는 모두 Macro `latest.json` → `layer_aux`에서 읽는다.
> PSF가 직접 수집하지 않는다. 상세: `macro/SKILL-macro-indicators.md` Layer AUX.

| Macro ID | 프록시 | PSF 매핑 | 용도 |
|---|---|---|---|
| X1 | `DGS10` | P-재정 보조 | 장기 금리 수준 |
| X2 | `DFII5` | S1 보조 | 단기 실질금리 |
| X3 | `BAMLC0A0CM` | S2 보조 | IG 스프레드 |
| X4~X6 | `MANEMP`, `INDPRO`, `RSAFS` | S4 보조 | PMI 교차검증 |
| X7 | `T10Y3M` | S5 보조 | 금리 곡선 보조 |
| X8 | `CIVPART` | P-인구 보조 | 경제활동참가율 |
| X9~X10 | `CL=F`, `NG=F` | P-자원 보조 | 에너지 다변화 |
| X11 | `HYG` | S2, L7 트리거 | HY ETF |
| X12 | `LQD` | S2, L8 트리거 | IG ETF |
| X13 | `GC=F` | F1, P-지정학 온도계 | 금 |
| X14 | `TLT` | F1, CorrFlip | 장기국채 ETF |
| X15~X16 | `EEM`, `SPY` | F3, CorrFlip | 선진/신흥 비율 |
| X17 | `SOXX` | P-기술 보조 | 반도체 ETF |
| X18 | `BTC-USD` | F4 보조 | 크립토 프록시 |
| X19 | 스테이블코인 시총 | F4 | 크립토 유입 |

---

## stale 트리거 + 자동 대행

```
Macro indicators를 읽을 때 (SKILL.md Phase 0에서 실행):

1. latest.json의 "date" 필드로 신선도 확인
2. 판정:
   당일~3일 → fresh → 그대로 사용
   3~7일  → ⚠️ stale → 자동 대행 실행
   7일+   → 🔴 expired → 자동 대행 실행

3. 자동 대행 절차:
   → macro 디렉토리(C:\Users\이미영\Downloads\에이전트\macro\)로 이동
   → PLUGIN-weekly-macro.md의 Step 1~10 수집 절차를 macro의 규칙대로 실행
   → 결과를 macro/indicators/latest.json에 저장 (macro의 정본)
   → psf-monitor 디렉토리로 복귀
   → 갱신된 latest.json으로 관측 진행

4. 대행의 원칙:
   ★ PSF 고유의 수집 경로를 만들지 않는다.
     macro의 PLUGIN-weekly-macro.md + RULES.md를 그대로 따른다.
     수집자는 여전히 macro. PSF는 "macro의 손을 빌려 실행"하는 것.

5. 대행 실패 시:
   MCP 접근 실패 등 → stale 데이터 그대로 사용.
   state.json에 "[macro stale]" + "macro_auto_triggered": false 태그.
   보고서에 "[macro 자동갱신 실패 — N일 전 데이터]" 태그.
   사용자에게 "수동 /macro-weekly 실행 권고" 안내.
```

---

## 축 신호 MCP 폴백 경로

```
PSF가 직접 동원하는 MCP(P층 정성 + 축 신호)의 폴백 경로:

┌──────────────┬────────────────┬────────────────┬──────────────┐
│ 데이터        │ 1차 도구        │ 2차 폴백        │ 최종 폴백     │
├──────────────┼────────────────┼────────────────┼──────────────┤
│ P층 정성 뉴스 │ Tavily search  │ WebSearch      │ "미확인"     │
│ P층 심층 뉴스 │ Tavily research│ Firecrawl crawl│ Tavily search│
├──────────────┼────────────────┼────────────────┼──────────────┤
│ DeFi TVL     │ DeFiLlama     │ CoinGecko      │ "미확인"     │
│ DeFi 상세    │ DeFiLlama     │ WebSearch      │ "미확인"     │
│ DEX 거래량   │ DeFiLlama     │ Dune           │ "미확인"     │
├──────────────┼────────────────┼────────────────┼──────────────┤
│ 크립토 가격   │ CoinGecko     │ Yahoo Finance  │ WebSearch    │
│ 글로벌 시총   │ CoinGecko     │ WebSearch      │ "미확인"     │
│ 스테이블코인  │ DeFiLlama     │ CoinGecko      │ "미확인"     │
├──────────────┼────────────────┼────────────────┼──────────────┤
│ 온체인 지표   │ CoinMetrics   │ blockchain.com │ "미확인"     │
│ NUPL         │ CoinMetrics   │ WebSearch      │ "[추정]"     │
├──────────────┼────────────────┼────────────────┼──────────────┤
│ 토큰 홀더    │ Etherscan     │ Dune           │ "미확인"     │
│ RWA 데이터   │ Dune          │ DeFiLlama     │ "미확인"     │
├──────────────┼────────────────┼────────────────┼──────────────┤
│ 한국 기업    │ DART          │ WebSearch      │ "미확인"     │
│ 미국 공시    │ SEC-EDGAR     │ WebSearch      │ "미확인"     │
└──────────────┴────────────────┴────────────────┴──────────────┘

원칙:
  1차 실패 → 2차 자동 전환. 로그 기록.
  2차도 실패 → 최종 폴백. "미확인 — [1차·2차 실패 사유]" 표기.
  "미확인"은 빈칸보다 낫다 (불변 원칙 2).
```
