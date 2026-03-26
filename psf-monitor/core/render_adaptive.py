"""
psf-monitor 자율 판단 보고서 생성기

state.json을 읽고 4단계 파이프라인으로 적응형 HTML 보고서를 생성한다.
  Phase 1: Extract Five (core_claim, tension, gravity, timeline, unresolved)
  Phase 2: Design Report (유형 A~E, 분류, 섹션 구성)
  Phase 3: Render HTML (컴포넌트 조합)
  Phase 4: Verify (V1~V5 셀프 감사)

Usage:
  python core/render_adaptive.py                    # state.json → HTML
  python core/render_adaptive.py --projection       # projection.json → HTML
  python core/render_adaptive.py --file X.json      # 특정 파일 → HTML
  python core/render_adaptive.py --design-only      # Phase 1-2만 (설계안 출력)
"""

import json
import sys
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"
PROJECTION_FILE = BASE_DIR / "projection.json"
TEMPLATE_FILE = BASE_DIR / "assets" / "template-base.html"
REPORTS_DIR = BASE_DIR / "reports"


# ──────────────────────────────────────────────
# Phase 1: Extract Five
# ──────────────────────────────────────────────

def extract_five(state: dict) -> dict:
    """state.json에서 5가지 핵심 요소를 추출한다.

    Returns:
        core_claim  - 국면 + 1순위 관측 요약
        tension     - 괴리(divergences) 존재 여부 및 상세
        gravity     - severity별 관측 분류
        timeline    - 현재/미래분기 판단
        unresolved  - 미해소 질문 + 미분류 신호 수
    """
    regime = state.get("regime", "미확인")
    obs = state.get("observations", [])
    top_signal = obs[0]["signal"] if obs else "관측 없음"
    core_claim = f"{regime} — {top_signal}"

    # Tension: divergences + conflicting links
    divergences = state.get("divergences", [])
    links = state.get("links", {})
    active_links = []
    for k, v in links.items():
        if isinstance(v, dict):
            status = str(v.get("status", "")).strip().lower()
            if (status.startswith("active") or "활성" in str(v.get("status", ""))
                    or "approach" in status or "접근" in status):
                active_links.append(k)

    tension = None
    if divergences:
        tension = {
            "exists": True,
            "count": len(divergences),
            "details": [d.get("description", "") for d in divergences],
        }

    # Gravity: severity 분포
    gravity = {"critical": [], "high": [], "medium": [], "low": []}
    for o in obs:
        sev = o.get("severity", "medium")
        bucket = gravity.get(sev, gravity["medium"])
        bucket.append(o.get("signal", ""))

    # Timeline: open questions가 있으면 미래 분기 포함
    questions = state.get("next_questions", [])
    open_q = [q for q in questions if q.get("status") == "open"]
    timeline = "현재 상태 + 미래 분기" if open_q else "현재 상태"

    # Unresolved
    unclassified = state.get("unclassified", [])
    unresolved = {
        "questions": len(open_q),
        "unclassified": len(unclassified),
        "total": len(open_q) + len(unclassified),
    }

    return {
        "core_claim": core_claim,
        "tension": tension,
        "gravity": gravity,
        "timeline": timeline,
        "unresolved": unresolved,
        "active_links": active_links,
    }


# ──────────────────────────────────────────────
# Phase 2: Design Report
# ──────────────────────────────────────────────

def design_report(five: dict, state: dict) -> dict:
    """보고서 유형(A~E), 분류, 섹션 구성을 결정한다."""
    tension = five["tension"]
    gravity = five["gravity"]
    has_scenarios = five["timeline"] == "현재 상태 + 미래 분기"

    # ── 유형 판별 ──
    if tension and tension["exists"] and has_scenarios:
        report_type, type_name = "E", "복합형 (대립 + 분기)"
    elif tension and tension["exists"]:
        report_type, type_name = "A", "대립형"
    elif has_scenarios:
        report_type, type_name = "D", "분기형"
    else:
        report_type, type_name = "C", "스냅샷형"

    # ── 분류 판별 ──
    regime = state.get("regime", "")
    links = state.get("links", {})
    l8_active = False
    for k, v in links.items():
        if isinstance(v, dict) and "L8" in k:
            status_str = str(v.get("status", "")).lower().strip()
            # "inactive"는 제외. "active"로 시작하거나 "활성"을 포함해야 함.
            if (status_str.startswith("active") or "활성" in str(v.get("status", ""))):
                l8_active = True

    if "🔴" in regime or l8_active:
        report_class, class_color = "CRISIS ALERT", "red"
    elif has_scenarios or (tension and tension["exists"]):
        report_class, class_color = "SPECIAL REPORT", "blue"
    else:
        report_class, class_color = "RESEARCH NOTE", "navy"

    # ── 섹션 구성 (gravity 기반) ──
    sections = []

    # Always: Executive Verdict
    sections.append({"id": "exec", "name": "Executive Verdict", "size": "large", "component": "exec-box"})

    # Always: Regime Dashboard
    sections.append({"id": "dashboard", "name": "국면 대시보드", "size": "large", "component": "regime-dashboard"})

    # Tension → Clash section
    if tension and tension["exists"]:
        sections.append({"id": "clash", "name": "긴장 구조", "size": "large", "component": "divergence-card"})

    # Critical observations → large
    if gravity["critical"]:
        sections.append({"id": "critical", "name": "핵심 관측", "size": "large", "component": "observation-card"})

    # High observations → medium→large
    if gravity["high"]:
        sections.append({"id": "high", "name": "주요 변화", "size": "medium", "component": "observation-card"})

    # Links
    if five["active_links"]:
        sections.append({"id": "links", "name": "Link 상태", "size": "medium", "component": "link-status"})

    # Axis status
    sections.append({"id": "axis", "name": "축 상태", "size": "medium", "component": "axis-status"})

    # Medium/low observations → small table
    if gravity["medium"]:
        sections.append({"id": "medium", "name": "보조 관측", "size": "small", "component": "monitor-table"})

    # Scenarios
    if has_scenarios:
        sections.append({"id": "scenarios", "name": "감시 + 시나리오", "size": "medium", "component": "scenario-grid"})

    # Unresolved
    if five["unresolved"]["total"] > 0:
        sections.append({"id": "unresolved", "name": "미해소 질문", "size": "small", "component": "open-questions"})

    return {
        "type": report_type,
        "type_name": type_name,
        "report_class": report_class,
        "class_color": class_color,
        "sections": sections,
        "section_count": len(sections),
    }


# ──────────────────────────────────────────────
# Phase 3: Render HTML
# ──────────────────────────────────────────────

def _regime_class(text: str) -> str:
    if "🟢" in text:
        return "regime-green"
    elif "🔴" in text:
        return "regime-red"
    return "regime-yellow"


def _escape(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _axis_color(status: str) -> str:
    """축 상태에 따른 CSS color."""
    if "건재" in status:
        return "var(--green)"
    elif "감속" in status or "가속" in status:
        return "var(--yellow)"
    elif "훼손" in status or "격화" in status:
        return "var(--red)"
    return "var(--text-dim)"


CSS_INLINE = """:root {
  --navy:#0d1117;--dark:#161b22;--border:#30363d;
  --text:#c9d1d9;--text-bright:#f0f6fc;--text-dim:#8b949e;
  --blue:#58a6ff;--green:#4caf50;--yellow:#ffd600;
  --red:#ff5252;--purple:#d2a8ff;--cyan:#80deea;
  --regime-green-bg:#003d00;--regime-green-text:#4caf50;
  --regime-yellow-bg:#4a3800;--regime-yellow-text:#ffd600;
  --regime-red-bg:#3d0000;--regime-red-text:#ff5252;
  --keyword-bg:#2a1a3e;--keyword-text:#ce93d8;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--navy);color:var(--text);font-family:'Noto Sans KR',sans-serif;line-height:1.7}
.container{max-width:780px;margin:0 auto;padding:16px}
.topbar{padding:6px 16px;font-size:.7em;font-weight:700;letter-spacing:2px;text-transform:uppercase;text-align:center}
.topbar.red{background:#5c0000;color:#ff5252}
.topbar.blue{background:#0a2540;color:#58a6ff}
.topbar.navy{background:#0d1117;color:#8b949e;border-bottom:1px solid var(--border)}
.topbar.gold{background:#3a2800;color:#ffd600}
.report-header{padding:20px 16px 12px}
.report-header h1{color:var(--text-bright);font-size:1.3em;margin-bottom:6px}
.report-header .meta{color:var(--text-dim);font-size:.8em}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.badge{padding:4px 12px;border-radius:4px;font-size:.75em;font-weight:600;white-space:nowrap}
.badge.regime-green{background:var(--regime-green-bg);color:var(--regime-green-text)}
.badge.regime-yellow{background:var(--regime-yellow-bg);color:var(--regime-yellow-text)}
.badge.regime-red{background:var(--regime-red-bg);color:var(--regime-red-text)}
.badge.keyword{background:var(--keyword-bg);color:var(--keyword-text)}
.exec-box{background:var(--dark);border-left:4px solid var(--yellow);padding:16px 20px;margin:16px;border-radius:0 8px 8px 0}
.exec-box .claim{color:var(--text-bright);font-size:1.05em;font-weight:500}
.exec-box .sub{color:var(--text-dim);font-size:.82em;margin-top:6px}
.section{margin:12px 16px}
.section-large{margin:16px}
.section-small{margin:8px 16px}
.section-title{color:var(--blue);font-size:.9em;font-weight:700;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.card{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px}
.card.critical{border-left:3px solid var(--red)}
.card.high{border-left:3px solid var(--yellow)}
.card.medium{border-left:3px solid var(--text-dim)}
.card .rank{color:var(--yellow);font-family:'DM Mono',monospace;font-weight:700;margin-right:8px}
.card .signal{color:var(--text-bright);font-weight:500}
.card .detail{color:var(--text-dim);font-size:.82em;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:.82em}
th{background:var(--dark);color:var(--text-dim);padding:8px 12px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:8px 12px;border-bottom:1px solid #1c2028}
.num{font-family:'DM Mono',monospace;color:var(--text-bright)}
.up{color:var(--red)}.down{color:var(--green)}.flat{color:var(--text-dim)}
.link-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.link-card{background:var(--dark);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:.8em}
.link-card.active{border-color:var(--red)}
.link-card.approaching{border-color:var(--yellow)}
.link-card .status{font-weight:600}
.axis-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.axis-card{background:var(--dark);border:1px solid var(--border);border-radius:6px;padding:10px;font-size:.8em;text-align:center}
.axis-card .axis-name{color:var(--text-bright);font-weight:600}
.axis-card .axis-status{margin-top:4px}
.scenario-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.scenario-card{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px}
.scenario-card .prob{font-family:'DM Mono',monospace;font-size:1.1em;color:var(--yellow)}
.scenario-card .name{color:var(--text-bright);font-weight:600;margin-top:4px}
.scenario-card .desc{color:var(--text-dim);font-size:.8em;margin-top:4px}
.divergence{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px}
.divergence .type{color:var(--purple);font-size:.75em;font-weight:600;text-transform:uppercase;letter-spacing:1px}
.divergence .desc{color:var(--text);font-size:.85em;margin-top:4px}
.question-list{list-style:none}
.question-list li{background:var(--dark);border:1px solid var(--border);border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:.82em}
.question-list .deadline{color:var(--yellow);font-family:'DM Mono',monospace;font-size:.8em}
.alert-box{background:var(--regime-red-bg);border:1px solid #5c0000;border-radius:8px;padding:12px 16px;margin-bottom:8px}
.alert-box .alert-title{color:var(--red);font-weight:700;font-size:.85em}
.alert-box .alert-body{color:var(--text);font-size:.82em;margin-top:4px}
.alert-box.warning{background:var(--regime-yellow-bg);border-color:#665200}
.alert-box.warning .alert-title{color:var(--yellow)}
.footer{margin:24px 16px;padding-top:12px;border-top:1px solid var(--border);color:var(--text-dim);font-size:.72em;text-align:center}
.disclaimer{color:#484f58;font-size:.68em;margin-top:8px;font-style:italic}
@media(max-width:600px){.link-grid,.scenario-grid{grid-template-columns:1fr}.axis-grid{grid-template-columns:1fr 1fr}}
@media(max-width:480px){.container{padding:8px}.report-header h1{font-size:1.1em}.exec-box{margin:8px;padding:12px 14px}.section,.section-large,.section-small{margin:8px}}"""


def render_html(design: dict, state: dict, five: dict) -> str:
    """design + state + five로 완전한 HTML을 생성한다."""
    regime = state.get("regime", "미확인")
    macro = state.get("macro_interface", {})
    today = state.get("last_updated", date.today().isoformat())
    regime_cls = _regime_class(regime)

    macro_regime = macro.get("macro_regime", "미확인")
    alignment = macro.get("alignment", "미확인")
    macro_cls = _regime_class(macro_regime)

    parts = []

    # ── Head ──
    parts.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PSF Briefing — {today}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS_INLINE}</style>
</head>
<body>""")

    # ── Topbar ──
    parts.append(f'<div class="topbar {design["class_color"]}">{design["report_class"]}</div>')

    # ── Header ──
    parts.append(f"""<div class="container">
<div class="report-header">
  <h1>PSF Briefing — {today}</h1>
  <div class="meta">{design['type_name']} · {design['section_count']}개 섹션 · 자율 판단</div>
  <div class="badges">
    <span class="badge {regime_cls}">PSF {_escape(regime)}</span>
    <span class="badge {macro_cls}">macro {_escape(macro_regime)}</span>
    <span class="badge keyword">{_escape(alignment)}</span>
  </div>
</div>""")

    # ── Sections ──
    for sec in design["sections"]:
        parts.append(_render_section(sec, state, five))

    # ── Footer ──
    quality = state.get("quality", {})
    mcp_count = quality.get("mcp_count", 0)
    mcp_ratio = quality.get("mcp_ratio", 0)
    parts.append(f"""
<div class="footer">
  MCP {mcp_count}건 · 비율 {mcp_ratio:.0%} · 상세 → state.json
  <div class="disclaimer">이 보고서는 관측 결과입니다. 투자 판단이나 행동 권고가 아닙니다. 모든 수치는 수집 시점 기준이며 실시간이 아닙니다.</div>
</div>
</div></body></html>""")

    return "\n".join(parts)


def _render_section(sec: dict, state: dict, five: dict) -> str:
    """단일 섹션을 렌더링한다."""
    sid = sec["id"]
    name = sec["name"]
    size = sec["size"]
    size_class = f"section-{size}" if size != "medium" else "section"

    html = f'<div class="{size_class}"><div class="section-title">{_escape(name)}</div>'

    if sid == "exec":
        html += _render_exec(state, five)
    elif sid == "dashboard":
        html += _render_dashboard(state)
    elif sid == "clash":
        html += _render_clash(state)
    elif sid in ("critical", "high", "medium"):
        html += _render_observations(state, sid)
    elif sid == "links":
        html += _render_links(state)
    elif sid == "axis":
        html += _render_axis(state)
    elif sid == "scenarios":
        html += _render_scenarios(state)
    elif sid == "unresolved":
        html += _render_unresolved(state)

    html += "</div>"
    return html


def _render_exec(state: dict, five: dict) -> str:
    obs = state.get("observations", [])
    sub = ""
    if obs:
        sub = obs[0].get("path", obs[0].get("cause", ""))
    return (
        f'<div class="exec-box">'
        f'<div class="claim">{_escape(five["core_claim"])}</div>'
        f'<div class="sub">{_escape(sub)}</div>'
        f'</div>'
    )


def _render_dashboard(state: dict) -> str:
    html = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'

    # P layer
    plates = state.get("plates", {})
    p_verdict = plates.get("verdict", "미확인")
    html += '<div class="card"><div style="color:var(--purple);font-weight:600;margin-bottom:6px">P 판</div>'
    for k, v in plates.items():
        if k == "verdict" or not isinstance(v, dict):
            continue
        signal = v.get("signal", "")
        summary = v.get("summary", "")
        label = k.split("_", 1)[-1] if "_" in k else k
        html += f'<div style="font-size:.78em;margin-bottom:3px">{signal} {_escape(label)} — {_escape(summary)}</div>'
    html += f'<div style="color:var(--text-dim);font-size:.72em;margin-top:4px">판정: {_escape(p_verdict)}</div></div>'

    # S layer
    structure = state.get("structure", {})
    s_verdict = structure.get("verdict", "미확인")
    html += '<div class="card"><div style="color:var(--blue);font-weight:600;margin-bottom:6px">S 구조</div>'
    for k in ["S1", "S2", "S3", "S4", "S5"]:
        v = structure.get(k)
        if not isinstance(v, dict):
            continue
        label = v.get("label", k)
        value = v.get("value", "")
        unit = v.get("unit", "")
        direction = v.get("direction", "")
        verdict = v.get("verdict", "")
        display_val = f"{value}{unit}" if unit else str(value)
        html += f'<div style="font-size:.78em;margin-bottom:3px"><span class="num">{_escape(label)} {_escape(display_val)}</span> {direction} <span style="color:var(--text-dim)">{_escape(verdict)}</span></div>'
    html += f'<div style="color:var(--text-dim);font-size:.72em;margin-top:4px">판정: {_escape(s_verdict)}</div></div>'

    # F layer
    flow = state.get("flow", {})
    f_verdict = flow.get("verdict", "미확인")
    html += '<div class="card"><div style="color:var(--cyan);font-weight:600;margin-bottom:6px">F 흐름</div>'
    for k in ["F1", "F2", "F3", "F4", "F5"]:
        v = flow.get(k)
        if not isinstance(v, dict):
            continue
        label = v.get("label", k)
        verdict = v.get("verdict", "")
        direction = v.get("direction", "")
        html += f'<div style="font-size:.78em;margin-bottom:3px">{_escape(label)} {direction} <span style="color:var(--text-dim)">{_escape(verdict)}</span></div>'
    html += f'<div style="color:var(--text-dim);font-size:.72em;margin-top:4px">판정: {_escape(f_verdict)}</div></div>'

    html += '</div>'
    return html


def _render_clash(state: dict) -> str:
    html = ""
    for d in state.get("divergences", []):
        dtype = d.get("type", "")
        desc = d.get("description", "")
        html += f'<div class="divergence"><div class="type">{_escape(dtype)}</div><div class="desc">{_escape(desc)}</div></div>'
    return html


def _render_observations(state: dict, target_sev: str) -> str:
    html = ""
    obs = [o for o in state.get("observations", []) if o.get("severity") == target_sev]
    for o in obs:
        rank = o.get("rank", "")
        signal = o.get("signal", "")
        cause = o.get("cause", o.get("path", ""))
        axis_rel = o.get("axis_relevance", "")
        html += f'<div class="card {target_sev}"><span class="rank">#{rank}</span><span class="signal">{_escape(signal)}</span>'
        html += f'<div class="detail">{_escape(cause)}</div>'
        if axis_rel:
            html += f'<div class="detail" style="color:var(--purple)">{_escape(axis_rel)}</div>'
        html += '</div>'
    return html


def _render_links(state: dict) -> str:
    html = '<div class="link-grid">'
    links = state.get("links", {})
    for k, v in links.items():
        if not isinstance(v, dict):
            continue
        status_raw = str(v.get("status", ""))
        status_lower = status_raw.strip().lower()
        if status_lower.startswith("active") or "활성" in status_raw:
            cls = "active"
        elif "approach" in status_lower or "접근" in status_raw:
            cls = "approaching"
        else:
            continue
        status = status_raw
        note = v.get("note", v.get("evidence", ""))
        html += (
            f'<div class="link-card {cls}">'
            f'<div class="status">{_escape(k)}</div>'
            f'<div style="color:var(--text-dim);font-size:.78em;margin-top:2px">{_escape(status)}</div>'
            f'<div style="color:var(--text);font-size:.78em;margin-top:2px">{_escape(note)}</div>'
            f'</div>'
        )
    html += '</div>'
    return html


def _render_axis(state: dict) -> str:
    axis_names = {
        "1_ai": "①AI",
        "2_energy": "②에너지",
        "3_aging": "③고령화",
        "4_blockchain": "④블록체인",
        "9_fiscal": "⑨재정",
        "8_uscn": "⑧미중",
    }
    html = '<div class="axis-grid">'
    for k, v in state.get("axis_status", {}).items():
        display_name = axis_names.get(k, k)
        status = v.get("status", "미확인") if isinstance(v, dict) else str(v)
        color = _axis_color(status)
        html += f'<div class="axis-card"><div class="axis-name">{_escape(display_name)}</div><div class="axis-status" style="color:{color}">{_escape(status)}</div></div>'
    html += '</div>'
    return html


def _render_scenarios(state: dict) -> str:
    """감시 질문을 테이블로, projection이 있으면 시나리오 그리드도 추가."""
    html = ""
    questions = state.get("next_questions", [])
    open_q = [q for q in questions if q.get("status") == "open"]
    if open_q:
        html += '<table><thead><tr><th>질문</th><th>기한</th><th>유형</th></tr></thead><tbody>'
        for q in open_q:
            html += (
                f'<tr><td>{_escape(q.get("question", ""))}</td>'
                f'<td class="num">{_escape(q.get("deadline", ""))}</td>'
                f'<td>{_escape(q.get("resolve_type", ""))}</td></tr>'
            )
        html += '</tbody></table>'

    # projection.json 시나리오 (있으면)
    proj_path = BASE_DIR / "projection.json"
    if proj_path.exists():
        try:
            with open(proj_path, "r", encoding="utf-8") as f:
                proj = json.load(f)
            scenarios_raw = proj.get("scenarios", {})
            # scenarios can be a dict of dicts or a list of dicts
            if isinstance(scenarios_raw, dict):
                scenarios = list(scenarios_raw.values())
            else:
                scenarios = scenarios_raw
            if scenarios:
                html += '<div class="scenario-grid" style="margin-top:12px">'
                for s in scenarios:
                    if not isinstance(s, dict):
                        continue
                    prob = s.get("probability", 0)
                    name = s.get("name", "")
                    rationale = s.get("rationale", s.get("probability_basis", ""))
                    html += (
                        f'<div class="scenario-card">'
                        f'<div class="prob">{prob:.0%}</div>'
                        f'<div class="name">{_escape(name)}</div>'
                        f'<div class="desc">{_escape(rationale)}</div>'
                        f'</div>'
                    )
                html += '</div>'
        except (json.JSONDecodeError, IOError):
            pass

    return html


def _render_unresolved(state: dict) -> str:
    html = '<ul class="question-list">'
    for q in state.get("next_questions", []):
        if q.get("status") == "open":
            html += f'<li><span class="deadline">{_escape(q.get("deadline", ""))}</span> {_escape(q.get("question", ""))}</li>'
    for u in state.get("unclassified", []):
        html += f'<li style="border-color:var(--purple)"><span style="color:var(--purple)">[미분류]</span> {_escape(u.get("signal", ""))}</li>'
    html += '</ul>'
    return html


# ──────────────────────────────────────────────
# Phase 4: Verify (V1~V5)
# ──────────────────────────────────────────────

def verify(html: str, state: dict, five: dict) -> list:
    """셀프 감사 V1~V5."""
    issues = []

    # V1: Core Claim이 HTML에 존재하는가
    claim_snippet = five["core_claim"][:30]
    if claim_snippet and claim_snippet not in html:
        issues.append("V1 FAIL: Core Claim이 HTML에 포함되지 않음")

    # V2: 상위 3개 관측의 핵심 수치가 반영되었는가
    obs = state.get("observations", [])
    for o in obs[:3]:
        signal = o.get("signal", "")
        key_part = signal[:20] if len(signal) > 20 else signal
        if key_part and key_part not in html:
            issues.append(f"V2 WARN: '{key_part}...' 미반영 가능")

    # V3: 빈 섹션이 없는가 (section-title 뒤에 바로 닫히는지)
    if '<div class="section-title"></div>' in html:
        issues.append("V3 WARN: 빈 section-title 발견")

    # V4: Gravity 비례 — critical이 있으면 large 섹션이어야
    if five["gravity"]["critical"] and "핵심 관측" not in html:
        issues.append("V4 WARN: critical 관측이 있으나 '핵심 관측' 섹션 없음")

    # V5: 첫 화면에 exec-box가 있는가
    first_2500 = html[:2500]
    if "exec-box" not in first_2500:
        issues.append("V5 WARN: exec-box가 첫 화면에 없을 수 있음")

    return issues


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    design_only = "--design-only" in args
    use_projection = "--projection" in args

    target_file = None
    for i, arg in enumerate(args):
        if arg == "--file" and i + 1 < len(args):
            target_file = Path(args[i + 1])

    # Load data
    if target_file:
        data_path = target_file
    elif use_projection:
        data_path = PROJECTION_FILE
    else:
        data_path = STATE_FILE

    if not data_path.exists():
        print(f"[ERROR] {data_path} 없음")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Phase 1
    five = extract_five(state)
    print(f"[Phase 1] Core Claim: {five['core_claim']}")
    print(f"[Phase 1] Tension: {'있음 ({0}건)'.format(five['tension']['count']) if five['tension'] and five['tension']['exists'] else '없음'}")
    print(f"[Phase 1] Gravity: critical {len(five['gravity']['critical'])} / high {len(five['gravity']['high'])} / medium {len(five['gravity']['medium'])} / low {len(five['gravity']['low'])}")
    print(f"[Phase 1] Timeline: {five['timeline']}")
    print(f"[Phase 1] Unresolved: {five['unresolved']['total']}건")

    # Phase 2
    design = design_report(five, state)
    print(f"\n[Phase 2] 유형: {design['type']} {design['type_name']}")
    print(f"[Phase 2] 분류: {design['report_class']}")
    print(f"[Phase 2] 섹션: {design['section_count']}개")
    for s in design["sections"]:
        print(f"  [{s['size'][0].upper()}] {s['name']}")

    if design_only:
        print("\n--design-only: Phase 1-2 완료. HTML 생성 생략.")
        return

    # Phase 3
    html = render_html(design, state, five)

    # Phase 4
    issues = verify(html, state, five)
    if issues:
        print(f"\n[Phase 4] 검증 이슈 {len(issues)}건:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"\n[Phase 4] V1~V5 통과")

    # Save
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = state.get("last_updated", date.today().isoformat())
    filename = f"{today}-briefing-adaptive.html"
    output_path = REPORTS_DIR / filename
    output_path.write_text(html, encoding="utf-8")
    print(f"\n저장: {output_path}")


if __name__ == "__main__":
    main()
