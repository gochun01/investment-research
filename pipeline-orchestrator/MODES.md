# 파이프라인 실행 모드 — 상황별 최적 조합

> 항상 풀 실행이 최선은 아니다. 데이터 축적은 최우선이지만,
> 이미 축적된 데이터를 재수집하는 것은 낭비다.
> 상황에 따라 최적 조합을 선택한다.

---

## 모드 판정 흐름

```
입력을 받으면 아래 순서로 모드를 판정한다:

Q1: 이슈가 새로운가, 기존 TC에 있는가?
  새로운 이슈 → Q2로
  기존 TC 있음 → Q3으로

Q2: 사용자가 스캔을 요청했는가, 특정 이슈를 줬는가?
  "오늘 이슈 스캔" → Mode A (풀 스캔)
  특정 이슈/기사 → Mode B (타겟 분석)

Q3: 무엇이 변했는가?
  새 이벤트 발생 → Mode C (델타)
  정기 체크 (Watch 만기) → Mode D (체크)
  임계값 재조정 → Mode E (재보정)
```

---

## Mode A: 풀 스캔 (Full Pipeline)

```
트리거: "풀 파이프라인", "이슈 스캔", "오늘 뭐 봐야 해"
구조:   scanner + macro → [선택] → rm + core + PSF → stereo
Agent:  5개 (A+B 병렬, C+D+E 병렬)
MCP:    ~66-94 (체감 ~29)
용도:   주 1~2회. 새 이슈 발굴 + 전체 매크로 갱신.
```

## Mode B: 타겟 분석 (Targeted)

```
트리거: 특정 기사/이슈 + "분석해줘", "stereo 돌려줘"
구조:   [scanner 스킵] → rm + core → stereo ← PSF(기존)
Agent:  2개 (C+D 병렬) + 메인(stereo)
MCP:    ~35-45 (체감 ~15)
용도:   수시. 특정 이슈를 깊이 분석. scanner 불필요(이슈 이미 특정).
조건:   macro가 7일 이내면 스킵. PSF도 7일 이내면 기존 state 사용.
```

## Mode C: 델타 분석 (Delta)

```
트리거: 기존 TC의 이슈에 새 이벤트 발생 (뉴스, 정책 변경 등)
구조:   [scanner 스킵] → rm(delta) → stereo(delta) ← PSF(기존)
Agent:  1개 (C: rm delta) + 메인(stereo delta)
MCP:    ~20-30 (체감 ~10)
용도:   수시. TC 카드의 Phase 전환 판단. 이전 분석 위에서 변화만 추적.
조건:   core-extractor 스킵 (3문 테스트는 최초 1회만).
        rm은 BATCH 1만 (prefetch 없이 가격+서사 변화 확인).
```

## Mode D: 정기 체크 (Watch Check)

```
트리거: Watch 만기 도래 (daily-tracking-scan 알림 또는 수동)
구조:   Watch data_sources로 MCP 수집 → 결과 기록 → TC 갱신
Agent:  0개 (메인 스레드에서 직접)
MCP:    ~3-8
용도:   일별/주별. Watch의 질문에 답하고 completed_checks에 기록.
조건:   분석 없음. 데이터만 수집하고 상태만 갱신.
        KC 상태 변화 있으면 사용자에게 알림.
```

## Mode E: 임계값 재보정 (Recalibration)

```
트리거: 월 1회 정기 또는 판 전환 이벤트
구조:   macro 수집 → PSF 매핑 → TC 카드별 Trigger-KC 재검토
Agent:  1개 (B: macro) + 메인(PSF + KC 검토)
MCP:    ~30-40 (macro 27 + PSF 3-5 + 검증 MCP)
용도:   월 1회. 임계값 설계 7항목 체크리스트로 전체 TC 재검토.
점검:   ① 변동성 체제 변했는가 (VIX 밴드)
        ② 가격 수준 구조적 이동했는가 (새 균형가)
        ③ 인과 체인 작동 중인가 (전이 비율)
        ④ 경보 피로 발생했는가 (Watch/Alert 상시 점등)
산출:   TC 카드의 scenarios.kc 업데이트 + 변경 전/후 기록
```

---

## 모드별 비교

```
                    Agent  MCP실제  MCP체감  용도       빈도
Mode A (풀 스캔)     5     66-94    ~29     발굴+갱신   주 1~2회
Mode B (타겟)        2+1   35-45    ~15     깊이 분석   수시
Mode C (델타)        1+1   20-30    ~10     변화 추적   수시
Mode D (체크)        0      3-8      3-8    Watch 확인  일별
Mode E (재보정)      1+1   30-40    ~20     KC 재조정   월 1회
```

---

## 모드 자동 판정 규칙

```
pipeline-orchestrator가 입력을 받으면:

1. "스캔", "풀 파이프라인", "전체 분석" → Mode A
2. 특정 기사/이슈 + "분석" → Phase 0 Gate로 TC 존재 여부 확인
   TC 없음 → Mode B
   TC 있음 → "새 이벤트인가?" 판단
     새 이벤트 있음 → Mode C
     없음 (정기 체크) → Mode D
3. "임계값 재조정", "KC 체크", "재보정" → Mode E
4. daily-tracking-scan 알림 → Mode D

사용자가 명시적으로 모드를 지정할 수도 있다:
  "풀로 해줘" → Mode A 강제
  "델타만" → Mode C 강제
  "Watch만 체크" → Mode D 강제
```

---

## Phase 0에서 모드 출력

```
분석 시작 시 모드를 출력 상단에 명시:

⚙️ 파이프라인 모드: [A/B/C/D/E] — [이유 1줄]
📂 과거 맥락: [있음/없음]
🔄 재사용: macro [오늘/N일전], PSF [오늘/N일전], scanner [오늘/스킵]
```
