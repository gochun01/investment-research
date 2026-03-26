# Guardrails — reaction-monitor 자율 울타리

> reaction-monitor 독립 모듈의 자율 행동 경계를 정의한다.
> PSF 자율 운영 레이어와 독립. 이 문서가 reaction-monitor의 유일한 울타리.
> 기본 정책: Yellow Zone (승인 필요). 무승인 범위를 최소화한다.

---

## 원칙

```
1. 읽기/수집만 무승인. 쓰기/수정/삭제는 승인 필요.
2. 모든 자율 행동은 로그 기록.
3. 투자 판단 관련 행동은 절대 무승인 불가.
4. Watch 등록/종료/변경은 반드시 사용자 승인.
5. 울타리 자체의 수정은 사용자 승인 필요.
```

---

## Green Zone — 무승인 허용 (읽기 + 수집만)

```
데이터 읽기:
├── state.json 로딩
├── history/*.json 로딩
├── active-watches.json 로딩
└── config/event-calendar.json 로딩

데이터 수집 (MCP 도구 — 읽기 전용):
├── WebSearch 실행
├── Yahoo Finance, FRED, CoinGecko 등 가격/지표 조회
├── Firecrawl, Tavily 검색
└── 수집 결과를 대화창에 출력

자동 계산:
├── Watch 기한 도래 여부 계산
├── unresolved → Watch 변환 제안 생성 (적용은 승인 필요)
├── validate.py 실행 (검증 결과 출력)
└── 알림 텍스트 생성
```

---

## Yellow Zone — 승인 필요 (기본 정책)

**아래 모든 행동은 사용자에게 "실행할까요?" 확인 후 진행한다.**

```
상태 파일 수정:
├── state.json 갱신 (수집 결과 반영)
├── state.json의 unresolved 상태 변경 (open → resolved)
├── history/ 스냅샷 저장
└── reports/ HTML 생성

Watch 관리 (전체 승인 필요):
├── active-watches.json에 Watch 등록
├── Watch 체크 실행 (데이터 수집은 Green, 결과 저장은 Yellow)
├── Watch 스케줄 변경
├── Watch 종료 판정
└── Watch 삭제

이슈 관리:
├── system-issues.json에 이슈 적재
├── 이슈 상태 변경 (open → fixed/wontfix)
└── 이슈 severity 변경

설계 파일 수정:
├── SKILL.md 수정
├── CLAUDE.md 수정
├── references/ 파일 수정
├── GUARDRAILS.md 수정
└── core/*.py 수정

보고서:
├── render.py 실행 (HTML 생성)
└── 이벤트 히스토리 생성/갱신
```

### 승인 요청 형식

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ 승인 필요 — {행동 유형}
━━━━━━━━━━━━━━━━━━━━━━━━━━
행동: {구체적 행동}
대상: {파일/항목}
이유: {왜 이 행동이 필요한지}
━━━━━━━━━━━━━━━━━━━━━━━━━━
실행할까요?
```

---

## Red Zone — 금지

```
투자 행동:
├── 매수/매도 판단
├── 포지션 변경 제안을 "추천"으로 프레이밍
└── 특정 가격 진입/청산 지시

비가역 행동:
├── 파일/데이터 영구 삭제
├── state.json 초기화
└── history/ 일괄 삭제

매체/전문가 최종 판정:
├── "이 매체는 신뢰할 수 없다"는 영구 판정
├── "이 전문가는 틀렸다"는 영구 판정
└── 채널을 영구 차단/금지하는 판정
```

---

## 자율 행동 로그 형식

```
[AUTO] {timestamp} | {zone} | {action} | {target} | {result}

예:
[AUTO] 09:31 | GREEN  | LOAD    | state.json           | ✅
[AUTO] 09:31 | GREEN  | SCAN    | active-watches.json   | 2건 기한 도래
[AUTO] 09:32 | GREEN  | COLLECT | WebSearch "CLARITY"   | 5건 수집
[AUTO] 09:32 | YELLOW | PROPOSE | Watch W-UQ-006 체크    | ⏳ 승인 대기
[AUTO] 09:33 | YELLOW | SAVE    | state.json 갱신       | ✅ (승인 후)
```

---

## Green → Yellow 승격 조건

```
아래 조건 충족 시 현재 Yellow인 항목을 Green으로 승격 검토 가능.
승격은 이 GUARDRAILS.md 수정을 통해서만 가능 (승인 필요).

승격 검토 가능 조건:
├── 해당 행동이 10회 이상 승인 실행되었고
├── 1회도 문제가 발생하지 않았고
├── 되돌림이 가능한 행동이며
└── 사용자가 명시적으로 "이건 자동으로 해줘"라고 지시

현재 승격 후보: 없음 (운영 이력 부족)
```
