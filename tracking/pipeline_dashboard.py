"""
pipeline_dashboard.py — 파이프라인 실행 실시간 대시보드
======================================================
파이프라인 실행 중 Agent 상태, 타이밍, 핵심 발견을 시각화.
오케스트레이터가 각 Phase 전환 시 update()를 호출.

사용법:
  from pipeline_dashboard import PipelineDashboard
  dash = PipelineDashboard(date="2026-03-28", topics=["이란","TLT","AI"])
  dash.update_agent("RM-1", status="running", model="sonnet")
  dash.update_agent("RM-1", status="completed", duration="8m36s", findings=["..."])
  dash.render()  # HTML 갱신

CLI:
  python pipeline_dashboard.py --status   # 현재 상태 출력
  python pipeline_dashboard.py --open     # 브라우저 열기
"""

import json
import os
import sys
from datetime import datetime

BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
DASH_PATH = os.path.join(BASE, "tracking", "reports", "pipeline-live.html")
STATE_PATH = os.path.join(BASE, "tracking", "reports", "pipeline-state.json")


class PipelineDashboard:
    def __init__(self, date=None, topics=None, mode="A"):
        self.state = {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "mode": mode,
            "topics": topics or [],
            "started": datetime.now().isoformat(),
            "current_phase": "Phase 0",
            "phases": {
                "phase0": {"status": "pending", "label": "Phase 0: 사전 점검"},
                "phase1": {"status": "pending", "label": "Phase 1: Scanner + Macro"},
                "selection": {"status": "pending", "label": "사용자 선택"},
                "phase2": {"status": "pending", "label": "Phase 2: RM + Core + PSF"},
                "phase3a": {"status": "pending", "label": "Phase 3-A: Stereo L1~L6"},
                "phase3b": {"status": "pending", "label": "Phase 3-B: L7 통합 (Opus)"},
                "phase4": {"status": "pending", "label": "Phase 4: 저장 + DB sync"},
            },
            "agents": {},
            "priority_gaps": [],
            "total_mcp": 0,
            "total_tokens": 0,
        }
        self._save_state()

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def set_phase(self, phase_key, status="running"):
        if phase_key in self.state["phases"]:
            self.state["phases"][phase_key]["status"] = status
            if status == "running":
                self.state["current_phase"] = self.state["phases"][phase_key]["label"]
                self.state["phases"][phase_key]["started_at"] = datetime.now().isoformat()
            elif status == "completed":
                self.state["phases"][phase_key]["completed_at"] = datetime.now().isoformat()
        self._save_state()

    def set_gaps(self, gaps):
        self.state["priority_gaps"] = gaps
        self._save_state()

    def update_agent(self, agent_id, status="running", model="sonnet",
                     topic="", duration="", tools=0, mcp=0, tokens=0,
                     findings=None, key_signal=""):
        if agent_id not in self.state["agents"]:
            self.state["agents"][agent_id] = {
                "status": "pending",
                "model": model,
                "topic": topic,
                "started_at": None,
                "duration": "",
                "tools": 0,
                "mcp": 0,
                "tokens": 0,
                "findings": [],
                "key_signal": "",
            }

        agent = self.state["agents"][agent_id]
        agent["status"] = status
        agent["model"] = model
        if topic:
            agent["topic"] = topic
        if status == "running" and not agent["started_at"]:
            agent["started_at"] = datetime.now().isoformat()
        if duration:
            agent["duration"] = duration
        if tools:
            agent["tools"] = tools
        if mcp:
            agent["mcp"] = mcp
            self.state["total_mcp"] += mcp
        if tokens:
            agent["tokens"] = tokens
            self.state["total_tokens"] += tokens
        if findings:
            agent["findings"] = findings
        if key_signal:
            agent["key_signal"] = key_signal

        self._save_state()

    def render(self, open_browser=False):
        s = self.state
        now = datetime.now().strftime("%H:%M:%S")

        # Agent 통계
        agents = s["agents"]
        total = len(agents)
        running = sum(1 for a in agents.values() if a["status"] == "running")
        completed = sum(1 for a in agents.values() if a["status"] == "completed")
        pending = sum(1 for a in agents.values() if a["status"] == "pending")

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>Pipeline Live — {s['date']}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',sans-serif; background:#0a0a1a; color:#e0e0e0; padding:24px; }}
  h1 {{ color:#58a6ff; font-size:22px; margin-bottom:4px; }}
  .sub {{ color:#8b949e; font-size:13px; margin-bottom:20px; }}
  .stats {{ display:flex; gap:12px; margin:16px 0; flex-wrap:wrap; }}
  .stat {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:12px 18px; text-align:center; min-width:90px; }}
  .stat .num {{ font-size:22px; font-weight:700; color:#58a6ff; }}
  .stat .label {{ font-size:10px; color:#8b949e; }}

  .phases {{ display:flex; gap:4px; margin:16px 0; align-items:center; }}
  .phase {{
    padding:8px 14px; border-radius:6px; font-size:11px; font-weight:600;
    border:1px solid #21262d; background:#161b22; color:#6e7681;
    position:relative;
  }}
  .phase.running {{ background:#0d419d; color:#79c0ff; border-color:#1f6feb; animation:pulse 1.5s infinite; }}
  .phase.completed {{ background:#1a4731; color:#56d364; border-color:#238636; }}
  .phase.pending {{ opacity:0.5; }}
  .phase-arrow {{ color:#484f58; font-size:16px; }}
  @keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.7;}} }}

  .agents {{ margin:16px 0; }}
  .agent-row {{
    display:flex; align-items:center; gap:12px; padding:10px 16px;
    background:#161b22; border:1px solid #21262d; border-radius:8px; margin:6px 0;
    transition:all 0.3s;
  }}
  .agent-row.running {{ border-color:#1f6feb; background:#0d1b3d; }}
  .agent-row.completed {{ border-color:#238636; }}
  .agent-id {{ font-weight:700; min-width:70px; font-size:13px; }}
  .agent-id.running {{ color:#58a6ff; }}
  .agent-id.completed {{ color:#56d364; }}
  .agent-id.pending {{ color:#6e7681; }}
  .model-tag {{ font-size:10px; padding:2px 6px; border-radius:8px; }}
  .model-sonnet {{ background:#1f3a5f; color:#58a6ff; }}
  .model-opus {{ background:#3b1f5e; color:#a78bfa; }}
  .topic {{ font-size:12px; color:#c9d1d9; min-width:120px; }}
  .duration {{ font-size:12px; color:#8b949e; min-width:70px; }}
  .tools {{ font-size:11px; color:#6e7681; min-width:60px; }}
  .status-dot {{ width:8px; height:8px; border-radius:50%; }}
  .status-dot.running {{ background:#58a6ff; animation:pulse 1s infinite; }}
  .status-dot.completed {{ background:#56d364; }}
  .status-dot.pending {{ background:#484f58; }}
  .finding {{ font-size:11px; color:#e3b341; margin-top:4px; padding-left:82px; }}
  .signal {{ font-size:12px; color:#f0883e; font-weight:600; }}

  .gaps {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:14px; margin:16px 0; }}
  .gaps h3 {{ font-size:13px; color:#79c0ff; margin-bottom:8px; }}
  .gap-item {{ font-size:12px; color:#c9d1d9; padding:3px 0; }}
  .gap-icon {{ margin-right:6px; }}

  .timeline {{ margin:16px 0; }}
  .timeline h3 {{ font-size:13px; color:#79c0ff; margin-bottom:8px; }}
  .findings-list {{ padding-left:16px; }}
  .findings-list li {{ font-size:12px; color:#c9d1d9; padding:3px 0; list-style:none; }}
  .findings-list li::before {{ content:''; display:inline-block; width:6px; height:6px; border-radius:50%; background:#56d364; margin-right:8px; }}
</style>
</head>
<body>
<h1>Pipeline Live Dashboard</h1>
<div class="sub">{s['date']} | Mode {s['mode']} | {len(s['topics'])} topics: {', '.join(s['topics'])} | Updated {now}</div>

<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="label">Total Agents</div></div>
  <div class="stat"><div class="num" style="color:#58a6ff">{running}</div><div class="label">Running</div></div>
  <div class="stat"><div class="num" style="color:#56d364">{completed}</div><div class="label">Completed</div></div>
  <div class="stat"><div class="num">{s['total_mcp']}</div><div class="label">MCP Calls</div></div>
  <div class="stat"><div class="num">{s['total_tokens']//1000}K</div><div class="label">Tokens</div></div>
</div>

<div class="phases">
"""
        # Phase indicators
        phase_order = ["phase0", "phase1", "selection", "phase2", "phase3a", "phase3b", "phase4"]
        for i, pk in enumerate(phase_order):
            p = s["phases"][pk]
            cls = p["status"]
            html += f'  <div class="phase {cls}">{p["label"]}</div>\n'
            if i < len(phase_order) - 1:
                html += '  <span class="phase-arrow">&#x25B6;</span>\n'
        html += "</div>\n"

        # Priority gaps
        if s["priority_gaps"]:
            html += '<div class="gaps"><h3>Priority Gaps</h3>\n'
            for g in s["priority_gaps"][:5]:
                html += f'  <div class="gap-item"><span class="gap-icon">{g.get("icon","")}</span>{g.get("text","")}</div>\n'
            html += '</div>\n'

        # Agent rows
        html += '<div class="agents">\n'

        # Group by phase
        phase_groups = {
            "Phase 1": [], "Phase 2 RM": [], "Phase 2 Core": [],
            "Phase 3-A": [], "Phase 3-B": [], "Phase 4": [],
        }
        for aid, a in agents.items():
            if aid.startswith("Scanner") or aid.startswith("Macro"):
                phase_groups["Phase 1"].append((aid, a))
            elif aid.startswith("RM"):
                phase_groups["Phase 2 RM"].append((aid, a))
            elif aid.startswith("Core"):
                phase_groups["Phase 2 Core"].append((aid, a))
            elif aid.startswith("Stereo-L"):
                phase_groups["Phase 3-A"].append((aid, a))
            elif aid.startswith("Stereo-통합") or aid.startswith("L7"):
                phase_groups["Phase 3-B"].append((aid, a))
            else:
                phase_groups["Phase 4"].append((aid, a))

        for group_name, group_agents in phase_groups.items():
            if not group_agents:
                continue
            html += f'<div style="font-size:11px;color:#6e7681;margin:12px 0 4px;font-weight:600;">{group_name}</div>\n'
            for aid, a in group_agents:
                status = a["status"]
                model_cls = f"model-{a['model']}" if a["model"] in ("sonnet", "opus") else ""
                html += f"""<div class="agent-row {status}">
  <div class="status-dot {status}"></div>
  <div class="agent-id {status}">{aid}</div>
  <span class="model-tag {model_cls}">{a['model']}</span>
  <div class="topic">{a.get('topic','')}</div>
  <div class="duration">{a.get('duration','')}</div>
  <div class="tools">{a.get('tools','')} {'tool' if a.get('tools') else ''}</div>
"""
                if a.get("key_signal"):
                    html += f'  <div class="signal">{a["key_signal"]}</div>\n'
                html += "</div>\n"

                # Findings
                for finding in a.get("findings", []):
                    html += f'<div class="finding">{finding}</div>\n'

        html += '</div>\n'

        # Key findings timeline
        all_findings = []
        for aid, a in agents.items():
            if a["status"] == "completed" and a.get("key_signal"):
                all_findings.append({"agent": aid, "signal": a["key_signal"]})

        if all_findings:
            html += '<div class="timeline"><h3>Key Signals</h3><ul class="findings-list">\n'
            for f in all_findings:
                html += f'  <li><b>{f["agent"]}</b>: {f["signal"]}</li>\n'
            html += '</ul></div>\n'

        html += "</body></html>"

        os.makedirs(os.path.dirname(DASH_PATH), exist_ok=True)
        with open(DASH_PATH, "w", encoding="utf-8") as f:
            f.write(html)

        if open_browser:
            import subprocess
            subprocess.run(["start", "", DASH_PATH], shell=True)

        return DASH_PATH


def load_dashboard():
    """기존 state에서 대시보드 복원."""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        dash = PipelineDashboard.__new__(PipelineDashboard)
        dash.state = state
        return dash
    return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    if args.status:
        dash = load_dashboard()
        if dash:
            s = dash.state
            print(f"Pipeline {s['date']} | {s['current_phase']}")
            for aid, a in s["agents"].items():
                icon = {"running": "⏳", "completed": "✅", "pending": "⬜"}.get(a["status"], "?")
                print(f"  {icon} {aid} ({a['model']}) {a.get('duration','')} {a.get('key_signal','')}")
        else:
            print("No active pipeline")
    elif args.open:
        dash = load_dashboard()
        if dash:
            dash.render(open_browser=True)
        else:
            print("No active pipeline")
