"""
psf-monitor 자율 운영 — 이상 감지 + 세션 요약

사용법:
  python core/autonomy.py scan       # 이상 감지 (state.json 기반)
  python core/autonomy.py summary    # 자율 행동 세션 요약
  python core/autonomy.py status     # 시스템 상태 한 줄 출력
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"
PROJECTION_FILE = BASE_DIR / "projection.json"
HISTORY_DIR = BASE_DIR / "history"
MACRO_LATEST = Path(r"C:\Users\이미영\Downloads\에이전트\macro\indicators\latest.json")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class AnomalyScanner:
    """GUARDRAILS.md 이상 감지 트리거 구현."""

    def __init__(self, state: dict, prev_snapshot: dict | None = None):
        self.state = state
        self.prev = prev_snapshot
        self.alerts = []

    def scan_all(self) -> list[dict]:
        self._check_data_anomaly()
        self._check_regime_jump()
        self._check_macro_paradox()
        self._check_mcp_failures()
        self._check_link_cascade()
        return self.alerts

    def _alert(self, level: int, trigger: str, detail: str):
        level_names = {1: "경미", 2: "주의", 3: "심각", 4: "긴급"}
        self.alerts.append({
            "level": level,
            "level_name": level_names.get(level, "?"),
            "trigger": trigger,
            "detail": detail,
            "timestamp": datetime.now().isoformat()
        })

    def _check_data_anomaly(self):
        """지표값 50% 이상 변동 감지."""
        if not self.prev:
            return
        for layer_key in ["structure", "flow"]:
            curr_layer = self.state.get(layer_key, {})
            prev_layer = self.prev.get(layer_key, {})
            for prop_id in curr_layer:
                if prop_id == "verdict":
                    continue
                curr_item = curr_layer.get(prop_id, {})
                prev_item = prev_layer.get(prop_id, {})
                if not isinstance(curr_item, dict) or not isinstance(prev_item, dict):
                    continue
                curr_val = curr_item.get("value")
                prev_val = prev_item.get("value")
                try:
                    c = float(curr_val) if curr_val is not None else None
                    p = float(prev_val) if prev_val is not None else None
                    if c and p and p != 0:
                        change_pct = abs((c - p) / p) * 100
                        if change_pct > 50:
                            label = curr_layer.get(prop_id, {}).get("label", prop_id)
                            self._alert(3, "데이터 이상",
                                        f"{label}: {p} → {c} ({change_pct:.0f}% 변동). 수치 오류 가능.")
                except (TypeError, ValueError):
                    pass

    def _check_regime_jump(self):
        """국면 급변 감지 (🟢→🔴 또는 🔴→🟢)."""
        if not self.prev:
            return
        curr_regime = self.state.get("regime", "")
        prev_regime = self.prev.get("regime", "")

        curr_level = 0 if "🟢" in curr_regime else (1 if "🟡" in curr_regime else (2 if "🔴" in curr_regime else -1))
        prev_level = 0 if "🟢" in prev_regime else (1 if "🟡" in prev_regime else (2 if "🔴" in prev_regime else -1))

        if abs(curr_level - prev_level) >= 2:
            self._alert(3, "국면 급변",
                        f"{prev_regime} → {curr_regime}. 2단계 이상 점프. 데이터 재확인 필요.")

    def _check_macro_paradox(self):
        """macro 🟢 + PSF 🔴 역설 감지."""
        macro_info = self.state.get("macro_interface", {})
        macro_regime = macro_info.get("macro_regime", "")
        psf_regime = self.state.get("regime", "")

        if "🟢" in macro_regime and "🔴" in psf_regime:
            self._alert(3, "macro-PSF 역설",
                        f"macro {macro_regime} + PSF {psf_regime}. 극히 드문 조합. 데이터 오류 가능.")

    def _check_mcp_failures(self):
        """MCP 대량 실패 감지."""
        quality = self.state.get("quality", {})
        failed = quality.get("sources_attempted_failed", [])
        if len(failed) >= 3:
            self._alert(2, "MCP 대량 실패",
                        f"{len(failed)}건 실패: {', '.join(failed[:5])}. 관측 품질 저하.")

    def _check_link_cascade(self):
        """L8 + CorrFlip 동시 활성 → 위기 진입."""
        links = self.state.get("links", {})
        l8_active = links.get("L8", {}).get("status") == "active"
        corrflip_active = links.get("corrflip", {}).get("status") == "active"
        l7_active = (links.get("L7_acute", {}).get("status") == "active" or
                     links.get("L7_chronic", {}).get("status") == "active")

        if l8_active and corrflip_active:
            self._alert(4, "위기 진입",
                        "L8 + CorrFlip 동시 활성. 🔴 위기. 모든 관측 정지. 사용자 개입 필요.")
        elif l8_active:
            self._alert(3, "L8 활성",
                        "L8 위기 Link 활성. 🔴 위기 진입 가능.")
        elif corrflip_active and l7_active:
            self._alert(3, "CorrFlip + L7",
                        "상관 붕괴 + 공포 동시. 🔴 위기 접근.")


def find_prev_snapshot() -> dict | None:
    if not HISTORY_DIR.exists():
        return None
    snapshots = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)
    today_str = date.today().isoformat()
    for snap_path in snapshots:
        if snap_path.stem != today_str:
            data = load_json(snap_path)
            if data:
                return data
    return None


def scan():
    """이상 감지 실행."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 없음")
        sys.exit(1)

    prev = find_prev_snapshot()
    scanner = AnomalyScanner(state, prev)
    alerts = scanner.scan_all()

    if not alerts:
        print("✅ 이상 감지: 없음")
        return

    print(f"\n{'='*60}")
    print(f"⚠  이상 감지: {len(alerts)}건")
    print(f"{'='*60}")

    for alert in sorted(alerts, key=lambda a: -a["level"]):
        level_icon = {1: "🟢", 2: "🟡", 3: "🔴", 4: "🚨"}.get(alert["level"], "?")
        print(f"\n{level_icon} Level {alert['level']} ({alert['level_name']}): {alert['trigger']}")
        print(f"   {alert['detail']}")

    # Level 3+ 있으면 경고
    severe = [a for a in alerts if a["level"] >= 3]
    if severe:
        print(f"\n🔴 Level 3+ 이상 {len(severe)}건 — 사용자 확인 필요")
        sys.exit(1)


def summary():
    """시스템 상태 요약."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 없음")
        return

    regime = state.get("regime", "미확인")
    macro_info = state.get("macro_interface", {})
    macro_regime = macro_info.get("macro_regime", "미확인")
    alignment = macro_info.get("alignment", "미확인")

    links = state.get("links", {})
    active_links = [k for k, v in links.items() if v.get("status") == "active"]

    questions = state.get("next_questions", [])
    open_q = [q for q in questions if q.get("status") == "open"]
    deadline_q = [q for q in open_q
                  if q.get("deadline") and q["deadline"] <= date.today().isoformat()]

    obs_count = len(state.get("observations", []))
    div_count = len(state.get("divergences", []))
    uc_count = len(state.get("unclassified", []))

    # macro 신선도
    macro_data = load_json(MACRO_LATEST)
    macro_fresh = "미확인"
    if macro_data and "date" in macro_data:
        try:
            macro_date = datetime.strptime(macro_data["date"], "%Y-%m-%d")
            age = (datetime.now() - macro_date).days
            macro_fresh = f"fresh ({age}일)" if age <= 3 else (f"⚠️ stale ({age}일)" if age <= 7 else f"🔴 expired ({age}일)")
        except ValueError:
            macro_fresh = "날짜 오류"

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 시스템 상태 ({date.today().isoformat()})")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"국면: {regime} | macro: {macro_regime} | 정합: {alignment}")
    print(f"macro 신선도: {macro_fresh}")
    print(f"Link: {', '.join(active_links) if active_links else '없음'}")
    print(f"관측: {obs_count}건 | Divergence: {div_count}건 | 미분류: {uc_count}건")
    print(f"질문: {len(open_q)}건 open ({len(deadline_q)}건 deadline 도래)")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def status():
    """한 줄 상태."""
    state = load_json(STATE_FILE)
    if state is None:
        print("PSF: state.json 없음")
        return

    regime = state.get("regime", "?")
    links = state.get("links", {})
    active = sum(1 for v in links.values() if isinstance(v, dict) and v.get("status") == "active")
    questions = len([q for q in state.get("next_questions", []) if q.get("status") == "open"])
    updated = state.get("last_updated", "?")

    print(f"PSF {regime} | Link {active}건 활성 | 질문 {questions}건 | {updated}")


def main():
    if len(sys.argv) < 2:
        print("사용법: python core/autonomy.py [scan|summary|status]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "scan":
        scan()
    elif cmd == "summary":
        summary()
    elif cmd == "status":
        status()
    else:
        print(f"알 수 없는 명령: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
