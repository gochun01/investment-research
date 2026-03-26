# Global Macro Environment Reader

> **"지금 돈이 위험자산 방향으로 흐르고 있는가"**를 매주 판정하는 독립 매크로 보고서 발행 시스템.

---

## 한눈에 보기

```
27개 매크로 지표 → 4-Layer 계층 분석 → 인과 체인 서사 → 레짐 판정 → 보고서
```

- 하위 섹터(크립토, AI, 주식) 분석과 **독립적으로 작동**
- 매크로 환경 판정 자체가 최종 결과물
- MCP(FRED, Yahoo Finance)로 93% 자동 수집, 나머지 웹검색

---

## 핵심 개념

### 4-Layer 지표 계층

| Layer | 역할 | 개수 | 점검 주기 |
|-------|------|------|----------|
| **A (근본)** | 움직이면 나머지가 따라옴 | 2 | 매주 필수 |
| **B (전달)** | A의 결과이자 시장의 직접 원인 | 5 | 매주 필수 |
| **C (확인)** | B와 교차 검증 | 10 | 불일치 시 상세 |
| **D (배경)** | 구조적 변수 | 10 | 변동 시에만 |

**결정적 7개 변수** (A2개 + B5개):

```
A1 Core PCE     Fed가 움직일 조건이 됐는가 (키스톤)
A2 중국 Credit  미국 밖에서도 돈이 풀리는가
B1 실질금리     돈이 국채에서 멈추는가, 위험자산으로 가는가
B2 DXY          돈이 미국에 갇히는가, 밖으로 퍼지는가
B3 USD/JPY      엔캐리 역류 위험이 있는가
B4 Net Liq      실제로 풀린 돈의 양
B5 HY 스프레드  금융 배관이 막혔는가
```

### 인과 체인

```
정상 경로 2개:
  ├── Fed 경로:  A1→Fed→B1→B4→B2→B5→위험자산
  └── 중국 경로: A2→C4→B2→위험자산

교란 경로 3개 (정상 경로를 무시하거나 역전):
  ├── 엔캐리:  B3 급변 → 글로벌 동반 매도 (Override)
  ├── 유가:    C7→C8→A1 역전 (Fed 인하 차단)
  └── 재정:    D7→D8→B1 상승 (Fed와 상충)
```

### 레짐 판정

```
L7/L8 리스크 게이트 (최우선):
  🟢 정상 (<0.60)  →  레짐 판정 진행
  🟡 경계 (≥0.60)  →  위험자산 축소
  🔴 위기 (L7+L8)  →  현금 극대화

레짐 (L7/L8 정상 시):
  🟢 팽창기:    Layer B 4개+ 위험자산 방향
  🟡 Transition: 2~3개 전환, 방향 미확정
  🔴 수축기:    4개+ 안전자산 방향
```

---

## 폴더 구조

```
macro/
│
├── README.md                      ← 이 파일. 프로젝트 전체 이해용
├── CLAUDE.md                      ← AI 에이전트 지침 (자동 인식)
│
│  ── 설계 문서 ──
├── SKILL-macro-framework.md       8축 정의, 인과 체인, 레짐 규칙 (원본)
├── RULES.md                       판정 임계값 + 정량 규칙 (최종 권위)
├── SKILL-macro-indicators.md      27개 지표 정의 + 현재값 추적 시트 (원본)
├── SKILL-macro-verification.md    3계층 검증 + 5개 전제 점검
├── REQUIREMENTS.md                기능/비기능 요구사항 (원본 참조)
├── PROJECT-GUIDE.md               프로젝트 개요 + 작업 일정
│
│  ── 실행 문서 ──
├── PLUGIN-weekly-macro.md         /macro-weekly 10단계 실행 순서
├── TEMPLATE-macro-report.md       보고서 출력 형식
├── MCP-SETUP.md                   MCP 연결 가이드 + 트러블슈팅
├── OPERATIONS.md                  주간/월간/분기 운영 사이클
├── triggers.md                    비정기 트리거 규칙 (지표 급변, 이벤트)
│
│  ── 데이터 ──
├── indicators/                    주간 YAML 스냅샷 (시계열 누적)
│   ├── _schema.md                 YAML 구조 정의
│   └── 2026-03-10.yaml            예시: 27개 지표 스냅샷
│
│  ── 산출물 ──
└── reports/                       주간 보고서 누적
    ├── GUIDE_annotated-example.md 보고서 작성 가이드 (주석 예시)
    ├── 2026-03-06_macro-weekly.md
    └── 2026-03-10_macro-weekly.md
```

---

## 실행 방법

### 주간 점검 (매주 월요일)

```
/macro-weekly
```

1. MCP로 FRED 13개 + Yahoo 6개 시리즈 자동 수집
2. L7/L8 리스크 게이트 최우선 확인
3. Layer A→B→C→D 순서로 분석
4. 이벤트 식별 + 인과 체인 서술
5. 레짐 판정 + 보고서 생성
6. `indicators/` YAML + `reports/` MD 저장
7. Notion 아카이브

상세 절차: `PLUGIN-weekly-macro.md`

### 비정기 트리거

| 조건 | 긴급도 | 실행 |
|------|--------|------|
| VIX 30+ | 🔴 즉시 | L7/L8 긴급 판정 |
| USD/JPY ±3% | 🔴 즉시 | 엔캐리 교란 점검 |
| Brent ±15% | 🟡 당일 | 유가 교란 점검 |
| FOMC/CPI/PCE | 🟡 당일 | 해당 지표 + 레짐 재판정 |
| 지정학 사건 | 🔴 즉시 | 전체 축약 재실행 |

상세 규칙: `triggers.md`

### 운영 사이클

| 주기 | 내용 | 참조 |
|------|------|------|
| 주간 | 27개 지표 수집 → 보고서 | `OPERATIONS.md` |
| 월간 | 전제 P1~P5 점검 + 트리거 임계값 리뷰 | `OPERATIONS.md` |
| 분기 | SLOOS 반영 + 프레임워크 리뷰 | `OPERATIONS.md` |

---

## MCP 데이터 수집

MCP 19개(FRED 13 + Yahoo 6) + 웹검색 8개 = 27개 지표.
상세 수집 순서: `PLUGIN-weekly-macro.md`
MCP 연결 설정: `MCP-SETUP.md`

---

## 보고서 구조

```
1. 핵심 결론       ← 1문장 (이벤트→지표→방향→레짐)
2. 레짐 판정       ← 레짐 + L7/L8 + 키스톤 + 내러티브
3. 이벤트 서사     ← 3~5문장, 인과 체인
4. 결정적 7개 변수  ← 현재값 + 전주 + 방향
5. 인과 체인 상세   ← 지배 경로 + 교란 + 상충 + 전환 트리거
6. 8축 상세        ← Layer별 차등 (A+B 상세, C 불일치만, D 변동만)
7. 검증 상태       ← 팩트/추론/종합 신뢰도
8. 행동 함의       ← 환경 판정 + 주시 포인트 + 일정
```

보고서 형식: `TEMPLATE-macro-report.md`
작성 가이드: `reports/GUIDE_annotated-example.md`

---

## 문서 체계

### 원본 지정 (Single Source of Truth)

각 개념은 **한 곳**에만 정의되고, 나머지는 참조한다.

| 개념 | 원본 | 참조하는 곳 |
|------|------|-----------|
| 8축, 인과 체인, 레짐, 키스톤 | `SKILL-macro-framework.md` | CLAUDE, README |
| B1~B5 ✓/✗ 기준, L7/L8 공식, 교란 조건 | `RULES.md` | framework, PLUGIN |
| 27개 지표 목록 + 현재값 | `SKILL-macro-indicators.md` | REQUIREMENTS, _schema |
| MCP 수집 순서 | `PLUGIN-weekly-macro.md` | MCP-SETUP |
| 검증 규칙 + 전제 P1~P5 | `SKILL-macro-verification.md` | REQUIREMENTS |

문서 간 상충 시 우선순위: `RULES.md` > `SKILL-macro-framework.md` > `PLUGIN-weekly-macro.md`

### 읽는 순서

```
이해 경로 (선형):
  README → SKILL-macro-framework → RULES → SKILL-macro-indicators
  → 최신 보고서 → GUIDE_annotated-example

실행 경로:
  MCP-SETUP → PLUGIN-weekly-macro → OPERATIONS → triggers

설계 변경 경로:
  REQUIREMENTS → RULES → SKILL-macro-framework → SKILL-macro-verification
```

---

## 현재 상태 (2026-03-11 기준)

```
레짐:     🟡 TRANSITION (4/5 위험자산 방향, 팽창기 접근)
L7/L8:    🟢 정상 (0.18 / 0.02)
키스톤:   Core PCE 2.4% 바인딩 (UNRATE 4.4% 전환 감시 중)
교란:     교란 2 (유가) 활성화 후 부분 해소 (Brent $106→$88)
보고서:   4회 발행 (3/6, 3/6 JP Morgan, 3/7 JP Morgan, 3/10)
```
