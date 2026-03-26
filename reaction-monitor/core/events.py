"""이벤트 히스토리 — 쟁점별 생애 추적.

사용:
  python core/events.py create             # state.json에서 이벤트 생성
  python core/events.py link EVT-ID        # 현재 state.json을 기존 이벤트에 연결
  python core/events.py list               # 이벤트 목록
  python core/events.py view EVT-ID        # 이벤트 생애 조회
  python core/events.py chain              # 이벤트 간 연쇄 관계 출력

원칙:
  Snapshots = 날짜 기준 → "3월 24일 시장은 어땠나"
  Events    = 주제 기준 → "나프타 위기는 어떻게 전개됐나"

  하나의 이벤트 = 하나의 파일에 생애 전체.
  연쇄 이벤트(나프타→이란→에틸렌)는 parent_event로 연결.

울타리: GUARDRAILS.md
  이벤트 생성/연결 = Yellow Zone (승인 필요)
  이벤트 조회/목록 = Green Zone
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STATE_PATH = BASE_DIR / "state.json"
EVENTS_DIR = BASE_DIR / "events"
WATCHES_PATH = BASE_DIR / "active-watches.json"


def _slug(text: str, max_len: int = 40) -> str:
    """한글+영문 슬러그 생성."""
    slug = re.sub(r'[^\w가-힣]', '-', text)[:max_len].strip('-')
    return re.sub(r'-+', '-', slug)


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _load_event(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_event(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _all_events() -> list[tuple[Path, dict]]:
    """모든 이벤트 파일을 로드."""
    results = []
    for f in sorted(EVENTS_DIR.glob("*.json")):
        try:
            data = _load_event(f)
            results.append((f, data))
        except Exception:
            continue
    return results


# ── 이벤트 생성 ──

def create_event(state: dict, parent_id: str = "") -> dict:
    """state.json에서 새 이벤트를 생성한다."""
    issue = state.get("issue", "")
    date = state.get("date", datetime.now().strftime("%Y-%m-%d"))
    fp = state.get("fingerprint", {})
    pattern = state.get("pattern", {})
    unresolved = state.get("unresolved", [])

    evt_id = f"EVT-{date}-{_slug(issue, 20)}"

    event = {
        "id": evt_id,
        "subject": issue,
        "created": date,
        "status": "active",
        "parent_event": parent_id,
        "child_events": [],

        "fingerprint": fp,

        "timeline": [
            {
                "date": date,
                "type": "initial_analysis",
                "source": "reaction-monitor",
                "summary": issue,
                "pattern": {
                    "direction": pattern.get("direction_alignment", ""),
                    "proportionality": pattern.get("proportionality", ""),
                    "propagation": pattern.get("propagation", ""),
                },
                "state_file": f"history/{date}.json",
                "key_finding": pattern.get("direction_rationale", ""),
            }
        ],

        "unresolved_at_creation": [
            {"id": uq.get("id", ""), "question": uq.get("question", "")}
            for uq in unresolved if isinstance(uq, dict) and uq.get("status") == "open"
        ],

        "resolution": {
            "date": None,
            "outcome": None,
            "lessons_learned": None,
        },
    }

    # 파일명
    filename = f"{evt_id}.json"
    filepath = EVENTS_DIR / filename
    _save_event(filepath, event)

    # parent에 child 등록
    if parent_id:
        _register_child(parent_id, evt_id)

    return event


def _register_child(parent_id: str, child_id: str):
    """parent 이벤트에 child를 등록한다."""
    for path, data in _all_events():
        if data.get("id") == parent_id:
            if child_id not in data.get("child_events", []):
                data.setdefault("child_events", []).append(child_id)
                _save_event(path, data)
            return


# ── 이벤트에 후속 분석 연결 ──

def link_analysis(evt_id: str, state: dict) -> bool:
    """현재 state.json을 기존 이벤트의 timeline에 추가한다."""
    for path, data in _all_events():
        if data.get("id") == evt_id:
            date = state.get("date", datetime.now().strftime("%Y-%m-%d"))
            pattern = state.get("pattern", {})
            issue = state.get("issue", "")

            # 이전 분석과의 변화 계산
            prev = data["timeline"][-1] if data["timeline"] else {}
            prev_dir = prev.get("pattern", {}).get("direction", "")
            curr_dir = pattern.get("direction_alignment", "")

            delta = ""
            if prev_dir and curr_dir and prev_dir != curr_dir:
                delta = f"방향 전환: {prev_dir} → {curr_dir}"
            elif prev_dir == curr_dir:
                delta = f"방향 유지: {curr_dir}"

            entry = {
                "date": date,
                "type": "follow_up",
                "source": "reaction-monitor",
                "summary": issue,
                "pattern": {
                    "direction": curr_dir,
                    "proportionality": pattern.get("proportionality", ""),
                    "propagation": pattern.get("propagation", ""),
                },
                "delta_vs_prev": delta,
                "state_file": f"history/{date}.json",
                "key_finding": pattern.get("direction_rationale", ""),
            }

            data["timeline"].append(entry)

            # unresolved 업데이트
            new_uq = state.get("unresolved", [])
            if new_uq:
                entry["new_unresolved"] = [
                    {"id": uq.get("id", ""), "question": uq.get("question", "")}
                    for uq in new_uq if isinstance(uq, dict) and uq.get("status") == "open"
                ]

            _save_event(path, data)
            return True

    return False


# ── 조회 ──

def list_events():
    """이벤트 목록 출력."""
    events = _all_events()
    if not events:
        print("  이벤트 없음\n")
        return

    for path, data in events:
        status = data.get("status", "?")
        icon = "🟢" if status == "active" else "⚪" if status == "monitoring" else "⏹"
        tl_count = len(data.get("timeline", []))
        parent = data.get("parent_event", "")
        children = data.get("child_events", [])

        print(f"  {icon} {data['id']}")
        print(f"     {data.get('subject', '')[:60]}")
        print(f"     상태: {status} | 분석: {tl_count}회 | 생성: {data.get('created', '')}")
        if parent:
            print(f"     ↑ parent: {parent}")
        if children:
            print(f"     ↓ children: {', '.join(children)}")
        print()


def view_event(evt_id: str):
    """이벤트 생애 상세 출력."""
    for path, data in _all_events():
        if data.get("id") == evt_id:
            print(f"\n{'=' * 60}")
            print(f"  {data['id']} — {data.get('subject', '')}")
            print(f"{'=' * 60}")
            print(f"  상태: {data.get('status', '?')} | 생성: {data.get('created', '')}")

            parent = data.get("parent_event", "")
            children = data.get("child_events", [])
            if parent:
                print(f"  ↑ parent: {parent}")
            if children:
                print(f"  ↓ children: {', '.join(children)}")

            print(f"\n  ── 타임라인 ({len(data.get('timeline', []))}건) ──\n")
            for i, entry in enumerate(data.get("timeline", [])):
                marker = "●" if i == 0 else "○"
                print(f"  {marker} [{entry.get('date', '')}] {entry.get('type', '')}")
                print(f"    {entry.get('summary', '')[:60]}")
                p = entry.get("pattern", {})
                if p:
                    print(f"    방향: {p.get('direction', '')} | 비례: {p.get('proportionality', '')} | 전파: {p.get('propagation', '')}")
                delta = entry.get("delta_vs_prev", "")
                if delta:
                    print(f"    Δ {delta}")
                finding = entry.get("key_finding", "")
                if finding:
                    print(f"    핵심: {finding[:80]}")
                print()

            uq = data.get("unresolved_at_creation", [])
            if uq:
                print(f"  ── 생성 시 미해소 ({len(uq)}건) ──\n")
                for q in uq:
                    print(f"    {q.get('id', '')}: {q.get('question', '')[:60]}")
                print()

            res = data.get("resolution", {})
            if res.get("date"):
                print(f"  ── 해소 ──")
                print(f"    날짜: {res['date']}")
                print(f"    결과: {res.get('outcome', '')}")
                print(f"    교훈: {res.get('lessons_learned', '')}")
                print()

            return

    print(f"  ❌ 이벤트 없음: {evt_id}")


def show_chain():
    """이벤트 간 연쇄 관계를 트리 형태로 출력."""
    events = _all_events()
    if not events:
        print("  이벤트 없음\n")
        return

    # root 이벤트 찾기 (parent가 없는 것)
    event_map = {d["id"]: d for _, d in events}
    roots = [d for d in event_map.values() if not d.get("parent_event")]

    def _print_tree(evt_id: str, depth: int = 0):
        evt = event_map.get(evt_id)
        if not evt:
            return
        indent = "  " + "  │ " * depth
        connector = "├── " if depth > 0 else ""
        tl = len(evt.get("timeline", []))
        direction = ""
        if evt.get("timeline"):
            last = evt["timeline"][-1]
            direction = last.get("pattern", {}).get("direction", "")

        print(f"{indent}{connector}{evt['id']}")
        print(f"{indent}{'│   ' if depth > 0 else ''}  {evt.get('subject', '')[:50]}")
        print(f"{indent}{'│   ' if depth > 0 else ''}  분석 {tl}회 | 방향: {direction}")
        print()

        for child_id in evt.get("child_events", []):
            _print_tree(child_id, depth + 1)

    print(f"\n{'=' * 60}")
    print(f"  이벤트 연쇄 관계")
    print(f"{'=' * 60}\n")

    for root in roots:
        _print_tree(root["id"])

    # 고아 이벤트 (parent가 있지만 parent가 존재하지 않는 것)
    orphans = [
        d for d in event_map.values()
        if d.get("parent_event") and d["parent_event"] not in event_map
    ]
    if orphans:
        print(f"  ⚠ 고아 이벤트 (parent 미존재):")
        for o in orphans:
            print(f"    {o['id']} → parent: {o['parent_event']}")
        print()


# ── CLI ──

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "create":
        state = _load_state()
        if not state:
            print("❌ state.json 없음")
            sys.exit(1)

        parent = ""
        if "--parent" in sys.argv:
            idx = sys.argv.index("--parent")
            if idx + 1 < len(sys.argv):
                parent = sys.argv[idx + 1]

        event = create_event(state, parent)
        print(f"\n  ✅ 이벤트 생성: {event['id']}")
        print(f"     주제: {event['subject'][:60]}")
        print(f"     파일: events/{event['id']}.json")
        if parent:
            print(f"     ↑ parent: {parent}")
        print(f"     타임라인: 1건 (initial_analysis)")
        print(f"     미해소: {len(event['unresolved_at_creation'])}건\n")

    elif cmd == "link":
        if len(sys.argv) < 3:
            print("사용법: python core/events.py link EVT-ID")
            sys.exit(1)
        evt_id = sys.argv[2]
        state = _load_state()
        if not state:
            print("❌ state.json 없음")
            sys.exit(1)
        ok = link_analysis(evt_id, state)
        if ok:
            print(f"\n  ✅ {evt_id}에 후속 분석 연결 완료")
            print(f"     쟁점: {state.get('issue', '')[:60]}\n")
        else:
            print(f"\n  ❌ 이벤트 없음: {evt_id}\n")

    elif cmd == "list":
        print(f"\n{'=' * 60}")
        print(f"  이벤트 목록")
        print(f"{'=' * 60}\n")
        list_events()

    elif cmd == "view":
        if len(sys.argv) < 3:
            print("사용법: python core/events.py view EVT-ID")
            sys.exit(1)
        view_event(sys.argv[2])

    elif cmd == "chain":
        show_chain()

    else:
        print("사용법: python core/events.py [create|link|list|view|chain]")
        print("  create              state.json에서 이벤트 생성")
        print("  create --parent ID  parent 이벤트에 연결하여 생성")
        print("  link EVT-ID         현재 state.json을 기존 이벤트에 연결")
        print("  list                이벤트 목록")
        print("  view EVT-ID         이벤트 생애 조회")
        print("  chain               이벤트 연쇄 관계 트리")


if __name__ == "__main__":
    main()
