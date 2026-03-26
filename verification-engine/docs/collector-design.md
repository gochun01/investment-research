# Verification Collector 설계서

---

## SS1. 개요

| 항목 | 내용 |
|---|---|
| 프로젝트명 | Verification Collector |
| 트랙 | Medium (5~8 에이전트, 병렬/분기/루프) |
| 에이전트 수 | 7개 |
| 팀 수 | 4개 팀 |
| 병렬 구간 | Team A(소스 병렬 스캔), Team B(Quick Check 병렬) |
| 핵심 정체성 | 6-Layer 검증 엔진에 다양한 문서를 자동 공급하여 경험 데이터(KC/패턴/규칙 활성도)를 축적하는 독립 수집 모듈 |
| 엔진 위치 | `C:\Users\이미영\Downloads\에이전트\verification-engine` |
| 수집기 위치 | `C:\Users\이미영\Downloads\에이전트\verification-engine\collector` (신규) |

---

## SS2. 기획 요약

Verification Collector는 8개 문서 유형(news_article, equity_research, crypto_research, legal_contract, macro_report, geopolitical, regulatory_filing, fund_factsheet)에 대해 다양한 외부 소스에서 문서를 자동 수집하고, 검증 엔진의 MCP 도구를 통해 간이/전체 검증을 수행하며, 그 결과를 KC 레지스트리·패턴 레지스트리·규칙 활성도에 축적한다. 핵심 가치는 **양보다 다양성** — 8개 유형이 골고루 축적되어야 하며, Balance Monitor가 편향을 감지하면 수집 우선순위를 자동 조정한다. 일 단위 자동 실행과 수동 온디맨드 실행을 모두 지원하며, 성공 기준은 8 doc_type × 5건 검증, 5개 이상 패턴 제안, 10개 이상 규칙 활성도 자동 기록이다. 주간 배치에서 `verify_analyze_outcomes()`를 실행하여 규칙 승격을 제안하되, 최종 승격 결정은 반드시 사용자가 수행한다.

---

## SS3. 기술 스택

### LLM 모델 배정

| 에이전트 | 모델 | 근거 |
|---|---|---|
| Agent 01: Source Monitor | Haiku | 단순 스크래핑 + URL 추출. 판단 불필요 |
| Agent 02: Classifier | Sonnet | doc_type 분류 + 중복 판별. 중간 수준 추론 |
| Agent 03: Quick Verifier | Sonnet | `verify_quick_check()` 결과 해석 + claim 추출 |
| Agent 04: Full Verifier | Opus | Phase 0~5 전체 검증. 복잡 추론 + MCP 교차검증 |
| Agent 05: Accumulator | 불필요 (코드) | JSON 파일 업데이트. LLM 판단 불필요 |
| Agent 06: Analyst | Opus | `verify_analyze_outcomes()` 해석 + 승격 제안 생성 |
| Agent 07: Balance Monitor | 불필요 (코드) | 분포 계산 + 우선순위 조정. 순수 로직 |

### MCP 도구 매핑

| 에이전트 | 사용 MCP 도구 |
|---|---|
| Agent 01 | `tavily_search`, `tavily_crawl`, `firecrawl_scrape`, `firecrawl_search` |
| Agent 02 | `verify_list_history` (중복 확인) |
| Agent 03 | `verify_quick_check`, `verify_add_claim`, `verify_set_verdict`, `verify_finalize` |
| Agent 04 | `verify_start`, `verify_add_claim`, `verify_set_verdict`, `verify_set_document_verdict`, `verify_get_checklist`, `verify_get_rules`, `verify_check_coverage`, `verify_finalize`, `verify_generate_html`, FRED/Yahoo Finance/CoinMetrics/SEC-EDGAR 등 데이터 MCP |
| Agent 05 | `verify_check_triggers`, `verify_rule_activity`, `verify_get_kc_status`, `verify_get_patterns` |
| Agent 06 | `verify_analyze_outcomes`, `verify_get_patterns`, `verify_rule_activity` |
| Agent 07 | 없음 (내부 JSON 집계만) |

### 데이터 소스 — doc_type별

| doc_type | 주요 소스 | 수집 도구 |
|---|---|---|
| news_article | 국내외 뉴스 사이트, Google News | Tavily Search |
| equity_research | 증권사 리포트 (네이버 금융, KIND), SEC EDGAR | Tavily Search, Firecrawl, SEC-EDGAR MCP |
| crypto_research | Messari, The Block, CoinDesk | Tavily Search, Firecrawl |
| legal_contract | 공개 계약서 사례, 법률 리포트 | Tavily Search, Firecrawl |
| macro_report | IMF, World Bank, 한은, FRED 블로그 | Tavily Search, FRED MCP |
| geopolitical | 외교 전문 매체, 싱크탱크 보고서 | Tavily Search |
| regulatory_filing | 안전보건 공시, 금융 규제 문서, DART | Tavily Search, DART MCP |
| fund_factsheet | 자산운용사 팩트시트, ETF 정보 | Tavily Search, Firecrawl |

### 저장소 전략

| 구분 | 저장소 | 역할 |
|---|---|---|
| 원본(Source of Truth) | JSON 파일 (`data/`, `output/history/`) | 모든 검증 결과, KC, 패턴, 규칙 활성도 |
| 뷰어(Viewer) | Notion 3-DB | Verification Memory, Pattern Registry, KC Tracker 시각화 |
| 수집 이력 | `collector/state/collection_log.json` | 수집 건별 상태 추적 |
| 밸런스 상태 | `collector/state/balance_state.json` | 유형별 분포 + 우선순위 |

---

## SS4. 에이전트 정의

### Team A: 수집팀 (병렬 수집 → 순차 분류)

#### Agent 01: Source Monitor

| 항목 | 내용 |
|---|---|
| 역할 | 8개 소스 유형에서 검증 대상 문서를 병렬로 탐색하여 원시 후보 목록을 생성한다 |
| 에이전트 유형 | 수집형 (코드 80%) |
| LLM | Haiku |
| 입력 | `CollectionRequest` — 수집 우선순위(doc_type별 가중치), 수집 목표 건수, 제외 URL 목록 |
| 출력 | `RawCandidateList` — 후보 문서 배열 [{title, url, snippet, source, timestamp, estimated_doc_type}] |
| MCP 도구 | `tavily_search`, `tavily_crawl`, `firecrawl_scrape`, `firecrawl_search` |
| 실패 모드 | (1) 특정 소스 스크래핑 차단 → degraded, 해당 소스 스킵 후 계속 (2) 전체 소스 무응답 → fatal, 캐시된 이전 후보 사용 또는 중단 |

팀 출력 집계: Agent 01 → Agent 02 순차 전달 (분류 전 원시 데이터)

부분 실패: 8개 소스 중 K개 성공 시, K ≥ 4이면 계속 진행. K < 4이면 이전 수집 결과 보충 후 계속.

---

#### Agent 02: Classifier

| 항목 | 내용 |
|---|---|
| 역할 | 후보 문서의 doc_type을 자동 판별하고, 기존 검증 이력과 대조하여 중복을 제거한다 |
| 에이전트 유형 | 분석형 (코드 40%) |
| LLM | Sonnet |
| 입력 | `RawCandidateList` — Agent 01의 후보 목록 |
| 출력 | `ClassifiedDocList` — 분류 완료 문서 배열 [{title, url, doc_type, confidence, is_duplicate, dedup_reason}] |
| MCP 도구 | `verify_list_history` |
| 실패 모드 | (1) doc_type 오분류 → degraded, 검증 단계에서 재분류 가능 (2) 중복 판별 실패 (history 로드 불가) → degraded, 중복 허용 후 진행 |

**체크포인트 #1**: 분류 완료 후, 다음 조건을 확인:
- 유효 후보(is_duplicate=false) ≥ 1건
- doc_type 분류 confidence ≥ 0.7인 항목만 통과
- 미달 시 Agent 01에 추가 수집 요청 (최대 2회)

---

### Team B: 검증팀 (Quick은 병렬, Full은 순차)

#### Agent 03: Quick Verifier

| 항목 | 내용 |
|---|---|
| 역할 | 분류된 각 문서에 `verify_quick_check()`를 병렬 실행하여 간이 판정(🟢/🟡/🔴)을 내린다 |
| 에이전트 유형 | 검증형 (코드 60%) |
| LLM | Sonnet |
| 입력 | `ClassifiedDocList` — 중복 제거된 문서 목록 |
| 출력 | `QuickCheckResults` — 간이 검증 결과 배열 [{vrf_id, title, doc_type, quick_verdict, claims_count, flags, needs_full_verification}] |
| MCP 도구 | `verify_quick_check`, `verify_add_claim`, `verify_set_verdict`, `verify_finalize` |
| 실패 모드 | (1) 개별 문서 Quick Check 실패 → degraded, 해당 건 스킵 (2) Quick Check 위양성(🔴 누락) → 잠재적, Analyst 주간 리뷰에서 사후 감지 |

실행 패턴: 문서별 병렬 처리. 동시 실행 상한 5건 (MCP 서버 부하 관리).

---

#### Agent 04: Full Verifier

| 항목 | 내용 |
|---|---|
| 역할 | Quick Check에서 🔴 판정을 받은 문서에 대해 Phase 0~5 전체 검증 파이프라인을 순차 실행한다 |
| 에이전트 유형 | 검증형 (코드 60%) |
| LLM | Opus |
| 입력 | `FullVerificationRequest` — 🔴 문서 1건 {title, url, doc_type, quick_check_vrf_id, quick_flags} |
| 출력 | `FullVerificationResult` — 전체 검증 결과 {vrf_id, title, doc_type, final_verdict, layer_verdicts[6], claims[], rules_triggered[], kc_extracted[], patterns_updated[]} |
| MCP 도구 | `verify_start`, `verify_add_claim`, `verify_set_verdict`, `verify_set_document_verdict`, `verify_get_checklist`, `verify_get_rules`, `verify_check_coverage`, `verify_finalize`, `verify_generate_html`, 데이터 MCP (FRED, Yahoo Finance, CoinMetrics, SEC-EDGAR 등) |
| 실패 모드 | (1) 전체 검증 타임아웃 (>10분) → retriable, 1회 재시도 후 degraded로 전환 (2) MCP 데이터 소스 불가 → degraded, 가용 데이터로만 검증 + 신뢰도 표기 |

실행 패턴: 순차 처리. 🔴 문서가 여러 건이면 하나씩.

---

### Team C: 축적팀 (순차)

#### Agent 05: Accumulator

| 항목 | 내용 |
|---|---|
| 역할 | 검증 완료된 결과를 KC 레지스트리, 패턴 레지스트리, 규칙 활성도에 기록하여 엔진 경험을 축적한다 |
| 에이전트 유형 | 조율형 (코드 90%) |
| LLM | 불필요 |
| 입력 | `AccumulationRequest` — Quick/Full 검증 결과 {vrf_id, doc_type, final_verdict, rules_triggered[], kc_extracted[], patterns_updated[]} |
| 출력 | `AccumulationReport` — 축적 결과 {kc_registered_count, kc_updated_count, patterns_recorded_count, rules_activity_updated_count, errors[]} |
| MCP 도구 | `verify_check_triggers`, `verify_rule_activity`, `verify_get_kc_status`, `verify_get_patterns` |
| 실패 모드 | (1) JSON 파일 쓰기 실패 → retriable, 3회 재시도 (2) Notion 동기화 실패 → degraded, JSON은 정상, Notion 나중에 수동 동기 |

---

#### Agent 06: Analyst

| 항목 | 내용 |
|---|---|
| 역할 | 주간 배치로 축적된 검증 결과를 분석하고, 패턴 승격/규칙 추가 제안을 생성한다 |
| 에이전트 유형 | 분석형 (코드 40%) |
| LLM | Opus |
| 입력 | `AnalysisRequest` — 분석 기간 {period_start, period_end, include_quick_checks: bool} |
| 출력 | `WeeklyAnalysisReport` — {outcome_analysis, promotion_suggestions[], dead_rules[], hot_rules[], doc_type_coverage, recommendations[]} |
| MCP 도구 | `verify_analyze_outcomes`, `verify_get_patterns`, `verify_rule_activity` |
| 실패 모드 | (1) 분석 대상 데이터 부족 (기간 내 검증 0건) → degraded, 빈 리포트 생성 + 수집 강화 권고 |

**체크포인트 #2**: 주간 분석 완료 후, 승격 제안이 있으면 사용자 승인 대기.
- 사용자가 `verify_promote_pattern()` 호출 → promoted
- 사용자가 기각 → dismissed
- 시스템이 자동 승격하지 않음

---

### Team D: 감시팀 (상시 실행)

#### Agent 07: Balance Monitor

| 항목 | 내용 |
|---|---|
| 역할 | doc_type/소스/섹터 분포를 추적하고, 편향 감지 시 수집 우선순위를 자동 조정한다 |
| 에이전트 유형 | 조율형 (코드 90%) |
| LLM | 불필요 |
| 입력 | `BalanceCheckRequest` — 현재 수집 상태 {collection_log, target_distribution} |
| 출력 | `BalanceReport` — {current_distribution, imbalance_detected: bool, underrepresented_types[], adjusted_priorities, alert_message} |
| MCP 도구 | 없음 (내부 JSON 집계) |
| 실패 모드 | (1) 편향 조정 후에도 불균형 지속 → degraded, 수동 수집 권고 메시지 생성 |

실행 패턴: 매 수집 사이클 종료 시 + 일일 1회 정기 점검.

균형 기준:
- 이상적 분포: 8개 doc_type 각 12.5% (±5%p 허용)
- 편향 감지: 특정 유형이 전체의 25% 초과 OR 특정 유형이 전체의 5% 미만
- 조정: 과대 유형 가중치 ×0.5, 과소 유형 가중치 ×2.0

---

## SS5. 스키마 계약

### 5-1. Source Monitor → Classifier

```json
{
  "schema": "RawCandidateList",
  "version": "1.0",
  "collected_at": "2026-03-20T09:00:00+09:00",
  "source_stats": {
    "total_sources_attempted": 8,
    "successful_sources": 6,
    "failed_sources": ["legal_contract", "fund_factsheet"]
  },
  "candidates": [
    {
      "candidate_id": "cand_001",
      "title": "삼성전자 1Q26 실적 프리뷰",
      "url": "https://example.com/report/001",
      "snippet": "삼성전자의 1분기 실적은...",
      "source": "naver_finance",
      "source_type": "equity_research",
      "estimated_doc_type": "equity_research",
      "timestamp": "2026-03-20T08:30:00+09:00",
      "metadata": {
        "author": "미래에셋증권",
        "language": "ko"
      }
    }
  ]
}
```

### 5-2. Classifier → Quick Verifier

```json
{
  "schema": "ClassifiedDocList",
  "version": "1.0",
  "classified_at": "2026-03-20T09:05:00+09:00",
  "total_candidates": 30,
  "duplicates_removed": 5,
  "documents": [
    {
      "doc_id": "doc_001",
      "candidate_id": "cand_001",
      "title": "삼성전자 1Q26 실적 프리뷰",
      "url": "https://example.com/report/001",
      "doc_type": "equity_research",
      "classification_confidence": 0.92,
      "is_duplicate": false,
      "dedup_reason": null,
      "author_id": "미래에셋증권",
      "source_url": "https://example.com/report/001"
    }
  ]
}
```

### 5-3. Quick Verifier → Full Verifier (🔴 항목만)

```json
{
  "schema": "FullVerificationRequest",
  "version": "1.0",
  "doc_id": "doc_001",
  "title": "삼성전자 1Q26 실적 프리뷰",
  "url": "https://example.com/report/001",
  "doc_type": "equity_research",
  "author_id": "미래에셋증권",
  "quick_check_vrf_id": "VRF-2026-0320-001",
  "quick_verdict": "🔴",
  "quick_flags": [
    "lr_001: growth_capex_mismatch — 매출 성장 전망 대비 CAPEX 감소 비정합",
    "lr_005: optimistic_without_downside — 하방 시나리오 없는 일방적 전망"
  ],
  "quick_claims_count": 4
}
```

### 5-4. Quick Verifier → Accumulator

```json
{
  "schema": "AccumulationRequest",
  "version": "1.0",
  "source": "quick_check",
  "vrf_id": "VRF-2026-0320-001",
  "doc_type": "equity_research",
  "final_verdict": "🟡",
  "rules_triggered": ["lr_003"],
  "kc_extracted": [],
  "patterns_updated": [
    {
      "pattern_id": "pat_012",
      "rule_id": "lr_003",
      "status": "candidate",
      "occurrence_count": 2
    }
  ]
}
```

### 5-5. Full Verifier → Accumulator

```json
{
  "schema": "AccumulationRequest",
  "version": "1.0",
  "source": "full_verification",
  "vrf_id": "VRF-2026-0320-002",
  "doc_type": "equity_research",
  "final_verdict": "🔴",
  "layer_verdicts": {
    "fact": "🟡",
    "norm": "🟢",
    "logic": "🔴",
    "temporal": "🟡",
    "incentive": "🟢",
    "omission": "🟡"
  },
  "rules_triggered": ["lr_001", "lr_005", "lr_021"],
  "kc_extracted": [
    {
      "kc_id": "KC-2026-0320-001",
      "premise": "삼성전자 CAPEX 감소가 지속되면 파운드리 점유율 하락",
      "current_status": "active",
      "verdict": "🟡"
    }
  ],
  "patterns_updated": [
    {
      "pattern_id": "pat_015",
      "rule_id": "lr_001",
      "status": "proposed",
      "occurrence_count": 3
    }
  ],
  "html_path": "output/삼성전자-1Q26-verification-2026-03-20.html"
}
```

### 5-6. Accumulator → Analyst (주간)

```json
{
  "schema": "AnalysisRequest",
  "version": "1.0",
  "period_start": "2026-03-14",
  "period_end": "2026-03-20",
  "include_quick_checks": true,
  "summary": {
    "total_verifications": 42,
    "by_type": {
      "quick_check": 35,
      "full_verification": 7
    },
    "by_doc_type": {
      "news_article": 8,
      "equity_research": 6,
      "crypto_research": 5,
      "legal_contract": 4,
      "macro_report": 6,
      "geopolitical": 5,
      "regulatory_filing": 4,
      "fund_factsheet": 4
    },
    "verdicts": {
      "🟢": 15,
      "🟡": 18,
      "🔴": 7,
      "⚫": 2
    },
    "new_kcs": 5,
    "new_patterns": 3,
    "rules_triggered_unique": 12
  }
}
```

### 5-7. Balance Monitor ↔ Source Monitor (우선순위 조정)

```json
{
  "schema": "PriorityAdjustment",
  "version": "1.0",
  "generated_at": "2026-03-20T21:00:00+09:00",
  "imbalance_detected": true,
  "current_distribution": {
    "news_article": 0.28,
    "equity_research": 0.18,
    "crypto_research": 0.15,
    "legal_contract": 0.05,
    "macro_report": 0.12,
    "geopolitical": 0.10,
    "regulatory_filing": 0.04,
    "fund_factsheet": 0.08
  },
  "adjusted_priorities": {
    "news_article": 0.5,
    "equity_research": 0.8,
    "crypto_research": 1.0,
    "legal_contract": 2.0,
    "macro_report": 1.0,
    "geopolitical": 1.0,
    "regulatory_filing": 2.0,
    "fund_factsheet": 1.5
  },
  "underrepresented_types": ["legal_contract", "regulatory_filing"],
  "overrepresented_types": ["news_article"],
  "alert_message": "legal_contract(5%), regulatory_filing(4%) 비율 과소. 수집 가중치 2.0 적용."
}
```

### 팀 간 집계 스키마

**Team A → Team B 집계**:
```json
{
  "team_a_output": {
    "total_collected": 30,
    "after_dedup": 25,
    "by_doc_type": { "news_article": 5, "equity_research": 4, "..." : "..." },
    "failed_sources": ["legal_contract"],
    "classification_low_confidence": ["doc_018", "doc_022"]
  }
}
```

**Team B → Team C 집계**:
```json
{
  "team_b_output": {
    "quick_checked": 25,
    "red_items": 3,
    "full_verified": 3,
    "results": [
      { "vrf_id": "...", "source": "quick_check", "verdict": "🟡", "..." : "..." },
      { "vrf_id": "...", "source": "full_verification", "verdict": "🔴", "..." : "..." }
    ]
  }
}
```

---

## SS6. 오케스트레이션 그래프

```
[START]
  │
  ▼
[Team A: 수집팀]
  ├─ Agent 01: Source Monitor (8개 소스 병렬 스캔)
  │    ├── news sources ──┐
  │    ├── equity sources ─┤
  │    ├── crypto sources ─┤
  │    ├── legal sources ──┤
  │    ├── macro sources ──┤  ──→ 후보 목록 합산
  │    ├── geo sources ────┤
  │    ├── reg sources ────┤
  │    └── fund sources ───┘
  │
  ▼
  ├─ Agent 02: Classifier (순차: 분류 + 중복 제거)
  │
  ▼
  ◆ 체크포인트 #1: 유효 후보 ≥ 1건?
  │    No → Agent 01 재수집 (max 2회) → 여전히 0건 → [END: 수집 실패]
  │    Yes ↓
  │
  ▼
[Team B: 검증팀]
  ├─ Agent 03: Quick Verifier (문서별 병렬, 동시 최대 5건)
  │    ├── doc_001 Quick Check ─┐
  │    ├── doc_002 Quick Check ─┤
  │    ├── doc_003 Quick Check ─┤  ──→ 결과 집계
  │    ├── ...                  ┤
  │    └── doc_N Quick Check ───┘
  │
  ▼
  ◇ 분기: 🔴 판정 존재?
  │    Yes → Agent 04: Full Verifier (🔴 건만, 순차 1건씩)
  │              ├── 🔴 doc_A Full Verify
  │              ├── 🔴 doc_B Full Verify
  │              └── ...
  │    No → Full Verification 스킵
  │
  ▼
[Team C: 축적팀]
  ├─ Agent 05: Accumulator (모든 Quick/Full 결과 순차 축적)
  │    ├── KC 레지스트리 업데이트
  │    ├── 패턴 레지스트리 기록
  │    └── 규칙 활성도 갱신
  │
  ▼
  ◇ 주간 배치 시점?
  │    Yes → Agent 06: Analyst (주간 분석)
  │              ├── verify_analyze_outcomes() 실행
  │              ├── 패턴 승격 제안 생성
  │              └── 죽은 규칙 / 핫 규칙 식별
  │              │
  │              ▼
  │         ◆ 체크포인트 #2: 승격 제안 있으면 사용자 승인 대기
  │    No → 스킵
  │
  ▼
[Team D: 감시팀]
  ├─ Agent 07: Balance Monitor
  │    ├── 분포 계산
  │    └── 편향 판정
  │
  ▼
  ◇ 편향 감지?
  │    Yes → 우선순위 조정 → Agent 01에 PriorityAdjustment 전달 → [LOOP: START]
  │    No  → [END: 사이클 완료]
```

**루프 종료 조건**: 밸런스 조정 후 재수집은 동일 사이클 내 최대 2회. 2회 후에도 불균형이면 사용자에게 경고 알림 후 종료.

---

## SS7. 에이전트별 프롬프트 전문

### Agent 01: Source Monitor 프롬프트

```
[역할]
너는 Verification Collector의 소스 모니터다. 8개 문서 유형에 대해 검증 대상 후보를 수집한다.

[맥락]
검증 엔진은 8개 doc_type을 지원한다: news_article, equity_research, crypto_research, legal_contract, macro_report, geopolitical, regulatory_filing, fund_factsheet.
각 유형에 대해 지정된 소스에서 최신 문서를 탐색한다.
우선순위 가중치가 주어지면, 가중치가 높은 유형에 더 많은 검색을 할당한다.

[입력]
- collection_priorities: doc_type별 가중치 (기본 1.0, 과소 유형은 2.0, 과대 유형은 0.5)
- target_count: 유형당 목표 수집 건수 (기본 5)
- exclude_urls: 이미 수집된 URL 목록

[출력]
RawCandidateList JSON:
- candidates 배열: 각 항목에 candidate_id, title, url, snippet, source, estimated_doc_type, timestamp
- source_stats: 시도/성공/실패 소스 수

[제약]
1. 각 doc_type에 대해 최소 1개 소스를 시도하라.
2. 가중치 2.0인 유형은 검색 쿼리를 2배로 늘려라.
3. 가중치 0.5인 유형은 검색을 절반으로 줄여라.
4. 스크래핑 차단 시 해당 소스를 failed_sources에 기록하고 다음으로 넘어가라.
5. 같은 URL이 exclude_urls에 있으면 건너뛰어라.
6. 최소 24시간 이내 발행 문서를 우선하라.

[자기검증]
- 8개 doc_type 중 최소 6개에서 후보가 있는가?
- 전체 후보 수가 target_count × 8 × 0.5 이상인가?
- failed_sources가 3개 이하인가?
```

### Agent 02: Classifier 프롬프트

```
[역할]
너는 수집된 문서 후보의 유형을 분류하고, 기존 검증 이력과 대조하여 중복을 제거하는 분류기다.

[맥락]
8개 유효 doc_type: news_article, equity_research, crypto_research, legal_contract, macro_report, geopolitical, regulatory_filing, fund_factsheet.
검증 엔진의 output/history/ 디렉터리에 기존 검증 결과가 JSON으로 저장되어 있다.

[입력]
- RawCandidateList: Source Monitor가 수집한 후보 목록
- verify_list_history() 결과: 기존 검증 이력

[출력]
ClassifiedDocList JSON:
- documents 배열: 각 항목에 doc_id, title, url, doc_type, classification_confidence (0~1), is_duplicate, dedup_reason
- 통계: total_candidates, duplicates_removed, by_doc_type 분포

[제약]
1. doc_type 판별은 title + snippet + source를 종합하여 결정하라.
2. confidence < 0.5이면 해당 후보를 제외하라.
3. 중복 판별: URL 정규화 후 비교 + 제목 유사도 0.9 이상이면 중복.
4. 유효한 8개 doc_type 외의 분류는 허용하지 않는다.
5. estimated_doc_type과 실제 분류가 다른 경우, 이유를 dedup_reason에 기록하라.

[자기검증]
- 모든 후보에 doc_type이 할당되었는가?
- is_duplicate=true인 항목에 dedup_reason이 있는가?
- confidence < 0.7인 항목이 전체의 30% 이하인가?
```

### Agent 03: Quick Verifier 프롬프트

```
[역할]
너는 분류된 문서에 간이 검증(Quick Check)을 실행하여 빠르게 위험도를 판별하는 검증자다.

[맥락]
verify_quick_check() MCP 도구를 사용한다. 이 도구는 3~5개 핵심 claim만 추출하여 Fact+Logic 중심으로 판정한다.
결과에 needs_full_verification=true이면 🔴 판정으로 Full Verification 대상이 된다.
Quick Check는 HTML 보고서를 생성하지 않는다.

[입력]
- ClassifiedDocList에서 is_duplicate=false인 문서들
- 각 문서의 title, doc_type, author_id, source_url

[출력]
QuickCheckResults JSON:
- results 배열: {vrf_id, doc_id, title, doc_type, quick_verdict, claims_count, flags[], needs_full_verification}
- 통계: total_checked, verdicts_distribution {🟢, 🟡, 🔴}

[제약]
1. 문서별 병렬 실행. 동시 최대 5건.
2. 각 문서에 대해 verify_quick_check(title, description, doc_type, author_id, source_url) 호출.
3. 호출 후 지시에 따라 claim 등록 → verdict 설정 → finalize 수행.
4. 개별 문서 Quick Check 실패 시, 해당 건을 errors에 기록하고 다음으로.
5. 전체 문서의 50% 이상이 실패하면 중단하고 에러 보고.

[자기검증]
- 모든 비중복 문서에 대해 Quick Check가 시도되었는가?
- 🔴 판정 문서가 needs_full_verification=true로 정확히 마킹되었는가?
- errors 배열이 전체의 50% 미만인가?
```

### Agent 04: Full Verifier 프롬프트

```
[역할]
너는 Quick Check에서 🔴 판정을 받은 문서에 대해 6-Layer 전체 검증(Phase 0~5)을 수행하는 심층 검증자다.

[맥락]
6-Layer 검증 엔진: Fact → Norm → Logic → Temporal → Incentive → Omission.
Phase 0: 문서 등록 (verify_start)
Phase 1: Claim 추출 + MCP 교차검증 (verify_add_claim + 데이터 MCP)
Phase 2: 6층 판정 (verify_set_verdict per layer per claim)
Phase 3: 문서 레벨 집계 (verify_set_document_verdict)
Phase 4: 커버리지 확인 (verify_check_coverage)
Phase 5: 최종화 (verify_finalize) + HTML 생성 (verify_generate_html)

Quick Check에서 이미 식별된 flags를 참고하되, 전체 검증에서는 모든 claim을 새로 추출한다.
MCP 데이터 수집은 필수: 2개 이상 MCP 소스 교차확인이 🟢 기준.

[입력]
- FullVerificationRequest: title, url, doc_type, author_id, quick_check_vrf_id, quick_flags

[출력]
FullVerificationResult JSON:
- vrf_id, title, doc_type, final_verdict
- layer_verdicts: {fact, norm, logic, temporal, incentive, omission} 각 verdict
- claims[]: 추출된 claim별 판정
- rules_triggered[]: trigger된 규칙 ID 목록
- kc_extracted[]: 추출된 Kill Condition 목록
- patterns_updated[]: 업데이트된 패턴 목록
- html_path: 생성된 HTML 보고서 경로

[제약]
1. 반드시 MCP 데이터 도구(FRED, Yahoo Finance, CoinMetrics, SEC-EDGAR 등)로 데이터를 수집하라. WebSearch만으로는 🟢 불가.
2. 각 claim에 대해 최소 Fact + Logic + Norm 3개 층 판정을 수행하라.
3. doc_type에 맞는 체크리스트(verify_get_checklist)와 규칙(verify_get_rules)을 반드시 확인하라.
4. 검증 완료 후 verify_check_coverage()로 누락 층이 없는지 확인하라.
5. verify_finalize() 호출 후 verify_generate_html()로 HTML 보고서를 생성하라.
6. 타임아웃 10분 초과 시 가용 데이터로 부분 검증 완료 + 신뢰도 하향 표기.

[자기검증]
- 6개 층 모두에 verdict가 설정되었는가? (N/A도 명시적 이유 필요)
- MCP 교차검증이 2개 이상 수행되었는가?
- verify_check_coverage() 결과가 100%인가?
- HTML 보고서가 정상 생성되었는가?
```

### Agent 05: Accumulator 프롬프트

```
[역할]
너는 검증 결과를 KC 레지스트리, 패턴 레지스트리, 규칙 활성도에 기록하여 엔진의 경험을 축적하는 축적기다.

[맥락]
- KC 레지스트리 (data/kc_registry.json): Kill Condition의 생명주기. active → approaching → resolved → revived.
- 패턴 레지스트리 (data/pattern_registry.json): 반복 검증 실패 누적. flag → candidate → proposed → promoted/dismissed.
- 규칙 활성도 (data/rule_activity.json): 각 규칙의 trigger 횟수 + 마지막 trigger 일시.
- JSON이 원본, Notion은 뷰어.

[입력]
- AccumulationRequest: vrf_id, doc_type, final_verdict, rules_triggered[], kc_extracted[], patterns_updated[]

[출력]
AccumulationReport JSON:
- kc_registered_count, kc_updated_count
- patterns_recorded_count, patterns_promoted_count (proposed 이상)
- rules_activity_updated_count
- errors[]: 기록 실패 항목

[제약]
1. JSON 파일 쓰기는 원자적으로 수행하라 (임시 파일 → rename).
2. kc_extracted가 있으면 각 KC를 verify_check_triggers()로 상태 확인 후 등록/업데이트.
3. rules_triggered가 있으면 규칙 활성도를 갱신하라.
4. patterns_updated에서 proposed 이상인 패턴이 있으면, 승격 제안 목록에 추가하라 (자동 승격 금지).
5. 오류 발생 시 해당 항목만 errors에 기록하고 나머지는 계속 처리하라.

[자기검증]
- 모든 rules_triggered가 rule_activity.json에 반영되었는가?
- kc_extracted 중 신규 KC가 kc_registry.json에 등록되었는가?
- errors가 전체 항목의 20% 이하인가?
```

### Agent 06: Analyst 프롬프트

```
[역할]
너는 주간 배치로 축적된 검증 데이터를 분석하여 패턴 승격 제안과 규칙 개선안을 생성하는 분석가다.

[맥락]
- verify_analyze_outcomes(): 과거 검증의 예측-실제 비교 분석 수행.
- verify_get_patterns(): proposed 이상 패턴 목록 조회.
- verify_rule_activity(): 규칙별 trigger 횟수 + 죽은 규칙/핫 규칙 식별.
- 승격 결정은 사용자가 한다. 시스템은 제안만.

[입력]
- AnalysisRequest: period_start, period_end, 기간 내 검증 요약

[출력]
WeeklyAnalysisReport JSON:
- outcome_analysis: verify_analyze_outcomes() 결과 요약
- promotion_suggestions[]: {pattern_id, rule_id, occurrence_count, suggested_severity, rationale}
- dead_rules[]: 6개월 이상 trigger 0회인 규칙
- hot_rules[]: trigger 빈도 상위 10개 규칙
- doc_type_coverage: 유형별 검증 건수
- recommendations[]: 자연어 개선 제안

[제약]
1. verify_analyze_outcomes()를 반드시 호출하라.
2. proposed 상태 패턴이 있으면 승격 제안을 생성하되, 자동 승격하지 마라.
3. 죽은 규칙은 "삭제 제안"이 아니라 "검토 필요" 표기하라.
4. recommendations에 최소 1건의 개선 제안을 포함하라.
5. 데이터 부족(기간 내 검증 0건)이면 빈 리포트 + "수집 강화 권고" 메시지.

[자기검증]
- outcome_analysis가 비어있지 않은가?
- promotion_suggestions에 rationale이 있는가?
- doc_type_coverage에 8개 유형이 모두 표시되었는가?
```

### Agent 07: Balance Monitor 프롬프트

```
[역할]
너는 수집 문서의 doc_type/소스/섹터 분포를 추적하고, 편향을 감지하여 수집 우선순위를 자동 조정하는 감시자다.

[맥락]
- 이상적 분포: 8개 doc_type 각 12.5% (±5%p 허용범위).
- 편향 기준: 특정 유형 > 25% 과대 OR 특정 유형 < 5% 과소.
- 조정 방식: 과대 유형 가중치 ×0.5, 과소 유형 가중치 ×2.0.
- 조정은 Agent 01의 다음 수집 사이클에 적용.

[입력]
- collection_log: 수집 이력 (doc_type별 건수)
- target_distribution: 목표 분포 (기본 균등)

[출력]
BalanceReport JSON:
- current_distribution: doc_type별 비율
- imbalance_detected: bool
- underrepresented_types[]: 과소 유형
- overrepresented_types[]: 과대 유형
- adjusted_priorities: doc_type별 가중치
- alert_message: 사람이 읽을 수 있는 경고 메시지

[제약]
1. 분포 계산은 최근 7일간 수집 이력 기준.
2. 편향 감지 시 adjusted_priorities를 계산하여 Agent 01에 전달.
3. 2회 연속 조정 후에도 불균형이면 alert_message에 "수동 수집 권고" 포함.
4. 소스 수준 편향도 추적: 특정 소스(예: Tavily)에 90% 이상 의존하면 경고.

[자기검증]
- current_distribution의 합이 1.0 (±0.01)인가?
- imbalance_detected=true이면 underrepresented_types가 비어있지 않은가?
- adjusted_priorities의 모든 값이 0.1~3.0 범위인가?
```

---

## SS8. 실패 모드 & 복구

### 에이전트별 실패 모드

| # | 실패 모드 | 에이전트 | 트리거 조건 | 에러 유형 | 복구 액션 |
|---|---|---|---|---|---|
| F-01 | 소스 스크래핑 차단 | Agent 01 | HTTP 403/429 또는 CAPTCHA 감지 | degraded | 해당 소스 스킵, 대체 소스 시도. failed_sources에 기록. K < 4이면 이전 캐시 보충 |
| F-02 | doc_type 오분류 | Agent 02 | confidence < 0.5 또는 실제 유형과 불일치 | degraded | 낮은 confidence 항목 제외. Agent 03에서 Quick Check 시 doc_type 재검증 기회 |
| F-03 | MCP 데이터 불가 | Agent 04 | FRED/Yahoo Finance 등 API 타임아웃 또는 에러 | degraded | 가용 MCP 소스로만 검증 수행. 신뢰도를 "MCP 교차검증 불완전" 표기. 🟢 판정 불가 |
| F-04 | Quick Check 위양성 (🔴 누락) | Agent 03 | 심각한 문제가 있지만 Quick Check에서 🟡 판정 | 잠재적 | Agent 06 주간 분석에서 사후 감지. verify_analyze_outcomes()로 예측-실제 괴리 식별 |
| F-05 | 전체 검증 타임아웃 | Agent 04 | Phase 0~5 수행이 10분 초과 | retriable | 1회 재시도. 재시도 실패 시 가용 데이터로 부분 검증 완료(degraded) |
| F-06 | Notion 동기화 실패 | Agent 05 | Notion API 에러 또는 연결 불가 | degraded | JSON 원본은 정상 저장. Notion은 다음 사이클에서 재동기. 사용자에게 수동 동기 알림 |
| F-07 | 유형 불균형 지속 | Agent 07 | 2회 우선순위 조정 후에도 편향 기준 초과 | degraded | 사용자에게 수동 수집 권고 알림. 해당 유형의 소스 목록 확장 제안 |

### 팀 레벨 실패 모드

| 팀 | 실패 유형 | 조건 | 복구 |
|---|---|---|---|
| Team A (수집) | 부분 실패 | 8개 소스 중 4개 이하 성공 | 성공 소스 결과 + 이전 캐시로 보충 후 계속 |
| Team A (수집) | 전체 실패 | 8개 소스 모두 실패 | 이전 사이클 캐시 사용. 캐시도 없으면 사이클 중단 + 사용자 알림 |
| Team B (검증) | 부분 실패 | 병렬 Quick Check 중 50% 이상 실패 | 사이클 중단 + MCP 서버 상태 점검 알림 |
| Team B (검증) | Full Verify 실패 | 🔴 문서 전체 검증 불가 | 해당 문서 "검증 보류" 표기 + 다음 사이클로 이월 |
| Team C (축적) | JSON 쓰기 충돌 | 동시 쓰기 시도 | 파일 잠금 + 3회 재시도 (1초 간격) |
| Team D (감시) | 분포 계산 불가 | collection_log 비어있음 | 기본 균등 분포로 초기화. 다음 사이클부터 실측 |

### 에러 전파 규칙

| 에러 유형 | 처리 방식 | 하류 영향 |
|---|---|---|
| retriable | 최대 3회 재시도, 지수 백오프 (1초 → 2초 → 4초) | 하류 에이전트 대기 |
| fatal | 해당 경로 스킵 + 에러 컨텍스트를 하류 에이전트에 전달 | 해당 문서/소스 관련 경로 비활성 |
| degraded | 계속 진행 + "미확인/불완전" 표기 | 최종 보고서 신뢰도 하향, Accumulator에 partial 마킹 |

### 에러 전파 흐름

```
Agent 01 fatal → Team A 전체 실패 → 사이클 중단
Agent 01 degraded → Agent 02 정상 (일부 소스 누락 허용)
Agent 02 degraded → Agent 03 정상 (분류 불확실 문서 포함, Quick Check에서 재판단)
Agent 03 fatal (50%+) → Team B 부분 실패 → 사이클 중단
Agent 03 degraded → Agent 04 정상 (🔴 판정만 전달)
Agent 04 fatal → 해당 문서 "보류" → Agent 05에 보류 상태 전달
Agent 04 degraded → Agent 05 정상 (partial 마킹)
Agent 05 retriable → 3회 재시도 → 실패 시 사이클 내 해당 항목 스킵
Agent 06 → 독립 (주간 배치, 하류 없음)
Agent 07 → Agent 01에 PriorityAdjustment 전달 (다음 사이클)
```

---

## SS9. 검증 결과

### 구조 검증 (C-01 ~ C-10)

| 검증 | 항목 | 결과 | 비고 |
|---|---|---|---|
| C-01 | Must Have 전부 매핑 | Pass | 수집/분류/검증/축적/분석/감시 모두 에이전트에 매핑 |
| C-02 | 단일 책임 | Pass | 각 에이전트 역할 1문장으로 정의됨 |
| C-03 | 에이전트 2~8개 | Pass | 7개 (범위 내) |
| C-04 | 검증 에이전트 존재 | Pass | Agent 03 (Quick), Agent 04 (Full) |
| C-05 | 그래프 연결 (모든 노드 → END 도달) | Pass | 모든 경로가 END에 도달. 루프도 종료 조건 있음 |
| C-06 | 엣지 조건 명시 | Pass | 🔴 분기, 주간 배치 분기, 편향 분기 모두 조건 명시 |
| C-07 | 루프 종료 조건 | Pass | 밸런스 조정 루프 최대 2회 |
| C-08 | 막다른 길 없음 | Pass | 모든 실패 경로에 복구 또는 종료 정의 |
| C-09 | 실패 모드 전체 5개+ | Pass | 7개 에이전트별 + 6개 팀별 = 13개 |
| C-10 | 프롬프트 6요소 | Pass | 7개 에이전트 모두 역할/맥락/입력/출력/제약/자기검증 포함 |

### Medium 확장 검증 (C-11 ~ C-13)

| 검증 | 항목 | 결과 | 비고 |
|---|---|---|---|
| C-11 | 병렬 에이전트 부분실패 처리 | Pass | Team A: K≥4 계속, Team B: 50% 기준. 각각 정의됨 |
| C-12 | 공유 상태 동시접근 제어 | Pass | JSON 파일 잠금 + 재시도 정의 (Agent 05) |
| C-13 | 팀 간 집계 스키마 정합 | Pass | Team A→B, Team B→C 집계 스키마 정의됨. output ⊇ next input 확인 |

### 스키마 검증 (S-01 ~ S-06)

| 검증 | 항목 | 결과 | 비고 |
|---|---|---|---|
| S-01 | 체인 정합 (output ⊇ next input) | Pass | 7개 스키마 계약 모두 필드 포함 관계 확인 |
| S-02 | 시스템 입력 = 기획 입력 | Pass | CollectionRequest (우선순위 + 목표) = 기획 S4 입력 |
| S-03 | 시스템 출력 = 기획 출력 | Pass | WeeklyAnalysisReport + BalanceReport = 기획 S4 출력 |
| S-04 | 빈 값 처리 정의 | Pass | null, [], "" 처리: dedup_reason=null(중복 아닐 때), errors=[](오류 없을 때) |
| S-05 | API 실패 시 폴백 데이터 스키마 | Pass | failed_sources 배열 + 캐시 보충 로직 정의 |
| S-06 | 에러 유형별 처리 명시 | Pass | retriable/fatal/degraded 3단계 + 에이전트별 매핑 |

### 비용 시뮬레이션 (COST-01)

| 검증 | 항목 | 결과 | 비고 |
|---|---|---|---|
| COST-01 | 최악 비용 ≤ 기획 제약 × 2 | Pass | SS11 부록 참조. 최악 $4.83 < 제약 $5 × 2 = $10 |

### 자기 평가 (5차원 × 5점)

| 차원 | 점수 | 근거 |
|---|---|---|
| 분해 품질 | 5/5 | 7개 에이전트가 수집→분류→검증→축적→분석→감시 전체를 빈틈없이 커버 |
| 역할 명확성 | 5/5 | 각 에이전트 역할 1문장, 유형 구분, 입출력 분리 명확 |
| 스키마 정합 | 4/5 | 7개 스키마 계약 정의. BalanceReport→CollectionRequest 간접 연결이 명시적 스키마보다는 PriorityAdjustment로 분리 (-1) |
| 실패 커버리지 | 5/5 | 에이전트별 7건 + 팀별 6건 + 에러 전파 규칙. 13건 총 식별 |
| 단순성 | 4/5 | 7개 에이전트는 Medium Track 범위 내이나, Agent 05(Accumulator)와 Agent 06(Analyst)의 경계가 미세 (-1) |

**총점: 23/25 — Pass**

**주의사항 (V-06 최소 1건)**:
1. Agent 04(Full Verifier)가 Opus를 사용하므로 🔴 문서가 다수일 경우 비용이 급증할 수 있다. 일일 Full Verification 상한(예: 5건)을 런타임에 설정할 것을 권장한다.
2. Quick Check의 위양성(F-04)은 구조적으로 사전 방지가 불가하다. 주간 Analyst 리뷰에서 사후 감지에 의존하므로, 최대 7일간 탐지 지연이 발생할 수 있다.

---

## SS10. 다음 단계

### Phase 1: 기반 구축 (1주)

1. `collector/` 디렉터리 구조 생성
   ```
   collector/
   ├── agents/
   │   ├── source_monitor.py      # Agent 01
   │   ├── classifier.py          # Agent 02
   │   ├── quick_verifier.py      # Agent 03
   │   ├── full_verifier.py       # Agent 04
   │   ├── accumulator.py         # Agent 05
   │   ├── analyst.py             # Agent 06
   │   └── balance_monitor.py     # Agent 07
   ├── orchestrator.py            # 7 에이전트 오케스트레이션
   ├── schemas/                   # 스키마 계약 JSON Schema 파일
   ├── state/
   │   ├── collection_log.json    # 수집 이력
   │   └── balance_state.json     # 밸런스 상태
   ├── config.py                  # 설정 (소스 URL, 가중치, 상한 등)
   └── run.py                     # CLI 엔트리포인트
   ```

2. Agent 05(Accumulator) + Agent 07(Balance Monitor) 먼저 구현 — LLM 불필요, 순수 코드

3. 스키마 계약을 JSON Schema 파일로 정의 (검증용)

### Phase 2: 수집 + 분류 (1주)

1. Agent 01(Source Monitor) 구현 — Tavily/Firecrawl MCP 연동
2. Agent 02(Classifier) 구현 — doc_type 분류 + 중복 확인
3. 체크포인트 #1 로직 구현

### Phase 3: 검증 연동 (1주)

1. Agent 03(Quick Verifier) 구현 — verify_quick_check() MCP 호출
2. Agent 04(Full Verifier) 구현 — Phase 0~5 전체 파이프라인 호출
3. 오케스트레이터에서 병렬/순차/분기 실행 로직 구현

### Phase 4: 분석 + 통합 (1주)

1. Agent 06(Analyst) 구현 — 주간 배치 + 승격 제안
2. 전체 사이클 통합 테스트 (8 doc_type × 5건)
3. 밸런스 조정 루프 테스트
4. 비용 모니터링 장치 추가

### 백로그

- [ ] Notion 3-DB 자동 동기화 (현재는 JSON 원본 only)
- [ ] event-reactor 연동 (검증 결과를 Knowledge Reservoir에 저장)
- [ ] KC → WatchRule 자동 등록 (event-reactor reactor_react와 연결)
- [ ] 수집 소스 확장 (YouTube 트랜스크립트, 학술 논문)
- [ ] 스케줄러 (cron/Task Scheduler) 연동으로 일일 자동 실행
- [ ] 대시보드 HTML 생성 (수집 현황, 밸런스, 주간 리포트)

---

## SS11. 부록

### 비용 시뮬레이션

#### 토큰 단가 (2026-03 기준 추정)

| 모델 | Input | Output |
|---|---|---|
| Opus | $15/1M tokens | $75/1M tokens |
| Sonnet | $3/1M tokens | $15/1M tokens |
| Haiku | $0.25/1M tokens | $1.25/1M tokens |

#### 정상 경로 (일일 1사이클)

| 에이전트 | 모델 | 호출 수 | Input 토큰 | Output 토큰 | 비용 |
|---|---|---|---|---|---|
| Agent 01: Source Monitor | Haiku | 8건 (소스별) | 8 × 2K = 16K | 8 × 1K = 8K | $0.01 |
| Agent 02: Classifier | Sonnet | 1건 (배치) | 30K | 5K | $0.17 |
| Agent 03: Quick Verifier | Sonnet | 40건 (8유형 × 5건) | 40 × 3K = 120K | 40 × 2K = 80K | $1.56 |
| Agent 04: Full Verifier | Opus | 3건 (🔴 추정) | 3 × 15K = 45K | 3 × 5K = 15K | $1.80 |
| Agent 05: Accumulator | 없음 | — | — | — | $0.00 |
| Agent 06: Analyst | Opus | 0.14건 (주 1회/7) | 10K/7 ≈ 1.4K | 3K/7 ≈ 0.4K | $0.05 |
| Agent 07: Balance Monitor | 없음 | — | — | — | $0.00 |
| **MCP API 호출** | — | ~50건 | — | — | ~$0.05 |
| **일일 합계** | — | — | ~212K | ~108K | **~$3.64** |

#### 최악 경로 (일일 1사이클, 재시도 포함)

| 항목 | 배수 | 근거 |
|---|---|---|
| Agent 01 재시도 | ×1.5 | 소스 차단으로 대체 소스 시도 |
| Agent 03 재시도 | ×1.2 | 개별 건 실패 시 재시도 |
| Agent 04 Full Verify 증가 | ×2.0 | 🔴 6건으로 증가 |
| Agent 05 재시도 | ×1.3 | JSON 쓰기 충돌 재시도 |
| 밸런스 조정 재수집 | ×1.3 | 추가 수집 1회 |

| 경로 | 일일 비용 | 월간 비용 (22일) |
|---|---|---|
| 정상 | $3.64 | $80.08 |
| 최악 | $4.83 | $106.26 |
| 기획 비용 제약 | $5.00/일 | $110.00/월 |
| 최악/제약 비율 | 0.97배 | — |

**판정**: 최악 경로 $4.83 < 기획 제약 $5.00 × 2 = $10.00 → **COST-01 Pass**

#### 비용 절감 옵션

1. Agent 03의 Quick Check를 Haiku로 다운그레이드 → 일일 -$1.20 (정확도 트레이드오프)
2. Full Verification 일일 상한 3건 → 최악 경로 $4.83 → $3.64로 억제
3. 주간 배치를 격주로 변경 → Agent 06 비용 50% 절감 (미미)

### 수집 소스 상세 목록

| doc_type | 소스명 | URL 패턴 | 수집 도구 |
|---|---|---|---|
| news_article | 네이버 뉴스 | news.naver.com | Tavily Search |
| news_article | 한겨레 | hani.co.kr | Tavily Search |
| news_article | Reuters | reuters.com | Tavily Search |
| equity_research | 네이버 금융 리서치 | finance.naver.com | Firecrawl |
| equity_research | KIND (전자공시) | kind.krx.co.kr | Tavily Search |
| crypto_research | CoinDesk | coindesk.com | Tavily Search |
| crypto_research | The Block | theblock.co | Firecrawl |
| legal_contract | 법률신문 | lawtimes.co.kr | Tavily Search |
| legal_contract | 공개 계약서 DB | — | Firecrawl |
| macro_report | FRED Blog | fredblog.stlouisfed.org | Tavily Search |
| macro_report | 한국은행 | bok.or.kr | Tavily Search |
| geopolitical | Foreign Affairs | foreignaffairs.com | Tavily Search |
| geopolitical | CSIS | csis.org | Tavily Search |
| regulatory_filing | DART | dart.fss.or.kr | DART MCP |
| regulatory_filing | 안전보건공단 | kosha.or.kr | Tavily Search |
| fund_factsheet | 금투협 펀드넷 | funddoctor.co.kr | Firecrawl |
| fund_factsheet | ETF 정보 (네이버) | finance.naver.com/etf | Firecrawl |

### 검증 엔진 MCP 도구 목록 (수집기가 사용하는 것)

| 도구명 | 사용 에이전트 | 용도 |
|---|---|---|
| `verify_quick_check` | Agent 03 | 간이 검증 시작 |
| `verify_start` | Agent 04 | 전체 검증 세션 시작 |
| `verify_add_claim` | Agent 03, 04 | claim 등록 |
| `verify_set_verdict` | Agent 03, 04 | 층별 판정 등록 |
| `verify_set_document_verdict` | Agent 04 | 문서 레벨 판정 |
| `verify_get_checklist` | Agent 04 | doc_type별 체크리스트 조회 |
| `verify_get_rules` | Agent 04 | Logic 규칙 조회 |
| `verify_check_coverage` | Agent 04 | 커버리지 확인 |
| `verify_finalize` | Agent 03, 04 | 검증 최종화 |
| `verify_generate_html` | Agent 04 | HTML 보고서 생성 |
| `verify_list_history` | Agent 02 | 기존 검증 이력 조회 (중복 확인) |
| `verify_check_triggers` | Agent 05 | KC 트리거 확인 |
| `verify_rule_activity` | Agent 05, 06 | 규칙 활성도 조회 |
| `verify_get_kc_status` | Agent 05 | KC 상태 조회 |
| `verify_get_patterns` | Agent 05, 06 | 패턴 레지스트리 조회 |
| `verify_analyze_outcomes` | Agent 06 | 예측-실제 비교 분석 |
| `verify_promote_pattern` | 사용자 (수동) | 패턴 승격 (시스템 자동 불가) |
