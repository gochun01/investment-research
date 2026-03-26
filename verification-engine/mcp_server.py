"""Verification Engine MCP Server
6층 입체 검증의 틀(파이프라인, 데이터)을 MCP 도구로 제공한다.
두뇌(판단)는 Claude가 프롬프트를 따라 수행하고, 결과를 이 도구로 등록한다.

실행: python mcp_server.py
등록: claude mcp add verification-engine -- python "C:/.../verification-engine/mcp_server.py"
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from core.engine import VerificationEngine
from core.layers import NormLayer, LogicLayer, OmissionLayer
from core.adapters import NewsAnalysisAdapter
from core.corrections import FindingCard, CorrectionEngine
from core.html_renderer import VerificationHTMLRenderer
from core.render_adaptive import AdaptiveVerificationRenderer
from core.rule_tracker import record_rule_activity, get_rule_activity, get_dead_rules, get_hot_rules
from core.tuning import run_full_tuning
from core.kc_lifecycle import (
    extract_and_register_kcs, get_active_kcs, get_all_kcs,
    update_kc_value, register_kc,
)
from core.pattern_registry import (
    record_triggered_rules, get_proposed_patterns, get_all_patterns,
    promote_pattern, dismiss_pattern, generate_promotion_suggestions,
)

# ── 로깅 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("verification-engine.mcp")

# ── 글로벌 ──
_sessions: dict[str, VerificationEngine] = {}
_current_session: str | None = None
_SESSION_TIMEOUT_MINUTES = 120
PROMPTS_DIR = Path(__file__).parent / "prompts"
DATA_DIR = Path(__file__).parent / "data"
HISTORY_DIR = Path(__file__).parent / "output" / "history"
CHANGELOG_PATH = Path(__file__).parent / "docs" / "changelog.json"

mcp = FastMCP("verification-engine")


def _append_changelog(entry: dict):
    """changelog.json에 변경 항목을 자동 추가한다."""
    from datetime import datetime
    try:
        CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CHANGELOG_PATH.exists():
            data = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
        else:
            data = []

        today = datetime.now().strftime("%Y-%m-%d")

        # 오늘 날짜 항목이 있으면 changes에 추가, 없으면 새 항목 생성
        today_entry = None
        for d in data:
            if d.get("date") == today:
                today_entry = d
                break

        if today_entry:
            # changes 키가 최상위에 있으면 직접 추가, sessions 구조면 마지막 session에 추가
            if "changes" in today_entry:
                today_entry["changes"].append(entry)
            elif "sessions" in today_entry:
                today_entry["sessions"][-1].setdefault("changes", []).append(entry)
            else:
                today_entry["changes"] = [entry]
        else:
            data.insert(0, {
                "date": today,
                "title": "검증 엔진 업데이트",
                "trigger": "실전 검증 피드백",
                "changes": [entry],
            })

        CHANGELOG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # CHANGELOG.md 자동 동기화
        _sync_changelog_md(entry, today)

    except Exception as e:
        logger.warning(f"changelog 기록 실패: {e}")


def _sync_changelog_md(entry: dict, date: str):
    """changelog.json 기록 시 CHANGELOG.md에도 자동 추가."""
    try:
        md_path = CHANGELOG_PATH.parent / "CHANGELOG.md"
        if not md_path.exists():
            return

        md = md_path.read_text(encoding="utf-8")

        # 항목 요약 텍스트 생성
        entry_type = entry.get("type", "unknown")
        entry_id = entry.get("id", "")
        source = entry.get("source", "")

        if entry_type == "rule_added":
            line = f"- 규칙 추가: `{entry_id}` ({entry.get('name', '')}) — {entry.get('scope', '')} [{entry.get('severity', '')}]"
        elif entry_type == "checklist_added":
            line = f"- 체크리스트 추가: `{entry_id}` — {entry.get('description', '')} [{entry.get('scope', '')}]"
        elif entry_type == "kc_updated":
            line = f"- KC 갱신: `{entry_id}` → {entry.get('status', '')} (값: {entry.get('value', '')})"
        elif entry_type == "pattern_promoted":
            line = f"- 패턴 승격: `{entry.get('pattern_id', '')}` → `{entry.get('promoted_as', '')}`"
        elif entry_type == "outcome_analysis":
            line = f"- outcome 분석: {entry.get('outcomes_analyzed', 0)}건 분석, 패턴 {entry.get('patterns_found', 0)}건, 규칙 제안 {entry.get('rules_suggested', 0)}건"
        elif entry_type == "code_modified":
            line = f"- 코드 수정: `{entry_id}` — {entry.get('file', source)}"
        elif entry_type == "engine_upgrade":
            items = entry.get("items", [])
            line = f"- 엔진 업그레이드: {len(items)}건"
            for item in items[:3]:
                line += f"\n  - {item[:80]}"
        else:
            line = f"- [{entry_type}] {entry_id}: {source}"

        # 오늘 날짜 섹션이 있는지 확인
        date_header = f"## {date}"
        auto_header = f"### 자동 기록 (changelog.json 동기화)"

        if date_header not in md:
            # 첫 번째 ## 앞에 오늘 날짜 섹션 삽입
            insert_pos = md.find("\n## ")
            if insert_pos == -1:
                md += f"\n\n{date_header}\n\n{auto_header}\n{line}\n"
            else:
                md = md[:insert_pos] + f"\n\n{date_header}\n\n{auto_header}\n{line}\n" + md[insert_pos:]
        elif auto_header not in md:
            # 오늘 날짜 섹션은 있지만 자동 기록 헤더가 없음
            pos = md.find(date_header)
            next_section = md.find("\n## ", pos + len(date_header))
            if next_section == -1:
                md += f"\n{auto_header}\n{line}\n"
            else:
                md = md[:next_section] + f"\n{auto_header}\n{line}\n" + md[next_section:]
        else:
            # 자동 기록 헤더 뒤에 추가
            pos = md.find(auto_header)
            end_of_header = pos + len(auto_header)
            md = md[:end_of_header] + f"\n{line}" + md[end_of_header:]

        md_path.write_text(md, encoding="utf-8")
    except Exception as e:
        logger.warning(f"CHANGELOG.md 동기화 실패: {e}")


def _get_engine() -> VerificationEngine:
    global _current_session
    if _current_session and _current_session in _sessions:
        return _sessions[_current_session]
    # 하위 호환: 세션이 1개면 그것을 기본으로 사용
    if len(_sessions) == 1:
        only_key = next(iter(_sessions))
        _current_session = only_key
        return _sessions[only_key]
    # 세션이 없으면 새로 생성
    engine = VerificationEngine()
    _current_session = "default"
    _sessions["default"] = engine
    return engine


# ══════════════════════════════════
#  오케스트레이터 (가장 먼저 호출)
# ══════════════════════════════════

@mcp.tool()
def verify_orchestrator() -> str:
    """검증 파이프라인의 실행 순서와 규칙을 반환합니다.
    검증을 시작하기 전에 반드시 이 도구를 먼저 호출하세요.
    CLAUDE.md(원칙) + SKILL.md(실행순서)를 결합하여 반환합니다."""

    parts = []
    for name in ["CLAUDE.md", "SKILL.md"]:
        path = PROMPTS_DIR / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
        else:
            return f"프롬프트를 찾을 수 없습니다: {name}"

    return "\n\n---\n\n".join(parts)


@mcp.tool()
def verify_scan() -> str:
    """세션 시작 스캔. KC 현황, Watch 기한, 이슈 현황, 최근 검증을 한 번에 반환합니다.
    검증을 시작하기 전에 이 도구를 호출하면 현재 시스템 상태를 파악할 수 있습니다.
    [Green Zone]"""

    try:
        from core.autonomy import session_scan
        result = session_scan()
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_scan 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@mcp.tool()
def verify_watch_convert(vrf_id: str = "") -> str:
    """검증 결과의 invalidation_triggers를 Watch로 변환 제안합니다.
    vrf_id 미지정 시 가장 최근 검증에서 변환합니다.
    [Green Zone — 제안만. 등록은 verify_watch_register()]"""

    try:
        from core.autonomy import convert_triggers_to_watches
        proposals = convert_triggers_to_watches(vrf_id)
        return json.dumps({
            "proposals": [
                {"id": w["id"], "subject": w["subject"][:60], "type": w["type"],
                 "next_check": w["schedule"]["next_check"]}
                for w in proposals
            ],
            "count": len(proposals),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def verify_watch_register(vrf_id: str = "") -> str:
    """Watch를 등록합니다. [Yellow Zone — 승인 후 호출]"""

    try:
        from core.autonomy import convert_triggers_to_watches, register_watches, _load_json, WATCHES_PATH
        proposals = convert_triggers_to_watches(vrf_id)
        added = register_watches(proposals)
        data = _load_json(WATCHES_PATH)
        return json.dumps({
            "added": added,
            "total_active": data.get("summary", {}).get("total_active", 0),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def verify_watch_scan() -> str:
    """기한 도래 Watch를 스캔합니다. [Green Zone]"""

    try:
        from core.autonomy import scan_watches, _load_json, WATCHES_PATH
        due = scan_watches()
        data = _load_json(WATCHES_PATH)
        return json.dumps({
            "due": [{"id": w["id"], "subject": w["subject"][:50]} for w in due],
            "total_active": data.get("summary", {}).get("total_active", 0),
            "next_due": data.get("summary", {}).get("next_due", ""),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def verify_get_adaptive_report_guide() -> str:
    """자율 판단 보고서 생성 가이드를 반환합니다.
    Phase 5에서 '보고서 만들어' 요청 시 이 도구를 먼저 호출하세요.
    데이터가 보고서 구조를 결정하는 자율 보고서 생성 프로토콜입니다. [Green Zone]"""

    path = PROMPTS_DIR / "adaptive-report.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps({"error": "adaptive-report.md 없음"})


@mcp.tool()
def verify_get_guardrails() -> str:
    """울타리(GUARDRAILS.md)를 반환합니다. 자율 행동 전 확인. [Green Zone]"""

    path = Path(__file__).parent / "GUARDRAILS.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps({"error": "GUARDRAILS.md 없음"})


@mcp.tool()
def verify_log_issue(
    title: str,
    description: str,
    evidence: str,
    category_key: str = "coverage_gap",
    severity: str = "medium",
    proposed_fix: str = "",
) -> str:
    """Self-Audit 이슈를 적재합니다. [Yellow Zone]

    category_key: mcp_miss, evidence_gap, coverage_gap, kc_incomplete, prompt_drift"""

    try:
        from core.autonomy import log_audit_issue
        issue = log_audit_issue(
            title=title, description=description, evidence=evidence,
            category_key=category_key, severity=severity,
            proposed_fix=proposed_fix,
        )
        if issue:
            return json.dumps({"logged": True, "id": issue["id"], "title": title}, ensure_ascii=False)
        return json.dumps({"logged": False, "reason": "중복 이슈"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def verify_get_issues() -> str:
    """시스템 이슈 현황을 반환합니다. [Green Zone]"""

    try:
        from core.autonomy import _load_json, ISSUES_PATH
        data = _load_json(ISSUES_PATH)
        if not isinstance(data, dict):
            return json.dumps({"summary": {"total_open": 0}, "open_issues": []})
        open_issues = [i for i in data.get("issues", []) if i.get("status") == "open"]
        return json.dumps({
            "summary": data.get("summary", {}),
            "weekly_review": data.get("weekly_review", {}),
            "open_issues": [
                {"id": i["id"], "severity": i["severity"], "title": i["title"][:60],
                 "category": i["category"]}
                for i in open_issues
            ],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════
#  Phase 0: 문서 설정
# ══════════════════════════════════

@mcp.tool()
def verify_start(
    title: str,
    doc_type: str,
    target_id: str = "",
    sector_id: str = "",
    author_id: str = "",
    institution_id: str = "",
    source_url: str = "",
    date_published: str = "",
) -> str:
    """검증 세션을 시작합니다. 문서 메타 정보를 설정합니다.
    doc_type: equity_research, crypto_research, legal_contract, fund_factsheet, regulatory_filing, macro_report, geopolitical, news_article
    sector_id: 반도체, 크립토, 바이오, 에너지, 부동산, 금융_대체투자, 법률_계약, 매크로, 지정학"""

    global _current_session

    # ── 결함#10 수정: 기존 세션 보호 ──
    if _current_session and _current_session in _sessions:
        prev_engine = _sessions[_current_session]
        if prev_engine.result.claims:
            prev_vrf = prev_engine.result.vrf_id
            prev_claims = len(prev_engine.result.claims)
            logger.warning(
                f"기존 검증 세션 유지: {prev_vrf} (claims={prev_claims}). "
                f"새 세션을 생성합니다."
            )

    try:
        engine = VerificationEngine()

        doc = engine.set_document(
            title=title, doc_type=doc_type, target_id=target_id,
            sector_id=sector_id, author_id=author_id, institution_id=institution_id,
            source_url=source_url, date_published=date_published,
        )

        # 세션 등록
        vrf_id = engine.result.vrf_id
        _sessions[vrf_id] = engine
        _current_session = vrf_id

        # ── 결함#5 수정: 미지원 doc_type 경고 ──
        FULLY_SUPPORTED = {"equity_research", "crypto_research", "legal_contract", "macro_report", "geopolitical", "news_article"}
        limited_warning = ""
        if doc_type not in FULLY_SUPPORTED:
            limited_warning = (
                f"⚠ '{doc_type}'는 체크리스트·규칙·소스가 아직 구축되지 않았습니다. "
                f"대부분의 층이 ⚫ NO BASIS로 처리될 수 있습니다. "
                f"완전 지원 유형: {sorted(FULLY_SUPPORTED)}"
            )
            logger.warning(limited_warning)

        # ── 검증 강도 프리셋 로드 ──
        depth_preset = {}
        try:
            matrix = engine.get_claim_matrix()
            depth_config = matrix.get("_verification_depth", {})
            depth_preset = depth_config.get(doc_type, depth_config.get("equity_research", {}))
        except Exception:
            pass

        logger.info(f"검증 세션 시작: vrf_id={engine.result.vrf_id}, doc_type={doc_type}, depth={depth_preset.get('depth', 'standard')}")
        result = {
            "vrf_id": engine.result.vrf_id,
            "document": doc.to_dict(),
            "fact_sources": engine.get_fact_sources(),
            "norm_checklist_count": len(engine.get_norm_checklist()),
            "logic_rules_count": len(engine.get_logic_rules()),
            "omission_sectors": engine.get_omission_sectors(),
            "incentive_checks": engine.get_incentive_checks(),
            "claim_type_matrix": engine.get_claim_matrix(),
            "verification_depth": depth_preset,
        }
        if limited_warning:
            result["warning"] = limited_warning
        return json.dumps(result, ensure_ascii=False)
    except ValueError as e:
        logger.warning(f"verify_start 검증 오류: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_start 내부 오류: {e}", exc_info=True)
        return json.dumps({"error": f"내부 오류: {type(e).__name__}: {e}"}, ensure_ascii=False)


@mcp.tool()
def verify_switch_session(vrf_id: str) -> str:
    """검증 세션을 전환합니다. 다른 vrf_id의 세션으로 전환할 때 사용합니다."""

    global _current_session

    if vrf_id not in _sessions:
        available = list(_sessions.keys())
        return json.dumps({
            "error": f"세션 '{vrf_id}'을(를) 찾을 수 없습니다",
            "available_sessions": available,
        }, ensure_ascii=False)

    _current_session = vrf_id
    engine = _sessions[vrf_id]
    logger.info(f"세션 전환: {vrf_id}")
    return json.dumps({
        "switched_to": vrf_id,
        "doc_type": engine.result.document.document_type,
        "claims_count": len(engine.result.claims),
        "session_age_minutes": round(engine.session_age_minutes, 1),
    }, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 1: Claim 등록
# ══════════════════════════════════

@mcp.tool()
def verify_add_claim(
    claim_id: str,
    text: str,
    claim_type: str,
    evidence_type: str = "fact",
    location: str = "",
    depends_on: list[str] | None = None,
) -> str:
    """검증 대상 claim을 등록합니다.
    claim_type: 수치주장, 인과주장, 예측, 사실진술, 의견, 조항
    evidence_type: fact(확인된 데이터), estimate(추정/전망), opinion(주관적 판단), survey(설문/여론조사 결과)
    depends_on: 이 claim이 의존하는 다른 claim ID (예: ["c001"])"""

    try:
        engine = _get_engine()
        claim = engine.add_claim(claim_id, text, claim_type, evidence_type, location, depends_on or [])

        # 어떤 층이 적용되는지 반환
        applicable = {k: v.verdict != "N/A" for k, v in claim.layers.items()}
        logger.info(f"Claim 등록: {claim_id} ({claim_type})")
        return json.dumps({
            "claim_id": claim_id,
            "claim_type": claim_type,
            "evidence_type": evidence_type,
            "applicable_layers": applicable,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_add_claim 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 2: 판정 등록
# ══════════════════════════════════

@mcp.tool()
def verify_set_verdict(
    claim_id: str,
    layer: str,
    verdict: str,
    notes: str = "",
    evidence: list[dict] | None = None,
    checklist_matched: list[str] | None = None,
    checklist_missed: list[str] | None = None,
    rules_triggered: list[str] | None = None,
    kc_extracted: list[dict] | None = None,
    data_reference_date: str = "",
    gap_days: int = 0,
    material_change: bool = False,
    valid_until: str = "",
    bbj_breaks: list[dict] | None = None,
) -> str:
    """개별 claim의 특정 층 판정을 등록합니다.
    layer: fact, norm, logic, temporal, incentive, omission
    verdict: 🟢, 🟡, 🔴, ⚫"""

    try:
        engine = _get_engine()
        lv = engine.set_claim_verdict(
            claim_id, layer, verdict=verdict, notes=notes,
            evidence=evidence or [], checklist_matched=checklist_matched or [],
            checklist_missed=checklist_missed or [], rules_triggered=rules_triggered or [],
            kc_extracted=kc_extracted or [], data_reference_date=data_reference_date,
            gap_days=gap_days, material_change=material_change,
            valid_until=valid_until, bbj_breaks=bbj_breaks or [],
        )
        logger.info(f"판정 등록: {claim_id}/{layer} → {verdict}")
        return json.dumps({"claim_id": claim_id, "layer": layer, "verdict": verdict}, ensure_ascii=False)
    except ValueError as e:
        logger.warning(f"verify_set_verdict 검증 오류: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_set_verdict 내부 오류: {e}", exc_info=True)
        return json.dumps({"error": f"내부 오류: {type(e).__name__}: {e}"}, ensure_ascii=False)


@mcp.tool()
def verify_set_document_verdict(
    layer: str,
    verdict: str,
    notes: str = "",
    checklist_matched: list[str] | None = None,
    checklist_missed: list[str] | None = None,
    relationships_checked: list[str] | None = None,
    disclosure_in_document: bool = False,
    bbj_breaks: list[dict] | None = None,
) -> str:
    """문서 전체 레벨 판정을 등록합니다. (norm, incentive, omission)"""

    try:
        engine = _get_engine()
        lv = engine.set_document_verdict(
            layer, verdict=verdict, notes=notes,
            checklist_matched=checklist_matched or [],
            checklist_missed=checklist_missed or [],
            relationships_checked=relationships_checked or [],
            disclosure_in_document=disclosure_in_document,
            bbj_breaks=bbj_breaks or [],
        )
        logger.info(f"문서 판정 등록: document/{layer} → {verdict}")
        return json.dumps({"level": "document", "layer": layer, "verdict": verdict}, ensure_ascii=False)
    except ValueError as e:
        logger.warning(f"verify_set_document_verdict 검증 오류: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_set_document_verdict 내부 오류: {e}", exc_info=True)
        return json.dumps({"error": f"내부 오류: {type(e).__name__}: {e}"}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 2: 데이터 조회 (검증에 필요한 기준 데이터)
# ══════════════════════════════════

@mcp.tool()
def verify_get_checklist(checklist_type: str, key: str) -> str:
    """체크리스트를 조회합니다.
    checklist_type: 'norm' 또는 'omission'
    key: norm이면 doc_type (equity_research 등), omission이면 sector (반도체 등)"""

    engine = _get_engine()
    if checklist_type == "norm":
        items = engine.get_norm_checklist()
    elif checklist_type == "omission":
        items = engine.get_omission_checklist(key)
    else:
        return json.dumps({"error": f"Unknown type: {checklist_type}"})

    return json.dumps({"type": checklist_type, "key": key, "items": items, "count": len(items)}, ensure_ascii=False)


@mcp.tool()
def verify_get_rules() -> str:
    """현재 문서 유형에 해당하는 Logic 규칙을 조회합니다."""
    engine = _get_engine()
    rules = engine.get_logic_rules()
    return json.dumps({"rules": rules, "count": len(rules)}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 2.5: 커버리지 체크
# ══════════════════════════════════

@mcp.tool()
def verify_check_coverage() -> str:
    """검증 커버리지를 체크합니다. 미실행 층이 있으면 반환합니다."""
    engine = _get_engine()
    missing = engine.check_coverage()
    return json.dumps({
        "complete": len(missing) == 0,
        "missing": missing,
        "message": "모든 층 검증 완료" if not missing else f"{len(missing)}개 항목 미실행",
    }, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 3+4: 결과 생성 + 저장
# ══════════════════════════════════

@mcp.tool()
def verify_finalize(
    valid_until: str = "",
    validity_condition: str = "",
    invalidation_triggers: list[dict] | None = None,
) -> str:
    """검증을 마무리합니다. 결과 JSON을 반환합니다.
    결과 JSON을 반환합니다.

    invalidation_triggers: 자동 무효화 트리거 이벤트 목록
      예: [{"event": "FOMC 금리 결정", "expected_date": "2026-03-19", "impact": "매크로 전제 재평가"}]

    반환값의 result_json을 Phase 5 HTML 보고서 생성에 사용합니다."""

    try:
        engine = _get_engine()
        engine.result.valid_until = valid_until
        engine.result.validity_condition = validity_condition
        engine.result.invalidation_triggers = invalidation_triggers or []

        result = engine.finalize()
        result_dict = engine.get_result_dict()

        # 세션을 finalized로 마킹 (삭제하지 않음)
        vrf_id = result.vrf_id
        logger.info(
            f"검증 완료: vrf_id={vrf_id}, "
            f"claims={len(result.claims)}, "
            f"critical_flags={len(result.critical_flags)}"
        )

        response = {
            "vrf_id": vrf_id,
            "status": "finalized",
            "summary": {
                "layer_verdicts": result.summary_verdicts,
                "critical_flags": result.critical_flags,
                "valid_until": result.valid_until,
                "validity_condition": result.validity_condition,
                "claims_count": len(result.claims),
            },
            "result_json": result_dict,
        }

        # ── result_json 자동 저장 ──
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        history_path = HISTORY_DIR / f"{vrf_id}.json"
        history_path.write_text(
            json.dumps(response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        response["saved_to"] = str(history_path)
        logger.info(f"검증 결과 저장: {history_path}")

        # ── KC 자동 등록/업데이트 ──
        try:
            kc_results = extract_and_register_kcs(result_dict, vrf_id)
            if kc_results:
                response["kc_registered"] = len(kc_results)
                response["kc_active"] = sum(1 for k in kc_results if k["status"] in ("active", "approaching", "revived"))
        except Exception as e:
            logger.warning(f"KC 등록 실패 (검증 결과에 영향 없음): {e}")

        # ── 패턴 자동 기록 ──
        try:
            all_triggered = []
            for claim in result.claims:
                for layer, lv in claim.layers.items():
                    if lv.rules_triggered:
                        all_triggered.extend(lv.rules_triggered)
            if all_triggered:
                doc = engine.result.document
                patterns = record_triggered_rules(
                    vrf_id=vrf_id,
                    target_id=doc.target_id,
                    author_id=doc.author_id,
                    sector_id=doc.sector_id,
                    doc_type=doc.document_type,
                    triggered_rules=all_triggered,
                )
                proposed = [p for p in patterns if p["status"] == "proposed"]
                if proposed:
                    response["pattern_proposals"] = len(proposed)
                    response["pattern_proposal_detail"] = generate_promotion_suggestions(proposed)
                response["patterns_updated"] = len(patterns)
        except Exception as e:
            logger.warning(f"패턴 기록 실패 (검증 결과에 영향 없음): {e}")

        # ── 규칙 활성도 기록 ──
        try:
            # 적용 가능했던 전체 규칙 ID 수집
            all_applicable = [r["id"] for r in engine.get_logic_rules()]
            record_rule_activity(all_triggered, all_applicable, vrf_id)
        except Exception as e:
            logger.warning(f"규칙 활성도 기록 실패 (검증 결과에 영향 없음): {e}")

        return json.dumps(response, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_finalize 오류: {e}", exc_info=True)
        return json.dumps({"error": f"마무리 오류: {type(e).__name__}: {e}"}, ensure_ascii=False)


# ══════════════════════════════════
#  검증 이력 조회
# ══════════════════════════════════

@mcp.tool()
def verify_list_history() -> str:
    """저장된 검증 이력 목록을 반환합니다.
    각 항목에 문서 제목, 6층 판정, 유효기간, 트리거 도래 여부를 포함합니다."""
    if not HISTORY_DIR.exists():
        return json.dumps({"history": [], "count": 0}, ensure_ascii=False)

    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    # 원본만 (corrected, outcome 제외)
    files = sorted(
        [f for f in HISTORY_DIR.glob("vrf_*.json")
         if "_corrected_" not in f.name and "_outcome" not in f.name],
        reverse=True,
    )
    history = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            result_json = data.get("result_json", {})
            doc = result_json.get("document", {})

            # 트리거 도래 여부 확인
            triggers = result_json.get("invalidation_triggers", [])
            expired_triggers = [
                t for t in triggers
                if t.get("expected_date", "9999-12-31") <= today
            ]

            # 사후 결과 기록 여부
            outcome_path = HISTORY_DIR / f"{f.stem}_outcome.json"
            has_outcome = outcome_path.exists()

            history.append({
                "vrf_id": data.get("vrf_id", f.stem),
                "title": doc.get("title", ""),
                "doc_type": doc.get("document_type", ""),
                "layer_verdicts": summary.get("layer_verdicts", {}),
                "claims_count": summary.get("claims_count", 0),
                "valid_until": summary.get("valid_until", ""),
                "triggers_total": len(triggers),
                "triggers_expired": len(expired_triggers),
                "has_outcome": has_outcome,
                "file": f.name,
            })
        except Exception:
            history.append({"vrf_id": f.stem, "file": f.name, "error": "파싱 실패"})

    return json.dumps({"history": history, "count": len(history)}, ensure_ascii=False)


@mcp.tool()
def verify_load_history(vrf_id: str) -> str:
    """저장된 검증 결과를 로드합니다. Phase 5 HTML 보고서 재생성에 사용합니다.

    vrf_id: 검증 ID (예: vrf_20260319_143052_123)"""
    history_path = HISTORY_DIR / f"{vrf_id}.json"
    if not history_path.exists():
        available = [f.stem for f in HISTORY_DIR.glob("vrf_*.json")] if HISTORY_DIR.exists() else []
        return json.dumps({"error": f"이력 없음: {vrf_id}", "available": available}, ensure_ascii=False)

    data = json.loads(history_path.read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
def verify_check_triggers(vrf_id: str = "") -> str:
    """검증 결과의 무효화 트리거(invalidation_triggers)를 현재 날짜와 대조합니다.
    도래한 이벤트가 있으면 재검증이 필요함을 알려줍니다.

    vrf_id: 검증 ID (미지정 시 현재 세션 사용)

    Returns: {vrf_id, today, triggers: [{event, expected_date, impact, status}], needs_reverification}
    status: "expired" (이미 지남), "imminent" (7일 이내), "upcoming" (아직 여유)"""

    from datetime import datetime, timedelta

    try:
        target_vrf_id = vrf_id or _current_session
        if not target_vrf_id:
            return json.dumps({"error": "vrf_id를 지정하거나 활성 세션이 필요합니다"}, ensure_ascii=False)

        # 세션 또는 이력에서 로드
        triggers = []
        title = ""
        valid_until = ""

        engine = _sessions.get(target_vrf_id)
        if engine:
            triggers = engine.result.invalidation_triggers or []
            title = engine.result.document.title
            valid_until = engine.result.valid_until
        else:
            history_path = HISTORY_DIR / f"{target_vrf_id}.json"
            if not history_path.exists():
                return json.dumps({"error": f"검증 결과를 찾을 수 없습니다: {target_vrf_id}"}, ensure_ascii=False)
            data = json.loads(history_path.read_text(encoding="utf-8"))
            result_json = data.get("result_json", {})
            triggers = result_json.get("invalidation_triggers", [])
            title = result_json.get("document", {}).get("title", "")
            valid_until = data.get("summary", {}).get("valid_until", "")

        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        imminent_threshold = today + timedelta(days=7)

        checked = []
        expired_count = 0
        for t in triggers:
            expected = t.get("expected_date", "")
            if expected:
                try:
                    event_date = datetime.strptime(expected, "%Y-%m-%d")
                    if event_date <= today:
                        status = "expired"
                        expired_count += 1
                    elif event_date <= imminent_threshold:
                        status = "imminent"
                    else:
                        days_left = (event_date - today).days
                        status = f"upcoming ({days_left}일 남음)"
                except ValueError:
                    status = "날짜 형식 오류"
            else:
                status = "날짜 미지정"

            checked.append({
                "event": t.get("event", ""),
                "expected_date": expected,
                "impact": t.get("impact", ""),
                "status": status,
            })

        # valid_until 체크
        validity_expired = False
        if valid_until:
            try:
                if datetime.strptime(valid_until, "%Y-%m-%d") <= today:
                    validity_expired = True
            except ValueError:
                pass

        needs_reverification = expired_count > 0 or validity_expired

        logger.info(
            f"트리거 점검: {target_vrf_id}, "
            f"총={len(checked)}, 도래={expired_count}, 재검증필요={needs_reverification}"
        )

        # outcome 기록 안내 (도래한 트리거가 있을 때)
        outcome_path = HISTORY_DIR / f"{target_vrf_id}_outcome.json"
        has_outcome = outcome_path.exists()
        outcome_prompt = ""
        if expired_count > 0 and not has_outcome:
            expired_events = [t["event"] for t in checked if t["status"] == "expired"]
            outcome_prompt = (
                f"⚠️ {len(expired_events)}건의 트리거가 이미 지났으나 실제 결과(outcome)가 기록되지 않았습니다.\n"
                f"  도래 이벤트: {', '.join(expired_events[:3])}\n"
                f"  → verify_record_outcome('{target_vrf_id}', '실제 결과 요약')으로 기록하세요.\n"
                f"  → 기록된 outcome은 verify_analyze_outcomes()에서 패턴 분석에 활용됩니다."
            )

        return json.dumps({
            "vrf_id": target_vrf_id,
            "title": title,
            "today": today_str,
            "valid_until": valid_until,
            "validity_expired": validity_expired,
            "triggers": checked,
            "triggers_total": len(checked),
            "triggers_expired": expired_count,
            "needs_reverification": needs_reverification,
            "has_outcome": has_outcome,
            "outcome_prompt": outcome_prompt,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_check_triggers 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def verify_record_outcome(
    vrf_id: str,
    actual_result: str,
    outcome_date: str = "",
    notes: str = "",
) -> str:
    """검증 이후 실제 결과를 기록합니다. 검증 판정이 맞았는지 사후 추적용.

    vrf_id: 검증 ID
    actual_result: 실제 결과 요약 (예: "목표가 10만원 제시 → 실제 8만원, 20% 괴리")
    outcome_date: 결과 확인 날짜 (미지정 시 오늘)
    notes: 추가 메모 (예: "Fact는 맞았으나 Logic 전제가 틀림")

    Returns: {vrf_id, saved_to, original_verdicts, outcome}"""

    from datetime import datetime

    try:
        # 원본 검증 결과 확인
        history_path = HISTORY_DIR / f"{vrf_id}.json"
        if not history_path.exists():
            available = [f.stem for f in HISTORY_DIR.glob("vrf_*.json")
                         if "_corrected_" not in f.name and "_outcome" not in f.name] if HISTORY_DIR.exists() else []
            return json.dumps({"error": f"검증 이력 없음: {vrf_id}", "available": available}, ensure_ascii=False)

        original = json.loads(history_path.read_text(encoding="utf-8"))
        original_verdicts = original.get("summary", {}).get("layer_verdicts", {})
        title = original.get("result_json", {}).get("document", {}).get("title", "")

        effective_date = outcome_date or datetime.now().strftime("%Y-%m-%d")

        outcome = {
            "vrf_id": vrf_id,
            "title": title,
            "original_verdicts": original_verdicts,
            "outcome_date": effective_date,
            "actual_result": actual_result,
            "notes": notes,
            "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 저장 (별도 파일로, 원본 불변)
        outcome_path = HISTORY_DIR / f"{vrf_id}_outcome.json"
        outcome_path.write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"사후 결과 기록: {vrf_id} → {outcome_path.name}")

        return json.dumps({
            "vrf_id": vrf_id,
            "title": title,
            "original_verdicts": original_verdicts,
            "outcome_date": effective_date,
            "actual_result": actual_result,
            "saved_to": str(outcome_path),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_record_outcome 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  피드백 루프: outcome 패턴 분석 → 규칙 자동 제안
# ══════════════════════════════════

@mcp.tool()
def verify_analyze_outcomes() -> str:
    """축적된 outcome 데이터를 분석하여 검증 실패 패턴을 찾고,
    rules.json / checklists.json에 추가할 규칙·체크리스트를 제안합니다.

    이 도구는 분석 결과와 제안만 반환합니다.
    사용자가 승인하면 verify_add_rule() / verify_add_checklist_item()으로 실제 추가합니다.

    Returns: {outcomes_analyzed, failure_patterns, suggested_rules, suggested_checklists}"""

    try:
        if not HISTORY_DIR.exists():
            return json.dumps({"error": "검증 이력이 없습니다", "outcomes_analyzed": 0}, ensure_ascii=False)

        # ── 1. 모든 outcome 수집 ──
        outcome_files = sorted(HISTORY_DIR.glob("vrf_*_outcome.json"))
        if not outcome_files:
            return json.dumps({
                "outcomes_analyzed": 0,
                "message": "outcome 기록이 없습니다. verify_record_outcome()으로 실제 결과를 먼저 기록하세요.",
            }, ensure_ascii=False)

        outcomes = []
        for f in outcome_files:
            try:
                outcome = json.loads(f.read_text(encoding="utf-8"))
                vrf_id = outcome.get("vrf_id", "")

                # 원본 검증 결과도 로드
                original_path = HISTORY_DIR / f"{vrf_id}.json"
                if original_path.exists():
                    original = json.loads(original_path.read_text(encoding="utf-8"))
                    result_json = original.get("result_json", {})
                    doc = result_json.get("document", {})
                    outcomes.append({
                        "vrf_id": vrf_id,
                        "title": doc.get("title", ""),
                        "doc_type": doc.get("document_type", ""),
                        "sector_id": doc.get("sector_id", ""),
                        "target_id": doc.get("target_id", ""),
                        "layer_verdicts": original.get("summary", {}).get("layer_verdicts", {}),
                        "critical_flags": original.get("summary", {}).get("critical_flags", []),
                        "actual_result": outcome.get("actual_result", ""),
                        "notes": outcome.get("notes", ""),
                    })
            except Exception:
                continue

        if not outcomes:
            return json.dumps({
                "outcomes_analyzed": 0,
                "message": "outcome 파일이 있으나 원본 검증과 매칭할 수 없습니다.",
            }, ensure_ascii=False)

        # ── 2. 패턴 분석 ──

        # 2a. 층별 실패 빈도
        layer_names = ["fact", "norm", "logic", "temporal", "incentive", "omission"]
        layer_fail_count = {l: 0 for l in layer_names}    # 🟢인데 outcome에서 틀린 경우
        layer_correct_count = {l: 0 for l in layer_names}  # 🔴/🟡인데 outcome에서도 맞은 경우
        layer_total = {l: 0 for l in layer_names}

        # 2b. sector별 실패 빈도
        sector_failures = {}  # sector → 실패 횟수

        # 2c. target별 반복 검증
        target_history = {}  # target_id → [outcomes]

        # 2d. notes에서 키워드 추출 (어떤 층이 문제였는지)
        notes_keywords = {l: 0 for l in layer_names}

        for o in outcomes:
            verdicts = o.get("layer_verdicts", {})
            notes = (o.get("notes", "") or "").lower()
            sector = o.get("sector_id", "unknown")
            target = o.get("target_id", "")

            # notes에서 층 이름 언급 빈도
            for l in layer_names:
                if l in notes:
                    notes_keywords[l] += 1

            # 층별 집계
            for l in layer_names:
                v = verdicts.get(l, "")
                if v and v != "N/A":
                    layer_total[l] += 1
                    # 🟢로 통과시켰는데 notes에 해당 층이 언급됨 = 해당 층이 잡지 못한 것
                    if v == "🟢" and l in notes:
                        layer_fail_count[l] += 1

            # sector별 실패
            if notes:  # notes가 있으면 = 뭔가 틀린 것
                sector_failures[sector] = sector_failures.get(sector, 0) + 1

            # target별
            if target:
                if target not in target_history:
                    target_history[target] = []
                target_history[target].append(o)

        # ── 3. 실패 패턴 정리 ──
        failure_patterns = []

        # 3a. 취약한 층 (🟢 판정 → 실제 틀림 비율 높은 층)
        for l in layer_names:
            if layer_total[l] > 0 and layer_fail_count[l] > 0:
                fail_rate = layer_fail_count[l] / layer_total[l]
                if fail_rate >= 0.3 or layer_fail_count[l] >= 2:
                    failure_patterns.append({
                        "type": "weak_layer",
                        "layer": l,
                        "fail_count": layer_fail_count[l],
                        "total": layer_total[l],
                        "fail_rate": round(fail_rate * 100, 1),
                        "description": f"{l} 층이 🟢로 통과시켰으나 실제로 틀린 비율: {round(fail_rate * 100, 1)}% ({layer_fail_count[l]}/{layer_total[l]}건)",
                    })

        # 3b. 취약한 sector
        for sector, count in sorted(sector_failures.items(), key=lambda x: -x[1]):
            if count >= 2:
                failure_patterns.append({
                    "type": "weak_sector",
                    "sector": sector,
                    "fail_count": count,
                    "description": f"'{sector}' 섹터에서 {count}건 실패. 해당 섹터의 체크리스트/규칙 보강 필요",
                })

        # 3c. 반복 실패 target
        for target, hist in target_history.items():
            if len(hist) >= 2:
                failure_patterns.append({
                    "type": "repeat_target",
                    "target_id": target,
                    "count": len(hist),
                    "description": f"'{target}' 대상이 {len(hist)}회 검증됨. 반복 실패 여부 확인 필요",
                    "history": [{"vrf_id": h["vrf_id"], "notes": h.get("notes", "")} for h in hist],
                })

        # ── 4. 규칙/체크리스트 제안 생성 ──
        suggested_rules = []
        suggested_checklists = []

        # 기존 규칙 ID 확인 (중복 방지)
        rules_path = DATA_DIR / "rules.json"
        existing_rule_ids = set()
        if rules_path.exists():
            rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
            existing_rule_ids = {r["id"] for rules in rules_data.values() for r in rules}

        # 체크리스트 ID 확인
        checklists_path = DATA_DIR / "checklists.json"
        existing_checklist_ids = set()
        if checklists_path.exists():
            cl_data = json.loads(checklists_path.read_text(encoding="utf-8"))
            for section in cl_data.values():
                if isinstance(section, dict):
                    for items in section.values():
                        if isinstance(items, list):
                            for item in items:
                                if isinstance(item, dict) and "id" in item:
                                    existing_checklist_ids.add(item["id"])

        auto_rule_counter = 1
        auto_cl_counter = 1

        for p in failure_patterns:
            if p["type"] == "weak_layer":
                layer = p["layer"]
                rule_id = f"lr_auto_{auto_rule_counter:03d}"
                while rule_id in existing_rule_ids:
                    auto_rule_counter += 1
                    rule_id = f"lr_auto_{auto_rule_counter:03d}"

                if layer == "logic":
                    suggested_rules.append({
                        "rule_id": rule_id,
                        "doc_type": "common",
                        "name": f"outcome_logic_tighten_{auto_rule_counter}",
                        "condition": "Logic 층에서 KC 미확인(🟡)인 claim이 있을 때",
                        "flag": f"과거 {p['fail_count']}건에서 Logic 🟢→실제 틀림. KC 미확인 시 🟡가 아닌 🔴 격상 검토",
                        "severity": "high",
                        "reason": f"outcome 분석: Logic 실패율 {p['fail_rate']}%",
                    })
                elif layer == "fact":
                    suggested_rules.append({
                        "rule_id": rule_id,
                        "doc_type": "common",
                        "name": f"outcome_fact_crosscheck_{auto_rule_counter}",
                        "condition": "Fact 층에서 Tier 2 소스 단독으로 🟢 판정할 때",
                        "flag": f"과거 {p['fail_count']}건에서 Fact 🟢→실제 불일치. Tier 2 단독 🟢 시 반드시 교차검증",
                        "severity": "high",
                        "reason": f"outcome 분석: Fact 실패율 {p['fail_rate']}%",
                    })
                elif layer == "temporal":
                    suggested_rules.append({
                        "rule_id": rule_id,
                        "doc_type": "common",
                        "name": f"outcome_temporal_tighten_{auto_rule_counter}",
                        "condition": "데이터 기준 시점이 8~30일 범위(🟡)일 때",
                        "flag": f"과거 {p['fail_count']}건에서 Temporal 🟢→실제 변동. 8~30일 gap은 material_change 추가 확인",
                        "severity": "medium",
                        "reason": f"outcome 분석: Temporal 실패율 {p['fail_rate']}%",
                    })
                elif layer == "omission":
                    suggested_rules.append({
                        "rule_id": rule_id,
                        "doc_type": "common",
                        "name": f"outcome_omission_expand_{auto_rule_counter}",
                        "condition": "BBJ Break가 1개만 생성되었을 때",
                        "flag": f"과거 {p['fail_count']}건에서 Omission이 리스크를 놓침. BBJ Break를 반드시 2개 생성",
                        "severity": "high",
                        "reason": f"outcome 분석: Omission 실패율 {p['fail_rate']}%",
                    })
                else:
                    suggested_rules.append({
                        "rule_id": rule_id,
                        "doc_type": "common",
                        "name": f"outcome_{layer}_review_{auto_rule_counter}",
                        "condition": f"{layer} 층 판정 시",
                        "flag": f"과거 {p['fail_count']}건에서 {layer} 🟢→실제 틀림. 판정 근거를 더 엄격하게 확인",
                        "severity": "medium",
                        "reason": f"outcome 분석: {layer} 실패율 {p['fail_rate']}%",
                    })
                auto_rule_counter += 1

            elif p["type"] == "weak_sector":
                sector = p["sector"]
                cl_id = f"om_auto_{auto_cl_counter:03d}"
                while cl_id in existing_checklist_ids:
                    auto_cl_counter += 1
                    cl_id = f"om_auto_{auto_cl_counter:03d}"

                suggested_checklists.append({
                    "checklist_type": "omission",
                    "key": sector,
                    "item_id": cl_id,
                    "item_text": f"과거 검증 실패 반복 영역 ({p['fail_count']}건). 추가 리스크 항목 점검 필요",
                    "severity_or_impact": "high",
                    "reason": f"'{sector}' 섹터에서 {p['fail_count']}건 outcome 불일치",
                })
                auto_cl_counter += 1

        logger.info(
            f"outcome 분석 완료: {len(outcomes)}건 분석, "
            f"패턴 {len(failure_patterns)}건, "
            f"규칙 제안 {len(suggested_rules)}건, "
            f"체크리스트 제안 {len(suggested_checklists)}건"
        )

        # changelog에 분석 실행 기록
        _append_changelog({
            "type": "outcome_analysis",
            "outcomes_analyzed": len(outcomes),
            "patterns_found": len(failure_patterns),
            "rules_suggested": len(suggested_rules),
            "checklists_suggested": len(suggested_checklists),
            "source": "verify_analyze_outcomes",
        })

        return json.dumps({
            "outcomes_analyzed": len(outcomes),
            "failure_patterns": failure_patterns,
            "suggested_rules": suggested_rules,
            "suggested_checklists": suggested_checklists,
            "next_step": (
                "제안된 규칙/체크리스트를 검토하신 후:\n"
                "  - 규칙 추가: verify_add_rule(doc_type, rule_id, name, condition, flag, severity)\n"
                "  - 체크리스트 추가: verify_add_checklist_item(checklist_type, key, item_id, item_text, severity_or_impact)\n"
                "  - 추가된 규칙은 다음 검증부터 코드가 자동으로 대입합니다."
            ),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_analyze_outcomes 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  KC 생명주기 + 패턴 레지스트리
# ══════════════════════════════════

@mcp.tool()
def verify_get_kc_status(sector: str = "") -> str:
    """활성 KC(Kill Condition) 목록과 상태를 반환합니다.
    sector를 지정하면 해당 섹터의 KC만 필터링합니다.

    KC 상태: active(미충족) → approaching(gap≤10%) → resolved(충족) → revived(부활)"""

    try:
        if sector:
            kcs = get_active_kcs(sector)
        else:
            kcs = get_all_kcs()

        active = [k for k in kcs if k["status"] in ("active", "approaching", "revived")]

        return json.dumps({
            "total": len(kcs),
            "active_count": len(active),
            "kcs": kcs,
            "status_summary": {
                "active": sum(1 for k in kcs if k["status"] == "active"),
                "approaching": sum(1 for k in kcs if k["status"] == "approaching"),
                "resolved": sum(1 for k in kcs if k["status"] == "resolved"),
                "revived": sum(1 for k in kcs if k["status"] == "revived"),
            },
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def verify_update_kc(kc_id: str, current_value: float) -> str:
    """KC의 현재값을 MCP 데이터로 갱신하고 상태 전이를 수행합니다.

    kc_id: KC 식별자 (예: KC-1)
    current_value: MCP로 조회한 현재 값

    상태 전이: gap≤10% → approaching, 조건 충족 → resolved, 다시 미충족 → revived"""

    try:
        result = update_kc_value(kc_id, current_value)
        if result:
            _append_changelog({
                "type": "kc_updated",
                "id": kc_id,
                "value": current_value,
                "status": result["status"],
                "source": "verify_update_kc",
            })
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": f"KC를 찾을 수 없습니다: {kc_id}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def verify_get_patterns(author_id: str = "") -> str:
    """패턴 레지스트리를 조회합니다. 반복되는 검증 실패 패턴을 추적합니다.

    author_id: 특정 기관의 패턴만 조회 (미지정 시 전체)

    상태: flag(1회) → candidate(2회) → proposed(≥3회, 승격 제안) → promoted(규칙화 완료)"""

    try:
        if author_id:
            from core.pattern_registry import get_patterns_for_author
            patterns = get_patterns_for_author(author_id)
        else:
            patterns = get_all_patterns()

        proposed = [p for p in patterns if p["status"] == "proposed"]
        suggestions = generate_promotion_suggestions(proposed)

        return json.dumps({
            "total": len(patterns),
            "patterns": patterns,
            "status_summary": {
                "flag": sum(1 for p in patterns if p["status"] == "flag"),
                "candidate": sum(1 for p in patterns if p["status"] == "candidate"),
                "proposed": sum(1 for p in patterns if p["status"] == "proposed"),
                "promoted": sum(1 for p in patterns if p["status"] == "promoted"),
                "dismissed": sum(1 for p in patterns if p["status"] == "dismissed"),
            },
            "promotion_suggestions": suggestions,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def verify_promote_pattern(pattern_id: str, promoted_as: str) -> str:
    """패턴을 규칙으로 승격 완료 처리합니다.
    verify_add_rule()로 규칙을 추가한 뒤 이 도구로 패턴 상태를 promoted로 변경합니다.

    pattern_id: 패턴 ID (예: pt_001)
    promoted_as: 승격된 규칙 ID (예: lr_auto_001)"""

    try:
        result = promote_pattern(pattern_id, promoted_as)
        if result:
            _append_changelog({
                "type": "pattern_promoted",
                "pattern_id": pattern_id,
                "promoted_as": promoted_as,
                "source": "verify_promote_pattern",
            })
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": f"패턴을 찾을 수 없습니다: {pattern_id}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  규칙 활성도 조회
# ══════════════════════════════════

@mcp.tool()
def verify_rule_activity() -> str:
    """규칙별 활성도(trigger 횟수, 적용 횟수)를 반환합니다.
    죽은 규칙(적용됐으나 한 번도 trigger 안 됨)과 핵심 규칙(자주 trigger)을 식별합니다.

    Returns: {total_tracked, hot_rules, dead_rules, all_activity}"""

    try:
        activity = get_rule_activity()
        dead = get_dead_rules()
        hot = get_hot_rules(min_triggers=2)

        return json.dumps({
            "total_tracked": len(activity),
            "hot_rules": hot,
            "hot_count": len(hot),
            "dead_rules": dead,
            "dead_count": len(dead),
            "all_activity": activity,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  미세조정 (Fine-tuning)
# ══════════════════════════════════

@mcp.tool()
def verify_tune() -> str:
    """검증 결과와 outcome을 분석하여 미세조정 제안을 생성합니다.

    4가지 분석:
    1. 규칙 정밀도 — outcome 대비 과잉/미탐지 식별 → severity 조정 제안
    2. 매체별 프로필 — 어떤 매체가 어떤 층에서 주로 걸리는지 → 검증 강도 조정 제안
    3. 수집 효과 — 어떤 doc_type이 검증 학습에 기여하는지 → 수집 방향 제안
    4. (outcome 필요) 규칙별 정확도 — trigger된 규칙이 실제로 맞았는지

    Returns: {rule_accuracy, media_profiles, collection_effectiveness, suggestions}"""

    try:
        result = run_full_tuning()

        # 종합 제안 생성
        suggestions = []

        # 규칙 정확도 기반 제안
        for r in result.get("rule_accuracy", []):
            suggestions.append(r["suggestion"])

        # 매체 프로필 기반 제안
        for p in result.get("media_profiles", []):
            if p.get("suggestion"):
                suggestions.append(p["suggestion"])

        # 수집 효과 기반 제안
        for e in result.get("collection_effectiveness", []):
            suggestions.append(e["suggestion"])

        if not suggestions:
            suggestions.append("데이터 부족. 검증 건수를 늘리고 outcome을 기록하세요.")

        result["suggestions_summary"] = suggestions

        _append_changelog({
            "type": "tuning_executed",
            "rule_accuracy_count": len(result.get("rule_accuracy", [])),
            "media_profiles_count": len(result.get("media_profiles", [])),
            "collection_effectiveness_count": len(result.get("collection_effectiveness", [])),
            "source": "verify_tune",
        })

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_tune 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  간이 검증 (Quick Check)
# ══════════════════════════════════

@mcp.tool()
def verify_quick_check(
    title: str,
    description: str = "",
    doc_type: str = "news_article",
    author_id: str = "",
    source_url: str = "",
) -> str:
    """제목+설명만으로 간이 검증합니다. 3~5개 핵심 claim만 추출하여 Fact+Logic 중심 판정.
    전체 검증(Phase 0~5)의 경량 버전으로, 패턴 레지스트리에 동일하게 기록됩니다.

    심각한 문제 발견 시 '전체 검증 권장'을 표시합니다.
    HTML 보고서는 생성하지 않습니다.

    title: 문서/기사/영상 제목
    description: 부제, 설명, 요약 (있으면)
    doc_type: 문서 유형 (기본: news_article)
    author_id: 저자/기관
    source_url: 원문 URL

    Returns: {vrf_id, quick_verdict, claims, flags, needs_full_verification, patterns_updated}"""

    try:
        engine = VerificationEngine()

        try:
            engine.set_document(
                title=title, doc_type=doc_type, target_id="",
                author_id=author_id, source_url=source_url,
            )
        except ValueError:
            engine.set_document(
                title=title, doc_type="news_article", target_id="",
                author_id=author_id, source_url=source_url,
            )

        vrf_id = engine.result.vrf_id

        # 규칙 로드
        logic_rules = engine.get_logic_rules()
        norm_checklist = engine.get_norm_checklist()

        # 간이 판정용 정보 반환 — Claude가 이것을 보고 간이 검증 수행
        result = {
            "vrf_id": vrf_id,
            "mode": "quick_check",
            "title": title,
            "description": description,
            "doc_type": doc_type,
            "author_id": author_id,
            "logic_rules_count": len(logic_rules),
            "norm_checklist_count": len(norm_checklist),
            "instructions": (
                "간이 검증 모드입니다. 아래 순서로 수행하세요:\n"
                "1. 제목+설명에서 핵심 claim 3~5개를 추출하여 verify_add_claim()으로 등록\n"
                "2. 각 claim에 Fact(MCP 교차검증)와 Logic(규칙 대입) 판정만 등록\n"
                "3. Norm은 문서 전체로 간이 판정 (nr_news_004 헤드라인 정합성 중심)\n"
                "4. Temporal, Incentive는 생략 가능\n"
                "5. Omission은 BBJ Break 생략, 체크리스트만 간이 점검\n"
                "6. verify_finalize()로 마무리 (KC 1단만, ACH 생략)\n"
                "7. HTML 보고서는 생성하지 않음\n"
                "※ 🔴 1개 이상 발견 시 → needs_full_verification = true"
            ),
        }

        # 세션 등록 (finalize까지 사용)
        global _current_session
        _sessions[vrf_id] = engine
        _current_session = vrf_id

        logger.info(f"간이 검증 시작: {vrf_id}, title={title[:50]}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_quick_check 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 4.5: 체크리스트·규칙 동적 관리
# ══════════════════════════════════

@mcp.tool()
def verify_add_checklist_item(
    checklist_type: str,
    key: str,
    item_id: str,
    item_text: str,
    severity_or_impact: str = "medium",
    keywords: list[str] | None = None,
    regulation: str = "",
) -> str:
    """체크리스트에 새 항목을 추가합니다. self_audit 후 사용자가 "체크리스트 추가해줘"라고 하면 사용.

    checklist_type: 'norm' 또는 'omission'
    key: norm이면 doc_type (equity_research 등), omission이면 sector (반도체 등)
    item_id: 고유 ID (예: nr_eq_006, om_semi_007)
    item_text: 체크 항목 설명
    severity_or_impact: norm은 severity (low/medium/high), omission은 impact (medium/high/critical)
    keywords: 키워드 스캔용 단어 리스트
    regulation: (norm만) 관련 법규"""

    try:
        path = DATA_DIR / "checklists.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        if checklist_type not in ("norm", "omission"):
            return json.dumps({"error": f"checklist_type은 'norm' 또는 'omission'만 가능합니다. 받은 값: '{checklist_type}'"}, ensure_ascii=False)

        section = data.get(checklist_type, {})
        if key not in section:
            section[key] = []
            data[checklist_type] = section

        # 중복 ID 체크
        existing_ids = {i["id"] for i in section[key]}
        if item_id in existing_ids:
            return json.dumps({"error": f"이미 존재하는 ID: {item_id}"}, ensure_ascii=False)

        # 항목 구성
        if checklist_type == "norm":
            new_item = {
                "id": item_id,
                "item": item_text.replace(" ", "_").lower(),
                "description": item_text,
                "regulation": regulation,
                "severity": severity_or_impact,
                "scan_keywords": keywords or [],
            }
        else:  # omission
            new_item = {
                "id": item_id,
                "item": item_text,
                "impact": severity_or_impact,
                "keywords": keywords or [],
            }

        section[key].append(new_item)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # JSON 캐시 클리어
        NormLayer.clear_cache()
        OmissionLayer.clear_cache()

        logger.info(f"체크리스트 추가: {checklist_type}/{key}/{item_id}")

        # changelog 자동 기록
        _append_changelog({
            "type": "checklist_added",
            "id": item_id,
            "scope": f"{checklist_type}/{key}",
            "description": item_text,
            "severity": severity_or_impact,
            "source": "verify_add_checklist_item",
        })

        return json.dumps({
            "status": "added",
            "checklist_type": checklist_type,
            "key": key,
            "id": item_id,
            "total_items": len(section[key]),
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_add_checklist_item 오류: {e}", exc_info=True)
        return json.dumps({"error": f"체크리스트 추가 오류: {e}"}, ensure_ascii=False)


@mcp.tool()
def verify_add_rule(
    doc_type: str,
    rule_id: str,
    name: str,
    condition: str,
    flag: str,
    severity: str = "medium",
) -> str:
    """Logic 규칙을 추가합니다. self_audit 후 사용자가 "규칙 추가해줘"라고 하면 사용.

    doc_type: 문서 유형 또는 'common' (모든 유형 공통)
    rule_id: 고유 ID (예: lr_013)
    name: 규칙 이름 (snake_case)
    condition: 트리거 조건
    flag: 위반 시 표시할 메시지
    severity: low, medium, high, critical"""

    try:
        path = DATA_DIR / "rules.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        if doc_type not in data:
            data[doc_type] = []

        # 전체에서 중복 ID 체크
        all_ids = {r["id"] for rules in data.values() for r in rules}
        if rule_id in all_ids:
            return json.dumps({"error": f"이미 존재하는 ID: {rule_id}"}, ensure_ascii=False)

        valid_severities = {"low", "medium", "high", "critical"}
        if severity not in valid_severities:
            return json.dumps({"error": f"severity는 {sorted(valid_severities)} 중 하나여야 합니다"}, ensure_ascii=False)

        new_rule = {
            "id": rule_id,
            "name": name,
            "condition": condition,
            "flag": flag,
            "severity": severity,
        }

        data[doc_type].append(new_rule)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # JSON 캐시 클리어
        LogicLayer.clear_cache()

        logger.info(f"규칙 추가: {doc_type}/{rule_id} ({name})")

        # changelog 자동 기록
        _append_changelog({
            "type": "rule_added",
            "id": rule_id,
            "scope": doc_type,
            "name": name,
            "severity": severity,
            "condition": condition,
            "flag": flag,
            "source": "verify_add_rule",
        })

        return json.dumps({
            "status": "added",
            "doc_type": doc_type,
            "id": rule_id,
            "total_rules": len(data[doc_type]),
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"verify_add_rule 오류: {e}", exc_info=True)
        return json.dumps({"error": f"규칙 추가 오류: {e}"}, ensure_ascii=False)


# ══════════════════════════════════
#  프롬프트 조회 (두뇌)
# ══════════════════════════════════

@mcp.tool()
def verify_get_prompt(phase: str) -> str:
    """검증 단계별 프롬프트를 반환합니다. Claude가 이 프롬프트를 따라 검증을 수행합니다.

    phase: extract_claims, fact_check, norm_check, logic_check,
           temporal_check, incentive_check, omission_check,
           coverage_recheck, finalize, self_audit

    ★ self_audit 프롬프트에는 {coverage_report}가 자동 주입됩니다."""

    # 프롬프트 경로 탐색 (우선순위: prompts/ → schemas/)
    prompt_path = PROMPTS_DIR / f"{phase}.md"
    if not prompt_path.exists():
        prompt_path = PROMPTS_DIR / "schemas" / f"{phase}.md"
    if not prompt_path.exists():
        available = [f.stem for f in PROMPTS_DIR.glob("**/*.md")]
        return json.dumps({"error": f"프롬프트 없음: {phase}", "available": available})

    prompt = prompt_path.read_text(encoding="utf-8")

    # 엔진이 있으면 동적 데이터를 플레이스홀더에 삽입
    engine = _get_engine() if _current_session else None
    if engine:
        if "{mcp_sources}" in prompt:
            prompt = prompt.replace("{mcp_sources}", json.dumps(engine.get_fact_sources(), ensure_ascii=False, indent=2))
        if "{checklist}" in prompt:
            prompt = prompt.replace("{checklist}", json.dumps(engine.get_norm_checklist(), ensure_ascii=False, indent=2))
        if "{rules}" in prompt:
            prompt = prompt.replace("{rules}", json.dumps(engine.get_logic_rules(), ensure_ascii=False, indent=2))
        if "{omission_checklist}" in prompt:
            sector = engine.result.document.sector_id
            prompt = prompt.replace("{omission_checklist}", json.dumps(engine.get_omission_checklist(sector), ensure_ascii=False, indent=2))
        if "{check_items}" in prompt:
            prompt = prompt.replace("{check_items}", json.dumps(engine.get_incentive_checks(), ensure_ascii=False, indent=2))
        if "{missing_items}" in prompt:
            prompt = prompt.replace("{missing_items}", json.dumps(engine.check_coverage(), ensure_ascii=False, indent=2))
        if "{author}" in prompt:
            prompt = prompt.replace("{author}", engine.result.document.author_id)
        if "{institution}" in prompt:
            prompt = prompt.replace("{institution}", engine.result.document.institution_id)
        if "{doc_type}" in prompt:
            prompt = prompt.replace("{doc_type}", engine.result.document.document_type)

        # ── 결함#2 수정: {document}, {claims}, {data} 플레이스홀더 주입 ──
        if "{document}" in prompt:
            prompt = prompt.replace("{document}",
                "[현재 대화 컨텍스트의 검증 대상 문서를 사용하라. "
                "문서가 대화에 없으면 사용자에게 문서를 제공해달라고 요청하라.]"
            )
        if "{claims}" in prompt:
            claims_data = [c.to_dict() for c in engine.result.claims]
            prompt = prompt.replace("{claims}", json.dumps(claims_data, ensure_ascii=False, indent=2))
        if "{data}" in prompt:
            prompt = prompt.replace("{data}", json.dumps(engine.get_result_dict(), ensure_ascii=False, indent=2))

        # ── 결함#6 수정: Fact→Temporal 값 전달 ──
        if "{fact_evidence}" in prompt:
            fact_evidence = {}
            for claim in engine.result.claims:
                fact_lv = claim.layers.get("fact")
                if fact_lv and fact_lv.evidence:
                    fact_evidence[claim.claim_id] = {
                        "text": claim.text,
                        "evidence": fact_lv.evidence,
                        "verdict": fact_lv.verdict,
                    }
            prompt = prompt.replace("{fact_evidence}", json.dumps(fact_evidence, ensure_ascii=False, indent=2))

        # ── 결함#8 수정: self_audit에 결과 데이터 주입 ──
        if "{result_json}" in prompt:
            prompt = prompt.replace("{result_json}", json.dumps(engine.get_result_dict(), ensure_ascii=False, indent=2))

        # ── 도메인 커버리지 보고 주입 (self_audit용) ──
        if "{coverage_report}" in prompt:
            prompt = prompt.replace("{coverage_report}", json.dumps(engine.get_coverage_report(), ensure_ascii=False, indent=2))


    return prompt


@mcp.tool()
def verify_list_prompts() -> str:
    """사용 가능한 검증 프롬프트 목록을 반환합니다."""

    prompts = []
    # prompts/ 폴더
    for f in sorted(PROMPTS_DIR.glob("**/*.md")):
        rel = f.relative_to(PROMPTS_DIR)
        prompts.append({
            "phase": f.stem,
            "filename": f"prompts/{rel}",
            "size_chars": len(f.read_text(encoding="utf-8")),
        })
    return json.dumps({
        "prompts": prompts,
        "count": len(prompts),
        "execution_order": [
            "verify_orchestrator() → CLAUDE.md + SKILL.md 로드 (가장 먼저)",
            "extract_claims → Phase 1: 주장 분해",
            "fact_check → ① Fact Ground",
            "norm_check → ② Norm Ground (문서 전체)",
            "logic_check → ③ Logic Ground + KC 추출",
            "temporal_check → ④ Temporal Ground",
            "incentive_check → ⑤ Incentive Ground (문서 전체)",
            "omission_check → ⑥ Omission Ground + BBJ Break",
            "coverage_recheck → Phase 2.5: 누락 재점검",
            "finalize → Phase 3+4: 마무리 (유효기간 + 무효화 트리거) → result_json 자동 저장",
            "self_audit → Phase 4.5: 자기 점검 → 사용자 승인 대기",
            "Phase 5 (사용자 승인 후) → SKILL.md §5 → HTML 보고서 생성",
            "verify_list_history() / verify_load_history() → 이력 조회·재활용",
            "verify_check_triggers(vrf_id) → 무효화 이벤트 도래 여부 점검",
            "verify_record_outcome(vrf_id, actual_result) → 사후 실제 결과 기록",
            "verify_analyze_outcomes() → outcome 패턴 분석 → 규칙/체크리스트 추가 제안",
            "verify_get_kc_status(sector?) → KC 생명주기 조회 (active/approaching/resolved/revived)",
            "verify_update_kc(kc_id, value) → KC 현재값 갱신 + 상태 전이",
            "verify_get_patterns(author?) → 패턴 레지스트리 조회 (flag/candidate/proposed/promoted)",
            "verify_promote_pattern(pattern_id, promoted_as) → 패턴 승격 완료 처리",
            "verify_rule_activity() → 규칙별 trigger 횟수·핵심 규칙·죽은 규칙 식별",
            "verify_quick_check(title, description?) → 간이 검증 (Fact+Logic 중심, 3~5 claims)",
            "verify_tune() → 미세조정 분석 (규칙 정밀도 + 매체 프로필 + 수집 효과)",
        ],
    }, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 1 자동화: 뉴스분석 → Claim 일괄 등록
# ══════════════════════════════════

@mcp.tool()
def verify_import_news_analysis(
    markdown: str,
    doc_type: str = "",
    sector_id: str = "",
) -> str:
    """news-essence-analyzer 출력(속보카드/브리프/풀분석)을 파싱하여
    claim을 일괄 등록합니다. verify_start() + verify_add_claim() x N을 자동 수행.

    markdown: news-essence-analyzer가 생성한 마크다운 전체 텍스트
    doc_type: 문서 유형 (미지정시 기사 성격에서 자동 추론)
    sector_id: 섹터 (미지정시 기사에서 자동 추론)

    Returns: {vrf_id, format_detected, claims_imported: [...], total}"""

    try:
        # 1) 파싱
        claims_list, meta = NewsAnalysisAdapter.parse(markdown)

        # 2) doc_type / sector 추론
        effective_doc_type = doc_type or NewsAnalysisAdapter.infer_doc_type(markdown)
        effective_sector = sector_id or NewsAnalysisAdapter.infer_sector(markdown)
        title = meta.title or meta.what or "뉴스 분석"

        # 3) 엔진 생성 + 문서 설정
        global _current_session
        engine = VerificationEngine()
        try:
            engine.set_document(
                title=title,
                doc_type=effective_doc_type,
                sector_id=effective_sector,
                source_url="",
                date_published=meta.date,
            )
        except ValueError:
            # doc_type이 지원 목록에 없으면 macro_report로 폴백
            engine.set_document(
                title=title,
                doc_type="macro_report",
                sector_id=effective_sector,
                source_url="",
                date_published=meta.date,
            )
            effective_doc_type = "macro_report"

        # 4) Claim 일괄 등록
        imported = []
        for c in claims_list:
            try:
                claim = engine.add_claim(
                    c["claim_id"], c["text"], c["claim_type"],
                    c["evidence_type"], c["location"], c["depends_on"],
                )
                imported.append({
                    "claim_id": c["claim_id"],
                    "claim_type": c["claim_type"],
                    "evidence_type": c["evidence_type"],
                    "text": c["text"][:80],
                })
            except Exception as e:
                logger.warning(f"Claim 등록 실패: {c['claim_id']} — {e}")

        # 5) 세션 등록
        vrf_id = engine.result.vrf_id
        _sessions[vrf_id] = engine
        _current_session = vrf_id

        logger.info(
            f"뉴스분석 임포트 완료: vrf_id={vrf_id}, "
            f"format={meta.format_type}, claims={len(imported)}"
        )

        return json.dumps({
            "vrf_id": vrf_id,
            "format_detected": meta.format_type,
            "doc_type": effective_doc_type,
            "sector_id": effective_sector,
            "title": title,
            "claims_imported": imported,
            "total": len(imported),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_import_news_analysis 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 4.5+: 수정 적용
# ══════════════════════════════════

@mcp.tool()
def verify_apply_corrections(
    findings: list[dict],
    approved_ids: list[str],
    vrf_id: str = "",
    auto_apply_definitive: bool = True,
) -> str:
    """Finding Card의 수정 제안을 원본 검증 결과에 적용합니다.

    findings: Finding Card 딕셔너리 리스트
      각 항목: {finding_id, layer, verdict, claim_id, location,
               original_text, error_type, evidence, fix_confidence, suggested_fix}
    approved_ids: 사용자가 승인한 finding_id 리스트
    vrf_id: 수정할 검증 ID (미지정 시 현재 세션)
    auto_apply_definitive: True이면 확정(definitive) 수정은 자동 적용

    Returns: {vrf_id, applied_count, skipped_count, corrections_log, saved_to, version}"""

    try:
        # 원본 result_json 획득
        target_vrf_id = vrf_id or _current_session
        if not target_vrf_id:
            return json.dumps({"error": "활성 세션이 없습니다"}, ensure_ascii=False)

        # 세션에서 가져오기 시도
        engine = _sessions.get(target_vrf_id)
        if engine:
            original = engine.get_result_dict()
        else:
            # 이력에서 로드
            history_path = HISTORY_DIR / f"{target_vrf_id}.json"
            if not history_path.exists():
                return json.dumps({"error": f"검증 결과를 찾을 수 없습니다: {target_vrf_id}"}, ensure_ascii=False)
            data = json.loads(history_path.read_text(encoding="utf-8"))
            original = data.get("result_json", data)

        # Finding Card 파싱
        finding_cards = [FindingCard.from_dict(f) for f in findings]

        # 수정 적용
        result = CorrectionEngine.apply_corrections(
            original, finding_cards, approved_ids, auto_apply_definitive
        )

        # 버전 관리 + 저장
        version = CorrectionEngine.find_next_version(target_vrf_id)
        saved_path = CorrectionEngine.save_corrected(
            target_vrf_id, result["corrected_report"], version
        )

        logger.info(
            f"수정 적용 완료: {target_vrf_id} v{version}, "
            f"적용={len(result['applied'])}, 미적용={len(result['skipped'])}"
        )

        return json.dumps({
            "vrf_id": target_vrf_id,
            "version": version,
            "applied_count": len(result["applied"]),
            "skipped_count": len(result["skipped"]),
            "applied": result["applied"],
            "corrections_log": result["corrections_log"],
            "saved_to": str(saved_path),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_apply_corrections 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  Phase 5: HTML 보고서 생성
# ══════════════════════════════════

@mcp.tool()
def verify_generate_html(
    vrf_id: str = "",
    save_path: str = "",
) -> str:
    """검증 결과를 HTML 보고서로 렌더링합니다.

    vrf_id: 검증 ID (미지정 시 현재 세션 사용)
    save_path: HTML 저장 경로 (미지정 시 output/ 폴더에 자동 생성)

    Returns: {html_path, sections_rendered, findings_count, file_size_kb}"""

    try:
        target_vrf_id = vrf_id or _current_session

        # result_json 획득
        result_json = None

        # 1) 수정본이 있으면 최신 수정본 사용
        if target_vrf_id:
            corrected_files = sorted(
                HISTORY_DIR.glob(f"{target_vrf_id}_corrected_v*.json"),
                reverse=True,
            )
            if corrected_files:
                data = json.loads(corrected_files[0].read_text(encoding="utf-8"))
                result_json = data
                logger.info(f"수정본 사용: {corrected_files[0].name}")

        # 2) 수정본 없으면 원본 사용
        if not result_json:
            engine = _sessions.get(target_vrf_id) if target_vrf_id else None
            if engine:
                result_json = engine.get_result_dict()
            elif target_vrf_id:
                history_path = HISTORY_DIR / f"{target_vrf_id}.json"
                if history_path.exists():
                    data = json.loads(history_path.read_text(encoding="utf-8"))
                    result_json = data.get("result_json", data)

        if not result_json:
            return json.dumps({"error": "렌더링할 검증 결과가 없습니다"}, ensure_ascii=False)

        # HTML 렌더링 — adaptive 우선, 고정 구조 폴백
        try:
            adaptive = AdaptiveVerificationRenderer(result_json)
            adaptive_html = adaptive.render()
            adaptive_path = adaptive.save()
            adaptive_summary = adaptive.summary()
            logger.info(f"Adaptive 보고서 생성: {adaptive_path}")
        except Exception as ae:
            logger.warning(f"Adaptive 렌더링 실패, 고정 구조 폴백: {ae}")
            adaptive_path = None
            adaptive_summary = None

        # 고정 구조도 항상 생성
        renderer = VerificationHTMLRenderer(result_json)
        out_path = renderer.save(save_path)
        file_size = out_path.stat().st_size / 1024

        logger.info(f"HTML 보고서 생성: {out_path} ({file_size:.1f}KB)")

        result_data = {
            "html_path": str(out_path),
            "vrf_id": target_vrf_id or "unknown",
            "findings_count": len(renderer.findings),
            "sections_rendered": 7,
            "file_size_kb": round(file_size, 1),
        }
        if adaptive_path:
            result_data["adaptive_html_path"] = str(adaptive_path)
            result_data["adaptive_summary"] = adaptive_summary

        return json.dumps(result_data, ensure_ascii=False)

    except Exception as e:
        logger.error(f"verify_generate_html 오류: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ══════════════════════════════════
#  실행
# ══════════════════════════════════

if __name__ == "__main__":
    mcp.run(transport="stdio")
