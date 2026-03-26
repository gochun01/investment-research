# 6-Layer Verification Engine 업그레이드 — MCP 및 준비사항

> 작성일: 2026-03-17
> 목적: 체크리스트(6layer-verification-upgrade-checklist.md) 전체 실행을 위한
>       MCP 추가 필요 여부 + 준비 사항 전수 점검
> 판정 기준: ✅ 현재 운영 중 / ⚠️ 설정 확인 필요 / 🔴 신규 추가 필요 / ❌ 대체 불가

---

## 1. 현재 운영 중인 MCP 목록 (기준선)

SKILL.md 기준 현재 엔진이 호출하는 MCP:

| MCP | 용도 | 상태 |
|---|---|---|
| DART | 한국 기업 재무제표·공시 | ✅ 운영 중 |
| SEC-EDGAR | 미국 10-K/10-Q | ✅ 운영 중 |
| Yahoo Finance | 주가·PER·PBR·배당 | ✅ 운영 중 |
| FRED | 매크로 지표(금리·GDP·CPI) | ✅ 운영 중 |
| CoinGecko | 토큰 가격·MCap·거래량 | ✅ 운영 중 |
| DeFiLlama | TVL·DEX 볼륨·Fees | ✅ 운영 중 |
| CoinMetrics | MVRV·NVT·온체인 지표 | ✅ 운영 중 |
| Etherscan | 컨트랙트·토큰 전송 | ✅ 운영 중 |
| Tavily | 뉴스 수집·URL 검색 | ✅ 운영 중 |
| Firecrawl | 전문 스크래핑 | ✅ 운영 중 |
| Notion | 아카이브 저장·검색 | ✅ 운영 중 |
| invest-db (PostgreSQL) | 온톨로지 DB | ✅ 운영 중 |

---

## 2. 작업별 MCP 요구사항 전수 대조

### 🔴 L1 — SKILL.md 수정

**L1-01 MCP 전수 수집 선언 조항**

| 신규 도메인 | 필요 MCP | 현재 상태 | 조치 |
|---|---|---|---|
| `macro_report` | FRED | ✅ | 없음 |
| `macro_report` | IMF/OECD 컨센서스 | 🔴 **미운영** | 신규 필요 or 대체 |
| `macro_report` | Fed Dot Plot | ⚠️ FRED 경유 가능 | 확인 필요 |
| `geopolitical` | Tavily (뉴스) | ✅ | 없음 |
| `geopolitical` | 에너지 지표 | ✅ FRED 경유 | 없음 |

> **IMF/OECD 컨센서스 대응 방안:**
> - FRED에 일부 IMF·OECD 데이터 수록됨 (FRED Series: NGDPD 등)
> - 완전 대체 불가 → Tavily로 IMF/OECD 발표 페이지 실시간 스크래핑 가능
> - **결론:** 신규 MCP 추가 없이 `Tavily → imf.org/oecd.org scrape`로 커버 가능

**L1-02, L1-03**
- 파일 수정만. MCP 추가 불필요.

---

### 🟠 L2 — RULES.md 신규 규칙

**L2-01 lr_017 금리 전망 규칙**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| Fed Dot Plot 수치 | FRED (FEDTARMD) | ✅ | 없음 |
| 시장 기대 금리 (OIS) | FRED | ✅ 일부 | 시리즈 ID 확인 필요 |
| 중앙은행 포워드가이던스 | Tavily → 중앙은행 공식사이트 | ✅ | 없음 |

**L2-02 lr_018 GDP 전망 규칙**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| 미국 GDP 실측 | FRED (GDP, GDPC1) | ✅ | 없음 |
| IMF WEO 전망치 | imf.org | 🔴 직접 MCP 없음 | Tavily 스크래핑으로 대체 |
| OECD Economic Outlook | oecd.org | 🔴 직접 MCP 없음 | Tavily 스크래핑으로 대체 |
| Bloomberg 컨센서스 | Bloomberg Terminal | ❌ 접근 불가 | Yahoo Finance 컨센서스로 부분 대체 |

> **Bloomberg 컨센서스 대체 전략:**
> - Yahoo Finance의 analyst estimates로 개별 지표 컨센서스 부분 확인 가능
> - Trading Economics (tradingeconomics.com) → Tavily scrape로 GDP 컨센서스 확인
> - **결론:** Bloomberg MCP 없이도 Tavily + FRED 조합으로 70~80% 커버 가능

**L2-03 lr_019 인플레이션 전망 규칙**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| PCE 실측값 | FRED (PCEPI, PCEPILFE) | ✅ | 없음 |
| CPI 실측값 | FRED (CPIAUCSL) | ✅ | 없음 |
| 기대인플레이션 (BEI) | FRED (T5YIE, T10YIE) | ✅ | 없음 |

> **L2-03은 추가 MCP 없이 완전 실행 가능**

**L2-04 lr_020 수치 서술형 은폐 규칙**
- 문서 내부 텍스트 분석. MCP 불필요.

**L2-05 lr_007_v2 MVRV 컨텍스트 세분화**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| MVRV 현재값 | CoinMetrics | ✅ | 없음 |
| BTC 사이클 시작일 | CoinMetrics / CoinGecko | ✅ | 없음 |
| 사이클 경과 개월수 계산 | 자체 계산 | ✅ | 없음 |

> **L2-05는 추가 MCP 없이 완전 실행 가능**

---

### 🟡 L3 — CHECKLISTS.md 섹터 확장

**L3-01 매크로 리포트 Omission**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| FOMC 경로 | FRED (Dot Plot) | ✅ | 없음 |
| 실질금리 | FRED (REAINTRATREARAT10Y) | ✅ | 없음 |
| GLI 방향성 | 자체 계산 (PSF 브리핑 참조) | ✅ 내부 연산 | 없음 |
| DXY | FRED (DTWEXBGS) | ✅ | 없음 |
| HY 스프레드 | FRED (BAMLH0A0HYM2) | ✅ | 없음 |
| 시나리오 확률 합계 | 문서 내부 계산 | 없음 (계산만) | 없음 |

> **L3-01은 추가 MCP 없이 완전 실행 가능**

**L3-02 지정학 분석 Omission**

| 검증 데이터 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| 에너지 경로 리스크 | Tavily 뉴스 | ✅ | 없음 |
| 원유·가스 가격 | FRED (DCOILWTICO 등) | ✅ | 없음 |
| 지정학 리스크 지수 | GPR Index (geopoliticalrisk.com) | 🔴 직접 MCP 없음 | Tavily 스크래핑 대체 |
| 역사적 유사 사례 | Claude 내부 지식 + Tavily | ✅ | 없음 |

> **GPR Index 대체 전략:**
> - Tavily로 `geopoliticalrisk.com` 또는 관련 논문 스크래핑
> - BlackRock Geopolitical Risk Indicator (BGRI) 뉴스 스크래핑으로 방향성 파악
> - **결론:** Tavily 조합으로 충분히 대체 가능

**L3-03~06 나머지 섹터**
- 문서 텍스트 스캔 기반. 추가 MCP 불필요.
- SaaS 섹터 Churn/NRR → SEC-EDGAR (미국 SaaS 10-K) + Tavily로 커버

---

### 🔵 L4 — 구조 설계

**L4-01 Notion 검증 결과 추적**

| 필요 기능 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| DB 필드 추가 | Notion MCP | ✅ | 설계 작업만 필요 |
| 검증 이력 저장 | invest-db (PostgreSQL) | ✅ | 테이블 설계 필요 |

**L4-02 Phase 2.5 독립화**
- 프롬프트 수정만. MCP 불필요.

**L4-03 OUTPUT_FORMAT.md 신규 생성**
- 파일 작성만. MCP 불필요.

**L4-04 오답노트 프로세스**

| 필요 기능 | 소스 | 현재 상태 | 조치 |
|---|---|---|---|
| Notion 아카이브 검색 | Notion MCP | ✅ | 없음 |
| 실패 분류 저장 | invest-db | ✅ | 테이블 설계 필요 |

---

## 3. 신규 MCP 추가 검토 대상

체크리스트 전체를 실행했을 때 **현재 MCP로 커버 불가능하거나 품질이 낮은 영역** 정리:

### 🔴 신규 추가 우선순위 HIGH

**① OpenBB MCP** (또는 Bloomberg API 대안)
- **필요 이유:**
  - GDP·CPI·금리 컨센서스를 Bloomberg Terminal 없이 구조화 데이터로 가져오는 유일한 대안
  - FRED는 실측값만 제공, 컨센서스(시장 전망 평균)는 별도 소스 필요
  - lr_018 GDP 전망 규칙 + lr_019 인플레이션 전망 규칙의 핵심 데이터
- **옵션:**
  - OpenBB Platform (openbb.co) → 무료, FRED·Yahoo·OECD 통합 API
  - Trading Economics API → 컨센서스 데이터 강점, 유료
- **권장:** OpenBB Platform MCP 구축 (Python SDK 존재, invest-db 연동 가능)
- **우선순위:** L2 작업 실행 전에 필요

**② Semantic Scholar MCP** (또는 학술 DB)
- **필요 이유:**
  - L4-04 오답노트 → 규칙화 작업에서 "역사적 실패 패턴"의 학술 근거 확인 필요
  - 지정학 분석의 역사적 유사 사례(om_geo_004) 검증 시 신뢰도 높은 소스
- **현재 대안:** Tavily로 부분 커버 가능하나 학술 논문 접근 품질 낮음
- **우선순위:** L4 작업 시작 전. 즉각 필요성은 낮음.

---

### ⚠️ 설정 확인 필요 (현재 운영 중이나 검증 필요)

**③ FRED 시리즈 ID 목록 정비**
- **문제:** FRED는 수만 개 시리즈 존재. 검증 엔진이 올바른 시리즈 ID를 쓰는지 확인 필요
- **확인 필요 시리즈:**

| 용도 | 시리즈 ID | 확인 여부 |
|---|---|---|
| Fed Funds Rate (실제) | FEDFUNDS | ✅ 표준 |
| Fed Dot Plot 중앙값 | FEDTARMD | ⚠️ 확인 필요 |
| 실질금리 (10년) | REAINTRATREARAT10Y | ⚠️ 확인 필요 |
| 기대인플레이션 (5년) | T5YIE | ✅ 표준 |
| HY 스프레드 | BAMLH0A0HYM2 | ✅ 표준 |
| DXY (달러지수) | DTWEXBGS | ⚠️ 확인 필요 — 광의 달러지수 |
| PCE (근원) | PCEPILFE | ✅ 표준 |
| GDP 성장률 (전기비연율) | A191RL1Q225SBEA | ⚠️ 확인 필요 |

- **조치:** RULES.md에 시리즈 ID 주석으로 명시 (규칙 실행 시 오조회 방지)

**④ CoinMetrics 사이클 데이터 접근 확인**
- **문제:** lr_007_v2에서 "사이클 경과 개월수" 계산에 BTC 바닥 날짜가 필요
- **확인 필요:** CoinMetrics MCP가 historical low date를 반환하는지
- **대안:** CoinGecko history API로 최저가 날짜 추출 가능

**⑤ Tavily 도메인 접근 정책 확인**
- **문제:** IMF(imf.org), OECD(oecd.org), ECB(ecb.europa.eu) 스크래핑 시
  일부 페이지가 PDF 또는 JavaScript 렌더링 필요
- **확인 필요:** Firecrawl이 해당 도메인 PDF 텍스트 추출 가능한지
- **대안:** 각 기관의 데이터 API (IMF Data API, OECD.Stat API) 직접 연동 검토

---

## 4. invest-db (PostgreSQL) 테이블 설계 필요

L4-01 검증 결과 추적을 위해 신규 테이블 2개 설계 필요:

### 신규 테이블 ① `verification_results`

```sql
CREATE TABLE verification_results (
  id              SERIAL PRIMARY KEY,
  document_id     VARCHAR(100),        -- 검증 대상 문서 식별자
  document_type   VARCHAR(50),         -- equity_research / crypto / macro / geo
  verified_at     TIMESTAMP,           -- 검증 실행 시점
  overall_verdict VARCHAR(10),         -- 🟢🟡🔴⚫
  top_flag        VARCHAR(200),        -- 최고 리스크 플래그 1개
  validity_until  DATE,                -- 유효기간
  json_path       VARCHAR(300),        -- verification_store JSON 경로
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### 신규 테이블 ② `verification_claim_outcomes`

```sql
CREATE TABLE verification_claim_outcomes (
  id                SERIAL PRIMARY KEY,
  verification_id   INT REFERENCES verification_results(id),
  claim_text        TEXT,              -- 검증한 Claim 원문
  claim_type        VARCHAR(50),       -- fact / estimate / opinion
  verdict_at_check  VARCHAR(10),       -- 검증 당시 판정 (🟢🟡🔴⚫)
  outcome_at        DATE,              -- 실제 결과 확인 시점
  outcome_correct   BOOLEAN,          -- 판정이 맞았는가
  failure_reason    VARCHAR(200),      -- 틀렸다면 원인 분류
  rule_triggered    VARCHAR(50),       -- 발동된 규칙 ID (lr_xxx)
  created_at        TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Notion 아카이브 설계 추가 필요

L4-01 추적을 위해 기존 Notion DB(ee345e95)에 필드 추가:

| 신규 필드명 | 타입 | 용도 |
|---|---|---|
| `verified_at` | Date | 검증 실행일 |
| `verification_verdict` | Select (🟢🟡🔴⚫) | 검증 종합 판정 |
| `top_flag_id` | Text | 최고 리스크 플래그 ID |
| `outcome_check_due` | Date | 결과 확인 예정일 (verified_at + 90일) |
| `outcome_correct` | Checkbox | 판정이 맞았는가 |
| `failure_reason` | Select | 수치오류 / 전제붕괴 / 생략 / 이해충돌 |

---

## 6. 전체 준비사항 요약

```
작업 전 준비 (L1~L2 실행 전)
├── ⚠️ FRED 시리즈 ID 목록 정비 (FEDTARMD, DTWEXBGS 등 확인)
├── ⚠️ CoinMetrics 사이클 날짜 반환 여부 확인
├── ⚠️ Firecrawl → imf.org / oecd.org PDF 추출 테스트
└── 🔴 OpenBB MCP 구축 검토 (컨센서스 데이터 공백 해소)

L3 실행 전
└── ⚠️ Tavily 도메인 정책 확인 (IMF·OECD·ECB)

L4 실행 전
├── 🔧 invest-db 신규 테이블 2개 설계 및 생성
├── 🔧 Notion DB 신규 필드 6개 추가
└── 🔴 Semantic Scholar MCP 도입 검토 (학술 근거 강화)

추가 MCP 없이 실행 가능한 작업
├── L1 전체 (SKILL.md 수정만)
├── L2-03, L2-04, L2-05 (FRED + CoinMetrics로 충분)
├── L3-01 전체 (FRED로 충분)
└── L4-02, L4-03, L4-04 (파일·프롬프트 수정만)
```

---

## 7. MCP 추가 없이 즉시 실행 가능한 작업 범위

| 작업 | 추가 MCP 필요 | 즉시 실행 가능 |
|---|---|---|
| L1-01~03 SKILL.md 수정 | 없음 | ✅ |
| L2-01 lr_017 금리 전망 | FRED만으로 부분 실행 | ✅ 부분 |
| L2-02 lr_018 GDP 전망 | OpenBB or Tavily 필요 | ⚠️ 조건부 |
| L2-03 lr_019 인플레이션 | 없음 (FRED 충분) | ✅ |
| L2-04 lr_020 서술형 은폐 | 없음 | ✅ |
| L2-05 lr_007_v2 MVRV | CoinMetrics 확인 필요 | ⚠️ 조건부 |
| L3-01 매크로 Omission | 없음 | ✅ |
| L3-02 지정학 Omission | 없음 (체크리스트 작성만) | ✅ |
| L3-03~06 섹터 보강 | 없음 | ✅ |
| L4-01 Notion 추적 | Notion MCP (운영 중) | ✅ 설계 후 |
| L4-02 감사 독립화 | 없음 | ✅ |
| L4-03 OUTPUT_FORMAT.md | 없음 | ✅ |
| L4-04 오답노트 | Notion MCP (운영 중) | ✅ |

---

*본 문서는 6layer-verification-upgrade-checklist.md 실행을 위한 인프라 점검 문서입니다.*
*OpenBB MCP 구축이 L2 작업의 품질을 가장 크게 좌우하는 단일 변수입니다.*
