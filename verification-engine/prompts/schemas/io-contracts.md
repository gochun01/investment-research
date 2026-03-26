# I/O 계약서 — 플레이스홀더 스키마 정의

> 이 문서는 `verify_get_prompt(phase)`가 각 프롬프트에 주입하는 플레이스홀더의 정확한 JSON 스키마를 정의한다.
> 서브에이전트는 이 스키마를 참조하여 입력 데이터를 해석하고, 출력을 MCP 도구에 등록한다.
>
> **출처**: `mcp_server.py` lines 544-600, `core/engine.py`, `core/models.py`, `core/layers/*.py`, `data/*.json`

---

## 입력 플레이스홀더 (verify_get_prompt가 주입)

### `{mcp_sources}`

- **주입 대상**: `fact_check.md`
- **출처**: `FactLayer.get_sources(doc_type)` — `core/layers/fact.py` `MCP_SOURCES` dict
- **타입**: `list[object]`
- **스키마**:

```json
[
  {"source": "DART", "coverage": "한국 기업 재무제표, 공시"},
  {"source": "SEC-EDGAR", "coverage": "미국 10-K, 10-Q"},
  {"source": "Yahoo Finance", "coverage": "주가, PER, PBR, 배당"},
  {"source": "FRED", "coverage": "금리, GDP, CPI"}
]
```

doc_type별 매핑:

| doc_type | sources |
|---|---|
| equity_research | DART, SEC-EDGAR, Yahoo Finance, FRED |
| crypto_research | CoinGecko, DeFiLlama, CoinMetrics, Etherscan |
| legal_contract | 내부 정합성 (외부 소스 불필요) |
| macro_report | FRED, Firecrawl/Tavily, Yahoo Finance |
| geopolitical | Tavily, FRED, Firecrawl |

미등록 doc_type은 `equity_research` 기본값 사용.

---

### `{checklist}`

- **주입 대상**: `norm_check.md`
- **출처**: `NormLayer.load_checklist(doc_type)` — `data/checklists.json` > `norm` > `{doc_type}`
- **타입**: `list[object]`
- **스키마**:

```json
[
  {
    "id": "nr_eq_001",
    "item": "risk_warning_exists",
    "description": "투자 리스크 경고 문구 존재",
    "regulation": "자본시장법 §178",
    "severity": "high",
    "scan_keywords": ["투자위험", "리스크", "원금손실", "투자 위험"]
  }
]
```

| 필드 | 타입 | 설명 |
|---|---|---|
| id | string | 체크 항목 ID (예: `nr_eq_001`) |
| item | string | 항목 코드명 |
| description | string | 검사 내용 |
| regulation | string | 근거 규정 |
| severity | `"high"` \| `"medium"` \| `"low"` | 중요도 |
| scan_keywords | string[] | 문서 내 탐색 키워드 |

---

### `{rules}`

- **주입 대상**: `logic_check.md`
- **출처**: `LogicLayer.load_rules(doc_type)` — `data/rules.json`에서 `{doc_type}` 전용 + `common` 합산
- **타입**: `list[object]`
- **스키마** (기본):

```json
[
  {
    "id": "lr_001",
    "name": "growth_capex_mismatch",
    "condition": "매출성장률 > 0% AND CAPEX성장률 < -10%",
    "flag": "매출 성장 전망 대비 CAPEX 감소 비정합",
    "severity": "high"
  }
]
```

**확장형** (context_branches 포함, 예: `lr_007_v2`):

```json
{
  "id": "lr_007_v2",
  "name": "mvrv_cycle_context",
  "condition": "MVRV > 3.0 AND 매수 추천",
  "flag": "MVRV 고평가 구간 매수 추천 — 사이클 컨텍스트별 판정 분기",
  "severity": "high",
  "replaces": "lr_007",
  "context_branches": [
    {"condition": "사이클 경과 > 18개월", "verdict": "🔴", "message": "..."},
    {"condition": "사이클 경과 < 6개월", "verdict": "🟡", "message": "..."}
  ],
  "data_sources": {
    "mvrv": "CoinMetrics CapMVRVCur",
    "cycle_start": "CoinGecko 365일 최저가 날짜",
    "cycle_months": "현재 날짜 - cycle_start (개월수)"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| id | string | Y | 규칙 ID |
| name | string | Y | 규칙 코드명 |
| condition | string | Y | 트리거 조건 (자연어) |
| flag | string | Y | 위반 시 플래그 메시지 |
| severity | `"low"` \| `"medium"` \| `"high"` \| `"critical"` | Y | 심각도 |
| replaces | string | N | 대체하는 이전 규칙 ID |
| context_branches | list[object] | N | 조건별 분기 판정 |
| data_sources | object | N | 검증에 필요한 MCP 데이터 소스 |

참고: `rules.json` 최상위에 `_fred_reference` 키가 있으나, `_`로 시작하므로 규칙 로딩에서 제외됨.

---

### `{omission_checklist}`

- **주입 대상**: `omission_check.md`
- **출처**: `OmissionLayer.load_checklist(sector_id)` — `data/checklists.json` > `omission` > `{sector_id}`
- **타입**: `list[object]`
- **스키마**:

```json
[
  {
    "id": "om_semi_001",
    "item": "수출규제",
    "impact": "critical",
    "keywords": ["수출규제", "export control", "entity list", "BIS", "대중 규제"]
  }
]
```

| 필드 | 타입 | 설명 |
|---|---|---|
| id | string | 항목 ID (예: `om_semi_001`) |
| item | string | 누락 점검 항목명 |
| impact | `"critical"` \| `"high"` \| `"medium"` | 영향도 |
| keywords | string[] | 문서 내 탐색 키워드 |

sector_id는 `engine.result.document.sector_id`에서 자동 결정. doc_type → sector_id 기본 매핑: macro_report→매크로, geopolitical→지정학, crypto_research→크립토, legal_contract→법률_계약.

---

### `{check_items}`

- **주입 대상**: `incentive_check.md`
- **출처**: `IncentiveLayer.get_checks(doc_type)` — `core/layers/incentive.py` `CHECK_ITEMS` dict
- **타입**: `list[string]`
- **스키마**:

```json
["증권사-주간사/인수인 관계", "자기매매 부서 보유현황", "애널리스트 개인 보유"]
```

doc_type별:

| doc_type | 체크 항목 |
|---|---|
| equity_research | 증권사-주간사/인수인 관계, 자기매매 부서 보유현황, 애널리스트 개인 보유 |
| crypto_research | 저자/발행처 토큰 보유, 프로젝트 후원/자문 관계, 에어드랍/보상 수령 여부 |
| legal_contract | 작성 주체의 계약 편향성, 일방에게 유리한 조항 구조 |
| macro_report | 발행기관의 경제 전망 편향, 저자의 기관 포지션과 전망 일치 여부 |
| geopolitical | 분석 기관의 정치적 입장/후원 관계, 정보 출처의 편향성 |

---

### `{fact_evidence}`

- **주입 대상**: `temporal_check.md`
- **출처**: Phase 2-1 Fact 결과에서 동적 구성 (`mcp_server.py` lines 580-590)
- **타입**: `object` — key는 claim_id
- **스키마**:

```json
{
  "c001": {
    "text": "Fed 기준금리 3.64%",
    "evidence": [
      {"source": "FRED", "query": "FEDFUNDS", "value": "3.50%", "retrieved_at": "2026-03-19T14:30:00"}
    ],
    "verdict": "🟡"
  },
  "c002": {
    "text": "비트코인 TVL $45B",
    "evidence": [
      {"source": "DeFiLlama", "query": "bitcoin TVL", "value": "$44.2B", "retrieved_at": "2026-03-19T14:31:00"}
    ],
    "verdict": "🟢"
  }
}
```

fact layer에서 evidence를 등록한 claim만 포함. evidence가 없는 claim은 누락됨.

| 필드 | 타입 | 설명 |
|---|---|---|
| `[claim_id].text` | string | claim 원문 |
| `[claim_id].evidence` | list[Evidence] | fact 검증 시 수집한 근거 |
| `[claim_id].verdict` | string | fact layer 판정 |

Evidence 객체:

| 필드 | 타입 | 설명 |
|---|---|---|
| source | string | MCP 소스명 (FRED, CoinGecko 등) |
| query | string | 조회에 사용한 쿼리/시리즈 ID |
| value | string | 조회 결과값 |
| retrieved_at | string | 조회 시각 (ISO 8601) |

---

### `{claims}`

- **주입 대상**: `logic_check.md`, `omission_check.md`
- **출처**: `[c.to_dict() for c in engine.result.claims]`
- **타입**: `list[Claim]`
- **스키마**:

```json
[
  {
    "claim_id": "c001",
    "text": "Fed 기준금리는 2026년 말까지 3.64%로 하락할 것",
    "claim_type": "예측",
    "evidence_type": "estimate",
    "location": "§3",
    "depends_on": [],
    "layers": {
      "fact": {"verdict": "🟡", "reason": "", "notes": "FRED 조회 결과 ±3%"},
      "logic": {"verdict": "", "reason": "", "notes": ""},
      "temporal": {"verdict": "", "reason": "", "notes": ""}
    }
  }
]
```

`layers` dict의 각 값은 `LayerVerdict.to_dict()` — 판정이 등록된 필드만 포함 (조건부 직렬화).

---

### `{missing_items}`

- **주입 대상**: `coverage_recheck.md`
- **출처**: `engine.check_coverage()` — 미실행 판정 목록
- **타입**: `list[string]`
- **스키마**:

```json
["c001/fact: 미실행", "c002/temporal: 미실행", "document/norm: 미실행"]
```

형식: `{claim_id 또는 "document"}/{layer}: 미실행`. verdict가 빈 문자열("")이고 N/A가 아닌 항목만 포함.

---

### `{result_json}`

- **주입 대상**: `self_audit.md`
- **출처**: `engine.get_result_dict()` → `VerificationResult.to_dict()`
- **타입**: `object`
- **스키마**:

```json
{
  "meta": {
    "id": "vrf_20260319_143052_123",
    "schema_version": "v2.0",
    "created_at": "2026-03-19T14:30:52.123456",
    "engine_version": "6layer_v2",
    "document": {
      "title": "반도체 산업 전망 2026H2",
      "document_type": "equity_research",
      "target_id": "005930",
      "sector_id": "반도체",
      "author_id": "홍길동",
      "institution_id": "XX증권",
      "source_url": "",
      "date_published": "2026-03-15",
      "date_accessed": "2026-03-19"
    },
    "previous_verification": ""
  },
  "document_level_verdicts": {
    "norm": {"verdict": "🟢", "reason": "", "notes": "...", "checklist_matched": [...], "checklist_missed": [...]},
    "incentive": {"verdict": "🟡", "reason": "", "notes": "...", "relationships_checked": [...], "disclosure_in_document": true},
    "omission": {"verdict": "🟡", "reason": "", "notes": "...", "bbj_breaks": [...]}
  },
  "claims": [
    {
      "claim_id": "c001",
      "text": "...",
      "claim_type": "수치주장",
      "evidence_type": "fact",
      "location": "§3",
      "depends_on": [],
      "layers": {
        "fact": {"verdict": "🟢", "notes": "...", "evidence": [...]},
        "logic": {"verdict": "🟢", "notes": "...", "rules_triggered": []},
        "temporal": {"verdict": "🟢", "notes": "...", "data_reference_date": "2026-03-15", "gap_days": 4, "material_change": false}
      }
    }
  ],
  "summary": {
    "layer_verdicts": {"fact": "🟢", "norm": "🟢", "logic": "🟡", "temporal": "🟢", "incentive": "🟡", "omission": "🟡"},
    "critical_flags": ["c003: MVRV 과열 구간 매수 추천"],
    "valid_until": "2026-04-19",
    "validity_condition": "FOMC 결정 전까지 유효",
    "invalidation_triggers": [{"event": "FOMC 금리 결정", "expected_date": "2026-05-07", "impact": "매크로 전제 재평가"}],
    "disclaimer": "본 결과는 법률/투자 자문이 아님. 검토 보조용"
  }
}
```

---

### `{coverage_report}`

- **주입 대상**: `self_audit.md`
- **출처**: `engine.get_coverage_report()`
- **타입**: `object`
- **스키마**:

```json
{
  "doc_type": "equity_research",
  "sector": "반도체",
  "coverage_level": "full",
  "dedicated_rules": 5,
  "common_rules": 3,
  "norm_checklist": 5,
  "omission_checklist": 8,
  "gaps": ["DCF 터미널 성장률 적정성 검증 규칙 없음", "PER 밴드/EV-EBITDA 비교 규칙 없음"],
  "self_audit_minimum": {
    "requires_limitation": true,
    "requires_coverage_assessment": true,
    "requires_improvement": true,
    "v06_note": "V-06 규칙: '문제 없음' 결론 금지. 최소 1개 한계 + 커버리지 평가 + 1개 개선 권고 필수"
  }
}
```

coverage_level 판정 기준:
- `"full"`: dedicated_rules >= 3 AND norm_checklist >= 3 AND omission_checklist >= 5
- `"partial"`: dedicated_rules >= 1 OR (norm_checklist >= 1 AND omission_checklist >= 1)
- `"minimal"`: 위 조건 모두 미충족

---

### `{data}`

- **주입 대상**: `prompts/SKILL.md` Phase 5 (HTML 보고서 생성)
- **출처**: `engine.get_result_dict()` — `{result_json}`과 동일 구조
- **참조**: 위 `{result_json}` 스키마 참조

---

### `{document}`

- **주입 대상**: `extract_claims.md`, `omission_check.md`
- **특수**: 자동 주입 시 안내 텍스트로 대체됨 (실제 문서 내용이 아님)
- **주입값**: `"[현재 대화 컨텍스트의 검증 대상 문서를 사용하라. 문서가 대화에 없으면 사용자에게 문서를 제공해달라고 요청하라.]"`

---

### 단순 문자열 플레이스홀더

| 플레이스홀더 | 주입 대상 | 출처 | 타입 |
|---|---|---|---|
| `{author}` | `incentive_check.md` | `engine.result.document.author_id` | string |
| `{institution}` | `incentive_check.md` | `engine.result.document.institution_id` | string |
| `{doc_type}` | 여러 프롬프트 | `engine.result.document.document_type` | string |

`{doc_type}` 가능한 값: `equity_research`, `crypto_research`, `legal_contract`, `fund_factsheet`, `regulatory_filing`, `macro_report`, `geopolitical`

---

## 출력 계약 (서브에이전트 -> MCP 도구)

### Phase 1 출력

- **도구**: `verify_add_claim(claim_id, text, claim_type, evidence_type, location, depends_on)`

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| claim_id | string | Y | 고유 ID (예: `c001`) |
| text | string | Y | claim 원문 |
| claim_type | string | Y | `수치주장` \| `인과주장` \| `예측` \| `사실진술` \| `의견` \| `조항` |
| evidence_type | string | N | `fact` \| `estimate` \| `opinion` (기본: `fact`) |
| location | string | N | 문서 내 위치 (예: `§3`) |
| depends_on | list[string] | N | 의존 claim ID (예: `["c001"]`) |

- **반환**:

```json
{
  "claim_id": "c001",
  "claim_type": "수치주장",
  "evidence_type": "fact",
  "applicable_layers": {"fact": true, "norm": false, "logic": true, "temporal": true, "incentive": false, "omission": false}
}
```

---

### Phase 2 Claim 레벨 출력

- **도구**: `verify_set_verdict(claim_id, layer, verdict, ...)`

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| claim_id | string | Y | claim ID |
| layer | string | Y | `fact` \| `norm` \| `logic` \| `temporal` \| `incentive` \| `omission` |
| verdict | string | Y | `🟢` \| `🟡` \| `🔴` \| `⚫` |
| notes | string | N | 판정 근거 서술 |
| evidence | list[object] | N | fact용: `[{source, query, value, retrieved_at}]` |
| checklist_matched | list[string] | N | norm용: 충족된 항목 ID |
| checklist_missed | list[string] | N | norm용: 미충족 항목 ID |
| rules_triggered | list[string] | N | logic용: 트리거된 규칙 ID |
| kc_extracted | list[object] | N | logic용: `[{kc_id, premise, current_status, verdict}]` |
| data_reference_date | string | N | temporal용: 데이터 기준일 (YYYY-MM-DD) |
| gap_days | int | N | temporal용: 기준일과 현재의 일수 차이 |
| material_change | bool | N | temporal용: 기간 내 중대 변화 여부 |
| valid_until | string | N | temporal용: 유효 기한 |
| bbj_breaks | list[object] | N | omission용: `[{break_text, in_document, verdict}]` |

- **반환**: `{"claim_id": "c001", "layer": "fact", "verdict": "🟢"}`

---

### Phase 2 Document 레벨 출력

- **도구**: `verify_set_document_verdict(layer, verdict, ...)`
- **layer**: `norm` \| `incentive` \| `omission` 만 가능

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| layer | string | Y | `norm` \| `incentive` \| `omission` |
| verdict | string | Y | `🟢` \| `🟡` \| `🔴` \| `⚫` |
| notes | string | N | 판정 근거 |
| checklist_matched | list[string] | N | 충족 항목 ID |
| checklist_missed | list[string] | N | 미충족 항목 ID |
| relationships_checked | list[string] | N | incentive용: 확인한 관계 |
| disclosure_in_document | bool | N | incentive용: 문서 내 공시 존재 여부 |
| bbj_breaks | list[object] | N | omission용: `[{break_text, in_document, verdict}]` |

- **반환**: `{"level": "document", "layer": "norm", "verdict": "🟢"}`

---

### Phase 2.5 출력

- **도구**: `verify_check_coverage()`
- **파라미터**: 없음
- **반환**:

```json
{
  "complete": false,
  "missing": ["c001/fact: 미실행", "document/norm: 미실행"],
  "message": "2개 항목 미실행"
}
```

complete가 `true`이면 Phase 3으로 진행. `false`이면 missing 항목을 처리 후 재호출.

---

### Phase 3+4 출력

- **도구**: `verify_finalize(valid_until, validity_condition, invalidation_triggers)`

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| valid_until | string | N | 유효 기한 (YYYY-MM-DD) |
| validity_condition | string | N | 유효 조건 (자연어) |
| invalidation_triggers | list[object] | N | 자동 무효화 트리거 |

invalidation_triggers 스키마:

```json
[{"event": "FOMC 금리 결정", "expected_date": "2026-05-07", "impact": "매크로 전제 재평가"}]
```

- **반환**:

```json
{
  "vrf_id": "vrf_20260319_143052_123",
  "status": "finalized",
  "storage": "Phase 5에서 HTML 보고서로 생성하세요",
  "summary": {
    "layer_verdicts": {"fact": "🟢", "norm": "🟢", "logic": "🟡", "temporal": "🟢", "incentive": "🟡", "omission": "🟡"},
    "critical_flags": [],
    "valid_until": "2026-04-19",
    "validity_condition": "FOMC 결정 전까지 유효",
    "claims_count": 5
  },
  "result_json": { ... }
}
```

`result_json`은 `{result_json}` 플레이스홀더와 동일한 `VerificationResult.to_dict()` 구조.
