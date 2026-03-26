# 6-Layer Verification Engine — 학습 피드백 루프 설계

> 검증 결과가 다음 검증의 입력이 되는 자기강화 시스템

---

## 현재 상태 진단

```
현재 흐름 (단방향):
  문서 입력 → Phase 0~4 → JSON 출력 → 끝 (소멸)

문제:
├── 같은 기관의 리포트를 10번 검증해도 매번 처음부터
├── 반복 발견되는 패턴(예: "A증권은 항상 목표가 과대")이 축적 안 됨
├── 한번 트리거된 KC가 다음 검증에서 자동 점검되지 않음
└── RULES.md, CHECKLISTS.md가 실전 경험으로 성장하지 않음
```

---

## 설계 원칙

```
1. LLM은 여전히 비교자 — 피드백 데이터가 새로운 "기준 데이터"가 됨
2. 자동 삽입이지 자동 판정이 아님 — 과거 데이터를 보여줄 뿐, 판정은 현재 검증에서
3. 최소 저장, 최대 활용 — 저장 단위는 작게(패턴 카드), 활용은 넓게(모든 Phase에서)
4. 사람이 최종 승인 — 패턴 등록은 자동 제안 + 수동 확인
```

---

## 핵심 아이디어: 3개 피드백 레이어

### Layer A: Verification Memory (검증 기억)

**목적:** 과거 검증 결과를 다음 검증에서 자동 참조

```
저장 단위: verification_card (검증 카드)
├── target_id: 검증 대상 (삼성전자, LINK, BDC 섹터 등)
├── author_id: 저자/기관 (미래에셋, Messari 등)
├── date: 검증 일시
├── layer_verdicts: {L1: 🟢, L2: 🟡, L3: 🔴, L4: 🟢, L5: 🟡, L6: 🔴}
├── flagged_claims: [구체적 플래그 리스트]
├── active_kcs: [아직 유효한 KC 전제 리스트]
└── drift_markers: [시간경과로 변할 수 있는 수치 + 기준값]
```

**활용 시점: Phase 0 직후**

```
Phase 0 완료 → target_id + author_id로 Memory 조회
├── 이전 검증 있음:
│   ├── "이전 검증 (2025-03-15): L1🟢 L3🔴 L6🔴"
│   ├── "활성 KC: 반도체 재고조정 미완료 → 이번에도 점검"
│   ├── "지난번 플래그: lr_005(하방 시나리오 누락) → 이번에도 누락인지 확인"
│   └── "Drift: 당시 DRAM 현물가 $2.1 → 현재 MCP 조회 대조"
└── 이전 검증 없음:
    └── 새로운 대상으로 처리 (기존 흐름 유지)
```

**핵심:** 과거 🔴가 이번에 🟢으로 바뀌면 "개선됨" 태그, 과거 🟢이 🔴이면 "악화됨" 태그. 변화 방향 자체가 인사이트.

---

### Layer B: Pattern Registry (패턴 등록부)

**목적:** 반복되는 검증 실패를 일반화된 규칙으로 승격

```
패턴 생명주기:
  1회 발견 → flag (개별 기록)
  2회 반복 → candidate_pattern (후보 패턴으로 태그)
  3회 이상 → proposed_rule (규칙 승격 제안)
  사용자 승인 → RULES.md 또는 CHECKLISTS.md에 정식 등록
```

**구조: pattern_card**

```yaml
pattern_id: "pt_001"
type: "author_bias" | "sector_blind_spot" | "logic_gap" | "temporal_lag" | "omission_repeat"
description: "A증권 리포트는 목표가 산출 시 하방 시나리오를 체계적으로 누락"
evidence:
  - {verification_id: "v_20250301", target: "삼성전자", flag: "lr_005"}
  - {verification_id: "v_20250310", target: "SK하이닉스", flag: "lr_005"}
  - {verification_id: "v_20250318", target: "한미반도체", flag: "lr_005"}
count: 3
status: "proposed_rule"
proposed_action: "A증권 리포트 검증 시 ⑥ Omission에서 lr_005 자동 우선 점검"
```

**패턴 유형 분류:**

| 유형 | 설명 | 승격 대상 |
|---|---|---|
| `author_bias` | 특정 기관의 반복적 편향 | ⑤ Incentive 자동 주석 |
| `sector_blind_spot` | 특정 섹터에서 반복 누락되는 항목 | CHECKLISTS.md 항목 추가 |
| `logic_gap` | 반복되는 논리 구조적 오류 | RULES.md 규칙 추가 |
| `temporal_lag` | 특정 데이터의 시차가 반복 문제 | ④ Temporal 자동 우선 점검 |
| `omission_repeat` | 동일 리스크의 반복적 생략 | ⑥ Omission 체크리스트 가중 |

---

### Layer C: KC Lifecycle Tracker (KC 생명주기 추적)

**목적:** 한번 발견된 KC가 해소될 때까지 모든 관련 검증에서 자동 점검

```
KC 생명주기:
  탄생: 검증 중 KC 전제 추출 → kc_card 생성
  활성: 전제가 아직 미충족 → 관련 검증마다 자동 삽입
  해소: MCP 조회에서 전제 충족 확인 → "해소됨" + 일시 기록
  부활: 해소 후 다시 전제 붕괴 → "부활" + 사이클 카운트 증가

kc_card:
├── kc_id: "kc_semi_001"
├── premise: "반도체 재고조정 완료"
├── indicator: "ISM 제조업 재고 지수 > 50"
├── current_value: 48.2 (2025-03-15 기준)
├── status: "active" | "resolved" | "revived"
├── related_targets: ["삼성전자", "SK하이닉스", "마이크론"]
├── cycle_count: 0 (부활 횟수)
└── created_at / resolved_at / revived_at
```

**활용 시점: Phase 2 ③ Logic**

```
Logic 실행 전 → target_id의 섹터에 걸린 활성 KC 자동 로드
├── "활성 KC-semi-001: 반도체 재고조정 미완료 (ISM 48.2)"
├── "이 KC가 관련된 이전 검증: 삼성전자(3/1), SK하이닉스(3/10)"
└── "→ 이번 문서에서도 이 전제에 의존하는 주장이 있는지 자동 스캔"
```

---

## 구현 방안: Notion DB + JSON 듀얼 저장

### 저장소 구조

```
Option A: Notion DB (추천 — 기존 아카이브 체계와 통합)
├── DB: verification_memory (검증 카드)
│   ├── Properties: target_id, author_id, date, layer_verdicts, flags, kcs
│   └── 기존 ee345e95 DB와 Relation 연결
├── DB: pattern_registry (패턴 등록부)
│   ├── Properties: pattern_id, type, count, status, evidence_links
│   └── count ≥ 3이면 status 자동 변경 (Notion formula)
└── DB: kc_tracker (KC 추적기)
    ├── Properties: kc_id, premise, indicator, status, related_targets
    └── status=active인 KC만 필터 뷰

Option B: JSON 파일 (로컬 경량 버전)
├── /verification_memory.json — 검증 카드 배열
├── /pattern_registry.json — 패턴 등록부
└── /kc_tracker.json — KC 추적기
→ Phase 4의 기존 JSON 저장을 확장하는 형태
```

### Phase 4 확장 (JSON 저장 → JSON 저장 + 피드백 기록)

```
기존 Phase 4: 검증 결과 JSON 생성 → 끝
확장 Phase 4:
  4-1. 검증 결과 JSON 생성 (기존)
  4-2. verification_memory에 검증 카드 추가/업데이트
  4-3. 플래그 패턴 매칭 → pattern_registry 업데이트
       ├── 기존 패턴과 매칭 → count++
       └── 신규 → flag 상태로 등록
  4-4. KC 상태 업데이트
       ├── 새 KC 발견 → kc_card 생성
       ├── 기존 KC 재확인 → current_value 업데이트
       └── 전제 충족 확인 → status: resolved
  4-5. 승격 제안 (count ≥ 3인 패턴)
       └── "⚡ 패턴 승격 제안: [설명] → RULES.md에 추가할까요?"
```

---

## 새로운 Phase 0.5: 피드백 로딩 (추가 Phase)

```
Phase 0: 문서 입력 + 유형 판별 (기존)
  ↓
Phase 0.5: 피드백 로딩 (신규)
  ├── Step 1: target_id로 verification_memory 조회
  │   └── 이전 검증 있으면 → delta 비교 준비
  ├── Step 2: author_id로 pattern_registry 조회
  │   └── 해당 기관의 알려진 패턴 → 우선 점검 항목에 추가
  ├── Step 3: 섹터로 kc_tracker 조회
  │   └── 활성 KC 목록 → Phase 2 ③ Logic에 자동 전달
  └── 결과: feedback_context 객체 생성
      {
        prior_verification: {...} | null,
        author_patterns: [...],
        active_kcs: [...],
        priority_checks: [...]  // 이전 실패 기반 우선 점검
      }
  ↓
Phase 1: 주장 단위 분해 (기존 — 단, priority_checks 반영)
```

---

## 출력 변화: Δ(델타) 섹션 추가

```
기존 출력:
  요약 → L1~L6 판정 → KC → BBJ → 면책

확장 출력:
  요약 → Δ 섹션 (신규) → L1~L6 판정 → KC → BBJ → 면책

Δ 섹션 내용:
┌─────────────────────────────────────────────┐
│ 📊 이전 검증 대비 변화 (Delta)               │
├─────────────────────────────────────────────┤
│ 이전: 2025-03-01 | 이번: 2025-03-20         │
│                                              │
│ L1 Fact:    🟢 → 🟢  (유지)                  │
│ L3 Logic:   🔴 → 🟡  (개선 — KC-1 접근 중)    │
│ L6 Omission: 🔴 → 🟢  (개선 — 하방 시나리오 추가됨) │
│                                              │
│ ⚡ 패턴 알림: A증권 lr_005 반복 (3/3회)       │
│   → 이번에는 하방 시나리오 포함 확인됨 (탈출)   │
│                                              │
│ 🔄 KC 상태 변화:                              │
│   KC-semi-001: active → approaching          │
│   (ISM 재고: 48.2 → 49.7, 임계 50 접근 중)    │
└─────────────────────────────────────────────┘
```

---

## 실패 방어 규칙 추가

```
V-06: 피드백 무시 금지
  Phase 0.5에서 로드된 feedback_context가 존재하면,
  해당 내용을 Phase 2 실행에 반영해야 한다.
  이전 🔴 항목을 점검 없이 🟢으로 바꾸면 안 된다.

V-07: 패턴 승격 제안 누락 금지
  count ≥ 3인 패턴이 존재하면 Phase 4에서 반드시 승격 제안을 출력한다.
  사용자가 무시해도 매번 제안한다 (3회 연속 무시 시 알림 빈도 감소).

V-08: KC 상태 업데이트 누락 금지
  검증에서 KC를 다뤘으면 kc_tracker를 반드시 업데이트한다.
  current_value와 timestamp이 이번 검증 시점으로 갱신되어야 한다.
```

---

## 구현 우선순위

```
┌─────────────────────────────────────────────────────────┐
│ Stage 1 (즉시 — SKILL.md 수정만으로 가능)                │
│                                                          │
│ ✅ Phase 4 JSON에 verification_card 필드 추가            │
│ ✅ Phase 0.5 로직을 SKILL.md에 추가                      │
│ ✅ V-06, V-07, V-08 실패 방어 규칙 추가                  │
│ ✅ 출력에 Δ 섹션 포맷 추가                               │
│                                                          │
│ → 저장소: 로컬 JSON 파일 (/verification_memory.json)     │
│ → Claude Code가 파일을 읽고 쓰는 것만으로 작동            │
├─────────────────────────────────────────────────────────┤
│ Stage 2 (1주 — Notion DB 연동)                           │
│                                                          │
│ 🔲 Notion에 verification_memory DB 생성                  │
│ 🔲 Notion에 pattern_registry DB 생성                     │
│ 🔲 Notion에 kc_tracker DB 생성                           │
│ 🔲 ee345e95 기존 DB와 Relation 연결                      │
│ 🔲 Phase 0.5에서 Notion 조회 로직 추가                   │
│ 🔲 Phase 4에서 Notion 저장 로직 추가                     │
├─────────────────────────────────────────────────────────┤
│ Stage 3 (2주 — 패턴 자동 승격 + 대시보드)                │
│                                                          │
│ 🔲 pattern_registry → RULES.md/CHECKLISTS.md 자동 제안   │
│ 🔲 KC 대시보드 (활성/해소/부활 현황)                     │
│ 🔲 기관별 신뢰도 점수 (검증 이력 기반)                   │
│ 🔲 Heartbeat 연동 (KC indicator 자동 모니터링)            │
└─────────────────────────────────────────────────────────┘
```

---

## 아키텍처 한 눈에

```
                    ┌─────────────────────┐
                    │   verification      │
                    │   _memory.json      │◄──────────────┐
                    │   (검증 카드)         │               │
                    └────────┬────────────┘               │
                             │ 조회                        │ 저장
                    ┌────────▼────────────┐               │
  문서 입력 ──► Phase 0 ──► Phase 0.5     │               │
                    │   (피드백 로딩)       │               │
                    │   ├ prior_verification               │
                    │   ├ author_patterns  │               │
                    │   └ active_kcs       │               │
                    └────────┬────────────┘               │
                             │                             │
                    Phase 1~3 (기존 검증)                   │
                             │                             │
                    ┌────────▼────────────┐               │
                    │   Phase 4 확장       │───────────────┘
                    │   ├ JSON 저장        │
                    │   ├ Memory 업데이트   │──► pattern_registry
                    │   ├ Pattern 매칭     │──► kc_tracker
                    │   └ KC 업데이트      │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   승격 제안 (≥3회)    │
                    │   → RULES.md 추가?   │
                    │   → CHECKLISTS.md?   │
                    └─────────────────────┘
```

---

## 기존 철학과의 정합성 체크

```
"LLM은 비교자이지 판단자가 아니다"
  → ✅ 피드백 데이터는 새로운 기준 데이터. LLM은 여전히 비교만 수행.
  → 과거 🔴은 "이번에도 🔴이어야 한다"가 아니라 "이 항목을 우선 점검하라"는 신호.

"⚫→🟢 승격 절대 금지"
  → ✅ 피드백에서 과거 🟢이었다고 이번에 자동 🟢이 되지 않음.
  → 매번 독립적으로 MCP 조회 후 판정.

"판단권은 인간에게"
  → ✅ 패턴 승격은 자동 제안 + 수동 확인. 자동 등록 없음.

"혀/tongue 원칙"
  → ✅ 피드백 시스템은 "더 많은 기준 데이터"를 제공할 뿐.
  → 뇌(brain)는 여전히 RULES.md + CHECKLISTS.md + 사용자 판단.
```
