# 컴포넌트 카탈로그 — Reaction Monitor Adaptive Report

> 데이터에 맞는 컴포넌트를 선택한다. "이 컴포넌트를 써야 한다"가 아니라 "이 데이터에 이 컴포넌트가 맞다"로 판단.
> 카탈로그에 없는 컴포넌트도 CSS 변수 기반으로 새로 만들 수 있다.

---

## 1. exec-box — Core Claim 강조

**용도**: 보고서 첫 화면. Core Claim 1문장 + 판정 배지.
**언제**: 항상 (불변 규칙 — 첫 화면에 Core Claim).

```html
<div class="exec-box">
  <div class="claim">천궁-II 실전 입증이 K-방산 전체 밸류에이션을 재설정했다</div>
  <div class="verdict">
    <span class="badge badge-green">수렴</span>
    <span class="badge badge-yellow">비례</span>
    <span class="badge badge-blue">미해소 4건</span>
  </div>
</div>
```

---

## 2. monitor-table — 수치 비교 테이블

**용도**: before/after, 변동률, threshold 등 수치 데이터.
**언제**: price 반응, positioning 수치, 정책 계약 금액 등.

```html
<table>
  <tr>
    <th>자산</th><th>이전</th><th>이후</th>
    <th>변동</th><th>속도</th><th>핵심</th>
  </tr>
  <tr>
    <td><strong>LIG넥스원 079550</strong></td>
    <td class="num">509,000원</td>
    <td class="num">641,000원</td>
    <td class="pos num">+25.9%</td>
    <td>즉시</td>
    <td>5거래일 78% 폭등 후 조정</td>
  </tr>
</table>
```

**변형**: 컬럼을 데이터에 맞게 자유롭게 변경. 불필요한 컬럼 생략.

---

## 3. channel-card — 계층별 채널 카드

**용도**: 채널 선정 요약. 계층 태그 + 채널명 + 선정 이유.
**언제**: 채널 정보가 보고서 맥락에 필요할 때.

```html
<div class="card">
  <span class="layer-tag lt-price">가격</span>
  <span class="layer-tag lt-narrative">서사</span>
  <span class="layer-tag lt-expert">전문가</span>
  <strong>12채널 수집</strong>
  <p style="font-size:.82rem;color:var(--muted);margin-top:.5rem;">
    가격 3 | 서사 7 | 전문가 6 | 정책 3 | 포지셔닝 3
  </p>
</div>
```

**참고**: 무게 중심이 채널에 없으면 이 컴포넌트를 작게 쓰거나 생략.

---

## 4. direction-grid — 방향 일치도 시각화

**용도**: 5계층의 방향(↑/↓/→/↑↓)을 한눈에.
**언제**: Tension이 존재하거나, 방향 패턴이 보고서 핵심일 때.

```html
<div class="direction-grid">
  <div class="direction-cell">
    <span class="direction-label">가격</span>
    <span class="direction-value" style="color:var(--converge)">↑</span>
  </div>
  <div class="direction-cell">
    <span class="direction-label">서사</span>
    <span class="direction-value" style="color:var(--converge)">↑</span>
  </div>
  <div class="direction-cell">
    <span class="direction-label">전문가</span>
    <span class="direction-value" style="color:var(--converge)">↑</span>
  </div>
  <div class="direction-cell">
    <span class="direction-label">정책</span>
    <span class="direction-value" style="color:var(--converge)">↑</span>
  </div>
  <div class="direction-cell">
    <span class="direction-label">포지셔닝</span>
    <span class="direction-value" style="color:var(--diverge)">↑↓</span>
  </div>
</div>
```

---

## 5. clash-grid — 대립 구조 시각화

**용도**: 두 힘의 충돌을 양쪽에 배치.
**언제**: Tension이 명확할 때. 유형 A(대립형) 보고서의 핵심 컴포넌트.

```html
<div class="clash-grid">
  <div class="clash-side bull">
    <h4>🟢 실전 입증 (구조적 호재)</h4>
    <ul style="font-size:.82rem;">
      <li>96% 요격률 — 패트리어트 대비 1/3 가격</li>
      <li>사우디 $3.2B + 이라크 $2.8B 기계약</li>
      <li>GCC 신규 문의 개시</li>
    </ul>
  </div>
  <div class="clash-side bear">
    <h4>🔴 밸류에이션 과열 (단기 리스크)</h4>
    <ul style="font-size:.82rem;">
      <li>LIG넥스원 PSR 35배 (록히드의 3배)</li>
      <li>고점 대비 -23% 조정 진행</li>
      <li>"뉴스에 팔기" 패턴</li>
    </ul>
  </div>
</div>
```

---

## 6. scenario-grid — 시나리오 분기 카드

**용도**: 미래 시나리오별 확률 + 핵심 지표 + 경로.
**언제**: Timeline이 "미래 분기"에 집중일 때. 유형 D(분기형).

```html
<div class="scenario-grid">
  <div class="scenario-card" style="border-top:3px solid var(--green)">
    <div class="prob pos">55%</div>
    <div class="label">실적 정당화</div>
    <div class="desc">매출 5~6조 달성. PSR 20배로 정상화. 주가 신고점.</div>
  </div>
  <div class="scenario-card" style="border-top:3px solid var(--yellow)">
    <div class="prob neu">30%</div>
    <div class="label">기대 미달</div>
    <div class="desc">매출 4조 이하. PSR 유지 불가. 추가 조정 -15%.</div>
  </div>
  <div class="scenario-card" style="border-top:3px solid var(--red)">
    <div class="prob neg">15%</div>
    <div class="label">외부 충격</div>
    <div class="desc">중동 휴전 + 수출 지연. 방산주 전체 리레이팅.</div>
  </div>
</div>
```

---

## 7. timeline — 시간 순서 이벤트

**용도**: 이벤트 전개 순서. 계층별 색상으로 구분.
**언제**: 시간 구조가 보고서의 핵심 서사일 때.

```html
<div class="timeline">
  <div class="timeline-item highlight">
    <span class="timeline-date">2026-03-01~03</span>
    <strong>정책</strong> — 이란 UAE 미사일 공격 → 천궁-II 실전 투입
  </div>
  <div class="timeline-item">
    <span class="timeline-date">2026-03-03</span>
    <strong>가격</strong> — LIG넥스원 +30% 급등
  </div>
  <div class="timeline-item">
    <span class="timeline-date">2026-03-05</span>
    <strong>전문가</strong> — 유용원 의원 '96% 요격률' 공개
  </div>
</div>
```

---

## 8. alert-box — 경고/주의

**용도**: KC approaching, 과열 경고, 데이터 한계 고지.
**언제**: 데이터에 경고 수준의 발견이 있을 때.

```html
<div class="alert-box warn">
  <strong>⚠ 밸류에이션 경고:</strong> LIG넥스원 PSR 35.3배 — 글로벌 방산 평균의 3배.
  실적이 뒷받침되지 않으면 급락 위험.
</div>

<div class="alert-box danger">
  <strong>🔴 KC 트리거:</strong> 나프타 가격 $600/t 돌파 — 석화 마진 적자 진입.
</div>

<div class="alert-box info">
  <strong>ℹ 데이터 한계:</strong> Raytheon 공식 반응 미수집. 의도적 침묵 vs 수집 한계 구분 불가.
</div>
```

---

## 9. comment — 판독 코멘트

**용도**: 렌즈별 해석, 데이터에 대한 판독.
**언제**: 사실과 해석을 시각적으로 분리할 때.

```html
<div class="comment">
  <strong>판독:</strong> 5계층 수렴이나 "수렴 속의 분열" 존재 —
  실전 입증(구조적)과 PSR 과열(단기)이 공존.
  가격은 이미 조정 중인데 서사(과열 경고)는 3/24에야 등장. 서사가 가격을 후행.
</div>
```

---

## 10. fingerprint-grid — 쟁점 지문

**용도**: 5차원 지문을 그리드로 표시.
**언제**: 지문이 보고서 맥락에 필요할 때. 무게 중심이 지문에 없으면 축소.

```html
<div class="fingerprint-grid">
  <span class="fp-label">영역</span><span>방산/국방 + 지정학</span>
  <span class="fp-label">지리</span><span>한국 → UAE → 글로벌</span>
  <span class="fp-label">접촉 자산</span><span>한화에어로, LIG넥스원, Raytheon</span>
  <span class="fp-label">이해관계자</span><span>DAPA, UAE군, GCC 구매국</span>
  <span class="fp-label">시간 성격</span><span>충격 + 구조적</span>
</div>
```

---

## 11. key-finding — 핵심 발견 1줄

**용도**: 섹션 시작 시 결론 먼저.
**언제**: 글쓰기 원칙 "첫 문장이 결론이다".

```html
<p style="font-size:.95rem;font-weight:600;margin-bottom:.75rem;">
  가격은 이미 "뉴스에 팔기" 단계에 진입 — 고점 대비 LIG -23%, 한화에어로 -10%.
</p>
```

---

## 12. uq-list — 미해소 질문

**용도**: 미해소 질문 목록. resolve_type 태그 + 해소 조건.
**언제**: Unresolved가 있을 때. 불변 규칙 — 있으면 반드시 포함.

```html
<ul class="uq-list">
  <li class="uq-open">
    <strong>UQ-014</strong> LIG넥스원 2026 실적이 PSR 35배를 정당화하는가?
    <span class="uq-type uq-data">data</span>
    <div class="uq-meta">
      해소 조건: 분기 실적 발표<br>
      기한: 2026-05-15<br>
      <span class="uq-help">→ MCP 도구로 즉시 체크 가능</span>
    </div>
  </li>
</ul>
```

---

## 13. sources-list — 출처 목록

**용도**: 하단 출처 정리.
**언제**: 항상 (불변 규칙 — 모든 수치에 출처).

```html
<ul class="sources">
  <li><a href="...">Yahoo Finance — LIG넥스원 079550</a></li>
  <li><a href="...">Army Recognition — First Combat Use</a></li>
  <li>Seoul Economic Daily (매체 인용)</li>
</ul>
```

---

## 데이터 → 컴포넌트 매핑 가이드

| 데이터 성격 | 1순위 컴포넌트 | 대안 |
|------------|---------------|------|
| Core Claim + 판정 | exec-box | key-finding |
| 수치 비교 (가격, 변동률) | monitor-table | 인라인 num 스타일 |
| 계층 간 대립/충돌 | clash-grid | direction-grid + comment |
| 시나리오 분기 | scenario-grid | 카드 + 테이블 |
| 시간 순서 전개 | timeline | 테이블 (시간 컬럼) |
| 경고/주의 | alert-box | comment + badge |
| 사실 vs 해석 분리 | comment | 별도 섹션 |
| 미해소 질문 | uq-list | 테이블 |
| 5계층 방향 | direction-grid | 테이블 |
| 쟁점 성격 요약 | fingerprint-grid | 인라인 텍스트 |

---

## 금지

```
- 데이터 없이 컴포넌트를 배치하지 않는다
- 모든 컴포넌트를 같은 크기로 만들지 않는다
- 컴포넌트를 많이 쓰면 좋다는 오해 금지. 텍스트로 충분하면 텍스트.
- 원문 JSON 구조를 그대로 테이블에 나열하지 않는다
```
