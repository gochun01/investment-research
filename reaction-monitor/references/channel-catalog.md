# 반응 채널 카탈로그

> 채널 선정 시 추론을 보조하는 참고 자료. 의무 목록이 아니다.

## 도구 폴백 경로

**MCP 도구 실패 시 아래 경로로 대체한다. 수집을 중단하지 않는다.**

| 1차 도구 | 실패 시 | 폴백 2차 | 행동 |
|----------|--------|---------|------|
| Yahoo Finance | 연결 실패 | `WebSearch "[티커] stock price today"` | 가격을 텍스트로 수집. "WebSearch 폴백" 표기 |
| FRED | 연결 실패 | `WebSearch "[지표명] latest value site:fred.stlouisfed.org"` | 수치를 텍스트로 수집 |
| CoinGecko | 연결 실패 | `WebSearch "bitcoin price today coingecko"` | 가격 텍스트로 수집 |
| DeFiLlama | 연결 실패 | `WebSearch "DeFi TVL today defillama"` | TVL 텍스트로 수집 |
| CoinMetrics | 연결 실패 | `WebSearch "[metric] bitcoin coinmetrics"` | 지표 텍스트로 수집 |
| Firecrawl | 연결 실패 | `WebSearch` (동일 쿼리) | 검색 결과로 대체 |
| Tavily | 연결 실패 | `WebSearch` (동일 쿼리) | 검색 결과로 대체 |
| DART | 연결 실패 | `WebSearch "[기업명] 공시 DART"` | 공시 텍스트로 수집 |
| SEC-EDGAR | 연결 실패 | `WebSearch "[company] SEC filing"` | 공시 텍스트로 수집 |
| 모든 MCP | 전체 장애 | WebSearch 전면 전환 | "⚠ MCP 전체 장애. WebSearch 폴백" 기록 |

수집 실패 시 행동: "미확인 — [도구명] 연결 실패. [폴백 결과 또는 수집 불가]" 표기하고 진행.
수집 중단은 Red Zone — 데이터 1건 못 가져왔다고 전체 수집을 멈추지 않는다.

---

## ① 가격 — 영역별 빈출 자산

| 영역 | 1차 | 2차 (인과 경로) | 대조 |
|------|-----|----------------|------|
| 지정학(중동) | WTI, Brent, 방산ETF | 금, 미국채10Y, 항공주 | VIX ↔ 주가지수 |
| 지정학(미-중) | CSI300, USD/CNY, 반도체ETF | 희토류, EM ETF, KRW | 미국 국내주 |
| 통화정책 | 미국채2Y/10Y, 달러인덱스 | 금, 리츠, 성장주 | 은행주 |
| 통상정책 | 대상국 지수, 관련 환율 | 원자재, 운송주 | 내수주 |
| 산업규제(크립토) | BTC, ETH, 규제 대상 토큰 | COIN, 스테이블코인 | DeFi TVL |
| 기업(실적) | 해당 종목 | 피어 종목, 섹터ETF | 시장 전체 |

도구: Yahoo Finance, FRED, CoinGecko, DeFiLlama, CoinMetrics

빈출 FRED 시리즈: FEDFUNDS, DGS10, DGS2, DTWEXBGS, DCOILWTICO, CPIAUCSL, PCEPILFE, BAMLH0A0HYM2, VIXCLS

## ② 서사 — 영역별 빈출 매체

| 영역 | 프레임 설정 | 깊이 분석 | 반대쪽 후보 | 국내 |
|------|-----------|----------|------------|------|
| 지정학(중동) | AP, Reuters | FP, CSIS, CFR | Al Jazeera, Al Arabiya | 연합, 한경 |
| 지정학(미-중) | Reuters, Bloomberg | CFR, Brookings | SCMP, Global Times | 한경 |
| 통화정책 | Reuters, Bloomberg | WSJ, FT | — | 한경, 매경 |
| 통상정책 | Reuters, FT | PIIE, Peterson | 대상국 매체 | 한경 |
| 산업규제(크립토) | CoinDesk, The Block | Messari | SEC 공식 | — |
| 기업 | Bloomberg, Reuters | 증권사 리포트 | — | 한경, 매경 |

도구: WebSearch, Firecrawl (정밀), Tavily research (심층)

## ③ 전문가 — 영역별 빈출 유형

| 영역 | 전문가 유형 |
|------|-----------|
| 지정학 | 외교안보 전문가, 전직 관료, 군사 분석가 |
| 통화정책 | 연준 인사, 채권 전략가, 이코노미스트 |
| 통상정책 | 통상 전문가, 전직 USTR |
| 산업규제 | 업계 CEO, 규제 전문 변호사 |
| 크립토 | 온체인 분석가, 거래소 CEO |

## ④ 정책 — 활성 조건: 이해관계자에 공공기관 포함 시

## ⑤ 포지셔닝 — 활성 조건: 시간 성격 전개형 이상

| 유형 | 데이터 | 도구 |
|------|--------|------|
| 자금 흐름 | ETF 유출입, 외국인 순매수 | WebSearch |
| 헤지 | 풋/콜비율, VIX, 스큐 | Yahoo Finance, FRED |
| 크립토 | 거래소 유출입, 스테이블코인 | CoinGecko, DeFiLlama |
| 신용 | HY OAS, CDS | FRED (BAMLH0A0HYM2) |
