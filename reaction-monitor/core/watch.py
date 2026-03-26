"""Watch 관리 — unresolved ↔ Watch 변환 + 상태 관리.

사용:
  python core/watch.py                    # state.json에서 Watch 생성 제안
  python core/watch.py scan               # active-watches.json 기한 스캔
  python core/watch.py status             # Watch 현황 출력

Watch 유형 (자율 운영 레이어 호환):
  event_tracking    — condition 타입. 조건 충족까지 D+5/10/14
  policy_watch      — date 타입. deadline까지 주 1회
  data_check        — data 타입. deadline 기준 1회
  threshold_watch   — threshold 타입. 2주 1회

울타리: GUARDRAILS.md 준수
  Watch 등록/종료/변경 = Yellow Zone (승인 필요)
  Watch 기한 스캔/제안 생성 = Green Zone (무승인)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STATE_PATH = BASE_DIR / "state.json"
WATCHES_PATH = BASE_DIR / "active-watches.json"

# ── resolve_type → Watch 유형 매핑 ──

TYPE_MAP = {
    "condition": "event_tracking",
    "date": "policy_watch",
    "data": "data_check",
    "threshold": "threshold_watch",
}

# ── Watch 유형별 스케줄 생성 ──

def _generate_schedule(watch_type: str, deadline: str, created: str) -> dict:
    """Watch 유형에 따라 체크 스케줄을 생성한다."""
    today = datetime.now().date()
    created_date = datetime.strptime(created, "%Y-%m-%d").date() if created else today

    if watch_type == "event_tracking":
        # D+5, D+10, D+14
        dates = [
            (created_date + timedelta(days=5)).isoformat(),
            (created_date + timedelta(days=10)).isoformat(),
            (created_date + timedelta(days=14)).isoformat(),
        ]
        return {
            "mode": "fixed_interval",
            "check_dates": dates,
            "next_check": dates[0],
            "rationale": "event_tracking: D+5/10/14 체크",
        }

    elif watch_type == "policy_watch":
        # deadline까지 주 1회 (월요일)
        if deadline:
            dl = datetime.strptime(deadline, "%Y-%m-%d").date()
            dates = []
            current = today + timedelta(days=(7 - today.weekday()) % 7 or 7)  # 다음 월요일
            while current <= dl:
                dates.append(current.isoformat())
                current += timedelta(weeks=1)
            if not dates:
                dates = [dl.isoformat()]
            return {
                "mode": "recurring",
                "check_dates": dates,
                "next_check": dates[0],
                "rationale": f"policy_watch: {deadline}까지 주 1회 월요일",
            }
        return {
            "mode": "recurring",
            "check_dates": [],
            "next_check": (today + timedelta(weeks=1)).isoformat(),
            "rationale": "policy_watch: deadline 미지정. 주 1회",
        }

    elif watch_type == "data_check":
        # deadline 기준 1회
        if deadline:
            return {
                "mode": "deadline",
                "check_dates": [deadline],
                "next_check": deadline,
                "rationale": f"data_check: {deadline}에 1회 체크",
            }
        return {
            "mode": "deadline",
            "check_dates": [(today + timedelta(days=7)).isoformat()],
            "next_check": (today + timedelta(days=7)).isoformat(),
            "rationale": "data_check: deadline 미지정. 7일 후 체크",
        }

    elif watch_type == "threshold_watch":
        # 2주 1회
        dates = [
            (today + timedelta(weeks=2)).isoformat(),
            (today + timedelta(weeks=4)).isoformat(),
            (today + timedelta(weeks=6)).isoformat(),
        ]
        return {
            "mode": "recurring",
            "check_dates": dates,
            "next_check": dates[0],
            "rationale": "threshold_watch: 2주 1회. 임계값 도달까지",
        }

    return {"mode": "unknown", "check_dates": [], "next_check": ""}


# ── unresolved → Watch 변환 ──

def convert_unresolved_to_watches(state: dict) -> list[dict]:
    """state.json의 unresolved를 Watch 제안으로 변환한다.
    실제 적용은 사용자 승인 후 (Yellow Zone)."""
    unresolved = state.get("unresolved", [])
    issue = state.get("issue", "")
    date = state.get("date", datetime.now().strftime("%Y-%m-%d"))
    proposals = []

    for uq in unresolved:
        if not isinstance(uq, dict):
            continue
        if uq.get("status") != "open":
            continue

        uq_id = uq.get("id", "")
        resolve_type = uq.get("resolve_type", "data")
        watch_type = TYPE_MAP.get(resolve_type, "data_check")
        deadline = uq.get("deadline", "")
        created = uq.get("created", date)

        watch = {
            "id": f"W-{date}-{uq_id}",
            "created": date,
            "source_report": f"reaction-monitor state.json ({date})",
            "source_uq": uq_id,
            "subject": uq.get("question", ""),
            "type": watch_type,
            "schedule": _generate_schedule(watch_type, deadline, created),
            "original_context": {
                "issue": issue,
                "resolve_condition": uq.get("resolve_condition", ""),
            },
            "check_template": {
                "questions": [uq.get("question", "")],
                "data_sources": _extract_data_sources(uq.get("check_channels", {})),
            },
            "status": "active",
            "completed_checks": [],
            "close_condition": uq.get("resolve_condition", ""),
            "closed_at": None,
            "close_reason": None,
        }
        proposals.append(watch)

    return proposals


def _extract_data_sources(check_channels: dict) -> list[str]:
    """check_channels에서 데이터 소스 목록을 추출한다."""
    sources = []
    for layer, items in check_channels.items():
        if isinstance(items, list):
            for item in items:
                sources.append(f"{layer}: {item}")
        elif isinstance(items, str):
            sources.append(f"{layer}: {items}")
    return sources


# ── Watch 파일 관리 ──

def load_watches() -> dict:
    if WATCHES_PATH.exists():
        return json.loads(WATCHES_PATH.read_text(encoding="utf-8"))
    return {"watches": [], "summary": {"total_active": 0, "next_due": "", "types": {}}}


def save_watches(data: dict):
    # summary 갱신
    active = [w for w in data["watches"] if w["status"] == "active"]
    data["summary"] = {
        "total_active": len(active),
        "next_due": min((w["schedule"]["next_check"] for w in active), default=""),
        "types": {},
    }
    for w in active:
        t = w.get("type", "unknown")
        data["summary"]["types"][t] = data["summary"]["types"].get(t, 0) + 1

    WATCHES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def register_watches(proposals: list[dict]):
    """제안된 Watch를 active-watches.json에 등록한다."""
    data = load_watches()
    existing_ids = {w["id"] for w in data["watches"]}
    existing_uqs = {w.get("source_uq") for w in data["watches"]}

    added = 0
    for w in proposals:
        # 중복 방지: 같은 UQ에서 이미 Watch가 있으면 건너뜀
        if w["id"] in existing_ids:
            continue
        if w.get("source_uq") and w["source_uq"] in existing_uqs:
            print(f"  ⏭ {w['id']}: UQ {w['source_uq']}에서 이미 Watch 존재. 건너뜀")
            continue
        data["watches"].append(w)
        added += 1

    save_watches(data)
    return added


# ── Watch 스캔 (기한 도래 체크) ──

def scan_due_watches() -> list[dict]:
    """기한이 도래한 Watch 목록을 반환한다. (Green Zone: 읽기만)"""
    data = load_watches()
    today = datetime.now().strftime("%Y-%m-%d")
    due = []

    for w in data["watches"]:
        if w["status"] != "active":
            continue
        next_check = w.get("schedule", {}).get("next_check", "")
        if next_check and next_check <= today:
            due.append(w)

    return due


# ── CLI ──

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "propose"

    if cmd == "propose":
        # state.json에서 Watch 제안 생성
        if not STATE_PATH.exists():
            print("❌ state.json 없음")
            sys.exit(1)

        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        proposals = convert_unresolved_to_watches(state)

        print(f"\n{'=' * 60}")
        print(f"  Watch 등록 제안 — {state.get('issue', '?')}")
        print(f"{'=' * 60}")

        if not proposals:
            print("  미해소 질문 없음. Watch 등록 불필요.\n")
            return

        for w in proposals:
            sched = w["schedule"]
            print(f"\n  📌 {w['id']}")
            print(f"     주제: {w['subject'][:60]}")
            print(f"     유형: {w['type']}")
            print(f"     스케줄: {sched['rationale']}")
            print(f"     다음 체크: {sched['next_check']}")
            print(f"     종료 조건: {w['close_condition'][:60]}")
            print(f"     데이터: {', '.join(w['check_template']['data_sources'][:3])}")

        print(f"\n  총 {len(proposals)}건 제안")
        print(f"  ⚠ Yellow Zone: 등록은 사용자 승인 필요")
        print(f"  → python core/watch.py register 로 등록\n")

    elif cmd == "register":
        # 제안 → 등록 (Yellow Zone: 승인 후 실행)
        if not STATE_PATH.exists():
            print("❌ state.json 없음")
            sys.exit(1)

        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        proposals = convert_unresolved_to_watches(state)

        if not proposals:
            print("  등록할 Watch 없음.\n")
            return

        added = register_watches(proposals)
        total = load_watches()["summary"]["total_active"]
        print(f"\n  ✅ {added}건 등록 완료 (총 활성: {total}건)")
        print(f"  저장: {WATCHES_PATH}\n")

    elif cmd == "scan":
        # 기한 도래 스캔 (Green Zone: 읽기만)
        due = scan_due_watches()

        print(f"\n{'=' * 60}")
        print(f"  Watch 기한 스캔 — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'=' * 60}")

        if not due:
            print("  ✅ 기한 도래 Watch 없음\n")
        else:
            print(f"  📌 {len(due)}건 기한 도래:\n")
            for w in due:
                print(f"  • {w['id']}: {w['subject'][:50]}")
                print(f"    유형: {w['type']} | 다음 체크: {w['schedule']['next_check']}")
                print(f"    데이터: {', '.join(w['check_template']['data_sources'][:3])}")
                print()

        # 전체 현황
        data = load_watches()
        summary = data["summary"]
        print(f"  전체: 활성 {summary['total_active']}건 | 다음 도래: {summary.get('next_due', '없음')}")
        print(f"  유형: {summary.get('types', {})}\n")

    elif cmd == "status":
        # Watch 현황 (Green Zone: 읽기만)
        data = load_watches()
        watches = data["watches"]
        summary = data["summary"]

        print(f"\n{'=' * 60}")
        print(f"  Watch 현황")
        print(f"{'=' * 60}")
        print(f"  활성: {summary['total_active']}건")
        print(f"  유형: {summary.get('types', {})}")
        print(f"  다음 도래: {summary.get('next_due', '없음')}")

        for w in watches:
            status_icon = "🟢" if w["status"] == "active" else "⚪"
            checks = len(w.get("completed_checks", []))
            print(f"\n  {status_icon} {w['id']}")
            print(f"     {w['subject'][:50]}")
            print(f"     유형: {w['type']} | 상태: {w['status']} | 체크: {checks}회")
            print(f"     다음: {w['schedule'].get('next_check', '—')}")

        print()

    else:
        print(f"사용법: python core/watch.py [propose|register|scan|status]")


if __name__ == "__main__":
    main()
