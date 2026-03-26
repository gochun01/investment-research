---
name: psf-report
description: "PSF 자율 판단 보고서. state.json → 4단계 파이프라인 → 적응형 HTML. 트리거: '보여줘'(현재 state → 렌더), '만들어줘'(갱신 + 렌더), '보고서', '브리핑 HTML', 'adaptive report'."
---

# PSF 자율 판단 보고서 — SKILL-report

> state.json을 읽고, 데이터가 보고서의 형태를 결정한다.
> 고정 템플릿이 아니다. 매번 다른 보고서가 나올 수 있다.

---

## 트리거 정의

| 트리거 | 동작 | 비고 |
|--------|------|------|
| "보여줘" | 현재 state.json → Phase 1~4 → HTML 생성 | 수집하지 않음. 있는 그대로 렌더. |
| "만들어줘" | SKILL-core.md Phase 0~6 실행 → state.json 갱신 → Phase 1~4 → HTML 생성 | 전체 파이프라인. |
| "설계만" | Phase 1~2만 실행. HTML 미생성. | `--design-only` 플래그 |
| "projection 보여줘" | projection.json → HTML | `--projection` 플래그 |

---

## 4단계 파이프라인

### Phase 1: Extract Five — 5가지 추출

state.json에서 5가지 핵심 요소를 추출한다.

| 요소 | 추출 원천 | 설명 |
|------|-----------|------|
| **Core Claim** | `regime` + `observations[0].signal` | 국면 + 1순위 관측. 보고서의 한 줄 요약. |
| **Tension** | `divergences[]` | 괴리가 존재하는가? 몇 건, 어떤 층 간? |
| **Gravity** | `observations[].severity` 분포 | critical/high/medium/low 각 몇 건. 섹션 크기 결정. |
| **Timeline** | `next_questions[].status == "open"` 존재 여부 | open 질문이 있으면 "현재 + 미래 분기". 없으면 "현재 상태". |
| **Unresolved** | `next_questions` (open) + `unclassified` | 미해소 총 건수. 0이면 해당 섹션 생략. |

부산물:
- `active_links`: links에서 active/approaching 상태인 Link 목록

### Phase 2: Design Report — 설계

Five 추출 결과로 보고서의 형태를 결정한다.

**유형 판별 (A~E):**

| 유형 | 조건 | 설명 |
|------|------|------|
| A 대립형 | Tension 있음 + Timeline 현재 | 괴리 중심. Clash 섹션 포함. |
| C 스냅샷형 | Tension 없음 + Timeline 현재 | 단순 현황. 가장 가벼운 보고서. |
| D 분기형 | Tension 없음 + Timeline 미래 분기 | 시나리오 중심. Scenario Grid 포함. |
| E 복합형 | Tension 있음 + Timeline 미래 분기 | 대립 + 분기. 가장 무거운 보고서. |

**분류 판별:**

| 분류 | 조건 | topbar 색상 |
|------|------|-------------|
| CRISIS ALERT | regime 🔴 또는 L8 활성 | red |
| SPECIAL REPORT | 시나리오 분기 또는 Tension 존재 | blue |
| RESEARCH NOTE | 기본 (위 조건 미해당) | navy |
| STRATEGY UPDATE | projection 기반 (--projection) | gold |

**섹션 구성 (Gravity 기반):**

```
항상 포함:
  [L] Executive Verdict (exec-box)
  [L] 국면 대시보드 (regime-dashboard)

조건부:
  [L] 긴장 구조       ← Tension 있을 때 (divergence-card)
  [L] 핵심 관측       ← critical 관측 있을 때 (observation-card)
  [M] 주요 변화       ← high 관측 있을 때 (observation-card)
  [M] Link 상태       ← active link 있을 때 (link-status)
  [M] 축 상태         ← 항상 (axis-status)
  [S] 보조 관측       ← medium 관측 있을 때 (monitor-table)
  [M] 감시 + 시나리오 ← open question 있을 때 (scenario-grid)
  [S] 미해소 질문     ← unresolved > 0일 때 (open-questions)
```

L = section-large, M = section (medium), S = section-small

### Phase 3: Render HTML — 생성

Phase 2의 설계대로 HTML을 조합한다.

- CSS: `assets/template-base.html`의 디자인 시스템 기반
- 컴포넌트: `references/component-catalog.md` 참조
- 코드: `core/render_adaptive.py`

구조:
```
<!DOCTYPE html>
<head> + CSS inline (외부 의존 최소화)
<body>
  topbar (분류)
  container
    report-header (제목 + 뱃지)
    [섹션 1] ... [섹션 N]  ← Phase 2에서 결정된 순서
    footer + disclaimer
```

### Phase 4: Verify — 셀프 감사

| 코드 | 검증 항목 | 실패 시 |
|------|-----------|---------|
| V1 | Core Claim이 HTML에 존재하는가 | FAIL — 재생성 |
| V2 | 상위 3개 관측의 핵심 수치가 반영되었는가 | WARN — 로그 출력 |
| V3 | 빈 섹션이 없는가 | WARN — 로그 출력 |
| V4 | critical 관측 → large 섹션인가 (Gravity 비례) | WARN — 로그 출력 |
| V5 | 첫 화면에 exec-box가 있는가 | WARN — 로그 출력 |

---

## state.json → Five 추출 매핑

```
state.json 키              →  Five 요소
─────────────────────────────────────────
regime                     →  Core Claim (국면 부분)
observations[0].signal     →  Core Claim (관측 부분)
observations[].severity    →  Gravity (분포 집계)
divergences[]              →  Tension (존재 + 상세)
next_questions[status=open]→  Timeline (있으면 미래 분기)
                           →  Unresolved (질문 수)
unclassified[]             →  Unresolved (미분류 수)
links[].status             →  active_links (부산물)
```

**Phase 2에서 추가로 참조하는 키:**
- `regime` — 🔴 여부 (CRISIS ALERT 판정)
- `links` — L8 활성 여부 (CRISIS ALERT 판정)

**Phase 3에서 렌더링에 사용하는 키:**
- `plates` (P1~P5 + verdict) — 대시보드 P열
- `structure` (S1~S5 + verdict) — 대시보드 S열
- `flow` (F1~F5 + verdict) — 대시보드 F열
- `macro_interface` (macro_regime, alignment) — 헤더 뱃지
- `axis_status` — 축 상태 카드
- `quality` (mcp_count, mcp_ratio) — 푸터
- `last_updated` — 제목 날짜
- `projection.json` (있으면) — 시나리오 그리드

---

## 실행 방법

```bash
# 현재 state.json → HTML
python core/render_adaptive.py

# projection.json → HTML
python core/render_adaptive.py --projection

# 특정 파일 → HTML
python core/render_adaptive.py --file history/2026-03-23.json

# Phase 1-2만 (설계안 확인)
python core/render_adaptive.py --design-only
```

출력: `reports/{date}-briefing-adaptive.html`

---

## F-테이블 (실패 유형)

| 코드 | 실패 유형 | 원인 | 대응 |
|------|-----------|------|------|
| F-01 | state.json 없음 | 파일 미존재 또는 경로 오류 | 오류 출력 + 종료. "PSF 갱신" 먼저 실행 권고. |
| F-02 | observations 비어있음 | 수집 실패 또는 빈 state | Core Claim을 "관측 없음"으로 설정. 스냅샷형(C) 강제. |
| F-03 | HTML 렌더링 실패 | 키 누락, 타입 오류 | try-except로 해당 섹션 건너뜀. 로그 출력. |
| F-04 | V1 FAIL (Core Claim 미반영) | 렌더링 버그 | 재생성 1회 시도. 재실패 시 로그 + 저장. |
| F-05 | projection.json 파싱 실패 | 형식 오류 | 시나리오 그리드 생략. 감시 질문만 표시. |
| F-06 | 출력 디렉토리 쓰기 실패 | 권한 문제 | mkdir -p 시도. 실패 시 stdout 출력. |

---

## 불변 규칙

```
1. PSF는 관측한다. 해석하지 않는다.
   보고서에 "왜 그런지", "앞으로 어떻게 될지", "뭘 해야 하는지"를 쓰지 않는다.
   관측 경로(path)와 수치만 기록한다.

2. 데이터가 형태를 결정한다.
   Tension이 없으면 Clash 섹션이 없다.
   critical이 없으면 핵심 관측 섹션이 없다.
   open question이 없으면 시나리오 섹션이 없다.
   고정 템플릿을 강제하지 않는다.

3. Gravity가 크기를 결정한다.
   critical → large. high → medium. medium → small table.
   중요한 것은 크게, 덜 중요한 것은 작게.

4. 첫 화면에 Core Claim.
   topbar + header + exec-box는 스크롤 없이 보여야 한다.

5. 출처를 속이지 않는다.
   MCP 수치와 비율을 footer에 표기한다.
   state.json의 quality 필드를 그대로 반영한다.

6. disclaimer는 항상 포함한다.
   "이 보고서는 관측 결과입니다. 투자 판단이나 행동 권고가 아닙니다."
```

---

## 참조 파일

| 파일 | 역할 |
|------|------|
| `assets/template-base.html` | CSS 디자인 시스템 (변수, 컴포넌트 클래스) |
| `references/component-catalog.md` | HTML 컴포넌트 카탈로그 (예제 포함) |
| `core/render_adaptive.py` | Python 렌더러 (Phase 1~4 구현) |
| `state.json` | 입력 데이터 (현재 관측값) |
| `projection.json` | 입력 데이터 (12개월 투영, 선택) |
| `SCHEMAS.md` | state.json / projection.json 스키마 정의 |
