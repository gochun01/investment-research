# Phase 3+4: 마무리 프롬프트

## 원칙

> 4대 불변 원칙, 판정 체계는 **CLAUDE.md** 참조.
> 아래는 Phase 3+4 마무리 전용 규칙만 기술한다.

## 마무리 전용 원칙

- **유효 조건에 KC를 반드시 포함하라.** ③ Logic에서 추출된 KC가 이 검증의 "생존 조건"이다.
- **무효화 트리거에 Temporal upcoming_triggers를 반드시 포함하라.** ④ Temporal에서 식별된 예정 이벤트가 자동 무효화 기준이다.
- **⑥ Omission 동심원에서 "전제 약화/붕괴"가 발견되었으면** validity_condition에 해당 전제를 포함하라.

---

검증이 완료되었다. 아래 **5단계를 순서대로** 수행하라:

## Step 1. 유효 기간 결정

| 문서 유형/범위 | 유효 기간 |
|---|---|
| 개별종목 | 다음 분기 실적발표 전 |
| 매크로 | 1개월 |
| 섹터·크립토 | 2주 |
| 법률 계약 | 계약 종료일 또는 1년 |

## Step 2. 유효 조건 + 재검증 트리거 서술

### 2a. 유효 조건

"이 판정이 유효하려면 [조건1] + [조건2] + ... 가 유지되어야 한다"

★ **③ Logic의 KC에서 추출된 전제를 여기에 종합**하라. KC가 이 문서의 "유효 조건"이다.

예: "유효 조건: (1) HBM 수요 증가 지속 (2) SK하이닉스 점유율 55% 이상 유지 (3) 원/달러 환율 1,350원 이하"

### 2b. 재검증 트리거 이벤트 (NIST AI RMF 기반)

★ **④ Temporal에서 식별된 upcoming_triggers를 여기에 종합**하라.

이 검증 결과를 **자동 무효화**하는 예정 이벤트 목록을 부착한다.
이벤트 발생 시 해당 검증 결과는 "재검증 필요" 상태로 전환된다.

```
invalidation_triggers=[
    {"event": "이벤트명", "expected_date": "YYYY-MM-DD", "impact": "영향 설명"},
    ...
]
```

예:
```
invalidation_triggers=[
    {"event": "FOMC 금리 결정", "expected_date": "2026-03-19", "impact": "매크로 전제(금리 동결) 재평가"},
    {"event": "SK하이닉스 1Q26 실적발표", "expected_date": "2026-04-24", "impact": "핵심 재무 데이터 전면 갱신"}
]
→ 유효 기간: min(기본 유효 기간, 첫 번째 트리거 날짜) = 2026-03-19
```

## Step 3. 마무리 (결과 반환)

```
verify_finalize(
    valid_until="YYYY-MM-DD",
    validity_condition="조건1 + 조건2 + ...",
    invalidation_triggers=[
        {"event": "이벤트명", "expected_date": "YYYY-MM-DD", "impact": "영향 설명"},
    ]
)
```

verify_finalize()는 결과 JSON을 **반환만** 한다.

## Step 4. 결과 전달

반환된 result_json은 Phase 5(HTML 보고서)에서 사용된다.
순서: finalize → self_audit → [사용자 대기] → HTML 보고서 (SKILL.md Phase 5 참조)

## Step 5. 면책 경고 (V-05, 필수)

출력에 반드시 포함:
"본 결과는 법률/투자 자문이 아닙니다. 검토 보조 목적으로만 사용하십시오."
🔴 플래그 항목이 있으면 추가: "전문가 검토를 권장합니다."
