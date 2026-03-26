# 산출물 규격

## state.json 핵심 구조

```
issue, date, depth,
fingerprint{5차원 + secondary_stakeholders(R-08)},
channels{5계층 + sns(R-06)},
reactions{5계층, expert에 침묵 기록 포함(R-09)},
pattern{4렌즈},
unresolved[{id, question, status, resolve_type, resolve_condition,
  check_channels, created, deadline, last_checked, last_checked_result,
  resolved_date, resolution}],
next_check
```

## fingerprint 추가 필드 (R-08)

| 필드 | 필수 | 설명 |
|------|------|------|
| secondary_stakeholders | O | 2차 이해관계자. "1차가 영향 받으면 다음은 누구?" 추론 결과 |

예시:
```json
"secondary_stakeholders": [
  {"from": "석화 기업", "to": "플라스틱 가공업체, 자동차 부품사, 여수 지역 노동자"},
  {"from": "산업부", "to": "고용노동부, 산업위 의원"}
]
```

## 침묵 기록 형식 (R-09)

reactions.expert 또는 reactions.policy에 침묵 항목 포함:
```json
{
  "name": "한국석유화학협회",
  "role": "피해자",
  "statement": "침묵 — 공식 성명 또는 매체 인용 미발견",
  "direction": "침묵",
  "channel": "—",
  "note": "업계 대표 단체이나 공식 입장 미발견"
}
```

## 미해소 질문 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| id | O | UQ-001 형식 |
| question | O | 질문 내용 |
| status | O | open / resolved |
| resolve_type | O | date / condition / data / threshold |
| resolve_condition | O | 해소 조건 설명 |
| check_channels | O | 체크할 MCP 도구/채널 |
| created | O | 생성일 |
| deadline | - | 날짜 또는 빈 문자열 |
| last_checked | - | 마지막 Phase 0 체크일 |
| last_checked_result | - | 체크 결과 요약 |
| resolved_date | - | 해소일 |
| resolution | - | 해소 내용 |

## HTML 보고서 구조

### A. 고정 구조 (render.py)
```
상태 바 → §1 지문 → §2 채널 → §3 반응(코멘트 포함) → §4 패턴(코멘트 포함) → §5 미해소(상태 표시) → Sources
```

### B. 자율 판단 (render_adaptive.py) ★ 권장
```
topbar → report-header → Executive Verdict(Core Claim) → [데이터 무게에 따른 자율 섹션] → Sources

자율 판단 Phase:
  Phase 1: Core Claim + Tension + Gravity + Timeline + Unresolved 추출
  Phase 2: 유형(A~E) 판정 + 섹션 자율 구성 (데이터 양 비례)
  Phase 3: 컴포넌트 자율 선택 (component-catalog.md 참조)
  Phase 4: V1~V5 자기 검증

핵심 원칙: 데이터가 보고서 형태를 결정. 빈 섹션 금지. 첫 화면에 Core Claim.
```

## 좋은 수집 vs 나쁜 수집 예시

### 좋은 수집 (에틸렌 하류 도미노)

```json
{
  "asset": "HD한국조선 329180",
  "before": "603,000원 (2/27)",
  "after": "516,000원 (3/24)",
  "change_pct": -14.4,
  "speed": "수일",
  "volume_change": "급증",
  "source": "Yahoo Finance",
  "timestamp": "2026-03-24",
  "note": "전쟁 발발 511K 급락→604K 회복(3/12)→다시 502K(3/23). 에틸렌 수급 뉴스에 재하락"
}
```
**왜 좋은가:**
- before/after 구체적 수치 + 날짜
- change_pct 정확한 계산
- source가 MCP 도구명 (1차 소스)
- note에 시간순 맥락 기록 (급락→회복→재하락)

### 나쁜 수집 (하지 말 것)

```json
{
  "asset": "조선주",
  "before": "",
  "after": "하락",
  "change_pct": 0,
  "speed": "",
  "source": "뉴스 기사에서 확인",
  "timestamp": "2026-03",
  "note": "조선주가 하락했다"
}
```
**왜 나쁜가:**
- 자산명이 모호 ("조선주" → 어떤 종목?)
- before 없음 → 변동 크기 판단 불가
- after가 수치가 아닌 "하락" → 정량화 안 됨
- source가 "뉴스 기사에서 확인" → 1차 소스 아님 (F-02)
- timestamp가 월 단위 → 시점 특정 불가

### 좋은 전문가 수집

```json
{
  "name": "한국조선해양플랜트협회",
  "role": "피해자",
  "statement": "선박 건조에 필요한 절단용 에틸렌 물량 확보 시급. 재고 1~2주분",
  "direction": "부",
  "channel": "공식 요청",
  "source": "https://www.ajunews.com/view/20260318080641989"
}
```

### 좋은 침묵 기록 (R-09)

```json
{
  "name": "삼성바이오/셀트리온",
  "role": "피해자",
  "statement": "침묵 — EO 수급 관련 공식 발언 미발견",
  "direction": "침묵",
  "channel": "—",
  "note": "CDMO 모델이라 원료 직접 구매 비중 낮을 수 있음. 주가 무반응과 일치"
}
```
**왜 좋은가:**
- "침묵"을 명시적으로 기록 (R-04)
- 침묵의 가능한 이유를 기록하되 단정하지 않음 ("낮을 수 있음")
- 다른 증거(주가 무반응)와 연결

### 나쁜 전문가 수집 (하지 말 것)

```json
{
  "name": "전문가",
  "role": "",
  "statement": "에틸렌이 부족하다고 한다",
  "direction": "부",
  "source": ""
}
```
**왜 나쁜가:**
- 이름이 "전문가" → 누구인지 특정 불가
- role 없음 → R-07 유형 체크 불가
- 출처 없음 → R-05 위반
- 선행 목록에서 못 찾은 사람의 침묵 기록도 없음 → R-09 위반

---

## history 규칙

파일: history/YYYY-MM-DD.json = state.json 사본
갱신 시마다 스냅샷. 같은 날 여러 번이면 마지막만 유지.
