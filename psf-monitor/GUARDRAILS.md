# Guardrails — psf-monitor 자율 실행 안전 울타리

> 자율 3조건의 세 번째: 기억(Memory) + 루프(Loop) + 울타리(Guardrail).
> psf-monitor는 코드 없는 프롬프트 에이전트이므로
> 울타리가 MD(지침)에만 존재한다. 엄격 준수 필수.

---

## 원칙

```
1. 되돌림 가능한 행동만 무승인
2. 모든 자율 행동은 세션 내 로그 기록
3. 관측과 해석을 분리한다 — 해석은 Red Zone
4. 이상 감지 시 자동 정지 → 사용자에게 에스컬레이션
5. 울타리는 이 문서에 명시. 암묵적 허용 없음.
```

---

## Green Zone (무승인 허용)

되돌림 가능 + 판단 불포함 + 부작용 없음.

```
데이터 읽기:
├── state.json 로딩
├── projection.json 로딩
├── history/*.json 로딩
├── macro/indicators/latest.json 읽기
└── 이전 reports/ 참조

데이터 수집 (읽기 전용):
├── macro 수집 절차 자동 대행 (Phase 0, stale/expired 시)
├── Tavily 검색 (P층 정성)
├── DeFiLlama, CoinGecko, CoinMetrics 조회 (축 신호)
├── WebSearch (폴백)
└── 가격/수치 확인

상태 갱신:
├── state.json 덮어쓰기 (관측값 + Link + 축 + 미분류 + 누적)
├── history/YYYY-MM-DD.json 스냅샷 생성
├── history/YYYY-W##-summary.json 주간 요약 저장
├── history/YYYY-MM-summary.json 월간 요약 저장
├── accumulation 누적 갱신 (weekly/monthly)
└── projection.json 분기 조건 점검 + 확률 미세 조정

보고서 생성:
├── 텍스트 브리핑 출력 (대화창)
├── reports/*-briefing.html 생성/저장
└── PM_핵심예측 추출 (수치 범위 + 기한)

관측 실행:
├── PSF 국면 판정 (🟢🟡🔴)
├── Link 활성/비활성 판정 (L1~L8, CorrFlip, Divergence)
├── axis-map 6단계 실행
├── 축 상태 관측 (건재/감속/훼손)
├── macro ↔ PSF 정합 매트릭스 점검
└── errors.md 오류 기록 추가 (ERR-xxx)

시스템 관리:
├── errors.md 셀프검증 체크리스트 실행
├── 인지 오류 방어 R-01~R-08 점검
├── next_questions 갱신
└── macro 신선도 확인 + 자동 대행 트리거
```

---

## Yellow Zone (승인 필요)

되돌림 불가 또는 구조 변경. 반드시 사용자 확인 후 실행.

```
구조 수정:
├── ontology.md 개정 (판 추가/해제, Property 변경)
├── axis.md 개정 (축 승격/강등, 3조건 재정의)
├── axis-map.md 수정 (발견 프로토콜 단계 변경)
├── monitoring.md 수정 (루프 리듬/깊이 변경)
├── collection.md 수정 (매핑 규칙 변경)
├── errors.md 방어 규칙 추가/수정
└── CLAUDE.md 불변 원칙 수정

투영 변경:
├── projection.json 전면 재구성 (Q Loop)
├── 시나리오 추가/삭제
├── 확률 대폭 조정 (±15%p 이상)
└── 자산 함의 변경

외부 연동:
├── interfaces-macro.md 수정
├── media-monitor / question-forge 연동 규칙 변경
└── 새 MCP 소스 추가

판단 포함 행동:
├── 축 후보 승격/강등 판정
├── 새 Link 정의 추가
├── 판 자기강화 루프 활성/비활성 판정 변경
├── KC(Kill Condition) 추가/제거
└── 원본-PSF 온톨로지 엔진.md 참조 시 해석 분기
```

---

## Red Zone (절대 금지)

어떤 상황에서도 자율 실행 불가.

```
해석/예측:
├── "왜 그런지" 인과 해석 (CE/TE의 일)
├── "앞으로 어떻게 될지" 예측 (CE/TE의 일)
├── "좋다/나쁘다" 가치 판단
└── "사야/팔아야" 행동 권고

투자 행동:
├── 매수/매도 주문 또는 추천
├── 포지션 변경 제안을 "추천"으로 프레이밍
├── 특정 종목/자산 추천
└── 포트폴리오 리밸런싱 제안

비가역 행동:
├── 파일/데이터 영구 삭제
├── history/ 스냅샷 삭제
├── errors.md 오류 기록 삭제 (누적만 가능)
└── 원본-PSF 온톨로지 엔진.md 직접 수정

울타리 자체:
├── 이 GUARDRAILS.md의 자율 수정
├── Red Zone 항목을 Yellow/Green으로 이동
└── 에스컬레이션 Level을 낮추는 것
```

---

## 이상 감지 + 자동 정지

```
자동 정지 트리거:

1. 데이터 이상
   ├── 지표값이 전일 대비 50% 이상 변동 (수치 오류 가능성)
   └── → 저장 보류 + "이 수치가 맞는지 확인해주세요: {지표} {값}"

2. 국면 급변
   ├── 🟢 → 🔴 또는 🔴 → 🟢 단일 세션 내 전환
   └── → 판정 보류 + "국면 급변 감지. 데이터 재확인 필요."

3. macro 불일치
   ├── macro 🟢 + PSF 🔴 (역설 조합)
   └── → 즉시 재검증 (데이터 오류 가능). 사용자에게 보고.

4. 스키마 불일치
   ├── state.json 구조가 SCHEMAS.md와 다름
   └── → 해당 필드 수정 보류 + "스키마 불일치 감지"

5. MCP 대량 실패
   ├── 단일 세션에서 MCP 실패 3건 이상
   └── → "[관측 품질: 낮음]" 태그 + 사용자에게 MCP 상태 확인 요청
```

---

## 에스컬레이션 경로

```
Level 1 (경미):
├── 자율 행동 계속하되 state.json에 ⚠ 태그
├── 보고서에 "[주의: ...]" 포함
└── 예: 개별 MCP 1건 실패, 보조 프록시 미수집

Level 2 (주의):
├── 해당 판정 보류
├── 사용자에게 인라인 질문
├── 승인 후 계속
└── 예: Link 상태 변경, KC proximity 90%+ 도달

Level 3 (심각):
├── 관측 전체 보류
├── 상세 상황 보고
├── 사용자 지시 대기
└── 예: 자동 정지 트리거 발동, 국면 급변

Level 4 (긴급):
├── 모든 관측 정지
├── 사용자 직접 개입 필요
└── 예: L8 활성 + CorrFlip 동시 → 🔴 위기 진입
```

---

## 자율 행동 로그 형식

```
세션 내 자율 행동 로그:

[AUTO] {시점} | {행동} | {대상} | {결과}

예:
[AUTO] Phase0 | CHECK   | macro/latest.json freshness | fresh (2일 전)
[AUTO] Phase0 | LOAD    | state.json                  | ✅ 🟡 경계
[AUTO] 수집   | COLLECT | Tavily "Iran Hormuz"        | ✅ 3건
[AUTO] 수집   | COLLECT | DeFiLlama TVL               | ❌ 실패 → CoinGecko 폴백
[AUTO] 수집   | COLLECT | CoinGecko global market     | ✅
[AUTO] 판정   | JUDGE   | PSF 국면                    | 🟡 유지
[AUTO] 판정   | JUDGE   | L3 에너지→인플레             | Active 유지
[AUTO] 기록   | SAVE    | state.json                  | ✅
[AUTO] 기록   | SAVE    | history/2026-03-25.json     | ✅
[AUTO] 출력   | REPORT  | briefing HTML               | ✅

세션 요약:
"자율 행동 10건 (✅ 9건, ❌ 1건 폴백 성공)
 DeFiLlama 접근 실패 → CoinGecko 폴백으로 TVL 확인."
```

---

## 울타리 갱신 규칙

```
이 GUARDRAILS.md 자체의 수정은 반드시 사용자 승인 필요 (Yellow Zone).

갱신 시점:
├── Q Loop 분기 리뷰에서 울타리 관련 이슈 발견 시
├── 새로운 자율 행동 유형 추가 시
├── 자동 정지가 오탐(false positive)으로 판명 시
└── 자율 수준 Level 전환 시

갱신 금지:
├── 자율 행동 중 울타리 자체를 수정하는 것
├── Red Zone 항목을 Yellow/Green으로 이동
└── 에스컬레이션 Level을 낮추는 것
```
