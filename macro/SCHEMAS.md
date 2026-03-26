# SCHEMAS.md — macro 데이터 파일 JSON 스키마

이 문서는 macro 시스템의 주요 데이터 파일 스키마를 정의한다.
validate.py가 이 스키마를 기준으로 검증한다.

---

## 1. indicators/latest.json

PSF가 읽는 핵심 인터페이스 파일. macro의 모든 수집 결과가 이 파일에 집약된다.

### Top-Level 필수 필드

```json
{
  "date": "YYYY-MM-DD",           // 스냅샷 생성일 (필수)
  "data_basis": "설명 텍스트",      // 실제 데이터 기준일 (필수)
  "prev_date": "YYYY-MM-DD",      // 전주 스냅샷 날짜 (필수)
  "prev_basis": "설명 텍스트",      // 전주 기준 설명
  "confidence": "🟢|🟡|🔴|⚫",    // 전체 신뢰도
  "next_update": "YYYY-MM-DD",    // 다음 예정 갱신일

  "regime": { ... },               // 레짐 판정 객체 (필수)

  "A1": { ... },                   // Layer A 지표 (2개)
  "A2": { ... },
  "B1": { ... },                   // Layer B 지표 (5개)
  ...
  "B5": { ... },
  "C1": { ... },                   // Layer C 지표 (10개)
  ...
  "C10": { ... },
  "D1": { ... },                   // Layer D 지표 (10개)
  ...
  "D10": { ... }
}
```

### regime 객체 스키마

```json
{
  "regime": {
    "status": "🟢 팽창기|🟡 Transition|🔴 수축기|🟡 과열기|🔴 위기",  // 필수
    "score": "X/5|X.5/5",         // 위험자산 방향 수 (필수)
    "previous": "전주 레짐 문자열", // 전주 비교용
    "L7": 0.00,                    // L7 점수 0~1 (필수, number)
    "L8": 0.00,                    // L8 점수 0~1 (필수, number)
    "keystone": "설명 텍스트",      // 키스톤 상태 (필수)
    "narrative": "Good news = Good|Good news = Bad",  // 내러티브
    "dominant_path": "경로 설명",   // 지배 경로
    "disruption": "교란 상태",      // 교란 경로 상태
    "transition_trigger": "전환 조건", // 다음 레짐 전환 조건
    "quadrant": "Q1 Goldilocks|Q2 Reflation|Q3 Stagflation|Q4 Deflationary",
    "quadrant_basis": "판정 근거"
  }
}
```

### 지표 객체 스키마 (A1~D10)

#### Layer A (A1~A2) — 근본

```json
{
  "name": "지표명",               // 필수. 예: "Core PCE YoY"
  "value": 2.4,                   // 필수. number 또는 null (미수집 시)
  "unit": "%",                    // 필수. 단위 문자열
  "prev": 2.4,                    // 전주값 (number 또는 null)
  "change": 0,                    // 전주 대비 변화량 (number 또는 null)
  "direction": "↑|↓|→|↑ 추세|↓ 추세|→↑|→↓",  // 필수. 방향
  "risk_asset": "✓|✗|△|⚠️",     // 위험자산 방향 판정
  "status": "✓|✗|△|⚠️",         // 상태 (risk_asset과 동일 가능)
  "source": "출처 문자열",         // 필수. 예: "FRED PCEPILFE"
  "note": "설명"                  // 비고 (빈 문자열 허용)
}
```

#### Layer B (B1~B5) — 전달

```json
{
  "name": "지표명",               // 필수
  "value": 1.88,                  // 필수. number 또는 null
  "unit": "%|bp|T USD|",         // 필수
  "prev": 1.80,                   // 전주값
  "change": 0.08,                 // 전주 대비 변화량
  "direction": "↑|↓|→|→↑|→↓",   // 필수
  "risk_asset": "✓|✗|△|⚠️",     // 필수. RULES.md §1 기준
  "status": "✓|✗|△|⚠️",         // 필수
  "source": "출처 문자열",         // 필수
  "note": "설명"                  // 비고
}
```

#### Layer C (C1~C10) — 확인

```json
{
  "name": "지표명",               // 필수
  "value": 26.78,                 // 필수. number, string, 또는 null
  "unit": "%|bp|USD|",           // 단위
  "prev": 24.0,                   // 전주값
  "change": 2.78,                 // 전주 대비 변화량
  "direction": "↑|↓|→",          // 필수
  "source": "출처 문자열",         // 필수
  "cross": "교차검증 결과",        // Layer B 교차 결과. 예: "B5 불일치 ⚠️"
  "note": "설명"                  // 비고
}
```

#### Layer D (D1~D10) — 배경

```json
{
  "name": "지표명",               // 필수
  "value": 3.02,                  // number, string, 또는 null
  "unit": "T USD|%|bp|",        // 단위 (있으면)
  "prev": 3.02,                   // 전주값
  "change": 0,                    // 변화량 (number, string, 또는 null)
  "direction": "↑|↓|→|↑ 추세|↓ 추세|→ 소진|→ 구조적",  // 방향
  "source": "출처 문자열",         // 필수
  "note": "설명"                  // 비고
}
```

### Validation Rules (latest.json)

```
1. Top-Level:
   - date: 필수, YYYY-MM-DD 형식
   - data_basis: 필수, 비어있지 않은 문자열
   - regime: 필수, 객체

2. regime:
   - status: 필수, 비어있지 않은 문자열
   - score: 필수
   - L7: 필수, number, 0 ≤ L7 ≤ 1
   - L8: 필수, number, 0 ≤ L8 ≤ 1
   - keystone: 필수, 비어있지 않은 문자열

3. 핵심 27개 지표:
   - A1, A2, B1~B5, C1~C10, D1~D10 모두 존재해야 함
   - 각 지표: name(필수), source(필수), direction(필수)
   - value: number 또는 null (null일 때 note에 사유 필수)

4. Freshness:
   - date와 오늘 날짜 차이 ≤ 7일 (초과 시 ⚠️ STALE)
   - date와 오늘 날짜 차이 ≤ 14일 (초과 시 🔴 EXPIRED)
```

---

## 2. indicators/YYYY-MM-DD.yaml (주간 스냅샷)

_schema.md에 정의된 YAML 구조를 따른다. JSON 대응 스키마:

### 헤더

```json
{
  "date": "YYYY-MM-DD",
  "data_as_of": "YYYY-MM-DD",
  "prev_date": "YYYY-MM-DD",
  "prev_basis": "설명 텍스트",
  "regime": "EXPANSION|TRANSITION|CONTRACTION|OVERHEATING|CRISIS",
  "regime_change": false,
  "l7": 0.18,
  "l8": 0.02,
  "risk_gate": "GREEN|YELLOW|RED"
}
```

### Layer 구조

```json
{
  "layer_a": {
    "A1_core_pce": {
      "value": 2.4,              // number 또는 정성 문자열
      "unit": "%",
      "direction": "up|down|flat",
      "status": "met|partial|unmet",
      "source": "FRED:PCEPILFE",
      "confidence": "green|yellow|red|black",
      "note": ""
    }
    // A2_china_credit 동일 구조
  },
  "layer_b": {
    "B1_real_rate": {
      "value": 1.80,
      "unit": "%",
      "prev": 1.82,
      "direction": "up|down|flat",
      "risk_asset": true,        // boolean
      "source": "FRED:DFII10",
      "confidence": "green|yellow|red|black"
    }
    // B2~B5 동일 구조
  },
  "layer_c": {
    "C1_vix": {
      "value": 19.2,
      "cross": "B5",             // 교차 대상
      "match": true              // boolean: 일치 여부
      // match: false일 때 note 필수
    }
    // C2~C10 동일 구조
  },
  "layer_d": {
    "D1_sloos": {
      "value": "Moderate",
      "changed": false           // boolean: 변동 여부
      // changed: true일 때 note 필수
    }
    // D2~D10 동일 구조
  },
  "layer_aux": {
    // X1~X19 + timeseries (AUX-FRED 8, AUX-Yahoo 10, CoinGecko 1)
    "X1_dgs10": { "value": null, "unit": "%", "source": "FRED:DGS10", "psf": "P1 보조" }
    // ... 19개 + timeseries
  }
}
```

### 이벤트 + 인과 체인

```json
{
  "events": [
    {
      "name": "이벤트명",
      "date": "YYYY-MM-DD",
      "path": "fed|china|yen_carry|oil|fiscal",
      "impact": "설명"
    }
  ],
  "causal_chain": {
    "dominant": "fed|china",
    "disruptions": [],
    "conflicts": [],
    "keystone": "core_pce|employment",
    "narrative": "good_is_good|good_is_bad"
  }
}
```

### Validation Rules (YAML 스냅샷)

```
1. 헤더: date, regime, l7, l8 필수
2. layer_a: A1, A2 필수
3. layer_b: B1~B5 필수, 각각 value + direction + risk_asset 필수
4. layer_c: C1~C10 필수
5. layer_d: D1~D10 필수
6. prev 필드: 전주 스냅샷 존재 시 해당 값과 일치해야 함
7. risk_gate: l7, l8 값과 RULES.md §2 기준으로 일관성 검증
```

---

## 3. Notion 아카이브 형식

DB: ee345e95

### 필드 매핑

```json
{
  "분석 날짜": "YYYY-MM-DD",         // Date. 실제 실행일.
  "다음 업데이트": "YYYY-MM-DD",      // Date. 7일 후.
  "핵심 결론": "1~2문장",             // Rich Text. 이벤트 서사 포함.
  "레짐 판정": "🟢|🟡|🔴|⚫",        // Select. 레짐 이모지.
  "레짐 상세": "팽창기|Transition|수축기|과열기|위기",  // Select.
  "L7": 0.19,                        // Number. 소수점 2자리.
  "L8": 0.02,                        // Number. 소수점 2자리.
  "쿼드런트": "Q1|Q2|Q3|Q4",         // Select.
  "키스톤": "Core PCE|고용 바인딩",    // Select.
  "데이터 기준일": "YYYY-MM-DD",      // Date. FRED/시장 기준일.
  "교란 상태": "없음|교란1 활성|교란2 잔류|...",  // Multi-Select.
  "신뢰도": "🟢|🟡|🔴",             // Select.
  "보고서 경로": "reports/YYYY-MM-DD_macro-weekly.md"  // URL/Text.
}
```

### Validation Rules (Notion)

```
1. 분석 날짜: latest.json의 date와 일치해야 함
2. 레짐 판정: latest.json의 regime.status 첫 이모지와 일치
3. L7, L8: latest.json의 regime.L7, regime.L8과 일치 (소수점 2자리)
4. 핵심 결론: 비어있으면 안 됨
5. 다음 업데이트: 분석 날짜 + 7일
```
