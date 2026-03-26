# Stereo Analyzer — 자율 실행 울타리 (Guardrails)

> 자율이란 제한 없음이 아니라, 제한 안에서의 자유다.

---

## Green Zone (자율 실행 가능)

아래 행위는 별도 승인 없이 자율적으로 수행한다.

```
데이터 수집:
  - Firecrawl로 기사 전문 수집
  - Tavily로 관련 기사 2~3건 추가 수집
  - Notion DB에서 이전 분석 검색

Pre-Read 판독:
  - Type 분류 (POLICY/MACRO/STRUCT/EVENT/NARR/NOISE)
  - SCP 판독 (0~5)
  - Urgency 판정 (URGENT/WATCH/SLOW)
  - 감정 분리 (감정 감지 시 자동 발동)
  - Context Router로 분석 전략 자율 결정

7-Layer 분석:
  - L1~L7 전체 해부 (Pre-Read 라우팅에 따른 선택적 깊이)
  - NOISE 판정 시 L1만으로 조기 종료
  - 프레이밍 태그 식별 (framing-catalog.md 참조)
  - 2차 효과 패턴 적용 (second-order-patterns.md 참조)

되먹임 순회:
  - FB-1~FB-3 선택적 실행 (Type에 따라)
  - FB-4 최종 대조 (항상 실행)
  - [FB 보강] 태그 부여

돌발 질문 생성:
  - 5가지 렌즈 중 적합한 것 선택
  - 최소 1개, 최대 3개 생성

불확실성 지도:
  - Layer별 확신도 자가 진단
  - 가장 약한 고리 식별 + 보강 방법 제시

출력:
  - 텍스트 출력 템플릿 (SKILL.md 형식)
  - HTML 보고서 생성 (core/render_adaptive.py)
  - history/ 에 분석 스냅샷 저장

자기 점검:
  - errors.md 셀프검증 체크리스트 실행
  - 오류 발견 시 errors.md 기록
```

---

## Yellow Zone (주의 필요 — 사용자 확인 권장)

아래 행위는 수행 전에 사용자에게 의도를 알리고 확인을 받는 것이 바람직하다.

```
구조 변경:
  - SKILL.md의 Phase 구조나 Layer 정의 수정
  - 새로운 Layer(L8 등) 추가 제안
  - Pre-Read 라우팅 규칙 변경

코드↔스키마 변경 (O-01 방어):
  - render_adaptive.py 수정 시 SCHEMAS.md 키 이름 대조 필수
  - SCHEMAS.md 키 변경 시 render_adaptive.py 동시 수정 필수
  - 한쪽만 바꾸면 HTML 출력에서 빈칸/누락 발생
  - 되먹임 경로(FB-1~FB-4) 수정

레퍼런스 변경:
  - references/framing-catalog.md에 새 프레이밍 패턴 추가
  - references/second-order-patterns.md에 새 패턴 추가
  - autonomous-thinking-guide.md 판단 기준 수정

스키마 변경:
  - SCHEMAS.md의 JSON 스키마 필드 추가/제거
  - SCP 스케일 재정의 (0~5 범위 변경)
  - 확신도 스케일 변경

모드 변경:
  - 새로운 분석 모드 추가
  - 기존 모드의 트리거 조건 변경

외부 연동:
  - PSF연결 모드에서 PSF state.json 직접 참조
  - verification-engine에 분석 결과 전달
  - macro 데이터 직접 읽기
```

---

## Red Zone (금지 — 절대 자율 실행 불가)

아래 행위는 어떤 상황에서도 자율적으로 수행할 수 없다.

```
투자 관련:
  - 투자 권고 ("사세요", "파세요", "비중 조절")
  - 가격 예측 ("X원까지 간다", "바닥이다")
  - 특정 종목 매매 시점 제안

감정 관련:
  - 공포 증폭 ("폭락합니다", "위험합니다, 즉시 행동하세요")
  - 탐욕 자극 ("지금 안 사면 후회합니다")
  - 사용자 감정을 분석 방향에 의도적으로 반영

시스템 파괴:
  - SKILL.md 삭제 또는 핵심 구조 임의 변경
  - errors.md 오류 기록 삭제 (해결 표시는 가능, 삭제는 불가)
  - GUARDRAILS.md Red Zone 자기 수정
  - history/ 기존 스냅샷 삭제 또는 변조
  - CLAUDE.md 불변 원칙 수정

확신 표현:
  - 예측을 확정형으로 표현 ("~할 것이다")
  - Kill Condition 없는 판단 제시
  - 불확실성 지도 생략
```

---

## 이상 탐지 (Anomaly Detection)

자동으로 감지하고 경고해야 할 이상 패턴:

### A-01: SCP 오판

```
증상: NOISE로 판정했으나 실제로는 구조 변화 이슈 (과소 판독)
      또는 EVENT를 STRUCT로 판정하여 불필요한 심층 분석 (과대 판독)
탐지: FB-4에서 "처음과 크게 달라졌다" → SCP 재점검 트리거
      분석 도중 새 팩트가 나와 Type/SCP가 변해야 하는 경우
조치: Pre-Read 재실행 + 분석 전략 수정 + errors.md 기록
```

### A-02: L2 팩트 충돌 미해소

```
증상: L2에서 🔴(충돌) 표시된 팩트가 L7까지 해소되지 않음
탐지: L7 완료 시점에서 L2의 🔴 팩트 목록 재점검
조치: 충돌이 해소 불가능하면 불확실성 지도에 명시 + 추적 지표에 포함
```

### A-03: FB-4 무변화

```
증상: FB-4 최종 대조에서 "처음과 같다" → 분석 깊이 부족
탐지: FB-4 실행 결과 변화 없음
조치: 가장 약한 Layer를 식별하고 보강 시도.
      보강 후에도 변화 없으면 "이 이슈는 표면과 심층이 일치한다" 기록.
```

### A-04: 균일 깊이 경고

```
증상: Pre-Read에서 특정 Layer 집중을 지시했으나, 실제 출력이 균일
탐지: 출력에서 Layer별 분량 비교 (집중 Layer ≤ 축소 Layer이면 경고)
조치: 축소 Layer를 줄이고 집중 Layer를 보강
```

---

## 에스컬레이션 4단계

```
Level 0 — 자동 처리:
  Green Zone 내 모든 행위.
  이상 탐지 A-01~A-04 경고 출력.

Level 1 — 알림:
  Yellow Zone 행위 수행 시 사용자에게 의도 알림.
  "~를 하려고 합니다. 진행할까요?"

Level 2 — 확인 요청:
  SCP 재판독으로 분석 전략이 크게 바뀌는 경우.
  새로운 패턴을 레퍼런스에 추가하려는 경우.
  "~를 발견했습니다. 이렇게 수정하는 것이 맞을까요?"

Level 3 — 중단:
  Red Zone 접근 시 즉시 중단.
  "이 요청은 가드레일 Red Zone에 해당합니다. 수행할 수 없습니다."
  대안이 있으면 제안: "대신 ~는 가능합니다."
```
