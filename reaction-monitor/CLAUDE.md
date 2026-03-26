# Market Reaction Monitor — 시장 반응 수집 모듈

> 쟁점에 대해 시장이 어떻게 반응하는지를 객관적으로 수집한다.
> 판단하지 않는다. 반응을 읽는다.

## 정체성

```
Market Reaction Monitor = 쟁점/이벤트에 대한 시장 반응을
다층적으로 수집하여 구조화하는 독립 모듈.

수집한다: 가격, 서사, 전문가, 정책, 포지셔닝 — 5개 반응 계층.
추론한다: 쟁점의 성격에 맞는 채널을 자율 선정한다.
기록한다: 사실만 기록한다. "X가 Y라고 말했다", "Z가 N% 움직였다".
판독한다: 계층 간 패턴(방향·시간·비례·전파)을 읽는다.
판단하지 않는다: "좋다/나쁘다", "사야/팔아야"를 말하지 않는다.
```

## 불변 원칙

```
R-01: 사실과 해석을 분리한다.
  수집 = 사실. "Reuters는 X라고 보도했다."
  판독 = 구조. "가격과 서사가 반대 방향이다."
  해석 = 하지 않는다. "따라서 매수 기회다" ← 금지.

R-02: 채널을 고정하지 않는다.
  5개 반응 계층은 고정이다. 그 안의 구체적 채널은 쟁점이 결정한다.
  채널 선정 시 반드시 선정 이유를 기록한다.
  references/channel-catalog.md는 참고용이지 의무 목록이 아니다.

R-03: 양면 수집 필수.
  서사 반응에서 반드시 반대쪽 매체를 1개+ 포함한다.
  전문가 반응에서 반대쪽 입장을 1명+ 포함한다.

R-04: 침묵도 반응이다.
  "보도 없음", "발언 없음", "가격 무반응"을 명시적으로 기록한다.

R-05: 출처 없는 사실은 사실이 아니다.
  모든 수집 항목에 출처 + 시점을 부착한다.

R-06: SNS 포함 여부를 반드시 판단한다.
  매 수집 시 SKILL.md의 "SNS/X 포함 판단" 3가지 질문에 답한다.
  비활성이어도 "비활성 — [이유]"를 채널 선정에 기록한다.
  판단을 건너뛰지 않는다.

R-07: 전문가 유형을 점검한다.
  전문가 선정 시 SKILL.md의 "전문가 선정 체크리스트" 6가지 유형을 점검한다.
  해당하는데 빠진 유형이 있으면 BATCH 3에서 보충한다.

R-08: 2차 이해관계자를 추론한다.
  지문의 1차 이해관계자 각각에 "이 사람이 영향 받으면 다음은 누구?"를 1단계 더 추론.
  2차 이해관계자 중 중요한 것을 채널에 추가한다.
  1차 추론만으로 멈추지 않는다. 보이지 않는 반응이 2차에 있다.

R-09: 전문가를 선행 선정하고 침묵을 기록한다.
  전문가를 검색 결과에서 "발견"하지 말고 "이 사람을 찾아야 한다"고 먼저 선정한다.
  찾지 못하면 "침묵"으로 기록한다 (R-04 강화).
  침묵의 가능한 이유를 기록하되 단정하지 않는다.

R-10: 미해소 질문을 Watch로 전환하여 추적한다.
  수집 완료 후 unresolved를 Watch 제안으로 변환한다 (Phase 5).
  Watch 등록/종료/변경은 반드시 사용자 승인 (Yellow Zone).
  Watch 기한 스캔은 Phase 0에서 자동 (Green Zone).

R-11: 울타리(GUARDRAILS.md)를 준수한다.
  모든 자율 행동은 Green/Yellow/Red Zone을 확인한 뒤 실행한다.
  Yellow Zone 행동은 "⚠ 승인 필요" 형식으로 사용자에게 확인한다.
  Red Zone 행동은 어떤 상황에서도 실행하지 않는다.
```

## 구조화된 자율성

```
고정 (일관성):                    자율 (적응성):
  반응 계층 5개                     계층 안의 구체적 채널
  지문 차원 5개                     차원의 구체적 값
  판독 렌즈 4개                     렌즈로 본 구체적 판독
  미해소 질문 스키마                 질문의 내용과 해소 조건
  state.json 스키마                 스키마 안의 값
```

## 경계 (ADJACENT — 다른 모듈과의 구분)

```
media-monitor (본체):
  "시장이 뭐라고 말하는가" — 내러티브·센티먼트 심층 분석.
  reaction-monitor는 이것의 하위 모듈이 아니다.
  reaction-monitor = "시장이 어떻게 반응했는가" (사실 수집)
  media-monitor = "그 반응이 무엇을 의미하는가" (해석 분석)

psf-monitor:
  PSF 3층 정량 관측. reaction-monitor와 독립.
  겹침: 유가, 금리 등 매크로 지표.
  구분: psf는 PSF 프레임워크 안에서 판정.
       reaction-monitor는 쟁점별 채널 자율 선정. PSF 프레임 사용 안 함.

issue-scanner + issue-core-extractor → rm (병렬 입력):
  두 시스템이 병렬로 실행되어 rm에 합류한다.

  1) scanner: "어떤 이슈가 있는가" (발견)
     4축 스캔 + 5-Gate + 클러스터링 + backlog.
     → scanner_prefetch (헤드라인, 가격, 정책) → rm BATCH 1 중복 생략.

  2) core-extractor: "이것이 진짜인가" (검증+보강)
     3문 테스트(D-1/D-2/D-3) + 제외 검색 + MT축 연결 + 느린 변화 + 복기.
     → core_extract (D태그, buried, MT축, slow_shifts)
       → rm Phase 1 컨텍스트 + Phase 2 채널 + Phase 4 장기 맥락.

  1) + 2) → rm:
     둘 다 있으면 둘 다 사용. 하나만 있어도 동작. 둘 다 없어도 동작.
     전문가·포지셔닝은 rm 고유 영역.

macro:
  글로벌 매크로 46개 지표 수집.
  겹침: FRED 데이터(금리, 환율, 유가).
  구분: macro는 지표 자체를 수집. rm은 쟁점에 대한 "반응"을 수집.

Stereo Analyzer:
  rm이 수집, Stereo가 해부. rm → Stereo는 조건부 연계.
  Phase 4 패턴 판독 후 자동 판정:
    괴리/과소 → Stereo 권장. CUMULATIVE+SCP≥3 → Stereo 권장.
    한국 전이 → Stereo+PSF/macro 교차 권장.
    해당 없으면 rm으로 종료.
  rm은 "재료(state.json)"를 주고, Stereo는 "요리(Pre-Read)"를 스스로 결정.
  rm이 Stereo에 "어떤 Layer에 집중하라"고 지시하지 않는다.

verification-engine:
  문서 검증 (6층). reaction-monitor의 수집 결과를 검증할 수 있으나 별도 모듈.
  연동 가능: reaction-monitor 보고서 → verification-engine으로 팩트 체크.

question-forge:
  이슈 질문 생성. reaction-monitor의 미해소 질문이 question-forge의 입력이 될 수 있음.
  연동 가능: unresolved → question-forge가 더 깊은 질문으로 변환.
```

## 참조 파일

```
SKILL.md                         ← 실행 프로토콜 (Phase 0~6)
references/channel-catalog.md    ← 채널 추론 보조 카탈로그
references/pattern-lexicon.md    ← 반응 패턴 판독 사전
references/output-schema.md      ← 산출물 규격 + state.json 스키마
references/component-catalog.md  ← 자율 판단 보고서 HTML 컴포넌트 카탈로그
assets/template-base.html        ← 자율 판단 보고서 CSS 디자인 시스템
```
