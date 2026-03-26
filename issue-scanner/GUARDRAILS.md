# Guardrails — Issue Scanner 자율 울타리

> reaction-monitor 패턴을 상속. 스캔은 자유, 전달은 승인.

---

## 원칙

```
1. 읽기/스캔만 무승인. 전달/저장은 승인 필요.
2. 사용자가 목록을 보기 전에 reaction-monitor를 자동 실행하지 않는다.
3. 투자 판단 관련 행동은 절대 무승인 불가.
4. backlog 아카이브는 자동(30일 규칙). 삭제는 승인 필요.
5. 울타리 자체의 수정은 사용자 승인 필요.
```

---

## Green Zone — 무승인 허용

```
데이터 읽기:
├── scan-state.json 로딩
├── backlog.json 로딩
├── ../reaction-monitor/state.json 로딩 (읽기 전용)
├── ../reaction-monitor/active-watches.json 로딩 (읽기 전용)
├── heartbeat/macro/GHS 상태 로딩 (읽기 전용)
└── history/*.json 로딩

MCP 스캔 (검색만):
├── Tavily search 실행 (A/B/C축)
├── WebSearch 실행 (B/C/D축)
├── Firecrawl search 실행 (선택적)
└── 검색 결과를 대화창에 출력

자동 처리:
├── 5-Gate 필터링 + 점수 산출
├── 사각지대 보정 계산
├── 근인 클러스터링
├── backlog 30일 자동 아카이브 (Phase S0)
├── 사용자 제시 포맷 생성
└── 이전 backlog appearance_count 갱신
```

---

## Yellow Zone — 승인 필요

**아래 모든 행동은 사용자에게 확인 후 진행한다.**

```
reaction-monitor 전달:
├── 선택된 클러스터/이슈를 rm Phase 1 입력으로 전달
└── rm의 state.json에 scanner_origin 기록

상태 파일 수정:
├── scan-state.json 갱신
├── backlog.json에 미선택 이슈 저장
├── history/ 스냅샷 저장
└── backlog 이슈 수동 승격 (promote)

설계 파일 수정:
├── SKILL.md 수정
├── CLAUDE.md 수정
├── GUARDRAILS.md 수정
└── references/ 파일 수정
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
├── "이 이슈가 중요하니 반드시 봐야 한다"는 강제
└── 특정 가격 진입/청산 지시

비가역 행동:
├── backlog 영구 삭제 (아카이브는 OK, 삭제는 금지)
├── scan-state.json 초기화
└── history/ 일괄 삭제

reaction-monitor 직접 수정:
├── rm의 state.json 직접 쓰기
├── rm의 active-watches.json 직접 쓰기
└── rm의 events/ 직접 쓰기
(전달(handoff)만 가능. 직접 수정 금지.)
```
