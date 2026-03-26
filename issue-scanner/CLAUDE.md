# Issue Scanner — 글로벌 이슈 스캐너

> 글로벌 미디어를 자동 스캔하여 5~10개 투자 관련 쟁점을 발굴하고,
> 근인(root cause) 기준으로 클러스터링한 뒤,
> 사용자 승인을 받아 reaction-monitor에 전달하는 전방 모듈.

## 정체성

```
Issue Scanner = reaction-monitor의 전방 모듈.

발견한다: 오늘 시장이 반응해야 할 쟁점 후보를 스캔한다.
묶는다:   같은 뿌리의 쟁점을 하나의 클러스터로 묶는다.
보여준다: 사용자에게 목록을 제시하고 선택을 받는다.
전달한다: 승인된 클러스터를 reaction-monitor의 입력으로 넘긴다.
판단하지 않는다: "이게 중요하다"고 단정하지 않고, 왜 후보인지 근거를 제시한다.
```

## 불변 원칙

```
IS-01: 스캔은 자동, 실행은 승인.
  스캔과 클러스터링은 Green Zone. reaction-monitor 전달은 Yellow Zone.
  사용자가 목록을 보고 선택하기 전에 자동 실행하지 않는다.

IS-02: 근인(root cause)으로 묶는다.
  "이란 휴전안" + "호르무즈 원자재 충격" + "걸프 공습" = 1 클러스터 (근인: 미-이란 전쟁).
  표면 키워드가 아닌 인과적 뿌리로 묶는다.

IS-03: 선택되지 않은 이슈를 버리지 않는다.
  미선택/미클러스터 이슈는 backlog에 기록.
  다음 스캔에서 재등장하거나 사용자가 승격(promote) 가능.
  30일 미등장 시 자동 아카이브.

IS-04: 외부 시드를 재활용한다.
  가능하면 당일 GHS 보고서, heartbeat KC 알림, macro 레짐 판정을
  씨앗(seed)으로 활용한다. 없으면 독립 스캔.

IS-05: 스캔은 breadth, depth는 rm이.
  이슈당 소스 2~3개 확인이면 충분하다.
  깊이 있는 반응 수집은 reaction-monitor가 한다.

IS-06: 한국어, 간결하게.
  류희발님은 비개발자. "실행할까요?" + 번호 선택이면 충분.
  목록 제시는 한눈에 파악 가능한 형태로.

IS-07: 기존 추적과 중복을 방지한다.
  reaction-monitor의 state.json과 active-watches.json을 읽어서
  이미 수집 중/추적 중인 쟁점은 태그 표시.
  단순 반복은 탈락. 새 전개(후속)는 통과.

IS-08: 울타리(GUARDRAILS.md)를 준수한다.
  reaction-monitor의 Green/Yellow/Red 체계를 동일하게 적용한다.
```

## 구조화된 자율성

```
고정 (일관성):                    자율 (적응성):
  4축 스캔 구조 (A/B/C/D)          각 축의 구체적 쿼리
  5-Gate 필터 구조                  G2/G3의 LLM 추론 내용
  사각지대 점검 4개 질문            점검 결과에 따른 보충 범위
  클러스터링 기준 (근인)            근인의 구체적 판정
  backlog 스키마                   backlog 안의 값
  사용자 제시 형식                  제시되는 이슈 내용
```

## 경계 (ADJACENT)

```
reaction-monitor:
  scanner가 발견 → rm이 수집.
  scanner는 rm의 state.json을 읽기만 한다. 직접 수정 금지.
  전달(handoff)은 Yellow Zone.

  ★ 패스스루 (v1.1):
  scanner가 이미 수집한 데이터(헤드라인, 가격, 정책)를
  scanner_prefetch로 rm에 전달한다.
  rm은 prefetch를 BATCH 1 기반으로 사용하고 중복 수집을 생략한다.
  전문가·포지셔닝은 scanner가 수집하지 않으므로 rm이 항상 전체 수집.
  prefetch가 없으면(rm 단독 실행) 기존대로 전체 수집. 영향 없음.

heartbeat:
  heartbeat KC 알림을 D축 시드로 활용 가능.
  KC-12(환율 1,500) 발동 → scanner의 D축에 "환율 스트레스" 투입.
  독립 시스템. heartbeat가 scanner를 호출하지 않음.

macro:
  macro 레짐 판정을 컨텍스트로 참조 가능.
  독립 시스템.

global-headline-scanner:
  GHS 보고서가 있으면 buried_issues, plate_detection을 D축 시드로 활용.
  GHS는 깊이(30~50 AC, 서사 분리). scanner는 넓이(5~10 이슈, 트리아지).
  별개 도구. GHS가 없어도 scanner는 독립 실행 가능.
```

## 참조 파일

```
SKILL.md                         ← 실행 프로토콜 (Phase S0~S5)
GUARDRAILS.md                    ← Green/Yellow/Red Zone
작동원리.md                       ← 3-Pass 추출 엔진 상세
references/scan-sources.md       ← 스캔용 소스 + 쿼리 가이드
```
