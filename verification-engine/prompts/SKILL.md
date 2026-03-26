# 6-Layer 검증 실행 흐름

> 이 문서는 검증 파이프라인의 실행 순서, 도구 호출 시퀀스, 조건 분기를 정의한다.
> 원칙과 판정 체계는 CLAUDE.md를 참조하라.
> 각 Phase의 상세 지시는 해당 Phase 프롬프트(prompts/*.md)를 참조하라.
> 플레이스홀더 스키마는 schemas/io-contracts.md를 참조하라.

---

## 트리거

### 실행 트리거

```
사용자 발화:
  "검증해줘", "verify", "팩트체크", "6층 검증", "[문서명] 검증"
  → verify_orchestrator() → Phase 0 시작

자동 트리거:
  verify_finalize() 완료 → KC 등록 + 패턴 기록 + 규칙 활성도 (Green Zone)
  Self-Audit ⚠ 발견 → verify_log_issue() (Yellow Zone)

세션 시작:
  verify_scan() → KC/Watch/이슈 현황 알림 (Green Zone)
```

### 금지 트리거 (이 상황에서는 검증 엔진을 실행하면 안 됨)

```
├── 단순 뉴스 요약 ("이 기사 요약해줘")
│   → 검증이 아님. 요약 스킬로.
├── 시장 반응 분석 ("시장이 어떻게 반응하는지")
│   → reaction-monitor로. 검증 엔진은 문서 안의 팩트를 검증.
├── 투자 판단 ("이거 사야 해?")
│   → Red Zone. 검증은 판단이 아닌 대조.
├── 번역 ("이 리포트 번역해줘")
│   → 검증 대상이 아님.
└── 문서가 없는 질문 ("금리 전망은?")
    → 검증할 문서가 없음. 분석 스킬로.
```

### 우선순위 (동시 요청 시)

```
1순위: verify_scan()에서 KC triggered 알림 → 관련 검증 재실행
2순위: Watch 기한 도래 → 해당 검증의 invalidation_trigger 체크
3순위: 신규 문서 검증 요청
4순위: 이전 검증 HTML 재생성
```

---

## 파이프라인 순서 (불변)

```
Phase 0 → 1 → 1.5 → 2(①→②→③→④→⑤→⑥) → 2.5 → 3+4 → 4.5 → 5
```

이 순서를 건너뛰거나 바꾸지 마라. 각 Phase는 이전 Phase가 완료되어야 시작한다.

---

## Phase별 실행

### Phase 0: 문서 설정
1. 문서 유형 판별 (doc_type 기준표 → CLAUDE.md §8 참조)
2. `verify_start(title, doc_type, target_id, sector_id, author_id, institution_id)` 호출
3. 반환값 확인: fact_sources, norm_checklist_count, logic_rules_count, claim_type_matrix
4. warning 있으면 사용자에게 전달

### Phase 1: Claim 추출
1. `verify_get_prompt("extract_claims")` → 서브에이전트 프롬프트 로드
2. 문서에서 claim 추출 (서브에이전트 지시 따름)
3. `verify_add_claim(claim_id, text, claim_type, evidence_type, location, depends_on)` × N
4. 반환값의 applicable_layers 확인

### Phase 1.5: MCP 전수 수집 완료 선언
1. doc_type별 수집 기준에 따라 MCP 소스 전수 호출
   - equity_research: DART + SEC-EDGAR + Yahoo Finance + FRED
   - crypto_research: CoinGecko + DeFiLlama + CoinMetrics + Etherscan
   - legal_contract: 내부 정합성 스캔
   - macro_report: FRED(금리·GDP·CPI·스프레드) + Firecrawl/Tavily(IMF·OECD) + FEDTARMD
   - geopolitical: Tavily(뉴스) + FRED(에너지: DCOILWTICO, DHHNGSP)
2. 수집 완료 선언: "[MCP 수집 완료] {doc_type} 도메인 소스 전수 호출 완료. 판정을 시작합니다."
★ 수집 중 판정 금지 (CFA V(A) "합리적 근거" 원칙)

★ 병렬화 옵션 (대규모 검증 시):
  claim 20건+ 또는 도구 호출 30회+ 예상 시 Phase 1.5를 병렬 분리 가능.
  패턴 D(하이브리드): Phase 0~1은 메인 순차, 1.5만 서브 병렬, 2~5는 메인 순차.
  서브 분리 예: 서브A(가격 Yahoo Finance) + 서브B(매크로 FRED) + 서브C(공시 DART/SEC+뉴스)
  서브는 수치+출처만 요약 반환. 메인이 합산 후 Phase 2 관통 판정.
  6층 판정(Phase 2)은 절대 병렬 불가 — 층 간 관통 일관성이 핵심 가치.

### Phase 2: 6층 검증 (순서 고정)
각 층마다:
1. `verify_get_prompt(layer_name)` → 서브에이전트 프롬프트 로드
2. 서브에이전트 지시에 따라 검증 수행
3. 결과를 MCP 도구로 등록

| 순서 | 층 | 도구 | 레벨 |
|---|---|---|---|
| ① | fact | verify_set_verdict() | claim별 |
| ② | norm | verify_set_document_verdict() | 문서 전체 |
| ③ | logic | verify_set_verdict() | claim별 |
| ④ | temporal | verify_set_verdict() | claim별 |
| ⑤ | incentive | verify_set_document_verdict() | 문서 전체 |
| ⑥ | omission | verify_set_document_verdict() + verify_set_verdict() | 문서 + claim |

★ ① Fact에서 조회한 MCP 값은 ④ Temporal에서 재사용 ({fact_evidence} 자동 주입)

### Phase 2.5: 커버리지 체크
1. `verify_check_coverage()` 호출
2. complete=true → Phase 3+4로
3. complete=false → 미실행 항목 재실행 (최대 2회)
4. 2회 후에도 미완 → ⚫ NO BASIS 처리
★ [역할 전환] 감사자(Auditor)로 전환. Phase 2 결과를 독립적으로 점검.

### Phase 3+4: 마무리
1. `verify_get_prompt("finalize")` → 서브에이전트 프롬프트 로드
2. 유효기간, 유효 조건, 무효화 트리거 결정
3. `verify_finalize(valid_until, validity_condition, invalidation_triggers)` 호출
4. 반환된 result_json은 Phase 5에서 HTML 보고서 생성에 사용

### Phase 4.5: 자기 점검 + 사용자 승인

#### 4.5-1. 자기 점검
1. `verify_get_prompt("self_audit")` → 서브에이전트 프롬프트 로드
   ({result_json}, {coverage_report} 자동 주입)
2. 9개 항목 점검 수행 (V-06: "문제 없음" 금지)
3. 자기 점검 결과를 사용자에게 출력

#### 4.5-2. 검증 결과 요약 제시
자기 점검 결과와 함께 **검증 결과 요약**을 사용자에게 제시한다:
```
"[검증 결과 요약]
 - 6층 판정: ① Fact 🟢 ② Norm 🟢 ③ Logic 🟡 ④ Temporal 🟢 ⑤ Incentive 🟡 ⑥ Omission 🟡
 - Claim N건 중 🔴 X건, 🟡 Y건, 🟢 Z건
 - KC: [핵심 전제 요약]
 - 유효기간: ~YYYY-MM-DD
 - 자기 점검 지적사항: [요약]
 - result_json 저장됨: output/history/vrf_*.json

 수정이 필요하면 지시해주세요:
   1) '재검증해줘' → 특정 층 재실행
   2) '체크리스트 추가해줘' → 체크리스트 항목 추가
   3) '규칙 추가해줘' → 규칙 추가
   4) '판정 수정해줘' → 특정 claim/층 판정 변경
   5) '괜찮아' → HTML 보고서 생성으로 진행"
```

#### 4.5-3. 사용자 승인 대기
★ **사용자가 명시적으로 승인하기 전까지 Phase 5로 진행하지 마라.**
★ 사용자가 수정을 요청하면 수정 완료 후 다시 4.5-2로 돌아가 결과를 재제시한다.

| 사용자 응답 | 처리 |
|---|---|
| "괜찮아" / "진행해" | Phase 5로 진행 |
| "재검증해줘" | 해당 층 재실행 → verify_finalize() 재호출 → 4.5-2 재제시 |
| "체크리스트 추가해줘" | verify_add_checklist_item() → 해당 층 재실행 → 4.5-2 재제시 |
| "규칙 추가해줘" | verify_add_rule() → 해당 층 재실행 → 4.5-2 재제시 |
| "판정 수정해줘" | verify_set_verdict() 또는 verify_set_document_verdict() → verify_finalize() 재호출 → 4.5-2 재제시 |

수정 시 result_json은 **재저장**된다 (verify_finalize() 재호출 시 output/history/에 덮어쓰기).

### Phase 5: HTML 검증 보고서 생성 (사용자 승인 후에만)

★ **Phase 4.5에서 사용자가 "괜찮아"/"진행해"라고 답한 후에만 실행.**

#### 보고서 모드 선택

```
사용자 발화에 따라 보고서 모드를 선택한다:

"보고서 만들어" / "리포트" / "알아서"
  → 자율 모드 (prompts/adaptive-report.md 참조)
    Phase 5-A~F 실행. 데이터가 구조를 결정.

"정형 보고서" / "기존 양식으로" / "7섹션으로"
  → 정형 모드 (아래 5-1~5-5)
    기존 7+1 섹션 고정 구조.

미지정 시 기본값: 자율 모드
```
★ CSS 컴포넌트 카탈로그: `prompts/schemas/component-catalog.md`
★ HTML 골격 템플릿: `output/template-verification.html`
★ HTML 단일 파일 원칙: CSS 인라인, JS 최소, 외부 의존성 = Google Fonts만.

#### 5-1. 저장 경로 확인

1. 사용자에게 저장 경로를 질문:
   ```
   "HTML 보고서를 생성합니다. 저장 경로를 지정해주세요. (기본값: output/ 폴더)"
   ```
2. 사용자 응답을 기다린다. 응답 없이 경로를 가정하지 마라.

#### 5-2. Actionable Finding 생성

🟡 또는 🔴 판정이 나온 모든 claim에 대해 Finding Card를 생성한다.

**Finding Card 필수 필드 (9개):**

| 필드 | 내용 |
|---|---|
| finding_id | F-001 (순번) |
| layer | L1~L6 중 발견 층 |
| verdict | 🟡 또는 🔴 |
| location | 문서 내 위치 |
| original_text | 문제가 된 원문 |
| error_type | 6가지 중 택1 (아래 참조) |
| evidence | 판단 근거 (MCP 조회 결과, 체크리스트 ID) |
| fix_confidence | 확정 / 권장 / 경고만 |
| suggested_fix | 수정 제안 |

**오류 유형 6분류:**

| error_type | 층 | 내용 |
|---|---|---|
| factual_error | L1 | 수치·데이터 불일치 |
| missing_source | L1/L2 | 무출처 단정 |
| logic_gap | L3 | 인과 비약, 규칙 위반, KC 트리거 |
| temporal_outdated | L4 | 기준 시점 괴리 |
| disclosure_missing | L5 | 공시·면책·이해충돌 누락 |
| omission_gap | L6 | 필수 분석 항목 미언급 |

**수정 신뢰도 3단계:**

| 등급 | 조건 | 의뢰인 행동 |
|---|---|---|
| 확정 (Definitive) | 1차 소스 존재 + 값 대조 가능. LLM 추론 혼입 금지 (V-07) | 바로 수정 |
| 권장 (Recommended) | 부족한 점 특정 + 방향 제시 가능 | 방향 동의 시 보충 |
| 경고만 (Advisory) | 구조적 한계, 수정=관점 변경 | 참고용 |

**좋은 Finding Card 예시:**

```json
{
  "finding_id": "F-001",
  "layer": "L1 Fact",
  "verdict": "🔴",
  "location": "§3 밸류에이션, p.12",
  "original_text": "현재 PER 15.3배로 업종 평균 대비 저평가",
  "error_type": "factual_error",
  "evidence": "Yahoo Finance 조회 결과 PER 18.7배 (2026-03-24 기준). 보고서 수치와 3.4배 괴리 (22% 차이). 업종 평균 17.2배 대비 오히려 고평가",
  "fix_confidence": "확정",
  "suggested_fix": "PER 15.3배 → 18.7배로 수정. '저평가' 판단 근거 재검토 필요"
}
```
**왜 좋은가:** location 구체적, evidence에 MCP 조회 결과+수치+날짜+괴리율, fix_confidence "확정"의 근거 명확, suggested_fix가 구체적 수정안

**나쁜 Finding Card 예시 (하지 말 것):**

```json
{
  "finding_id": "F-001",
  "layer": "L1",
  "verdict": "🟡",
  "location": "",
  "original_text": "PER이 낮다",
  "error_type": "factual_error",
  "evidence": "PER이 좀 다른 것 같다",
  "fix_confidence": "권장",
  "suggested_fix": "PER을 확인해보세요"
}
```
**왜 나쁜가:** location 없음, evidence에 MCP 수치 없이 "좀 다른 것 같다"(V-01 위반), fix_confidence "권장"인데 "확정"이어야 할 사안, suggested_fix가 모호

**좋은 검증 결과 요약 예시:**

```
[검증 결과 요약]
- 6층 판정: ① Fact 🟡 ② Norm 🟢 ③ Logic 🔴 ④ Temporal 🟢 ⑤ Incentive 🟡 ⑥ Omission 🟡
- Claim 12건 중 🔴 2건, 🟡 4건, 🟢 5건, N/A 1건
- Critical: c003 매출 추정 10조 → DART 확인 8.2조 (22% 괴리), c007 인과 전제 붕괴
- KC: "금리 4.5% 이상 유지 시 DCF 할인율 전제 무효" (approaching, proximity 85%)
- 유효기간: ~2026-04-30 (FOMC 금리 결정 전까지)
- 자기 점검: MCP 조회 누락 1건(Omission BBJ), 도메인 커버리지 partial
```

**나쁜 검증 결과 요약 (하지 말 것):**

```
검증 완료. 대체로 괜찮습니다. 일부 수치가 다를 수 있습니다.
```
**왜 나쁜가:** 6층 판정 없음, claim별 집계 없음, KC 없음, 유효기간 없음, Self-Audit 없음. "대체로 괜찮다"는 V-06 위반

**생성 규칙:** 🔴 먼저 → 같은 verdict 내 P1>P2. 🟢/⚫ claim은 생성 금지.
Finding 0건 출력 금지 — 🟡/🔴이 있으면 반드시 생성 (V-08).

#### 5-3. HTML 렌더링

**7+1 섹션 구조:**

| 섹션 | 내용 | 표시 모드 |
|---|---|---|
| I | Executive Summary — 판정 + Finding 요약 | 항상 |
| II | 6-Layer 판정표 — 층별 독립 판정 | full-only |
| III | Actionable Findings — Finding Card 배치 | 항상 |
| IV | Fact Check Detail — claim별 대조 | full-only |
| V | Logic & KC — 인과 체인 + KC | full-only |
| VI | Omission Ground — BBJ + 누락 | full-only |
| VII | 수정 대시보드 — 집계 + 최종 판정 | 항상 |
| VIII | [부록] — 복수 문서 시 (선택) | 항상 |

**필수 UI:** topbar(sticky) + float-nav(우측) + SHORT/FULL 토글 + 다크모드 + 인쇄

**Tooltip:** 전문용어 최초 등장 시 `<span class="tip" data-tip="설명">용어</span>` 부착. 과잉 금지.

#### 5-4. 파일 저장

파일명: `[슬러그]-verification-report.html` → 지정 경로(기본 output/)에 저장.

#### 5-5. HTML 위반 규칙 (V-10 ~ V-13)

| 코드 | 규칙 |
|---|---|
| V-10 | float-nav 누락 금지. 모든 섹션에 nav-item 필수. |
| V-11 | SHORT 모드 미구현 금지. I, III, VII만 표시. |
| V-12 | 다크모드 깨짐 금지. 모든 색상은 CSS 변수(var()) 사용. |
| V-13 | float-nav에 `<a>` 태그 금지. `<div class="nav-item" data-target="id">` + JS scrollIntoView 사용. |

---

## 에러 핸들링

| 상황 | 처리 |
|---|---|
| Phase 0 verify_start() 실패 | 중단 + 에러 메시지 출력 |
| Phase 1 claim 0건 | "검증할 claim이 없습니다" 출력 후 종료 |
| Phase 1.5 MCP 호출 실패 | 3회 재시도 → 실패 시 해당 소스 ⚫ 처리 + 로그 |
| Phase 2.5 루프 2회 초과 | 미완 항목 ⚫ 처리 |
| Phase 3+4 finalize 실패 | result_json을 사용자에게 직접 출력 (데이터 유실 방지) |

---

## 데이터 전달 규칙

| 출발 | 도착 | 전달 방식 |
|---|---|---|
| Phase 0 반환값 | Phase 2 각 층 | 플레이스홀더 자동 주입 ({mcp_sources}, {checklist} 등) |
| ① Fact evidence | ③ Logic | {fact_evidence} 플레이스홀더 (KC 확인 시 MCP 중복 방지) |
| ① Fact evidence | ④ Temporal | {fact_evidence} 플레이스홀더 |
| ① Fact evidence | ⑥ Omission | {fact_evidence} 플레이스홀더 (BBJ 시그널 확인 시 재사용) |
| ③ Logic KC | ⑥ Omission | kc_extracted → BBJ Break 소재 (대화 컨텍스트 참조) |
| ③ Logic KC | Phase 3+4 validity_condition | finalize 서브에이전트가 KC에서 추출 |
| ⑥ Omission 동심원 | Phase 3+4 validity_condition | notes → finalize가 참조 |
| Phase 3+4 result_json | Phase 4.5 | {result_json} 플레이스홀더 |
| engine coverage_report | Phase 4.5 | {coverage_report} 플레이스홀더 |
| Phase 3+4 result_json | Phase 5 | {data} 플레이스홀더 |

---

## 컨텍스트 로딩 전략

```
전부 로딩하지 않는다. 필요한 것만, 필요한 시점에.

세션 시작 시 (Phase 0 전):
  ├── verify_scan() → state/current-status.json (KC/Watch/이슈 현황)
  ├── verify_orchestrator() → CLAUDE.md + SKILL.md
  └── 나머지 prompts/*.md는 해당 Phase에서만 로딩

Phase별 로딩:
  Phase 1:  prompts/extract_claims.md (claim 추출 시)
  Phase 2①: prompts/fact_check.md (Fact 층 시)
  Phase 2②: prompts/norm_check.md (Norm 층 시)
  Phase 2③: prompts/logic_check.md (Logic 층 시)
  Phase 2④: prompts/temporal_check.md
  Phase 2⑤: prompts/incentive_check.md
  Phase 2⑥: prompts/omission_check.md
  Phase 2.5: prompts/coverage_recheck.md
  Phase 3+4: prompts/finalize.md
  Phase 4.5: prompts/self_audit.md
  Phase 5:  prompts/schemas/component-catalog.md

로딩하지 않는 것:
  ├── 모든 prompts/*.md를 한꺼번에 (컨텍스트 과잉)
  ├── output/history/ 전체 (최근 1건만 필요 시)
  ├── data/rules.json 전체 (해당 doc_type 규칙만)
  └── schemas/ 전체 (Phase 5에서만)

이전 검증 참조 시:
  └── verify_load_history(vrf_id)로 1건만 로딩
```

---

## 도구 폴백 경로

```
MCP 도구 실패 시 수집을 중단하지 않는다. 폴백으로 대체한다.

| 1차 도구 | 실패 시 | 폴백 |
|----------|--------|------|
| DART | 연결 실패 | WebSearch "[기업명] 공시 DART" |
| SEC-EDGAR | 연결 실패 | WebSearch "[company] SEC filing" |
| Yahoo Finance | 연결 실패 | WebSearch "[ticker] stock price" |
| FRED | 연결 실패 | WebSearch "[series] latest value fred" |
| CoinGecko | 연결 실패 | WebSearch "bitcoin price coingecko" |
| DeFiLlama | 연결 실패 | WebSearch "DeFi TVL defillama" |
| CoinMetrics | 연결 실패 | WebSearch "[metric] coinmetrics" |
| Etherscan | 연결 실패 | WebSearch "[address] etherscan" |
| Firecrawl/Tavily | 연결 실패 | WebSearch (동일 쿼리) |
| 모든 MCP | 전체 장애 | WebSearch 전면 전환 + "⚠ MCP 전체 장애" 기록 |

수집 실패 시:
  ├── 해당 claim → ⚫ NO BASIS 처리 (CLAUDE.md 불변원칙 2)
  ├── "⚫ [도구명] 연결 실패. 폴백 결과 없음" 기록
  └── 3회 재시도 후 실패 확정 (에러 핸들링 참조)
```

---

## 알려진 실패 패턴과 방어 규칙 (F-테이블)

**이 테이블은 운영하면서 누적한다. 삭제하지 않는다.**

| # | 실패 패턴 | 원인 | 방어 규칙 | 감지 방법 |
|---|----------|------|----------|----------|
| F-01 | MCP 조회 없이 🟢 판정 | LLM이 내장 지식으로 "맞다"고 판단 | evidence 빈 배열인 🟢 금지. V-01 | Self-Audit 항목 1 |
| F-02 | 단일 소스로 🟢 | 교차검증 없이 1개 소스만으로 확정 | Tier 2는 교차검증 권장. notes에 "단일 소스" 표기 | Self-Audit 항목 2 |
| F-03 | estimate를 🟢 판정 | 추정치를 확인된 사실로 취급 | evidence_type="estimate" → Fact 🟢 상한 🟡로 제한 | FactLayer.judge() 코드 |
| F-04 | KC 미추출 | Logic 검증에서 핵심 전제를 KC로 등록 안 함 | Logic 🟡/🔴 시 KC 1건+ 필수 | Self-Audit 항목 4 |
| F-05 | depends_on 미연결 | claim 간 논리적 의존성 누락 | 인과주장이 수치주장에 의존하면 depends_on 필수 | engine.py 전파 로직 |
| F-06 | 도메인 커버리지 미확인 | doc_type에 전용 규칙/체크리스트가 없는데 무시 | verify_start()에서 warning 출력. Self-Audit에서 재확인 | coverage_report |
| F-07 | Self-Audit "문제 없음" | 자기 점검에서 모든 항목 통과로 끝냄 | V-06: "문제 없음" 종료 금지. 최소 한계 1건+개선 1건 | Self-Audit V-06 |
| F-08 | invalidation_triggers 미설정 | finalize에서 무효화 트리거를 빈 배열로 넘김 | 트리거 0건 시 "유효기간 제한 없음"이 의도적인지 확인 | verify_finalize 반환값 |
| F-09 | 보고서에 데이터 없는 섹션 생성 | "보고서니까 섹션이 있어야지" | V3 검증: 빈 섹션 발견 시 삭제. 데이터 없으면 만들지 않는다 | 자율 보고서 V3 |
| F-10 | 보고서 모든 섹션 균등 크기 | 디자인 균형 추구 | V4 검증: 데이터 양과 섹션 크기 비례 확인 | 자율 보고서 V4 |
| F-11 | Core Claim이 본문과 불일치 | Phase 5-A에서 추출 후 렌더링 중 이야기 변경 | V1 검증: 첫 줄과 본문 정합성 확인 | 자율 보고서 V1 |
| F-12 | 첫 화면에 배경 설명 배치 | "순서대로" 작성 습관 | V5 검증: 첫 화면 = Core Claim + 판정 | 자율 보고서 V5 |
| ... | 운영하면서 추가 | | | |

---

## Self-Audit → 이슈 적재 연동

```
Phase 4.5 Self-Audit 완료 후:

시스템성 이슈 판별:
  ├── 동일 ⚠가 이전 검증에서도 발생 → 시스템성 확정
  ├── 도메인 커버리지 갭 (coverage_level ≠ "full") → 즉시 적재
  ├── MCP 수집 실패 (폴백 사용) → 즉시 적재
  └── 프롬프트 지시와 실제 동작 불일치 → 즉시 적재

적재 방법:
  verify_log_issue(title, description, evidence, category_key, severity)

카테고리:
  mcp_miss       (CAT-2) — MCP 연결/조회 실패
  evidence_gap   (CAT-2) — 증거 부족으로 ⚫ 처리
  coverage_gap   (CAT-1) — 도메인 규칙/체크리스트 부족
  kc_incomplete  (CAT-4) — KC 미추출 또는 불완전
  prompt_drift   (CAT-3) — 프롬프트 지시 미준수
```

---

## 불변 규칙 (진화의 하한선)

```
어떤 SKILL.md/CLAUDE.md 수정에서도 아래는 절대 변경하지 않는다:

1. 6층 검증 순서 (Fact→Norm→Logic→Temporal→Incentive→Omission)는 바꾸지 않는다.
2. CLAUDE.md 불변 원칙 4개는 완화하지 않는다.
3. Phase 1.5 "수집 중 판정 금지" 원칙은 "효율" 명목으로 생략하지 않는다.
4. V-06 "문제 없음 종료 금지"는 해제하지 않는다.
5. evidence 없는 🟢 판정을 허용하지 않는다 (V-01).
6. claim_type × layer 매트릭스의 적용/미적용 구조를 임의 변경하지 않는다.
7. F-테이블 항목을 삭제하지 않고 누적만 한다.
8. verify_finalize() 후 자동 후처리 (KC/패턴/규칙활성도)를 비활성화하지 않는다.
```

---

## 주간 리뷰 프로토콜

```
트리거: 매주 월요일 또는 "시스템 리뷰"

Step 1: verify_get_issues() → open 이슈 로딩
Step 2: verify_rule_activity() → 죽은 규칙/핫 규칙 확인
Step 3: verify_get_patterns() → 승격 대기 패턴 확인
Step 4: verify_tune() 결과 확인 (실행 이력 있으면)
Step 5: 이슈별 수정안 + 승인 → rules.json/checklists.json 보강
Step 6: 감사 요약:
  "이슈 {N}건 / 죽은 규칙 {N}건 / 승격 대기 패턴 {N}건"

주기: 매주 월요일. 이슈 0건이면 "이슈 없음" 출력.
```

---

## 갱신 규칙

```
갱신 주기: 주간 리뷰 시 + 이슈 발견 즉시
갱신 주체: 사용자 승인 후 반영 (Yellow Zone)
버전 관리: docs/changelog.json에 자동 기록 (mcp_server.py _append_changelog)
불변 규칙: GUARDRAILS.md Red Zone 항목은 수정 불가
```
