"""
visualize_transition.py — 1년 전이 경로 시각화
===============================================
v_transition_timeline 뷰에서 데이터 조회 → 시각화 JSON + HTML 생성

사용법:
  python visualize_transition.py             # JSON + HTML 생성
  python visualize_transition.py --json-only # JSON만 생성
  python visualize_transition.py --open      # 생성 후 브라우저 열기
"""

import json
import os
import sys
import argparse
import subprocess
from datetime import date, timedelta
from decimal import Decimal

import psycopg2

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
OUTPUT_DIR = os.path.join(TRACKING, "reports")
CARDS_DIR = os.path.join(TRACKING, "cards")

# ── DB ──
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "invest_ontology",
    "user": "investor",
    "password": "invest2025!secure",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return str(obj)
        return super().default(obj)


# ============================================================
# 1. 데이터 수집
# ============================================================
def collect_transition_data(conn):
    """v_transition_timeline + 관련 데이터를 수집하여 시각화 JSON 생성."""
    cur = conn.cursor()

    # TH 타임라인
    cur.execute("SELECT * FROM v_transition_timeline")
    columns = [desc[0] for desc in cur.description]
    th_rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    # Prediction 통계
    cur.execute("""
        SELECT status, count(*) FROM predictions GROUP BY status
    """)
    pred_stats = dict(cur.fetchall())

    # Learning log (conviction templates)
    cur.execute("""
        SELECT rule_id, pattern, correction, pred_type, hit_rate_before
        FROM learning_log WHERE rule_id LIKE 'LS-%'
    """)
    templates = [dict(zip(["rule_id", "pattern", "correction", "pred_type", "hit_rate"],
                          row)) for row in cur.fetchall()]

    # 전체 적중률
    cur.execute("""
        SELECT count(*) FILTER (WHERE status = 'hit') as hits,
               count(*) FILTER (WHERE status = 'partial') as partials,
               count(*) FILTER (WHERE status IN ('hit','miss','partial','expired')) as resolved
        FROM predictions
    """)
    hits, partials, resolved = cur.fetchone()
    overall_hr = None
    if resolved and resolved > 0:
        overall_hr = round((hits * 1.0 + partials * 0.5) / resolved, 3)

    # Watch 통계
    cur.execute("SELECT count(*) FROM watches WHERE status = 'active'")
    active_watches = cur.fetchone()[0]

    return {
        "th_rows": th_rows,
        "pred_stats": pred_stats,
        "templates": templates,
        "overall_hit_rate": overall_hr,
        "resolved_count": resolved or 0,
        "active_watches": active_watches,
    }


def build_path(conn, th_row):
    """TH 1건의 시각화 경로 데이터 구성."""
    cur = conn.cursor()
    th_id = th_row["th_id"]

    # 수렴 멤버
    cur.execute("""
        SELECT tc_id, role FROM th_tc_links
        WHERE th_id = %s ORDER BY role, tc_id
    """, (th_id,))
    members = [{"tc_id": r[0], "role": r[1]} for r in cur.fetchall()]

    # 증거 이력
    cur.execute("""
        SELECT ev_date, ev_type, description, confidence_delta, confidence_after
        FROM th_evidence WHERE th_id = %s
        ORDER BY ev_date, id
    """, (th_id,))
    evidence_trail = []
    for ev_date, ev_type, desc, delta, after in cur.fetchall():
        evidence_trail.append({
            "date": str(ev_date),
            "type": ev_type,
            "description": desc[:100] if desc else "",
            "delta": float(delta) if delta else 0,
            "confidence_after": float(after) if after else None,
        })

    # 연결된 Predictions
    cur.execute("""
        SELECT p.pred_id, p.tc_id, p.claim, p.scenario, p.probability,
               p.trigger_condition, p.deadline, p.status
        FROM predictions p
        JOIN th_tc_links tl ON tl.tc_id = p.tc_id
        WHERE tl.th_id = %s
        ORDER BY p.deadline, p.scenario
    """, (th_id,))
    predictions = []
    for row in cur.fetchall():
        predictions.append({
            "pred_id": row[0], "tc_id": row[1], "claim": row[2],
            "scenario": row[3], "probability": row[4],
            "trigger": row[5], "deadline": str(row[6]), "status": row[7],
        })

    # waypoints: deadline 기반 분기점
    waypoints = []
    seen_dates = set()
    for p in predictions:
        if p["deadline"] not in seen_dates and p["status"] == "open":
            waypoints.append({
                "date": p["deadline"],
                "event": p["trigger"][:60] if p["trigger"] else p["claim"][:60],
                "branch": True,
                "predictions": [pp for pp in predictions if pp["deadline"] == p["deadline"]],
            })
            seen_dates.add(p["deadline"])
    waypoints.sort(key=lambda w: w["date"])

    # causal_chain (있으면)
    chain = th_row.get("causal_chain")
    chain_progress = []
    if chain and isinstance(chain, dict):
        for step in chain.get("steps", []):
            chain_progress.append({
                "order": step.get("order", 0),
                "description": step.get("description", ""),
                "estimated": step.get("estimated", ""),
                "active": False,  # 추후 ont_link 상태 연동
            })

    # kill conditions
    kills = th_row.get("kill_conditions", {})
    kc_zones = []
    if isinstance(kills, dict):
        for key, val in kills.items():
            if isinstance(val, dict):
                kc_zones.append({
                    "key": key,
                    "condition": val.get("condition", str(val)),
                    "weight": val.get("weight", -0.3),
                })
            else:
                kc_zones.append({"key": key, "condition": str(val), "weight": -0.3})

    return {
        "th_id": th_id,
        "hypothesis": th_row["hypothesis"],
        "confidence": float(th_row["confidence"]),
        "from_regime": th_row["from_regime"],
        "to_regime": th_row["to_regime"],
        "horizon": th_row["horizon"],
        "start_date": str(th_row["start_date"]),
        "target_date": str(th_row["target_date"]),
        "convergence_count": th_row["convergence_count"],
        "evidence_count": th_row["evidence_count"],
        "recent_delta_trend": float(th_row["recent_delta_trend"]) if th_row.get("recent_delta_trend") else 0,
        "members": members,
        "waypoints": waypoints,
        "chain_progress": chain_progress,
        "kc_zones": kc_zones,
        "evidence_trail": evidence_trail,
        "predictions": predictions,
    }


def generate_json(conn):
    """전체 시각화 JSON 생성."""
    data = collect_transition_data(conn)
    paths = []
    for th_row in data["th_rows"]:
        paths.append(build_path(conn, th_row))

    output = {
        "generated": str(date.today()),
        "horizon": f"{date.today().strftime('%Y-%m')} ~ {(date.today() + timedelta(days=365)).strftime('%Y-%m')}",
        "paths": paths,
        "summary": {
            "active_th": len(paths),
            "total_predictions": sum(data["pred_stats"].values()),
            "resolved_predictions": data["resolved_count"],
            "overall_hit_rate": data["overall_hit_rate"],
            "active_watches": data["active_watches"],
            "conviction_templates": len(data["templates"]),
        },
        "self_reinforcement": {
            "templates": data["templates"],
            "system_confidence_trend": (
                "rising" if paths and paths[0]["recent_delta_trend"] > 0
                else "falling" if paths and paths[0]["recent_delta_trend"] < 0
                else "stable"
            ),
        },
    }

    return output


# ============================================================
# 2. HTML 생성
# ============================================================
def generate_html(data):
    """시각화 HTML 생성."""
    paths_json = json.dumps(data, cls=DecimalEncoder, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Transition Path — {data['generated']}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e0e0e0; padding: 40px; }}
  h1 {{ color: #58a6ff; margin-bottom: 8px; font-size: 24px; }}
  h2 {{ color: #79c0ff; margin: 32px 0 16px; font-size: 18px; }}
  h3 {{ color: #8b949e; margin: 20px 0 8px; font-size: 14px; }}
  .subtitle {{ color: #8b949e; font-size: 13px; margin-bottom: 24px; }}

  .stats {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
  .stat {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 14px 20px; text-align: center; min-width: 120px; }}
  .stat .num {{ font-size: 24px; font-weight: 700; color: #58a6ff; }}
  .stat .label {{ font-size: 11px; color: #8b949e; margin-top: 2px; }}

  .path-card {{
    background: #161b22; border: 1px solid #21262d; border-radius: 12px;
    padding: 24px; margin: 16px 0;
  }}
  .path-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
  .path-title {{ font-size: 16px; font-weight: 600; color: #e6edf3; }}
  .confidence-badge {{
    font-size: 14px; font-weight: 700; padding: 4px 12px; border-radius: 16px;
  }}
  .conf-high {{ background: #1a4731; color: #56d364; }}
  .conf-mid {{ background: #3d2e00; color: #e3b341; }}
  .conf-low {{ background: #3d1e20; color: #f85149; }}

  .regime-flow {{
    display: flex; align-items: center; gap: 12px; margin: 12px 0;
    font-size: 14px;
  }}
  .regime {{ padding: 4px 12px; border-radius: 6px; font-weight: 600; }}
  .regime-from {{ background: #21262d; color: #8b949e; }}
  .regime-to {{ background: #1f3a5f; color: #58a6ff; }}
  .arrow {{ color: #484f58; font-size: 20px; }}

  .timeline {{
    position: relative; margin: 20px 0 20px 20px;
    border-left: 2px solid #30363d; padding-left: 24px;
  }}
  .timeline-item {{
    position: relative; margin-bottom: 20px;
  }}
  .timeline-item::before {{
    content: ''; position: absolute; left: -31px; top: 4px;
    width: 12px; height: 12px; border-radius: 50%;
    border: 2px solid #58a6ff; background: #0f0f23;
  }}
  .timeline-item.branch::before {{ background: #e3b341; border-color: #e3b341; }}
  .timeline-item.evidence::before {{ background: #56d364; border-color: #56d364; width: 8px; height: 8px; left: -29px; top: 6px; }}
  .timeline-date {{ font-size: 11px; color: #6e7681; }}
  .timeline-event {{ font-size: 13px; color: #c9d1d9; margin-top: 2px; }}
  .timeline-detail {{ font-size: 12px; color: #8b949e; margin-top: 2px; }}

  .chain {{
    display: flex; gap: 8px; align-items: center; margin: 16px 0; flex-wrap: wrap;
  }}
  .chain-step {{
    padding: 6px 12px; border-radius: 6px; font-size: 12px;
    border: 1px solid #30363d; color: #8b949e;
  }}
  .chain-step.active {{ background: #1a4731; color: #56d364; border-color: #56d364; }}
  .chain-arrow {{ color: #484f58; }}

  .kc-zone {{
    background: #3d1e20; border: 1px solid #f8514933;
    border-radius: 6px; padding: 8px 12px; margin: 4px 0;
    font-size: 12px; color: #f85149;
  }}

  .members {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }}
  .member-tag {{
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    background: #1f3a5f; color: #58a6ff;
  }}
  .member-tag.cascade {{ background: #3d2e00; color: #e3b341; }}

  .section {{ margin: 24px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0; }}
  th {{ text-align: left; padding: 8px; background: #161b22; color: #79c0ff; border-bottom: 1px solid #30363d; }}
  td {{ padding: 8px; border-bottom: 1px solid #21262d; color: #c9d1d9; }}
</style>
</head>
<body>

<h1>Transition Path Visualization</h1>
<div class="subtitle">Generated {data['generated']} | Horizon: {data['horizon']}</div>

<div class="stats">
  <div class="stat"><div class="num">{data['summary']['active_th']}</div><div class="label">Active TH</div></div>
  <div class="stat"><div class="num">{data['summary']['total_predictions']}</div><div class="label">Predictions</div></div>
  <div class="stat"><div class="num">{data['summary']['resolved_predictions']}</div><div class="label">Resolved</div></div>
  <div class="stat"><div class="num">{f"{data['summary']['overall_hit_rate']:.0%}" if data['summary']['overall_hit_rate'] else 'N/A'}</div><div class="label">Hit Rate</div></div>
  <div class="stat"><div class="num">{data['summary']['active_watches']}</div><div class="label">Active Watches</div></div>
  <div class="stat"><div class="num">{data['summary']['conviction_templates']}</div><div class="label">Convictions</div></div>
</div>
"""

    for path in data["paths"]:
        conf = path["confidence"]
        conf_class = "conf-high" if conf >= 0.6 else "conf-mid" if conf >= 0.3 else "conf-low"
        trend = path["recent_delta_trend"]
        trend_icon = "&#x25B2;" if trend > 0 else "&#x25BC;" if trend < 0 else "&#x25C6;"

        html += f"""
<div class="path-card">
  <div class="path-header">
    <div class="path-title">{path['th_id']}: {path['hypothesis'][:70]}</div>
    <div class="confidence-badge {conf_class}">{conf:.1%} {trend_icon}</div>
  </div>

  <div class="regime-flow">
    <span class="regime regime-from">{path['from_regime']}</span>
    <span class="arrow">&#x2192;</span>
    <span class="regime regime-to">{path['to_regime']}</span>
    <span style="color:#6e7681; font-size:12px;">({path['horizon']}, target: {path['target_date'][:10]})</span>
  </div>

  <div class="members">
"""
        for m in path["members"]:
            cls = "cascade" if m["role"] == "cascade_target" else ""
            html += f'    <span class="member-tag {cls}">{m["tc_id"]}</span>\n'

        html += "  </div>\n"

        # Causal chain
        if path["chain_progress"]:
            html += '  <h3>Causal Chain</h3>\n  <div class="chain">\n'
            for i, step in enumerate(path["chain_progress"]):
                cls = "active" if step["active"] else ""
                html += f'    <span class="chain-step {cls}">{step["description"]}</span>\n'
                if i < len(path["chain_progress"]) - 1:
                    html += '    <span class="chain-arrow">&#x2192;</span>\n'
            html += "  </div>\n"

        # Timeline: waypoints + evidence merged
        html += '  <h3>Timeline</h3>\n  <div class="timeline">\n'

        # 증거 + waypoints를 시간순 정렬
        timeline_items = []
        for ev in path["evidence_trail"]:
            timeline_items.append({
                "date": ev["date"], "type": "evidence",
                "text": ev["description"][:60],
                "detail": f"[{ev['type']}] delta={ev['delta']:+.3f}" if ev["delta"] else "",
            })
        for wp in path["waypoints"]:
            timeline_items.append({
                "date": wp["date"], "type": "branch",
                "text": wp["event"],
                "detail": f"{len(wp['predictions'])} predictions at this point",
            })
        timeline_items.sort(key=lambda x: x["date"])

        for item in timeline_items:
            cls = item["type"]
            html += f"""    <div class="timeline-item {cls}">
      <div class="timeline-date">{item['date']}</div>
      <div class="timeline-event">{item['text']}</div>
      <div class="timeline-detail">{item['detail']}</div>
    </div>\n"""

        html += "  </div>\n"

        # KC zones
        if path["kc_zones"]:
            html += "  <h3>Kill Conditions</h3>\n"
            for kc in path["kc_zones"]:
                html += f'  <div class="kc-zone">&#x26A0; {kc["condition"]} (weight: {kc["weight"]})</div>\n'

        # Predictions table
        if path["predictions"]:
            html += """  <h3>Linked Predictions</h3>
  <table>
    <tr><th>ID</th><th>TC</th><th>Scenario</th><th>Claim</th><th>Prob</th><th>Deadline</th><th>Status</th></tr>
"""
            for p in path["predictions"]:
                status_color = {"open": "#8b949e", "hit": "#56d364", "miss": "#f85149", "partial": "#e3b341", "expired": "#6e7681"}.get(p["status"], "#8b949e")
                html += f'    <tr><td>{p["pred_id"][-3:]}</td><td>{p["tc_id"]}</td><td>{p["scenario"]}</td><td>{p["claim"][:40]}</td><td>{p["probability"]}</td><td>{p["deadline"][:10]}</td><td style="color:{status_color}">{p["status"]}</td></tr>\n'
            html += "  </table>\n"

        html += "</div>\n"

    html += """
<div class="section">
  <h2>Self-Reinforcement Status</h2>
  <table>
    <tr><th>Type</th><th>Pattern</th><th>Boost</th><th>Hit Rate</th></tr>
"""
    for t in data.get("self_reinforcement", {}).get("templates", []):
        html += f'    <tr><td>{t["rule_id"]}</td><td>{t["pattern"][:60]}</td><td>{t.get("correction","")}</td><td>{t.get("hit_rate","N/A")}</td></tr>\n'

    if not data.get("self_reinforcement", {}).get("templates"):
        html += '    <tr><td colspan="4" style="color:#6e7681">No conviction templates yet. Need 5+ resolved predictions with 60%+ hit rate.</td></tr>\n'

    html += """  </table>
</div>

</body>
</html>"""

    return html


# ============================================================
# 3. 메인
# ============================================================
def run(json_only=False, open_browser=False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = get_conn()

    try:
        print("━━ Transition Path Visualization ━━\n")

        data = generate_json(conn)

        # JSON 저장
        json_path = os.path.join(OUTPUT_DIR, f"transition-{date.today()}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=DecimalEncoder, ensure_ascii=False, indent=2)
        print(f"  JSON: {json_path}")

        if not json_only:
            # HTML 저장
            html = generate_html(data)
            html_path = os.path.join(OUTPUT_DIR, f"transition-{date.today()}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  HTML: {html_path}")

            if open_browser:
                subprocess.run(["start", "", html_path], shell=True)
                print("  브라우저 열기 완료")

        # 요약
        print(f"\n  TH: {data['summary']['active_th']}건")
        print(f"  Predictions: {data['summary']['total_predictions']}건 (resolved: {data['summary']['resolved_predictions']})")
        print(f"  Hit Rate: {data['summary']['overall_hit_rate'] or 'N/A'}")
        print(f"  Watches: {data['summary']['active_watches']}건")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transition Path Visualization")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    run(json_only=args.json_only, open_browser=args.open)
