# Guardrails — verification-engine 자율 울타리

> 6층 검증 엔진의 자율 행동 경계 정의.
> 기존 CLAUDE.md 불변 원칙 4개를 확장하여 Green/Yellow/Red Zone으로 구조화.

---

## 원칙

```
1. 되돌림 가능한 행동만 무승인
2. 모든 자율 행동은 로그 기록
3. 투자 판단 관련 행동은 절대 무승인 불가
4. 검증 판정(🟢🟡🔴⚫)을 자동으로 변경하지 않는다
5. 이상 감지 시 자동 정지 → 사용자에게 에스컬레이션
6. 울타리는 이 문서에 명시. 암묵적 허용 없음.
```

---

## Green Zone — 무승인 허용

```
검증 실행 (핵심 파이프라인):
├── verify_orchestrator() — 프롬프트 로딩
├── verify_start() — 세션 시작
├── verify_add_claim() — claim 등록
├── verify_set_verdict() — 층별 판정 등록
├── verify_set_document_verdict() — 문서 판정 등록
├── verify_check_coverage() — 커버리지 체크
├── verify_finalize() — 결과 생성 + 저장
│   (finalize 시 자동 후처리 포함: KC 등록, 패턴 기록, 규칙 활성도)
├── verify_generate_html() — HTML 보고서 생성
└── verify_get_prompt() — 프롬프트 조회

데이터 읽기:
├── verify_get_checklist() — 체크리스트 조회
├── verify_get_rules() — 규칙 조회
├── verify_list_history() — 검증 이력 조회
├── verify_load_history() — 이력 로드
├── verify_check_triggers() — 트리거 점검
├── verify_get_kc_status() — KC 현황
├── verify_get_patterns() — 패턴 현황
├── verify_rule_activity() — 규칙 활성도
└── state/ 파일 로딩

상태 자동 갱신 (finalize 후 자동):
├── data/kc_registry.json — KC 등록/proximity 갱신
├── data/pattern_registry.json — 패턴 기록
├── data/rule_activity.json — 규칙 활성도
├── output/history/vrf_*.json — 검증 결과 저장
├── state/current-status.json — 현황 갱신
└── state/verification-issues.json — Self-Audit 이슈 적재

Watch 스캔:
├── state/verification-watches.json — 기한 도래 체크
└── 알림 텍스트 생성
```

---

## Yellow Zone — 승인 필요

```
규칙/체크리스트 변경:
├── verify_add_rule() — 규칙 추가
├── verify_add_checklist_item() — 체크리스트 항목 추가
├── verify_promote_pattern() — 패턴 → 규칙 승격
└── data/claim_type_matrix.json 수정

KC 관리:
├── verify_update_kc() — KC 값 수동 갱신
├── KC 임계값 변경
└── KC 삭제

Watch 관리:
├── Watch 등록/종료/변경
└── 트리거 스케줄 변경

판정 관련:
├── verify_apply_corrections() — Finding Card 수정 적용
├── verify_record_outcome() — 사후 결과 기록
└── verify_tune() — 미세조정 실행

지침 수정:
├── prompts/*.md 수정
├── CLAUDE.md 수정
├── GUARDRAILS.md 수정
└── schemas/*.md 수정

이슈 관리:
├── verification-issues.json 이슈 상태 변경 (fix/wontfix)
└── 이슈 severity 수동 변경
```

---

## Red Zone — 금지

```
판정 자동 변경:
├── finalize 완료 후 🟢🟡🔴⚫ 판정을 자동 수정
├── Self-Audit 결과로 판정을 재평가
└── "이 판정은 틀렸으니 바꾸겠습니다" ← 금지

투자 행동:
├── 검증 결과를 매수/매도 추천으로 전환
├── "이 문서는 신뢰할 수 있으니 투자해도 됩니다" ← 금지
└── 특정 자산의 가격 목표 제시

비가역 행동:
├── data/*.json 파일 삭제
├── output/history/ 일괄 삭제
├── rules.json / checklists.json 초기화
└── kc_registry.json 전체 삭제

MCP 1차 소스 원칙 위반:
├── MCP 조회 없이 🟢 판정 (CLAUDE.md 불변원칙 1)
├── 기준 데이터 없이 맞다/틀리다 판정 (불변원칙 2)
└── 하나의 해석을 정답으로 선언 (불변원칙 3)
```

---

## 자율 행동 로그

```
[AUTO] {timestamp} | {zone} | {action} | {target} | {result}

예:
[AUTO] 09:31 | GREEN  | LOAD    | state/current-status.json  | ✅
[AUTO] 09:31 | GREEN  | SCAN    | verification-watches.json  | 1건 도래
[AUTO] 09:32 | GREEN  | CHECK   | KC-VIX-30 proximity        | 88% → approaching
[AUTO] 09:33 | YELLOW | PROPOSE | Watch W-VRF-001 재검증      | ⏳ 승인 대기
```

---

## 이상 감지 + 자동 정지

```
1. 동일 claim에 같은 층 판정 3회+ 덮어쓰기 → 정지
2. finalize 시 critical_flags 5건+ → 사용자 확인 요청
3. KC triggered + approaching 동시 3건+ → 사용자 에스컬레이션
4. system-issues high 3건+ → 검증 품질 경고
5. outcome 분석에서 동일 규칙 3회+ false positive → 규칙 재검토 제안
```
