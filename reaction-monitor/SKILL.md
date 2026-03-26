---
name: market-reaction-monitor
description: >
  쟁점/이벤트에 대한 시장 반응을 다층 수집하는 스킬.
  5개 반응 계층(가격·서사·전문가·정책·포지셔닝)에서
  쟁점 성격에 맞는 채널을 자율 선정하여 사실 기반 반응을 수집하고,
  4개 렌즈(방향·시간·비례·전파)로 패턴을 판독한다.
  트리거: '시장 반응', '반응 수집', '반응 분석',
  '시장이 어떻게 반응', 'market reaction', '매체 반응',
  '반응 모니터', '미해소 체크', '쟁점 반응'.
---

# 시장 반응 수집 스킬

## 공유 파일 경로

```
active-watches.json 경로 (원본):
  C:\Users\이미영\Downloads\에이전트\01-New project\tracking\active-watches.json

  ★ reaction-monitor/ 내부에 active-watches.json을 두지 않는다.
  ★ 공용 tracking/ 1곳만 원본. GitHub tracking-cards 브랜치로 동기화.
  ★ 읽기/쓰기 모두 위 경로를 사용한다.
```

## 전체 흐름

```
[Phase 0] 미해소 자동 체크 — 이전 state.json의 미해소 질문 점검
    ↓
[Phase 1] 쟁점 지문 — 쟁점의 성격을 5차원으로 규정
    ↓
[Phase 2] 채널 선정 — 지문 기반으로 반응 채널 자율 설계
    ↓
[Phase 3] 반응 수집 — 채널별 사실 수집 (prefetch 체크 → BATCH 1→2→3)
    ↓
[Phase 4] 패턴 판독 — 4렌즈로 계층 간 패턴 읽기 + Stereo 연계 판정
    ↓
[산출물] state.json + HTML 보고서 + history 스냅샷
    ↓
[Phase 5] Watch 등록 제안 — unresolved → Watch 변환 (승인 필요)
    ↓
[Phase 5.5] Stereo 연계 — 괴리/과소/한국전이/CUMULATIVE 시 Stereo 권장 (승인 필요)
```

---

## Phase 0: 미해소 + Watch 자동 체크 (항상 먼저 실행)

**이 Phase는 스킬 트리거 시 항상 자동으로 실행한다. 건너뛰지 않는다.**
**울타리: GUARDRAILS.md 준수. 읽기/스캔 = Green. 저장/등록 = Yellow(승인 필요).**

### 실행 조건

```
state.json이 존재하고 unresolved 배열에 항목이 있으면 → Phase 0 실행
active-watches.json이 존재하면 → Watch 기한 스캔도 실행
둘 다 없으면 → Phase 0 건너뛰고 Phase 1로
```

### 절차

```
Step 0: Watch 기한 스캔 [Green Zone — 읽기만]
    active-watches.json 로딩 → 기한 도래 Watch 필터
    도래한 Watch가 있으면 → "📌 Watch {N}건 기한 도래" 알림
    각 Watch의 check_template.data_sources를 표시
    (실제 데이터 수집은 Step 2에서 승인 후 실행)
    ↓
Step 1: state.json 읽기 → unresolved 배열 확인
    ↓
Step 2: 각 미해소 질문 + 도래 Watch의 resolve_type에 따라 체크
    │
    ├── date → deadline이 지났는가?
    │     YES → check_channels의 MCP 도구 호출하여 결과 확인
    │     NO  → "대기 중" 유지
    │
    ├── condition → resolve_condition 충족 여부를 WebSearch로 확인
    │     YES → check_channels의 MCP 도구 호출하여 상세 확인
    │     NO  → "미충족" 유지
    │
    ├── data → check_channels의 MCP 도구를 바로 호출하여 최신 데이터 확인
    │     데이터가 질문에 답하는가?
    │     YES → 해소
    │     NO  → 유지 (새 데이터 값은 기록)
    │
    └── threshold → MCP 도구로 현재 값 조회
          기준선 넘었는가?
          YES → 해소
          NO  → 유지 (현재 값 기록)
    ↓
Step 3: 결과 반영
    해소된 질문 → status: "resolved", resolution에 답 기록
    미해소 유지 → status: "open" 유지, 최신 체크 결과 기록
    ↓
Step 4: 대화창에 체크 결과 요약 출력
    "이전 미해소 5건 중 2건 해소, 3건 유지"
    ↓
Step 5: state.json 갱신 (unresolved 업데이트)
    ↓
Phase 1로 진행 (새 수집이 있는 경우)
또는 Phase 0만으로 종료 ("미해소 체크해줘"만 요청한 경우)
```

### "미해소 체크만" 요청 시

```
사용자: "미해소 체크해줘" / "미해소 질문 확인"
  → Phase 0만 실행하고 종료
  → 새 수집(Phase 1~4)은 하지 않음
  → HTML 보고서를 미해소 체크 결과로 갱신
```

---

## Phase 1: 쟁점 지문 (Issue Fingerprint)

### 5가지 차원

| 차원 | 질문 | 예시 값 |
|------|------|---------|
| 영역 | 무엇에 관한 쟁점인가 | 지정학, 통화정책, 산업규제, 통상정책, 기업, 기술 |
| 지리 범위 | 어디까지 영향이 미치는가 | 글로벌, 지역(미-중, 중동), 국내 |
| 접촉 자산 | 어떤 자산이 영향을 받는가 | 1차→2차→대조 순서로 추론 |
| 이해관계자 | 누가 영향을 받는가 | 쟁점에 따라 추론 |
| 시간 성격 | 어떤 시간 구조인가 | 충격 / 전개 / 구조적 |

불확실한 차원은 "?"로 두고 BATCH 1 수집 후 보정.

---

## Phase 2: 반응 채널 선정

### 5개 반응 계층

| 계층 | 선정 기준 | 활성 조건 |
|------|-----------|-----------|
| ① 가격 | 지문의 접촉 자산 | 항상 |
| ② 서사 | 지문의 영역 + 지리 | 항상 |
| ③ 전문가 | 지문의 이해관계자 | 항상 |
| ④ 정책 | 이해관계자에 공공기관 포함 시 | 조건부 |
| ⑤ 포지셔닝 | 시간 성격이 전개형 이상 | 조건부 |

채널 수 가이드:

| 깊이 | ①가격 | ②서사 | ③전문가 | ④정책 | ⑤포지셔닝 | 총 도구호출 |
|------|-------|-------|---------|-------|-----------|------------|
| Quick | 3~4 | 2~3 | 1~2 | 0~1 | 0 | 8~12 |
| Standard | 4~6 | 4~6 | 3~4 | 1~2 | 1~2 | 18~25 |
| Deep | 5~8 | 6~8 | 4~6 | 2~3 | 2~3 | 25~35 |

references/channel-catalog.md 참조. 카탈로그에 없는 채널도 자유롭게 선정 가능.

### SNS/X 포함 판단

채널 선정 시 아래 3가지 질문에 답하고 SNS 포함 여부를 결정한다.
**이 판단을 건너뛰지 않는다. 비활성이어도 "비활성 — [이유]"를 기록한다.**

```
Q1: 이 쟁점에 X/SNS에서 직접 발언하는 핵심 인물이 있는가?
    (기업 CEO, 트레이더, 정치인 등)
    → YES: 해당 인물 타겟 수집
      도구: WebSearch 프록시 ("[이름] said/posted [쟁점]" site:reuters.com OR cnbc.com)
      또는: Apify Actor (X 직접 검색 — 키워드/계정 타겟)
    → NO: Q2로

Q2: 이 쟁점이 리테일 투자자 / 일반 대중의 관심사인가?
    (크립토, 부동산, 주식시장 이벤트 등)
    → YES: 커뮤니티 반응 프록시 수집
      도구: WebSearch ("reddit reacts [쟁점]", "[쟁점] 투자자 반응")
    → NO: Q3로

Q3: 정책 결정자가 SNS에서 발언하는가?
    (트럼프 Truth Social, 의원 X 포스트 등)
    → YES: 해당 발언을 정책 반응(④)에 포함. Tier 1 승격.
      도구: WebSearch ("[이름] [쟁점]" site:truthsocial.com OR site:x.com)
    → NO: SNS 비활성

3개 모두 NO → SNS 비활성.
  channels에 "sns": {"status": "비활성", "reason": "[이유]"} 기록.

판단 예시:
  크립토 쟁점: Q1=YES(머스크), Q2=YES(리테일), Q3=YES(트럼프) → 전면 활성
  나프타 쟁점: Q1=일부(업계 내부자), Q2=NO(산업 B2B), Q3=일부(의원) → 제한적 활성
  FOMC 금리: Q1=YES(연준 인사), Q2=YES(투자자), Q3=NO → 부분 활성
```

### 전문가 선정 체크리스트

전문가(③) 선정 시 아래 6가지 유형을 점검한다.
**모두 포함할 필요는 없지만, 해당하는데 빠진 유형이 있으면 BATCH 3에서 보충한다.**

```
□ 공급자 측 — 이 쟁점의 원인/공급 측 당사자
    예: 나프타→중동 수출국, 크립토→SEC 위원
□ 피해자 측 — 이 쟁점의 직접 영향을 받는 당사자
    예: 나프타→석화 기업 경영진, 크립토→거래소 CEO
□ 분석자 — 독립적 분석을 제공하는 전문가
    예: 증권사 애널리스트, 산업 전문 리서치
□ 반대 입장 — R-03 양면 수집. 다수 의견의 반대쪽 (필수 1명+)
    예: 나프타→"기회론" 애널리스트, 크립토→"전쟁 상쇄" 분석가
    ★ 서사(②)에만 반대쪽이 있고 전문가(③)에 없으면 R-03 미충족.
      서사의 반대쪽 매체에서 인용된 전문가를 전문가 계층에도 등록한다.
      반대 전문가를 찾지 못하면 "반대입장: 미발견 — [검색 키워드]" 기록.
    ★ 검색 키워드 예: "[쟁점] 과장 OR 제한적 OR 영향 없다 전문가"
□ 하류/2차 영향권 — 도미노 영향을 받는 2차 당사자 (해당 시)
    예: 나프타→자동차/가전 구매 담당, 크립토→DeFi 프로젝트
□ 정책 관련자 — 규제/지원 결정권자 (해당 시)
    예: 나프타→산업부 관계자, 크립토→SEC 위원장

선정 후 기록 형식:
  각 전문가에 role 태그 부착: 공급자 | 피해자 | 분석자 | 반대입장 | 하류 | 정책
```

### 2차 이해관계자 맵 (R-08)

1차 추론(지문 → 채널)만으로는 "보이지 않는 반응"을 놓친다.
**Phase 2에서 반드시 1단계 더 추론한다.**

```
절차:
  1. 지문의 이해관계자 각각에 대해 질문한다:
     "이 이해관계자가 영향을 받으면 → 다음으로 누가 영향을 받는가?"

  2. 답을 2차 이해관계자로 기록한다.

  3. 2차 이해관계자 중 중요한 것을 채널(서사/전문가/가격)에 추가한다.

예시 — 나프타 수급:
  1차: 석화 기업 → 2차: 플라스틱 가공업체, 자동차 부품사, 여수 지역 노동자
  1차: 정유사 → 2차: 주유소, 물류 운송, 항공사
  1차: 산업부 → 2차: 고용노동부(셧다운→고용), 산업위 의원(추경)

  → "여수 지역 노조", "플라스틱 가공업체 대표" 등이 전문가에 추가되어야 했음

예시 — 이란 원유 면제:
  1차: 한국 정유사 → 2차: 중국 정유사(독점 해체 당사자), 인도 정유사(경쟁 구매)
  1차: 미 재무부 → 2차: 미 의회 비판론(FDD), 이란 정부(공급자 측 시각)

  → "중국 정유사 반응", "인도 정유사 동향"이 수집되어야 했음

기록: state.json의 fingerprint에 "secondary_stakeholders" 필드 추가
```

### 전문가 선행 목록 + 침묵 대상 (R-09)

전문가를 "검색에서 발견"하는 것이 아니라 **"이 사람을 찾아야 한다"고 미리 선정**한다.
또한 "말해야 하는데 안 말한 사람/기관"을 **명시적으로 침묵 기록**한다.

```
절차:

Step 1: 전문가 선행 목록 작성 (Phase 2, BATCH 수집 전)
  지문의 이해관계자 + 2차 이해관계자에서 "발언을 찾아야 할 사람"을 목록화.
  이름이 특정되지 않으면 역할로 기재.

  예시 — 나프타:
    찾아야 할 발언:
    ☐ LG화학/롯데케미칼 경영진 (피해자 측)
    ☐ 여천NCC 대표 (불가항력 선언 당사자)
    ☐ 석유화학 섹터 애널리스트 (분석자)
    ☐ 여수시장 또는 지역 상공회의소 (2차 영향권)
    ☐ 산업위 소속 의원 (정책 관련자)
    ☐ 한국석유화학협회 (업계 단체)

Step 2: BATCH 2에서 이름으로 타겟 검색
  WebSearch: "[이름/역할] + [쟁점]"
  찾으면 → 전문가 반응에 기록
  못 찾으면 → Step 3

Step 3: 침묵 기록 (R-04 강화)
  선행 목록에 있었지만 발언을 찾지 못한 사람/기관을 명시적으로 기록:

  reactions.expert에 추가:
  {
    "name": "한국석유화학협회",
    "role": "피해자",
    "statement": "침묵 — 공식 성명 또는 매체 인용 미발견",
    "direction": "침묵",
    "channel": "—",
    "note": "업계 대표 단체이나 공식 입장 미발견. 의도적 침묵 또는 수집 한계"
  }

  침묵의 해석:
    - 정부 기관의 침묵 = 아직 입장 미정리, 또는 의도적 회피
    - 업계 단체의 침묵 = 내부 조율 중, 또는 수집 도구의 한계
    - 하류 기업의 침묵 = 아직 영향 미도달, 또는 미디어 관심 밖
  침묵의 원인을 단정하지 않되, 가능한 이유를 기록한다.
```

---

## Phase 3: 반응 수집

### ★ scanner 패스스루 체크 (BATCH 1 실행 전)

```
scanner_prefetch가 존재하는가? (scanner → rm handoff에 포함)

IF scanner_prefetch 존재:
  가격: prefetch.price_snapshot에 있는 자산은 재수집 생략.
        prefetch에 없는 자산만 Yahoo Finance로 추가 수집.
  서사: prefetch.narrative_snippets를 BATCH 1 서사 기반으로 사용.
        BATCH 2에서 심화(반대쪽, 전문매체)만 추가 수집.
  정책: prefetch.policy_signals를 BATCH 1 정책 기반으로 사용.
        상세(공식 성명, 법안 텍스트)만 추가 수집.
  → BATCH 1의 MCP 호출이 대폭 감소 (기존 8~12회 → 2~5회).

IF scanner_prefetch 없음 (rm 단독 실행, 사용자 직접 입력):
  기존대로 BATCH 1 전체 수집. 변화 없음.

주의:
  prefetch 데이터의 신선도를 확인한다.
  scanner 실행 후 1시간+ 경과 시 가격(price_snapshot)은 재수집 권장.
  서사/정책은 신선도 영향 적음 (기사는 수시간 유효).

  prefetch는 "기반"이지 "완료"가 아니다.
  전문가 계층과 포지셔닝 계층은 prefetch에 없다 → BATCH 2에서 반드시 수집.
```

### BATCH 1 (동시): 가격 + 1차 서사 + 정책
  (prefetch 있으면 잔여분만 수집)
### BATCH 2 (BATCH 1 기반): 서사 심화 + 전문가 + 포지셔닝
  (prefetch 유무와 무관하게 항상 전체 수집 — scanner가 안 하는 영역)
### BATCH 3: 보정 + 양면 체크 + 침묵 기록

수집 형식:
```
계층 / 채널 / 선정 이유 / 관측 사실 / 출처 / 시점
[prefetch] 태그: scanner에서 온 데이터에는 [prefetch] 표시.
[MCP] 태그: rm이 직접 수집한 데이터에는 [MCP] 표시.
```

---

## Phase 4: 패턴 판독

4개 렌즈 (references/pattern-lexicon.md 참조):
1. 방향 일치도: 수렴 / 분열 / 괴리 / 침묵
2. 시간 구조: 시장주도(A) / 미디어주도(B) / 정책주도(C) / 분석주도(D)
3. 크기 비례성: 과잉 / 비례 / 과소 / 무반응
4. 전파 경로: A / B / C / D / 복합

각 렌즈에 코멘트(해석)를 반드시 부착한다.

### ★ Stereo 연계 판정 (Phase 4 완료 후)

```
패턴 판독 완료 후, Stereo 입체 분석이 필요한지 자동 판정한다.
판정만 한다. 실행은 사용자 승인 (Yellow Zone).

IF 방향 일치도 == "괴리" OR 비례성 == "과소":
  → "⚠ 표면과 심층의 괴리가 있습니다. Stereo 입체 분석을 권장합니다."
  이유: 시장 반응이 이슈의 크기와 맞지 않음 = 보이지 않는 것이 있다.
  예: Section 301 16+60개국인데 시장 무반응 → 괴리 → stereo L4+L5 필요.

ELIF scanner_origin.temporal_tag == "CUMULATIVE" AND SCP ≥ 3:
  → "⚠ 장기 누적 + 구조 변화 신호입니다. Stereo 시간축 분해를 권장합니다."
  이유: 스냅샷으로는 구조를 볼 수 없다. 시간축 분해(L5)가 필요.
  예: KRW 1,500 = 14개월 3단계 누적 → stereo L5 시간축 분해.

ELIF "한국" in touched_assets OR 한국 관련 이해관계자 존재:
  → "⚠ 한국 전이 경로가 식별됩니다. Stereo + PSF/macro 교차를 권장합니다."
  이유: 글로벌 이슈의 한국 영향은 rm 5계층으로 부족. macro 5경로 + PSF 3층이 필요.
  예: KRW + 25조 추경 → stereo L6(2차효과) + PSF/macro 교차.

ELSE:
  → stereo_recommendation: null. "rm 수집으로 충분합니다."

출력 형식 (사용자에게):
  "━━━━━━━━━━━━━━━━━━━━━━━━━━
   📐 Stereo 연계 판정
   ━━━━━━━━━━━━━━━━━━━━━━━━━━
   판정: [권장/불필요]
   이유: [1문장]
   모드: [기본 / PSF+macro 교차 / 시간축 분해]
   ━━━━━━━━━━━━━━━━━━━━━━━━━━
   실행할까요?"

사용자가 승인하면 → rm state.json 전체를 Stereo에 전달.
사용자가 거부하면 → rm으로 종료. Watch 등록으로 진행.

★ rm이 stereo에 주는 것: state.json + scanner_prefetch + stereo_trigger
★ rm이 stereo에 안 주는 것: "어떤 Layer에 집중하라"는 지시
  → Stereo의 Pre-Read가 Type/SCP/Urgency를 스스로 판독.
```

---

## 미해소 질문 스키마

Phase 4 완료 후 미해소 질문을 아래 구조로 등록한다:

```json
{
  "id": "UQ-001",
  "question": "질문 내용",
  "status": "open | resolved",
  "resolve_type": "date | condition | data | threshold",
  "resolve_condition": "해소 조건 설명",
  "check_channels": { "price": [], "narrative": [], "positioning": [] },
  "created": "YYYY-MM-DD",
  "deadline": "YYYY-MM-DD 또는 빈 문자열",
  "last_checked": "YYYY-MM-DD",
  "last_checked_result": "체크 결과 요약",
  "resolved_date": "",
  "resolution": ""
}
```

resolve_type별 의미:
- date: 특정 날짜에 답이 나옴 (CLARITY Act 투표일)
- condition: 특정 이벤트 발생 시 (이란 휴전)
- data: MCP 도구로 데이터를 보면 답이 나옴 (ETF 흐름)
- threshold: 수치가 기준선을 넘으면 (MVRV < 1.0)

---

## Phase 5: Watch 등록 제안 (수집 완료 후)

**울타리: Yellow Zone — 등록은 반드시 사용자 승인.**

### 절차

```
Step 1: Phase 4 완료 후, state.json의 unresolved를 Watch 제안으로 변환
    변환 규칙:
    ├── resolve_type: "condition" → event_tracking (D+5/10/14)
    ├── resolve_type: "date"      → policy_watch (deadline까지 주 1회)
    ├── resolve_type: "data"      → data_check (deadline 기준 1회)
    └── resolve_type: "threshold" → threshold_watch (2주 1회)

Step 2: 제안 출력
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ⚠ 승인 필요 — Watch 등록
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {N}건 Watch 등록 제안:

    📌 W-{date}-UQ-xxx
       주제: {question}
       유형: {watch_type}
       스케줄: {schedule 요약}
       종료 조건: {close_condition}
       데이터: {data_sources}

    등록할까요?"

Step 3: 승인 시 → active-watches.json에 저장
        거절 시 → 끝 (미해소는 state.json에 유지)

도구: python core/watch.py propose → 제안 확인
      python core/watch.py register → 승인 후 등록
```

### Watch ↔ Phase 0 연동

```
다음 세션에서:
  Phase 0 → active-watches.json 스캔
  → 기한 도래 Watch 발견
  → 데이터 수집 (Green Zone)
  → 결과 저장 (Yellow Zone — 승인 필요)
  → Watch 갱신 또는 종료 제안 (Yellow Zone)
```

---

## Phase 6: 이벤트 히스토리 등록 (수집 완료 후)

**울타리: Yellow Zone — 생성/연결은 반드시 사용자 승인.**

```
수집 완료 후, 이 쟁점이 이벤트로 추적할 가치가 있는지 판단한다.

판단 기준:
  ├── 미해소 질문이 2건+ → 추적 가치 있음 → 이벤트 생성
  ├── 이전 이벤트와 연쇄 관계 → parent 이벤트에 연결
  └── 1회성 쟁점 → 이벤트 불필요 (history/ 스냅샷만)

신규 생성:
  "이벤트 생성할까요?"
  → 승인 시: python core/events.py create
  → 이전 이벤트의 후속이면: python core/events.py create --parent EVT-ID

후속 연결:
  "기존 이벤트에 연결할까요?"
  → 승인 시: python core/events.py link EVT-ID
  → 이벤트 타임라인에 후속 분석 추가 + 패턴 변화(Δ) 기록

조회:
  python core/events.py list     → 이벤트 목록 (Green)
  python core/events.py view ID  → 이벤트 생애 (Green)
  python core/events.py chain    → 이벤트 연쇄 트리 (Green)
```

### 이벤트 구조

```
events/{EVT-ID}.json:
  id, subject, created, status
  parent_event, child_events          ← 연쇄 관계
  fingerprint                         ← 쟁점 지문
  timeline[]:                         ← 분석 생애 (initial + follow_up)
    date, type, pattern, delta_vs_prev, key_finding
  unresolved_at_creation[]            ← 생성 시 미해소
  resolution: {date, outcome, lessons_learned}  ← 해소 시
```

### 이벤트 체인 예시

```
EVT-나프타-수급 (root, 방향: 수렴)
  ├── EVT-이란-원유-면제 (child, 방향: 분열)
  └── EVT-에틸렌-하류-도미노 (child, 방향: 분열)

EVT-크립토-SEC-전쟁 (standalone, 방향: 괴리)
```

---

## 산출물

```
1. state.json — 구조화된 반응 데이터 + 미해소 질문
2. history/YYYY-MM-DD-{slug}.json — state.json 스냅샷
3. HTML 보고서 (아래 두 방식 중 선택)
4. active-watches.json — Watch 목록 (Phase 5)
5. events/{EVT-ID}.json — 이벤트 생애 파일 (Phase 6)
```

### HTML 보고서 — 두 가지 방식

```
A. 고정 구조 (render.py)
   └── §1 지문 → §2 채널 → §3 반응 → §4 패턴 → §5 미해소 → Sources
   └── 항상 같은 골격. 빠르고 일관적.
   └── python core/pipeline.py

B. 자율 판단 (render_adaptive.py) ★ 권장
   └── 데이터가 보고서의 형태를 결정한다.
   └── Phase 1: 데이터 읽기 (Core Claim, Tension, Gravity, Timeline, Unresolved)
   └── Phase 2: 구조 설계 (유형 A~E 자동 판정, 섹션 자율 구성)
   └── Phase 3: 렌더링 (컴포넌트 자율 선택)
   └── Phase 4: 자기 검증 (V1~V5)
   └── python core/pipeline.py --adaptive

선택 기준:
├── 데이터가 풍부하고 긴장/대립 존재 → B (자율 판단)
├── 정기 업데이트 성격의 수집 → A (고정 구조) 또는 B
├── "이 데이터로 최적의 보고서 알아서" → B
├── "빠르게 기본 형태로" → A
└── 기본값: B (자율 판단)

자율 판단 보고서 유형:
├── A 대립형: Tension 명확. 힘A vs 힘B → 균형 → 분기 조건
├── B 서사형: 단일 흐름. 배경 → 전개 → 현재 → 전망
├── C 스냅샷형: 현재 상태 집중. 대시보드 느낌.
├── D 분기형: 미래 분기 집중. 시나리오 카드 중심.
└── E 복합형: 2개+ 유형 조합.

참조 파일 (자율 판단 시):
├── assets/template-base.html — CSS 디자인 시스템 베이스
└── references/component-catalog.md — HTML 컴포넌트 카탈로그
```

---

## 울타리 (GUARDRAILS.md 요약)

```
Green Zone (무승인):  읽기, MCP 수집, 스캔, 계산, 알림 텍스트 생성
Yellow Zone (승인 필요): state.json 갱신, Watch 등록/종료/변경,
                        history 저장, HTML 생성, 이슈 적재, 설계 파일 수정
Red Zone (금지):      투자 판단, 파일 삭제, 매체/전문가 영구 판정
```

상세: GUARDRAILS.md 참조

---

## 금지 트리거 (이 상황에서는 실행하면 안 됨)

```
├── 단순 뉴스 요약 요청 ("이 기사 요약해줘")
│   → reaction-monitor가 아님. 뉴스 요약으로.
├── 개별 종목 분석 ("삼성전자 분석해줘")
│   → company-analysis 스킬로.
├── PSF 브리핑 ("오늘 시장 브리핑")
│   → psf-morning-briefing으로.
├── 투자 판단 요청 ("이거 사야 해?")
│   → Red Zone. 어떤 스킬도 실행 불가.
└── 과거 완료된 이벤트 복기 ("작년 이란 사태 정리해줘")
    → events.py view로 조회만. 새 수집 불필요.
```

---

## 금지사항

- 수집된 반응을 투자 판단으로 전환하지 않는다
- 채널 선정 이유를 생략하지 않는다
- 한쪽 방향 반응만 수집하지 않는다
- 출처 없는 정보를 사실로 기록하지 않는다
- 무반응/침묵을 생략하지 않는다
- Phase 0(미해소 + Watch 체크)를 건너뛰지 않는다
- Watch 등록/종료/변경은 반드시 사용자 승인 (Yellow Zone)

---

## 컨텍스트 로딩 전략

```
전부 로딩하지 않는다. 필요한 것만, 필요한 시점에.

Phase 0 로딩 (항상):
  ├── state.json (1건)
  ├── active-watches.json (기한 도래분만)
  └── system-issues.json summary만 (건수)

Phase 2 로딩 (채널 선정 시):
  └── references/channel-catalog.md (참고 필요 시만)

Phase 4 로딩 (판독 시):
  └── references/pattern-lexicon.md

보고서 생성 시 (자율 판단 모드):
  ├── assets/template-base.html (CSS 변수/클래스 파악)
  └── references/component-catalog.md (컴포넌트 선택 시)

후속 수집 시:
  └── 이전 동일 쟁점의 state.json 1건만 (history/에서)

로딩하지 않는 것:
  ├── history/ 전체 (필요한 1건만)
  ├── events/ 전체 (chain 확인 시만)
  ├── 이전 reports/ HTML
  └── references 4개를 한꺼번에 (필요 시점에 1개씩)
```

---

## 알려진 실패 패턴과 방어 규칙 (F-테이블)

**이 테이블은 운영하면서 누적한다. 삭제하지 않는다.**

| # | 실패 패턴 | 원인 | 방어 규칙 | 감지 방법 |
|---|----------|------|----------|----------|
| F-01 | 반대입장 전문가 누락 | 서사에만 반대쪽 넣고 전문가에 안 넣음 | 서사 반대쪽 매체의 인용 전문가를 전문가 계층에도 등록. 반대 전문가 미발견 시 "반대입장: 미발견 — [검색 키워드]" 기록 | validate.py R-03 WARN |
| F-02 | 핵심 수치의 1차 소스 미확보 | 매체 인용 수치만 사용. ICIS/Argus 등 원본 미조회 | 핵심 수치(가격, 변동률)는 반드시 MCP 도구 또는 원본에서 직접 확인. 매체 인용만이면 "매체 인용 — 1차 미확인" 표기 | Self-Audit Q5에서 체크 |
| F-03 | 2차 이해관계자 추론만 하고 수집 안 함 | R-08 추론은 했으나 BATCH 2에서 검색 누락 | 2차 이해관계자 중 최소 1건은 BATCH 2에서 타겟 검색. 검색 결과 없으면 "침묵" 기록 | R-08 추론 건수 vs 실제 수집 건수 비교 |
| F-04 | 매체 프레임을 시장 반응으로 착각 | "일파만파" 매체 보도 ≠ 시장 실제 반응 | 서사 톤과 가격 방향이 불일치하면 반드시 "매체 프레임 vs 시장 반응 괴리" 명시. 기업 침묵이 있으면 매체 과장 가능성 검토 | 렌즈 1(방향 일치도)에서 서사↑ 가격→ 조합 감지 |
| F-05 | SNS 판단만 하고 실제 수집 안 함 | R-06 Q1~Q3 판단은 했으나 프록시 검색 미실시 | "활성" 판단 시 최소 프록시 검색 2회 실행. "비활성"이면 OK | channels.sns.collected=false인데 status≠"비활성" |
| F-06 | 동일 쟁점 후속 수집 시 이전 판독과 비교 안 함 | 새 수집에만 집중. 이전 패턴 변화 무시 | 후속 수집 시 이전 state.json의 pattern과 현재를 대조. delta 명시 | events.py link 시 delta_vs_prev 필드 비어있으면 경고 |
| ... | 운영하면서 추가 | | | |

---

## Self-Audit (매 수집 완료 후)

**수집 완료 후 아래 5개 항목을 자기 검증한다. 건너뛰지 않는다.**

```
Q1: 채널 선정에 선정 이유가 모든 채널에 기록되어 있는가? (R-02)
    → state.json channels 각 항목에 reason 필드 확인

Q2: 서사와 전문가 양쪽에 반대 입장이 1건+ 있는가? (R-03 + F-01)
    → narrative에 role="반대쪽" 1건+
    → expert에 role="반대입장" 1건+
    → 둘 다 없으면 F-01 발동

Q3: 가격 반응과 서사 프레임이 불일치할 때 그 괴리를 명시했는가? (F-04)
    → 서사 대다수 "부"인데 가격 "무반응"이면 → 코멘트에 괴리 명시 필수
    → 명시 안 했으면 F-04 발동

Q4: 전문가 선행 목록에서 검색했으나 못 찾은 사람을 침묵으로 기록했는가? (R-09)
    → expert에 direction="침묵" 항목 존재 확인
    → 선행 목록 전원 발견(침묵 0건)이면 정말 전원 발언한 것인지 재확인

Q5: 핵심 수치(가격, 변동률)의 1차 출처가 모두 MCP 또는 원본인가? (R-05 + F-02)
    → price 반응의 source가 전부 MCP 도구명이면 ✅
    → "매체 인용"만 있으면 F-02 발동

결과 처리:
  5개 ✅ → 정상 완료
  1~2개 ⚠ → 일회성이면 보고서 내 보완. 시스템성이면 system-issues.json 적재
  3개+ ⚠ → 수집 품질 의심. 보충 수집 또는 재수집 검토.
```

---

## 불변 규칙 (진화의 하한선)

**어떤 SKILL.md/CLAUDE.md 수정에서도 아래는 절대 변경하지 않는다.**

```
1. 반응 계층 5개 (가격/서사/전문가/정책/포지셔닝)는 줄이지 않는다.
2. 판독 렌즈 4개 (방향/시간/비례/전파)는 줄이지 않는다.
3. R-01 (사실과 해석 분리)은 완화하지 않는다.
4. R-03 (양면 수집)은 "효율" 명목으로 생략하지 않는다.
5. Phase 0 (미해소+Watch 자동 체크)를 "선택"으로 격하하지 않는다.
6. validate.py의 검증 규칙을 비활성화하지 않는다.
7. F-테이블 항목을 삭제하지 않고 누적만 한다.
```

---

## 주간 리뷰 프로토콜 (매주 월요일)

```
트리거: 월요일 첫 세션 또는 "시스템 리뷰"

Step 1: system-issues.json 로딩 → open 이슈 목록
Step 2: 심각도순 정렬 (high → medium → low)
Step 3: 각 이슈별 수정안 출력 + 승인 요청
Step 4: 승인된 수정 반영 (SKILL.md, channel-catalog.md 등)
Step 5: F-테이블에 새 패턴 추가 (해당 시)
Step 6: 감사 요약 출력:
  "이슈 {N}건 open → {N}건 수정 / {N}건 이월"
  "이번 주 실패 패턴: {F-xx} {N}회"

주기: 매주 월요일. 이슈 0건이면 "이슈 없음. 스킵." 출력.
```

---

## 갱신 규칙

```
갱신 주기: 주간 리뷰 시 + 이슈 발견 즉시 (Step 6 FAIL)
갱신 주체: 사용자 승인 후 Claude가 반영 (Yellow Zone)
버전 관리: system-issues.json의 fix_applied 필드에 수정 내역 기록
변경 이력: GUARDRAILS.md는 수정 시 반드시 이유 기록
```
