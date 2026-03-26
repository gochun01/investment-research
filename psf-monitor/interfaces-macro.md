# macro ↔ psf-monitor 인터페이스 명세

> **목적**: 독립된 두 시스템(macro, psf-monitor)의 연결점을 정의한다.
> **원칙**: 합치지 않는다. 각자 전문성을 유지하되, 접점을 명확히 한다.

---

## 두 시스템의 역할 구분

```
macro = "돈이 어디로 가는가" (유동성 전문가)
  8축으로 유동성의 양·가격·방향·장애물을 읽는다.
  46개 지표를 수집하는 유일한 수집자.
  레짐 판정: "위험자산에 돈이 가는 환경인가"

psf-monitor = "세상이 어디로 가는가" (관측+메가트렌드)
  3층(판-구조-흐름)으로 충격의 전파를 추적한다.
  축(9대 메가트렌드)의 방향과 거리를 측정한다.
  국면 판정: "시스템이 스트레스 상태인가"

둘은 같은 데이터의 다른 단면을 본다.
macro가 "물의 양과 방향"을 보면,
psf-monitor는 "그 물이 어떤 건물을 통과하며 어떤 방향으로 흘러가는가"를 본다.
```

---

## 3단 매핑: macro 8축 ↔ PSF P/S/F ↔ axis 9대

```
macro 축              PSF Property          axis 메가트렌드
──────────────────────────────────────────────────────────────
축1 유동성 양          F2 (Net Liq)          ⑨ 재정지배 (부채→유동성)
  B4 Net Liq           F2 대표
  D3 RRP               F2 구성요소
  D4 TGA               F2 구성요소
  D5 WALCL             F2 구성요소

축2 유동성 가격        S1 (실질금리)         ⑨ 재정지배 (금융억압)
  B1 DFII10            S1 대표
  C3 T10Y2Y            S5 대표
  C10 DFF              P-재정

축3 달러/외환          F1 (DXY)              ⑧ 미중 (달러 패권)
  B2 DXY               F1 대표               ④ 블록체인 (달러→스테이블 수요)
  B3 USD/JPY           F1 보조
  C9 USD/CNY           F3 보조

축4 경기 사이클        S4 (PMI)              ③ 고령화 (노동 구조)
  A1 Core PCE          P-재정 키스톤         ⑨ 재정지배 (인플레→억압)
  C5 ISM PMI           S4 대표
  C6 실업률            S4 교차               ③ 고령화 (노동력 감소)

축5 신용/금융안정      S2 (스프레드)          (직접 대응 없음)
  B5 HY OAS            S2 대표                — Link L7/L8의 입력
  D6 SOFR              S3 대표
  D2 지급준비금         S3 보조

축6 리스크 환경        F5 (VIX)              (직접 대응 없음)
  C1 VIX               F5 대표                — Link L7의 입력
  C2 MOVE              F5 보조

축7 지정학/에너지      P-지정학, P-자원       ② 에너지전환, ⑧ 미중
  C7 Brent             P-자원 대표            ② 에너지 (판 조건)
  C8 BEI               S1 교차               ⑨ 재정지배 (에너지→인플레)

축8 자본흐름           P-재정                 ⑨ 재정지배
  A2 중국 Credit       P-재정 보조            ⑧ 미중 (중국 정책)
  D7 재정적자/GDP       P-재정                 ⑨ 재정지배 (부채 경로)
  D8 텀프리미엄         S5 보조                ⑨ 재정지배 (채권시장)
```

### macro가 안 보는 것 (psf-monitor가 보완)

```
① AI/컴퓨트       → macro에 직접 지표 없음. P-기술은 Tavily 정성 수집.
④ 블록체인        → macro에 보조(F4 스테이블)만. DeFiLlama/CoinMetrics는 psf-monitor가 동원.
② 에너지전환 세부  → macro는 Brent(가격)만 봄. 재생에너지 설치량, 그리드 등은 미추적.
③ 고령화 세부     → macro는 실업률만. 인구 구조, 연금, 의료비는 미추적.
⑤⑦ 축 후보       → macro 관측 범위 밖. psf-monitor 분기 점검.
```

### psf-monitor가 안 보는 것 (macro가 보완)

```
엔캐리(USD/JPY)    → macro 축3 B3. psf-monitor에 없음. Override 위험.
중국 Credit        → macro 축8 A2. psf-monitor에 미반영.
은행 지급준비금     → macro D2. 금융 시스템 내부 건강.
SLOOS(대출 태도)   → macro D1. 신용 공급 의향.
글로벌 M2          → macro C4. 글로벌 유동성 총량.
```

---

## 레짐 판정 정합

```
macro 레짐:
  기준: Layer B 5개 위험자산 방향 수
  🟢 팽창기: 4~5/5
  🟡 Transition: 2~3/5
  🔴 수축기: 0~1/5
  질문: "돈이 위험자산 방향으로 가고 있는가"

PSF 국면:
  기준: Link L7/L8 활성 여부
  🟢 정상: 모든 Link 비활성
  🟡 경계: L7 활성 또는 Divergence
  🔴 위기: L8 활성
  질문: "시스템이 스트레스 상태인가"

이 둘은 다른 것을 측정한다. 일치할 필요 없다.
불일치 자체가 신호다:

┌──────────────────────────────────────────┐
│           PSF 국면                        │
│         🟢      🟡       🔴              │
│ macro ──────────────────────────         │
│ 🟢    정상     주의      역설            │
│ 🟡    이행     이행      악화            │
│ 🔴    회복     악화      위기            │
└──────────────────────────────────────────┘

주목할 조합:
  macro 🟢 + PSF 🟡 = 돈은 흐르는데 시스템 긴장.
    → "잔치 중에 균열" — 다음 변곡점 근접 가능.

  macro 🟡 + PSF 🟢 = 돈이 망설이는데 시스템은 안정.
    → "대기 중" — 촉매 하나로 방향 결정.

  macro 🟢 + PSF 🔴 = 돈이 흐르는데 시스템 위기.
    → 역설. 극히 드묾. 발생 시 즉시 재검증 (데이터 오류 가능).

현재 (2026-03-23):
  macro: 🟡 Transition (3.5/5)
  PSF:   🟡 경계 (L7 접근, Divergence 4건)
  → 이행+이행 = 양쪽 모두 불확실. 방향 미결정.
```

---

## 데이터 흐름 인터페이스

```
macro가 쓰는 것:
  indicators/latest.json  ← 46개 지표 + 레짐 + L7/L8

psf-monitor가 읽는 것:
  indicators/latest.json  ← 동일 파일

연결 규칙:
  1. macro가 latest.json을 갱신하면 psf-monitor는 다음 실행에서 읽는다.
  2. psf-monitor는 latest.json을 직접 수집하지 않는다.
     단, stale/expired 시 macro의 수집 절차(PLUGIN-weekly-macro.md)를 대행하여
     latest.json을 갱신할 수 있다. 이때도 macro의 규칙을 그대로 따른다.
  3. psf-monitor가 추가 MCP로 발견한 것(DeFiLlama, CoinMetrics 등)은
     psf-monitor/state.json에만 저장한다.
  4. macro의 레짐 판정과 PSF의 국면 판정이 불일치하면
     psf-monitor 보고서에 불일치 사실과 조합을 명시한다.

신선도:
  latest.json의 "date" 필드로 판단.
  fresh(~3일): 그대로 사용.
  stale(3~7일) / expired(7일+): psf-monitor가 macro 수집 절차를 자동 대행.
  대행 실패 시: stale 데이터 사용 + "[macro 자동갱신 실패]" 태그.
```

---

## psf-monitor 보고서에서의 macro 참조

```
핵심 3줄 아래에 macro 레짐 상태를 1줄로 추가:

  macro 레짐: [🟢/🟡/🔴] [점수] | PSF 국면: [🟢/🟡/🔴] | 정합: [정상/주의/역설/...]

상세에서:
  macro 지표를 인용할 때 "macro:B1 DFII10 1.88%" 형식으로 출처 명시.
  psf-monitor 자체 수집 데이터는 "psf:DeFiLlama TVL $93B" 형식.
```

---

## 갱신 규칙

```
이 인터페이스 문서를 갱신하는 경우:
  1. macro의 8축 또는 지표 구성이 변경될 때
  2. axis.md의 축 분류가 변경될 때 (분기 Q Loop)
  3. PSF ontology의 Property/Link가 변경될 때
  4. 새 MCP 소스가 추가될 때 (매핑 갱신)

갱신 주체: 변경을 일으킨 쪽이 이 문서도 갱신.
```

---

> **이 문서의 사본**: macro/CLAUDE.md에서 참조. psf-monitor/에 원본 보관.
