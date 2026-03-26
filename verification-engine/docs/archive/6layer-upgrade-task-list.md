# 6-Layer Verification Engine 업그레이드 — 전체 작업 과정

> 작성일: 2026-03-17
> 소스: 체크리스트 + MCP 요구사항 통합
> 읽는 법: 위에서 아래로 순서대로 실행. 블록 단위로 독립 실행 가능.

---

## BLOCK 0 — 사전 점검 (작업 시작 전 필수)

> 이 블록을 완료하지 않으면 L2 작업이 불완전하게 실행됨.

- [ ] **0-1** FRED 시리즈 ID 정상 반환 테스트
  - `FEDTARMD` → Fed Dot Plot 중앙값
  - `DTWEXBGS` → 달러 광의지수(DXY 대용)
  - `REAINTRATREARAT10Y` → 실질금리 10년
  - `A191RL1Q225SBEA` → GDP 성장률 전기비연율
  - 테스트 방법: FRED MCP로 각 시리즈 직접 호출 → 값 반환 확인

- [ ] **0-2** CoinMetrics BTC 사이클 날짜 추출 확인
  - 확인 항목: CoinMetrics MCP가 BTC historical low date 반환하는지
  - 대안 확인: CoinGecko history API로 최저가 날짜 추출 가능한지
  - 목적: lr_007_v2 (MVRV 사이클 컨텍스트 분기) 실행 조건

- [ ] **0-3** Firecrawl → IMF·OECD 페이지 추출 테스트
  - 테스트 URL: `https://www.imf.org/en/Publications/WEO`
  - 테스트 URL: `https://stats.oecd.org/`
  - 확인 항목: PDF 포함 페이지 텍스트 추출 가능 여부
  - 실패 시: Tavily search로 대체 경로 확인

- [ ] **0-4** OpenBB MCP 도입 여부 결정
  - 필요 이유: GDP·CPI 컨센서스(시장 전망 평균) 구조화 데이터
  - 옵션 A: OpenBB Platform Python SDK → MCP 서버 구축
  - 옵션 B: Trading Economics API 유료 구독
  - 옵션 C: Tavily + Trading Economics 스크래핑으로 임시 대체
  - **결정 후 진행 → L2-01·02 작업 품질에 직접 영향**

---

## BLOCK 1 — SKILL.md 수정 (L1 전체)

> 대상 파일: `/mnt/skills/user/6layer-verification/SKILL.md`
> 의존성: 없음. 즉시 실행 가능.

- [ ] **1-1** Phase 1 → Phase 2 사이에 MCP 전수 수집 선언 조항 삽입
  - 위치: Phase 1 종료 직후, Phase 2 시작 직전
  - 내용: 도메인별 MCP 전수 호출 완료 선언 + 수집 중 판정 금지 원칙
  - 신규 도메인 매핑 추가:
    - `macro_report` → FRED + Tavily(IMF/OECD)
    - `geopolitical` → Tavily + FRED(에너지)

- [ ] **1-2** Phase 1 Claim 태그에 근거유형 필드 추가
  - 위치: `각 claim에 유형 태그 부착` 섹션
  - 변경: 기존 유형 태그에 `| fact / estimate / opinion` 구분 추가
  - 판정 연동: `estimate` 태그 → ① Fact 판정 기본값 🟡 하향

- [ ] **1-3** Phase 2 ③ Logic 섹션에 수치 부재 처리 규칙 추가
  - 위치: Phase 2 ③ Logic 실행 지침 하단
  - 내용: P1 Claim 수치 부재 → 🟡 하향 / P2~P4 → ⚫ NO BASIS
  - 연동: lr_020 규칙(L2-04) 참조 명시

- [ ] **1-4** Phase 0 문서 유형 판별 섹션에 신규 유형 2개 추가
  - `macro_report` → 매크로 리포트, 글로벌 전망 보고서, FOMC 분석
  - `geopolitical` → 지정학 분석, 분쟁·제재 리포트, 시나리오 분석

- [ ] **1-5** Phase 2 ① Fact Ground MCP 호출 목록에 신규 도메인 추가
  - `macro_report` 블록 추가:
    - FRED → 금리·GDP·CPI·스프레드 실측값
    - Tavily → IMF/OECD 컨센서스 페이지 스크래핑
  - `geopolitical` 블록 추가:
    - Tavily → 지정학 뉴스 수집
    - FRED → 원유·에너지 가격 지표

---

## BLOCK 2 — RULES.md 수정 (L2 전체)

> 대상 파일: `/mnt/skills/user/6layer-verification/RULES.md`
> 의존성: BLOCK 0 완료 후 진행 권장 (0-1·0-4 결과에 따라 규칙 세부 조정)

- [ ] **2-1** `### 매크로 리포트 / macro_report 규칙` 섹션 신규 추가
  - 위치: 기존 `### 금융/대체투자 규칙` 다음

- [ ] **2-2** lr_017 금리 전망 규칙 추가
  - 조건: 금리 전망 주장 AND Fed Dot Plot/포워드가이던스 미인용
  - 플래그: 금리 전망 1차 소스 부재
  - 심각도: high
  - FRED 시리즈: `FEDTARMD` 주석 명시

- [ ] **2-3** lr_018 GDP 전망 규칙 추가
  - 조건: GDP 전망 수치 AND IMF·OECD·컨센서스 미비교
  - 플래그: 성장 전망 컨센서스 대비 괴리 여부 미확인
  - 심각도: medium
  - 데이터 소스: FRED(NGDP계열) + Tavily(IMF WEO 페이지) 주석 명시

- [ ] **2-4** lr_019 인플레이션 전망 규칙 추가
  - 조건: 인플레이션 전망 AND 최신 PCE/CPI 실측값 미비교
  - 플래그: 전망이 현재 실측 추세와 일치하는지 확인 불가
  - 심각도: high
  - FRED 시리즈: `PCEPILFE`, `CPIAUCSL` 주석 명시

- [ ] **2-5** lr_020 결론 수치 서술형 은폐 규칙 추가
  - 조건: P1 Claim이 정량 수치 없이 서술형으로만 표현됨
  - 트리거 예시: "방어력이 높다" / "상당한 성장세" / "유동성 충분"
  - 플래그: 결론 근거가 검증 불가능한 서술형으로 표현됨
  - 심각도: high
  - 연동: SKILL.md L1-03과 쌍으로 작동

- [ ] **2-6** lr_007 → lr_007_v2 교체 (MVRV 컨텍스트 세분화)
  - 기존 단순 조건 삭제
  - 신규 3-way 분기 작성:
    - 사이클 경과 > 18개월 → 🔴
    - 사이클 경과 < 6개월 → 🟡
    - 사이클 정보 없음 → 🟡
  - CoinMetrics 시리즈 주석 명시

- [ ] **2-7** RULES.md 상단에 FRED 시리즈 ID 레퍼런스 테이블 추가
  - 각 규칙에서 사용하는 시리즈 ID를 별도 섹션으로 정리
  - 오조회 방지 + 향후 유지보수 용이성 확보

---

## BLOCK 3 — CHECKLISTS.md 수정 (L3 전체)

> 대상 파일: `/mnt/skills/user/6layer-verification/CHECKLISTS.md`
> 의존성: 없음. BLOCK 1·2와 병렬 실행 가능.

### [NORM] 섹션 추가

- [ ] **3-1** `macro_report` NORM 체크리스트 추가
  - nr_macro_001: 데이터 출처 명시 (high)
  - nr_macro_002: 기준 시점 명시 (high)
  - nr_macro_003: 시나리오 가정 근거 명시 (medium)
  - nr_macro_004: 투자 자문 아님 면책 (medium)
  - 스캔 키워드: "출처", "source", "기준일", "가정", "disclaimer"

- [ ] **3-2** `geopolitical_report` NORM 체크리스트 추가
  - nr_geo_001: 정보 출처 명시 (high)
  - nr_geo_002: 분석 시점 명시 (high)
  - nr_geo_003: 불확실성 경고 (high)
  - 스캔 키워드: "출처", "분석일", "불확실", "uncertainty", "caveat"

### [OMISSION] 섹션 추가

- [ ] **3-3** `매크로 리포트 (macro_report)` Omission 섹터 신규 추가
  - om_macro_001: FOMC 경로 언급 (critical)
  - om_macro_002: 실질금리 기준값 (high)
  - om_macro_003: GLI 방향성 (high)
  - om_macro_004: 달러 방향성 DXY (high)
  - om_macro_005: 신용 스프레드 수준 (high)
  - om_macro_006: 시나리오 확률 합계 검증 (medium)
  - om_macro_007: 유효기간 / 업데이트 조건 (low)

- [ ] **3-4** `지정학 분석 (geopolitical)` Omission 섹터 신규 추가
  - om_geo_001: 에너지 경로 리스크 (critical)
  - om_geo_002: 시나리오 확률 배분 근거 (high)
  - om_geo_003: Base/Bull/Bear 전부 포함 (high)
  - om_geo_004: 역사적 유사 사례 (medium)
  - om_geo_005: 타임라인 명시 (medium)
  - om_geo_006: 2차 효과 — 금융시장 연쇄 (high)

- [ ] **3-5** `SaaS/IT` Omission 섹터 신규 추가
  - om_saas_001: ARR/NRR 성장 추이 (critical)
  - om_saas_002: Rule of 40 (high)
  - om_saas_003: 고객 집중도 (high)
  - om_saas_004: 번오프율 Churn (high)
  - om_saas_005: AI 경쟁 위협 (high)

### 기존 섹터 보강

- [ ] **3-6** 크립토 섹터 Omission 3개 항목 추가
  - om_crypto_006: 브릿지/크로스체인 리스크 (high)
  - om_crypto_007: 중앙화 리스크 (high)
  - om_crypto_008: 거버넌스 리스크 (medium)

- [ ] **3-7** 반도체 섹터 Omission 2개 항목 추가
  - om_semi_007: CoWoS/패키징 병목 (high)
  - om_semi_008: 고객사 집중도 (high)

---

## BLOCK 4 — OUTPUT_FORMAT.md 신규 생성 (L4-03)

> 대상: 신규 파일 생성
> 의존성: 없음. 가장 먼저 또는 BLOCK 1·2·3과 병렬로 실행 가능.

- [ ] **4-1** 파일 생성: `OUTPUT_FORMAT.md`
  - 경로: `/mnt/skills/user/6layer-verification/OUTPUT_FORMAT.md`

- [ ] **4-2** `[SUMMARY]` 종합 판정 블록 포맷 작성
  - 전체 등급 (🟢/🟡/🔴/⚫)
  - 최고 리스크 플래그 1개
  - 유효기간
  - 검증 문서명 + 유형

- [ ] **4-3** `[LAYER TABLE]` 6층 판정 테이블 포맷 작성
  - 컬럼: 층 번호 / 층 이름 / 판정 / 핵심 근거 1줄 / 플래그 ID

- [ ] **4-4** `[CLAIM LIST]` Claim별 결과 포맷 작성
  - 컬럼: Claim 텍스트 / 유형 / 근거유형(fact/estimate/opinion) / 판정 / 근거

- [ ] **4-5** `[KC LIST]` Kill Condition 목록 포맷 작성
  - 컬럼: KC 전제 내용 / 현재 상태 / 판정 / MCP 출처

- [ ] **4-6** `[BBJ BREAK]` Break 목록 포맷 작성
  - 컬럼: Break 내용 / 임팩트 / 문서 언급 여부 / Omission 여부

- [ ] **4-7** `[JSON]` verification_store v1.1 스키마 정의
  - 필드: doc_id / doc_type / verified_at / overall_verdict / layers[] / claims[] / flags[]
  - 저장 경로 규칙 명시

- [ ] **4-8** `[DISCLAIMER]` 면책 경고 표준 문구 확정
  - 현재 V-05 규칙의 "면책 경고" 문구를 이 파일로 이관·표준화

- [ ] **4-9** `[EXPERT MODE]` 전문가 모드 출력 포맷 확정
  - 현재 비전문가 모드 변환 규칙과 대응되는 전문가 모드 기준 명시

---

## BLOCK 5 — DB·Notion 설계 (L4-01)

> 의존성: invest-db 접속 가능 상태 확인 후 진행.

- [ ] **5-1** invest-db에 `verification_results` 테이블 생성
  ```sql
  id, document_id, document_type, verified_at,
  overall_verdict, top_flag, validity_until, json_path, created_at
  ```

- [ ] **5-2** invest-db에 `verification_claim_outcomes` 테이블 생성
  ```sql
  id, verification_id(FK), claim_text, claim_type,
  verdict_at_check, outcome_at, outcome_correct,
  failure_reason, rule_triggered, created_at
  ```

- [ ] **5-3** Notion DB(ee345e95)에 추적 필드 6개 추가
  - `verified_at` (Date)
  - `verification_verdict` (Select: 🟢🟡🔴⚫)
  - `top_flag_id` (Text)
  - `outcome_check_due` (Date — verified_at + 90일 자동 계산)
  - `outcome_correct` (Checkbox)
  - `failure_reason` (Select: 수치오류/전제붕괴/생략/이해충돌)

- [ ] **5-4** JSON 저장 경로 규칙 확정
  - 예: `/verification_store/{doc_type}/{YYYYMMDD}_{doc_id}.json`
  - heartbeat.py 또는 수동 저장 방식 결정

---

## BLOCK 6 — 구조 개선 (L4-02·04)

> 의존성: BLOCK 1~4 완료 후 진행. 이전 블록이 안정화된 후 적용.

- [ ] **6-1** SKILL.md Phase 2.5 섹션 — 감사자 역할 전환 선언 문구 추가
  - 위치: Phase 2.5 `커버리지 체크리스트` 직전
  - 문구: `"[역할 전환] 이제 감사자(Auditor)로 전환. Phase 2 결과를 독립 점검."`
  - 효과: 셀프 검증 편향 감소

- [ ] **6-2** 오답노트 프로세스 문서화
  - Notion에 `검증 오답노트` 페이지 생성
  - 구조: 날짜 / 검증 대상 / 틀린 판정 / 실제 결과 / 실패 원인 / 신규 규칙 초안
  - 주기: 월 1회 정기 리뷰 캘린더 등록

- [ ] **6-3** 월 1회 RULES.md 업데이트 루틴 확립
  - 오답노트 → 실패 원인 분류 → 신규 규칙 or 기존 규칙 조건 세분화
  - 업데이트 시 규칙 버전 번호 부여 (lr_007 → lr_007_v2 패턴 유지)

---

## BLOCK 7 — 검증 테스트 (전체 완료 후)

> 전체 블록 완료 후 실제 리포트로 엔진 작동 확인.

- [ ] **7-1** 매크로 리포트 검증 테스트
  - 대상: FOMC 관련 최신 리포트 1개
  - 확인: ⚫가 아닌 실제 판정 출력 여부
  - 확인: lr_017·018·019 규칙 정상 작동 여부

- [ ] **7-2** 지정학 리포트 검증 테스트
  - 대상: 이란·관세·러시아 관련 최신 분석 1개
  - 확인: om_geo_001~006 체크리스트 스캔 작동 여부

- [ ] **7-3** 크립토 리포트 검증 테스트
  - 대상: 최근 BTC 또는 알트코인 분석 1개
  - 확인: lr_007_v2 사이클 분기 정상 작동 여부

- [ ] **7-4** OUTPUT_FORMAT.md 포맷 일관성 확인
  - 동일 문서를 2회 검증 → 출력 포맷 동일한지 확인
  - 포맷 불일치 → OUTPUT_FORMAT.md 보완

- [ ] **7-5** Notion + invest-db 저장 흐름 확인
  - 검증 1회 실행 → DB 레코드 생성 여부 확인
  - Notion 필드 자동 기입 여부 확인

---

## 전체 실행 순서 요약

```
BLOCK 0  사전 점검          → MCP 테스트 4개 (병렬 실행)
   ↓
BLOCK 1  SKILL.md 수정      → 5개 작업 (BLOCK 0 완료 후)
BLOCK 2  RULES.md 수정      → 7개 작업 (BLOCK 0 완료 후, BLOCK 1과 병렬)
BLOCK 3  CHECKLISTS.md 수정 → 7개 작업 (BLOCK 1·2와 병렬 가능)
BLOCK 4  OUTPUT_FORMAT.md   → 9개 작업 (독립 실행, 가장 먼저 해도 됨)
   ↓
BLOCK 5  DB·Notion 설계     → 4개 작업 (BLOCK 1~4 완료 후)
BLOCK 6  구조 개선          → 3개 작업 (BLOCK 5 완료 후)
   ↓
BLOCK 7  검증 테스트        → 5개 작업 (전체 완료 후)
```

---

## 작업 수 집계

| 블록 | 작업 수 | 예상 시간 | 병렬 가능 |
|---|---|---|---|
| BLOCK 0 사전 점검 | 4 | 1시간 | 병렬 |
| BLOCK 1 SKILL.md | 5 | 1시간 | - |
| BLOCK 2 RULES.md | 7 | 2시간 | BLOCK 1과 병렬 |
| BLOCK 3 CHECKLISTS.md | 7 | 3시간 | 전부 병렬 |
| BLOCK 4 OUTPUT_FORMAT.md | 9 | 3시간 | 전부 독립 |
| BLOCK 5 DB·Notion | 4 | 2시간 | - |
| BLOCK 6 구조 개선 | 3 | 1시간 | - |
| BLOCK 7 테스트 | 5 | 2시간 | - |
| **합계** | **44** | **~15시간** | |

---

## 완료 기준

| 기준 | 확인 방법 |
|---|---|
| 엔진 도메인 완전성 | 매크로·지정학 리포트 검증 시 ⚫ 없이 판정 출력 |
| 규칙 작동 | lr_017~020 플래그 정상 발동 |
| 포맷 일관성 | 동일 문서 2회 검증 시 포맷 동일 |
| 추적 루프 | 검증 → DB 저장 → Notion 기록 자동화 |
| 오답노트 | 첫 월간 리뷰 실행 완료 |

---

*본 문서는 6layer-verification-upgrade-checklist.md + 6layer-upgrade-mcp-requirements.md 통합 실행 로드맵입니다.*
