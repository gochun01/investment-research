---
name: psf
description: "PSF 계기판. 세계의 현재 상태를 관측하고 축까지의 거리를 측정한다. 트리거: 'PSF 갱신', 'PSF 상태', '계기판', '국면', '브리핑', '주간 리뷰', '분기 진단', '시스템 상태', '자율 점검'. state.json이 3일 이상 stale이면 갱신 권고. 자율 3조건(기억+루프+울타리) 내장. GUARDRAILS.md 준수."
---

# PSF 실행 프로토콜 — Core

> 과정은 고정이 아니다. 데이터가 과정을 결정한다.
> 이 문서는 D Loop(일일) 실행에 필요한 핵심만 포함한다.
> 자율 운영: SKILL-autonomy.md | 실패 방어+진화: SKILL-fail-evolve.md

---

## 반드시 해야 하는 것 (불변)

```
1. errors.md 셀프검증 체크리스트를 실행 전에 확인한다.
2. P1~P4는 독립적으로 수집한다. 통합 검색으로 퉁치지 않는다.
3. PSF는 MCP를 직접 호출하지 않는다. Macro가 유일한 정량 수집자.
   (단, P층 정성 데이터와 축 신호 탐색에서는 Tavily 등을 직접 사용한다.)
4. 관측과 해석을 분리한다. PSF는 "무엇이 변했는가"를 말한다.
   "왜 변했는가"는 CE/TE의 일.
5. state.json에 기록한다. history/에 스냅샷을 남긴다.
6. 감속·훼손 신호를 가속 신호보다 먼저 점검한다.
7. 축 관련성 판단 시 axis-summary.md를 참조한다.
   상세가 필요하면 axis.md를 추가 로딩한다.
```

---

## Phase 0: Macro 신선도 확인 + 자동 트리거

```
★ PSF 실행의 최초 단계. 다른 모든 단계보다 먼저 실행한다.

경로: C:\Users\이미영\Downloads\에이전트\macro\indicators\latest.json
참조: macro/SKILL-macro-indicators.md

1. latest.json의 "date" 필드를 읽는다.
2. 오늘 날짜와 비교하여 신선도를 판정한다.

판정 + 행동:
  fresh(~3일): 그대로 사용. Phase 1로 진행.
  stale(3~7일): ⚠️ 자동 트리거 실행.
    → macro 디렉토리(C:\Users\이미영\Downloads\에이전트\macro\)로 이동
    → PLUGIN-weekly-macro.md의 Step 1~10 수집 절차를 실행
    → latest.json 갱신 완료 확인
    → psf-monitor 디렉토리로 복귀, 갱신된 latest.json으로 Phase 1 진행
  expired(7일+): 🔴 자동 트리거 실행 (동일 절차).
    → 보고서에 "[macro 자동갱신 — 이전 N일 경과]" 태그 부착.

자동 트리거 규칙:
  수집자는 여전히 macro다. PSF가 macro의 수집 절차를 "대신 실행"하는 것.
  PSF가 독자적 MCP 수집 경로를 만들지 않는다.
  macro의 PLUGIN-weekly-macro.md + RULES.md + SKILL-macro-indicators.md를 그대로 따른다.
  갱신 결과는 macro/indicators/latest.json에 저장한다 (macro의 정본).
  PSF state.json에 "macro_auto_triggered": true, "trigger_reason": "stale|expired" 기록.

실패 시:
  MCP 접근 실패 등으로 수집 불가 → stale 데이터 그대로 사용.
  보고서에 "[macro 자동갱신 실패 — N일 전 데이터 사용]" 태그.
  사용자에게 "수동 /macro-weekly 실행 권고" 안내.
```

---

## 데이터 수집

### 정량 데이터 — Macro에서 읽기

```
경로: C:\Users\이미영\Downloads\에이전트\macro\indicators\latest.json
참조: macro/SKILL-macro-indicators.md

Phase 0에서 신선도 확인 + 자동 트리거 완료 후 이 단계에 도달한다.
이 시점에서 latest.json은 fresh 상태여야 한다.

PSF → Macro 매핑: collection.md 참조
★ PSF는 Macro의 데이터를 읽기만 한다. 직접 수집하지 않는다.
  (Phase 0의 자동 트리거는 macro의 수집 절차를 대행하는 것이지,
   PSF 고유의 수집 경로가 아니다.)
```

### 정성 데이터 — P층 독립 수집

```
원칙:
  각 Property(P1~P4)별로 맥락 기반 탐색을 실행한다.
  쿼리는 고정이 아니다. 직전 관측(state.json)에서 파생한다.

쿼리 생성 방법:
  1. state.json에서 해당 Property의 마지막 상태를 확인한다.
  2. "이 상태에서 다음에 일어날 수 있는 것은?"을 질문으로 만든다.
  3. "이 Property에서 놓치기 쉬운 것은?"도 별도 검색한다.

"특이사항 없음"도 반드시 명시한다. 검색 없이 생략 금지.
```

### 축 신호 탐색 — 맥락 기반 MCP 동원

```
원칙:
  모든 MCP를 매번 쓰지 않는다.
  "오늘의 데이터에서 답이 필요한 질문"이 소스를 결정한다.

사용 가능한 소스 카탈로그: axis-map.md §데이터 소스 카탈로그 참조
폴백 경로: collection.md §축 신호 MCP 폴백 경로 참조
```

---

## 관찰과 판정

### axis-map.md 프로토콜 실행

```
axis-map.md의 6단계를 실행한다.
모든 단계를 매일 깊이 할 필요 없다 — 변화의 크기가 깊이를 결정한다.

1단계: 변화 감지 — 뭐가 달라졌나?
2단계: 인과 추적 — 어디서 왔고, 어디로 가나?
3단계: 축 관련성 — 메가트렌드에 영향을 주는가? (axis-summary.md 참조)
4단계: 이상 탐지 — 모르는 것이 있는가?
5단계: 위험 거리 — 가장 가까운 위험은?
6단계: 전수 점검 — 놓친 것 없는가?
```

### P층 판정

```
원본 v3의 P1~P4 하위 속성(a/b/c)을 참조하여 각 Property를 판정한다.
판정 기준(🟢/🟡/🔴/⚫)은 원본 v3에 정의되어 있다.

★ 임계값은 절대 기준이 아니라 참고선이다.
  판정의 근거를 반드시 서술한다.
```

---

## 기록

```
1. state.json 갱신
   모든 Property 상태 + 수치 + 변경 사항 + alerts

2. history/ 스냅샷
   history/YYYY-MM-DD.json (core/snapshot.py save)

3. 경보 (자동)
   Link 상태 변경, 국면 전환, Divergence, 임계 접근

4. PM_핵심예측
   수치 범위 + 기한 필수. 모호한 서술 금지.
   예: "3/30까지 HY OAS 350bp 미돌파. 돌파 시 L7 재판정."

5. 누적 갱신 (accumulation)
   매일 state.json 저장 시 accumulation.weekly도 함께 갱신.
```

---

## 출력 — 보고서(핵심) + JSON(상세) 분리

```
★ 원칙: 보고서는 핵심만. 상세는 전부 state.json.
  보고서 = 사람이 읽는 것. 20줄 이내.
  JSON = 기계가 읽고, 필요할 때 사람이 열어보는 것. 제한 없음.

보고서 형식 (고정):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[날짜] | macro [🟢🟡🔴](점수) | PSF [🟢🟡🔴] | [축 상태] | [한 단어 키워드]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[전문가]
1. [전파+돈] PSF 전파 위치 + macro 레짐 + 핵심 제약/교란. (1줄)
2. [방향] 축 상태 + 비가역 변화 + 레짐 방향. (1줄)
3. [위험] 가장 가까운 분기점 + 유동성 + 특이 신호. (1줄)

[해석]
1. (2~3문장. 개인투자자 수준. 전문 용어를 일상어로.)
2. (2~3문장.)
3. (2~3문장.)

[감시]
  날짜 | 이벤트 | 심각도
  (변화가 있는 것만. 3~5건.)

[예측 — 검증일]
  (수치 범위 + 기한. 2~4건.)

상세 → state.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 통합 실행 원칙: 축+PSF를 한 번에

```
축 모니터링과 PSF 관측을 따로 실행하지 않는다.
하나의 실행에서 두 렌즈를 모두 적용한다.
```

---

## 모니터링 루프 트리거

```
상세: monitoring.md 참조

일일: "브리핑", "오늘 시장", "PSF 갱신", "축 모니터링" ← 모두 같은 실행
주간: "주간 리뷰", "축 리뷰"
월간: "월간 점검", "배관 점검" + 투영 확률 조정
분기: "분기 진단", "축 진단" + 투영 전면 재구성
긴급: "긴급 점검" + [사유]
수시: "KC 상태", "질문 상태"
투영: "12개월 투영", "시나리오", "전망"
```

---

## 투영 엔진

```
상세: projection-engine.md 참조

역할: 3시스템 관측을 입력으로, 12개월 시나리오를 산출.

실행 주기:
  분기 (Q Loop): 전면 재구성.
  월간 (M Loop): 확률 재조정.
  일일: 분기 조건 충족 시에만 보고서에 "투영 변화" 1줄 추가.
  긴급: 시나리오 분기 이벤트 시 즉시 재조정.
```

---

## 외부 연결

```
media-monitor: 상세 → ../media-monitor/interfaces-psf.md
  독립 모듈. 센티먼트 공유. 국면 전환 시 자동 트리거.

question-forge: 상세 → ../question-forge/interfaces-psf.md
  독립 모듈. 주간 리뷰 시 8대 질문 생성 연동.
```

---

## 후처리 (관측 완료 후)

```
관측 완료 시 자동 실행:

1. core/validate.py → state.json 스키마 검증
2. core/snapshot.py save → history/YYYY-MM-DD.json 저장 + delta 계산
3. core/autonomy.py scan → 이상 감지

도구 체인:
  python core/validate.py
  python core/snapshot.py save
  python core/autonomy.py scan
```

---

## 분리된 지침 파일 (필요 시 추가 로딩)

```
SKILL-autonomy.md     ← 자율 운영 (세션 시작 스캔, GUARDRAILS, 자율 수준)
SKILL-fail-evolve.md  ← F-테이블 + Self-Audit + 진화 규칙 + 불변 규칙
axis-summary.md       ← 축 요약 카드 (D Loop용. 상세는 axis.md)
```
