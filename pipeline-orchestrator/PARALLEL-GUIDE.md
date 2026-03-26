# 병렬화 가이드 — 각 시스템 내부 MCP 병렬 규칙

> 시스템 간 병렬은 Agent tool이 처리한다.
> 이 문서는 각 시스템 "내부"에서의 MCP 병렬화 규칙이다.

---

## scanner 내부 병렬

```
Phase S1 (4축 스캔):
  병렬 그룹 1 (동시 실행):
    - A축 영문: Tavily (Reuters/Bloomberg/CNBC)
    - A축 한국어: WebSearch (한국 시장 뉴스)
    - B축 영문: Tavily (정책/규제)
    - B축 한국어: WebSearch (한국 정책)
    - C축: Tavily (공급/구조 충격)
    - D축: WebSearch (매몰 이슈)
  → 6개 동시. 결과 취합 후 Phase S2로.

  직렬 (그룹 1 완료 후):
    - D축 backlog 재검증: 1~2회
    - 보충 스캔 (Q1~Q4 보정): 0~2회
```

## macro 내부 병렬

```
46개 지표를 MCP별로 그룹화:

  병렬 그룹 1 (FRED 지표 — 동시 실행):
    A1(FFR), A2(UST10Y), A3(UST2Y), A4(TED), A5(BEI5Y),
    B1(DXY), C1(Brent), C2(Gold), C7(CRB),
    D5(MOVE), D6(VIX), D7(CDX-IG), D8(CDX-HY)
    → 13개 fred_get_latest 동시

  병렬 그룹 2 (Yahoo Finance — 동시 실행):
    B2(EURUSD), B3(USDJPY), B4(USDKRW), B5(USDCNY),
    C3(S&P500), C4(KOSPI), C5(CSI300), C6(DAX),
    D1(SPY-flow proxy), D2(IWM), D3(EEM), D4(HYG),
    D9(TIPS-ETF), D10(BTC)
    → 14개 get_current_stock_price 동시

  직렬 (보조 지표):
    AUX 시리즈: 개별 확인 필요한 것만 직렬

  총 MCP: ~27~35회. 병렬 시 체감 ~15회.
```

## rm 내부 병렬

```
Phase 3 (반응 수집):

  BATCH 1 (동시 — scanner_prefetch 보충):
    - 가격: Yahoo Finance 3~6개 동시
    - 서사 1차: Tavily 2~3개 동시
    - 정책: WebSearch 1~2개 동시
    → 6~11개 동시

  BATCH 2 (BATCH 1 완료 후, 동시):
    - 서사 심화: Tavily 2~3개 동시
    - 전문가 타겟 검색: WebSearch 3~4개 동시
    - 포지셔닝: Yahoo Finance 1~2개 동시
    → 6~9개 동시

  BATCH 3 (직렬):
    - 양면 체크: 1~2회
    - 침묵 확인: 1~2회

  총 MCP: 18~25회. 병렬 시 체감 ~10회.
```

## core-extractor 내부 병렬

```
  병렬 그룹 1 (이슈별 3문 테스트):
    - D-1 (어제와 다른가): WebSearch 1회
    - D-2 (내일을 바꾸는가): 추론 (MCP 불필요)
    - D-3 (구조가 움직이는가): 추론 (MCP 불필요)
    → 1회

  제외 검색: WebSearch 2~3회 (묻힌 것)
  느린 변화: WebSearch/FRED 2~3회 (3개월 추세)

  총 MCP: 5~8회. 대부분 직렬.
```

## PSF 내부 병렬

```
  macro/indicators/latest.json 읽기 (파일 Read, MCP 아님)
  P층 정성 탐색: Tavily 2~3회 (동시 가능)
  매핑: 연산 (MCP 불필요)

  총 MCP: 3~5회.
```

## stereo 내부 병렬

```
  Phase 0 Gate: 파일 Read (MCP 아님)
  Phase 1 (수집):
    - 기사 전문: Firecrawl/Tavily 1~2회
    - 관련 기사: Tavily 2~3회
    - 가격 데이터: Yahoo Finance 2~3회
    - 매크로: FRED 2~3회
    → 7~11개 동시 가능

  총 MCP: 5~10회. 병렬 시 체감 ~4회.
```

---

## 전체 파이프라인 체감 MCP

```
                    실제 호출    병렬 후 체감
Phase 1:
  scanner            8~11         ~6
  macro             27~35        ~15
  (Phase 1 동시)                  max(6,15) = ~15

Phase 2:
  rm                18~25        ~10
  core-extractor     5~8         ~6
  PSF                3~5         ~3
  (Phase 2 동시)                  max(10,6,3) = ~10

Phase 3:
  stereo             5~10        ~4

총계:              66~94         ~29 체감
```
