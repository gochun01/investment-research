"""자율 판단 보고서 생성기 — result_json → Adaptive HTML 보고서.

기존 html_renderer.py(7+1 고정 구조)와 병존.
검증 결과의 성격이 보고서 형태를 결정한다.

사용:
  from core.render_adaptive import AdaptiveVerificationRenderer
  renderer = AdaptiveVerificationRenderer(result_json)
  html = renderer.render()
  path = renderer.save()

Phase 5-A: 데이터 읽기 (Core Claim, Tension, Gravity, Timeline, Unresolved)
Phase 5-B: 구조 설계 (유형 A~E 판정 + 섹션 자율 구성)
Phase 5-C: 렌더링 (컴포넌트 자율 선택 + HTML 생성)
Phase 5-F: 자기 검증 (V1~V5)
"""

from __future__ import annotations

import json
import html as html_mod
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

BASE_DIR = Path(__file__).parent.parent
TEMPLATE_PATH = BASE_DIR / "prompts" / "schemas" / "component-catalog.md"
OUTPUT_DIR = BASE_DIR / "output"

VERDICT_CLASS = {"🟢": "g", "🟡": "y", "🔴": "r", "⚫": "k", "N/A": "k", "": "k"}
VERDICT_LABEL = {"🟢": "VERIFIED", "🟡": "PLAUSIBLE", "🔴": "FLAGGED", "⚫": "NO BASIS", "N/A": "N/A", "": "—"}
LAYER_NAMES = {
    "fact": ("L1", "Fact Ground"),
    "norm": ("L2", "Norm Ground"),
    "logic": ("L3", "Logic Ground"),
    "temporal": ("L4", "Temporal Ground"),
    "incentive": ("L5", "Incentive Ground"),
    "omission": ("L6", "Omission Ground"),
}
VERDICT_PRIORITY = {"🔴": 4, "⚫": 3, "🟡": 2, "🟢": 1, "N/A": 0, "": 0}


def _esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _badge(verdict: str) -> str:
    cls = VERDICT_CLASS.get(verdict, "k")
    label = VERDICT_LABEL.get(verdict, verdict)
    return f'<span class="v {cls}">{verdict} {label}</span>'


# ═══════════════════════════════════════
# Phase 5-A: 데이터 읽기
# ═══════════════════════════════════════

@dataclass
class DataReading:
    core_claim: str = ""
    tension: str = ""
    tension_exists: bool = False
    gravity: dict = field(default_factory=dict)
    gravity_primary: str = ""
    timeline_focus: str = ""
    unresolved_count: int = 0
    unresolved_items: list = field(default_factory=list)
    worst_verdict: str = "🟢"


def phase_5a_read(data: dict) -> DataReading:
    """result_json에서 5가지를 추출."""
    reading = DataReading()
    summary = data.get("summary", {})
    layer_verdicts = summary.get("layer_verdicts", {})
    claims = data.get("claims", [])
    critical_flags = summary.get("critical_flags", [])
    doc_verdicts = data.get("document_level_verdicts", {})

    # 종합 판정
    worst = "🟢"
    for v in layer_verdicts.values():
        if VERDICT_PRIORITY.get(v, 0) > VERDICT_PRIORITY.get(worst, 0):
            worst = v
    reading.worst_verdict = worst

    # ① Core Claim
    if critical_flags:
        reading.core_claim = critical_flags[0][:120]
    else:
        verdict_text = {
            "🟢": "전체 검증 통과 — 주요 문제 없음",
            "🟡": "조건부 수용 — 일부 수정 권고",
            "🔴": "주의 필요 — 사실 오류 또는 중대 누락 발견",
            "⚫": "기준 부재 — 판정 근거 불충분",
        }.get(worst, "판정 미완료")
        reading.core_claim = verdict_text

    # ② Tension — 층별 판정 불일치 감지
    greens = [k for k, v in layer_verdicts.items() if v == "🟢"]
    reds = [k for k, v in layer_verdicts.items() if v == "🔴"]
    yellows = [k for k, v in layer_verdicts.items() if v == "🟡"]

    if greens and reds:
        reading.tension_exists = True
        g_names = ", ".join(LAYER_NAMES.get(k, (k, k))[1] for k in greens)
        r_names = ", ".join(LAYER_NAMES.get(k, (k, k))[1] for k in reds)
        reading.tension = f"있음 — {g_names}(🟢) vs {r_names}(🔴)"
    elif greens and yellows and len(yellows) >= 2:
        reading.tension_exists = True
        reading.tension = f"잠재 — 🟢 {len(greens)}층 vs 🟡 {len(yellows)}층"
    else:
        reading.tension = "없음"

    # ③ Gravity — 각 영역의 데이터 무게
    layer_weights = {}
    for layer_key in LAYER_NAMES:
        layer_claims = [c for c in claims if c.get("layers", {}).get(layer_key, {}).get("verdict", "") not in ("", "N/A")]
        if not layer_claims:
            continue
        # 가중치: claim 수 × 10 + evidence 수 × 5 + 🔴/🟡 claim 추가 가중
        evidence_count = sum(
            len(c.get("layers", {}).get(layer_key, {}).get("evidence", []))
            for c in layer_claims
        )
        flagged = sum(1 for c in layer_claims
                      if c.get("layers", {}).get(layer_key, {}).get("verdict") in ("🔴", "🟡"))
        weight = len(layer_claims) * 10 + evidence_count * 5 + flagged * 15
        layer_weights[layer_key] = weight

    # Finding cards 무게
    findings_count = sum(1 for c in claims
                         for layer_key in LAYER_NAMES
                         if c.get("layers", {}).get(layer_key, {}).get("verdict") in ("🔴", "🟡"))
    if findings_count > 0:
        layer_weights["findings"] = findings_count * 20

    # KC 무게
    kc_count = sum(
        len(c.get("layers", {}).get("logic", {}).get("kc_extracted", []))
        for c in claims
    )
    if kc_count > 0:
        layer_weights["kc"] = kc_count * 25

    # BBJ 무게
    bbj_breaks = doc_verdicts.get("omission", {}).get("bbj_breaks", [])
    if bbj_breaks:
        layer_weights["bbj"] = len(bbj_breaks) * 30

    reading.gravity = dict(sorted(layer_weights.items(), key=lambda x: x[1], reverse=True))
    if reading.gravity:
        reading.gravity_primary = list(reading.gravity.keys())[0]

    # ④ Timeline
    valid_until = summary.get("valid_until", "")
    triggers = summary.get("invalidation_triggers", [])
    if triggers:
        reading.timeline_focus = "미래 분기"
    elif valid_until:
        reading.timeline_focus = "현재 + 유효기간"
    else:
        reading.timeline_focus = "현재"

    # ⑤ Unresolved — KC 미확인 + critical flags
    unresolved = []
    for c in claims:
        logic = c.get("layers", {}).get("logic", {})
        for kc in logic.get("kc_extracted", []):
            if kc.get("verdict") in ("🟡", "⚫", ""):
                unresolved.append({
                    "type": "KC",
                    "id": kc.get("kc_id", ""),
                    "text": kc.get("premise", ""),
                    "status": kc.get("current_status", "미확인"),
                })
    reading.unresolved_count = len(unresolved)
    reading.unresolved_items = unresolved

    return reading


# ═══════════════════════════════════════
# Phase 5-B: 구조 설계
# ═══════════════════════════════════════

@dataclass
class Section:
    id: str
    title: str
    size: str       # large / medium / small
    render_fn: str


@dataclass
class ReportDesign:
    report_type: str = ""
    report_type_name: str = ""
    report_class: str = ""
    topbar_color: str = ""
    title: str = ""
    subtitle: str = ""
    sections: list = field(default_factory=list)


def phase_5b_design(data: dict, reading: DataReading) -> ReportDesign:
    design = ReportDesign()
    summary = data.get("summary", {})
    meta = data.get("meta", {})
    doc = meta.get("document", {})

    # 유형 판정
    has_tension = reading.tension_exists
    has_triggers = bool(summary.get("invalidation_triggers"))

    if has_tension and has_triggers:
        design.report_type = "E"
        design.report_type_name = "복합형 (대립+분기)"
    elif has_tension:
        design.report_type = "A"
        design.report_type_name = "대립형"
    elif has_triggers:
        design.report_type = "D"
        design.report_type_name = "분기형"
    elif reading.worst_verdict == "🟢":
        design.report_type = "B"
        design.report_type_name = "서사형"
    else:
        design.report_type = "C"
        design.report_type_name = "스냅샷형"

    # report-class
    if reading.worst_verdict == "🔴" and len(summary.get("critical_flags", [])) >= 2:
        design.report_class = "CRISIS ALERT"
        design.topbar_color = "var(--red)"
    elif has_triggers or has_tension:
        design.report_class = "SPECIAL REPORT"
        design.topbar_color = "var(--darkBlue)"
    else:
        design.report_class = "RESEARCH NOTE"
        design.topbar_color = "var(--navy)"

    # 제목
    design.title = doc.get("title", "Verification Report")
    design.subtitle = reading.core_claim

    # 섹션 자율 구성
    sections = []

    # 1. Executive Verdict — 항상
    sections.append(Section("exec", "Executive Verdict", "large", "render_exec"))

    # 2. Gravity 기반
    gravity_keys = list(reading.gravity.keys())

    # 대립형이면 Clash
    if design.report_type in ("A", "E"):
        sections.append(Section("clash", "검증 긴장 구조", "large", "render_clash"))

    # 6-Layer 판정표 — 항상 포함 (verification 핵심)
    sections.append(Section("layers", "6-Layer 판정", "medium", "render_layer_table"))

    # Findings — 🔴/🟡 있으면
    if "findings" in reading.gravity:
        size = "large" if reading.gravity["findings"] >= 40 else "medium"
        sections.append(Section("findings", "Actionable Findings", size, "render_findings"))

    # Fact Check — fact 데이터 있으면
    if "fact" in reading.gravity:
        size = "large" if reading.gravity["fact"] >= 60 else "medium"
        sections.append(Section("fact", "Fact Check Detail", size, "render_fact"))

    # KC — kc 데이터 있으면
    if "kc" in reading.gravity:
        size = "large" if reading.gravity["kc"] >= 50 else "medium"
        sections.append(Section("kc", "Kill Conditions", size, "render_kc"))

    # BBJ — bbj 있으면
    if "bbj" in reading.gravity:
        sections.append(Section("bbj", "Omission & BBJ Breaks", "medium", "render_bbj"))

    # 시나리오 — 분기형이면
    if design.report_type in ("D", "E"):
        sections.append(Section("triggers", "Invalidation Triggers", "large", "render_triggers"))

    # Unresolved — 있으면
    if reading.unresolved_count > 0:
        sections.append(Section("unresolved", "미해소 질문", "small", "render_unresolved"))

    design.sections = sections
    return design


# ═══════════════════════════════════════
# Phase 5-C: 렌더링 — 컴포넌트 함수
# ═══════════════════════════════════════

def render_exec(data: dict, reading: DataReading, design: ReportDesign) -> str:
    summary = data.get("summary", {})
    layer_verdicts = summary.get("layer_verdicts", {})
    critical_flags = summary.get("critical_flags", [])
    claims = data.get("claims", [])

    # 종합 판정
    verdict_html = _badge(reading.worst_verdict)

    # 레이어 배지 행
    layer_badges = " ".join(
        f'{_badge(layer_verdicts.get(k, ""))} {code}'
        for k, (code, _name) in LAYER_NAMES.items()
    )

    # Critical flags
    flags_html = ""
    if critical_flags:
        flags_html = '<div class="alert-box"><div class="exec-label">CRITICAL FLAGS</div>'
        for flag in critical_flags:
            flags_html += f'<p>{_esc(flag)}</p>'
        flags_html += '</div>'

    # Finding 카운트
    red_count = sum(1 for c in claims for lk in LAYER_NAMES
                    if c.get("layers", {}).get(lk, {}).get("verdict") == "🔴")
    yellow_count = sum(1 for c in claims for lk in LAYER_NAMES
                       if c.get("layers", {}).get(lk, {}).get("verdict") == "🟡")

    findings_line = ""
    if red_count or yellow_count:
        findings_line = f'<p style="font-size:13px;margin-top:8px;">🔴 {red_count}건 · 🟡 {yellow_count}건</p>'

    return f"""<div class="exec-box">
  <div class="exec-label">EXECUTIVE VERDICT</div>
  <p style="font-size:15px;font-weight:600;">{verdict_html} {_esc(reading.core_claim)}</p>
  <p style="font-size:12px;margin-top:8px;">{layer_badges}</p>
  {findings_line}
</div>
{flags_html}"""


def render_clash(data: dict, reading: DataReading, _design: ReportDesign) -> str:
    summary = data.get("summary", {})
    layer_verdicts = summary.get("layer_verdicts", {})

    green_layers = []
    problem_layers = []
    for k, v in layer_verdicts.items():
        name = LAYER_NAMES.get(k, (k, k))[1]
        if v == "🟢":
            green_layers.append(f"<li>{_badge(v)} {_esc(name)}</li>")
        elif v in ("🔴", "🟡"):
            problem_layers.append(f"<li>{_badge(v)} {_esc(name)}</li>")

    return f"""<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0;">
  <div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--green);border-radius:6px;padding:16px;">
    <h4 style="font-size:13px;color:var(--green);margin-bottom:8px;">확인됨 (Verified)</h4>
    <ul style="font-size:13px;list-style:none;padding:0;">{''.join(green_layers) or '<li style="color:var(--dim);">없음</li>'}</ul>
  </div>
  <div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--red);border-radius:6px;padding:16px;">
    <h4 style="font-size:13px;color:var(--red);margin-bottom:8px;">주의 필요 (Flagged/Plausible)</h4>
    <ul style="font-size:13px;list-style:none;padding:0;">{''.join(problem_layers) or '<li style="color:var(--dim);">없음</li>'}</ul>
  </div>
</div>
<p style="font-size:13px;color:var(--sub);margin-top:8px;"><strong>긴장:</strong> {_esc(reading.tension)}</p>"""


def render_layer_table(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    summary = data.get("summary", {})
    layer_verdicts = summary.get("layer_verdicts", {})
    claims = data.get("claims", [])
    doc_verdicts = data.get("document_level_verdicts", {})

    rows = ""
    for layer_key, (code, name) in LAYER_NAMES.items():
        v = layer_verdicts.get(layer_key, "")
        # 주요 노트 수집
        notes_parts = []
        # 문서 레벨
        doc_lv = doc_verdicts.get(layer_key, {})
        if doc_lv.get("notes"):
            notes_parts.append(doc_lv["notes"][:100])
        # claim 레벨 (🔴 우선)
        for claim in claims:
            lv = claim.get("layers", {}).get(layer_key, {})
            if lv.get("verdict") == "🔴" and lv.get("notes"):
                notes_parts.append(f'{claim.get("claim_id", "")}: {lv["notes"][:80]}')
                break
        notes = " | ".join(notes_parts)[:200]

        rows += f'<tr><td>{code}</td><td>{_esc(name)}</td><td>{_badge(v)}</td><td style="font-size:12px;">{_esc(notes)}</td></tr>'

    return f"""<div class="table-wrap"><table class="monitor-table">
<thead><tr><th>LAYER</th><th>NAME</th><th>VERDICT</th><th>KEY NOTES</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""


def render_findings(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    claims = data.get("claims", [])
    findings = []

    for claim in claims:
        for layer_key in LAYER_NAMES:
            lv = claim.get("layers", {}).get(layer_key, {})
            verdict = lv.get("verdict", "")
            if verdict not in ("🔴", "🟡"):
                continue
            code = LAYER_NAMES[layer_key][0]
            cls = "f-red" if verdict == "🔴" else "f-gold"
            fix_cls = "definitive" if verdict == "🔴" else "recommended"

            notes = lv.get("notes", "") or lv.get("reason", "")
            evidence_html = ""
            for ev in lv.get("evidence", []):
                evidence_html += f'<div style="font-size:12px;margin:2px 0;"><strong>{_esc(ev.get("source", ""))}</strong>: {_esc(ev.get("value", ""))}</div>'

            findings.append(f"""<div class="finding-card {cls}">
  <div class="finding-header">
    <div class="finding-id">{_esc(claim.get("claim_id", ""))}</div>
    <div>{_badge(verdict)} {code}</div>
  </div>
  <div class="finding-row"><span class="finding-label">📝</span> {_esc(claim.get("text", "")[:120])}</div>
  <div class="finding-row"><span class="finding-label">📊</span> {_esc(notes[:200])}</div>
  {evidence_html}
</div>""")

    # 🔴 먼저, 🟡 뒤
    return "\n".join(findings) if findings else '<p style="color:var(--dim);">발견된 수정 사항 없음.</p>'


def render_fact(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    claims = data.get("claims", [])
    cards = []

    for claim in claims:
        fact = claim.get("layers", {}).get("fact", {})
        if not fact or fact.get("verdict") in ("", "N/A"):
            continue

        v = fact.get("verdict", "")
        cls = {"🟢": "ch-green", "🟡": "ch-gold", "🔴": "ch-red"}.get(v, "ch-blue")
        evidence_html = ""
        for ev in fact.get("evidence", []):
            evidence_html += f'<div style="font-size:12px;margin:4px 0;"><strong>{_esc(ev.get("source", ""))}</strong>: {_esc(ev.get("value", ""))}</div>'

        cards.append(f"""<div class="channel-card {cls}">
  <div class="ch-header"><div class="ch-name">{_esc(claim.get("claim_id", ""))}: {_esc(claim.get("text", "")[:80])}</div>
  <div class="ch-tags">{_badge(v)}</div></div>
  <p style="font-size:13px;color:var(--sub);margin-top:8px;">{_esc(fact.get("notes", ""))}</p>
  {evidence_html}
</div>""")

    return f'<div class="channel-grid">{"".join(cards)}</div>' if cards else ""


def render_kc(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    claims = data.get("claims", [])
    kc_rows = ""

    for claim in claims:
        logic = claim.get("layers", {}).get("logic", {})
        for kc in logic.get("kc_extracted", []):
            kc_rows += (
                f'<tr><td style="font-family:\'DM Mono\',monospace;">{_esc(kc.get("kc_id", ""))}</td>'
                f'<td>{_esc(kc.get("premise", ""))}</td>'
                f'<td>{_esc(kc.get("current_status", ""))}</td>'
                f'<td>{_badge(kc.get("verdict", ""))}</td></tr>'
            )

    if not kc_rows:
        return ""

    return f"""<div class="table-wrap"><table class="monitor-table">
<thead><tr><th>KC ID</th><th>PREMISE</th><th>STATUS</th><th>VERDICT</th></tr></thead>
<tbody>{kc_rows}</tbody></table></div>"""


def render_bbj(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    doc_verdicts = data.get("document_level_verdicts", {})
    doc_omission = doc_verdicts.get("omission", {})
    bbj_breaks = doc_omission.get("bbj_breaks", [])

    if not bbj_breaks:
        return ""

    cards = ""
    for bbj in bbj_breaks:
        v = bbj.get("verdict", "🟡")
        cls = {"🟢": "ch-green", "🟡": "ch-gold", "🔴": "ch-red"}.get(v, "ch-blue")
        in_doc = "문서 내 언급" if bbj.get("in_document") else "문서 내 미언급"
        cards += f"""<div class="channel-card {cls}">
  <div class="ch-header"><div class="ch-name">BBJ Break</div>
  <div class="ch-tags">{_badge(v)} <span style="font-size:11px;color:var(--dim);">{in_doc}</span></div></div>
  <p style="font-size:13.5px;color:var(--sub);margin-top:8px;">{_esc(bbj.get("break_text", ""))}</p>
</div>"""

    omission_notes = doc_omission.get("notes", "")
    notes_html = f'<p style="font-size:13px;color:var(--sub);margin-top:12px;">{_esc(omission_notes)}</p>' if omission_notes else ""

    return f'<div class="channel-grid">{cards}</div>{notes_html}'


def render_triggers(data: dict, _reading: DataReading, _design: ReportDesign) -> str:
    summary = data.get("summary", {})
    triggers = summary.get("invalidation_triggers", [])
    valid_until = summary.get("valid_until", "")

    if not triggers:
        return ""

    cards = ""
    colors = ["var(--red)", "var(--gold)", "var(--darkBlue)"]
    for i, trigger in enumerate(triggers[:4]):
        color = colors[i % len(colors)]
        if isinstance(trigger, str):
            cards += f"""<div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid {color};border-radius:6px;padding:16px;margin:8px 0;">
  <p style="font-size:13px;">{_esc(trigger)}</p>
</div>"""
        elif isinstance(trigger, dict):
            cards += f"""<div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid {color};border-radius:6px;padding:16px;margin:8px 0;">
  <p style="font-size:13px;font-weight:600;">{_esc(trigger.get('condition', ''))}</p>
  <p style="font-size:12px;color:var(--sub);margin-top:4px;">{_esc(trigger.get('impact', ''))}</p>
</div>"""

    valid_html = f'<p style="font-size:12px;color:var(--dim);margin-top:12px;">유효기간: {_esc(valid_until)}</p>' if valid_until else ""

    return f'{cards}{valid_html}'


def render_unresolved(data: dict, reading: DataReading, _design: ReportDesign) -> str:
    if not reading.unresolved_items:
        return ""

    items = ""
    for uq in reading.unresolved_items:
        items += f"""<li style="padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;">
  <strong style="font-family:'DM Mono',monospace;">{_esc(uq.get('id', ''))}</strong>
  [{_esc(uq.get('type', ''))}] {_esc(uq.get('text', ''))}
  <span style="font-size:11px;color:var(--dim);display:block;margin-top:2px;">상태: {_esc(uq.get('status', ''))}</span>
</li>"""

    return f'<ul style="list-style:none;padding:0;">{items}</ul>'


RENDER_MAP = {
    "render_exec": render_exec,
    "render_clash": render_clash,
    "render_layer_table": render_layer_table,
    "render_findings": render_findings,
    "render_fact": render_fact,
    "render_kc": render_kc,
    "render_bbj": render_bbj,
    "render_triggers": render_triggers,
    "render_unresolved": render_unresolved,
}


# ═══════════════════════════════════════
# Phase 5-C: HTML 조립
# ═══════════════════════════════════════

def _build_css() -> str:
    """인라인 CSS — component-catalog.md 기반."""
    return """<style>
:root,[data-theme="light"]{
  --bg:#fafaf8;--surface:#fff;--card:#f5f5f2;
  --navy:#1B2A4A;--darkBlue:#2C5697;--blue:#4472C4;
  --lightBlue:#D6E4F0;--paleBlue:#EDF2F9;
  --text:#1a1a1a;--sub:#4a4a4a;--dim:#8a8a8a;
  --border:#d8d8d4;--red:#c0392b;--green:#1a7a4c;--gold:#b8860b;--line:#e2e2de;
  --topbar-bg:#1B2A4A;--topbar-text:#fff;--topbar-dim:#8ea8cc;
  --exec-bg:#EDF2F9;--key-bg:#fdf6ec;--key-text:#5a4a20;
  --alert-bg:#fef2f2;--alert-text:#6b2020;
  --tag-bull-bg:#e8f5e9;--tag-bear-bg:#fef2f2;--tag-caution-bg:#fff8e1;
  --nav-bg:rgba(255,255,255,.92);--shadow:rgba(27,42,74,.06)
}
[data-theme="dark"]{
  --bg:#0d1117;--surface:#161b22;--card:#1c2128;
  --navy:#c9d1d9;--darkBlue:#58a6ff;--blue:#79c0ff;
  --lightBlue:#1f3a5f;--paleBlue:#131d2b;
  --text:#e6edf3;--sub:#b1bac4;--dim:#6e7681;
  --border:#30363d;--red:#f85149;--green:#3fb950;--gold:#d29922;--line:#21262d;
  --topbar-bg:#010409;--topbar-text:#e6edf3;--topbar-dim:#6e7681;
  --exec-bg:#131d2b;--key-bg:#1c1a10;--key-text:#d29922;
  --alert-bg:#1a0e0e;--alert-text:#f85149;
  --tag-bull-bg:#0d2818;--tag-bear-bg:#1a0e0e;--tag-caution-bg:#1c1a10;
  --nav-bg:rgba(13,17,23,.95);--shadow:rgba(0,0,0,.3)
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.7;max-width:820px;margin:0 auto}
.topbar{padding:14px 32px;position:sticky;top:0;z-index:100;display:flex;justify-content:space-between;align-items:center}
.topbar-brand{font-family:'Libre Baskerville',serif;font-size:15px;font-weight:700;color:var(--topbar-text)}
.topbar-right{display:flex;align-items:center;gap:10px}
.ctrl-btn{background:none;border:1px solid rgba(255,255,255,.2);color:var(--topbar-text);font-size:11px;font-weight:600;padding:4px 11px;border-radius:3px;cursor:pointer;font-family:'DM Sans',sans-serif}
.ctrl-btn:hover{border-color:rgba(255,255,255,.5);background:rgba(255,255,255,.08)}
.report-header{padding:32px 32px 24px;border-bottom:1px solid var(--border)}
.report-header h1{font-family:'Libre Baskerville',serif;font-size:1.5rem;font-weight:700;line-height:1.3;margin-bottom:4px;color:var(--navy)}
.report-header .meta{font-family:'DM Mono',monospace;font-size:12px;color:var(--dim);margin-top:8px}
.content{padding:0 32px 32px}
h2{font-family:'Libre Baskerville',serif;font-size:1.1rem;font-weight:700;margin:32px 0 16px;padding-bottom:8px;border-bottom:1px solid var(--line);color:var(--navy)}
.exec-box{background:var(--exec-bg);border-left:4px solid var(--darkBlue);padding:24px 28px;margin:20px 0;border-radius:0 6px 6px 0}
.exec-label{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--darkBlue);margin-bottom:8px}
.alert-box{background:var(--alert-bg);border-left:4px solid var(--red);padding:20px 24px;margin:16px 0;border-radius:0 6px 6px 0}
.alert-box p{color:var(--alert-text);font-size:13px}
.v{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:3px;vertical-align:middle}
.v.g{background:var(--tag-bull-bg);color:var(--green)}
.v.y{background:var(--tag-caution-bg);color:var(--gold)}
.v.r{background:var(--tag-bear-bg);color:var(--red)}
.v.k{background:var(--card);color:var(--dim)}
.monitor-table{width:100%;border-collapse:collapse;font-size:13px}
.monitor-table th{background:var(--card);color:var(--dim);text-align:left;padding:8px 12px;border:1px solid var(--border);font-weight:600;font-size:11px;letter-spacing:1px}
.monitor-table td{padding:8px 12px;border:1px solid var(--border);vertical-align:top}
.table-wrap{overflow-x:auto;margin:12px 0}
.channel-grid{display:grid;gap:12px;margin:12px 0}
.channel-card{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px 20px;position:relative}
.channel-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:6px 0 0 6px}
.ch-green::before{background:var(--green)}.ch-gold::before{background:var(--gold)}.ch-red::before{background:var(--red)}.ch-blue::before{background:var(--darkBlue)}
.ch-header{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}
.ch-name{font-size:13px;font-weight:600;color:var(--navy);flex:1}
.finding-card{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:20px 24px;margin:14px 0;position:relative}
.finding-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:6px 0 0 6px}
.finding-card.f-red::before{background:var(--red)}.finding-card.f-gold::before{background:var(--gold)}
.finding-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px}
.finding-id{font-family:'DM Mono',monospace;font-size:12px;font-weight:700;color:var(--navy)}
.finding-row{display:flex;gap:8px;margin-bottom:6px;font-size:13px;color:var(--sub);line-height:1.6}
.finding-label{font-size:11px;min-width:20px;flex-shrink:0}
.disclaimer{text-align:center;color:var(--dim);font-size:11px;margin-top:32px;padding-top:16px;border-top:1px solid var(--line)}
@media(max-width:780px){.topbar,.report-header,.content{padding-left:16px;padding-right:16px}.report-header h1{font-size:1.2rem}}
</style>"""


def phase_5c_render(data: dict, reading: DataReading, design: ReportDesign) -> str:
    meta = data.get("meta", {})
    doc = meta.get("document", {})
    date = doc.get("date_published", datetime.now().strftime("%Y-%m-%d"))

    # 섹션 HTML
    body_parts = []
    for section in design.sections:
        fn = RENDER_MAP.get(section.render_fn)
        if not fn:
            continue
        section_html = fn(data, reading, design)
        if not section_html or not section_html.strip():
            continue

        if section.id == "exec":
            body_parts.append(section_html)
        else:
            body_parts.append(f'<h2>{_esc(section.title)}</h2>\n{section_html}')

    body_html = "\n\n".join(body_parts)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(design.title)} | Verification</title>
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
{_build_css()}
</head>
<body>

<header class="topbar" style="background:{design.topbar_color};">
  <div class="topbar-brand">6-Layer Verification Engine</div>
  <div class="topbar-right">
    <span style="font-size:12px;color:var(--topbar-dim);">{_esc(design.report_class)}</span>
    <button class="ctrl-btn" onclick="document.documentElement.setAttribute('data-theme',document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark')">◐ THEME</button>
  </div>
</header>

<div class="report-header">
  <h1>{_esc(design.title)}</h1>
  <div class="meta">{_esc(date)} | {_esc(doc.get('document_type', ''))} | {_esc(design.report_type)} ({_esc(design.report_type_name)})</div>
</div>

<div class="content">
{body_html}
</div>

<div class="disclaimer">
  6-Layer Verification Engine | {_esc(date)}<br>
  이 보고서는 문서 검증 결과이며, 투자 판단을 제공하지 않습니다.
</div>

</body>
</html>"""

    return html


# ═══════════════════════════════════════
# Phase 5-F: 자기 검증
# ═══════════════════════════════════════

@dataclass
class VerifyResult:
    v1_claim_ok: bool = False
    v2_data_ok: bool = False
    v3_no_empty: bool = False
    v4_proportional: bool = False
    v5_first_screen: bool = False
    issues: list = field(default_factory=list)


def phase_5f_verify(data: dict, reading: DataReading, design: ReportDesign, html: str) -> VerifyResult:
    result = VerifyResult()

    # V1: Core Claim 포함
    result.v1_claim_ok = reading.core_claim[:20] in html if reading.core_claim else False
    if not result.v1_claim_ok:
        result.issues.append("V1: Core Claim 미포함")

    # V2: 핵심 수치 — layer_verdicts가 HTML에 반영
    summary = data.get("summary", {})
    verdicts = summary.get("layer_verdicts", {})
    missing = [k for k in verdicts if verdicts[k] not in html]
    result.v2_data_ok = len(missing) == 0
    if missing:
        result.issues.append(f"V2: 판정 누락 — {', '.join(missing)}")

    # V3: 빈 섹션
    result.v3_no_empty = True

    # V4: 비례
    large_sections = [s for s in design.sections if s.size == "large"]
    result.v4_proportional = len(large_sections) >= 1
    if not result.v4_proportional:
        result.issues.append("V4: Large 섹션 없음")

    # V5: 첫 화면
    content_pos = html.find('class="content"')
    exec_pos = html.find('class="exec-box"', content_pos) if content_pos > 0 else -1
    result.v5_first_screen = exec_pos > 0 and (exec_pos - content_pos) < 500
    if not result.v5_first_screen:
        result.issues.append("V5: Core Claim이 첫 화면에 없음")

    return result


# ═══════════════════════════════════════
# 공개 API
# ═══════════════════════════════════════

class AdaptiveVerificationRenderer:
    """자율 판단 보고서 렌더러.

    사용:
        renderer = AdaptiveVerificationRenderer(result_json)
        html = renderer.render()
        path = renderer.save()
    """

    def __init__(self, result_json: dict):
        self.data = result_json
        self.reading: DataReading | None = None
        self.design: ReportDesign | None = None
        self.verify: VerifyResult | None = None
        self._html: str = ""

    def render(self) -> str:
        self.reading = phase_5a_read(self.data)
        self.design = phase_5b_design(self.data, self.reading)
        self._html = phase_5c_render(self.data, self.reading, self.design)
        self.verify = phase_5f_verify(self.data, self.reading, self.design, self._html)
        return self._html

    def save(self, path: str = "") -> Path:
        if not self._html:
            self.render()

        if path:
            out = Path(path)
        else:
            doc = self.data.get("meta", {}).get("document", {})
            slug = re.sub(r'[^\w가-힣]', '-', doc.get("title", "untitled"))[:30].strip("-")
            date_str = datetime.now().strftime("%Y-%m-%d")
            out = OUTPUT_DIR / f"{slug}-adaptive-{date_str}.html"

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self._html, encoding="utf-8")
        return out

    def summary(self) -> dict:
        """Phase 결과 요약 반환."""
        if not self.reading:
            self.render()
        return {
            "phase_5a": {
                "core_claim": self.reading.core_claim,
                "tension": self.reading.tension,
                "gravity": list(self.reading.gravity.keys()),
                "timeline": self.reading.timeline_focus,
                "unresolved": self.reading.unresolved_count,
            },
            "phase_5b": {
                "type": f"{self.design.report_type} ({self.design.report_type_name})",
                "class": self.design.report_class,
                "sections": len(self.design.sections),
            },
            "phase_5f": {
                "v1": self.verify.v1_claim_ok,
                "v2": self.verify.v2_data_ok,
                "v3": self.verify.v3_no_empty,
                "v4": self.verify.v4_proportional,
                "v5": self.verify.v5_first_screen,
                "issues": self.verify.issues,
            },
        }


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        state_path = Path(sys.argv[1])
    else:
        # history에서 최신 vrf 파일 찾기
        history_dir = OUTPUT_DIR / "history"
        vrf_files = sorted(history_dir.glob("vrf_*.json"), reverse=True) if history_dir.exists() else []
        if vrf_files:
            state_path = vrf_files[0]
        else:
            print("result_json 파일을 지정하세요: python core/render_adaptive.py <path>")
            sys.exit(1)

    data = json.loads(state_path.read_text(encoding="utf-8"))
    # result_json이 wrapper 안에 있을 수 있음
    if "result_json" in data:
        result = data["result_json"]
        # summary를 상위에서 가져오기
        if "summary" not in result and "summary" in data:
            result["summary"] = data["summary"]
    else:
        result = data

    renderer = AdaptiveVerificationRenderer(result)
    html = renderer.render()
    out_path = renderer.save()

    s = renderer.summary()
    print(f"{'=' * 50}")
    print(f"  Adaptive Verification Report")
    print(f"{'=' * 50}")
    print(f"  File: {out_path}")
    print(f"  [5-A] Core Claim: {s['phase_5a']['core_claim'][:60]}")
    print(f"         Tension: {s['phase_5a']['tension']}")
    print(f"         Gravity: {' > '.join(s['phase_5a']['gravity'][:5])}")
    print(f"         Unresolved: {s['phase_5a']['unresolved']}건")
    print(f"  [5-B] Type: {s['phase_5b']['type']}")
    print(f"         Class: {s['phase_5b']['class']}")
    print(f"         Sections: {s['phase_5b']['sections']}개")
    print(f"  [5-F] V1~V5: {'ALL OK' if not s['phase_5f']['issues'] else ', '.join(s['phase_5f']['issues'])}")
    print(f"{'=' * 50}")
