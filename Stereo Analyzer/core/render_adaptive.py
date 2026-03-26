"""
Stereo Analyzer 적응형 HTML 보고서 생성기

analysis JSON을 읽고 4단계 파이프라인으로 적응형 HTML 보고서를 생성한다.
  Phase 1: Extract Five (core_finding, tension, gravity, timeline, unresolved)
  Phase 2: Design Report (유형 A~E, 분류, 섹션 구성)
  Phase 3: Render HTML (컴포넌트 조합)
  Phase 4: Verify (V1~V5 셀프 감사)

Usage:
  python core/render_adaptive.py                        # 최신 분석 → HTML
  python core/render_adaptive.py --file analysis.json   # 특정 파일 → HTML
  python core/render_adaptive.py --design-only          # Phase 1-2만 (설계안 출력)
"""

import json
import sys
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_FILE = BASE_DIR / "assets" / "template-base.html"
REPORTS_DIR = BASE_DIR / "reports"
HISTORY_DIR = BASE_DIR / "history"


# ──────────────────────────────────────────────
# Phase 1: Extract Five
# ──────────────────────────────────────────────

def extract_five(analysis: dict) -> dict:
    """분석 JSON에서 5가지 핵심 요소를 추출한다.

    Returns:
        core_finding  - 한줄 본질 (Pre-Read + L7 기반)
        tension       - Layer 간 긴장/충돌
        gravity       - Layer 깊이별 가중치
        timeline      - L6의 시간 프레임
        unresolved    - 돌발 질문 중 미답변 항목
    """
    pre_read = analysis.get("pre_read", {})
    layers = analysis.get("layers", {})
    l7 = layers.get("L7", {})
    l6 = layers.get("L6", {})
    l1 = layers.get("L1", {})

    # Core Finding
    issue_type = pre_read.get("type", "UNKNOWN")
    scp = pre_read.get("scp", 0)
    headline = l1.get("headline", "")
    implication = l7.get("investment_implication", "")
    core_finding = f"[{issue_type} SCP{scp}] {headline}"
    if implication:
        core_finding += f" → {implication}"

    # Tension: L2 facts with red confidence, L4 surface vs structural cause gap
    l2 = layers.get("L2", {})
    red_facts = [f for f in l2.get("facts", []) if f.get("confidence") == "red"]
    l4 = layers.get("L4", {})
    surface = l4.get("surface_cause", "")
    structural = l4.get("structural_cause", "")
    tension = None
    if red_facts or (surface and structural and surface != structural):
        tension = {
            "exists": True,
            "red_facts": len(red_facts),
            "cause_gap": surface != structural if surface and structural else False,
            "details": [f.get("fact", "") for f in red_facts],
        }

    # Gravity: SCP-based layer weight distribution
    routing = pre_read.get("routing", {})
    focus = routing.get("focus_layers", [])
    reduced = routing.get("reduced_layers", [])
    skip = routing.get("skip_layers", [])
    gravity = {
        "focus": focus,
        "reduced": reduced,
        "skip": skip,
        "scp": scp,
        "depth_profile": "deep" if scp >= 4 else "standard" if scp >= 2 else "shallow",
    }

    # Timeline: from L6
    timeline = {
        "short_term": l6.get("short_term", ""),
        "mid_term": l6.get("mid_term", ""),
        "long_term": l6.get("long_term", ""),
        "scenarios": l6.get("scenarios", []),
    }

    # Unresolved: unanswered emergent questions
    eq = analysis.get("emergent_questions", [])
    unanswered = [q for q in eq if not q.get("answerable", True)]
    unresolved = {
        "total_questions": len(eq),
        "unanswered": len(unanswered),
        "items": [q.get("question", "") for q in unanswered],
    }

    return {
        "core_finding": core_finding,
        "tension": tension,
        "gravity": gravity,
        "timeline": timeline,
        "unresolved": unresolved,
    }


# ──────────────────────────────────────────────
# Phase 2: Design Report
# ──────────────────────────────────────────────

def design_report(five: dict, analysis: dict) -> dict:
    """보고서 유형(A~E), 분류, 섹션 구성을 결정한다."""
    pre_read = analysis.get("pre_read", {})
    issue_type = pre_read.get("type", "EVENT")
    scp = pre_read.get("scp", 0)
    tension = five["tension"]
    has_scenarios = bool(five["timeline"]["scenarios"])
    emotion = pre_read.get("emotion", {})
    has_emotion = emotion.get("detected", False)

    # ── 유형 판별 (Pre-Read type 기반) ──
    type_map = {
        "POLICY": ("A", "정책 분석"),
        "MACRO": ("B", "매크로 분석"),
        "STRUCT": ("C", "구조 분석"),
        "EVENT": ("D", "이벤트 분석"),
        "NARR": ("D", "내러티브 분석"),
        "NOISE": ("E", "노이즈 판정"),
    }
    base_type = issue_type.split("×")[0] if "×" in issue_type else issue_type
    report_type, type_name = type_map.get(base_type, ("D", "일반 분석"))
    if "×" in issue_type:
        type_name = f"복합 분석 ({issue_type})"

    # ── 보고서 분류 (SCP 기반) ──
    if scp >= 4:
        report_class, class_color = "STRUCTURAL SHIFT", "red"
    elif scp >= 2:
        report_class, class_color = "DEEP ANALYSIS", "blue"
    else:
        report_class, class_color = "QUICK NOTE", "navy"

    # NOISE override
    if base_type == "NOISE":
        report_class, class_color = "NOISE FILTER", "navy"

    # ── 섹션 구성 ──
    sections = []

    # Always: Topbar + Pre-Read summary
    sections.append({"id": "preread", "name": "Pre-Read", "size": "medium", "component": "preread-badges"})

    # Emotion block (if applicable)
    if has_emotion:
        sections.append({"id": "emotion", "name": "감정 분리", "size": "medium", "component": "emotion-block"})

    # Always: Executive Finding
    sections.append({"id": "exec", "name": "한줄 본질", "size": "large", "component": "exec-box"})

    # NOISE: only L1, then stop
    if base_type == "NOISE":
        sections.append({"id": "l1", "name": "L1 헤드라인 디코딩", "size": "medium", "component": "layer-card"})
        sections.append({"id": "noise-verdict", "name": "노이즈 판정", "size": "medium", "component": "noise-card"})
        return {
            "type": report_type, "type_name": type_name,
            "report_class": report_class, "class_color": class_color,
            "sections": sections, "section_count": len(sections),
        }

    # Surface Layers (L1-L3)
    sections.append({"id": "surface", "name": "SURFACE (보이는 것)", "size": "large", "component": "surface-group"})

    # Subsurface Layers (L4-L6)
    sections.append({"id": "subsurface", "name": "SUBSURFACE (보이지 않는 것)", "size": "large", "component": "subsurface-group"})

    # Emergent Questions
    eq = analysis.get("emergent_questions", [])
    if eq:
        sections.append({"id": "emergent", "name": "돌발 질문", "size": "medium", "component": "emergent-questions"})

    # L7 Judgment
    sections.append({"id": "l7", "name": "L7 판단 프레임", "size": "large", "component": "judgment-frame"})

    # Uncertainty Map
    sections.append({"id": "uncertainty", "name": "불확실성 지도", "size": "medium", "component": "uncertainty-map"})

    # Feedback Record
    sections.append({"id": "feedback", "name": "되먹임 기록", "size": "small", "component": "feedback-record"})

    # Self-check
    sections.append({"id": "selfcheck", "name": "자기 점검", "size": "small", "component": "selfcheck-summary"})

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

def _escape(text) -> str:
    """HTML 특수문자 이스케이프."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _confidence_icon(conf: str) -> str:
    icons = {"green": "🟢", "yellow": "🟡", "red": "🔴", "black": "⚫"}
    return icons.get(conf, "⚪")


def _verdict_icon(verdict: str) -> str:
    icons = {"repeat": "🔄", "shift": "🔀", "ambiguous": "❓"}
    return icons.get(verdict, "❓")


def _confidence_bar(level: int) -> str:
    filled = min(max(level, 0), 5)
    return "■" * filled + "□" * (5 - filled)


def _scp_class(scp: int) -> str:
    if scp >= 4:
        return "scp-high"
    elif scp >= 2:
        return "scp-mid"
    return "scp-low"


CSS_INLINE = """:root {
  --navy:#0d1117;--dark:#161b22;--border:#30363d;
  --text:#c9d1d9;--text-bright:#f0f6fc;--text-dim:#8b949e;
  --blue:#58a6ff;--green:#4caf50;--yellow:#ffd600;
  --red:#ff5252;--purple:#d2a8ff;--cyan:#80deea;--gold:#ffab00;
  --surface-blue:#1a3a5c;--surface-text:#7ec8e3;
  --subsurface-purple:#2a1a4a;--subsurface-text:#ce93d8;
  --l7-gold-bg:#3a2800;--l7-gold-text:#ffd600;
  --scp-high-bg:#3d0000;--scp-high-text:#ff5252;
  --scp-mid-bg:#0a2540;--scp-mid-text:#58a6ff;
  --scp-low-bg:#1c2028;--scp-low-text:#8b949e;
  --framing-bg:#2a1a3e;--framing-text:#ce93d8;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--navy);color:var(--text);font-family:'Noto Sans KR',sans-serif;line-height:1.7}
.container{max-width:780px;margin:0 auto;padding:16px}
.topbar{padding:6px 16px;font-size:.7em;font-weight:700;letter-spacing:2px;text-transform:uppercase;text-align:center}
.topbar.red{background:#5c0000;color:#ff5252}
.topbar.blue{background:#0a2540;color:#58a6ff}
.topbar.navy{background:#0d1117;color:#8b949e;border-bottom:1px solid var(--border)}
.report-header{padding:20px 16px 12px}
.report-header h1{color:var(--text-bright);font-size:1.3em;margin-bottom:6px}
.report-header .meta{color:var(--text-dim);font-size:.8em}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.badge{padding:4px 12px;border-radius:4px;font-size:.75em;font-weight:600;white-space:nowrap}
.badge.scp-high{background:var(--scp-high-bg);color:var(--scp-high-text)}
.badge.scp-mid{background:var(--scp-mid-bg);color:var(--scp-mid-text)}
.badge.scp-low{background:var(--scp-low-bg);color:var(--scp-low-text)}
.badge.type-badge{background:#1a2733;color:var(--cyan)}
.badge.urgency-badge{background:#2a1a00;color:var(--gold)}
.badge.framing{background:var(--framing-bg);color:var(--framing-text)}
.exec-box{background:var(--dark);border-left:4px solid var(--gold);padding:16px 20px;margin:16px 0;border-radius:0 8px 8px 0}
.exec-box .claim{color:var(--text-bright);font-size:1.05em;font-weight:500}
.exec-box .sub{color:var(--text-dim);font-size:.82em;margin-top:6px}
.section{margin:12px 0}.section-large{margin:16px 0}.section-small{margin:8px 0}
.section-title{color:var(--blue);font-size:.9em;font-weight:700;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.section-title.surface{color:var(--surface-text)}.section-title.subsurface{color:var(--subsurface-text)}.section-title.l7{color:var(--l7-gold-text)}
.card{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px}
.card.surface{border-left:3px solid var(--surface-text)}
.card.subsurface{border-left:3px solid var(--subsurface-text)}
.card.l7{border-left:3px solid var(--l7-gold-text)}
.card .layer-label{font-size:.75em;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.card .layer-label.surface-label{color:var(--surface-text)}
.card .layer-label.subsurface-label{color:var(--subsurface-text)}
.card .layer-label.l7-label{color:var(--l7-gold-text)}
.card .content{color:var(--text);font-size:.85em}
.card .detail{color:var(--text-dim);font-size:.82em;margin-top:4px}
.card .fb-tag{background:#1a2733;color:var(--cyan);padding:2px 6px;border-radius:3px;font-size:.7em;margin-left:4px}
table{width:100%;border-collapse:collapse;font-size:.82em}
th{background:var(--dark);color:var(--text-dim);padding:8px 12px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:8px 12px;border-bottom:1px solid #1c2028}
.num{font-family:'DM Mono',monospace;color:var(--text-bright)}
.emotion-box{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:12px 16px;margin-bottom:8px}
.emotion-box .emotion-label{color:var(--purple);font-size:.75em;font-weight:600}
.emotion-box .emotion-content{font-size:.85em;margin-top:4px}
.uncertainty-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px}
.uncertainty-cell{background:var(--dark);border:1px solid var(--border);border-radius:6px;padding:8px;text-align:center;font-size:.78em}
.uncertainty-cell .layer-name{color:var(--text-bright);font-weight:600}
.uncertainty-cell .bar{font-family:'DM Mono',monospace;color:var(--yellow);font-size:.85em;margin-top:2px}
.uncertainty-cell.weakest{border-color:var(--red);background:#1a0000}
.noise-card{background:#1c2028;border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center}
.noise-card .verdict{color:var(--text-dim);font-size:1em;font-weight:600}
.scenario-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.scenario-card{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px}
.scenario-card .condition{color:var(--text-bright);font-weight:500;font-size:.85em}
.scenario-card .result{color:var(--text-dim);font-size:.8em;margin-top:4px}
.question-card{background:var(--dark);border:1px solid var(--border);border-left:3px solid var(--purple);border-radius:8px;padding:10px 14px;margin-bottom:6px}
.question-card .lens{color:var(--purple);font-size:.7em;font-weight:600;text-transform:uppercase}
.question-card .q-text{color:var(--text-bright);font-size:.85em;margin-top:2px}
.question-card .q-answer{color:var(--text-dim);font-size:.8em;margin-top:4px}
.tracking-list{list-style:none}
.tracking-list li{background:var(--dark);border:1px solid var(--border);border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:.82em}
.tracking-list .indicator{color:var(--text-bright);font-weight:500}
.tracking-list .check-date{color:var(--gold);font-family:'DM Mono',monospace;font-size:.8em}
.signal-noise-box{background:var(--dark);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-top:8px}
.signal-noise-box .signal{color:var(--green);font-size:.85em}
.signal-noise-box .noise{color:var(--text-dim);font-size:.85em;margin-top:4px}
.footer{margin:24px 0;padding-top:12px;border-top:1px solid var(--border);color:var(--text-dim);font-size:.72em;text-align:center}
.disclaimer{color:#484f58;font-size:.68em;margin-top:8px;font-style:italic}
@media(max-width:600px){.scenario-grid{grid-template-columns:1fr}.uncertainty-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:480px){.container{padding:8px}.report-header h1{font-size:1.1em}.exec-box{padding:12px 14px}.section,.section-large,.section-small{margin:8px 0}}"""


def render_html(design: dict, analysis: dict, five: dict) -> str:
    """design + analysis + five로 완전한 HTML을 생성한다."""
    pre_read = analysis.get("pre_read", {})
    layers = analysis.get("layers", {})
    today = analysis.get("date", date.today().isoformat())
    analysis_id = analysis.get("id", "SA-unknown")
    l1 = layers.get("L1", {})
    headline = l1.get("headline", "분석")

    parts = []

    # ── Head ──
    parts.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stereo Analysis — {_escape(headline[:50])}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS_INLINE}</style>
</head>
<body>""")

    # ── Topbar ──
    parts.append(f'<div class="topbar {design["class_color"]}">{design["report_class"]}</div>')

    # ── Header ──
    parts.append(f"""<div class="container">
<div class="report-header">
  <h1>🔬 입체 분석 │ {_escape(headline[:80])}</h1>
  <div class="meta">{analysis_id} · {today} · {design['type_name']} · {design['section_count']}개 섹션</div>
</div>""")

    # ── Sections ──
    for sec in design["sections"]:
        parts.append(_render_section(sec, analysis, five))

    # ── Footer ──
    parts.append(f"""
<div class="footer">
  Stereo Analyzer v2.0 · {analysis_id}
  <div class="disclaimer">이 보고서는 분석 결과입니다. 투자 판단이나 행동 권고가 아닙니다.</div>
</div>
</div></body></html>""")

    return "\n".join(parts)


def _render_section(sec: dict, analysis: dict, five: dict) -> str:
    sid = sec["id"]
    name = sec["name"]
    size = sec["size"]
    size_class = f"section-{size}" if size != "medium" else "section"

    html = f'<div class="{size_class}">'

    if sid == "preread":
        html += _render_preread(analysis)
    elif sid == "emotion":
        html += _render_emotion(analysis)
    elif sid == "exec":
        html += _render_exec(five)
    elif sid == "surface":
        html += _render_surface(analysis)
    elif sid == "subsurface":
        html += _render_subsurface(analysis)
    elif sid == "emergent":
        html += _render_emergent(analysis)
    elif sid == "l7":
        html += _render_l7(analysis, five)
    elif sid == "uncertainty":
        html += _render_uncertainty(analysis)
    elif sid == "feedback":
        html += _render_feedback(analysis)
    elif sid == "selfcheck":
        html += _render_selfcheck(analysis)
    elif sid == "l1":
        html += _render_l1_only(analysis)
    elif sid == "noise-verdict":
        html += _render_noise_verdict(analysis)

    html += "</div>"
    return html


def _render_preread(analysis: dict) -> str:
    pr = analysis.get("pre_read", {})
    issue_type = pr.get("type", "UNKNOWN")
    scp = pr.get("scp", 0)
    urgency = pr.get("urgency", "WATCH")
    routing = pr.get("routing", {})
    mode = routing.get("mode", "full")
    strategy = routing.get("strategy_summary", "")
    scp_basis = pr.get("scp_basis", "")
    scp_cls = _scp_class(scp)

    html = f'<div class="section-title">Pre-Read</div>'
    html += f'<div class="badges">'
    html += f'<span class="badge type-badge">{_escape(issue_type)}</span>'
    html += f'<span class="badge {scp_cls}">SCP {scp}</span>'
    html += f'<span class="badge urgency-badge">{_escape(urgency)}</span>'
    html += f'<span class="badge" style="background:var(--dark);color:var(--text-dim);border:1px solid var(--border)">{_escape(mode)}</span>'
    html += f'</div>'
    if scp_basis:
        html += f'<div style="color:var(--text-dim);font-size:.78em;margin-top:6px">SCP: {_escape(scp_basis)}</div>'
    if strategy:
        html += f'<div style="color:var(--text-dim);font-size:.78em;margin-top:2px">전략: {_escape(strategy)}</div>'
    return html


def _render_emotion(analysis: dict) -> str:
    emotion = analysis.get("pre_read", {}).get("emotion", {})
    html = '<div class="emotion-box">'
    html += '<div class="emotion-label">💭 감정 분리</div>'
    html += f'<div class="emotion-content">걱정 원문: "{_escape(emotion.get("original", ""))}"</div>'
    html += f'<div class="emotion-content" style="color:var(--text-dim)">핵심 불확실성: {_escape(emotion.get("core_uncertainty", ""))}</div>'
    html += f'<div class="emotion-content" style="color:var(--text-bright)">검증 질문: "{_escape(emotion.get("converted_question", ""))}"</div>'
    html += '</div>'
    return html


def _render_exec(five: dict) -> str:
    return (
        f'<div class="exec-box">'
        f'<div class="claim">{_escape(five["core_finding"])}</div>'
        f'</div>'
    )


def _render_surface(analysis: dict) -> str:
    layers = analysis.get("layers", {})
    html = '<div class="section-title surface">━━ SURFACE (보이는 것) ━━</div>'

    # L1
    l1 = layers.get("L1", {})
    html += '<div class="card surface">'
    html += '<div class="layer-label surface-label">L1 헤드라인 디코딩</div>'
    html += f'<div class="content">{_escape(l1.get("headline", ""))}</div>'
    framing = l1.get("framing", [])
    if framing:
        html += '<div style="margin-top:6px">'
        for f in framing:
            html += f'<span class="badge framing">[{_escape(f)}]</span> '
        html += '</div>'
    html += '</div>'

    # L2
    l2 = layers.get("L2", {})
    facts = l2.get("facts", [])
    unsaid = l2.get("unsaid", [])
    html += '<div class="card surface">'
    html += '<div class="layer-label surface-label">L2 팩트 스켈레톤</div>'
    if facts:
        html += '<table><thead><tr><th>#</th><th>팩트</th><th>신뢰도</th><th>출처</th></tr></thead><tbody>'
        for f in facts:
            icon = _confidence_icon(f.get("confidence", ""))
            fb = ' <span class="fb-tag">FB</span>' if f.get("fb_enhanced") else ""
            html += f'<tr><td class="num">{f.get("id", "")}</td><td>{_escape(f.get("fact", ""))}{fb}</td><td>{icon}</td><td style="color:var(--text-dim)">{_escape(f.get("source", ""))}</td></tr>'
        html += '</tbody></table>'
    if unsaid:
        html += '<div style="margin-top:8px;color:var(--text-dim);font-size:.82em">📦 기사가 말하지 않은 것:</div>'
        for u in unsaid:
            if isinstance(u, dict):
                item_text = u.get("item", "")
                fb = ' <span class="fb-tag">FB</span>' if u.get("fb_enhanced") else ""
            else:
                item_text = str(u)
                fb = ' <span class="fb-tag">FB</span>' if "[FB" in item_text else ""
            html += f'<div style="font-size:.82em;padding-left:12px">├── {_escape(item_text)}{fb}</div>'
    html += '</div>'

    # L3
    l3 = layers.get("L3", {})
    players = l3.get("players", [])
    html += '<div class="card surface">'
    html += '<div class="layer-label surface-label">L3 이해관계 지도</div>'
    if players:
        html += '<table><thead><tr><th>플레이어</th><th>입장</th><th>이익</th><th>숨은 동기</th></tr></thead><tbody>'
        for p in players:
            fb = ' <span class="fb-tag">FB</span>' if p.get("fb_enhanced") else ""
            html += f'<tr><td style="color:var(--text-bright)">{_escape(p.get("name", ""))}{fb}</td><td>{_escape(p.get("position", ""))}</td><td>{_escape(p.get("benefit", ""))}</td><td style="color:var(--text-dim)">{_escape(p.get("hidden_motive", ""))}</td></tr>'
        html += '</tbody></table>'
    html += '</div>'

    return html


def _render_subsurface(analysis: dict) -> str:
    layers = analysis.get("layers", {})
    html = '<div class="section-title subsurface">━━ SUBSURFACE (보이지 않는 것) ━━</div>'

    # L4
    l4 = layers.get("L4", {})
    html += '<div class="card subsurface">'
    html += '<div class="layer-label subsurface-label">L4 인과 역추적</div>'
    html += f'<div class="content" style="color:var(--text-bright)">왜 지금: {_escape(l4.get("why_now", ""))}</div>'
    html += f'<div class="detail">├── 직접 트리거: {_escape(l4.get("surface_cause", ""))}</div>'
    html += f'<div class="detail">├── 구조적 원인: {_escape(l4.get("structural_cause", ""))}</div>'
    html += f'<div class="detail">└── 타이밍: {_escape(l4.get("timing_factor", ""))}</div>'
    tree = l4.get("causal_tree", "")
    if tree:
        html += f'<div style="margin-top:8px;font-size:.8em;color:var(--text-dim);white-space:pre-wrap;font-family:DM Mono,monospace">{_escape(tree)}</div>'
    html += '</div>'

    # L5
    l5 = layers.get("L5", {})
    verdict = l5.get("verdict", "ambiguous")
    html += '<div class="card subsurface">'
    html += '<div class="layer-label subsurface-label">L5 구조 레이어</div>'
    html += f'<div class="content">소속 시스템: {_escape(l5.get("system", ""))}</div>'
    html += f'<div class="content">판정: {_verdict_icon(verdict)} — {_escape(l5.get("verdict_basis", ""))}</div>'
    html += f'<div class="detail">전례: {_escape(l5.get("precedent", ""))}</div>'
    html += '</div>'

    # L6
    l6 = layers.get("L6", {})
    html += '<div class="card subsurface">'
    html += '<div class="layer-label subsurface-label">L6 2차 효과 체인</div>'
    html += f'<div class="detail">├── [단기] {_escape(l6.get("short_term", ""))}</div>'
    html += f'<div class="detail">├── [중기] {_escape(l6.get("mid_term", ""))}</div>'
    html += f'<div class="detail">└── [장기] {_escape(l6.get("long_term", ""))}</div>'
    scenarios = l6.get("scenarios", [])
    if scenarios:
        html += '<div style="margin-top:8px"><div class="scenario-grid">'
        for s in scenarios:
            html += f'<div class="scenario-card"><div class="condition">{_escape(s.get("condition", ""))}</div><div class="result">{_escape(s.get("result", ""))}</div></div>'
        html += '</div></div>'
    html += '</div>'

    return html


def _render_emergent(analysis: dict) -> str:
    eq = analysis.get("emergent_questions", [])
    html = '<div class="section-title" style="color:var(--purple)">🔍 돌발 질문 (Emergent Questions)</div>'
    for q in eq:
        html += '<div class="question-card">'
        html += f'<div class="lens">[{_escape(q.get("lens", ""))}]</div>'
        html += f'<div class="q-text">{_escape(q.get("question", ""))}</div>'
        answer = q.get("answer", "")
        if answer:
            html += f'<div class="q-answer">→ {_escape(answer)}</div>'
        html += '</div>'
    return html


def _render_l7(analysis: dict, five: dict) -> str:
    l7 = analysis.get("layers", {}).get("L7", {})
    emotion = analysis.get("pre_read", {}).get("emotion", {})

    html = '<div class="section-title l7">L7 판단 프레임</div>'
    html += '<div class="card l7">'
    html += '<div class="layer-label l7-label">L7 JUDGMENT FRAME</div>'
    html += f'<div class="content" style="color:var(--text-bright)">📍 투자 함의: {_escape(l7.get("investment_implication", ""))}</div>'
    html += f'<div class="content" style="color:var(--red);margin-top:6px">🚨 Kill Condition: {_escape(l7.get("kill_condition", ""))}</div>'

    # Tracking
    tracking = l7.get("tracking", [])
    if tracking:
        html += '<div style="margin-top:8px"><div style="color:var(--text-dim);font-size:.82em;margin-bottom:4px">📡 추적 지표:</div>'
        html += '<ul class="tracking-list">'
        for t in tracking:
            name = t.get("metric", t.get("indicator", ""))
            current = t.get("current", "")
            trigger = t.get("trigger", "")
            distance = t.get("distance", "")
            next_chk = t.get("next_check", "")
            html += f'<li><span class="indicator">{_escape(name)}</span>'
            if current:
                html += f' <span style="font-family:DM Mono,monospace;color:var(--text-bright)">{_escape(str(current))}</span>'
            if trigger:
                html += f' <span style="color:var(--text-dim)">→ 트리거: {_escape(str(trigger))}</span>'
            if distance:
                html += f' <span style="color:var(--gold)">({_escape(str(distance))})</span>'
            if next_chk:
                html += f' <span class="check-date">[{_escape(next_chk)}]</span>'
            html += '</li>'
        html += '</ul></div>'

    # Signal/Noise
    sn = l7.get("signal_or_noise", {})
    if sn:
        html += '<div class="signal-noise-box">'
        if isinstance(sn, dict):
            html += f'<div class="signal">💡 시그널 조건: {_escape(sn.get("signal_condition", ""))}</div>'
            html += f'<div class="noise">💤 노이즈 조건: {_escape(sn.get("noise_condition", ""))}</div>'
        else:
            html += f'<div class="signal">{_escape(str(sn))}</div>'
        html += '</div>'

    # Emotion response
    er = l7.get("emotion_response", {})
    if isinstance(er, dict) and er.get("applicable"):
        html += f'<div class="emotion-box" style="margin-top:8px"><div class="emotion-label">💬 걱정에 대한 회답</div><div class="emotion-content">{_escape(er.get("response", ""))}</div></div>'

    html += '</div>'
    return html


def _render_uncertainty(analysis: dict) -> str:
    um = analysis.get("uncertainty_map", {})
    weakest = um.get("weakest", "")

    html = '<div class="section-title">📊 불확실성 지도</div>'
    html += '<div class="uncertainty-grid">'
    for layer in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        level = um.get(layer, 3)
        cls = "uncertainty-cell weakest" if layer == weakest else "uncertainty-cell"
        html += f'<div class="{cls}"><div class="layer-name">{layer}</div><div class="bar">{_confidence_bar(level)}</div></div>'
    html += '</div>'
    if weakest:
        html += f'<div style="margin-top:8px;font-size:.82em;color:var(--red)">⚠️ 약한 고리: {_escape(weakest)} — {_escape(um.get("weakest_reason", ""))}</div>'
        html += f'<div style="font-size:.82em;color:var(--text-dim)">📡 보강: {_escape(um.get("strengthen_by", ""))}</div>'
    return html


def _render_feedback(analysis: dict) -> str:
    fb = analysis.get("feedback", {})
    executed = fb.get("executed", [])
    delta = fb.get("fb4_delta", "")

    html = '<div class="section-title">🔄 되먹임 기록</div>'
    html += '<div class="card">'
    html += f'<div class="content">실행된 FB: {", ".join(executed) if executed else "없음"}</div>'
    if fb.get("fb1_result"):
        html += f'<div class="detail">FB-1 (L4→L2): {_escape(fb["fb1_result"])}</div>'
    if fb.get("fb2_result"):
        html += f'<div class="detail">FB-2 (L5→L3): {_escape(fb["fb2_result"])}</div>'
    if fb.get("fb3_result"):
        html += f'<div class="detail">FB-3 (L6→L7): {_escape(fb["fb3_result"])}</div>'
    html += f'<div class="detail" style="color:var(--text-bright);margin-top:6px">FB-4 최종 대조: {_escape(delta)}</div>'
    html += '</div>'
    return html


def _render_selfcheck(analysis: dict) -> str:
    sc = analysis.get("self_check", {})
    total = sc.get("total_items", 12)
    passed = sc.get("passed", 0)
    failed = sc.get("failed_items", [])

    html = '<div class="section-title">✅ 자기 점검</div>'
    html += '<div class="card">'
    color = "var(--green)" if passed == total else "var(--yellow)" if passed >= total - 2 else "var(--red)"
    html += f'<div class="content" style="color:{color}">{passed}/{total} 통과</div>'
    if failed:
        for f in failed:
            html += f'<div class="detail" style="color:var(--red)">✗ {_escape(f)}</div>'
    html += '</div>'
    return html


def _render_l1_only(analysis: dict) -> str:
    l1 = analysis.get("layers", {}).get("L1", {})
    html = '<div class="card surface">'
    html += '<div class="layer-label surface-label">L1 헤드라인 디코딩</div>'
    html += f'<div class="content">{_escape(l1.get("headline", ""))}</div>'
    framing = l1.get("framing", [])
    if framing:
        html += '<div style="margin-top:6px">'
        for f in framing:
            html += f'<span class="badge framing">[{_escape(f)}]</span> '
        html += '</div>'
    html += '</div>'
    return html


def _render_noise_verdict(analysis: dict) -> str:
    pr = analysis.get("pre_read", {})
    scp_basis = pr.get("scp_basis", "")
    html = '<div class="noise-card">'
    html += '<div class="verdict">⚡ NOISE — 분석 불필요</div>'
    html += f'<div style="color:var(--text-dim);font-size:.82em;margin-top:8px">사유: {_escape(scp_basis)}</div>'
    html += '</div>'
    return html


# ──────────────────────────────────────────────
# Phase 4: Verify (V1~V5)
# ──────────────────────────────────────────────

def verify(html: str, analysis: dict, five: dict) -> list:
    """셀프 감사 V1~V5."""
    issues = []

    # V1: Core Finding이 HTML에 존재하는가
    snippet = five["core_finding"][:40]
    if snippet and _escape(snippet) not in html:
        issues.append("V1 FAIL: Core Finding이 HTML에 포함되지 않음")

    # V2: Pre-Read badges가 렌더링되었는가
    pre_read = analysis.get("pre_read", {})
    if pre_read.get("type", "") and pre_read["type"] not in html:
        issues.append("V2 WARN: Pre-Read type이 HTML에 미반영")

    # V3: L7이 있으면 kill_condition이 HTML에 존재해야
    l7 = analysis.get("layers", {}).get("L7", {})
    kc = l7.get("kill_condition", "")
    if kc and _escape(kc[:20]) not in html:
        issues.append("V3 WARN: Kill Condition이 HTML에 미반영")

    # V4: 불확실성 지도가 렌더링되었는가
    if "uncertainty-grid" not in html and pre_read.get("type") != "NOISE":
        issues.append("V4 WARN: 불확실성 지도가 HTML에 없음")

    # V5: exec-box가 첫 화면에 있는가
    first_3000 = html[:3000]
    if "exec-box" not in first_3000:
        issues.append("V5 WARN: exec-box가 첫 화면에 없을 수 있음")

    return issues


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def render_from_dict(analysis: dict, save: bool = True) -> tuple[str, str | None]:
    """
    dict에서 직접 HTML을 생성한다. JSON 파일 의존 없음.

    Args:
        analysis: 분석 결과 dict (SCHEMAS.md 형식)
        save: True면 reports/에 저장 + history/에 JSON 저장

    Returns:
        (html_string, saved_path_or_None)
    """
    # Phase 1
    five = extract_five(analysis)

    # Phase 2
    design = design_report(five, analysis)

    # Phase 3
    html = render_html(design, analysis, five)

    # Phase 4
    issues = verify(html, analysis, five)
    if issues:
        for issue in issues:
            print(f"  [V] {issue}")

    saved_path = None
    if save:
        # HTML 저장
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        today = analysis.get("date", date.today().isoformat())
        title = analysis.get("id", "unknown")
        filename = f"{today}-{title}-adaptive.html"
        output_path = REPORTS_DIR / filename
        output_path.write_text(html, encoding="utf-8")
        saved_path = str(output_path)

        # JSON도 동시 저장 (이력 축적용, HTML 생성과 독립)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        json_path = HISTORY_DIR / f"{today}-{title}.json"
        if not json_path.exists():  # 이미 있으면 덮어쓰지 않음
            import json as _json
            with open(json_path, "w", encoding="utf-8") as f:
                _json.dump(analysis, f, ensure_ascii=False, indent=2)

    return html, saved_path


def main():
    """
    CLI 진입점.

    ★ --file은 명시적 지정 전용. 자동으로 history/에서 가져오지 않음.
       파일 없이 실행하면 stdin에서 JSON을 읽거나 오류 출력.

    Usage:
      python render_adaptive.py --file history/2026-03-25-xxx.json   # 명시 파일
      echo '{"id":"..."}' | python render_adaptive.py --stdin         # stdin 입력
      python render_adaptive.py --design-only --file xxx.json         # 설계만
    """
    args = sys.argv[1:]
    design_only = "--design-only" in args
    use_stdin = "--stdin" in args

    target_file = None
    for i, arg in enumerate(args):
        if arg == "--file" and i + 1 < len(args):
            target_file = Path(args[i + 1])

    # Load data — 반드시 명시적 소스 필요. 자동 탐색 없음.
    if use_stdin:
        import sys as _sys
        raw = _sys.stdin.read()
        analysis = json.loads(raw)
        print(f"[입력] stdin에서 JSON 로드 ({len(raw)}자)")
    elif target_file:
        if not target_file.exists():
            print(f"[ERROR] {target_file} 없음")
            sys.exit(1)
        with open(target_file, "r", encoding="utf-8") as f:
            analysis = json.load(f)
        print(f"[입력] {target_file}")
    else:
        print("[ERROR] 입력 소스를 지정하세요.")
        print("  --file history/xxx.json   (명시 파일)")
        print("  --stdin                   (표준입력에서 JSON)")
        print("")
        print("★ history/에서 자동으로 가져오지 않습니다.")
        print("  과거 데이터 오염을 방지하기 위해 반드시 명시적 지정 필요.")
        sys.exit(1)

    # Phase 1
    five = extract_five(analysis)
    print(f"[Phase 1] Core Finding: {five['core_finding']}")
    print(f"[Phase 1] Tension: {'있음' if five['tension'] and five['tension']['exists'] else '없음'}")
    print(f"[Phase 1] Gravity: {five['gravity']['depth_profile']} (SCP {five['gravity']['scp']})")
    print(f"[Phase 1] Timeline: scenarios {len(five['timeline']['scenarios'])}건")
    print(f"[Phase 1] Unresolved: {five['unresolved']['unanswered']}건")

    # Phase 2
    design = design_report(five, analysis)
    print(f"\n[Phase 2] 유형: {design['type']} {design['type_name']}")
    print(f"[Phase 2] 분류: {design['report_class']}")
    print(f"[Phase 2] 섹션: {design['section_count']}개")
    for s in design["sections"]:
        print(f"  [{s['size'][0].upper()}] {s['name']}")

    if design_only:
        print("\n--design-only: Phase 1-2 완료. HTML 생성 생략.")
        return

    # Phase 3 + 4 + Save (render_from_dict 사용)
    html, saved_path = render_from_dict(analysis, save=True)

    print(f"\n[Phase 4] ✅ 완료")
    if saved_path:
        print(f"저장: {saved_path}")


if __name__ == "__main__":
    main()
