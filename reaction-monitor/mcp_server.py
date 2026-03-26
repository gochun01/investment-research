"""Reaction Monitor MCP Server
시장 반응 수집의 틀(파이프라인, 검증, 추적)을 MCP 도구로 제공한다.
두뇌(판단)는 호스트의 LLM이 프롬프트를 따라 수행하고, 결과를 이 도구로 등록한다.

실행: python mcp_server.py
등록: claude mcp add reaction-monitor -- python "C:/.../reaction-monitor/mcp_server.py"

설계 원칙: "틀은 코드, 두뇌는 프롬프트"
  코드(이 서버): 검증, 저장, 추적, 렌더링, 오케스트레이션
  LLM(호스트): 채널 선정, 수집, 판독, 코멘트
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from core.validate import validate, auto_log_issues
from core.audit import audit
from core.watch import (
    convert_unresolved_to_watches, register_watches,
    scan_due_watches, load_watches, save_watches,
)
from core.events import (
    create_event, link_analysis, _all_events, _slug,
)
from core.render import render
from core.render_adaptive import render_adaptive

# ── 로깅 ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("reaction-monitor.mcp")

# ── 경로 ──
BASE_DIR = Path(__file__).parent
STATE_PATH = BASE_DIR / "state.json"
WATCHES_PATH = BASE_DIR / "active-watches.json"
ISSUES_PATH = BASE_DIR / "system-issues.json"
EVENTS_DIR = BASE_DIR / "events"
HISTORY_DIR = BASE_DIR / "history"
REPORTS_DIR = BASE_DIR / "reports"
PROMPTS_DIR = BASE_DIR

mcp = FastMCP("reaction-monitor")


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_state(data: dict):
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════
#  오케스트레이터
# ══════════════════════════════════

@mcp.tool()
def reaction_orchestrator() -> str:
    """반응 수집의 실행 규칙을 반환합니다.
    수집을 시작하기 전에 반드시 이 도구를 먼저 호출하세요.
    CLAUDE.md(원칙) + SKILL.md(실행순서)를 결합하여 반환합니다."""
    parts = []
    for name in ["CLAUDE.md", "SKILL.md"]:
        path = PROMPTS_DIR / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
        else:
            return json.dumps({"error": f"파일 없음: {name}"})
    return "\n\n---\n\n".join(parts)


# ══════════════════════════════════
#  Phase 0: 세션 스캔
# ══════════════════════════════════

@mcp.tool()
def reaction_scan() -> str:
    """세션 시작 스캔. Watch 기한 + 이전 상태 + 검증 + 이슈 현황을 한 번에 반환합니다.
    모든 수집 시작 전에 이 도구를 호출하세요."""
    result = {}

    # 1. state.json
    state = _load_state()
    if state:
        result["current_issue"] = state.get("issue", "")
        result["current_date"] = state.get("date", "")
        uq = state.get("unresolved", [])
        result["unresolved_open"] = sum(
            1 for q in uq if isinstance(q, dict) and q.get("status") == "open"
        )
    else:
        result["current_issue"] = "없음 (첫 수집)"

    # 2. Watch 스캔
    due = scan_due_watches()
    watches = load_watches()
    result["watches"] = {
        "total_active": watches.get("summary", {}).get("total_active", 0),
        "next_due": watches.get("summary", {}).get("next_due", ""),
        "due_now": [
            {"id": w["id"], "subject": w["subject"][:50], "type": w["type"]}
            for w in due
        ],
    }

    # 3. 검증 (state가 있으면)
    if state:
        issues = validate(state)
        result["validation"] = {
            "errors": sum(1 for i in issues if i["level"] == "ERROR"),
            "warns": sum(1 for i in issues if i["level"] == "WARN"),
            "details": [
                {"level": i["level"], "field": i["field"], "message": i["message"][:80]}
                for i in issues
            ],
        }

    # 4. 시스템 이슈
    if ISSUES_PATH.exists():
        issues_data = json.loads(ISSUES_PATH.read_text(encoding="utf-8"))
        result["system_issues"] = issues_data.get("summary", {})
    else:
        result["system_issues"] = {"total_open": 0}

    # 5. 이벤트
    events = _all_events()
    active_events = [d for _, d in events if d.get("status") == "active"]
    result["events"] = {
        "total": len(events),
        "active": len(active_events),
    }

    logger.info(f"세션 스캔 완료: watches={result['watches']['total_active']}, "
                f"issues={result['system_issues'].get('total_open', 0)}")
    return json.dumps(result, ensure_ascii=False)


# ══════════════════════════════════
#  State 관리
# ══════════════════════════════════

@mcp.tool()
def reaction_get_state() -> str:
    """현재 state.json을 반환합니다."""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음. 첫 수집을 실행하세요."})
    return json.dumps(state, ensure_ascii=False)


@mcp.tool()
def reaction_save_state(state_json: str) -> str:
    """수집 결과(state.json)를 저장합니다.
    호스트 LLM이 수집+판독 완료 후 결과를 이 도구로 전달합니다.

    state_json: 전체 state.json 문자열 (JSON)"""
    try:
        data = json.loads(state_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON 파싱 오류: {e}"})

    # 검증
    issues = validate(data)
    errors = [i for i in issues if i["level"] == "ERROR"]
    warns = [i for i in issues if i["level"] == "WARN"]

    if errors:
        return json.dumps({
            "error": f"스키마 검증 실패: ERROR {len(errors)}건",
            "errors": [{"field": e["field"], "message": e["message"]} for e in errors],
        }, ensure_ascii=False)

    # 저장
    _save_state(data)

    # history 스냅샷
    date = data.get("date", "")
    issue_slug = _slug(data.get("issue", ""), 30)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_path = HISTORY_DIR / f"{date}-{issue_slug}.json"
    history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # WARN 이슈 자동 적재
    logged = 0
    if warns:
        logged = auto_log_issues(issues, data)

    logger.info(f"state.json 저장: {data.get('issue', '')[:30]}, WARN {len(warns)}건, 이슈 적재 {logged}건")

    return json.dumps({
        "saved": True,
        "issue": data.get("issue", ""),
        "date": date,
        "validation": {"errors": 0, "warns": len(warns)},
        "issues_logged": logged,
        "history_saved": str(history_path),
    }, ensure_ascii=False)


# ══════════════════════════════════
#  검증 + 감사
# ══════════════════════════════════

@mcp.tool()
def reaction_validate() -> str:
    """현재 state.json의 스키마를 검증합니다. 15개+ 규칙 체크."""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    issues = validate(state)
    errors = [i for i in issues if i["level"] == "ERROR"]
    warns = [i for i in issues if i["level"] == "WARN"]

    return json.dumps({
        "errors": len(errors),
        "warns": len(warns),
        "details": [
            {"level": i["level"], "field": i["field"], "message": i["message"]}
            for i in issues
        ],
        "pass": len(errors) == 0,
    }, ensure_ascii=False)


@mcp.tool()
def reaction_audit() -> str:
    """Self-Audit Q1~Q5를 실행합니다. 수집 품질 자기 검증."""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    results = audit(state)
    pass_count = sum(1 for r in results if r["result"] == "✅")
    warn_count = sum(1 for r in results if r["result"] == "⚠")

    return json.dumps({
        "pass": pass_count,
        "warn": warn_count,
        "total": len(results),
        "results": results,
        "verdict": "정상" if warn_count == 0 else
                   f"⚠ {warn_count}건" if warn_count <= 2 else
                   f"⚠ {warn_count}건 — 수집 품질 의심",
    }, ensure_ascii=False)


@mcp.tool()
def reaction_pipeline() -> str:
    """전체 후처리 파이프라인 실행: 검증 → 감사 → 렌더링 → Watch 제안.
    수집 완료 후 이 도구를 호출하면 전체 후처리를 한 번에 실행합니다."""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    result = {}

    # 1. validate
    v_issues = validate(state)
    v_errors = sum(1 for i in v_issues if i["level"] == "ERROR")
    v_warns = sum(1 for i in v_issues if i["level"] == "WARN")
    logged = 0
    if v_warns:
        logged = auto_log_issues(v_issues, state)
    result["validate"] = {"errors": v_errors, "warns": v_warns, "issues_logged": logged}

    # 2. audit
    a_results = audit(state)
    a_warns = sum(1 for r in a_results if r["result"] == "⚠")
    result["audit"] = {
        "pass": sum(1 for r in a_results if r["result"] == "✅"),
        "warn": a_warns,
        "results": a_results,
    }

    # 3. render — adaptive(자율 판단) 우선, 실패 시 고정 구조 폴백
    try:
        from core.render_adaptive import render_adaptive, TEMPLATE_PATH as ADAPTIVE_TPL, REPORTS_DIR as RD
        import re
        if ADAPTIVE_TPL.exists():
            html, reading, design, verify = render_adaptive(state)
            date = state.get("date", "")
            slug = _slug(state.get("issue", ""), 30)
            RD.mkdir(parents=True, exist_ok=True)
            out_path = RD / f"{date}-{slug}-adaptive.html"
            out_path.write_text(html, encoding="utf-8")
            result["render"] = {
                "mode": "adaptive",
                "saved": str(out_path),
                "report_type": f"{design.report_type} ({design.report_type_name})",
                "report_class": design.report_class,
                "sections": len(design.sections),
                "verify": {
                    "v1_claim": verify.v1_claim_ok,
                    "v2_data": verify.v2_data_ok,
                    "v3_empty": verify.v3_no_empty,
                    "v4_proportion": verify.v4_proportional,
                    "v5_first_screen": verify.v5_first_screen,
                    "issues": verify.issues,
                },
            }
        else:
            # 폴백: 고정 구조
            from core.render import render as render_fixed, TEMPLATE_PATH as FIXED_TPL, REPORTS_DIR as RD2
            if FIXED_TPL.exists():
                html = render_fixed(state)
                date = state.get("date", "")
                slug = _slug(state.get("issue", ""), 30)
                RD2.mkdir(parents=True, exist_ok=True)
                out_path = RD2 / f"{date}-{slug}-reaction.html"
                out_path.write_text(html, encoding="utf-8")
                result["render"] = {"mode": "fixed", "saved": str(out_path)}
            else:
                result["render"] = {"error": "template 없음 (adaptive, fixed 모두)"}
    except Exception as e:
        result["render"] = {"error": str(e)}

    # 4. watch propose
    proposals = convert_unresolved_to_watches(state)
    result["watch_proposals"] = len(proposals)

    logger.info(f"파이프라인 완료: validate WARN={v_warns}, audit ⚠={a_warns}, "
                f"watch 제안={len(proposals)}")

    return json.dumps(result, ensure_ascii=False)


# ══════════════════════════════════
#  Watch 관리
# ══════════════════════════════════

@mcp.tool()
def reaction_watch_scan() -> str:
    """기한 도래 Watch를 스캔합니다. [Green Zone]"""
    due = scan_due_watches()
    watches = load_watches()
    return json.dumps({
        "due": [
            {"id": w["id"], "subject": w["subject"][:60], "type": w["type"],
             "next_check": w["schedule"]["next_check"],
             "data_sources": w["check_template"]["data_sources"][:3]}
            for w in due
        ],
        "total_active": watches.get("summary", {}).get("total_active", 0),
        "next_due": watches.get("summary", {}).get("next_due", ""),
    }, ensure_ascii=False)


@mcp.tool()
def reaction_watch_propose() -> str:
    """현재 state.json의 미해소 질문을 Watch로 변환 제안합니다. [Green Zone — 제안만]"""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    proposals = convert_unresolved_to_watches(state)
    return json.dumps({
        "proposals": [
            {"id": w["id"], "subject": w["subject"][:60], "type": w["type"],
             "next_check": w["schedule"]["next_check"],
             "close_condition": w["close_condition"][:60]}
            for w in proposals
        ],
        "count": len(proposals),
        "note": "등록은 reaction_watch_register()로 (Yellow Zone — 승인 필요)",
    }, ensure_ascii=False)


@mcp.tool()
def reaction_watch_register() -> str:
    """제안된 Watch를 등록합니다. [Yellow Zone — 승인 후 호출]"""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    proposals = convert_unresolved_to_watches(state)
    added = register_watches(proposals)
    watches = load_watches()

    logger.info(f"Watch 등록: {added}건 추가, 총 활성 {watches['summary']['total_active']}건")
    return json.dumps({
        "added": added,
        "total_active": watches["summary"]["total_active"],
        "next_due": watches["summary"].get("next_due", ""),
    }, ensure_ascii=False)


@mcp.tool()
def reaction_watch_status() -> str:
    """Watch 현황을 반환합니다. [Green Zone]"""
    watches = load_watches()
    return json.dumps({
        "watches": [
            {"id": w["id"], "subject": w["subject"][:50], "type": w["type"],
             "status": w["status"], "checks": len(w.get("completed_checks", [])),
             "next_check": w["schedule"].get("next_check", "")}
            for w in watches.get("watches", [])
        ],
        "summary": watches.get("summary", {}),
    }, ensure_ascii=False)


# ══════════════════════════════════
#  이벤트 관리
# ══════════════════════════════════

@mcp.tool()
def reaction_event_create(parent_id: str = "") -> str:
    """현재 state.json에서 이벤트를 생성합니다. [Yellow Zone]

    parent_id: 부모 이벤트 ID (연쇄 관계 시)"""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    event = create_event(state, parent_id)
    logger.info(f"이벤트 생성: {event['id']}, parent={parent_id or '없음'}")

    return json.dumps({
        "id": event["id"],
        "subject": event["subject"],
        "parent": parent_id or "없음 (root)",
        "timeline_count": len(event["timeline"]),
        "unresolved_count": len(event["unresolved_at_creation"]),
    }, ensure_ascii=False)


@mcp.tool()
def reaction_event_link(event_id: str) -> str:
    """현재 state.json을 기존 이벤트에 후속 분석으로 연결합니다. [Yellow Zone]

    event_id: 연결할 이벤트 ID"""
    state = _load_state()
    if not state:
        return json.dumps({"error": "state.json 없음"})

    ok = link_analysis(event_id, state)
    if ok:
        logger.info(f"이벤트 연결: {event_id} ← {state.get('issue', '')[:30]}")
        return json.dumps({"linked": True, "event_id": event_id, "issue": state.get("issue", "")})
    return json.dumps({"error": f"이벤트 없음: {event_id}"})


@mcp.tool()
def reaction_event_list() -> str:
    """이벤트 목록을 반환합니다. [Green Zone]"""
    events = _all_events()
    return json.dumps({
        "events": [
            {"id": d["id"], "subject": d.get("subject", "")[:50],
             "status": d.get("status", ""), "created": d.get("created", ""),
             "timeline_count": len(d.get("timeline", [])),
             "parent": d.get("parent_event", ""),
             "children": d.get("child_events", [])}
            for _, d in events
        ],
        "total": len(events),
    }, ensure_ascii=False)


@mcp.tool()
def reaction_event_chain() -> str:
    """이벤트 연쇄 관계를 트리 형태로 반환합니다. [Green Zone]"""
    events = _all_events()
    event_map = {d["id"]: d for _, d in events}

    def _build_tree(evt_id: str) -> dict:
        evt = event_map.get(evt_id, {})
        last_pattern = {}
        if evt.get("timeline"):
            last_pattern = evt["timeline"][-1].get("pattern", {})
        return {
            "id": evt_id,
            "subject": evt.get("subject", "")[:50],
            "status": evt.get("status", ""),
            "direction": last_pattern.get("direction", ""),
            "timeline_count": len(evt.get("timeline", [])),
            "children": [
                _build_tree(child_id) for child_id in evt.get("child_events", [])
            ],
        }

    roots = [d for d in event_map.values() if not d.get("parent_event")]
    tree = [_build_tree(r["id"]) for r in roots]

    return json.dumps({"chain": tree}, ensure_ascii=False)


# ══════════════════════════════════
#  레퍼런스 조회
# ══════════════════════════════════

@mcp.tool()
def reaction_get_channels() -> str:
    """채널 카탈로그를 반환합니다. 채널 선정 시 참조용. [Green Zone]"""
    path = BASE_DIR / "references" / "channel-catalog.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps({"error": "channel-catalog.md 없음"})


@mcp.tool()
def reaction_get_patterns() -> str:
    """패턴 판독 사전을 반환합니다. Phase 4 판독 시 참조. [Green Zone]"""
    path = BASE_DIR / "references" / "pattern-lexicon.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps({"error": "pattern-lexicon.md 없음"})


@mcp.tool()
def reaction_get_guardrails() -> str:
    """울타리(GUARDRAILS.md)를 반환합니다. 자율 행동 전 확인. [Green Zone]"""
    path = BASE_DIR / "GUARDRAILS.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps({"error": "GUARDRAILS.md 없음"})


# ══════════════════════════════════
#  시스템 이슈
# ══════════════════════════════════

@mcp.tool()
def reaction_get_issues() -> str:
    """시스템 이슈 현황을 반환합니다. [Green Zone]"""
    if ISSUES_PATH.exists():
        data = json.loads(ISSUES_PATH.read_text(encoding="utf-8"))
        open_issues = [i for i in data["issues"] if i["status"] == "open"]
        return json.dumps({
            "summary": data.get("summary", {}),
            "weekly_review": data.get("weekly_review", {}),
            "open_issues": [
                {"id": i["id"], "severity": i["severity"], "title": i["title"][:60],
                 "category": i["category"], "proposed_fix": i["proposed_fix"][:60]}
                for i in open_issues
            ],
        }, ensure_ascii=False)
    return json.dumps({"summary": {"total_open": 0}, "open_issues": []})


# ══════════════════════════════════
#  실행
# ══════════════════════════════════

if __name__ == "__main__":
    logger.info("reaction-monitor MCP 서버 시작")
    mcp.run()
