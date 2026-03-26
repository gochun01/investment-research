"""
render_report.py — macro 주간 보고서 렌더러

Usage:
    python core/render_report.py                    # MD + HTML 생성
    python core/render_report.py --md-only          # MD만 생성
    python core/render_report.py --html-only        # HTML만 생성
    python core/render_report.py --output-dir ./out # 출력 디렉토리 지정

입력: indicators/latest.json
출력: reports/YYYY-MM-DD_macro-weekly.md + .html
형식: TEMPLATE-macro-report.md 준수
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── 경로 ─────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent.parent
LATEST_FILE = SCRIPT_DIR / "indicators" / "latest.json"
REPORTS_DIR = SCRIPT_DIR / "reports"

# ── 지표 ID ──────────────────────────────────────────

LAYER_A = ["A1", "A2"]
LAYER_B = ["B1", "B2", "B3", "B4", "B5"]
LAYER_C = [f"C{i}" for i in range(1, 11)]
LAYER_D = [f"D{i}" for i in range(1, 11)]


# ── 데이터 로드 ──────────────────────────────────────

def load_latest():
    """latest.json 로드."""
    if not LATEST_FILE.exists():
        print(f"오류: {LATEST_FILE} 없음")
        sys.exit(1)
    with open(LATEST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ── MD 렌더링 ────────────────────────────────────────

def render_md(data):
    """latest.json → TEMPLATE-macro-report.md 형식의 MD 문자열 생성."""
    regime = data.get("regime", {})
    date_str = data.get("date", "????-??-??")
    basis = data.get("data_basis", "")
    prev_date = data.get("prev_date", "")

    lines = []

    # ── 헤더 ──
    lines.append(f"# 글로벌 매크로 주간 점검 — {date_str}")
    lines.append("")

    # ── 핵심 3줄 + 해석 ──
    lines.append("## 핵심 결론")
    lines.append("")
    lines.append(_build_headline(data, regime))
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 1. 레짐 판정 ──
    lines.append("## 1. 레짐 판정")
    lines.append("")
    lines.append("| 항목 | 판정 | 전주 |")
    lines.append("|------|------|------|")
    lines.append(
        f"| 레짐 | {regime.get('status', '?')} ({regime.get('quadrant', '?')}) "
        f"| {regime.get('previous', '?')} |"
    )
    lines.append(
        f"| L7 | {regime.get('L7', '?')} / 0.60 "
        f"{_gate_icon(regime.get('L7', 0))} | |"
    )
    lines.append(
        f"| L8 | {regime.get('L8', '?')} / 0.60 "
        f"{_gate_icon(regime.get('L8', 0))} | |"
    )
    lines.append(f"| 키스톤 | {regime.get('keystone', '?')} | |")
    lines.append(f"| 내러티브 | {regime.get('narrative', '?')} | |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 2. 이벤트 서사 ──
    lines.append("## 2. 이벤트 서사")
    lines.append("")
    lines.append(f"지배 경로: {regime.get('dominant_path', '?')}")
    lines.append(f"교란 상태: {regime.get('disruption', '없음')}")
    lines.append(f"전환 트리거: {regime.get('transition_trigger', '?')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 3. Layer A (키스톤) ──
    lines.append("## 3. Layer A — 근본 (키스톤)")
    lines.append("")
    lines.append("| ID | 지표 | 현재값 | 방향 | 상태 | 비고 |")
    lines.append("|-----|------|--------|------|------|------|")
    for ind_id in LAYER_A:
        ind = data.get(ind_id, {})
        lines.append(_indicator_row(ind_id, ind))
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 4. Layer B (전달) ──
    lines.append("## 4. Layer B — 전달 (위험자산 방향)")
    lines.append("")
    lines.append("| ID | 지표 | 현재값 | 전주 | 변화 | 방향 | 위험자산 |")
    lines.append("|-----|------|--------|------|------|------|----------|")
    for ind_id in LAYER_B:
        ind = data.get(ind_id, {})
        val = _fmt_val(ind.get("value"), ind.get("unit", ""))
        prev = _fmt_val(ind.get("prev"), ind.get("unit", ""))
        change = ind.get("change", "")
        direction = ind.get("direction", "")
        ra = ind.get("risk_asset", ind.get("status", ""))
        lines.append(
            f"| {ind_id} | {ind.get('name', '')} | {val} | {prev} "
            f"| {change} | {direction} | {ra} |"
        )
    lines.append("")
    risk_count = regime.get("score", "?")
    lines.append(f"**위험자산 방향: {risk_count}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 5. Layer C (교차검증) ──
    lines.append("## 5. Layer C — 교차 검증")
    lines.append("")
    lines.append("| ID | 지표 | 현재값 | 방향 | 교차 | 비고 |")
    lines.append("|-----|------|--------|------|------|------|")
    for ind_id in LAYER_C:
        ind = data.get(ind_id, {})
        val = _fmt_val(ind.get("value"), ind.get("unit", ""))
        lines.append(
            f"| {ind_id} | {ind.get('name', '')} | {val} "
            f"| {ind.get('direction', '')} | {ind.get('cross', '')} "
            f"| {ind.get('note', '')} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 6. Layer D (배경) ──
    lines.append("## 6. Layer D — 배경")
    lines.append("")
    lines.append("| ID | 지표 | 현재값 | 방향 | 비고 |")
    lines.append("|-----|------|--------|------|------|")
    for ind_id in LAYER_D:
        ind = data.get(ind_id, {})
        val = _fmt_val(ind.get("value"), ind.get("unit", ""))
        lines.append(
            f"| {ind_id} | {ind.get('name', '')} | {val} "
            f"| {ind.get('direction', '')} | {ind.get('note', '')} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 7. 검증 ──
    lines.append("## 7. 검증")
    lines.append("")
    lines.append(f"- 데이터 기준일: {basis}")
    lines.append(f"- 전주 기준일: {prev_date}")
    lines.append(f"- 전체 신뢰도: {data.get('confidence', '?')}")
    lines.append(f"- 다음 갱신: {data.get('next_update', '?')}")
    lines.append("")

    # ── 푸터 ──
    lines.append("---")
    lines.append("")
    lines.append(f"*생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                 f"macro v3.0 | TEMPLATE-macro-report.md 준수*")

    return "\n".join(lines)


def _build_headline(data, regime):
    """핵심 3줄 + 해석 생성."""
    status = regime.get("status", "?")
    score = regime.get("score", "?")
    quadrant = regime.get("quadrant", "")
    dominant = regime.get("dominant_path", "?")
    disruption = regime.get("disruption", "없음")
    trigger = regime.get("transition_trigger", "?")

    line1 = f"**1줄:** {status} ({score}). {quadrant}."
    line2 = f"**2줄:** 지배경로 {dominant}. 교란: {disruption}."
    line3 = f"**3줄:** 다음 감시 — {trigger}."

    return f"{line1}\n\n{line2}\n\n{line3}"


def _gate_icon(val):
    """L7/L8 값에 따른 게이트 아이콘."""
    if not isinstance(val, (int, float)):
        return ""
    if val >= 0.60:
        return "🔴"
    elif val >= 0.40:
        return "🟡"
    return "🟢"


def _indicator_row(ind_id, ind):
    """Layer A 지표 행 생성."""
    val = _fmt_val(ind.get("value"), ind.get("unit", ""))
    return (
        f"| {ind_id} | {ind.get('name', '')} | {val} "
        f"| {ind.get('direction', '')} | {ind.get('status', ind.get('risk_asset', ''))} "
        f"| {ind.get('note', '')} |"
    )


def _fmt_val(value, unit=""):
    """값 + 단위 포맷."""
    if value is None:
        return "⚫ 미수집"
    if isinstance(value, float):
        formatted = f"{value:,.2f}" if abs(value) < 100 else f"{value:,.1f}"
    elif isinstance(value, int):
        formatted = f"{value:,}"
    else:
        formatted = str(value)
    return f"{formatted}{unit}" if unit else formatted


# ── HTML 렌더링 ──────────────────────────────────────

def render_html(md_content, data):
    """MD → HTML (다크 테마)."""
    regime = data.get("regime", {})
    date_str = data.get("date", "????-??-??")
    status = regime.get("status", "")

    # 레짐에 따른 accent color
    if "🟢" in status:
        accent = "#4ade80"
        accent_bg = "rgba(74,222,128,0.1)"
    elif "🔴" in status:
        accent = "#f87171"
        accent_bg = "rgba(248,113,113,0.1)"
    else:
        accent = "#facc15"
        accent_bg = "rgba(250,204,21,0.1)"

    # 간단한 MD → HTML 변환 (테이블 + 헤더 + 볼드)
    html_body = _md_to_html(md_content)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Weekly — {date_str}</title>
<style>
  :root {{
    --bg: #0f0f0f;
    --surface: #1a1a1a;
    --border: #2a2a2a;
    --text: #e0e0e0;
    --text-dim: #888;
    --accent: {accent};
    --accent-bg: {accent_bg};
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.7;
    padding: 2rem;
    max-width: 960px;
    margin: 0 auto;
  }}
  h1 {{
    color: var(--accent);
    font-size: 1.6rem;
    border-bottom: 2px solid var(--accent);
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
  }}
  h2 {{
    color: var(--accent);
    font-size: 1.2rem;
    margin-top: 2rem;
    margin-bottom: 0.8rem;
    padding-left: 0.5rem;
    border-left: 3px solid var(--accent);
  }}
  p {{ margin-bottom: 0.8rem; }}
  strong {{ color: #fff; }}
  hr {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.9rem;
  }}
  th {{
    background: var(--surface);
    color: var(--accent);
    padding: 0.6rem 0.8rem;
    text-align: left;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
  }}
  td {{
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  tr:hover td {{ background: var(--accent-bg); }}
  ul, ol {{ padding-left: 1.5rem; margin-bottom: 0.8rem; }}
  li {{ margin-bottom: 0.3rem; }}
  code {{
    background: var(--surface);
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    font-size: 0.85em;
  }}
  .footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 0.8rem;
    text-align: center;
  }}
</style>
</head>
<body>
{html_body}
<div class="footer">
  macro v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')} | TEMPLATE-macro-report.md
</div>
</body>
</html>"""
    return html


def _md_to_html(md):
    """간이 MD → HTML 변환."""
    import re
    lines = md.split("\n")
    html_parts = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # 테이블 행
        if stripped.startswith("|") and stripped.endswith("|"):
            if "|---" in stripped or "|----" in stripped or "|:---" in stripped:
                continue  # separator 무시
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not in_table:
                in_table = True
                table_rows = []
                # 첫 행 = 헤더
                header = "".join(f"<th>{c}</th>" for c in cells)
                table_rows.append(f"<thead><tr>{header}</tr></thead><tbody>")
            else:
                row = "".join(f"<td>{c}</td>" for c in cells)
                table_rows.append(f"<tr>{row}</tr>")
            continue

        # 테이블 끝
        if in_table:
            table_rows.append("</tbody>")
            html_parts.append(f"<table>{''.join(table_rows)}</table>")
            in_table = False
            table_rows = []

        # 헤더
        if stripped.startswith("# "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped == "---":
            html_parts.append("<hr>")
        elif stripped.startswith("- "):
            html_parts.append(f"<ul><li>{stripped[2:]}</li></ul>")
        elif stripped.startswith("**") and stripped.endswith("**"):
            html_parts.append(f"<p><strong>{stripped[2:-2]}</strong></p>")
        elif stripped:
            # 인라인 bold
            processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            html_parts.append(f"<p>{processed}</p>")

    # 잔여 테이블 닫기
    if in_table:
        table_rows.append("</tbody>")
        html_parts.append(f"<table>{''.join(table_rows)}</table>")

    return "\n".join(html_parts)


# ── 메인 ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="macro 보고서 렌더러")
    parser.add_argument("--md-only", action="store_true", help="MD만 생성")
    parser.add_argument("--html-only", action="store_true", help="HTML만 생성")
    parser.add_argument("--output-dir", "-o", help="출력 디렉토리 (기본: reports/)")
    args = parser.parse_args()

    data = load_latest()
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    output_dir = Path(args.output_dir) if args.output_dir else REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    md_content = render_md(data)

    if not args.html_only:
        md_path = output_dir / f"{date_str}_macro-weekly.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ MD 생성: {md_path}")

    if not args.md_only:
        html_content = render_html(md_content, data)
        html_path = output_dir / f"{date_str}_macro-weekly.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ HTML 생성: {html_path}")


if __name__ == "__main__":
    main()
