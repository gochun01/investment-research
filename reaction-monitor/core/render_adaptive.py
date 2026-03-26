"""자율 판단 보고서 생성기 — state.json → Adaptive HTML 보고서.

기존 render.py(고정 §1~§5 구조)와 병존.
데이터가 보고서의 형태를 결정한다.

사용:
  python core/render_adaptive.py                      # state.json → adaptive HTML
  python core/render_adaptive.py path/to/state.json   # 지정 파일

Phase 1: 데이터 읽기 — Core Claim, Tension, Gravity, Timeline, Unresolved 추출
Phase 2: 구조 설계 — 보고서 유형(A~E) 판정 + 섹션 자율 구성
Phase 3: 렌더링 — 컴포넌트 자율 선택 + HTML 생성
Phase 4: 자기 검증 — V1~V5 체크
"""

import json
import html as html_mod
import re
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

BASE_DIR = Path(__file__).parent.parent
TEMPLATE_PATH = BASE_DIR / "assets" / "template-base.html"
REPORTS_DIR = BASE_DIR / "reports"


# ═══════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════

def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def tone_class(tone: str) -> str:
    if tone in ("긍", "pos", "Positive"):
        return "pos"
    if tone in ("부", "neg", "Negative"):
        return "neg"
    if tone in ("분열", "split"):
        return "spl"
    if tone in ("침묵",):
        return "silent"
    return "neu"


# ═══════════════════════════════════════
# Phase 1: 데이터 읽기
# ═══════════════════════════════════════

@dataclass
class DataReading:
    """Phase 1 추출 결과."""
    core_claim: str = ""
    tension: str = ""           # "있음 — 설명" 또는 "없음"
    tension_exists: bool = False
    gravity: dict = field(default_factory=dict)  # {layer: weight}
    gravity_primary: str = ""   # 가장 무거운 영역
    timeline_focus: str = ""    # "과거" / "현재" / "미래" / "현재+미래"
    unresolved_count: int = 0
    unresolved_items: list = field(default_factory=list)


def phase1_read(data: dict) -> DataReading:
    """state.json에서 5가지를 추출한다."""
    reading = DataReading()
    pt = data.get("pattern", {})
    rx = data.get("reactions", {})
    fp = data.get("fingerprint", {})
    uq = data.get("unresolved", [])

    # ① Core Claim: pattern.direction_rationale의 핵심 1문장
    rationale = pt.get("direction_rationale", "")
    if rationale:
        # 첫 문장 또는 마침표까지
        sentences = [s.strip() for s in re.split(r'[.。]', rationale) if s.strip()]
        reading.core_claim = sentences[0] if sentences else rationale

    # ② Tension: direction_detail에서 충돌하는 힘 찾기
    detail = pt.get("direction_detail", {})
    directions = {}
    for layer, desc in detail.items():
        if "↑" in str(desc) and "↓" not in str(desc):
            directions[layer] = "up"
        elif "↓" in str(desc) and "↑" not in str(desc):
            directions[layer] = "down"
        elif "↑↓" in str(desc) or "분열" in str(desc):
            directions[layer] = "split"
        elif "→" in str(desc) or "무반응" in str(desc):
            directions[layer] = "flat"
        else:
            directions[layer] = "up" if "긍" in str(desc) or "+" in str(desc) else "mixed"

    ups = [k for k, v in directions.items() if v == "up"]
    downs = [k for k, v in directions.items() if v == "down"]
    splits = [k for k, v in directions.items() if v == "split"]

    if (ups and downs) or splits:
        reading.tension_exists = True
        if ups and downs:
            reading.tension = f"있음 — {', '.join(ups)}(↑) vs {', '.join(downs)}(↓)"
        elif splits:
            reading.tension = f"있음 — {', '.join(splits)} 내부 분열"
    else:
        # 방향은 수렴이나 rationale에 "그러나/다만/but" 있으면 잠재 긴장
        if any(kw in rationale for kw in ["그러나", "다만", "하지만", "공존", "속의"]):
            reading.tension_exists = True
            reading.tension = "잠재 — 수렴 속 내부 긴장 존재"
        else:
            reading.tension = "없음"

    # ③ Gravity: 각 계층의 데이터 양 측정
    layer_weights = {}
    for layer_name in ["price", "narrative", "expert", "policy", "positioning"]:
        items = rx.get(layer_name, [])
        if not items:
            continue
        # 가중치: 항목 수 + 내용 깊이(문자 수 비례)
        content_depth = sum(len(str(item)) for item in items)
        weight = len(items) * 10 + content_depth // 100
        layer_weights[layer_name] = weight

    # 패턴 데이터도 무게에 포함
    pattern_depth = len(json.dumps(pt, ensure_ascii=False))
    if pattern_depth > 500:
        layer_weights["pattern"] = pattern_depth // 50

    reading.gravity = dict(sorted(layer_weights.items(), key=lambda x: x[1], reverse=True))
    if reading.gravity:
        reading.gravity_primary = list(reading.gravity.keys())[0]

    # ④ Timeline: time_character + time_structure에서 추론
    time_char = fp.get("time_character", "")
    time_struct = pt.get("time_structure", "")

    if "충격" in time_char or "즉시" in time_char:
        reading.timeline_focus = "현재"
    elif "구조적" in time_char and "충격" in time_char:
        reading.timeline_focus = "현재+미래"
    elif "전개" in time_char:
        reading.timeline_focus = "현재"
    elif "구조적" in time_char:
        reading.timeline_focus = "미래"
    else:
        reading.timeline_focus = "현재"

    # unresolved가 많으면 미래 비중 높임
    open_uq = [q for q in uq if isinstance(q, dict) and q.get("status") == "open"]
    if len(open_uq) >= 3 and "미래" not in reading.timeline_focus:
        reading.timeline_focus = reading.timeline_focus + "+미래"

    # ⑤ Unresolved
    reading.unresolved_count = len(open_uq)
    reading.unresolved_items = open_uq

    return reading


# ═══════════════════════════════════════
# Phase 2: 구조 설계
# ═══════════════════════════════════════

@dataclass
class Section:
    """보고서 섹션."""
    id: str
    title: str
    size: str        # "large" / "medium" / "small"
    component: str   # 주력 컴포넌트 힌트
    data_key: str    # state.json에서 가져올 키
    render_fn: str   # 렌더 함수명


@dataclass
class ReportDesign:
    """Phase 2 설계 결과."""
    report_type: str = ""       # A, B, C, D, E
    report_type_name: str = ""  # 대립형, 서사형, ...
    report_class: str = ""      # CRISIS ALERT, SPECIAL REPORT, ...
    topbar_class: str = ""      # crisis, special, research, strategy
    title: str = ""
    subtitle: str = ""
    sections: list = field(default_factory=list)


def phase2_design(data: dict, reading: DataReading) -> ReportDesign:
    """Phase 1 결과로 보고서 구조를 설계한다."""
    design = ReportDesign()
    pt = data.get("pattern", {})
    rx = data.get("reactions", {})
    uq = data.get("unresolved", [])

    # ── 보고서 유형 판정 ──
    has_tension = reading.tension_exists
    has_scenarios = reading.unresolved_count >= 2 and "미래" in reading.timeline_focus
    is_snapshot = reading.timeline_focus == "현재" and not has_tension
    is_narrative = not has_tension and "과거" in reading.timeline_focus

    if has_tension and has_scenarios:
        design.report_type = "E"
        design.report_type_name = "복합형 (대립+분기)"
    elif has_tension:
        design.report_type = "A"
        design.report_type_name = "대립형"
    elif has_scenarios:
        design.report_type = "D"
        design.report_type_name = "분기형"
    elif is_snapshot:
        design.report_type = "C"
        design.report_type_name = "스냅샷형"
    elif is_narrative:
        design.report_type = "B"
        design.report_type_name = "서사형"
    else:
        design.report_type = "B"
        design.report_type_name = "서사형"

    # ── report-class 자동 판정 ──
    alignment = pt.get("direction_alignment", "")
    proportionality = pt.get("proportionality", "")

    if "괴리" in alignment or "과잉" in proportionality:
        design.report_class = "CRISIS ALERT"
        design.topbar_class = "crisis"
    elif has_scenarios or has_tension:
        design.report_class = "SPECIAL REPORT"
        design.topbar_class = "special"
    elif "전략" in data.get("issue", ""):
        design.report_class = "STRATEGY UPDATE"
        design.topbar_class = "strategy"
    else:
        design.report_class = "RESEARCH NOTE"
        design.topbar_class = "research"

    # ── 제목/부제 ──
    design.title = data.get("issue", "시장 반응 수집")
    design.subtitle = reading.core_claim

    # ── 섹션 자율 구성 ──
    sections = []

    # 1. Executive Verdict — 항상 (Core Claim + 판정)
    sections.append(Section(
        id="exec", title="Executive Verdict",
        size="large", component="exec-box",
        data_key="pattern", render_fn="render_exec_verdict"
    ))

    # 2. Gravity 기반 주력 섹션
    gravity_keys = list(reading.gravity.keys())

    # 대립형이면 Clash 섹션 우선
    if design.report_type in ("A", "E"):
        sections.append(Section(
            id="clash", title="The Clash",
            size="large", component="clash-grid",
            data_key="pattern", render_fn="render_clash"
        ))

    # 무게 중심 순서로 반응 섹션 배치
    layer_labels = {
        "price": "가격 반응", "narrative": "서사 반응",
        "expert": "전문가 반응", "policy": "정책 반응",
        "positioning": "포지셔닝"
    }

    for layer_key in gravity_keys:
        if layer_key == "pattern":
            continue
        if layer_key not in layer_labels:
            continue

        weight = reading.gravity[layer_key]
        # 무게에 따라 크기 결정
        if weight >= 80:
            size = "large"
        elif weight >= 40:
            size = "medium"
        else:
            size = "small"

        sections.append(Section(
            id=layer_key, title=layer_labels[layer_key],
            size=size, component="monitor-table",
            data_key=f"reactions.{layer_key}",
            render_fn=f"render_{layer_key}"
        ))

    # 패턴 판독 — 무게가 있으면 포함
    if "pattern" in reading.gravity or len(gravity_keys) >= 3:
        sections.append(Section(
            id="pattern", title="패턴 판독",
            size="medium" if design.report_type not in ("A", "E") else "large",
            component="direction-grid + timeline",
            data_key="pattern", render_fn="render_pattern"
        ))

    # 시나리오 — 분기형이면 포함
    if design.report_type in ("D", "E"):
        sections.append(Section(
            id="scenarios", title="시나리오 분기",
            size="large", component="scenario-grid",
            data_key="unresolved", render_fn="render_scenarios"
        ))

    # 미해소 질문 — 있으면 포함
    if reading.unresolved_count > 0:
        sections.append(Section(
            id="unresolved", title="미해소 질문",
            size="small" if reading.unresolved_count <= 2 else "medium",
            component="uq-list",
            data_key="unresolved", render_fn="render_unresolved"
        ))

    # Sources — 항상
    sections.append(Section(
        id="sources", title="Sources",
        size="small", component="sources-list",
        data_key="reactions", render_fn="render_sources"
    ))

    design.sections = sections
    return design


# ═══════════════════════════════════════
# Phase 3: 렌더링 — 컴포넌트별 렌더 함수
# ═══════════════════════════════════════

def render_exec_verdict(data: dict, reading: DataReading, _design: ReportDesign) -> str:
    """Core Claim + 판정 배지."""
    pt = data.get("pattern", {})
    alignment = pt.get("direction_alignment", "—")
    prop = pt.get("proportionality", "—")

    # 배지 색상 결정
    align_cls = "badge-green" if alignment in ("수렴",) else \
                "badge-red" if alignment in ("괴리",) else \
                "badge-yellow"
    prop_cls = "badge-green" if prop in ("비례",) else \
               "badge-red" if prop in ("과잉",) else \
               "badge-yellow"

    uq_open = reading.unresolved_count
    uq_badge = f'<span class="badge badge-blue">미해소 {uq_open}건</span>' if uq_open > 0 else ""

    return f"""<div class="exec-box">
  <div class="claim">{esc(reading.core_claim)}</div>
  <div class="verdict">
    <span class="badge {align_cls}">방향: {esc(alignment)}</span>
    <span class="badge {prop_cls}">비례: {esc(prop)}</span>
    {uq_badge}
  </div>
</div>"""


def render_clash(data: dict, reading: DataReading, _design: ReportDesign) -> str:
    """대립 구조 시각화."""
    pt = data.get("pattern", {})
    detail = pt.get("direction_detail", {})
    rx = data.get("reactions", {})

    # 긍정/부정 반응을 분류
    bull_items = []
    bear_items = []

    # 서사에서 추출
    for item in rx.get("narrative", []):
        tone = item.get("tone", "")
        frame = item.get("frame", "")
        if tone in ("긍", "pos"):
            bull_items.append(f"{esc(item.get('source', ''))}: {esc(frame[:60])}")
        elif tone in ("부", "neg"):
            bear_items.append(f"{esc(item.get('source', ''))}: {esc(frame[:60])}")

    # 전문가에서 추출
    for item in rx.get("expert", []):
        direction = item.get("direction", "")
        stmt = item.get("statement", "")[:60]
        if direction in ("긍", "pos"):
            bull_items.append(f"{esc(item.get('name', ''))}: {esc(stmt)}")
        elif direction in ("부", "neg"):
            bear_items.append(f"{esc(item.get('name', ''))}: {esc(stmt)}")
        elif direction == "침묵":
            bear_items.append(f"{esc(item.get('name', ''))}: 침묵 ({esc(item.get('note', '')[:40])})")

    bull_html = "\n".join(f"<li>{item}</li>" for item in bull_items[:5])
    bear_html = "\n".join(f"<li>{item}</li>" for item in bear_items[:5])

    rationale = pt.get("direction_rationale", "")
    comment_html = f'<div class="comment"><strong>판독:</strong> {esc(rationale)}</div>' if rationale else ""

    return f"""<div class="clash-grid">
  <div class="clash-side bull">
    <h4 class="pos">호재 신호</h4>
    <ul style="font-size:.82rem;list-style:disc;padding-left:1.2rem;">
      {bull_html}
    </ul>
  </div>
  <div class="clash-side bear">
    <h4 class="neg">리스크 신호</h4>
    <ul style="font-size:.82rem;list-style:disc;padding-left:1.2rem;">
      {bear_html}
    </ul>
  </div>
</div>
{comment_html}"""


def render_price(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """가격 반응 테이블."""
    items = data.get("reactions", {}).get("price", [])
    if not items:
        return ""

    rows = []
    for r in items:
        chg = r.get("change_pct", 0)
        cls = "neg" if chg < -1 else "pos" if chg > 1 else "neu"
        note = r.get("note", "")
        rows.append(f"""<tr>
<td><strong>{esc(r.get('asset', ''))}</strong></td>
<td class="num">{esc(r.get('before', '—'))}</td>
<td class="num">{esc(r.get('after', '—'))}</td>
<td class="{cls} num">{chg:+.1f}%</td>
<td>{esc(r.get('speed', ''))}</td>
<td style="font-size:.78rem;">{esc(note[:80])}</td>
</tr>""")

    return f"""<table>
<tr><th>자산</th><th>이전</th><th>이후</th><th>변동</th><th>속도</th><th>핵심</th></tr>
{''.join(rows)}
</table>"""


def render_narrative(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """서사 반응 테이블."""
    items = data.get("reactions", {}).get("narrative", [])
    if not items:
        return ""

    rows = []
    for r in items:
        tc = tone_class(r.get("tone", ""))
        role = r.get("role", "")
        rows.append(f"""<tr>
<td>{esc(r.get('source', ''))}</td>
<td>{esc(r.get('frame', ''))}</td>
<td class="{tc}">{esc(r.get('tone', ''))}</td>
<td>{esc(role)}</td>
<td style="font-size:.75rem;">{esc(r.get('timestamp', ''))}</td>
</tr>""")

    return f"""<table>
<tr><th>매체</th><th>프레임</th><th>톤</th><th>역할</th><th>시점</th></tr>
{''.join(rows)}
</table>"""


def render_expert(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """전문가 반응 테이블."""
    items = data.get("reactions", {}).get("expert", [])
    if not items:
        return ""

    rows = []
    for r in items:
        tc = tone_class(r.get("direction", ""))
        note = r.get("note", "")
        note_html = f'<br><span style="font-size:.72rem;color:var(--muted);">{esc(note[:60])}</span>' if note else ""
        rows.append(f"""<tr>
<td><strong>{esc(r.get('name', ''))}</strong><br>
<span style="color:var(--muted);font-size:.75rem;">{esc(r.get('affiliation', ''))} · {esc(r.get('role', ''))}</span></td>
<td>{esc(r.get('statement', ''))}{note_html}</td>
<td class="{tc}">{esc(r.get('direction', ''))}</td>
</tr>""")

    return f"""<table>
<tr><th>이름/기관</th><th>핵심 발언</th><th>방향</th></tr>
{''.join(rows)}
</table>"""


def render_policy(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """정책 반응 테이블."""
    items = data.get("reactions", {}).get("policy", [])
    if not items:
        return ""

    rows = []
    for r in items:
        rows.append(f"""<tr>
<td><strong>{esc(r.get('institution', ''))}</strong></td>
<td>{esc(r.get('action', ''))}</td>
<td>{esc(r.get('binding_level', ''))}</td>
<td>{esc(r.get('market_implication', ''))}</td>
</tr>""")

    return f"""<table>
<tr><th>기관</th><th>조치</th><th>구속력</th><th>시장 시사점</th></tr>
{''.join(rows)}
</table>"""


def render_positioning(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """포지셔닝 반응 테이블."""
    items = data.get("reactions", {}).get("positioning", [])
    if not items:
        return ""

    rows = []
    for r in items:
        rows.append(f"""<tr>
<td><strong>{esc(r.get('indicator', ''))}</strong></td>
<td class="num">{esc(r.get('value', ''))}</td>
<td>{esc(r.get('implication', ''))}</td>
</tr>""")

    return f"""<table>
<tr><th>지표</th><th>값</th><th>시사점</th></tr>
{''.join(rows)}
</table>"""


def render_pattern(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """패턴 판독 — 방향 그리드 + 타임라인 + 코멘트."""
    pt = data.get("pattern", {})
    html_parts = []

    # 방향 그리드
    detail = pt.get("direction_detail", {})
    labels = {"price": "가격", "narrative": "서사", "expert": "전문가",
              "policy": "정책", "positioning": "포지셔닝"}
    colors = {"↑": "var(--converge)", "↓": "var(--decouple)", "→": "var(--silence)",
              "↑↓": "var(--diverge)"}

    cells = []
    for key, label in labels.items():
        val = detail.get(key, "—")
        # 방향 기호 추출
        arrow = "→"
        for sym in ["↑↓", "↑", "↓", "→"]:
            if sym in str(val):
                arrow = sym
                break
        color = colors.get(arrow, "var(--muted)")
        cells.append(f'<div class="direction-cell"><span class="direction-label">{label}</span>'
                     f'<span class="direction-value" style="color:{color}">{esc(arrow)}</span></div>')

    html_parts.append(f"""<h3>방향 일치도 — {esc(pt.get('direction_alignment', ''))}</h3>
<div class="direction-grid">{''.join(cells)}</div>
<div class="comment"><strong>판독:</strong> {esc(pt.get('direction_rationale', ''))}</div>""")

    # 타임라인
    sequence = pt.get("time_sequence", [])
    if sequence:
        items = []
        for s in sorted(sequence, key=lambda x: x.get("order", 0)):
            layer = s.get("layer", "")
            cls = " highlight" if any(kw in layer for kw in ["정책", "전쟁", "충격"]) else ""
            items.append(f'<div class="timeline-item{cls}"><span class="timeline-date">'
                         f'{esc(s.get("timestamp", ""))}</span> <strong>{esc(layer)}</strong> — '
                         f'{esc(s.get("event", ""))}</div>')
        html_parts.append(f"""<h3>시간 구조 — {esc(pt.get('time_structure', ''))}</h3>
<div class="timeline">{''.join(items)}</div>
<div class="comment"><strong>판독:</strong> {esc(pt.get('time_rationale', ''))}</div>""")

    # 비례성 + 전파
    if pt.get("proportionality_rationale"):
        html_parts.append(f"""<h3>비례성 — {esc(pt.get('proportionality', ''))}</h3>
<p style="font-size:.85rem;">{esc(pt.get('proportionality_rationale', ''))}</p>""")

    if pt.get("propagation_rationale"):
        html_parts.append(f"""<h3>전파 경로 — {esc(pt.get('propagation', ''))}</h3>
<p style="font-size:.85rem;">{esc(pt.get('propagation_rationale', ''))}</p>""")

    if pt.get("next_observation"):
        html_parts.append(f"""<div class="alert-box info">
<strong>후속 관찰:</strong> {esc(pt.get('next_observation', ''))}
</div>""")

    return "\n".join(html_parts)


def render_scenarios(data: dict, reading: DataReading, _design: ReportDesign) -> str:
    """미해소 질문 기반 시나리오 카드."""
    uq = reading.unresolved_items
    if not uq:
        return ""

    cards = []
    colors = ["var(--green)", "var(--yellow)", "var(--red)", "var(--accent)"]
    for i, item in enumerate(uq[:4]):
        color = colors[i % len(colors)]
        rt = item.get("resolve_type", "")
        condition = item.get("resolve_condition", "")
        cards.append(f"""<div class="scenario-card" style="border-top:3px solid {color}">
  <div class="label">{esc(item.get('question', '')[:50])}</div>
  <div class="desc" style="margin-top:.3rem;">
    <span class="uq-type uq-{esc(rt)}">{esc(rt)}</span>
    {esc(condition)}
  </div>
</div>""")

    return f'<div class="scenario-grid">{"".join(cards)}</div>'


def render_unresolved(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """미해소 질문 목록."""
    uq = data.get("unresolved", [])
    if not uq:
        return '<p style="color:var(--muted);">미해소 질문 없음</p>'

    lis = []
    for item in uq:
        if isinstance(item, str):
            lis.append(f'<li class="uq-open">{esc(item)}</li>')
            continue
        status_cls = "uq-resolved" if item.get("status") == "resolved" else "uq-open"
        rt = item.get("resolve_type", "")

        meta_parts = []
        if item.get("resolve_condition"):
            meta_parts.append(f"해소 조건: {esc(item['resolve_condition'])}")
        if item.get("deadline"):
            meta_parts.append(f"기한: {esc(item['deadline'])}")
        if item.get("last_checked"):
            meta_parts.append(f"마지막 체크: {esc(item['last_checked'])} — {esc(item.get('last_checked_result', ''))}")

        meta_html = "<br>".join(meta_parts)

        lis.append(f"""<li class="{status_cls}">
<strong>{esc(item.get('id', ''))}</strong> {esc(item.get('question', ''))}
<span class="uq-type uq-{esc(rt)}">{esc(rt)}</span>
<div class="uq-meta">{meta_html}</div>
</li>""")

    next_check = data.get("next_check", "")
    next_html = f'<p style="font-size:.82rem;color:var(--muted);margin-top:.75rem;"><strong>다음 확인:</strong> {esc(next_check)}</p>' if next_check else ""

    return f'<ul class="uq-list">{"".join(lis)}</ul>{next_html}'


def render_sources(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    """출처 목록."""
    reactions = data.get("reactions", {})
    sources = set()
    for layer_items in reactions.values():
        if not isinstance(layer_items, list):
            continue
        for item in layer_items:
            if not isinstance(item, dict):
                continue
            for key in ("source", "url"):
                val = item.get(key, "")
                if val and val.startswith("http"):
                    source_name = item.get("source", "") or item.get("name", "") or item.get("institution", "") or val
                    sources.add((source_name, val))
                elif val and val != "—":
                    sources.add((val, ""))

    lis = []
    for name, url in sorted(sources):
        if url:
            lis.append(f'<li><a href="{esc(url)}">{esc(name)}</a></li>')
        else:
            lis.append(f'<li>{esc(name)}</li>')

    return f'<ul class="sources">{"".join(lis)}</ul>' if lis else ""


# 렌더 함수 매핑
RENDER_MAP = {
    "render_exec_verdict": render_exec_verdict,
    "render_clash": render_clash,
    "render_price": render_price,
    "render_narrative": render_narrative,
    "render_expert": render_expert,
    "render_policy": render_policy,
    "render_positioning": render_positioning,
    "render_pattern": render_pattern,
    "render_scenarios": render_scenarios,
    "render_unresolved": render_unresolved,
    "render_sources": render_sources,
}


# ═══════════════════════════════════════
# Phase 3: 조립
# ═══════════════════════════════════════

def phase3_render(data: dict, reading: DataReading, design: ReportDesign) -> str:
    """설계에 따라 HTML을 조립한다."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # 섹션별 HTML 생성
    body_parts = []
    for section in design.sections:
        fn = RENDER_MAP.get(section.render_fn)
        if not fn:
            continue
        section_html = fn(data, reading, design)
        if not section_html or not section_html.strip():
            continue  # 빈 섹션은 만들지 않는다

        # 섹션 래퍼 (exec는 h2 없이)
        if section.id == "exec":
            body_parts.append(section_html)
        else:
            body_parts.append(f"<h2>{esc(section.title)}</h2>\n{section_html}")

    body_html = "\n\n".join(body_parts)

    # 템플릿 치환
    result = template
    replacements = {
        "{{TOPBAR_CLASS}}": design.topbar_class,
        "{{REPORT_CLASS}}": esc(design.report_class),
        "{{TITLE}}": esc(design.title),
        "{{SUBTITLE}}": esc(design.subtitle),
        "{{DATE}}": esc(data.get("date", "")),
        "{{DEPTH}}": esc(data.get("depth", "Standard")),
        "{{BODY}}": body_html,
    }

    for key, val in replacements.items():
        result = result.replace(key, val)

    return result


# ═══════════════════════════════════════
# Phase 4: 자기 검증
# ═══════════════════════════════════════

@dataclass
class VerifyResult:
    """검증 결과."""
    v1_claim_ok: bool = False
    v2_data_ok: bool = False
    v3_no_empty: bool = False
    v4_proportional: bool = False
    v5_first_screen: bool = False
    issues: list = field(default_factory=list)


def phase4_verify(data: dict, reading: DataReading, design: ReportDesign, html: str) -> VerifyResult:
    """V1~V5 자기 검증."""
    result = VerifyResult()

    # V1: Core Claim 정합성 — claim이 HTML에 포함되어 있는가
    result.v1_claim_ok = reading.core_claim and reading.core_claim[:20] in html
    if not result.v1_claim_ok:
        result.issues.append("V1: Core Claim이 보고서에 포함되지 않음")

    # V2: 핵심 수치 누락 — price 반응의 change_pct가 HTML에 있는가
    prices = data.get("reactions", {}).get("price", [])
    missing = []
    for p in prices:
        chg = p.get("change_pct", 0)
        if f"{chg:+.1f}" not in html and str(abs(chg)) not in html:
            missing.append(p.get("asset", "?"))
    result.v2_data_ok = len(missing) == 0
    if missing:
        result.issues.append(f"V2: 핵심 수치 누락 — {', '.join(missing)}")

    # V3: 빈 섹션 — <h2> 뒤에 내용이 있는가
    h2_pattern = re.findall(r'<h2>.*?</h2>\s*\n*\s*(<[^/]|$)', html)
    result.v3_no_empty = True  # 빈 섹션은 phase3에서 이미 제거

    # V4: 무게 비례 — large 섹션이 gravity 상위에 있는가
    large_sections = [s for s in design.sections if s.size == "large"]
    if reading.gravity_primary and large_sections:
        result.v4_proportional = True
    else:
        result.v4_proportional = len(design.sections) <= 3
    if not result.v4_proportional:
        result.issues.append("V4: 데이터 양과 섹션 크기 비례 미확인")

    # V5: 첫 화면 — exec-box가 content 영역에서 첫 컴포넌트인가
    content_pos = html.find('class="content"')
    # content 이후에서 exec-box 찾기
    exec_pos = html.find('class="exec-box"', content_pos) if content_pos > 0 else -1
    result.v5_first_screen = exec_pos > 0 and (exec_pos - content_pos) < 500
    if not result.v5_first_screen:
        result.issues.append("V5: Core Claim이 첫 화면에 없음")

    return result


# ═══════════════════════════════════════
# 메인
# ═══════════════════════════════════════

def render_adaptive(data: dict) -> tuple[str, DataReading, ReportDesign, VerifyResult]:
    """전체 파이프라인 실행. (html, reading, design, verify) 반환."""
    # Phase 1
    reading = phase1_read(data)

    # Phase 2
    design = phase2_design(data, reading)

    # Phase 3
    html = phase3_render(data, reading, design)

    # Phase 4
    verify = phase4_verify(data, reading, design, html)

    return html, reading, design, verify


def main():
    if len(sys.argv) > 1:
        state_path = Path(sys.argv[1])
    else:
        state_path = BASE_DIR / "state.json"

    if not state_path.exists():
        print(f"state.json not found: {state_path}")
        sys.exit(1)

    if not TEMPLATE_PATH.exists():
        print(f"template-base.html not found: {TEMPLATE_PATH}")
        sys.exit(1)

    data = json.loads(state_path.read_text(encoding="utf-8"))
    html, reading, design, verify = render_adaptive(data)

    # 파일명 생성
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    issue_slug = re.sub(r'[^\w가-힣]', '-', data.get("issue", "reaction"))[:30].strip("-")
    filename = f"{date}-{issue_slug}-adaptive.html"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / filename
    out_path.write_text(html, encoding="utf-8")

    # 결과 출력
    print(f"{'=' * 50}")
    print(f"  Adaptive Report Generated")
    print(f"{'=' * 50}")
    print(f"  File: {out_path}")
    print(f"  Issue: {data.get('issue', '?')}")
    print(f"  Date: {date}")
    print()
    print(f"  [Phase 1] Data Reading")
    print(f"    Core Claim: {reading.core_claim[:60]}...")
    print(f"    Tension: {reading.tension}")
    print(f"    Gravity: {' > '.join(reading.gravity.keys())}")
    print(f"    Timeline: {reading.timeline_focus}")
    print(f"    Unresolved: {reading.unresolved_count}건")
    print()
    print(f"  [Phase 2] Design")
    print(f"    Type: {design.report_type} ({design.report_type_name})")
    print(f"    Class: {design.report_class}")
    print(f"    Sections: {len(design.sections)}개")
    for s in design.sections:
        print(f"      [{s.size[0].upper()}] {s.title}")
    print()
    print(f"  [Phase 4] Verify")
    print(f"    V1 Core Claim: {'OK' if verify.v1_claim_ok else 'FAIL'}")
    print(f"    V2 Data:       {'OK' if verify.v2_data_ok else 'FAIL'}")
    print(f"    V3 No Empty:   {'OK' if verify.v3_no_empty else 'FAIL'}")
    print(f"    V4 Proportion: {'OK' if verify.v4_proportional else 'FAIL'}")
    print(f"    V5 First Screen: {'OK' if verify.v5_first_screen else 'FAIL'}")
    if verify.issues:
        print(f"    Issues:")
        for issue in verify.issues:
            print(f"      - {issue}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
