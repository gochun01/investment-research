# 글로벌 매크로 분석 시스템 — 요구사항 정의서

```
문서 유형: 요구사항 정의서 (Requirements Specification)
버전:      v1.1
작성일:    2026-03-06
갱신일:    2026-03-11
```

---

## 1. 시스템 정의

### 1-1. 한 문장 정의
매주 27개 매크로 지표를 수집하고, 인과 체인으로 글로벌 환경을 읽어내며, 레짐을 판정하는 보고서 발행 시스템.

### 1-2. 시스템이 하는 것 / 하지 않는 것
```
한다:
├── 27개 지표 데이터 수집 (MCP + 웹검색)
├── 7개 필수 변수로 "돈의 흐름 방향" 판정
├── 이벤트 → 지표 → 레짐 영향의 인과 체인 서술
├── 레짐 판정 (팽창/과열/수축/위기/Transition)
├── L7/L8 시스템 리스크 게이트 판정
├── 주간 보고서 MD 생성 + 로컬 저장
└── Notion 아카이브

하지 않는다:
├── 개별 종목/자산 추천
├── 매매 타이밍 제시
├── 크립토/AI/주식 섹터 분석 (독립 시스템)
├── 실시간 알림 (Phase 4에서)
└── DB 저장 (Phase 4에서)
```

---

## 2. 기능 요구사항

> 프레임워크 상세(8축, 인과 체인, 레짐 규칙) → `SKILL-macro-framework.md`
> 판정 임계값(B1~B5 기준, 교란 조건) → `RULES.md`
> 27개 지표 목록 + 소스 + 수집 방법 → `SKILL-macro-indicators.md`

### FR-01: 데이터 수집
```
입력: 27개 매크로 지표 (SKILL-macro-indicators.md 참조)
수집: MCP 19개(FRED 13 + Yahoo 6) + 웹검색 8개
주기: Layer A+B 매주, C 매주(불일치 시 상세), D 변동 시
실패 시: 웹검색 폴백. 부재 시 "⚫ 미수집" + 직전값 유지.
신선도: RULES.md §7 기준 준수.
```

### FR-02: 이벤트 식별
```
입력: Layer B 5개의 전주 대비 변화
기준: RULES.md §4 유의미 변화 기준 적용
처리: 기준 초과 시 웹검색으로 원인 이벤트 탐색
출력: 이벤트명 + 영향 지표 + 인과 경로 초안
```

### FR-03: 인과 체인 서술
```
입력: 이벤트 + 7개 필수 변수 현재값 + 방향
처리: SKILL-macro-framework.md의 5개 경로에 매핑
출력: 3~5문장 서사 (이벤트→지표→방향→함의)
```

### FR-04: 레짐 판정
```
입력: Layer B ✓/✗ 상태 + L7/L8 점수
규칙: RULES.md §1 (B1~B5 기준) + §6 (의사결정 트리)
출력: 레짐명 + 전주 대비 변경 여부 + 변경 사유
```

### FR-05: L7/L8 판정
```
입력: HY, VIX, SOFR, MOVE, TED
공식: RULES.md §2 참조
출력: L7/L8 점수 + 구성 요소 분해 + 게이트 판정
```

### FR-06: 보고서 생성
```
형식: TEMPLATE-macro-report.md 준수
저장: reports/[날짜]_macro-weekly.md + indicators/[날짜].yaml
```

### FR-07: Notion 아카이브
```
DB: ee345e95
항목: 분석 날짜, 다음 업데이트, 핵심 결론, 레짐 판정, 데이터 기준일
```

### FR-08: 검증 실행
```
규칙: SKILL-macro-verification.md 참조
주간: Layer 1(팩트) + Layer 2(추론). 괴리 기준 ±2%.
월간: Layer 3(전제 P1~P5). 역추적 포함.
```

---

## 3. 비기능 요구사항

### NFR-01: 데이터 정확도
```
Layer A+B: 🟢 MCP 직접 조회 (날짜 기준 명확)
Layer C:   🟢/🟡 MCP + 웹검색 혼합
Layer D:   🟡 웹검색 + 수동 (지연 허용)
충돌 시:   RULES.md §7 데이터 신선도/충돌 규칙 적용
```

### NFR-02: 실행 시간
```
/macro-weekly → 완료까지 10분 이내 목표
  MCP 호출 ~3분 → 분석 ~3분 → 웹검색 ~3분 → 저장 ~1분
```

### NFR-03: 보고서 일관성
```
매주 동일 형식 (TEMPLATE 준수)
레짐 변경 시 반드시 변경 사유 명시
```

### NFR-04: 장애 대응
```
MCP 실패: 웹검색 폴백 → "⚠️ MCP 미연결" 표시
미수집: 직전값 유지 + "⚫ 미수집" 태그
```

---

## 4. 기술 요구사항

### 4-1. 실행 환경
```
├── Claude Code (Opus 4.6)
├── Windows PC (로컬)
├── MCP 서버 (FRED, Yahoo, Notion, Tavily, Firecrawl)
└── 인터넷 연결
```

### 4-2. MCP 요구사항
```
필수:
  ├── FRED MCP: fred_get_series (13개 시리즈)
  ├── Tavily MCP: tavily_search (이벤트 + 수동 지표)
  └── Notion MCP: 아카이브 저장 (DB ee345e95)

권장:
  ├── Firecrawl MCP: TGA, FedWatch, CFTC 크롤링
  └── Yahoo Finance MCP: 6개 티커 (미연결 시 Tavily 폴백)
```

### 4-3. 저장 요구사항
```
reports/[날짜]_macro-weekly.md — 보고서
indicators/[날짜].yaml — 데이터 스냅샷
Notion DB ee345e95 — 아카이브
보존: 최소 52주 (1년)
```
