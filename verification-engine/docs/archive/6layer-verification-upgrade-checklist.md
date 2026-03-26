# 6-Layer Verification Engine — 업그레이드 체크리스트

> 작성일: 2026-03-17
> 기반: 글로벌 표준(CFA V(A), IFCN, GIPS, Knowledge Elicitation 연구) 대비 갭 분석
> 대상 파일: SKILL.md / RULES.md / CHECKLISTS.md / OUTPUT_FORMAT.md(신규)

---

## 읽는 법

| 레벨 | 기준 | 예상 시간 | 대상 파일 |
|---|---|---|---|
| 🔴 L1 즉시 | 구조 리스크 차단 — 현재 판정 오염 가능 | 1~2시간 | SKILL.md |
| 🟠 L2 단기 | 작동 안 하는 도메인 규칙 추가 | 반나절 | RULES.md |
| 🟡 L3 중기 | PSF 핵심 도메인 섹터 확장 | 2~3일 | CHECKLISTS.md |
| 🔵 L4 장기 | 구조 설계 변경 — 살아있는 엔진 전환 | 1~2주 | 복수 파일 |

완료 시 `[x]`로 체크. 각 항목은 독립 실행 가능.

---

## 🔴 L1 — 즉시 반영 (SKILL.md)

### L1-01 MCP 전수 수집 선언 조항 추가
- [ ] **위치:** Phase 2 시작 직전 (Phase 1 종료 바로 다음)
- [ ] **추가할 내용:**
  ```
  ### [수집 완료 선언 — Phase 2 진입 전 필수]
  문서 유형에 해당하는 MCP 소스를 전부 호출 완료한다.
  수집 중 판정 금지. 수집 완료 선언 후 → 판정 시작.
  
  equity_research  → DART + SEC-EDGAR + Yahoo Finance + FRED 전부 완료
  crypto_research  → CoinGecko + DeFiLlama + CoinMetrics + Etherscan 전부 완료
  legal_contract   → 내부 정합성 스캔 완료
  macro_report     → FRED + IMF/OECD 컨센서스 + Fed Dot Plot 완료
  geopolitical     → 관련 뉴스 Tavily 수집 + 에너지 지표 FRED 완료
  ```
- [ ] **이유:** 현재 수집+판정이 인터리브드 → 한 층 결과가 다른 층 판정을 암묵적으로 오염. CFA V(A) "합리적 근거" 원칙 위반.

---

### L1-02 Claim 추출 출력에 근거유형 필드 추가
- [ ] **위치:** Phase 1 — `각 claim에 유형 태그 부착` 섹션
- [ ] **현재:**
  ```
  수치주장 → ① Fact 우선 검증
  인과주장 → ③ Logic + ⑥ Omission 우선 검증
  의견     → ⑤ Incentive 맥락에서 참조
  예측     → ④ Temporal + ③ Logic (KC 추출)
  사실진술 → ① Fact 검증
  조항     → ② Norm 검증 (법률 계약)
  ```
- [ ] **변경 후:**
  ```
  수치주장 | fact     → ① Fact 우선 검증
  수치주장 | estimate → ① Fact + 🟡 하향 기본값
  인과주장 | opinion  → ③ Logic + ⑥ Omission 우선 검증
  예측     | estimate → ④ Temporal + ③ Logic (KC 추출)
  사실진술 | fact     → ① Fact 검증
  조항     | fact     → ② Norm 검증 (법률 계약)
  ```
- [ ] **이유:** CFA 표준 "Distinguish between fact and opinion" 명시 의무 — 현재 출력에서 누락. 동일 수치도 추정이면 검증 기준이 달라야 함.

---

### L1-03 수치 부재 자체를 플래그 대상으로 명시
- [ ] **위치:** Phase 2 ③ Logic 섹션 + RULES.md 적용 방법 섹션
- [ ] **SKILL.md에 추가할 내용:**
  ```
  수치 부재 처리 규칙:
  - 규칙 대입에 필요한 수치를 추출할 수 없는 경우:
    → P1 Claim에 해당하면: 🟡 PLAUSIBLE로 하향 (기존 "적용 불가" 대체)
    → P2~P4 Claim에 해당하면: ⚫ NO BASIS 표기 후 통과
  - "결론을 지탱하는 수치가 서술형으로만 표현된 경우"는
    P1 수치 부재로 간주하고 lr_020 규칙 적용
  ```
- [ ] **이유:** 현재 수치 없으면 규칙이 통과 → P1 결론 근거를 서술형("방어력 높음")으로 숨기면 검증 엔진이 무력화됨.

---

## 🟠 L2 — 단기 반영 (RULES.md)

> 신규 섹터 `### 매크로 리포트 / macro_report 규칙` 추가

### L2-01 매크로 금리 전망 규칙
- [ ] **ID:** lr_017
- [ ] **조건:** 금리 전망 주장 AND Fed Dot Plot / 중앙은행 포워드가이던스 미인용
- [ ] **플래그 메시지:** 금리 전망의 1차 소스 부재. 자체 추정인지 공식 전망인지 불명확
- [ ] **심각도:** high

---

### L2-02 GDP/성장 전망 규칙
- [ ] **ID:** lr_018
- [ ] **조건:** GDP 전망 수치 AND IMF·OECD·Bloomberg 컨센서스 미비교
- [ ] **플래그 메시지:** 성장 전망이 글로벌 컨센서스 대비 괴리 여부 미확인
- [ ] **심각도:** medium

---

### L2-03 인플레이션 전망 규칙
- [ ] **ID:** lr_019
- [ ] **조건:** 인플레이션 전망 AND 최신 PCE/CPI 실측값 미비교
- [ ] **플래그 메시지:** 전망이 현재 실측 추세와 일치하는지 확인 불가
- [ ] **심각도:** high

---

### L2-04 결론 수치 서술형 은폐 규칙
- [ ] **ID:** lr_020
- [ ] **조건:** P1 Claim(결론 지탱 수치)이 정량 수치 없이 서술형으로만 표현
- [ ] **예시 트리거:**
  - "방어력이 높다" → 구체적 수치(부실률, LTV 등) 없음
  - "상당한 성장세" → % 수치 없음
  - "유동성이 충분하다" → 구체적 커버리지 비율 없음
- [ ] **플래그 메시지:** 결론 근거가 검증 불가능한 서술형으로만 표현됨. 정량화 필요.
- [ ] **심각도:** high

---

### L2-05 크립토 MVRV 규칙 컨텍스트 세분화
- [ ] **기존 lr_007 → lr_007_v2로 대체**
- [ ] **변경 전:** `MVRV > 3.0 AND 매수추천 → 🔴`
- [ ] **변경 후 (조건 분기):**
  ```
  MVRV > 3.0 AND 매수추천
    AND 사이클 경과 > 18개월 → 🔴 고평가 구간 매수. 과열 리스크 미반영.
    AND 사이클 경과 < 6개월  → 🟡 Bull 초기 가능. 사이클 위치 확인 필요.
    AND 사이클 정보 없음     → 🟡 사이클 컨텍스트 미확인. 근거 추가 필요.
  ```
- [ ] **이유:** 동일 MVRV 3.0이라도 Bull 첫해 vs 사이클 말 해석이 완전히 다름. 단순 임계값 규칙은 과도한 🔴 또는 누락 🟢를 발생시킴.

---

## 🟡 L3 — 중기 반영 (CHECKLISTS.md)

### L3-01 매크로 리포트 Omission 섹터 신규 추가
- [ ] **섹터명:** `### 매크로 리포트 (macro_report)`
- [ ] **추가할 항목:**

| ID | 필수 항목 | 임팩트 | 탐지 키워드 |
|---|---|---|---|
| om_macro_001 | FOMC 경로 언급 | critical | Fed, FOMC, Dot Plot, 기준금리, 포워드가이던스 |
| om_macro_002 | 실질금리 기준값 | high | 실질금리, real rate, TIPS, 기대인플레이션 |
| om_macro_003 | GLI 방향성 | high | GLI, 글로벌유동성, 확장, 수축, 레짐 |
| om_macro_004 | 달러 방향성(DXY) | high | DXY, 달러, 달러인덱스, dollar |
| om_macro_005 | 신용 스프레드 수준 | high | HY스프레드, IG스프레드, credit spread, 하이일드 |
| om_macro_006 | 시나리오 확률 합계 검증 | medium | Base, Bull, Bear, 시나리오, 확률, 가능성 |
| om_macro_007 | 유효기간 / 업데이트 조건 | low | 유효기간, 재검토, 트리거, 조건부 |

---

### L3-02 지정학 분석 Omission 섹터 신규 추가
- [ ] **섹터명:** `### 지정학 분석 (geopolitical)`
- [ ] **추가할 항목:**

| ID | 필수 항목 | 임팩트 | 탐지 키워드 |
|---|---|---|---|
| om_geo_001 | 에너지 경로 리스크 | critical | 호르무즈, 흑해, 파이프라인, 에너지, LNG |
| om_geo_002 | 시나리오 확률 배분 근거 | high | 시나리오, 확률, Base, Bear, 가능성 |
| om_geo_003 | Base/Bull/Bear 전부 포함 | high | Base, Bull, Bear, 낙관, 비관 |
| om_geo_004 | 역사적 유사 사례 | medium | 유사, 전례, 역사, 과거, 사례 |
| om_geo_005 | 타임라인 명시 | medium | 단기, 중기, 장기, 1개월, 6개월, timeline |
| om_geo_006 | 2차 효과(금융시장 연쇄) | high | 금리, 환율, 원자재, 시장, 연쇄, spillover |

---

### L3-03 SaaS/IT 섹터 Omission 신규 추가
- [ ] **섹터명:** `### SaaS/IT 섹터`
- [ ] **추가할 항목:**

| ID | 필수 항목 | 임팩트 | 탐지 키워드 |
|---|---|---|---|
| om_saas_001 | ARR/NRR 성장 추이 | critical | ARR, NRR, 반복매출, 순수익유지율 |
| om_saas_002 | Rule of 40 충족 여부 | high | Rule of 40, 성장률+이익률 |
| om_saas_003 | 고객 집중도 | high | 상위고객, 집중도, top customer, 의존도 |
| om_saas_004 | 번오프율(Churn) | high | Churn, 이탈률, 해지, 유지율 |
| om_saas_005 | AI 경쟁 위협 | high | AI, 경쟁, ChatGPT, Copilot, 대체 |

---

### L3-04 NORM — 매크로/지정학 리포트 유형 추가
- [ ] **현재 NORM 커버리지:** equity_research / crypto_research / finance_alt / legal_contract
- [ ] **신규 추가 유형: `macro_report`**

| ID | 항목 | 심각도 |
|---|---|---|
| nr_macro_001 | 데이터 출처 명시 (FRED, IMF, Bloomberg 등) | high |
| nr_macro_002 | 기준 시점 명시 (수치의 기준일) | high |
| nr_macro_003 | 시나리오 가정 근거 명시 | medium |
| nr_macro_004 | 투자 자문 아님 면책 | medium |

- [ ] **신규 추가 유형: `geopolitical_report`**

| ID | 항목 | 심각도 |
|---|---|---|
| nr_geo_001 | 정보 출처 명시 (뉴스, 정부 발표, 싱크탱크) | high |
| nr_geo_002 | 분석 시점 명시 | high |
| nr_geo_003 | 불확실성 경고 (지정학은 예측 불가 요소 多) | high |

---

### L3-05 크립토 Omission 보강
- [ ] **기존 섹터에 항목 추가:**

| ID | 필수 항목 | 임팩트 | 탐지 키워드 |
|---|---|---|---|
| om_crypto_006 | 브릿지/크로스체인 리스크 | high | 브릿지, bridge, 크로스체인, 해킹, exploit |
| om_crypto_007 | 중앙화 리스크 | high | 팀지갑, 멀티시그, multisig, 발행자, 집중 |
| om_crypto_008 | 거버넌스 리스크 | medium | DAO, 투표, governance, 참여율, 집중도 |

---

### L3-06 반도체 Omission 보강
- [ ] **기존 섹터에 항목 추가:**

| ID | 필수 항목 | 임팩트 | 탐지 키워드 |
|---|---|---|---|
| om_semi_007 | CoWoS/패키징 병목 | high | CoWoS, 패키징, HBM, 어드밴스드패키징, TSMC |
| om_semi_008 | 고객사 집중도 | high | Apple, NVIDIA, 의존도, 고객집중, 단일고객 |

---

## 🔵 L4 — 장기 반영 (구조 설계)

### L4-01 검증 결과 추적 메커니즘 (Notion 연동)
- [ ] **내용:** 검증 시 🟢 판정 받은 claim을 3개월 후 실제 결과와 대조
- [ ] **구현 방법:**
  - Notion 아카이브 "검증 이력" DB에 신규 필드 추가
  - 필드: `verified_at` / `outcome_at` / `outcome_correct (True/False)` / `failure_reason`
- [ ] **효과:** "틀린 🟢"가 쌓이면 → 해당 규칙 재검토 트리거. 살아있는 엔진으로 전환.
- [ ] **주기:** 월 1회 오답노트 리뷰 → RULES.md 업데이트

---

### L4-02 Phase 2.5 Coverage Audit 독립화
- [ ] **문제:** 현재 Claude가 자신의 작업을 자신이 감사 → 셀프 검증 편향
- [ ] **변경 방법:**
  - Phase 2 완료 후 명시적 역할 전환 선언:
    `"이제 감사자(Auditor) 역할로 전환. Phase 2 결과를 독립적으로 점검합니다."`
  - 이후 Phase 2.5 실행
- [ ] **효과:** 역할 분리로 자기 오류 탐지 확률 향상 (GIPS Verifier 개념 적용)

---

### L4-03 OUTPUT_FORMAT.md 신규 생성
- [ ] **현재 문제:** Phase 3·4에서 참조하는 OUTPUT_FORMAT.md 파일이 존재하지 않음 → 검증마다 출력 포맷이 다름
- [ ] **포함할 내용:**
  ```
  [SUMMARY] 종합 판정 블록
    - 전체 등급 (🟢/🟡/🔴/⚫)
    - 최고 리스크 플래그 1개 (가장 심각한 것)
    - 유효기간

  [LAYER TABLE] 층별 판정 테이블
    | 층 | 판정 | 핵심 근거 | 플래그 ID |
    
  [CLAIM LIST] Claim별 결과
    - Claim 텍스트 | 유형 | 판정 | 근거

  [KC LIST] Kill Condition 목록
    - KC 전제 | 현재 상태 | 판정

  [BBJ BREAK] Break 목록
    - Break 내용 | 문서 언급 여부 | 임팩트

  [JSON] verification_store v1.1 스키마
    - 저장 경로, 필드 정의, 예시

  [DISCLAIMER] 면책 경고 표준 문구
  ```

---

### L4-04 실전 오답노트 → 규칙화 프로세스
- [ ] **작업 순서:**
  1. Notion 아카이브에서 "예측 틀린 분석" 검색
  2. 실패 원인 분류: 수치 오류 / 전제 붕괴 / 생략 / 이해충돌 미탐지
  3. 원인별 → RULES.md 신규 규칙 or CHECKLISTS.md 항목으로 코드화
- [ ] **주기:** 월 1회 정기 실행
- [ ] **핵심 원칙:** 책이나 논문이 아니라 실전 실패에서 역추출하는 것이 진짜 전문 규칙의 소재

---

## 실행 순서 (권장)

```
Step 1: L1-01 → SKILL.md Phase 2 앞에 2줄 추가 (30분)
Step 2: L1-02 → SKILL.md Phase 1 태그 수정 (30분)
Step 3: L1-03 → SKILL.md + RULES.md 수치 부재 처리 추가 (30분)
Step 4: L2-01~04 → RULES.md 매크로 섹터 신규 추가 (2시간)
Step 5: L2-05 → RULES.md lr_007 → lr_007_v2 교체 (30분)
Step 6: L3-01~02 → CHECKLISTS.md 매크로·지정학 섹터 추가 (3시간)
Step 7: L4-03 → OUTPUT_FORMAT.md 신규 생성 (3시간)
Step 8: L3-03~06 → CHECKLISTS.md 나머지 섹터 (2시간)
Step 9: L4-01~02 → Notion 연동 + Phase 2.5 독립화 (별도 스프린트)
Step 10: L4-04 → 오답노트 프로세스 구축 (별도 스프린트)
```

---

## 완료 기준

| 체크 | 기준 |
|---|---|
| L1 완료 | SKILL.md에 MCP 선언 조항 + 근거유형 태그 + 수치부재 처리 반영됨 |
| L2 완료 | RULES.md에 lr_017~020 추가 + lr_007_v2 교체됨 |
| L3 완료 | CHECKLISTS.md에 매크로·지정학·SaaS 섹터 추가됨 |
| L4 완료 | OUTPUT_FORMAT.md 생성 + Notion 추적 필드 추가됨 |
| 전체 완료 | 매크로 리포트 검증 시 ⚫가 아닌 실제 판정이 나옴 |

---

*본 문서는 6-Layer Verification Engine의 점진적 고도화 로드맵입니다.*
*글로벌 기준(CFA V(A), IFCN Code of Principles, GIPS, Knowledge Elicitation 연구) 대비 갭 분석 기반.*
