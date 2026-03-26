# 6-Layer Verification Engine — Notion DB 피드백 시스템 구체 설계

> Option A 구체화: 기존 아카이브(ee345e95) 체계와 통합하는 3-DB 피드백 시스템

---

## 전체 아키텍처

```
기존 Notion 체계
├── ee345e95 (분석 아카이브 DB) — 투자 분석 결과물 저장
└── 87e543c4 (데이터소스 DB) — 원문·소스 관리

신규 Notion DB 3개 (피드백 전용)
├── DB①: verification_memory — 검증 카드 (건별 기록)
├── DB②: pattern_registry — 패턴 등록부 (반복 패턴 추적)
└── DB③: kc_tracker — KC 생명주기 (전제 조건 모니터링)

연결 관계:
  ee345e95 ←──Relation──→ DB① verification_memory
  DB① ────Relation──→ DB② pattern_registry
  DB① ────Relation──→ DB③ kc_tracker
  DB③ ────Relation──→ ee345e95 (KC가 관련된 분석 참조)
```

---

## DB①: verification_memory (검증 기억)

### 목적
매 검증마다 1건의 카드를 생성. 다음 검증 시 동일 target/author 검색으로 이전 이력 로딩.

### Properties 설계

| Property | Type | 설명 | 예시값 |
|---|---|---|---|
| `Name` (Title) | Title | 검증 식별자 | `V-20250320-삼성전자-미래에셋` |
| `verification_id` | Rich Text | 고유 ID | `v_20250320_001` |
| `target_id` | Select | 검증 대상 | `삼성전자`, `LINK`, `BDC섹터` |
| `target_type` | Select | 대상 유형 | `equity` / `crypto` / `sector` / `macro` / `contract` |
| `author_id` | Select | 저자/기관 | `미래에셋`, `Messari`, `Goldman Sachs` |
| `doc_type` | Select | 문서 유형 | `equity_research` / `crypto_research` / `legal_contract` / `fund_factsheet` / `regulatory_filing` |
| `검증일` | Date | 검증 실행 일시 | 2025-03-20 |
| `L1_Fact` | Select | ① Fact 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `L2_Norm` | Select | ② Norm 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `L3_Logic` | Select | ③ Logic 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `L4_Temporal` | Select | ④ Temporal 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `L5_Incentive` | Select | ⑤ Incentive 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `L6_Omission` | Select | ⑥ Omission 판정 | 🟢 / 🟡 / 🔴 / ⚫ |
| `종합점수` | Formula | 🔴 개수 기반 점수 | `(🟢×3 + 🟡×2 + 🔴×0 + ⚫×1) / 18` → 0~1.0 |
| `red_count` | Formula | 🔴 층 수 카운트 | 0~6 |
| `flagged_rules` | Multi-select | 트리거된 규칙 ID | `lr_005`, `lr_002`, `lr_012` |
| `flagged_claims` | Rich Text | 주요 플래그 요약 (JSON) | `[{"claim":"목표가 과대","layer":"L1","verdict":"🔴"}]` |
| `active_kcs` | Rich Text | 활성 KC 요약 (JSON) | `[{"kc_id":"kc_semi_001","premise":"재고조정완료"}]` |
| `drift_markers` | Rich Text | 추적 필요 수치 (JSON) | `[{"indicator":"DRAM현물가","value":2.1,"date":"2025-03-20"}]` |
| `delta_from_prior` | Rich Text | 이전 검증 대비 변화 | `L3: 🔴→🟡(개선), L6: 🔴→🟢(개선)` |
| `prior_verification` | Relation | 이전 검증 카드 링크 | → DB① 자기참조 Relation |
| `related_analysis` | Relation | ee345e95 분석 카드 링크 | → ee345e95 |
| `related_patterns` | Relation | 매칭된 패턴 | → DB② pattern_registry |
| `related_kcs` | Relation | 관련 KC | → DB③ kc_tracker |
| `원문링크` | URL | 검증 대상 문서 URL | |
| `다음검증예정` | Date | 유효기간 기반 자동 설정 | 개별종목→다음분기, 매크로→1개월, 섹터→2주 |
| `비고` | Rich Text | 자유 메모 | |

### Views 설계

| View 이름 | 유형 | 필터/정렬 | 용도 |
|---|---|---|---|
| `📋 전체 이력` | Table | 검증일 desc | 전체 검증 기록 조회 |
| `🔴 Red Flags` | Table | red_count ≥ 2 | 문제 많은 검증만 |
| `🏢 기관별` | Board | Group by author_id | 기관별 검증 패턴 시각화 |
| `🎯 대상별` | Board | Group by target_id | 대상별 검증 이력 추적 |
| `📅 만료 임박` | Table | 다음검증예정 ≤ today+3d | 재검증 필요 알림 |
| `📈 Δ 추적` | Table | delta_from_prior ≠ empty | 변화 있는 것만 |

### Naming Convention

```
Title: V-{YYYYMMDD}-{target_id}-{author_id}
verification_id: v_{YYYYMMDD}_{seq_number}

예시:
  V-20250320-삼성전자-미래에셋      / v_20250320_001
  V-20250320-LINK-Messari          / v_20250320_002
  V-20250321-BDC섹터-자체분석       / v_20250321_001
```

---

## DB②: pattern_registry (패턴 등록부)

### 목적
반복되는 검증 실패를 자동 탐지하고, 임계치(3회) 도달 시 RULES.md/CHECKLISTS.md 승격을 제안.

### Properties 설계

| Property | Type | 설명 | 예시값 |
|---|---|---|---|
| `Name` (Title) | Title | 패턴 설명 | `미래에셋-하방시나리오 체계적 누락` |
| `pattern_id` | Rich Text | 고유 ID | `pt_001` |
| `pattern_type` | Select | 패턴 유형 | `author_bias` / `sector_blind_spot` / `logic_gap` / `temporal_lag` / `omission_repeat` |
| `author_scope` | Select | 해당 기관 (있으면) | `미래에셋`, `ALL` |
| `sector_scope` | Select | 해당 섹터 (있으면) | `반도체`, `크립토`, `ALL` |
| `target_layer` | Multi-select | 관련 검증 층 | `L3_Logic`, `L6_Omission` |
| `matched_rule` | Multi-select | 매칭되는 기존 규칙 ID | `lr_005`, `om_semi_001` |
| `detection_count` | Number | 탐지 횟수 | 3 |
| `status` | Select | 생명주기 상태 | `flag`(1회) / `candidate`(2회) / `proposed`(≥3) / `promoted`(승격완료) / `dismissed`(기각) |
| `evidence_list` | Rich Text | 증거 목록 (JSON) | `[{"v_id":"v_20250301","target":"삼성전자"},...]` |
| `evidence_verifications` | Relation | 증거 검증 카드들 | → DB① (복수) |
| `first_detected` | Date | 최초 탐지일 | 2025-03-01 |
| `last_detected` | Date | 최근 탐지일 | 2025-03-20 |
| `proposed_action` | Rich Text | 승격 시 제안 액션 | `RULES.md에 lr_017로 추가: "미래에셋 리포트 검증 시 lr_005 자동 우선 점검"` |
| `promotion_target` | Select | 승격 대상 파일 | `RULES.md` / `CHECKLISTS.md` / `SKILL.md` / `없음` |
| `promoted_as` | Rich Text | 승격 후 ID (있으면) | `lr_017` or `om_semi_007` |
| `사용자확인` | Checkbox | 승격 승인 여부 | ☑/☐ |

### Pattern Matching 로직

```
Phase 4 실행 시:
  1. 이번 검증의 flagged_rules를 추출
  2. 각 rule에 대해 pattern_registry 조회:
     ├── Query: matched_rule contains {rule_id} AND author_scope = {author_id}
     ├── 기존 패턴 있음 → detection_count++ , evidence 추가, last_detected 갱신
     └── 기존 패턴 없음 → 새 pattern_card 생성 (status: flag)
  3. status 자동 전이:
     ├── count = 1 → flag
     ├── count = 2 → candidate
     ├── count ≥ 3 → proposed (승격 제안 출력)
     └── 사용자확인 ☑ → promoted (RULES/CHECKLISTS 반영 완료)
```

### Views 설계

| View 이름 | 유형 | 필터 | 용도 |
|---|---|---|---|
| `⚡ 승격 대기` | Table | status = proposed, 사용자확인 = ☐ | 승인 필요 패턴 |
| `🔍 후보` | Table | status = candidate | 1회 더 발견 시 승격 |
| `✅ 승격 완료` | Table | status = promoted | 이미 규칙화된 것 |
| `🏢 기관별 편향` | Board | Group by author_scope, type = author_bias | 기관 편향 한눈에 |
| `🏭 섹터 사각지대` | Board | Group by sector_scope, type = sector_blind_spot | 섹터별 누락 패턴 |

### 자동 승격 제안 출력 포맷

```
Phase 4 완료 후 (count ≥ 3인 패턴 존재 시):

┌──────────────────────────────────────────────────────┐
│ ⚡ 패턴 승격 제안 (pattern_registry)                   │
├──────────────────────────────────────────────────────┤
│ pt_001 | author_bias | 미래에셋                       │
│ "하방 시나리오 체계적 누락" (lr_005)                    │
│ 탐지: 3회 (삼성전자 3/1, SK하이닉스 3/10, 한미반도체 3/18) │
│                                                       │
│ 제안 액션:                                             │
│   RULES.md에 lr_017 추가:                              │
│   "미래에셋 리포트 → ⑥ Omission에서 lr_005 자동 우선 점검" │
│                                                       │
│ → "승격해줘" / "기각" / "보류"                          │
└──────────────────────────────────────────────────────┘
```

---

## DB③: kc_tracker (KC 생명주기 추적)

### 목적
발견된 KC(Kill Condition)의 전제가 해소될 때까지 추적. 관련 검증마다 자동 로딩.

### Properties 설계

| Property | Type | 설명 | 예시값 |
|---|---|---|---|
| `Name` (Title) | Title | KC 설명 | `반도체 재고조정 미완료` |
| `kc_id` | Rich Text | 고유 ID | `kc_semi_001` |
| `premise` | Rich Text | 전제 조건 문장 | `반도체 재고조정이 완료되어야 함` |
| `indicator` | Rich Text | 판별 지표 + 조건 | `ISM 제조업 재고지수 > 50` |
| `indicator_source` | Select | MCP 소스 | `FRED` / `CoinGecko` / `Yahoo Finance` / `DeFiLlama` / `manual` |
| `threshold` | Rich Text | 임계값 (JSON) | `{"operator":">","value":50,"unit":"index"}` |
| `current_value` | Number | 최근 측정값 | 48.2 |
| `current_value_date` | Date | 측정 일시 | 2025-03-15 |
| `gap_to_threshold` | Formula | 임계값까지 거리 | `abs(current_value - threshold.value)` |
| `trend_direction` | Select | 추세 방향 | `approaching` / `diverging` / `flat` / `unknown` |
| `status` | Select | 생명주기 | `active` / `approaching` / `resolved` / `revived` |
| `sector_scope` | Multi-select | 관련 섹터 | `반도체`, `AI` |
| `related_targets` | Multi-select | 영향받는 대상 | `삼성전자`, `SK하이닉스`, `마이크론` |
| `cycle_count` | Number | 부활 횟수 | 0 |
| `created_at` | Date | 최초 발견일 | 2025-03-01 |
| `resolved_at` | Date | 해소일 (있으면) | |
| `revived_at` | Date | 부활일 (있으면) | |
| `origin_verification` | Relation | 최초 발견 검증 카드 | → DB① |
| `all_verifications` | Relation | 관련된 모든 검증 | → DB① (복수) |
| `related_analysis` | Relation | 관련 분석 카드 | → ee345e95 |
| `heartbeat_monitor` | Checkbox | Heartbeat 자동 모니터링 대상 | ☑/☐ |
| `check_frequency` | Select | 점검 주기 | `daily` / `weekly` / `monthly` / `on_event` |
| `비고` | Rich Text | | |

### KC 상태 전이 규칙

```
┌──────────┐    전제 미충족     ┌──────────┐
│  active  │◄──────────────────│ (신규발견) │
└────┬─────┘                   └──────────┘
     │
     │ current_value가 threshold에 접근 (gap ≤ 10%)
     ▼
┌──────────────┐
│ approaching  │  ← "거의 해소되지만 아직 아님"
└────┬─────────┘
     │
     │ 조건 충족
     ▼
┌──────────┐
│ resolved │  ← resolved_at 기록
└────┬─────┘
     │
     │ 다시 조건 미충족 (역행)
     ▼
┌──────────┐
│ revived  │  ← revived_at 기록, cycle_count++
└──────────┘    → 다시 active로 전이
```

### 상태 판정 자동화 (Phase 0.5 + Phase 4)

```
Phase 0.5 (검증 시작 시):
  1. target의 sector_scope로 kc_tracker 조회
     Query: sector_scope contains {sector} AND status in [active, approaching, revived]
  2. 활성 KC 목록을 feedback_context.active_kcs에 적재
  3. 각 KC의 indicator를 MCP로 실시간 조회 → current_value 갱신

Phase 4 (검증 완료 후):
  1. 갱신된 current_value로 상태 재판정:
     ├── threshold 충족 → status: resolved, resolved_at: today
     ├── gap ≤ 10% → status: approaching, trend_direction 갱신
     ├── gap > 10% 유지 → status 유지
     └── resolved였는데 다시 미충족 → status: revived, cycle_count++
  2. Notion DB③ 업데이트
  3. 새로 발견된 KC → 신규 kc_card 생성
```

### Views 설계

| View 이름 | 유형 | 필터 | 용도 |
|---|---|---|---|
| `🔴 활성 KC` | Table | status in [active, revived] | 현재 유효한 위험 전제 |
| `🟡 접근 중` | Table | status = approaching | 곧 해소될 가능성 |
| `✅ 해소됨` | Table | status = resolved | 해소 이력 |
| `🔄 부활` | Table | cycle_count ≥ 1 | 반복적으로 부활하는 KC |
| `⏰ Heartbeat 대상` | Table | heartbeat_monitor = ☑ | 자동 모니터링 목록 |
| `🏭 섹터별` | Board | Group by sector_scope | 섹터별 활성 KC 현황 |

---

## DB 간 Relation 맵 (전체)

```
ee345e95 (분석 아카이브)
    │
    │ related_analysis (1:N)
    │
    ▼
DB① verification_memory ◄────────────────────────┐
    │           │           │                      │
    │           │           │ evidence_verifications│
    │           │           │ (N:1)                 │
    │           │           ▼                      │
    │           │     DB② pattern_registry         │
    │           │                                   │
    │           │ all_verifications (N:N)            │
    │           ▼                                   │
    │     DB③ kc_tracker ──────────────────────────┘
    │           │         related_analysis
    │           │
    ▼           ▼
  87e543c4    (Heartbeat 연동 대상)
 (데이터소스)
```

---

## Phase별 Notion 호출 명세

### Phase 0.5: 피드백 로딩

```
Step 1: 이전 검증 조회
  API: Notion DB① 조회
  Filter: target_id = {current_target} AND author_id = {current_author}
  Sort: 검증일 desc
  Limit: 1 (가장 최근)
  
  결과 활용:
  ├── 있으면 → prior_verification에 저장
  │   ├── 6층 판정 로딩 (L1~L6)
  │   ├── flagged_rules 로딩 (이번에도 해당되는지 점검 대상)
  │   ├── drift_markers 로딩 (변한 수치 추적)
  │   └── active_kcs 로딩
  └── 없으면 → skip (신규 대상)

Step 2: 기관 패턴 조회
  API: Notion DB② 조회
  Filter: author_scope = {current_author} AND status in [candidate, proposed]
  
  결과 활용:
  ├── 있으면 → priority_checks에 추가
  │   └── "이 기관은 lr_005 패턴 2회 발견 → 이번에도 우선 점검"
  └── 없으면 → skip

Step 3: 활성 KC 조회
  API: Notion DB③ 조회
  Filter: sector_scope contains {current_sector} AND status in [active, approaching, revived]
  
  결과 활용:
  ├── 있으면 → active_kcs에 적재
  │   ├── 각 KC의 indicator를 MCP로 실시간 조회
  │   └── current_value 갱신 (Phase 4에서 DB 업데이트)
  └── 없으면 → skip

Output: feedback_context 객체
  {
    prior_verification: { ... } | null,
    author_patterns: [ ... ],
    active_kcs: [ ... ],
    priority_checks: [ ... ],
    drift_markers: [ ... ]
  }
```

### Phase 4: 피드백 저장

```
Step 4-1: 검증 카드 저장 (기존 JSON + Notion)
  API: Notion DB① 페이지 생성
  Properties: 위 DB① 스키마 전체
  
  delta 계산:
  ├── prior_verification 있으면 → 각 층 비교
  │   ├── 🔴→🟢 = "개선"
  │   ├── 🟢→🔴 = "악화"
  │   └── 동일 = "유지"
  └── delta_from_prior에 기록
  
  prior_verification Relation 연결

Step 4-2: 패턴 매칭 + 업데이트
  이번 검증의 flagged_rules 각각에 대해:
  
  API: Notion DB② 조회
  Filter: matched_rule contains {rule_id} AND
          (author_scope = {author_id} OR author_scope = ALL) AND
          (sector_scope = {sector} OR sector_scope = ALL)
  
  ├── 기존 패턴 있음:
  │   API: Notion DB② 페이지 업데이트
  │   ├── detection_count++
  │   ├── last_detected = today
  │   ├── evidence_list에 추가
  │   ├── evidence_verifications Relation에 이번 카드 추가
  │   └── status 전이 체크 (count 기반)
  │
  └── 기존 패턴 없음:
      API: Notion DB② 페이지 생성
      ├── status = flag
      ├── detection_count = 1
      └── first_detected = today

Step 4-3: KC 업데이트
  A) 기존 KC 상태 갱신:
     Phase 0.5에서 조회한 active_kcs 각각에 대해:
     
     API: Notion DB③ 페이지 업데이트
     ├── current_value = MCP 조회 결과
     ├── current_value_date = today
     ├── trend_direction 재계산
     ├── status 전이 판정
     └── all_verifications Relation에 이번 카드 추가
  
  B) 신규 KC 발견 시:
     API: Notion DB③ 페이지 생성
     ├── status = active
     ├── created_at = today
     ├── origin_verification = 이번 카드
     └── heartbeat_monitor = 섹터별 기본값
         (반도체→☑, 크립토→☑, 기타→☐)

Step 4-4: ee345e95 연결
  이번 target에 대한 기존 분석이 ee345e95에 있으면:
  API: Notion DB① 페이지 업데이트
  └── related_analysis Relation 연결
```

---

## Heartbeat 연동 설계

```
Heartbeat이 KC를 자동 모니터링하는 구조:

DB③ kc_tracker에서 heartbeat_monitor = ☑인 KC 목록
  → Heartbeat의 모니터링 대상에 등록
  → 각 KC의 indicator + indicator_source + threshold 정보 전달
  → Heartbeat이 주기적으로 MCP 조회

상태 변화 감지 시:
  ├── approaching → resolved: 
  │   Telegram: "✅ KC 해소: {kc_id} — {premise} 조건 충족"
  ├── active → approaching:
  │   Telegram: "🟡 KC 접근: {kc_id} — {indicator} 임계 {gap}% 이내"
  └── resolved → revived:
      Telegram: "⚠️ KC 부활: {kc_id} — {premise} 다시 미충족"

Heartbeat 점검 주기 (check_frequency):
  daily  → FRED 금리, DXY, 주요 지수 관련 KC
  weekly → 섹터 구조 변화 관련 KC  
  monthly → 매크로 저빈도 데이터 KC (GDP, SLOOS 등)
  on_event → FOMC, CPI 등 이벤트 후 즉시
```

---

## MCP 호출 시퀀스 (Phase 0.5 전체)

```
Phase 0.5 실행 시 Notion MCP 호출 순서:

1. notion-query DB① (verification_memory)
   → target + author로 이전 검증 조회
   → API: databases/{db①_id}/query
   → filter: and(target_id = X, author_id = Y)
   → sort: 검증일 desc, page_size: 1

2. notion-query DB② (pattern_registry)  
   → author로 패턴 조회
   → API: databases/{db②_id}/query
   → filter: and(author_scope = Y, status in [candidate, proposed])

3. notion-query DB③ (kc_tracker)
   → sector로 활성 KC 조회
   → API: databases/{db③_id}/query
   → filter: and(sector_scope contains Z, status in [active, approaching, revived])

4. MCP 실시간 조회 (KC indicator 갱신)
   → 각 활성 KC의 indicator_source에 따라:
   ├── FRED → FRED MCP
   ├── CoinGecko → CoinGecko MCP
   ├── Yahoo Finance → Yahoo Finance MCP
   └── etc.

총 Notion 호출: 3회 (Phase 0.5)
총 Notion 호출: 2~5회 (Phase 4, 건수에 따라)
MCP 호출: 활성 KC 수에 비례
```

---

## Notion DB 생성 실행 가이드

### Step 1: DB 생성 순서

```
반드시 이 순서로 생성 (Relation 의존성):
  1. DB③ kc_tracker (독립, 의존 없음)
  2. DB② pattern_registry (독립, 의존 없음)
  3. DB① verification_memory (DB②, DB③에 Relation)
  4. DB① ↔ ee345e95 양방향 Relation 추가
  5. DB③ → ee345e95 단방향 Relation 추가
```

### Step 2: 각 DB 생성 시 Claude Code 명령

```
DB③ 생성:
  "Notion에 kc_tracker DB 만들어줘. 
   Properties: [위 DB③ 스키마]. 
   워크스페이스 루트에 생성."

DB② 생성:
  "Notion에 pattern_registry DB 만들어줘.
   Properties: [위 DB② 스키마].
   워크스페이스 루트에 생성."

DB① 생성:
  "Notion에 verification_memory DB 만들어줘.
   Properties: [위 DB① 스키마].
   DB②, DB③에 Relation 연결.
   ee345e95에도 Relation 연결."
```

### Step 3: 초기 데이터

```
기존 검증 결과가 JSON으로 남아있으면:
  → Phase 4 JSON 파일에서 verification_card 추출
  → DB①에 일괄 등록 (backfill)
  → 패턴 매칭 일괄 실행 → DB② 초기 패턴 생성
  → KC 추출 → DB③ 초기 KC 등록
```

---

## SKILL.md 수정 범위 요약

```
추가할 내용:
├── Phase 0.5 (피드백 로딩) 전체 섹션
├── Phase 4 확장 (4-2, 4-3, 4-4 스텝)
├── 실패 방어 규칙 V-06, V-07, V-08
├── 출력 포맷에 Δ 섹션 추가
└── 보조 파일 참조 규칙에 Notion DB ID 추가

수정하지 않는 것:
├── Phase 1 (주장 분해) — 기존 유지
├── Phase 2 (6층 검증) — 기존 유지, feedback_context 참조만 추가
├── Phase 3 (출력) — Δ 섹션 추가만
├── 불변 원칙 5개 — 절대 변경 없음
└── RULES.md, CHECKLISTS.md — 패턴 승격 시에만 수정 (수동)
```

---

## 비용/트레이드오프

```
장점:
├── 기존 ee345e95 아카이브와 원클릭 연동
├── Notion Board 뷰로 패턴/KC 시각화 즉시 가능
├── Notion Formula로 자동 점수 계산 (종합점수, red_count)
├── Notion Filter로 "만료 임박" 자동 알림
└── Claude Code + Notion MCP로 구현 완결

대가:
├── Phase 0.5에 Notion 조회 3회 추가 (속도 ~3초)
├── Phase 4에 Notion 쓰기 2~5회 추가 (속도 ~5초)
├── Notion API rate limit 주의 (분당 3회 제한 시 순차 호출)
└── JSON 로컬 백업 병행 권장 (Notion 장애 대비)

vs JSON-only 대비:
├── Notion: 시각화 ✅, 검색 ✅, 공유 ✅, 속도 △
└── JSON:  시각화 ✗, 검색 △, 공유 ✗, 속도 ✅
→ 권장: Notion 주저장 + JSON 로컬 백업 (듀얼)
```
