"""자율 운영 모듈 — verification-engine 세션 스캔 + Watch + 이슈 관리.

사용:
  python core/autonomy.py scan          # 세션 시작 스캔 (Green Zone)
  python core/autonomy.py watch-convert # finalize 후 triggers → Watch 변환 제안
  python core/autonomy.py watch-scan    # Watch 기한 도래 스캔
  python core/autonomy.py watch-status  # Watch 현황
  python core/autonomy.py issue-log     # Self-Audit → 이슈 적재 (최근 검증)
  python core/autonomy.py status        # 전체 현황 갱신 + 출력

GUARDRAILS.md 준수:
  scan/watch-scan/status = Green Zone
  watch-convert/issue-log = 제안만 Green, 적용은 Yellow
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STATE_DIR = BASE_DIR / "state"
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = BASE_DIR / "output" / "history"
CONFIG_DIR = BASE_DIR / "config"
LOG_DIR = BASE_DIR / "logs" / "autonomy"

STATUS_PATH = STATE_DIR / "current-status.json"
WATCHES_PATH = STATE_DIR / "verification-watches.json"
ISSUES_PATH = STATE_DIR / "verification-issues.json"
KC_PATH = DATA_DIR / "kc_registry.json"
PATTERN_PATH = DATA_DIR / "pattern_registry.json"
RULE_ACTIVITY_PATH = DATA_DIR / "rule_activity.json"
TUNING_PATH = DATA_DIR / "tuning_state.json"
CALENDAR_PATH = CONFIG_DIR / "event-calendar.json"


# ── 자율 행동 로그 ──

def _log_action(zone: str, action: str, target: str, result: str):
    """자율 행동 로그를 파일에 기록한다."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"{today}.log"
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[AUTO] {timestamp} | {zone:<6} | {action:<12} | {target:<35} | {result}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════
#  세션 시작 스캔 (#5)
# ══════════════════════════════════

def session_scan() -> dict:
    """세션 시작 시 전체 현황 스캔. verify_orchestrator() 확장용."""
    result = {}
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 최근 검증
    recent = _find_latest_verification()
    result["last_verification"] = recent

    # 2. KC 현황
    kc_data = _load_json(KC_PATH)
    if isinstance(kc_data, list):
        active_kc = [k for k in kc_data if k.get("status") in ("active", "approaching", "revived")]
        approaching = [k for k in kc_data if k.get("status") == "approaching"]
        triggered = [k for k in kc_data if k.get("status") == "resolved" and
                     k.get("resolved_at", "") >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
        result["kc"] = {
            "total": len(kc_data),
            "active": len(active_kc),
            "approaching": len(approaching),
            "recently_triggered": len(triggered),
            "approaching_list": [
                {"kc_id": k["kc_id"], "premise": k["premise"][:50],
                 "current_value": k.get("current_value"),
                 "status": k["status"]}
                for k in approaching
            ],
        }
    else:
        result["kc"] = {"total": 0, "active": 0, "approaching": 0}

    # 3. 패턴 현황
    patterns = _load_json(PATTERN_PATH)
    if isinstance(patterns, list):
        proposed = [p for p in patterns if p.get("status") == "proposed"]
        result["patterns"] = {
            "total": len(patterns),
            "proposed": len(proposed),
            "proposed_list": [
                {"pattern_id": p["pattern_id"], "description": p.get("description", "")[:50]}
                for p in proposed
            ],
        }
    else:
        result["patterns"] = {"total": 0, "proposed": 0}

    # 4. Watch 스캔
    watches_data = _load_json(WATCHES_PATH)
    watches = watches_data.get("watches", [])
    due = [w for w in watches if w.get("status") == "active" and
           w.get("schedule", {}).get("next_check", "9999") <= today]
    active_watches = [w for w in watches if w.get("status") == "active"]
    result["watches"] = {
        "total_active": len(active_watches),
        "due_now": [{"id": w["id"], "subject": w["subject"][:50]} for w in due],
        "next_due": min((w["schedule"]["next_check"] for w in active_watches), default=""),
    }

    # 5. 이슈 현황
    issues_data = _load_json(ISSUES_PATH)
    if isinstance(issues_data, dict):
        result["issues"] = issues_data.get("summary", {"total_open": 0})
    else:
        result["issues"] = {"total_open": 0}

    # 6. 튜닝 현황
    tuning = _load_json(TUNING_PATH)
    result["tuning"] = {
        "last_tuned": tuning.get("last_tuned", ""),
        "dead_rules": len(tuning.get("dead_rules", [])) if isinstance(tuning.get("dead_rules"), list) else 0,
    }

    # 7. 캘린더 체크
    calendar_data = _load_json(CALENDAR_PATH)
    events_today = []
    events_upcoming = []
    if isinstance(calendar_data, dict):
        for evt in calendar_data.get("events", []):
            evt_date = evt.get("date", "")
            alert_days = evt.get("alert_days_before", [])
            if evt_date == today:
                events_today.append(evt)
            elif evt_date:
                try:
                    ed = datetime.strptime(evt_date, "%Y-%m-%d").date()
                    td = datetime.strptime(today, "%Y-%m-%d").date()
                    days_until = (ed - td).days
                    if days_until > 0 and days_until in alert_days:
                        events_upcoming.append({**evt, "days_until": days_until})
                except ValueError:
                    pass
    result["calendar"] = {
        "today": [{"name": e["name"], "impact": e.get("impact", "")} for e in events_today],
        "upcoming": [{"name": e["name"], "days_until": e["days_until"], "impact": e.get("impact", "")}
                     for e in events_upcoming],
    }
    _log_action("GREEN", "CALENDAR", "event-calendar.json",
                f"오늘 {len(events_today)}건, 예정 {len(events_upcoming)}건")

    # current-status.json 갱신
    status = {
        "last_updated": today,
        "last_verification": recent,
        "kc_summary": result["kc"],
        "pattern_summary": result["patterns"],
        "watch_summary": result["watches"],
        "issues_summary": result["issues"],
        "tuning": result["tuning"],
        "calendar": result["calendar"],
    }
    _save_json(STATUS_PATH, status)
    _log_action("GREEN", "SAVE", "current-status.json", "✅ 갱신")

    # 일일 상태 스냅샷 저장
    snapshot_path = HISTORY_DIR / f"status-{today}.json"
    _save_json(snapshot_path, status)
    _log_action("GREEN", "SNAPSHOT", f"status-{today}.json", "✅ 저장")

    return result


def _find_latest_verification() -> dict:
    """가장 최근 검증 결과를 찾는다."""
    if not HISTORY_DIR.exists():
        return {"vrf_id": "", "title": "검증 이력 없음"}
    files = sorted(
        [f for f in HISTORY_DIR.glob("vrf_*.json")
         if "_corrected_" not in f.name and "_outcome" not in f.name],
        reverse=True
    )
    if not files:
        return {"vrf_id": "", "title": "검증 이력 없음"}
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        rj = data.get("result_json", {})
        doc = rj.get("meta", {}).get("document", rj.get("document", {}))
        summary = data.get("summary", {})
        return {
            "vrf_id": data.get("vrf_id", files[0].stem),
            "title": doc.get("title", ""),
            "doc_type": doc.get("document_type", ""),
            "date": doc.get("date_accessed", ""),
            "summary_verdicts": summary.get("layer_verdicts", {}),
            "critical_flags_count": len(summary.get("critical_flags", [])),
        }
    except Exception:
        return {"vrf_id": files[0].stem, "title": "파싱 오류"}


# ══════════════════════════════════
#  Watch: invalidation_triggers → Watch 변환 (#3)
# ══════════════════════════════════

def convert_triggers_to_watches(vrf_id: str = "") -> list[dict]:
    """최근 검증의 invalidation_triggers를 Watch로 변환."""
    # 최근 검증 로드
    if not vrf_id:
        latest = _find_latest_verification()
        vrf_id = latest.get("vrf_id", "")
    if not vrf_id:
        return []

    history_path = HISTORY_DIR / f"{vrf_id}.json"
    if not history_path.exists():
        return []

    data = json.loads(history_path.read_text(encoding="utf-8"))
    rj = data.get("result_json", {})
    summary = data.get("summary", rj.get("summary", {}))
    triggers = summary.get("invalidation_triggers", rj.get("summary", {}).get("invalidation_triggers", []))

    if not triggers:
        return []

    today = datetime.now()
    proposals = []

    for i, t in enumerate(triggers):
        event = t.get("event", "")
        expected = t.get("expected_date", "")
        impact = t.get("impact", "")

        # Watch 유형 결정
        if expected:
            try:
                exp_date = datetime.strptime(expected, "%Y-%m-%d")
                days_until = (exp_date - today).days
                if days_until <= 7:
                    watch_type = "verification_urgent"
                    check_dates = [expected]
                elif days_until <= 30:
                    watch_type = "verification_follow_up"
                    # 주 1회
                    check_dates = []
                    current = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
                    while current.date() <= exp_date.date():
                        check_dates.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(weeks=1)
                    if not check_dates:
                        check_dates = [expected]
                else:
                    watch_type = "verification_monitor"
                    check_dates = []
                    current = today + timedelta(weeks=2)
                    while current.date() <= exp_date.date() and len(check_dates) < 5:
                        check_dates.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(weeks=2)
            except ValueError:
                watch_type = "verification_watch"
                check_dates = [(today + timedelta(weeks=2)).strftime("%Y-%m-%d")]
        else:
            watch_type = "verification_watch"
            check_dates = [(today + timedelta(weeks=2)).strftime("%Y-%m-%d")]

        watch = {
            "id": f"W-VRF-{vrf_id[-3:]}-{i+1:02d}",
            "created": today.strftime("%Y-%m-%d"),
            "source_vrf": vrf_id,
            "subject": f"[재검증] {event}",
            "type": watch_type,
            "schedule": {
                "mode": "fixed_interval" if len(check_dates) > 1 else "deadline",
                "check_dates": check_dates,
                "next_check": check_dates[0] if check_dates else "",
            },
            "original_trigger": t,
            "status": "active",
            "completed_checks": [],
            "close_condition": f"{event} 발생/미발생 확인 → 재검증 필요 여부 판단",
        }
        proposals.append(watch)

    return proposals


def register_watches(proposals: list[dict]):
    """Watch 등록 (Yellow Zone)."""
    data = _load_json(WATCHES_PATH)
    if not isinstance(data, dict):
        data = {"watches": [], "summary": {}}
    existing_ids = {w["id"] for w in data.get("watches", [])}
    added = 0
    for w in proposals:
        if w["id"] not in existing_ids:
            data.setdefault("watches", []).append(w)
            added += 1
    # summary 갱신
    active = [w for w in data["watches"] if w.get("status") == "active"]
    data["summary"] = {
        "total_active": len(active),
        "next_due": min((w["schedule"]["next_check"] for w in active if w["schedule"].get("next_check")), default=""),
        "types": {},
    }
    for w in active:
        t = w.get("type", "unknown")
        data["summary"]["types"][t] = data["summary"]["types"].get(t, 0) + 1
    _save_json(WATCHES_PATH, data)
    return added


def scan_watches() -> list[dict]:
    """기한 도래 Watch 스캔 (Green Zone)."""
    data = _load_json(WATCHES_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    due = []
    for w in data.get("watches", []):
        if w.get("status") == "active":
            nc = w.get("schedule", {}).get("next_check", "")
            if nc and nc <= today:
                due.append(w)
    return due


# ══════════════════════════════════
#  Self-Audit → 이슈 적재 (#4)
# ══════════════════════════════════

ISSUE_CATEGORIES = {
    "mcp_miss": ("CAT-2", "DATA_GAP"),
    "evidence_gap": ("CAT-2", "DATA_GAP"),
    "coverage_gap": ("CAT-1", "SKILL_DEFECT"),
    "kc_incomplete": ("CAT-4", "LOGIC_HOLE"),
    "prompt_drift": ("CAT-3", "PROMPT_DRIFT"),
}


def log_audit_issue(
    title: str,
    description: str,
    evidence: str,
    category_key: str = "coverage_gap",
    severity: str = "medium",
    detected_by: str = "self_audit.md",
    proposed_fix: str = "",
) -> dict | None:
    """Self-Audit 결과를 이슈로 적재한다."""
    data = _load_json(ISSUES_PATH)
    if not isinstance(data, dict):
        data = {"issues": [], "weekly_review": {}, "summary": {}}

    # 중복 체크
    existing_titles = {
        i["title"] for i in data.get("issues", [])
        if i.get("status") in ("open", "in_progress", "duplicate")
    }
    if title in existing_titles:
        return None

    cat, cat_name = ISSUE_CATEGORIES.get(category_key, ("CAT-1", "SKILL_DEFECT"))
    today = datetime.now()
    week_num = today.isocalendar()[1]
    issue_id = f"ISS-VE-2026-W{week_num:02d}-{len(data.get('issues', [])) + 1:03d}"

    issue = {
        "id": issue_id,
        "detected_at": today.strftime("%Y-%m-%d"),
        "detected_by": detected_by,
        "category": cat,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": evidence,
        "proposed_fix": proposed_fix,
        "target_file": "",
        "status": "open",
        "fixed_at": None,
        "fix_applied": None,
    }

    data.setdefault("issues", []).append(issue)

    # summary 갱신
    open_issues = [i for i in data["issues"] if i["status"] == "open"]
    sev = {}
    cat_count = {}
    for i in open_issues:
        s = i.get("severity", "low")
        sev[s] = sev.get(s, 0) + 1
        c = i.get("category", "CAT-1")
        cat_count[c] = cat_count.get(c, 0) + 1
    data["summary"] = {"total_open": len(open_issues), "by_severity": sev, "by_category": cat_count}

    # next_review
    days_until_monday = (7 - today.weekday()) % 7 or 7
    data.setdefault("weekly_review", {})["next_review"] = (today + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")

    _save_json(ISSUES_PATH, data)
    return issue


# ══════════════════════════════════
#  CLI
# ══════════════════════════════════

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        result = session_scan()
        print(f"\n{'=' * 60}")
        print(f"  verification-engine 세션 스캔")
        print(f"{'=' * 60}")

        lv = result.get("last_verification", {})
        print(f"  최근 검증: {lv.get('vrf_id', '없음')} — {lv.get('title', '')[:40]}")
        print(f"  판정: {lv.get('summary_verdicts', {})} | critical: {lv.get('critical_flags_count', 0)}")

        kc = result.get("kc", {})
        print(f"\n  KC: 총 {kc.get('total', 0)} | active {kc.get('active', 0)} | "
              f"approaching {kc.get('approaching', 0)}")
        for k in kc.get("approaching_list", []):
            print(f"    🟡 {k['kc_id']}: {k['premise'][:40]} (값: {k.get('current_value')})")

        pt = result.get("patterns", {})
        print(f"\n  패턴: 총 {pt.get('total', 0)} | 승격 대기 {pt.get('proposed', 0)}")

        w = result.get("watches", {})
        print(f"  Watch: 활성 {w.get('total_active', 0)} | 도래 {len(w.get('due_now', []))}건 | "
              f"다음 {w.get('next_due', '없음')}")

        iss = result.get("issues", {})
        print(f"  이슈: open {iss.get('total_open', 0)}")

        cal = result.get("calendar", {})
        cal_today = cal.get("today", [])
        cal_upcoming = cal.get("upcoming", [])
        if cal_today:
            print(f"\n  📅 오늘 이벤트:")
            for e in cal_today:
                print(f"    🔴 {e['name']} ({e.get('impact', '')})")
        if cal_upcoming:
            print(f"\n  📅 예정 이벤트:")
            for e in cal_upcoming:
                print(f"    🟡 {e['name']} (D-{e['days_until']}, {e.get('impact', '')})")
        if not cal_today and not cal_upcoming:
            print(f"\n  📅 이벤트: 없음")
        print()

    elif cmd == "watch-convert":
        vrf_id = sys.argv[2] if len(sys.argv) > 2 else ""
        proposals = convert_triggers_to_watches(vrf_id)
        if not proposals:
            print("  Watch 변환 대상 없음 (invalidation_triggers 없음)\n")
            return
        print(f"\n{'=' * 60}")
        print(f"  Watch 변환 제안 — {len(proposals)}건")
        print(f"{'=' * 60}")
        for w in proposals:
            print(f"\n  📌 {w['id']}")
            print(f"     {w['subject'][:60]}")
            print(f"     유형: {w['type']} | 다음: {w['schedule']['next_check']}")
        print(f"\n  ⚠ Yellow Zone: 등록은 승인 필요")
        print(f"  → python core/autonomy.py watch-register\n")

    elif cmd == "watch-register":
        vrf_id = sys.argv[2] if len(sys.argv) > 2 else ""
        proposals = convert_triggers_to_watches(vrf_id)
        added = register_watches(proposals)
        data = _load_json(WATCHES_PATH)
        print(f"  ✅ {added}건 등록 (총 활성: {data.get('summary', {}).get('total_active', 0)})\n")

    elif cmd == "watch-scan":
        due = scan_watches()
        print(f"\n  Watch 기한 스캔: {len(due)}건 도래")
        for w in due:
            print(f"  📌 {w['id']}: {w['subject'][:50]}")
        if not due:
            data = _load_json(WATCHES_PATH)
            nd = data.get("summary", {}).get("next_due", "없음")
            print(f"  다음 도래: {nd}")
        print()

    elif cmd == "watch-status":
        data = _load_json(WATCHES_PATH)
        watches = data.get("watches", [])
        print(f"\n  Watch 현황: 활성 {data.get('summary', {}).get('total_active', 0)}")
        for w in watches:
            icon = "🟢" if w["status"] == "active" else "⚪"
            print(f"  {icon} {w['id']}: {w['subject'][:50]} | 다음: {w['schedule'].get('next_check', '—')}")
        print()

    elif cmd == "issue-log":
        # 최근 검증의 Self-Audit 이슈를 수동 적재하는 예시
        print("  이슈 적재는 MCP 서버(verify_scan)를 통해 자동 실행됩니다.")
        print("  수동 적재: python -c \"from core.autonomy import log_audit_issue; ...\"")
        print()

    elif cmd == "status":
        session_scan()
        status = _load_json(STATUS_PATH)
        print(json.dumps(status, ensure_ascii=False, indent=2))

    else:
        print("사용법: python core/autonomy.py [scan|watch-convert|watch-register|watch-scan|watch-status|issue-log|status]")


if __name__ == "__main__":
    main()
