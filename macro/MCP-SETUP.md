# MCP 연결 가이드

## 이 문서의 역할
매크로 시스템에서 사용하는 MCP의 연결, 테스트, 트러블슈팅.
FRED와 Yahoo Finance MCP가 이미 로컬에서 가동 중인 상태를 전제로 한다.

---

## 현재 환경

```
MCP 서버 전체 (claude_desktop_config.json 설정 완료):
├── fred              ✅ 핵심 — 13개 경제 시리즈
├── yahoo-finance     ✅ 핵심 — 6개 시장 티커
├── tavily-mcp        ✅ 활용 — 웹검색 대체 (고정밀 검색)
├── firecrawl         ✅ 활용 — 웹페이지 크롤링 (TGA, FedWatch, CFTC)
├── invest-db         ⏳ Phase 4 — 보고서 결과 DB 저장
├── dart              — 한국 기업 공시 (매크로 보고서에서 미사용)
├── sec-edgar         — 미국 기업 실적 (매크로 보고서에서 미사용)
├── coingecko         — 크립토 (매크로 보고서에서 미사용)
├── defillama         — DeFi (매크로 보고서에서 미사용)
├── coinmetrics       — 온체인 (매크로 보고서에서 미사용)
├── etherscan         — 이더리움 (매크로 보고서에서 미사용)
├── blockchain-com    — BTC 온체인 (매크로 보고서에서 미사용)
├── dune-analytics    — 온체인 쿼리 (매크로 보고서에서 미사용)
├── github            — 코드 (매크로 보고서에서 미사용)
├── apify             — 웹스크래핑 (필요 시 활용 가능)
└── Filesystem        ⚠️ 경고 표시 — 확인 필요

Cowork: Desktop 앱 Cowork 탭에서 동일 config 인식. 별도 재설정 불필요.
```

---

## Step 1: 기존 MCP가 Cowork에서 작동하는지 확인

claude_desktop_config.json에 설정된 MCP는 Chat 모드와 Cowork 모드 모두에서 인식된다.
별도 재설정 불필요. 단, Cowork 탭으로 전환한 상태에서 테스트 필요.

```
테스트 순서:

1. Claude Desktop 앱 실행
2. 상단 모드를 "Cowork"로 전환
3. 작업 폴더: C:\Users\이미영\Downloads\investment-os\macro 지정
4. 다음 명령어로 MCP 연결 테스트:

테스트 1 — FRED:
  "FRED에서 DFII10 최신값을 조회해줘"
  → 성공: 값(예: 1.82) + 날짜(예: 2026-03-05) 반환
  → 실패: Step 3으로

테스트 2 — FRED 다중:
  "FRED에서 WALCL, RRPONTSYD, T10Y2Y 최신값을 한번에 조회해줘"
  → 성공: 3개 시리즈 모두 반환
  → 실패: API 키 또는 rate limit 문제

테스트 3 — Yahoo Finance:
  "Yahoo Finance에서 DXY(DX-Y.NYB), VIX(^VIX), USD/JPY(JPY=X) 현재가를 조회해줘"
  → 성공: 3개 티커 모두 반환
  → 실패: Step 3으로

테스트 4 — Net Liquidity 계산:
  "FRED에서 WALCL과 RRPONTSYD를 조회하고, 
   TGA는 웹검색으로 찾아서, Net Liquidity = WALCL − TGA − RRP를 계산해줘"
  → 성공: 계산값 + 각 구성요소 값 + 기준일 반환

테스트 5 — Notion:
  "Notion DB ee345e95에 테스트 페이지를 만들어줘. 
   제목: MCP 연결 테스트, 내용: 테스트 성공"
  → 성공: 페이지 생성 확인
```

---

## Step 2: 매크로 보고서용 전체 MCP 테스트

Step 1 통과 후, 실제 보고서에서 사용하는 전체 시리즈를 테스트.

```
FRED 일괄 테스트 (13개):
"FRED에서 다음 시리즈의 최신값을 모두 조회해줘:
PCEPILFE, DFII10, BAMLH0A0HYM2, T10Y2Y, WM2NS,
UNRATE, T10YIE, DFF, WALCL, RRPONTSYD, WRESBAL, SOFR"

→ 확인: 각 시리즈별 값 + 관측일
→ 누락 시리즈 기록 → 해당 시리즈는 웹검색 폴백

Yahoo 일괄 테스트 (6개):
"Yahoo Finance에서 다음 티커의 현재가를 조회해줘:
DX-Y.NYB, JPY=X, ^VIX, ^MOVE, CL=F, CNY=X"

→ 확인: 각 티커별 현재가
→ ^MOVE가 안 잡히면 웹검색 폴백 대상
```

---

## Step 3: 트러블슈팅

### MCP 응답 없음

```
확인 1: MCP 서버 실행 중인가
  Windows 터미널:
    tasklist | findstr "node"     (npx 기반이면)
    tasklist | findstr "python"   (Python 기반이면)
    docker ps                     (Docker 기반이면)
  → 프로세스 없으면 재시작

확인 2: claude_desktop_config.json 경로
  위치: %APPDATA%\Claude\claude_desktop_config.json
  → 메모장으로 열어 FRED/Yahoo 항목 존재 확인
  → JSON 구문 오류 확인 (쉼표, 중괄호)

확인 3: Cowork 모드 전환 여부
  → Desktop 앱 상단이 "Cowork" 탭인지 확인
  → "Chat" 탭에서도 MCP는 작동하지만 Cowork 기능(파일 접근 등)은 안 됨

확인 4: 앱 재시작
  → Claude Desktop 완전 종료 후 재실행
  → config.json 변경 시 반드시 재시작 필요
```

### 특정 FRED 시리즈 조회 실패

```
원인 1: 시리즈 코드 오류
  → FRED 웹사이트에서 시리즈 존재 확인
  → 예: BAMLH0A0HYM2 (길고 복잡) 오타 주의

원인 2: API rate limit
  → FRED 무료 키: 분당 120회 제한
  → 13개 시리즈 일괄 조회 시 문제 없음
  → 반복 테스트 시 간격 두기

원인 3: 시리즈 업데이트 지연
  → Core PCE(PCEPILFE): 월 1회 발표, 최신값이 1~2개월 전일 수 있음
  → 정상. 관측일 확인하여 "기준: YYYY-MM" 명시
```

### Yahoo 티커 조회 실패

```
^MOVE 실패 시:
  → ICE 소유 데이터로 Yahoo에서 불안정할 수 있음
  → 폴백: 웹검색 "MOVE index current value"
  → 보고서에 "⚠️ 웹검색 대체" 표시

주말/공휴일:
  → 전 거래일 종가 반환 → 정상
  → "기준: 전 거래일" 명시
```

---

## Step 4: 웹검색 → tavily/firecrawl 전환

기존 "웹검색 폴백" 8개 중 5개를 tavily-mcp + firecrawl로 자동화.

```
tavily-mcp 활용 (고정밀 검색, 웹검색 대체):
├── A2 중국 Credit Impulse
│   쿼리: "China new yuan loans [월] 2026 PBOC"
│   → tavily가 복수 소스 교차 반환 → 일반 웹검색보다 정확
│
├── C5 ISM PMI
│   쿼리: "ISM manufacturing PMI [월] 2026"
│   → 월간 발표 직후 tavily로 수집
│
└── D7 재정적자/GDP
    쿼리: "US federal budget deficit GDP ratio CBO 2026"
    → 반기 데이터, tavily로 CBO 원문 찾기

firecrawl 활용 (웹페이지 직접 크롤링):
├── D4 TGA 잔고
│   URL: https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/
│   → firecrawl로 Treasury Daily Statement 페이지 크롤 → TGA 값 추출
│   → 매주 최신 값 자동 수집 가능
│
├── D10 CME FedWatch
│   URL: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
│   → firecrawl로 FedWatch 페이지 크롤 → 내재 확률 추출
│
└── D9 CFTC JPY 순포지션
    URL: https://www.cftc.gov/dea/futures/deacmesf.htm
    → firecrawl로 COT 보고서 크롤 → JPY 순포지션 추출

여전히 수동 (MCP 불가):
├── D1 SLOOS: Fed 분기 발표, PDF 형식 → 수동 입력
├── D8 텀 프리미엄: NY Fed ACM 모델, 전용 페이지 → firecrawl 시도 가능
└── → 수동 2개로 축소 (기존 8개에서 대폭 개선)
```

---

## 수집 가능 현황 요약 (업데이트)

```
MCP 자동 (19개):
├── fred (13): PCEPILFE, DFII10, BAMLH0A0HYM2, T10Y2Y, WM2NS,
│   UNRATE, T10YIE, DFF, WALCL, RRPONTSYD, WRESBAL, SOFR
├── yahoo-finance (6): DX-Y.NYB, JPY=X, ^VIX, ^MOVE(불안정), CL=F, CNY=X
└── 비율: 19/27

tavily-mcp 자동검색 (3개):
├── A2 중국 Credit, C5 ISM PMI, D7 재정적자
└── 비율: +3 = 22/27

firecrawl 크롤링 (3개):
├── D4 TGA, D9 CFTC JPY, D10 FedWatch
└── 비율: +3 = 25/27

수동 (2개):
├── D1 SLOOS (분기), D8 텀 프리미엄 (월간)
└── 비율: 2/27 = 7% 수동

→ Layer A+B 7개 중 7개 자동 (A2도 tavily로)
→ 전체 자동 수집률: 93% (25/27)
```

---

## Step 5: tavily + firecrawl 테스트

```
테스트 6 — tavily:
  "tavily로 'US ISM manufacturing PMI March 2026' 검색해줘"
  → 성공: PMI 수치 + 출처 + 날짜 반환
  → tavily가 일반 웹검색보다 정확한 소스를 반환

테스트 7 — firecrawl (TGA):
  "firecrawl로 https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/
   페이지를 크롤해서 Treasury General Account 잔고를 추출해줘"
  → 성공: TGA 값 + 날짜 반환
  → 실패: 페이지 구조 변경 → tavily 폴백

테스트 8 — firecrawl (FedWatch):
  "firecrawl로 CME FedWatch 페이지를 크롤해서
   다음 FOMC 금리 내재 확률을 추출해줘"
  → 성공: 동결/인하 확률 반환
  → 실패: 동적 렌더링 문제 → tavily 폴백

테스트 9 — firecrawl (CFTC):
  "firecrawl로 https://www.cftc.gov/dea/futures/deacmesf.htm
   에서 JPY 순포지션을 추출해줘"
  → 성공: 순포지션 값 반환
  → 실패: tavily 폴백
```

---

## Step 6: /macro-weekly 첫 실행

MCP + tavily + firecrawl 테스트 통과 후:

```
Cowork에서:
1. macro\ 폴더를 작업 폴더로 지정
2. 다음 입력:

"PLUGIN-weekly-macro.md의 실행 순서에 따라
이번 주 글로벌 매크로 주간 보고서를 작성해줘.
데이터 수집:
 - fred MCP로 FRED 시리즈 13개
 - yahoo-finance MCP로 시장 티커 6개
 - tavily-mcp로 중국 Credit, ISM PMI, 재정적자
 - firecrawl로 TGA, FedWatch, CFTC JPY
 - 수동 불가 시 웹검색 폴백
보고서는 TEMPLATE-macro-report.md 형식으로
reports/ 폴더에 저장해줘."

3. 실행 결과 확인:
  [ ] reports/[날짜]_macro-weekly.md 생성 확인
  [ ] Layer A+B 7개 값이 MCP/tavily에서 수집됐는지 확인
  [ ] 이벤트 서사가 포함됐는지 확인
  [ ] 레짐 판정이 있는지 확인
  [ ] Notion 아카이브 저장 확인 (Notion MCP 연결 시)
```
