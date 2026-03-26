# 6-Layer Verification Engine — 메타 검증 레이어 (L4) 상세 설계

> 작성일: 2026-03-17
> 위치: 업그레이드 체크리스트(L4)의 상세 설계 문서
> 연관 파일: 6layer-verification-upgrade-checklist.md (L4 항목)
>            6layer-engine-domain-roadmap.md (섹션 7·8)
> 작업 시점: L1~L3 완료 후 별도 스프린트로 실행

---

## 1. 메타 검증이란

```
검증의 3층 구조
│
├── Layer 1: 문서 검증 (현재 구현됨)
│   └── "외부 문서의 주장이 맞는가?"
│       → 6층 파이프라인 (Phase 0~2)이 하는 일
│
├── Layer 2: 검증 감사 (Phase 2.5 — 부분 구현)
│   └── "검증 프로세스가 빠뜨린 것이 있는가?"
│       → 현재 셀프 감사 한계 존재
│
└── Layer 3: 메타 검증 (L4 — 미구현)
    └── "검증 시스템 자체가 제대로 작동하는가?"
        → 엔진의 정확도·일관성·규칙 유효성을 측정
        → L4-01~04가 이 레이어를 구현
```

**핵심 원칙:**
검증 엔진도 검증받아야 한다. 검증자가 자신의 검증을 감사하면 신뢰도가 없다.
이것이 GIPS 외부 검증자 의무, IFCN 연간 재인증 심사와 동일한 논리다.

---

## 2. 글로벌 표준과의 대응

| L4 항목 | 글로벌 표준 대응 | 표준 원칙 |
|---|---|---|
| L4-01 결과 추적 | CFA V(A) | "권고 정확도를 시계열로 측정하는 기준 보유" |
| L4-01 결과 추적 | IFCN | "연간 재인증 — 팩트체킹 기관 자체를 외부가 심사" |
| L4-02 감사 독립화 | GIPS Verifier | "운용사 성과를 독립 기관이 재검증" |
| L4-03 포맷 표준화 | GIPS | "공정 표현과 완전 공개 — 비교 가능한 형태" |
| L4-04 오답노트 | Knowledge Elicitation | "실전 실패에서 역추출하는 전문 규칙" |

---

## 3. L4-01 — 검증 결과 추적 메커니즘

### 3-1. 왜 필요한가

```
현재 문제
├── 검증 실행 → 결과 출력 → 끝
├── 🟢 판정이 실제로 맞았는지 아무도 모름
├── RULES.md의 lr_007이 계속 틀려도
│   얼마나 틀리는지 측정 불가
└── 규칙이 개선될 근거가 없음 → 엔진이 영원히 제자리
```

### 3-2. 구체적으로 하는 일

```
검증 실행 시 흐름 변화

현재:
검증 실행 → 결과 출력 → 끝

L4-01 이후:
검증 실행
    └── 결과 출력
    └── Notion + invest-db 자동 저장
        ├── verified_at: 오늘 날짜
        ├── overall_verdict: 🟢
        ├── top_flag: lr_005
        └── outcome_check_due: 90일 후 날짜

90일 후 heartbeat 자동 알림:
"[검증 추적] 2026-03-17 리포트 결과 확인 시점입니다"
    └── 희발님 확인
        ├── outcome_correct: True / False
        └── failure_reason: 전제붕괴 / 수치오류 / 생략 / 이해충돌
```

### 3-3. 필요한 인프라

**invest-db 신규 테이블 2개:**

```sql
-- 테이블 1: 검증 이력
CREATE TABLE verification_results (
  id              SERIAL PRIMARY KEY,
  document_id     VARCHAR(100),        -- 검증 대상 문서 식별자
  document_type   VARCHAR(50),         -- equity / crypto / macro / geo
  verified_at     TIMESTAMP,           -- 검증 실행 시점
  overall_verdict VARCHAR(10),         -- 🟢🟡🔴⚫
  top_flag        VARCHAR(200),        -- 최고 리스크 플래그 ID
  validity_until  DATE,                -- 유효기간
  json_path       VARCHAR(300),        -- JSON 저장 경로
  created_at      TIMESTAMP DEFAULT NOW()
);

-- 테이블 2: Claim별 결과 추적
CREATE TABLE verification_claim_outcomes (
  id                SERIAL PRIMARY KEY,
  verification_id   INT REFERENCES verification_results(id),
  claim_text        TEXT,              -- 검증한 Claim 원문
  claim_type        VARCHAR(50),       -- fact / estimate / opinion
  verdict_at_check  VARCHAR(10),       -- 검증 당시 판정
  outcome_at        DATE,              -- 실제 결과 확인 시점
  outcome_correct   BOOLEAN,          -- 판정이 맞았는가
  failure_reason    VARCHAR(200),      -- 실패 원인 분류
  rule_triggered    VARCHAR(50),       -- 발동된 규칙 ID (lr_xxx)
  created_at        TIMESTAMP DEFAULT NOW()
);
```

**Notion DB(ee345e95) 신규 필드 6개:**

| 필드명 | 타입 | 용도 |
|---|---|---|
| `verified_at` | Date | 검증 실행일 |
| `verification_verdict` | Select (🟢🟡🔴⚫) | 검증 종합 판정 |
| `top_flag_id` | Text | 최고 리스크 플래그 ID |
| `outcome_check_due` | Date | 결과 확인 예정일 (verified_at + 90일) |
| `outcome_correct` | Checkbox | 판정이 맞았는가 |
| `failure_reason` | Select | 수치오류 / 전제붕괴 / 생략 / 이해충돌 |

### 3-4. 효과

```
이것이 작동하면
├── "lr_007: 최근 3개월 정확도 40%" 자동 집계
├── heartbeat가 "이 규칙 재검토 권장" 알림 발송
└── L4-04 오답노트의 소재가 자동으로 쌓임
    → L4-01 없이는 L4-04가 작동하지 않음
```

---

## 4. L4-02 — Phase 2.5 Coverage Audit 독립화

### 4-1. 왜 필요한가

```
현재 셀프 감사 문제
│
├── Claude가 ①~⑥ 판정 수행
└── 동일한 Claude가 "내가 잘 했나?" 스스로 체크
    → 자기 오류를 자기가 못 잡는 구조
    → "MCP 조회 없이 🟢 판정" 같은 V-01 위반을
       자기 감사에서 발견하지 못하는 경우 발생
```

### 4-2. 구체적으로 하는 일

**SKILL.md Phase 2.5에 추가할 내용:**

```
[역할 전환 선언 — 필수]
Phase 2 판정 완료.
이제 감사자(Auditor) 역할로 전환합니다.
판정자가 수행한 Phase 2 결과를 독립적 관점에서 점검합니다.

감사 체크포인트:
□ ① Fact — 판정자가 MCP를 실제로 호출했는가?
            lr_* 규칙 ID 없이 🟢를 내리지 않았는가?
□ ② Norm — CHECKLISTS.md item_id를 실제로 인용했는가?
□ ③ Logic — RULES.md를 실제로 읽고 대입했는가?
             수치 부재 시 "적용 불가"로 통과시키지 않았는가?
□ ④ Temporal — 기준 시점을 추출했는가?
□ ⑤ Incentive — 면책 조항 스캔을 실제로 했는가?
□ ⑥ Omission — BBJ Break를 최소 1개 생성했는가?

감사 결과:
- 위반 발견 시 → 해당 층 재실행 요청
- 이상 없음 → Phase 3 진행 승인
```

### 4-3. 왜 "같은 Claude"인데 효과가 있는가

```
역할 선언의 인지적 효과
│
├── 판정자 모드: "이 수치가 맞는가?" (탐색적)
└── 감사자 모드: "판정자가 규칙을 지켰는가?" (규칙 준수 점검)
    → 동일 모델이지만 관점이 전환됨
    → 자기 오류 탐지 확률 실질적으로 향상

GIPS Verifier 원칙의 소프트 버전:
"완전한 외부 분리가 없어도 역할 분리만으로
 편향을 상당 부분 감소시킬 수 있다"
```

---

## 5. L4-03 — OUTPUT_FORMAT.md 신규 생성

### 5-1. 왜 필요한가

```
현재 문제
├── SKILL.md Phase 3: "OUTPUT_FORMAT.md를 읽고 출력하라"
├── 그 파일이 존재하지 않음
└── Claude가 매번 임의로 포맷을 만듦
    → 검증 A: SUMMARY 블록이 맨 앞
    → 검증 B: 층별 판정이 산문으로 서술
    → 검증 C: KC LIST 없음
    → 비교·추적 불가
    → L4-01 추적 메커니즘도 무력화
```

### 5-2. OUTPUT_FORMAT.md에 들어갈 내용

```
[SUMMARY] — 종합 판정 블록 (맨 위 고정)
─────────────────────────────────────
문서명: [리포트 제목]
문서 유형: equity_research
검증일: 2026-03-17
전체 판정: 🔴 FLAGGED
최고 리스크: lr_005 — 하방 시나리오 없는 일방적 전망 (high)
유효기간: 2026-04-17 (1개월)
─────────────────────────────────────

[LAYER TABLE] — 6층 판정 요약
| 층 | 이름 | 판정 | 핵심 근거 | 플래그 ID |
|---|---|---|---|---|
| ① | Fact Ground | 🟢 | PER 12.3x DART 일치 | - |
| ② | Norm Ground | 🟡 | 목표가 근거 모호 | nr_eq_004 |
| ③ | Logic Ground | 🔴 | 하방 시나리오 없음 | lr_005 |
| ④ | Temporal Ground | 🟢 | 수치 기준일 유효 | - |
| ⑤ | Incentive Ground | 🟡 | 주간사 관계 공시됨 | - |
| ⑥ | Omission Ground | 🔴 | 수출규제 미언급 | om_semi_001 |

[CLAIM LIST] — Claim별 결과
| # | Claim | 유형 | 근거유형 | 판정 | 플래그 |
|---|---|---|---|---|---|
| 1 | "PER 12.3배로 저평가" | 수치주장 | fact | 🟢 | - |
| 2 | "업황 회복으로 실적 반등 전망" | 예측 | estimate | 🔴 | lr_005 |

[KC LIST] — Kill Condition 목록
| KC | 전제 내용 | 현재 상태 | 판정 |
|---|---|---|---|
| KC-1 | 반도체 재고조정 완료 | FRED ISM 48.2 (미완료) | 🔴 트리거 |
| KC-2 | 메모리 ASP 반등 | 횡보 중 | 🟡 |

[BBJ BREAK] — 반론 목록
| Break | 임팩트 | 문서 언급 | Omission |
|---|---|---|---|
| 대중 수출규제 강화 시 매출 30% 직격 | 매우 높음 | ❌ 없음 | 🔴 플래그 |

[JSON] — verification_store v1.1
{
  "doc_id": "samsung_2026Q1_report",
  "doc_type": "equity_research",
  "verified_at": "2026-03-17T09:00:00",
  "overall_verdict": "🔴",
  "validity_until": "2026-04-17",
  "layers": [
    {"id": 1, "name": "Fact", "verdict": "🟢", "flag": null},
    ...
  ],
  "claims": [...],
  "kc_list": [...],
  "bbj_breaks": [...]
}

[TELEGRAM] — heartbeat 전송 포맷 (압축)
🔴 [검증 완료] 삼성전자 Q1 리포트
├── 종합: 🔴 FLAGGED
├── 최고 리스크: lr_005 하방 시나리오 없음
├── KC 트리거: 반도체 재고조정 미완료
└── 유효기간: 2026-04-17

[DISCLAIMER] — 면책 경고 (고정 문구)
본 검증 결과는 법률·투자 자문이 아닙니다.
최종 판단은 사용자 본인에게 있습니다.
```

### 5-3. 이 파일이 없으면 무너지는 것

```
OUTPUT_FORMAT.md 부재 시 연쇄 영향
├── L4-01 추적 불가 (포맷이 달라서 DB 저장 구조 불일치)
├── heartbeat Telegram 포맷 불일치
├── 검증 결과 간 비교 불가
└── 오답노트 리뷰 시 "이전에 뭐라고 판정했지?" 확인 어려움
```

---

## 6. L4-04 — 실전 오답노트 → 규칙화 프로세스

### 6-1. 왜 가장 핵심인가

```
L1~L3 vs L4-04
│
├── L1~L3: "현재 알고 있는 것"을 파일에 반영
│   → 완성되면 그 시점에서 멈춤
│
└── L4-04: "앞으로 알게 되는 것"을 반영하는 루프
    → 엔진이 시간이 갈수록 정교해짐
    → BloombergGPT가 363B 토큰으로 학습한 것을
       실전 실패 역추출로 대체
    → 비용 없이 도메인 전문성 축적
```

### 6-2. 월 1회 오답노트 리뷰 프로세스 (30분)

```
Step 1: 소재 수집 (5분)
  Notion에서 outcome_correct = False 케이스 조회
  또는 heartbeat가 보낸 "규칙 재검토 권장" 알림 목록 확인

Step 2: 실패 원인 분류 (10분)
  각 케이스마다:
  ├── 수치 오류: MCP 데이터가 틀렸음 (FRED 시리즈 오조회 등)
  ├── 전제 붕괴: KC 전제가 이미 깨진 상태였음
  ├── 생략: 리포트가 숨긴 리스크를 못 잡음
  └── 이해충돌: 저자 편향을 탐지 못함

Step 3: 규칙 초안 작성 (10분)
  원인 → 새로운 규칙 조건으로 변환
  예시:
  "삼성전자 리포트 검증 시 🟢 판정
   → 다음 분기 실적 크게 하락
   → 원인: HBM 고객사 집중도(NVIDIA 의존) 미탐지
   → 신규 항목: om_semi_008 CoWoS 패키징 병목
   → 이미 L3-06으로 추가됨 ← 이런 식으로 귀납"

Step 4: RULES.md / CHECKLISTS.md 업데이트 (5분)
  규칙 버전 번호 부여 (lr_021, lr_022...)
  또는 기존 규칙 조건 세분화 (lr_007 → lr_007_v2)
```

### 6-3. 오답노트 Notion 페이지 구조

```
페이지명: [검증 오답노트]
위치: Notion 아카이브 하위

| 날짜 | 검증 대상 | 판정 | 실제 결과 | 실패 원인 | 신규 규칙 초안 | 반영 여부 |
|---|---|---|---|---|---|---|
| 2026-03-17 | 삼성전자 Q1 | 🟢 | ❌ 실적 하락 | 생략 | om_semi_008 | ✅ |
| 2026-03-20 | BTC 분석 | 🟢 | ❌ 가격 급락 | 전제붕괴 | KC 조건 강화 | 🔲 |
```

---

## 7. L4 4개 항목의 순환 구조

```
L4 메타 검증 피드백 루프
│
L4-03 OUTPUT_FORMAT.md
    ↓ 일관된 포맷으로 저장되어야
L4-01 결과 추적
    ↓ 추적된 실패가 쌓여야
L4-04 오답노트 → 규칙화
    ↓ 규칙이 정교해져야
L4-02 Coverage Audit이 더 잘 작동
    ↓ 감사가 정교해져야
L4-03 포맷 기준도 더 명확해짐
    ↓
(다시 L4-01로)

→ 4개가 독립이 아니라 순환 구조
→ L4-03이 없으면 L4-01이 불완전
→ L4-01이 없으면 L4-04의 소재가 없음
→ 이 순환이 돌기 시작하면 엔진이 스스로 개선
```

---

## 8. 실행 순서 및 의존성

```
실행 전제: L1~L3 작업 완료 후 별도 스프린트

Step 1: L4-03 OUTPUT_FORMAT.md 생성 (3시간)
  → 나머지 모든 L4 작업의 인프라
  → 이것이 없으면 L4-01의 JSON 저장 구조가 확정 불가

Step 2: L4-01 invest-db 테이블 2개 생성 (2시간)
  → verification_results
  → verification_claim_outcomes

Step 3: L4-01 Notion 필드 6개 추가 (30분)
  → outcome_check_due 자동 계산 설정

Step 4: L4-02 SKILL.md Phase 2.5 역할 전환 선언 추가 (30분)

Step 5: L4-04 Notion 오답노트 페이지 생성 (30분)
  → 첫 월간 리뷰를 위한 빈 테이블 준비

Step 6: heartbeat.py 연동 모듈 추가 (별도 스프린트)
  → 실시간 재검증 트리거 모듈
  → 월간 규칙 정확도 집계 모듈
  → Telegram 포맷 OUTPUT_FORMAT.md [TELEGRAM] 섹션 기반
```

---

## 9. 완료 기준

| 항목 | 완료 기준 |
|---|---|
| L4-03 | OUTPUT_FORMAT.md 존재 + 검증 2회 실행 시 포맷 동일 |
| L4-01 | 검증 후 invest-db + Notion 자동 저장 확인 |
| L4-02 | Phase 2.5에서 "감사자 역할 전환" 선언 출력 확인 |
| L4-04 | 첫 월간 리뷰 실행 + 최소 1개 규칙 추가됨 |
| 메타 검증 가동 | heartbeat가 "규칙 재검토 권장" 알림 발송 시작 |

---

## 10. L4의 본질 — 한 줄 정의

> **L4 메타 검증 레이어는 "6층 검증 엔진 자체를 검증하는 시스템"이다.
> L1~L3이 엔진의 몸체라면, L4는 엔진이 스스로 학습하고 개선되는 신진대사다.**

---

*본 문서는 L4 메타 검증 레이어의 상세 설계 노트입니다.*
*L1~L3 완료 확인 후 이 문서를 기준으로 작업을 시작하세요.*
*heartbeat.py 연동은 별도 스프린트로 분리하여 진행합니다.*
