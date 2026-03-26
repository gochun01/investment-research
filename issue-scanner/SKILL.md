---
name: issue-scanner
description: >
  글로벌 미디어를 4축 스캔하여 투자 관련 쟁점 5~10개를 발굴하고,
  5-Gate 필터 + 근인 클러스터링으로 정제한 뒤,
  사용자 승인 후 reaction-monitor에 전달하는 전방 모듈.
  트리거: '이슈 스캔', '스캔', '오늘 뭐 봐야 해', '이슈 찾아줘',
  'scan', 'issue scan', '글로벌 스캔'.
---

# 이슈 스캐너 실행 프로토콜

## 전체 흐름

```
[Phase S0] 컨텍스트 로딩 — rm state + watches + backlog + 외부 시드
    ↓
[Phase S1] 4축 글로벌 스캔 — A(시장) B(정책) C(공급) D(매몰)
    ↓  원재료 15~30건
[Phase S2] 5-Gate 필터 — 접촉면 / 변화 / 전파 / 긴급 / 중복
    ↓  후보 8~12건
[Phase S3] 사각지대 보정 + 결정 — 자산군·지역·다양성·backlog
    ↓  최종 5~10건
[Phase S4] 근인 클러스터링 — 같은 뿌리 묶기
    ↓
[Phase S5] 사용자 제시 — ★ 핵심 승인 지점
    ↓  사용자 선택
[Phase S6] 전달 + 백로그 — rm handoff + 미선택 저장
```

---

## Phase S0: 컨텍스트 로딩 [GREEN]

**매 스캔 시작 시 반드시 실행. 건너뛰지 않는다.**

```
Step 1: reaction-monitor 상태 로딩
  ../reaction-monitor/state.json → 현재 수집 중인 쟁점
  ../reaction-monitor/active-watches.json → 추적 중인 주제 목록

Step 2: scanner 자체 상태 로딩
  scan-state.json → 마지막 스캔 날짜, 이전 결과 요약
  backlog.json → 미선택 이슈 누적 목록

Step 3: 외부 시드 로딩 (있으면)
  heartbeat KC 알림 → 발동된 KC가 있으면 D축 시드로 투입
  macro 레짐 → 현재 레짐 컨텍스트 참조
  GHS 보고서 → buried_issues, plate_detection을 D축 시드로

Step 4: backlog 정리
  30일+ 미등장 이슈 → 자동 아카이브 (backlog에서 제거, history에 기록)

출력:
  "현재 rm 쟁점: [이슈명]
   활성 Watch: [N]건
   backlog: [M]건 (3회+ 반복: [K]건)
   외부 시드: [있음/없음]"
```

---

## Phase S1: 4축 글로벌 스캔 [GREEN]

**4개 축 × 2개 언어. 각 축은 독립 스캔. 합치지 않는다.**
**v1.1: A~C축 6회를 병렬 실행. D축만 backlog 의존으로 후행.**

### A축: 시장 반응 (이미 움직인 것)

```
목적: 가격이 먼저 반응한 이벤트 포착
쿼리:
  EN: Tavily — "Reuters OR Bloomberg OR CNBC market stocks oil gold today [date]"
       (v1.1: 소스명 한정으로 노이즈 방지)
  KR: WebSearch — "증시 급등 급락 유가 환율 금 오늘 [date]"
       (v1.1: Tavily→WebSearch. 한국어 검색 품질 개선)
도구: Tavily 1회 + WebSearch 1회 = 2회
이것이 잡는 것: 이란 휴전 → S&P +1%, 원유 -5%
```

### B축: 정책 변화 (곧 움직일 것)

```
목적: 발표·결정·성명 중 시장 미반영된 것
쿼리:
  EN: Tavily — "central bank regulation sanctions tariff policy [date]"
  KR: WebSearch — "금리 결정 규제 관세 제재 정부 발표 오늘"
도구: Tavily 1회 + WebSearch 1회 = 2회
이것이 잡는 것: ECB 인하 기대 후퇴, 트럼프 관세 변경
```

### C축: 공급/구조 충격 (느리게 번질 것)

```
목적: 밸류체인·인프라·공급 차질 — 2차·3차 충격의 씨앗
쿼리:
  EN: Tavily — "supply chain shortage disruption force majeure infrastructure [date]"
  KR: WebSearch — "공급 차질 물량 부족 가동 중단 수급 불안 오늘"
도구: Tavily 1회 + WebSearch 1회 = 2회
이것이 잡는 것: 호르무즈 비료 충격, 반도체 수급
```

### D축: 매몰 이슈 + backlog (묻힌 것)

```
목적: dominant event에 묻힌 구조적 변화 + backlog 재검증
쿼리:
  backlog 3회+ 반복 이슈의 title로 WebSearch (최대 2회)
  + 외부 시드 키워드가 있으면 해당 키워드로 1회
도구: WebSearch 2~3회
이것이 잡는 것: 래리 핑크 AI 투자, 크립토 규제 진전
```

### 총 MCP 호출: 8~9회

```
A: Tavily 2회
B: Tavily 1회 + WebSearch 1회
C: Tavily 1회 + WebSearch 1회
D: WebSearch 2~3회
────────────────
합계: 8~9회
```

**모든 스캔 결과를 원재료(raw)로 보존. 각 결과에 축 태그(A/B/C/D) 부착.**

---

## Phase S2: 5-Gate 필터 [GREEN]

**원재료 15~30건 → 후보 8~12건. 각 헤드라인이 5개 Gate를 통과해야 "쟁점"이 된다.**

### Gate 구조

```
┌─────────────────────────────────────────────────────────┐
│ G1: 시장 접촉면 (Market Contact Surface) — 체크리스트   │
│                                                          │
│ "이것이 어떤 자산·섹터·지표에 영향을 주는가?"             │
│                                                          │
│   □ 주식 (어떤 종목/섹터?)                               │
│   □ 채권/금리 (어떤 듀레이션?)                           │
│   □ 원자재 (유가? 금? 농산물?)                           │
│   □ 통화 (달러? 원화? 신흥국?)                           │
│   □ 크립토 (BTC? 알트? DeFi?)                           │
│   □ 부동산/모기지                                        │
│                                                          │
│   체크 0개 → 탈락 (시장과 무관)                          │
│   체크 1개 → 1점                                        │
│   체크 2개+ → 2점                                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ G2: 변화 벡터 (Change Vector) — LLM 자유 추론           │
│                                                          │
│ "이것이 기존 상태를 바꾸는가, 확인하는가?"                │
│                                                          │
│   새로운 힘의 투입 (방향 전환, 최초 발생, 임계값 돌파)    │
│     → 2점 + 변화 내용 1줄 기록                          │
│                                                          │
│   기존 추세의 가속/감속 (강화 또는 약화)                  │
│     → 1점 + 어떤 추세의 가속/감속인지 기록               │
│                                                          │
│   기존 상태의 단순 확인 (이미 알려진 것의 반복)           │
│     → 0점                                               │
│                                                          │
│   ★ G2는 판별력이 핵심. LLM이 자유 추론한다.             │
│     단, 반드시 "왜 변화/확인인지" 1줄 근거를 붙인다.     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ G3: 전파 가능성 (Propagation Potential) — LLM 자유 추론  │
│                                                          │
│ "이것이 다른 영역으로 번지는가, 여기서 끝나는가?"         │
│                                                          │
│   LLM이 전파 경로를 추론한다:                            │
│     "A → B → C → ..." 형태로 도미노 체인 기술           │
│                                                          │
│   전파 단계 수로 점수:                                    │
│     1단계 (여기서 끝) → 0점                              │
│     2단계              → 1점                              │
│     3단계+             → 2점                              │
│                                                          │
│   예:                                                     │
│     "개별 기업 실적 부진" → 해당 종목만 → 0점             │
│     "호르무즈 LNG 차단 → 비료 → 농업 → 식량 → 인플레"   │
│       → 4단계 → 2점                                     │
│                                                          │
│   ★ G3도 판별력이 핵심. LLM이 자유 추론한다.             │
│     단, 추론한 전파 경로를 반드시 기록한다.               │
│     근거 없는 "전파될 것이다"는 금지.                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ G3.5: 시간 깊이 (Temporal Depth) — 태그 전용            │
│                                                          │
│ "이것은 오늘 시작인가, 누적인가?"                         │
│                                                          │
│   □ 오늘/이번 주 시작 (신규 이벤트) → [SNAPSHOT] 태그    │
│   □ 수개월+ 누적 (장기 진행) → [CUMULATIVE] 태그         │
│                                                          │
│   점수 변경: 없음. 기존 Gate 점수 체계 그대로.           │
│   태그 전달: [CUMULATIVE]이면 Stereo에서 L5 시간축 분해  │
│             자동 발동 + FB-5 시간축 검증 실행.            │
│                                                          │
│   ★ R-07 방어 (2026-03-26 도출):                        │
│     스냅샷 데이터로 구조적 판단을 점프하는 오류 방지.     │
│     [CUMULATIVE] 태그가 Stereo에 "시간축을 봐라" 신호.   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ G4: 시간 긴급성 (Time Urgency) — 체크리스트              │
│                                                          │
│ "이것이 언제 반응이 필요한가?"                            │
│                                                          │
│   □ 오늘/내일 (이벤트 발생 중, 시장 실시간 반응)         │
│     → 2점 + 🔴 즉시                                    │
│   □ 이번 주 (발표 예정, 결정 임박)                       │
│     → 1점 + 🟡 표준                                    │
│   □ 수주~수개월 (구조적 변화, 느린 전파)                  │
│     → 0점 + 🟢 관찰 (backlog 후보)                     │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ G5: 기존 추적 중복 (Overlap Check) — 체크리스트           │
│                                                          │
│ rm state.json + active-watches.json 대조                 │
│                                                          │
│   □ rm에서 현재 수집 중 → ✅수집됨 태그, -3점 감점      │
│   □ Watch에서 추적 중 → 🔄추적중 태그, -2점 감점       │
│   □ 기존과 연결되는 새 전개 → 🆕후속 태그, 감점 없음    │
│   □ 완전히 새로운 이슈 → 태그 없음, 감점 없음           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 점수 산출

```
최종 점수 = G1 × (G2 + G3 + G4) + G5 감점

점수 범위 (G5 감점 전):
  G1(0~2) × (G2(0~2) + G3(0~2) + G4(0~2)) = 0~12

판정:
  8~12: 핵심 쟁점 (거의 확실히 포함)
  5~7:  후보 쟁점 (다른 쟁점과 경합)
  3~4:  약한 후보 (backlog 직행 가능)
  0~2:  탈락

G5 감점 후 3점 미만 → 탈락 (이미 충분히 추적 중)
단, "🆕후속" 태그는 감점 없으므로 새 전개는 살아남음.
```

### 기록 형식

```json
{
  "title": "이란 15-point 휴전안 거부 + 공격 지속",
  "scan_axis": "A",
  "gates": {
    "G1": {"score": 2, "contacts": ["Brent", "S&P500", "금", "방산"]},
    "G2": {"score": 2, "type": "free", "reasoning": "15-point 안 최초 전달 — 전쟁 시작 후 첫 공식 휴전 제안. 새로운 벡터."},
    "G3": {"score": 2, "type": "free", "chain": "휴전 성사 → 호르무즈 재개 → LNG 복구 → 비료 안정 → 인플레 완화 (4단계)"},
    "G4": {"score": 2, "urgency": "즉시"},
    "G5": {"score": 0, "tag": "🆕후속", "overlap": "기존 이란 전쟁의 새 전개"}
  },
  "total_score": 12,
  "status": "핵심"
}
```

---

## Phase S3: 사각지대 보정 + 결정 [GREEN]

**Pass 2에서 8~12건이 남았다. 최종 5~10건 확정 전에 4가지 사각지대를 점검한다.**

```
Q1: 자산군 커버리지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  6개 자산군 체크: 달러 / 금 / 주가 / 채권 / BTC / 부동산
  빠진 군이 있으면 → 해당 군 키워드로 WebSearch 1회 보충
  보충 결과가 G1 1점+ 이면 추가. 없으면 "해당 군 오늘 시그널 없음" 기록.

Q2: 지역 균형
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  글로벌 vs 한국 비율 확인.
  한쪽이 0건이면 → 반대쪽 보충 스캔 1회.
  0건이 아니면 → 통과 (비율 강제 아님).

Q3: backlog 승격
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  backlog 3회+ 반복 이슈가 오늘 A~C축에서 재등장했는가?
  재등장 + Gate 4점+ → 자동 승격 (목록에 🔁 태그로 포함)
  재등장 + Gate 4점 미만 → backlog 유지 (appearance_count +1)
  미등장 → backlog 유지

Q4: 다양성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  전체 이슈의 root_cause가 모두 같은가?
  (예: 8건 모두 "미-이란 전쟁" 파생)
  → D축 결과 중 Gate 4점+ 이슈를 최소 1건 강제 포함
  → 4점+ 없으면 → "비주류 이슈 없음" 기록 (억지 삽입 안 함)
```

**보정 결과를 기록:**

```json
{
  "blind_spot_checks": {
    "Q1_missing_asset": "부동산 — 보충 스캔. 시그널 없음.",
    "Q2_geo_balance": "글로벌 7건 / 한국 2건. 보충 불필요.",
    "Q3_backlog_promotion": "래리 핑크 AI — 3회 반복 + Gate 5점. 승격.",
    "Q4_diversity": "비전쟁 이슈 2건 확보 (AI, ECB). OK."
  }
}
```

---

## Phase S4: 근인 클러스터링 [GREEN]

```
클러스터 판정 기준 (3가지 질문):
  ① 같은 인과 체인에 있는가? (A→B→C면 하나)
  ② 같은 지정학적 사건에서 파생되었는가?
  ③ 같은 정책/규제 변화에서 파생되었는가?

  3개 중 하나라도 YES → 같은 클러스터.

클러스터 구성:
  각 클러스터에:
    id, root_label (근인 라벨)
    구성 이슈 목록 (id + title)
    priority_score (구성 이슈의 최고 Gate 점수)
    market_contact_combined (접촉면 합집합)
    rm_input_title (reaction-monitor 전달용 통합 제목)

  클러스터에 속하지 않는 이슈 → 독립 항목으로 유지.

우선순위 정렬:
  1순위: priority_score 내림차순
  2순위: 구성 이슈 수 내림차순
  3순위: urgency 🔴 > 🟡 > 🟢
```

---

## Phase S5: 사용자 제시 [★ 핵심 승인 지점]

**이 Phase에서 사용자가 목록을 보고 선택한다. 자동 진행 금지.**

### 제시 형식

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 오늘의 이슈 스캔 — [날짜]
   스캔 소스 [N]건 → 이슈 [M]건 추출 → 클러스터 [K]개
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

◆ 클러스터 1: [근인 라벨] ──── 점수 [X] | 🔴즉시
  ├── ① [이슈A 제목] — [1줄 요약]
  ├── ② [이슈B 제목] — [1줄 요약]
  └── ③ [이슈C 제목] — [1줄 요약]
  시장 접촉: [자산/섹터 합집합]
  전파 경로: [G3에서 추론한 도미노 체인]

◆ 클러스터 2: [근인 라벨] ──── 점수 [X] | 🟡표준
  ├── ④ [이슈D 제목] — [1줄 요약]
  └── ⑤ [이슈E 제목] — [1줄 요약]
  시장 접촉: [자산/섹터]

◇ 독립:
  ⑥ [이슈F] — [요약] 🔁3회 반복 | Gate [X]점
  ⑦ [이슈G] — [요약] 🔄추적중 (W-2026-...)
  ⑧ [이슈H] — [요약] 🟢관찰

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 사각지대 점검:
  [Q1~Q4 결과 1줄씩]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Gate 점수 (상위 3건):
  ① [이슈A] G1:2 G2:2 G3:2 G4:2 = 12
  ⑥ [이슈F] G1:2 G2:2 G3:2 G4:1 = 10
  ⑧ [이슈H] G1:2 G2:1 G3:1 G4:2 = 8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
어떤 것을 수집할까요?
  예: "1" / "1, 2" / "1, ⑥" / "전부" / "패스"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### v1.1 추가 규칙

```
클러스터 내 🆕후속 비율 경고:
  클러스터 구성 이슈 중 🆕후속이 50%+ → 경고 표시
  "⚠ 5건 중 2건이 이미 수집됨. 새 각도 3건만 추가 수집 권장."

  이유: 🆕후속이 많으면 rm을 다시 돌려도 중복 수집.
  사용자가 "새 각도만" 선택할 수 있도록 분할 제안.

history 저장 강제:
  Phase S6에서 history/SCAN-YYYYMMDD.json 저장을 반드시 실행.
  최소 내용: issues[], clusters[], blind_spot_checks{}, user_selection[]
  다음 스캔의 D축 + 메타 분석 기반.
```
```

### 사용자 응답 처리

```
"1"       → 클러스터 1만 rm 전달
"1, 2"    → 클러스터 1, 2 순차 rm 전달
"1, ⑥"   → 클러스터 1 + 독립 이슈 ⑥ 각각 rm 전달
"전부"    → 전체 rm 전달 (경고: "N건 실행, 약 X분 소요")
"패스"    → 전부 backlog 저장. rm 미실행.
번호 없이 텍스트 → "번호로 선택해주세요" 재요청
```

---

## Phase S6: 전달 + 백로그 저장 [YELLOW]

### 선택된 클러스터/이슈 → reaction-monitor 전달 (패스스루 포함)

```
전달 형식 (rm Phase 1 입력):
  이슈 제목: rm_input_title (클러스터 통합 제목)

  보조 컨텍스트:
    scanner_origin: {scan_id, date, cluster_id}
    constituent_issues: [구성 이슈 목록]
    initial_sources: [스캔에서 확인한 소스]
    market_contact: [접촉면 합집합]
    propagation_chains: [G3 전파 경로]
    gate_scores: [각 이슈의 Gate 점수]
    temporal_tag: "SNAPSHOT" 또는 "CUMULATIVE" (G3.5에서 판정)

  ★ 패스스루 데이터 (scanner가 이미 수집한 것):
    scanner_prefetch: {
      headlines: [
        해당 클러스터 구성 이슈의 원본 헤드라인 + 요약.
        A/B/C/D 어느 축에서 왔는지 태그 포함.
      ],
      price_snapshot: {
        자산명: 가격 (scanner Phase S1에서 확인된 것).
        예: {"S&P500": 6591.90, "Brent": 98.13, "KRW": 1506.48}
      },
      policy_signals: [
        B축에서 수집된 정책 발표/변화.
        예: "Section 301 16개국 조사 개시 (3/11)"
      ],
      narrative_snippets: [
        A/B/C축에서 수집된 주요 매체 프레임 1줄씩.
        예: {"source": "AP", "frame": "이란 15-point 안 거부"}
      ]
    }

  패스스루 원칙:
    1. scanner가 수집한 것을 버리지 않는다. rm에 그대로 전달.
    2. rm은 prefetch를 BATCH 1 기반으로 사용하고, 심화만 추가 수집.
    3. prefetch가 없으면 (rm 단독 실행) 기존대로 전체 수집. 영향 없음.
    4. prefetch 데이터의 신선도: scanner 실행 시점 기준.
       scanner→rm 전달이 1시간+ 지연되면 가격 재수집 권장.

복수 선택 시 순차 실행:
  클러스터 1 → rm Phase 0~6 완료 → 클러스터 2 → rm Phase 0~6
  병렬 실행 안 함.
```

### 미선택 이슈 → backlog 저장

```
미선택 이슈:
  backlog.json에 추가 (또는 기존 항목의 appearance_count +1)
  last_seen 갱신
  30일+ 미등장 → 자동 아카이브 (Phase S0에서 처리)
```

### 스캔 결과 저장

```
history/SCAN-YYYY-MM-DD.json → 전체 스캔 결과 스냅샷
scan-state.json → 현재 상태 갱신
```

---

## 스키마 정의

### scan-state.json

```json
{
  "last_scan": "ISO 8601",
  "scan_id": "SCAN-YYYYMMDD-NNN",
  "raw_count": "number (원재료 건수)",
  "issues_extracted": "number (Gate 통과 건수)",
  "clusters_formed": "number",
  "independent_issues": "number",
  "selected": ["cluster/issue id"],
  "backlogged": ["issue id"],
  "context": {
    "rm_current_issue": "string",
    "rm_active_watches": "number",
    "backlog_total": "number",
    "seeds_used": ["heartbeat | macro | ghs"]
  }
}
```

### backlog.json

```json
{
  "last_updated": "ISO 8601",
  "issues": [
    {
      "id": "BL-NNN",
      "original_id": "IS-YYYYMMDD-NNN",
      "title": "string",
      "root_cause": "string",
      "first_seen": "YYYY-MM-DD",
      "last_seen": "YYYY-MM-DD",
      "appearance_count": "number",
      "max_gate_score": "number",
      "promoted": "boolean",
      "archived": "boolean",
      "note": "string"
    }
  ],
  "summary": {
    "total_active": "number",
    "repeat_3plus": "number",
    "oldest_unresolved": "YYYY-MM-DD",
    "archived_count": "number"
  }
}
```

### history/SCAN-YYYYMMDD.json

```json
{
  "date": "YYYY-MM-DD",
  "scan_id": "SCAN-YYYYMMDD-NNN",
  "sources_used": [
    {"axis": "A|B|C|D", "tool": "string", "query": "string", "result_count": "number"}
  ],
  "seeds": {
    "heartbeat": ["KC-xx 발동 내역"],
    "macro": "regime string",
    "ghs": ["buried_issues"]
  },
  "raw_headlines": ["string"],
  "issues": [
    {
      "id": "IS-YYYYMMDD-NNN",
      "title": "string",
      "summary": "string",
      "root_cause": "string",
      "scan_axis": "A|B|C|D",
      "sources": ["string"],
      "market_contact": ["string"],
      "gates": {
        "G1": {"score": "0|1|2", "contacts": ["string"]},
        "G2": {"score": "0|1|2", "type": "free", "reasoning": "string"},
        "G3": {"score": "0|1|2", "type": "free", "chain": "string"},
        "G4": {"score": "0|1|2", "urgency": "즉시|표준|관찰"},
        "G5": {"score": "0|-2|-3", "tag": "string", "overlap": "string"}
      },
      "total_score": "number",
      "status": "핵심|후보|약함|탈락",
      "cluster_id": "string | null"
    }
  ],
  "clusters": [
    {
      "id": "CL-YYYYMMDD-NNN",
      "root_label": "string",
      "issues": ["issue id"],
      "priority_score": "number",
      "market_contact_combined": ["string"],
      "rm_input_title": "string"
    }
  ],
  "independent": ["issue id"],
  "blind_spot_checks": {
    "Q1_missing_asset": "string",
    "Q2_geo_balance": "string",
    "Q3_backlog_promotion": "string",
    "Q4_diversity": "string"
  },
  "user_selection": ["cluster/issue id"],
  "handoff": {
    "to": "reaction-monitor",
    "titles": ["string"],
    "timestamp": "ISO 8601"
  }
}
```
