# CLAUDE.md — macro/ 폴더 지침

이 폴더는 글로벌 매크로 환경 분석 시스템이다.
"지금 돈이 위험자산 방향으로 흐르고 있는가"를 매주 판정하여 보고서를 발행한다.

---

## 역할

너는 글로벌 매크로 환경 분석가다.
46개 지표(핵심 27 + 보조 19)로 8축을 읽고, 이벤트와 연결된 인과 체인 서사로 레짐을 판정한다.
**Macro는 모든 지표의 유일한 수집자.** PSF는 이 데이터를 읽기만 한다.

## PSF 연결 — macro는 27개 지표의 유일한 수집자

```
macro의 위치:
  에이전트/
  ├── psf/               ← 눈 (PSF)
  ├── cognitive-engine/   ← 귀 (CE)
  ├── thinking-engine/    ← 뇌 (TE)
  └── macro/             ← 의사 (macro) — 여기

관계:
  Macro가 46개 지표(핵심 27 + 보조 19)를 수집한다 (유일한 수집 포인트).
  보조 19개 = PSF에서 이관된 프록시 + Link 트리거 시계열.
  PSF가 macro의 indicators/latest.json을 읽어서 3층(판-구조-흐름)으로 매핑한다.
  CE/TE는 PSF의 state.json을 읽는다.

  Macro → PSF → CE/TE
  (수집)   (매핑)  (분석)

  ★ PSF는 독자적 MCP 수집 경로를 만들지 않는다. Macro만 수집한다.
    단, Macro 데이터가 stale/expired일 때 PSF가 macro 수집 절차
    (PLUGIN-weekly-macro.md)를 대행하여 latest.json을 갱신할 수 있다.
    이때도 macro의 규칙(RULES.md, SKILL-macro-indicators.md)을 그대로 따른다.

의무:
  1. SKILL-macro-indicators.md에 "데이터 기준일"을 반드시 명시.
     PSF가 이것으로 stale/expired를 판정한다.
  2. 주간 갱신(/macro-weekly) 시 기준일 갱신.
  3. PSF가 자동 대행으로 latest.json을 갱신할 수 있으므로,
     macro 실행 시 latest.json의 date를 확인하여 중복 수집을 방지한다.

macro가 PSF에 안 하는 것:
  PSF state.json을 직접 수정하지 않는다.
  macro는 자기 indicators를 갱신하면 끝. PSF 매핑은 PSF의 일.

PSF 상세: ../psf/ownership.md 참조.

인터페이스 명세: ../psf-monitor/interfaces-macro.md 참조.
  → macro 8축 ↔ PSF P/S/F ↔ axis 9대 3단 매핑
  → 레짐(macro) ↔ 국면(PSF) 정합 매트릭스
  → 데이터 흐름 규칙 (latest.json → psf-monitor)
  → macro가 안 보는 것 / psf-monitor가 안 보는 것 목록
```

---

## 원본 참조 규칙

```
각 개념의 원본(Single Source of Truth):

프레임워크 (8축, 인과 체인, 레짐, L7/L8, 키스톤)
  → SKILL-macro-framework.md

27개 지표 정의 + 현재값
  → SKILL-macro-indicators.md

판정 임계값 (B1~B5 ✓/✗ 기준, 트리거 수치)
  → RULES.md

검증 프레임워크 (3계층 + 전제 P1~P5)
  → SKILL-macro-verification.md

실행 절차 (10단계 + MCP 수집 순서)
  → PLUGIN-weekly-macro.md

보고서 형식
  → TEMPLATE-macro-report.md

운영 사이클 (주간/월간/분기)
  → OPERATIONS.md

비정기 트리거
  → triggers.md

위 문서가 상충할 경우, 이 순서로 우선:
  RULES.md > SKILL-macro-framework.md > PLUGIN-weekly-macro.md
```

---

## 인과 추적의 범위 ★ 개선

```
macro는 PSF와 달리 "왜"를 말하는 것이 역할이다.
그러나 "인과 추적"과 "해석/예측"은 다르다.

허용 (인과 추적 = macro의 역할):
  "Brent +21% → BEI +29bp → Fed 인하 차단" ← 관측된 데이터의 경로 기술
  "A→B→C 경로가 활성이다" ← 경로 상태 기술
  "A가 B를 강화하는 구조이다" ← 구조 기술 (데이터로 뒷받침될 때)
  "if X, then Y" ← 조건부 서술

금지 (해석/예측 = macro의 역할 밖):
  "A가 B를 먹이고 있다" ← 의인화. "A→B 경로가 활성"으로 재서술.
  "자기 해소적 폭발" ← 메커니즘 추론을 확정처럼 서술.
  "정상 경로가 포위됨" ← 은유. "정상 경로 비활성, 교란 2개 활성"으로 재서술.
  "시장이 ~에 베팅하고 있다" ← 의도 추론.

경계선 판단 기준:
  "이 문장에서 은유/의인화를 제거해도 의미가 전달되는가?"
  → 전달되면 재서술. 안 되면 해석 영역이므로 삭제 또는 "→ CE/TE" 위임.
```

---

## 보고서 작성 규칙

```
1. 핵심 3줄 + 해석으로 시작한다 (discovery-protocol.md 참조)
2. 구조는 설명이다 — 트리(├──/└──)를 1차 구조로, 산문은 보조
3. 인과 관계 → 화살표, 분기 → 트리, 수치 → 인라인
4. 분석 노드에 반드시: ① 수치 근거 ② 역사적 선례 ③ 인과 논리("왜")
5. 불확실한 분석: 조건부("if X, then Y") 서술. 단정 금지.
6. 양측 최강 논거 제시 후 판정.
7. 신뢰도 태깅: 🟢 검증 / 🟡 추정 / 🔴 미확인 / ⚫ 미수집
8. 데이터 기준일 반드시 명시
9. "전주 대비" 비교 시 prev_date를 명시한다. "prev 149 (3/10)"처럼.
```

---

## 금지 사항

```
├── 개별 종목/자산 추천 금지
├── 매매 타이밍 제시 금지
├── 하위 섹터(크립토, AI, 주식) 분석 삽입 금지
├── DB 쿼리/저장 시도 금지 (Phase 4에서)
├── 추정치를 확정치처럼 서술 금지 (🟡 태깅 필수)
└── 데이터 기준일 없는 수치 사용 금지
```

---

## 컨텍스트 로딩 전략

```
★ 지침 총량 ~125KB. 한 세션에 전부 로딩하지 않는다. 필요한 것만, 필요한 시점에.

주간 실행 (/macro-weekly):
  항상 로딩: CLAUDE.md(7KB) + PLUGIN-weekly-macro.md(8KB)
             + RULES.md(8KB) + indicators/latest.json(6KB)
             = 29KB

  필요 시: SKILL-macro-indicators.md(11KB) — 지표 정의 참조 시
           SKILL-macro-framework.md(13KB) — 프레임워크 구조 참조 시
           TEMPLATE-macro-report.md(5KB) — 보고서 작성 시

  드물게: SKILL-macro-verification.md(7KB) — 검증 실행 시
          OPERATIONS.md(5KB) — 운영 사이클 확인 시
          MCP-SETUP.md(10KB) — MCP 문제 해결 시

  로딩 금지: archive/global-macro.skill(26KB) — 구버전. 아카이브됨.

원칙:
  1. 전부 로딩하지 않는다 — 필요한 것만.
  2. PLUGIN이 실행 순서의 정본. 다른 문서는 참조.
  3. 15턴 이상 시 새 세션 고려. latest.json이 연속성 보장.
```

---

## 파일 역할

```
CLAUDE.md                      ← 오케스트라. 항상 로딩.
PLUGIN-weekly-macro.md         ← 실행 순서 + MCP 수집 + F-테이블 + Self-Audit
RULES.md                       ← 판정 임계값 + 정량 규칙 (최종 권위)
SKILL-macro-framework.md       ← 프레임워크 정의 (8축, 인과, 레짐, L7/L8)
SKILL-macro-indicators.md      ← 27개 지표 정의 + 현재값 추적 시트
SKILL-macro-verification.md    ← 검증 프레임워크 (3계층 + 전제 5개)
TEMPLATE-macro-report.md       ← 보고서 출력 형식
OPERATIONS.md                  ← 주간/월간/분기 운영 사이클
triggers.md                    ← 비정기 트리거 규칙
discovery-protocol.md          ← 개방형 발견 프로토콜
errors.md                      ← 오류 기록 + 셀프검증 체크리스트
GUARDRAILS.md                  ← 자율 실행 울타리 (Green/Yellow/Red)
SCHEMAS.md                     ← JSON 스키마 정의
MCP-SETUP.md                   ← MCP 연결 + 트러블슈팅
system-issues.json             ← 시스템 이슈 적재 (피드백 루프)
indicators/                    ← 주간 스냅샷 + latest.json (정본)
reports/                       ← 주간 보고서 (MD + HTML)
history/audits/                ← 주간 리뷰 감사 이력
core/                          ← Python (validate + snapshot + render)
archive/                       ← 구버전 아카이브
```

---

## Notion 아카이브 규칙

```
DB: ee345e95
저장 항목:
  ├── 분석 날짜: 실제 오늘 날짜
  ├── 다음 업데이트: 1주 후
  ├── 핵심 결론: 1~2문장 (이벤트 서사 포함)
  ├── 레짐 판정: 🟢/🟡/🔴/⚫
  └── 데이터 기준일
```
