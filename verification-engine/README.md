# 6-Layer Verification Engine

외부 문서(투자 리포트, 법률 계약서, 크립토 리서치, 매크로 분석, 지정학 시나리오)를 6개 층으로 입체 검증하는 독립 모듈.

**LLM은 비교자이지 판단자가 아니다.** 모든 판정은 1차 소스(MCP) 기준 데이터에 기반하며, 최종 결론은 사용자의 몫이다.

---

## 아키텍처

```
verification-engine/
│
├── mcp_server.py              ← 진입점: MCP 도구 12개 + 세션 관리
│
├── core/                      ← 검증 엔진 (틀)
│   ├── engine.py              │  파이프라인 오케스트레이터
│   ├── models.py              │  데이터 모델 (Claim, Verdict, Result)
│   └── layers/                │  6층 검증 구현
│       ├── fact.py            │  ① MCP 소스 매핑 + 수치 비교
│       ├── norm.py            │  ② 체크리스트 + 규정 준수
│       ├── logic.py           │  ③ 규칙 대입 + KC 추출
│       ├── temporal.py        │  ④ 시점 정합 + gap 계산
│       ├── incentive.py       │  ⑤ 이해충돌 + 공시 검증
│       └── omission.py        │  ⑥ 누락 위험 + BBJ Break
│
├── data/                      ← 기준 데이터
│   ├── checklists.json        │  Norm(7 doc_type) + Omission(18 섹터)
│   ├── rules.json             │  Logic 규칙 (34개)
│   └── claim_type_matrix.json │  claim 유형 × 적용 층 매트릭스
│
├── prompts/                   ← 판정 로직 (두뇌)
│   ├── CLAUDE.md              │  불변 원칙 + 판정 체계 + Tier + KC/BBJ
│   ├── SKILL.md               │  Phase 0→1→1.5→2→2.5→3+4→4.5→5
│   ├── extract_claims.md      │  Phase 1: claim 추출
│   ├── fact_check.md          │  Phase 2①
│   ├── norm_check.md          │  Phase 2②
│   ├── logic_check.md         │  Phase 2③
│   ├── temporal_check.md      │  Phase 2④
│   ├── incentive_check.md     │  Phase 2⑤
│   ├── omission_check.md      │  Phase 2⑥
│   ├── coverage_recheck.md    │  Phase 2.5: 미실행 재점검
│   ├── finalize.md            │  Phase 3+4: 유효기간 + 트리거
│   ├── self_audit.md          │  Phase 4.5: 자기 점검
│   └── schemas/
│       ├── io-contracts.md    │  플레이스홀더 JSON 스키마
│       └── component-catalog.md │  HTML CSS 컴포넌트 카탈로그
│
├── output/                    ← HTML 보고서 생성
│   ├── template-verification.html  │  HTML 골격
│   └── [generated].html       │  생성된 보고서
│
└── docs/                      ← 문서 + 아카이브
    └── archive/               │  작업 로그, 로드맵, 분석 문서
```

---

## 핵심 원리: 틀 vs 두뇌

```
┌─────────────────┐     ┌─────────────────┐
│   틀 (코드)      │     │  두뇌 (프롬프트)  │
│                 │     │                 │
│  core/engine.py │◄───►│  prompts/*.md   │
│  core/layers/   │     │  CLAUDE.md      │
│  mcp_server.py  │     │  SKILL.md       │
│  data/*.json    │     │  output/*.md    │
│                 │     │                 │
│  파이프라인 순서  │     │  판정 기준       │
│  상태 관리       │     │  인과 분석       │
│  MCP 도구 제공   │     │  KC/BBJ 추출    │
│  데이터 로드     │     │  보고서 구조     │
└─────────────────┘     └─────────────────┘
```

판정 로직 변경 시 **프롬프트만 수정**. Python 코드를 건드릴 필요 없음.

---

## 파이프라인

```
Phase 0    verify_start() → 세션 생성 + 소스/체크리스트/규칙 로드
  ↓
Phase 1    extract_claims → claim 10~20개 추출 + depends_on 매핑
  ↓
Phase 1.5  MCP 전수 수집 완료 선언 (수집 중 판정 금지)
  ↓
Phase 2    6층 순차 검증: ①Fact → ②Norm → ③Logic → ④Temporal → ⑤Incentive → ⑥Omission
  ↓
Phase 2.5  커버리지 체크 → 미실행 항목 재실행 (최대 2회)
  ↓
Phase 3+4  finalize → 유효기간 + KC→유효조건 + 무효화 트리거
  ↓
Phase 4.5  self_audit → 9항목 자기 점검 → 사용자 승인 대기
  ↓
Phase 5    HTML 보고서 생성 → 사용자 지정 경로에 저장
```

---

## 판정 체계

| 등급 | 의미 |
|---|---|
| 🟢 VERIFIED | MCP 1차 소스 직접 확인 |
| 🟡 PLAUSIBLE | 간접 근거 / 불확실 |
| ⚫ NO BASIS | 기준 데이터 없음 |
| 🔴 FLAGGED | 명백한 문제 |

집계: 🔴 > ⚫ > 🟡 > 🟢 (최고 심각도가 대표)

---

## MCP 도구 (12개)

| 도구 | Phase | 역할 |
|---|---|---|
| verify_orchestrator | 시작 | CLAUDE.md + SKILL.md 결합 반환 |
| verify_start | 0 | 세션 생성 + 소스/체크리스트 로드 |
| verify_add_claim | 1 | claim 등록 |
| verify_set_verdict | 2 | claim별 판정 등록 |
| verify_set_document_verdict | 2 | 문서 전체 판정 (Norm/Incentive/Omission) |
| verify_check_coverage | 2.5 | 미실행 항목 탐지 |
| verify_finalize | 3+4 | 결과 집계 + JSON 반환 |
| verify_get_prompt | 전체 | Phase별 프롬프트 + 플레이스홀더 주입 |
| verify_get_checklist | 2 | 체크리스트 조회 |
| verify_get_rules | 2 | 규칙 조회 |
| verify_add_checklist_item | 4.5+ | 체크리스트 동적 추가 |
| verify_add_rule | 4.5+ | 규칙 동적 추가 |

---

## doc_type 지원 현황

| doc_type | Fact | Norm | Logic | Temporal | Incentive | Omission |
|---|---|---|---|---|---|---|
| equity_research | Full | Full | Full | Full | Full | Full |
| crypto_research | Full | Full | Full | Full | Full | Full |
| legal_contract | - | Full | Full | Full | Full | Full |
| macro_report | Full | Full | Full | Full | Full | Full |
| geopolitical | Full | Full | Full | Full | Full | Full |
| fund_factsheet | Partial | Partial | - | - | Partial | - |
| regulatory_filing | Partial | Partial | - | - | Partial | - |
