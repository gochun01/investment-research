# Verification Engine — 변경 이력

> 검증 엔진의 규칙·체크리스트·코드 변경을 추적합니다.
> 구조화된 데이터는 `changelog.json`에 병행 기록됩니다.
> `verify_add_rule()`, `verify_add_checklist_item()`, `verify_analyze_outcomes()` 호출 시 **자동 기록**됩니다.

---

## 2026-03-20 — 뉴스 기사 검증 체계 + 피드백 루프 + 변경 추적 시스템

### Phase 1: 이력 관리 도구 추가
검증 결과를 저장만 하고 활용하지 못하는 문제 해결.
- `verify_check_triggers()` — 무효화 트리거 도래 확인
- `verify_record_outcome()` — 사후 결과 기록 (`{vrf_id}_outcome.json`)
- `verify_list_history()` 개선 — 제목, 판정, 트리거 도래, outcome 유무 표시

### Phase 2: 프롬프트 주입 방식 시도 → 철회
과거 이력을 `{past_context}`로 프롬프트에 주입하는 방식을 구현했으나, "틀은 코드" 철학과 맞지 않아 제거.
- `_lookup_past_context()` 헬퍼 → 추가 후 제거
- `{past_context}` 플레이스홀더 4개 프롬프트 → 추가 후 제거
- **교훈: Claude에게 "참고해줘"는 강제가 아니다. 규칙으로 만들어야 코드가 강제한다.**

### Phase 3: 코드 강제 피드백 루프 구축
- `verify_analyze_outcomes()` — outcome 패턴 분석 → 규칙/체크리스트 추가 후보 자동 생성
- 루프: 검증 → 저장 → outcome 기록 → 패턴 분석 → 규칙 제안 → 승인 → rules.json 추가 → 다음 검증에 강제 대입

### Phase 4: news_article 검증 체계 신설

**규칙 6개:**

| ID | 범위 | 이름 | 잡는 것 |
|---|---|---|---|
| lr_031 | common | perception_as_reality | 설문→머니무브 등치 |
| lr_032 | common | minority_framed_as_majority | 37.4%를 "국민이 답했다" |
| lr_033 | common | counter_trend_omission | 7000 전망하면서 -7.7% 하락 누락 |
| lr_news_001 | news | survey_sample_insufficient | 설문 방법론 미공개 |
| lr_news_002 | news | editorial_as_fact | 의견을 사실처럼 서술 |
| lr_news_003 | news | single_source_generalization | 단일 설문을 "국민" 일반화 |

**체크리스트 10개:** Norm 5(nr_news_001~005) + Omission 5(om_news_001~005)

**코드 변경:** engine.py(doc_type), models.py(survey), fact.py(MCP소스+🟡상한), CLAUDE.md(survey 정의)

### Phase 5: 실전 검증 실행
- vrf_20260320_093206_847: 매경 기사 → 🔴 FLAGGED
- 10 claims, 17 findings (🔴5 + 🟡12)
- 새 규칙 6/6 전부 trigger 확인
- KC 6건 추출, BBJ Break 2건, 무효화 트리거 3건

### Phase 6: HTML 보고서 검토 → 보완사항 5건 도출
| ID | 내용 | 상태 |
|---|---|---|
| html_001 | Section VI BBJ Break 미렌더링 | 미수정 |
| html_002 | Section II KEY NOTES 🔴 우선표시 안됨 | 미수정 |
| html_003 | Temporal 🟡 전파 설명 부재 | UX 개선 필요 |
| html_004 | Finding Card suggested_fix 미등록 | 데이터 입력 필요 |
| html_005 | report-class 배경색 gold→red 필요 | 미수정 |

### Phase 7: 변경 추적 시스템 구축
- `docs/CHANGELOG.md` — 사람이 읽는 이력
- `docs/changelog.json` — 구조화된 이력 (코드 읽기용)
- `_append_changelog()` — verify_add_rule/checklist/analyze_outcomes 호출 시 자동 기록
- **이후 모든 규칙·체크리스트 변경이 자동으로 추적됨**

### Phase 8: KC 생명주기 + 패턴 레지스트리 구축
Notion 3-DB 피드백 시스템 설계를 분석하여 핵심 로직을 코드로 구현. Notion은 뷰어로만 사용.
- `core/kc_lifecycle.py` — KC 상태 전이 엔진 (active→approaching→resolved→revived)
- `core/pattern_registry.py` — 패턴 누적 카운터 (flag→candidate→proposed→promoted)
- `data/kc_registry.json` — KC 영구 저장 (8건)
- `data/pattern_registry.json` — 패턴 영구 저장 (8건)
- `verify_get_kc_status()`, `verify_update_kc()` — KC 조회/갱신 도구
- `verify_get_patterns()`, `verify_promote_pattern()` — 패턴 조회/승격 도구
- `verify_finalize()` 확장 — KC 자동 등록 + 패턴 자동 기록 연동

### Phase 9: Notion 3-DB 생성 + 데이터 동기화
- DB① Verification Memory (45e66b17) — 검증 이력 4건 동기화
- DB② Pattern Registry (a6b5d868) — 패턴 8건 동기화
- DB③ KC Tracker (18b82429) — KC 8건 동기화
- DB간 Relation 연결: DB①→DB②(related_patterns), DB①→DB③(related_kcs)

### Phase 10: 엔진 스마트 업그레이드 4건
history 분석 결과(Omission 100% 🔴, Logic 75% 🔴)를 기반으로 개선.
1. **outcome 반자동 수집** — `verify_check_triggers()`에 expired 트리거 시 outcome 기록 안내 자동 표시
2. **간이 검증** — `verify_quick_check()` 도구. 제목+설명만으로 Fact+Logic 경량 검증 (3~5분/건)
3. **규칙 활성도 추적** — `core/rule_tracker.py` + `data/rule_activity.json` + `verify_rule_activity()`. finalize 시 자동 기록. 죽은 규칙/핵심 규칙 식별
5. **doc_type별 검증 강도** — `claim_type_matrix.json`에 `_verification_depth` 프리셋 8개. news_article=light, equity=standard, legal=heavy 등

### Phase 11: 검증엔진 수집기(Collector) 설계
엔진에 다양한 유형의 문서를 자동 수집하여 경험을 축적하는 시스템 설계.
- 설계서: `docs/collector-design.md`
- 7 에이전트, 4팀 (수집팀/검증팀/축적팀/감시팀)
- 핵심: 건수보다 다양성. 8개 doc_type 균형 수집
- 병렬 처리: 소스 모니터링 병렬, 간이 검증 병렬
- 실패 대응: retriable/fatal/degraded 3단계
- 성공 기준: 8 doc_type × 5건 → proposed 5개 → 규칙 승격 10개

### 현재 시스템 상태 (Phase 11 완료 시점)
```
도구: 28개 (초기 12 → +16)
규칙: 46개 (초기 34 → +12)
체크리스트: 161개 (초기 ~140 → +21)
KC: 8건 추적 중
패턴: 8건 추적 중
Notion DB: 3개 (총 20건 동기화)
검증 이력: 4건
doc_type: 8개 (초기 7 → +1)
검증 강도 프리셋: 8개
```

---

### 자동 기록 (changelog.json 동기화)
- [tuning_executed] : verify_tune
- [ontology_applied] megatrend_plate_structure_flow: ontology_design
- [project_created] verification-collector: collector_implementation
- 코드 수정: `changelog_md_auto_sync` — mcp_server.py

## 2026-03-19 — 보완사항 제안서 작성
- `output/보완사항/feature-proposals.md` — 8개 기능 제안 (A~H)
- 난이도×효과 매트릭스

---

## 2026-03-17 — 초기 구축 v1.0
- 6-Layer 검증 엔진 초기 구축
- MCP 서버 12개 도구
- rules.json 34개 규칙 (common 7 + equity 8 + crypto 2 + legal 8 + macro 2 + regulatory 6 + geopolitical 1)
- checklists.json: Norm 7 doc_type + Omission 18 섹터
- HTML 보고서 렌더러 7+1 섹션
- 설계 철학: "틀은 코드, 두뇌는 프롬프트"
- 상세: `docs/archive/2026-03-17-업그레이드-작업일지.md`
