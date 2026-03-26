---
name: pipeline-orchestrator
description: >
  6개 시스템을 3 Phase 병렬 파이프라인으로 실행하는 지휘자.
  scanner+macro(병렬) → rm+core-extractor+PSF(병렬) → stereo(종합).
  풀 실행만. 축약 금지. 데이터 축적 최우선.
  트리거: "풀 파이프라인", "전체 분석", "issue부터 stereo까지",
  "오늘 이슈 스캔해서 분석까지", "/파이프라인".
---

# Pipeline Orchestrator v1.0 — 실행 프로토콜

---

## Phase 0: 사전 점검

```
1. macro stale 체크
   Read: macro/indicators/latest.json → date 필드 확인
   IF date == 오늘 → macro_skip = true (Phase 1에서 Agent B 스킵)
   IF date != 오늘 → macro_skip = false (Agent B 실행)

2. scanner 상태 체크
   Read: issue-scanner/scan-state.json (있으면)
   → last_scan이 오늘이고 사용자가 "다시 스캔" 안 했으면 스킵 가능
   → 기본은 매번 실행

3. PSF 상태 체크
   Read: psf/state.json → last_updated 확인
   → macro가 스킵이고 PSF도 오늘이면 PSF도 스킵 가능

4. 입력 확인
   사용자가 특정 기사/주제를 줬는가?
   YES → scanner S1에서 해당 주제를 seed로 포함
   NO  → scanner 오픈 스캔
```

---

## Phase 1: 발견 + 수집 (병렬)

**Agent tool로 2개 동시 실행.**

```
┌─────────────────────────────────────────────────────────────┐
│ Agent A: scanner                                             │
│                                                              │
│ 프롬프트:                                                     │
│   "issue-scanner 프로토콜을 풀 실행하라.                        │
│    CLAUDE.md: [scanner 경로]/CLAUDE.md                        │
│    SKILL.md:  [scanner 경로]/SKILL.md                        │
│    Phase S0~S4까지 실행하고 S5 제시용 결과를 반환하라.           │
│    S5(사용자 선택)는 반환만. 직접 실행하지 않는다.               │
│    scan-state.json, backlog.json, history/SCAN-*.json 저장.   │
│    [사용자 seed가 있으면: seed 명시]"                           │
│                                                              │
│ 산출물:                                                       │
│   - issue-scanner/history/SCAN-YYYY-MM-DD.json               │
│   - issue-scanner/scan-state.json                            │
│   - issue-scanner/backlog.json                               │
│   - S5 제시 텍스트 (클러스터 + 독립 이슈 목록)                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Agent B: macro (macro_skip == false일 때만)                   │
│                                                              │
│ 프롬프트:                                                     │
│   "macro 주간 수집을 실행하라.                                  │
│    CLAUDE.md: [macro 경로]/CLAUDE.md                          │
│    SKILL: PLUGIN-weekly-macro.md                             │
│    46개 지표(핵심 27 + 보조 19)를 MCP로 수집하고               │
│    indicators/latest.json을 갱신하라.                          │
│    indicators/YYYY-MM-DD.json 스냅샷도 저장."                  │
│                                                              │
│ 산출물:                                                       │
│   - macro/indicators/latest.json (갱신)                       │
│   - macro/indicators/YYYY-MM-DD.json (스냅샷)                 │
└─────────────────────────────────────────────────────────────┘
```

**Phase 1 완료 후: 오케스트레이터가 scanner S5 결과를 사용자에게 제시.**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 오늘의 이슈 스캔 — [날짜]
   스캔 소스 [N]건 → 이슈 [M]건 → 클러스터 [K]개
   macro: [갱신 완료 / 오늘자 기존 사용]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[scanner S5 형식 그대로 출력]

어떤 것을 분석할까요?
  예: "1" / "1, 2" / "전부" / "패스"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**사용자 응답 대기. 이것이 유일한 승인 지점.**

- "패스" → 전부 backlog 저장. 파이프라인 종료.
- "1" / "1, 2" / "전부" → 선택된 항목으로 Phase 2 진입.

---

## Phase 2: 반응 + 검증 + 매핑 (병렬)

**사용자 선택 완료 후, Agent tool로 3개 동시 실행.**

```
┌─────────────────────────────────────────────────────────────┐
│ Agent C: reaction-monitor                                    │
│                                                              │
│ 프롬프트:                                                     │
│   "reaction-monitor 프로토콜을 풀 실행하라.                     │
│    CLAUDE.md: [rm 경로]/CLAUDE.md                             │
│    SKILL.md:  [rm 경로]/SKILL.md                             │
│    입력 이슈: [선택된 클러스터/이슈 — scanner S6 핸드오프 형식]  │
│    scanner_prefetch: [SCAN JSON에서 추출]                     │
│    Phase 0~4.5까지 풀 실행.                                    │
│    Phase 5(Watch 등록)는 제안만 반환. 자동 등록 안 함.          │
│    state.json, history/*.json 저장.                           │
│    BATCH 1·2·3 모두 실행. 축약 금지.                           │
│    R-03(양면 수집), R-09(전문가 선행), R-04(침묵 기록) 준수."   │
│                                                              │
│ 산출물:                                                       │
│   - reaction-monitor/state.json                              │
│   - reaction-monitor/history/YYYY-MM-DD-*.json               │
│   - Phase 4 패턴 판독 결과                                    │
│   - Phase 4.5 Stereo 연계 판정                                │
│   - Phase 5 Watch 제안 목록                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Agent D: core-extractor                                      │
│                                                              │
│ 프롬프트:                                                     │
│   "issue-core-extractor 프로토콜을 실행하라.                    │
│    SKILL.md: [core-extractor 경로]/SKILL.md                  │
│    입력: [선택된 클러스터/이슈 — scanner 결과]                  │
│    3문 테스트(D-1/D-2/D-3) 실행.                               │
│    제외 검색(묻힌 것) 실행.                                     │
│    메가트렌드 축 연결(MT-01~07) 실행.                           │
│    느린 변화(3개월 추세) 확인.                                  │
│    core_extract 구조로 결과 반환."                              │
│                                                              │
│ 산출물:                                                       │
│   - core_extract JSON (rm과 stereo가 소비)                    │
│   - 3문 테스트 결과 (통과/탈락/보류)                            │
│   - MT 축 연결 결과                                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Agent E: PSF (psf_skip == false일 때만)                       │
│                                                              │
│ 프롬프트:                                                     │
│   "PSF 매핑을 실행하라.                                        │
│    CLAUDE.md: [psf 경로]/CLAUDE.md                            │
│    SKILL.md:  [psf 경로]/SKILL.md                            │
│    macro 데이터: macro/indicators/latest.json 읽기             │
│    3층 매핑 (판-구조-흐름) 실행.                                │
│    state.json 갱신. history/ 스냅샷 저장."                     │
│                                                              │
│ 산출물:                                                       │
│   - psf/state.json (갱신)                                    │
│   - psf/history/YYYY-MM-DD.json (스냅샷)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 3: 입체 분석 (메인 스레드)

**Phase 2의 3개 에이전트 모두 완료 후, 메인 스레드에서 Stereo 실행.**

```
Stereo 실행 전 입력 조립:
  1. Read: reaction-monitor/state.json → 5계층 반응 + 4렌즈 패턴
  2. Read: core-extractor 결과 → 3문 테스트 + MT 연결 + 느린 변화
  3. Read: psf/state.json → 판·구조·흐름 현재 상태
  4. Read: Stereo Analyzer/history/ + tracking/cards/ → Phase 0 Gate (과거 맥락)

Stereo 실행:
  CLAUDE.md: [stereo 경로]/CLAUDE.md
  SKILL.md:  [stereo 경로]/SKILL.md

  ★ Phase 0 Gate 반드시 먼저 (history/ + tracking/ 스캔)
  ★ Pre-Read에서 rm 패턴(괴리/과소)과 PSF 상태를 참조
  ★ L4에 core-extractor의 MT 축 연결 반영
  ★ L5에 PSF의 구조·흐름 상태 반영
  ★ L7에 rm의 Watch 제안 통합

산출물:
  - Stereo Analyzer/history/YYYY-MM-DD-*.json
  - Stereo Analyzer/tracking/cards/TC-NNN-*.json
  - git commit + push (tracking-cards 브랜치)
```

---

## Phase 4: 파이프라인 로그 + 마무리

```
1. 파이프라인 로그 저장
   pipeline-orchestrator/history/PIPE-YYYY-MM-DD-NNN.json

   {
     "pipe_id": "PIPE-YYYYMMDD-NNN",
     "date": "YYYY-MM-DD",
     "input": "사용자 입력 요약",
     "selected_issues": ["클러스터/이슈 목록"],

     "phase_1": {
       "scanner": {"status": "완료", "issues_found": N, "clusters": K},
       "macro": {"status": "완료|스킵", "reason": "오늘자 기존"}
     },
     "phase_2": {
       "rm": {"status": "완료", "pattern": "분열|수렴|괴리|침묵"},
       "core_extractor": {"status": "완료", "3q_pass": N, "mt_linked": N},
       "psf": {"status": "완료|스킵", "regime": "risk-on|neutral|risk-off"}
     },
     "phase_3": {
       "stereo": {"id": "SA-YYYYMMDD-NNN", "scp": N, "verdict": "repeat|shift|ambiguous"},
       "tc_card": "TC-NNN",
       "git_push": true
     },

     "total_mcp_calls": N,
     "total_agents": 5,
     "pipeline_complete": true
   }

2. rm Watch 제안 표시 (승인 필요)
   Phase 2에서 rm이 제안한 Watch 목록을 사용자에게 제시.
   승인 시 active-watches.json에 저장.

3. 최종 요약 출력
   1줄: 핵심 발견
   TC 카드: 번호 + 시나리오 요약
   다음 확인일: 추적 지표 기준
```

---

## 에이전트 프롬프트 규칙

```
각 Agent에 반드시 포함할 것:

1. 해당 시스템의 CLAUDE.md + SKILL.md 전체 경로
   "이 파일들을 Read하고 프로토콜을 따르라"

2. 풀 실행 지시
   "축약하지 마라. 모든 Phase를 실행하라. MCP 호출을 줄이지 마라."

3. 산출물 저장 지시
   "결과를 [경로]에 JSON으로 저장하라"

4. 핸드오프 데이터 (이전 Phase의 산출물)
   Agent C(rm): scanner_prefetch + 선택된 이슈
   Agent D(core): 선택된 이슈
   Agent E(PSF): macro/indicators/latest.json 경로

5. 반환 지시
   "완료 후 핵심 결과를 요약하여 반환하라"
```

---

## 에러 처리

```
Agent 실패 시:
  Phase 1: scanner 실패 → 파이프라인 중단. macro만 완료해도 의미 없음.
           macro 실패 → PSF를 기존 state.json으로 실행. 경고 출력.

  Phase 2: rm 실패 → stereo에 rm 결과 없이 진행 (품질 저하 경고).
           core-extractor 실패 → stereo에 core 결과 없이 진행 (허용).
           PSF 실패 → stereo에 PSF 없이 진행 (기존 state.json 사용).

  Phase 3: stereo 실패 → 파이프라인 실패. Phase 2 결과는 이미 저장됨.

원칙:
  Phase 2 에이전트 1개 실패 ≠ 파이프라인 중단.
  나머지 결과로 stereo 진행하되 "불완전" 태그 부착.
  Phase 1 scanner 실패 = 파이프라인 중단 (입력이 없으므로).
```
