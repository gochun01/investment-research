# 스캔 소스 + 쿼리 가이드

> 4축별 MCP 도구 + 쿼리 패턴. 쿼리는 고정이 아니라 가이드.
> 날짜와 상황에 맞게 LLM이 조정할 수 있다.
>
> **v1.1 (2026-03-26)**: 첫 실행 피드백 반영.
> A축 한국어를 Tavily→WebSearch로 변경. A축 영문에 소스 한정 추가.
> 한국어는 WebSearch 전용. Tavily는 영문 전용.

---

## A축: 시장 반응 (이미 움직인 것)

| # | 도구 | 쿼리 패턴 | 목적 |
|---|------|-----------|------|
| A1 | Tavily | `"Reuters OR Bloomberg OR CNBC market stocks oil gold today {date}"` | 영문 시장 반응 (소스 한정) |
| A2 | WebSearch | `"증시 급등 급락 유가 환율 금 오늘 {date}"` | 한국어 시장 반응 |

**v1.0→v1.1 변경**: A1에 소스명(Reuters/Bloomberg/CNBC)을 포함하여 인도/베트남 주식 테이블 노이즈 방지. A2를 Tavily→WebSearch로 변경 (한국어 검색 품질 개선).

**조정 가이드**: 특정 자산이 급변했으면 해당 자산 키워드 추가. 예: `"oil surge"`, `"금 급등"`.

---

## B축: 정책 변화 (곧 움직일 것)

| # | 도구 | 쿼리 패턴 | 목적 |
|---|------|-----------|------|
| B1 | Tavily | `"central bank regulation sanctions tariff policy announcement {date}"` | 영문 정책 |
| B2 | WebSearch | `"금리 결정 규제 관세 제재 정부 발표 오늘"` | 한국어 정책 |

**조정 가이드**: FOMC/ECB/BOJ 등 회의 주간이면 해당 기관 키워드 강화.

---

## C축: 공급/구조 충격 (느리게 번질 것)

| # | 도구 | 쿼리 패턴 | 목적 |
|---|------|-----------|------|
| C1 | Tavily | `"supply chain shortage disruption force majeure infrastructure damage {date}"` | 영문 공급 |
| C2 | WebSearch | `"공급 차질 물량 부족 가동 중단 수급 불안 불가항력 오늘"` | 한국어 공급 |

**조정 가이드**: 특정 밸류체인 이슈(반도체, 에너지, 식량)가 있으면 해당 키워드 추가.

---

## D축: 매몰 이슈 + backlog (묻힌 것)

| # | 도구 | 쿼리 패턴 | 목적 |
|---|------|-----------|------|
| D1 | WebSearch | `"{backlog 3회+ 이슈 title}"` | backlog 재검증 (최대 2건) |
| D2 | WebSearch | `"{외부 시드 키워드}"` | heartbeat KC / GHS buried 시드 |

**조정 가이드**:
- backlog에 3회+ 반복 이슈가 없으면 D1 건너뜀.
- 외부 시드가 없으면 대체 쿼리: `"AI investment OR crypto regulation OR earnings surprise today"` (비위기 축)

---

## 외부 시드 소스

| 시드 | 위치 | 사용 방법 |
|------|------|-----------|
| heartbeat KC 알림 | `../heartbeat/data/latest.json` | 발동 KC의 지표명을 D축 키워드로 |
| macro 레짐 | `../macro/` | 레짐 전환 시 해당 레짐 키워드를 B축에 추가 |
| GHS buried_issues | GHS state.json | buried_issues 제목을 D축 검색 쿼리로 |

**시드가 없으면 독립 스캔.** 시드는 선택적 보강이지 필수가 아니다.

---

## 실행 최적화

### 병렬화 (v1.1 추가)

```
Phase S1 MCP 호출을 2단계로 분리:

단계 1 (병렬): A1, A2, B1, B2, C1, C2 — 동시 실행 (6회)
단계 2 (직렬): D1, D2 — backlog 의존이라 Phase S0 완료 후 실행 (2~3회)

효과: 직렬 8회 → 병렬 6회 + 직렬 2회 = 체감 3~4분 → 1~2분
```

### MCP 호출 총량

```
A축: Tavily 1회 + WebSearch 1회
B축: Tavily 1회 + WebSearch 1회
C축: Tavily 1회 + WebSearch 1회
D축: WebSearch 2~3회
보정: WebSearch 0~2회 (사각지대 보충)
────────────────────────
합계: 8~11회 (보정 포함)
병렬 실행 시 체감: 2단계 (1~2분 + 30초)

패스스루 포함 시 총 파이프라인:
  scanner: 8~11회
  rm (prefetch 활용): 10~17회 (기존 15~25회에서 5~8회 절약)
  합계: 18~28회 (기존 23~36회 대비 -5~8회)
```

---

## 패스스루 데이터 구성 가이드 (v1.1 추가)

```
scanner Phase S6 handoff 시, scanner_prefetch에 포함할 데이터:

1. headlines: 해당 클러스터 이슈의 원본 헤드라인 + 1줄 요약
   - A/B/C/D 축 태그 포함
   - rm이 BATCH 1 서사 기반으로 사용

2. price_snapshot: scanner가 확인한 자산 가격
   - A축 수집 시 이미 확인된 것 (S&P, Brent, KRW 등)
   - rm이 동일 자산 재수집 생략

3. policy_signals: B축에서 수집한 정책 발표
   - rm이 BATCH 1 정책 기반으로 사용

4. narrative_snippets: A/B/C축 주요 매체 프레임
   - source + frame 1줄씩
   - rm이 BATCH 2 심화의 출발점으로 사용

포함하지 않는 것:
  전문가 발언 → scanner가 수집하지 않음. rm BATCH 2의 일.
  포지셔닝 데이터 → scanner가 수집하지 않음. rm BATCH 2의 일.
  → 이 2개 계층은 rm만 할 수 있는 고유 영역. 패스스루 대상 아님.
```

---

## 검색 품질 팁

```
1. time_range: "day" 사용. "week"은 노이즈 폭증.
2. search_depth: "advanced" 사용 (Tavily). "basic"은 피상적.
3. max_results: 5~8 per query. 10 이상은 중복 증가.
4. 한국어 검색은 WebSearch가 Tavily보다 품질 좋음. (v1.1 확인)
5. 영문 검색은 Tavily가 WebSearch보다 구조화 잘 됨.
6. A축 영문에 소스명(Reuters/Bloomberg/CNBC) 포함하면 노이즈 감소. (v1.1 확인)
7. include_domains 파라미터 활용 가능 (Tavily): ["reuters.com", "bloomberg.com"]
```
