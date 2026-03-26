"""
psf-monitor 스냅샷 관리

사용법:
  python core/snapshot.py save              # 오늘 스냅샷 저장 + delta 계산
  python core/snapshot.py delta             # 직전 대비 변화 출력
  python core/snapshot.py weekly-summary    # 주간 요약 저장
  python core/snapshot.py monthly-summary   # 월간 요약 저장
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"
HISTORY_DIR = BASE_DIR / "history"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 저장: {path}")


def find_prev_snapshot() -> tuple[Path | None, dict | None]:
    """가장 최근 스냅샷 찾기."""
    if not HISTORY_DIR.exists():
        return None, None
    snapshots = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)
    today_str = date.today().isoformat()
    for snap_path in snapshots:
        if snap_path.stem != today_str:
            data = load_json(snap_path)
            if data:
                return snap_path, data
    return None, None


def calc_delta(current: dict, prev: dict) -> dict:
    """현재 state와 이전 스냅샷 간 delta 계산."""
    delta = {
        "prev_date": prev.get("date", prev.get("last_updated", "unknown")),
        "regime_changed": current.get("regime", "") != prev.get("regime", ""),
        "new_links": [],
        "closed_links": [],
        "notable_changes": []
    }

    # Link 변화 감지
    curr_links = current.get("links", {})
    prev_links = prev.get("links", {})
    for link_id in set(list(curr_links.keys()) + list(prev_links.keys())):
        curr_status = curr_links.get(link_id, {}).get("status", "inactive")
        prev_status = prev_links.get(link_id, {}).get("status", "inactive")
        if curr_status == "active" and prev_status != "active":
            delta["new_links"].append(link_id)
        elif curr_status != "active" and prev_status == "active":
            delta["closed_links"].append(link_id)

    # S층 변화 감지
    for layer_key, layer_name in [("structure", "S"), ("flow", "F")]:
        curr_layer = current.get(layer_key, {})
        prev_layer = prev.get(layer_key, {})
        for prop_id in ["S1", "S2", "S3", "S4", "S5"] if layer_name == "S" else ["F1", "F2", "F3", "F4", "F5"]:
            curr_val = curr_layer.get(prop_id, {}).get("value")
            prev_val = prev_layer.get(prop_id, {}).get("value")
            if curr_val is not None and prev_val is not None:
                try:
                    curr_num = float(curr_val) if not isinstance(curr_val, str) else None
                    prev_num = float(prev_val) if not isinstance(prev_val, str) else None
                    if curr_num is not None and prev_num is not None and curr_num != prev_num:
                        label = curr_layer.get(prop_id, {}).get("label", prop_id)
                        diff = curr_num - prev_num
                        sign = "+" if diff > 0 else ""
                        delta["notable_changes"].append(
                            f"{label} {prev_num} → {curr_num} ({sign}{diff:.2f})"
                        )
                except (TypeError, ValueError):
                    pass

    return delta


def save_snapshot():
    """오늘 스냅샷 저장."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 파일 없음")
        sys.exit(1)

    today_str = date.today().isoformat()
    snapshot_path = HISTORY_DIR / f"{today_str}.json"

    # 이전 스냅샷과 delta 계산
    prev_path, prev_data = find_prev_snapshot()
    delta = {}
    if prev_data:
        delta = calc_delta(state, prev_data)

    # 스냅샷 구성
    observations = state.get("observations", [])
    top3 = [{"rank": o.get("rank", i+1), "signal": o.get("signal", ""),
             "severity": o.get("severity", "medium")}
            for i, o in enumerate(observations[:3])]

    links_active = [k for k, v in state.get("links", {}).items()
                    if v.get("status") == "active"]

    snapshot = {
        "date": today_str,
        "source": "psf D Loop",
        "regime": state.get("regime", "미확인"),
        "macro_regime": state.get("macro_interface", {}).get("macro_regime", "미확인"),
        "alignment": state.get("macro_interface", {}).get("alignment", "미확인"),
        "observations_top3": top3,
        "links_active": links_active,
        "divergences_count": len(state.get("divergences", [])),
        "unclassified_count": len(state.get("unclassified", [])),
        "questions_open": len([q for q in state.get("next_questions", [])
                               if q.get("status") == "open"]),
        "axis_snapshot": {
            k: v.get("status", "미확인")
            for k, v in state.get("axis_status", {}).items()
        },
        "delta_vs_prev": delta
    }

    save_json(snapshot_path, snapshot)

    # delta 출력
    if delta:
        print(f"\n📊 Delta vs {delta.get('prev_date', '?')}:")
        if delta.get("regime_changed"):
            print(f"  🔄 국면 변경!")
        if delta.get("new_links"):
            print(f"  🔴 새 Link 활성: {', '.join(delta['new_links'])}")
        if delta.get("closed_links"):
            print(f"  🟢 Link 비활성: {', '.join(delta['closed_links'])}")
        for change in delta.get("notable_changes", []):
            print(f"  📈 {change}")


def print_delta():
    """직전 대비 변화 출력."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 없음")
        return

    prev_path, prev_data = find_prev_snapshot()
    if prev_data is None:
        print("⚠ 이전 스냅샷 없음 — 비교 불가")
        return

    delta = calc_delta(state, prev_data)
    print(f"📊 Delta: {state.get('last_updated', '?')} vs {delta.get('prev_date', '?')}")
    print(f"  국면 변경: {'예' if delta.get('regime_changed') else '아니오'}")
    print(f"  새 Link: {delta.get('new_links', [])}")
    print(f"  종료 Link: {delta.get('closed_links', [])}")
    for change in delta.get("notable_changes", []):
        print(f"  {change}")


def save_weekly_summary():
    """주간 요약 저장."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 없음")
        return

    today = date.today()
    week_num = today.isocalendar()[1]
    year = today.isocalendar()[0]
    summary_path = HISTORY_DIR / f"{year}-W{week_num:02d}-summary.json"

    accum = state.get("accumulation", {}).get("weekly", {})

    summary = {
        "week": f"{year}-W{week_num:02d}",
        "period": accum.get("period", f"{today.isoformat()}"),
        "source": "psf W Loop",
        "regime_start": state.get("regime", "미확인"),
        "regime_end": state.get("regime", "미확인"),
        "regime_changed": False,
        "signal_counts": accum.get("signal_counts", {}),
        "top_observations": [o.get("signal", "") for o in state.get("observations", [])[:4]],
        "questions_resolved": [],
        "questions_new": [q.get("id", "") for q in state.get("next_questions", [])
                          if q.get("status") == "open"],
        "unclassified_resolved": 0,
        "unclassified_new": len(state.get("unclassified", [])),
        "errors_reviewed": {"new_errors": 0, "recurring_errors": [], "rules_added": []},
        "axis_psf_alignment": {"matrix": "미정", "note": ""}
    }

    save_json(summary_path, summary)


def save_monthly_summary():
    """월간 요약 저장."""
    state = load_json(STATE_FILE)
    if state is None:
        print("❌ state.json 없음")
        return

    today = date.today()
    summary_path = HISTORY_DIR / f"{today.strftime('%Y-%m')}-summary.json"

    summary = {
        "month": today.strftime("%Y-%m"),
        "source": "psf M Loop",
        "regime_trajectory": [],
        "dominant_theme": "",
        "axis_monthly": {
            k: {"trend": v.get("status", "미확인"), "note": ""}
            for k, v in state.get("axis_status", {}).items()
        },
        "pipe_changes": "",
        "regime_9_update": "",
        "kc_validity": "",
        "projection_adjusted": False,
        "projection_note": ""
    }

    save_json(summary_path, summary)


def main():
    if len(sys.argv) < 2:
        print("사용법: python core/snapshot.py [save|delta|weekly-summary|monthly-summary]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "save":
        save_snapshot()
    elif cmd == "delta":
        print_delta()
    elif cmd == "weekly-summary":
        save_weekly_summary()
    elif cmd == "monthly-summary":
        save_monthly_summary()
    else:
        print(f"알 수 없는 명령: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
