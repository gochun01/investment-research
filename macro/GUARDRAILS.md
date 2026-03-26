# GUARDRAILS.md — macro 시스템 안전 장치

이 문서는 macro 시스템의 허용/승인/금지 행동 범위를 정의한다.
모든 실행(정기/비정기)에서 이 규칙을 따른다.

---

## Green Zone (무승인 — 자유 실행)

아래 작업은 승인 없이 즉시 실행한다.

```
├── indicators/latest.json 갱신 (date, regime, A1~D10, AUX)
├── indicators/YYYY-MM-DD.json 스냅샷 저장
├── MCP 데이터 수집 (FRED, Yahoo Finance, CoinGecko, DeFiLlama 등)
├── firecrawl/tavily 크롤링 (TGA, FedWatch, CFTC)
├── 레짐 판정 (🟢🟡🔴, RULES.md 기준)
├── L7/L8 점수 계산 (RULES.md §2 공식)
├── 쿼드런트 판정 (Q1~Q4, RULES.md §2.5)
├── 키스톤 상태 판정 (Core PCE / 고용 바인딩)
├── 인과 체인 서사 작성 (데이터 근거 있는 경로 기술)
├── 보고서 생성 (MD, TEMPLATE-macro-report.md 준수)
├── reports/ 폴더 저장
├── errors.md 오류 기록 추가
├── 교란 경로 활성/해소 판정 (RULES.md §5 기준)
└── 내러티브 판정 (Good news = Good/Bad)
```

---

## Yellow Zone (승인 필요 — 사용자 확인 후 실행)

아래 작업은 사용자에게 변경 내용과 사유를 설명하고 승인을 받은 후 실행한다.

```
├── RULES.md 임계값 변경 (B1~B5 ✓/✗ 기준, L7/L8 가중치 등)
├── SKILL-macro-framework.md 8축 구조 변경 (축 추가/삭제/재정의)
├── SKILL-macro-indicators.md 지표 추가/삭제 (27+23 구성 변경)
├── SKILL-macro-verification.md 검증 프레임워크 변경
├── OPERATIONS.md 운영 사이클 변경 (주기, 트리거 조건)
├── PLUGIN-weekly-macro.md 실행 순서 변경 (Step 추가/삭제/순서 변경)
├── TEMPLATE-macro-report.md 보고서 형식 변경
├── triggers.md 비정기 트리거 규칙 변경
├── Notion 아카이브 저장/수정 (DB ee345e95)
├── _schema.md 스키마 구조 변경
└── 새 MCP 소스 추가 또는 기존 소스 제거
```

---

## Red Zone (금지 — 어떤 상황에서도 실행 불가)

```
├── 개별 종목/자산 추천 (SPY 매수, BTC 매도 등)
├── 매매 타이밍 제시 ("지금이 진입 시점" 등)
├── 하위 섹터 분석 삽입 (크립토 디파이, AI 반도체 등)
├── 추정치를 확정치처럼 서술 (🟡 태깅 없이 미확인 수치 사용)
├── 데이터 기준일 없는 수치 사용
├── PSF state.json 직접 수정 (PSF 매핑은 PSF의 역할)
├── 의인화/은유를 분석으로 대체 ("시장이 베팅 중", "경로가 포위됨")
├── 의도 추론 ("Fed가 ~을 원한다", "시장이 ~에 기대 중")
├── DB 쿼리/저장 시도 (Phase 4 이후)
├── GUARDRAILS.md 자체 수정
└── CLAUDE.md 금지사항 우회
```

---

## Anomaly Detection Triggers (이상 탐지 자동 플래그)

아래 조건 감지 시 자동으로 플래그를 발생시키고, Escalation Level에 따라 대응한다.

### 데이터 이상

| 조건 | 플래그 | Escalation |
|------|--------|------------|
| 지표값 전주 대비 50%+ 변화 (절대값) | ⚠️ DATA_SPIKE | Level 2 |
| MCP 수집값 vs 웹검색값 ±5% 이상 불일치 | ⚠️ DATA_CONFLICT | Level 1 |
| 핵심 27개 중 5개+ 동시 미수집 | 🔴 DATA_BLACKOUT | Level 3 |
| latest.json date가 7일+ 지연 | ⚠️ DATA_STALE | Level 2 |

### 레짐 이상

| 조건 | 플래그 | Escalation |
|------|--------|------------|
| 레짐 2단계 점프 (🟢→🔴 또는 🔴→🟢) | 🔴 REGIME_JUMP | Level 3 |
| Layer B 3개+ 동시 방향 전환 | ⚠️ REGIME_SHIFT | Level 2 |
| Layer B↔C 불일치 3개+ | ⚠️ CROSS_MISMATCH | Level 2 |
| 쿼드런트와 레짐 판정 상충 | ⚠️ QUADRANT_CONFLICT | Level 1 |

### 리스크 이상

| 조건 | 플래그 | Escalation |
|------|--------|------------|
| L7 Score 0.40+ 접근 | ⚠️ L7_WARNING | Level 2 |
| L7 Score 0.60+ 돌파 | 🔴 L7_BREACH | Level 4 |
| L7 + L8 동시 0.60+ | 🔴 CRISIS_GATE | Level 4 |
| VIX 30+ 돌파 | 🔴 VIX_OVERRIDE | Level 3 |
| USD/JPY 주간 ±3%+ | ⚠️ YEN_CARRY | Level 3 |
| L7 Score 전주 대비 0.15+ 급등 | ⚠️ L7_SPIKE | Level 3 |

---

## Escalation Levels (대응 단계)

### Level 1 — 기록

```
조건: 경미한 불일치, 단일 지표 이상
대응:
  1. errors.md에 기록 (🟢 LOW)
  2. 보고서에 주석 추가
  3. 정상 절차 계속
```

### Level 2 — 재검증

```
조건: 다중 지표 이상, 데이터 신뢰도 저하
대응:
  1. errors.md에 기록 (🟡 MEDIUM)
  2. 해당 지표 MCP 재수집 (최대 1회 재시도)
  3. 재수집 후에도 이상 → 보고서에 ⚠️ 플래그 + 해당 지표 신뢰도 🔴 태깅
  4. 레짐 판정에 "재검증 필요" 주석
```

### Level 3 — 긴급 보고

```
조건: 교란 경로 활성, 리스크 게이트 접근, 레짐 급변
대응:
  1. errors.md에 기록 (🔴 HIGH)
  2. 정규 보고서 외 긴급 보고서 별도 생성
  3. 비정기 트리거 절차 발동 (triggers.md)
  4. PSF에 "[긴급]" 상태 전파 (latest.json 즉시 갱신)
```

### Level 4 — 위기 모드

```
조건: L7/L8 ≥ 0.60, 🔴 위기 게이트
대응:
  1. 모든 정규 분석 중단
  2. L7/L8 위기 보고서만 발행 (RULES.md §2 기준)
  3. 레짐 판정 불필요. "🔴 위기" 고정.
  4. latest.json regime.status = "🔴 위기" 즉시 갱신
  5. 정상 복귀 시까지 Level 4 유지
  6. 복귀 조건: L7 < 0.50 AND L8 < 0.50 (2주 연속)
```

---

## 가드레일 위반 시

```
Green Zone 작업 실패: 재시도 1회 → 실패 시 보고서에 "[미수집]" 기록
Yellow Zone 무승인 실행: 즉시 롤백 + errors.md에 PROCESS 오류 기록
Red Zone 실행 시도: 즉시 중단 + errors.md에 🔴 HIGH 기록 + 사용자 알림
```
