# PSF 자율 운영 레이어

> SKILL-core.md의 보조 지침. W Loop 또는 자율 점검 시 추가 로딩.
> 자율 3조건: 기억(Memory) + 루프(Loop) + 울타리(Guardrail)

---

## 자율 3조건

```
자율 수준: Level 3 (자율 실행)
  울타리(Green/Yellow/Red Zone) 안에서 관측·판정·기록을 무승인 실행.
  구조 수정(ontology/axis 개정)은 Yellow Zone → 승인 필요.

상세: GUARDRAILS.md, SCHEMAS.md 참조
코드: core/validate.py, core/snapshot.py, core/autonomy.py
```

---

## 세션 시작 스캔 (모든 세션의 첫 동작)

```
1. state.json 로딩 → 현재 국면 확인
2. macro/latest.json 신선도 확인 (Phase 0)
3. next_questions에서 deadline 도래 항목 필터
4. errors.md 셀프검증 체크리스트 확인
5. 루프 유형 판별 (D/W/M/Q)

종합 알림 출력:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 시스템 상태 ({날짜})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
국면: {🟢🟡🔴} | macro: {🟢🟡🔴}(점수) | 정합: {상태}
질문: {N}건 open ({deadline 도래 N건})
Link: {활성 Link 목록}
축: {변화 있는 축}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

알림 없으면 요약 1줄만. 과잉 알림 금지.
```

---

## 자율 행동 로그

```
세션 내 자율 행동 로그:

[AUTO] {시점} | {행동} | {대상} | {결과}

예:
[AUTO] Phase0 | CHECK   | macro/latest.json freshness | fresh (2일 전)
[AUTO] Phase0 | LOAD    | state.json                  | ✅ 🟡 경계
[AUTO] 수집   | COLLECT | Tavily "Iran Hormuz"        | ✅ 3건
[AUTO] 판정   | JUDGE   | PSF 국면                    | 🟡 유지
[AUTO] 기록   | SAVE    | state.json                  | ✅

세션 종료 시 요약 출력.
```

---

## 자율 수준 정의

```
Level 1 — 자율 감지:     세션 시작 시 state/ 자동 스캔 + 알림
Level 2 — 자율 판단:     axis-map 6단계 자율 실행 + macro 자동 대행 제안
Level 3 — 자율 실행:     울타리 안에서 무승인 실행 ← 현재 위치

전환 조건:
├── 0→1: state.json 구축 완료 ✅
├── 1→2: D/W/M/Q 루프 안정 운영 ✅
└── 2→3: GUARDRAILS.md + validate.py + autonomy.py 검증 완료 ✅
```

---

## 이상 감지 트리거

```
상세: GUARDRAILS.md 참조

1. 데이터 이상: 지표 전일 대비 50%+ 변동
2. 국면 급변: 🟢→🔴 또는 🔴→🟢 단일 세션 전환
3. macro 역설: macro 🟢 + PSF 🔴
4. MCP 대량 실패: 단일 세션 3건+
5. Link 폭주: L8 + CorrFlip 동시 활성

자동 감지: python core/autonomy.py scan
```

---

## 에스컬레이션 경로

```
Level 1 (경미): ⚠ 태그 후 계속. 보고서에 "[주의]" 포함.
Level 2 (주의): 해당 판정 보류. 사용자 인라인 질문.
Level 3 (심각): 관측 전체 보류. 상세 보고 + 사용자 지시 대기.
Level 4 (긴급): 모든 관측 정지. 사용자 직접 개입.
```
