"""state.json → HTML 보고서 렌더러.

사용:
  python core/render.py                      # state.json → reports/ 에 HTML 생성
  python core/render.py path/to/state.json   # 지정 파일로 렌더링

구조:
  1. references/template.html (골격 + CSS) 을 로드
  2. state.json 데이터를 읽어서 플레이스홀더를 치환
  3. reports/YYYY-MM-DD-[쟁점]-reaction.html 로 저장
"""

import json
import html as html_mod
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TEMPLATE_PATH = BASE_DIR / "references" / "template.html"
REPORTS_DIR = BASE_DIR / "reports"


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def tone_class(tone: str) -> str:
    if tone in ("긍", "pos", "Positive"):
        return "pos"
    if tone in ("부", "neg", "Negative"):
        return "neg"
    if tone in ("분열", "split"):
        return "spl"
    return "neu"


def uq_type_class(rt: str) -> str:
    return f"uq-{rt}" if rt in ("date", "condition", "data", "threshold") else "uq-data"


def uq_help(item: dict) -> str:
    rt = item.get("resolve_type", "")
    if rt == "data":
        return "→ MCP 도구로 즉시 체크 가능"
    if rt == "threshold":
        return "→ MCP 도구로 즉시 조회 가능"
    if rt == "date":
        dl = item.get("deadline", "")
        return f"→ {dl} 이후 WebSearch로 확인"
    if rt == "condition":
        return "→ 이벤트 대기. 후속 수집 시 자동 체크"
    return ""


def render_price_table(reactions: list) -> str:
    if not reactions:
        return "<p style='color:var(--muted);font-size:.82rem;'>수집 없음</p>"
    rows = []
    for r in reactions:
        chg = r.get("change_pct", 0)
        cls = "neg" if chg < -1 else "pos" if chg > 1 else "neu"
        rows.append(f"""<tr>
<td><strong>{esc(r.get('asset',''))}</strong></td>
<td>{esc(r.get('before','—'))}</td>
<td>{esc(r.get('after','—'))}</td>
<td class="{cls}">{chg:+.1f}%</td>
<td>{esc(r.get('speed',''))}</td>
<td>{esc(r.get('note',''))}</td>
</tr>""")
    return f"""<table>
<tr><th>자산</th><th>이전</th><th>이후</th><th>변동</th><th>속도</th><th>핵심</th></tr>
{''.join(rows)}
</table>"""


def render_narrative_table(reactions: list) -> str:
    if not reactions:
        return "<p style='color:var(--muted);font-size:.82rem;'>수집 없음</p>"
    rows = []
    for r in reactions:
        tc = tone_class(r.get("tone", ""))
        orig = "O" if r.get("original_analysis") else "X"
        rows.append(f"""<tr>
<td>{esc(r.get('source',''))}</td>
<td>{esc(r.get('frame',''))}</td>
<td class="{tc}">{esc(r.get('tone',''))}</td>
<td>{orig}</td>
<td>{esc(r.get('timestamp',''))}</td>
</tr>""")
    return f"""<table>
<tr><th>매체</th><th>프레임</th><th>톤</th><th>독자분석</th><th>시점</th></tr>
{''.join(rows)}
</table>"""


def render_expert_table(reactions: list) -> str:
    if not reactions:
        return "<p style='color:var(--muted);font-size:.82rem;'>수집 없음</p>"
    rows = []
    for r in reactions:
        tc = tone_class(r.get("direction", ""))
        rows.append(f"""<tr>
<td><strong>{esc(r.get('name',''))}</strong><br><span style="color:var(--muted);font-size:.75rem;">{esc(r.get('affiliation',''))}</span></td>
<td>{esc(r.get('statement',''))}</td>
<td class="{tc}">{esc(r.get('direction',''))}</td>
</tr>""")
    return f"""<table>
<tr><th>이름/기관</th><th>핵심 발언</th><th>방향</th></tr>
{''.join(rows)}
</table>"""


def render_policy_table(reactions: list) -> str:
    if not reactions:
        return "<p style='color:var(--muted);font-size:.82rem;'>비활성</p>"
    rows = []
    for r in reactions:
        rows.append(f"""<tr>
<td>{esc(r.get('institution',''))}</td>
<td>{esc(r.get('action',''))}</td>
<td>{esc(r.get('binding_level',''))}</td>
<td>{esc(r.get('market_implication',''))}</td>
</tr>""")
    return f"""<table>
<tr><th>기관</th><th>조치</th><th>구속력</th><th>시장 시사점</th></tr>
{''.join(rows)}
</table>"""


def render_positioning_table(reactions: list) -> str:
    if not reactions:
        return "<p style='color:var(--muted);font-size:.82rem;'>비활성</p>"
    rows = []
    for r in reactions:
        rows.append(f"""<tr>
<td>{esc(r.get('indicator',''))}</td>
<td>{esc(r.get('value',''))}</td>
<td>{esc(r.get('implication',''))}</td>
</tr>""")
    return f"""<table>
<tr><th>지표</th><th>값</th><th>시사점</th></tr>
{''.join(rows)}
</table>"""


def render_channels_table(channels: dict) -> str:
    rows = []
    layer_tags = {
        "price": ("가격", "t-p"), "narrative": ("서사", "t-n"),
        "expert": ("전문가", "t-e"), "policy": ("정책", "t-po"),
        "positioning": ("포지셔닝", "t-ps"),
    }
    for key, (label, cls) in layer_tags.items():
        items = channels.get(key, [])
        if not items:
            continue
        names = ", ".join(
            item.get("asset", "") or item.get("source", "") or
            item.get("name", "") or item.get("institution", "") or
            item.get("indicator", "")
            for item in items
        )
        reasons = " / ".join(item.get("reason", "") for item in items if item.get("reason"))
        rows.append(f"""<tr>
<td><span class="lt {cls}">{label}</span></td>
<td>{esc(names)}</td>
<td>{esc(reasons)}</td>
</tr>""")
    return f"""<table>
<tr><th>계층</th><th>채널</th><th>선정 이유</th></tr>
{''.join(rows)}
</table>"""


def render_direction_grid(detail: dict) -> str:
    cells = []
    labels = {"price": "가격", "narrative": "서사", "expert": "전문가",
              "policy": "정책", "positioning": "포지셔닝"}
    colors = {"↑": "var(--converge)", "↓": "var(--decouple)", "→": "var(--silence)",
              "↑↓": "var(--diverge)", "분열": "var(--expert)", "이중": "var(--policy)"}
    for key, label in labels.items():
        val = detail.get(key, "—")
        color = colors.get(val, "var(--muted)")
        cells.append(f'<div class="dc"><span class="dl">{label}</span><span class="dv" style="color:{color}">{esc(val)}</span></div>')
    return f'<div class="dg">{"".join(cells)}</div>'


def render_timeline(sequence: list) -> str:
    if not sequence:
        return ""
    items = []
    for s in sorted(sequence, key=lambda x: x.get("order", 0)):
        layer = s.get("layer", "")
        war_cls = " war" if "전쟁" in layer else (" sec" if "SEC" in layer else "")
        items.append(f'<div class="ti{war_cls}"><span class="td">{esc(s.get("timestamp",""))}</span> <strong>{esc(layer)}</strong> — {esc(s.get("event",""))}</div>')
    return f'<div class="tl">{"".join(items)}</div>'


def render_unresolved(items: list) -> str:
    if not items:
        return "<p style='color:var(--muted);'>미해소 질문 없음</p>"
    lis = []
    for item in items:
        if isinstance(item, str):
            lis.append(f'<li class="uq-open">⚠️ (미구조화) {esc(item)}</li>')
            continue
        status_cls = "uq-resolved" if item.get("status") == "resolved" else "uq-open"
        rt = item.get("resolve_type", "")
        tc = uq_type_class(rt)
        help_text = uq_help(item)

        meta_parts = []
        if item.get("resolve_condition"):
            meta_parts.append(f"해소 조건: {esc(item['resolve_condition'])}")
        if item.get("deadline"):
            meta_parts.append(f"기한: {esc(item['deadline'])}")
        if item.get("last_checked"):
            meta_parts.append(f"마지막 체크: {esc(item['last_checked'])} — {esc(item.get('last_checked_result',''))}")
        if item.get("resolution"):
            meta_parts.append(f"<strong>해소:</strong> {esc(item['resolution'])}")

        meta_html = "<br>".join(meta_parts)

        lis.append(f"""<li class="{status_cls}">
<strong>{esc(item.get('id',''))}</strong> {esc(item.get('question',''))}
<span class="uq-type {tc}">{rt}</span>
<div class="uq-meta">{meta_html}<br><span class="uq-help">{help_text}</span></div>
</li>""")
    return f'<ul class="uq">{"".join(lis)}</ul>'


def render_sources(reactions: dict) -> str:
    """모든 반응에서 source/url 필드를 수집하여 소스 목록 생성."""
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
                    # 매체명 추출 시도
                    source_name = item.get("source", "") or item.get("name", "") or item.get("institution", "") or val
                    sources.add((source_name, val))
                elif val:
                    sources.add((val, ""))
    lis = []
    for name, url in sorted(sources):
        if url:
            lis.append(f'<li><a href="{esc(url)}">{esc(name)}</a></li>')
        else:
            lis.append(f'<li>{esc(name)}</li>')
    return f'<ul class="src">{"".join(lis)}</ul>' if lis else ""


def render(data: dict) -> str:
    """state.json → 완전한 HTML 문자열."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    fp = data.get("fingerprint", {})
    ch = data.get("channels", {})
    rx = data.get("reactions", {})
    pt = data.get("pattern", {})
    uq = data.get("unresolved", [])

    uq_open = sum(1 for q in uq if isinstance(q, dict) and q.get("status") == "open")
    uq_resolved = sum(1 for q in uq if isinstance(q, dict) and q.get("status") == "resolved")

    replacements = {
        "{{TITLE}}": esc(data.get("issue", "")),
        "{{DATE}}": esc(data.get("date", "")),
        "{{DEPTH}}": esc(data.get("depth", "Standard")),
        "{{DIRECTION}}": esc(pt.get("direction_alignment", "—")),
        "{{PROPORTIONALITY}}": esc(pt.get("proportionality", "—")),
        "{{PROPAGATION}}": esc(pt.get("propagation", "—")),
        "{{UQ_SUMMARY}}": f"미해소: {uq_open} open / {uq_resolved} resolved",

        # §1 fingerprint
        "{{FP_DOMAIN}}": esc(fp.get("domain", "")),
        "{{FP_GEO}}": esc(fp.get("geography", "")),
        "{{FP_ASSETS}}": esc(", ".join(fp.get("touched_assets", []))),
        "{{FP_STAKEHOLDERS}}": esc(", ".join(fp.get("stakeholders", []))),
        "{{FP_TIME}}": esc(fp.get("time_character", "")),

        # §2 channels
        "{{CHANNELS_TABLE}}": render_channels_table(ch),

        # §3 reactions
        "{{PRICE_TABLE}}": render_price_table(rx.get("price", [])),
        "{{NARRATIVE_TABLE}}": render_narrative_table(rx.get("narrative", [])),
        "{{EXPERT_TABLE}}": render_expert_table(rx.get("expert", [])),
        "{{POLICY_TABLE}}": render_policy_table(rx.get("policy", [])),
        "{{POSITIONING_TABLE}}": render_positioning_table(rx.get("positioning", [])),

        # §4 pattern
        "{{DIRECTION_GRID}}": render_direction_grid(pt.get("direction_detail", {})),
        "{{DIRECTION_RATIONALE}}": esc(pt.get("direction_rationale", "")),
        "{{TIME_STRUCTURE}}": esc(pt.get("time_structure", "")),
        "{{TIMELINE}}": render_timeline(pt.get("time_sequence", [])),
        "{{TIME_RATIONALE}}": esc(pt.get("time_rationale", "")),
        "{{PROP_RATIONALE}}": esc(pt.get("proportionality_rationale", "")),
        "{{PROPAGATION_RATIONALE}}": esc(pt.get("propagation_rationale", "")),
        "{{NEXT_OBSERVATION}}": esc(pt.get("next_observation", "")),

        # §5 unresolved
        "{{UNRESOLVED}}": render_unresolved(uq),

        # sources
        "{{SOURCES}}": render_sources(rx),

        "{{NEXT_CHECK}}": esc(data.get("next_check", "")),
    }

    result = template
    for key, val in replacements.items():
        result = result.replace(key, val)

    return result


def main():
    if len(sys.argv) > 1:
        state_path = Path(sys.argv[1])
    else:
        state_path = BASE_DIR / "state.json"

    if not state_path.exists():
        print(f"❌ state.json 없음: {state_path}")
        sys.exit(1)

    if not TEMPLATE_PATH.exists():
        print(f"❌ 템플릿 없음: {TEMPLATE_PATH}")
        sys.exit(1)

    data = json.loads(state_path.read_text(encoding="utf-8"))
    html_content = render(data)

    # 파일명 생성
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    issue_slug = re.sub(r'[^\w가-힣]', '-', data.get("issue", "reaction"))[:30].strip("-")
    filename = f"{date}-{issue_slug}-reaction.html"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / filename
    out_path.write_text(html_content, encoding="utf-8")

    print(f"✅ 보고서 생성: {out_path}")
    print(f"   쟁점: {data.get('issue', '?')}")
    print(f"   날짜: {date}")


if __name__ == "__main__":
    main()
