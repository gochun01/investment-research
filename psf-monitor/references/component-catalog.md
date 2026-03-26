# PSF-Monitor Component Catalog

> 자율 보고서 생성에 사용하는 HTML 컴포넌트 카탈로그.
> render_adaptive.py가 이 컴포넌트들을 조합하여 보고서를 생성한다.
> CSS는 `assets/template-base.html`에 정의되어 있다.

---

## 1. topbar — 보고서 분류 바

보고서 상단에 고정. 4종 분류에 따라 색상이 달라진다.

| 분류 | 클래스 | 조건 |
|------|--------|------|
| CRISIS ALERT | `.topbar.red` | regime 🔴 또는 L8 활성 |
| SPECIAL REPORT | `.topbar.blue` | 긴장 존재 또는 시나리오 분기 |
| RESEARCH NOTE | `.topbar.navy` | 기본 (스냅샷) |
| STRATEGY UPDATE | `.topbar.gold` | projection 기반 |

```html
<div class="topbar red">CRISIS ALERT</div>
<div class="topbar blue">SPECIAL REPORT</div>
<div class="topbar navy">RESEARCH NOTE</div>
<div class="topbar gold">STRATEGY UPDATE</div>
```

---

## 2. report-header — 제목 + 날짜 + 뱃지

```html
<div class="report-header">
  <h1>PSF Briefing — 2026-03-25</h1>
  <div class="meta">대립형 · 8개 섹션 · 자율 판단</div>
  <div class="badges">
    <span class="badge regime-yellow">PSF 🟡 경계 (다소 완화)</span>
    <span class="badge regime-yellow">macro 🟡 Transition (3.5/5)</span>
    <span class="badge keyword">이행+이행 = 양쪽 불확실</span>
  </div>
</div>
```

뱃지 종류:
- `.badge.regime-green` — 🟢 정상
- `.badge.regime-yellow` — 🟡 경계
- `.badge.regime-red` — 🔴 위기
- `.badge.keyword` — 정렬 상태, 키워드

---

## 3. exec-box — Core Claim 하이라이트

금색 좌측 보더. 보고서의 핵심 주장을 담는다.

```html
<div class="exec-box">
  <div class="claim">🟡 경계 (다소 완화) — 미국 5일 군사행동 정지 → Brent $106→$103(-$4), BEI 2.63→2.53%(-10bp)</div>
  <div class="sub">P-지정학(정지) → P-자원(Brent↓) → L3(BEI↓) → S1(실질금리 영향 지연)</div>
</div>
```

---

## 4. regime-dashboard — P/S/F 3열 대시보드

판(P), 구조(S), 흐름(F) 각각의 상태를 표시.

```html
<div class="dashboard-grid">
  <!-- P 판 -->
  <div class="dashboard-col">
    <div class="layer-label plate">P 판</div>
    <div class="item">🟡 P1_fiscal — DFF 3.64% 동결</div>
    <div class="item">⚫ P2_trade — 뉴스 부재</div>
    <div class="item">🔴 P3_geopolitics — 5일 정지 ↔ 걸프 공격 경고</div>
    <div class="item">🟡 P4_regulation — SEC 크립토 해석 시행 중</div>
    <div class="item">🟡 P5_resources — Brent $103(↓)</div>
    <div class="verdict">판정: 변동</div>
  </div>

  <!-- S 구조 -->
  <div class="dashboard-col">
    <div class="layer-label structure">S 구조</div>
    <div class="item"><span class="num">S1 실질금리 2.01</span> ↑ <span style="color:var(--text-dim)">긴장</span></div>
    <div class="item"><span class="num">S2 HY OAS 319bp</span> ↓ <span style="color:var(--text-dim)">건전</span></div>
    <div class="item"><span class="num">S3 SOFR-FF -2bp</span> → <span style="color:var(--text-dim)">건전</span></div>
    <div class="item"><span class="num">S4 ISM PMI 49</span> ↓ <span style="color:var(--text-dim)">긴장</span></div>
    <div class="item"><span class="num">S5 T10Y2Y 0.51</span> → <span style="color:var(--text-dim)">건전</span></div>
    <div class="verdict">판정: 건전~긴장</div>
  </div>

  <!-- F 흐름 -->
  <div class="dashboard-col">
    <div class="layer-label flow">F 흐름</div>
    <div class="item">F1 DXY <span style="color:var(--text-dim)">이동</span></div>
    <div class="item">F2 Net Liq <span style="color:var(--text-dim)">정체</span></div>
    <div class="item">F3 EM/DM <span style="color:var(--text-dim)">정체</span></div>
    <div class="item">F4 크립토 <span style="color:var(--text-dim)">횡보</span></div>
    <div class="item">F5 VIX/MOVE <span style="color:var(--text-dim)">경계→정상 접근</span></div>
    <div class="verdict">판정: 정체~이동</div>
  </div>
</div>
```

---

## 5. monitor-table — 데이터 비교 테이블

before/after/delta 형식. 숫자는 DM Mono.

```html
<table class="monitor-table">
  <thead>
    <tr><th>지표</th><th>이전</th><th>현재</th><th>변동</th><th>판정</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>DFII10 실질금리</td>
      <td class="num">1.88%</td>
      <td class="num">2.01%</td>
      <td class="num up">+13bp</td>
      <td>긴장</td>
    </tr>
    <tr>
      <td>HY OAS</td>
      <td class="num">327bp</td>
      <td class="num">319bp</td>
      <td class="num down">-8bp</td>
      <td>건전</td>
    </tr>
    <tr>
      <td>MOVE</td>
      <td class="num">108.84</td>
      <td class="num">98.15</td>
      <td class="num down">-10.69</td>
      <td>정상 복귀</td>
    </tr>
  </tbody>
</table>
```

---

## 6. link-status — Link 활성화 상태 카드

2열 그리드. active=빨강 보더, approaching=노랑 보더.

```html
<div class="link-grid">
  <div class="link-card active">
    <div class="status">L3_energy_inflation</div>
    <div style="color:var(--text-dim);font-size:0.78em;margin-top:2px">active (약화)</div>
    <div style="color:var(--text);font-size:0.78em;margin-top:2px">BEI 2.53%(↓10bp). 여전히 높으나 감속.</div>
  </div>
  <div class="link-card active">
    <div class="status">L5_geopolitics_energy</div>
    <div style="color:var(--text-dim);font-size:0.78em;margin-top:2px">active</div>
    <div style="color:var(--text);font-size:0.78em;margin-top:2px">호르무즈 폐쇄 지속 + 걸프 공격 경고.</div>
  </div>
  <div class="link-card approaching">
    <div class="status">L7_chronic</div>
    <div style="color:var(--text-dim);font-size:0.78em;margin-top:2px">approaching</div>
    <div style="color:var(--text);font-size:0.78em;margin-top:2px">VIX 25.84. 25+ 지속이나 하락 방향.</div>
  </div>
</div>
```

---

## 7. scenario-grid — 시나리오 비교

2~3열. 확률은 DM Mono, 노란색.

```html
<div class="scenario-grid">
  <div class="scenario-card">
    <div class="prob">40%</div>
    <div class="name">Base — 교착 지속</div>
    <div class="desc">호르무즈 부분 개방, 유가 $95~105, 금리 동결 연장. PSF 🟡 유지.</div>
  </div>
  <div class="scenario-card">
    <div class="prob">30%</div>
    <div class="name">Escalation — 걸프 확대</div>
    <div class="desc">이란 걸프 공격 → Brent $130+ → L7→L8 활성 → PSF 🔴 전환.</div>
  </div>
  <div class="scenario-card">
    <div class="prob">30%</div>
    <div class="name">De-escalation — 협상 시작</div>
    <div class="desc">5일 정지→연장→협상. Brent $85. L3/L5 비활성. PSF 🟢 접근.</div>
  </div>
</div>
```

---

## 8. alert-box — 경고 알림

critical=빨강 배경, warning=노랑 배경.

```html
<div class="alert-box">
  <div class="alert-title">CRITICAL — L8 위기 Link 접근</div>
  <div class="alert-body">LQD/SOFR 스프레드 급등. 신용 동결 가능성. 시스템 리스크 단계.</div>
</div>

<div class="alert-box warning">
  <div class="alert-title">WARNING — P↔S 괴리 지속</div>
  <div class="alert-body">P-지정학 🔴 vs S2 건전(319bp). 전쟁 심각도를 신용이 무시하는 구조.</div>
</div>
```

---

## 9. observation-card — 순위별 관측 카드

severity에 따라 좌측 보더 색상 변경.

```html
<div class="card critical">
  <span class="rank">#4</span>
  <span class="signal">이란 걸프 에너지 인프라 공격 경고 (사우디/UAE 대상)</span>
  <div class="detail">이란 IRGC의 사우디/UAE 에너지 시설 공격 시사. 걸프국 군사대응권 유보 경고.</div>
  <div class="detail" style="color:var(--purple)">②에너지: 축 자체는 건재하나 판(P)이 위험. ⑧지정학: 연합 재편 가속.</div>
</div>

<div class="card high">
  <span class="rank">#1</span>
  <span class="signal">미국 5일 군사행동 정지 → Brent $106→$103(-$4)</span>
  <div class="detail">P-지정학(정지) → P-자원(Brent↓) → L3(BEI↓) → S1(실질금리 영향 지연)</div>
</div>

<div class="card medium">
  <span class="rank">#3</span>
  <span class="signal">MOVE 108.84→98.15(-10.69), 100 하회</span>
  <div class="detail">F5(변동성↓) → S2(스프레드 안정 지지) → F2(유동성 긴장 완화)</div>
</div>
```

---

## 10. axis-status — 축 상태 요약 카드

auto-fill 그리드. 상태에 따라 텍스트 색상 변경.

```html
<div class="axis-grid">
  <div class="axis-card">
    <div class="axis-name">①AI</div>
    <div class="axis-status" style="color:var(--green)">건재</div>
  </div>
  <div class="axis-card">
    <div class="axis-name">②에너지</div>
    <div class="axis-status" style="color:var(--green)">건재 (판 차단)</div>
  </div>
  <div class="axis-card">
    <div class="axis-name">③고령화</div>
    <div class="axis-status" style="color:var(--green)">건재</div>
  </div>
  <div class="axis-card">
    <div class="axis-name">④블록체인</div>
    <div class="axis-status" style="color:var(--green)">건재</div>
  </div>
  <div class="axis-card">
    <div class="axis-name">⑨재정</div>
    <div class="axis-status" style="color:var(--yellow)">가속</div>
  </div>
  <div class="axis-card">
    <div class="axis-name">⑧미중</div>
    <div class="axis-status" style="color:var(--red)">격화</div>
  </div>
</div>
```

색상 규칙:
- `건재` → `var(--green)`
- `감속`, `가속` → `var(--yellow)`
- `훼손`, `격화` → `var(--red)`

---

## 11. open-questions — 미해소 질문 목록

```html
<ul class="question-list">
  <li>
    <span class="deadline">2026-03-28</span>
    5일 군사 정지 만료(~3/27) 후 미국 행동은?
  </li>
  <li>
    <span class="deadline">2026-03-31</span>
    이란 걸프 에너지 인프라 공격이 실행되는가?
  </li>
  <li style="border-color:var(--purple)">
    <span style="color:var(--purple)">[미분류]</span>
    Gold $4,414 — 지정학 피크에서 하락 후 반등. 지정학 헤지 vs 실질금리 상승 상충.
  </li>
</ul>
```

---

## 12. divergence-card — 괴리 하이라이트

```html
<div class="divergence">
  <div class="type">P↔S</div>
  <div class="desc">P-지정학 🔴(전쟁+걸프 공격 경고) vs S2 건전(319bp 개선). 전쟁 심각도를 신용이 무시.</div>
</div>

<div class="divergence">
  <div class="type">F5 내부</div>
  <div class="desc">MOVE 98(정상) vs VIX 25.8(경계). 채권은 안심, 주식은 불안. 괴리 축소 중.</div>
</div>
```

---

## 13. footer + disclaimer

```html
<div class="footer">
  MCP 17건 · 비율 89% · 상세 → state.json
  <div class="disclaimer">이 보고서는 관측 결과입니다. 투자 판단이나 행동 권고가 아닙니다. 모든 수치는 수집 시점 기준이며 실시간이 아닙니다.</div>
</div>
```

---

## 조합 규칙

```
보고서 유형에 따라 컴포넌트를 조합한다:

A 대립형:  topbar + header + exec + dashboard + clash(divergence) + observations + links + axis + questions
C 스냅샷형: topbar + header + exec + dashboard + observations + links + axis + table
D 분기형:  topbar + header + exec + dashboard + observations + scenarios + links + axis + questions
E 복합형:  topbar + header + exec + dashboard + clash + observations + scenarios + links + axis + questions

Gravity(중력) 규칙:
  critical → section-large + card.critical
  high     → section-large + card.high
  medium   → section-small + monitor-table
  low      → 생략 또는 footer 언급

첫 화면 규칙:
  topbar + header + exec-box는 반드시 첫 스크롤 안에 보여야 한다.
```
