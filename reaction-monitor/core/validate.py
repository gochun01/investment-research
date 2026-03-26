"""state.json 스키마 검증기.

사용:
  python core/validate.py                    # state.json 검증
  python core/validate.py path/to/file.json  # 지정 파일 검증

검증 항목:
  1. 최상위 필수 필드 존재 여부
  2. fingerprint 5차원 존재 여부
  3. channels 5계층 존재 여부 (빈 배열 허용, 키 누락 불가)
  4. reactions 5계층 존재 여부
  5. pattern 4렌즈 존재 여부
  6. unresolved 배열의 각 항목 스키마 검증
  7. unresolved가 구조화 객체인지 (문자열 배열이면 경고)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 스키마 정의 ──

REQUIRED_TOP = ["issue", "date", "depth", "fingerprint", "channels",
                "reactions", "pattern", "unresolved", "next_check"]

REQUIRED_FINGERPRINT = ["domain", "geography", "touched_assets",
                        "stakeholders", "time_character"]

REQUIRED_CHANNELS = ["price", "narrative", "expert", "policy", "positioning"]

REQUIRED_REACTIONS = ["price", "narrative", "expert", "policy", "positioning"]

REQUIRED_PATTERN = ["direction_alignment", "direction_detail",
                    "direction_rationale", "time_structure",
                    "time_sequence", "time_rationale",
                    "proportionality", "proportionality_rationale",
                    "propagation", "propagation_rationale",
                    "next_observation"]

REQUIRED_UNRESOLVED_ITEM = ["id", "question", "status", "resolve_type",
                            "resolve_condition", "check_channels", "created"]

VALID_STATUS = {"open", "resolved"}
VALID_RESOLVE_TYPE = {"date", "condition", "data", "threshold"}
VALID_DIRECTION = {"수렴", "분열", "괴리", "침묵"}
VALID_TIME_STRUCTURE = {"A", "B", "C", "D", "동시"}
VALID_PROPORTIONALITY = {"과잉", "비례", "과소", "무반응"}
VALID_PROPAGATION = {"A", "B", "C", "D", "복합"}


def validate(data: dict) -> list[dict]:
    """state.json을 검증. 결과를 [{level, field, message}] 리스트로 반환."""
    issues = []

    def err(field, msg):
        issues.append({"level": "ERROR", "field": field, "message": msg})

    def warn(field, msg):
        issues.append({"level": "WARN", "field": field, "message": msg})

    # ── 1. 최상위 필수 필드 ──
    for key in REQUIRED_TOP:
        if key not in data:
            err(key, f"최상위 필수 필드 '{key}' 누락")

    if not data.get("issue"):
        err("issue", "issue가 비어있음")
    if not data.get("date"):
        err("date", "date가 비어있음")

    # ── 2. fingerprint ──
    fp = data.get("fingerprint", {})
    if not isinstance(fp, dict):
        err("fingerprint", "fingerprint가 dict가 아님")
    else:
        for key in REQUIRED_FINGERPRINT:
            if key not in fp:
                err(f"fingerprint.{key}", f"필수 차원 '{key}' 누락")
            elif not fp[key]:
                warn(f"fingerprint.{key}", f"'{key}'가 비어있음")

    # ── 3. channels ──
    ch = data.get("channels", {})
    if not isinstance(ch, dict):
        err("channels", "channels가 dict가 아님")
    else:
        for key in REQUIRED_CHANNELS:
            if key not in ch:
                err(f"channels.{key}", f"계층 '{key}' 키 누락 (비활성이면 빈 배열 []로 유지)")
            elif not isinstance(ch[key], list):
                err(f"channels.{key}", f"'{key}'가 배열이 아님")
            else:
                for i, item in enumerate(ch[key]):
                    if not isinstance(item, dict):
                        err(f"channels.{key}[{i}]", "채널 항목이 dict가 아님")
                    elif "reason" not in item:
                        warn(f"channels.{key}[{i}]", "선정 이유(reason) 누락 — R-02 위반")

    # ── 4. reactions ──
    rx = data.get("reactions", {})
    if not isinstance(rx, dict):
        err("reactions", "reactions가 dict가 아님")
    else:
        for key in REQUIRED_REACTIONS:
            if key not in rx:
                err(f"reactions.{key}", f"계층 '{key}' 키 누락 (비활성이면 빈 배열 []로 유지)")
            elif not isinstance(rx[key], list):
                err(f"reactions.{key}", f"'{key}'가 배열이 아님")
            else:
                for i, item in enumerate(rx[key]):
                    if not isinstance(item, dict):
                        err(f"reactions.{key}[{i}]", "반응 항목이 dict가 아님")
                    elif "source" not in item and "timestamp" not in item:
                        warn(f"reactions.{key}[{i}]", "출처(source) 또는 시점(timestamp) 누락 — R-05 위반")

    # ── 5. pattern ──
    pt = data.get("pattern", {})
    if not isinstance(pt, dict):
        err("pattern", "pattern이 dict가 아님")
    else:
        for key in REQUIRED_PATTERN:
            if key not in pt:
                err(f"pattern.{key}", f"렌즈 필드 '{key}' 누락")

        # 값 유효성
        da = pt.get("direction_alignment", "")
        if da and da not in VALID_DIRECTION:
            warn("pattern.direction_alignment", f"'{da}' — 유효 값: {VALID_DIRECTION}")

        pp = pt.get("proportionality", "")
        if pp and pp not in VALID_PROPORTIONALITY:
            warn("pattern.proportionality", f"'{pp}' — 유효 값: {VALID_PROPORTIONALITY}")

    # ── 6. unresolved ──
    uq = data.get("unresolved", [])
    if not isinstance(uq, list):
        err("unresolved", "unresolved가 배열이 아님")
    else:
        for i, item in enumerate(uq):
            # 문자열이면 구조화 안 된 것 — 경고
            if isinstance(item, str):
                err(f"unresolved[{i}]", f"문자열임. 구조화 객체(dict)로 변환 필요: \"{item[:50]}...\"")
                continue
            if not isinstance(item, dict):
                err(f"unresolved[{i}]", "dict가 아님")
                continue

            # 필수 필드
            for key in REQUIRED_UNRESOLVED_ITEM:
                if key not in item:
                    err(f"unresolved[{i}].{key}", f"필수 필드 '{key}' 누락")

            # 값 유효성
            status = item.get("status", "")
            if status and status not in VALID_STATUS:
                warn(f"unresolved[{i}].status", f"'{status}' — 유효 값: {VALID_STATUS}")

            rt = item.get("resolve_type", "")
            if rt and rt not in VALID_RESOLVE_TYPE:
                warn(f"unresolved[{i}].resolve_type", f"'{rt}' — 유효 값: {VALID_RESOLVE_TYPE}")

            # deadline 체크 (date 타입인데 deadline 없으면)
            if rt == "date" and not item.get("deadline"):
                warn(f"unresolved[{i}]", "resolve_type=date인데 deadline이 비어있음")

            # check_channels 체크
            cc = item.get("check_channels", {})
            if not cc:
                warn(f"unresolved[{i}].check_channels", "check_channels가 비어있음 — Phase 0 체크 불가")

    # ── 7. 양면 수집 체크 (R-03) ──
    narrative_roles = set()
    for item in rx.get("narrative", []):
        if isinstance(item, dict):
            narrative_roles.add(item.get("role", ""))
    if "반대쪽" not in narrative_roles and rx.get("narrative"):
        warn("reactions.narrative", "반대쪽 역할 매체 없음 — R-03 위반 가능")

    expert_roles = set()
    for item in rx.get("expert", []):
        if isinstance(item, dict):
            expert_roles.add(item.get("role", ""))
    if "반대입장" not in expert_roles and rx.get("expert"):
        warn("reactions.expert", "반대입장 전문가 없음 — R-03 위반 가능")

    # ── 8. SNS 판단 기록 체크 (R-06) ──
    sns_info = ch.get("sns")
    has_sns_in_narrative = any(
        "SNS" in (item.get("role", "") or "").upper() or
        "twitter" in (item.get("reason", "") or "").lower() or
        "x.com" in (item.get("reason", "") or "").lower()
        for item in ch.get("narrative", [])
    )
    has_sns_in_expert = any(
        "SNS" in (item.get("channel", "") or "").upper() or
        "twitter" in (item.get("source", "") or "").lower()
        for item in rx.get("expert", [])
    )
    if not sns_info and not has_sns_in_narrative and not has_sns_in_expert:
        warn("channels.sns", "SNS/X 포함 판단 기록 없음 — R-06 위반 가능. "
             "channels에 sns 필드(활성 또는 비활성+이유) 기록 필요")

    # ── 9. 전문가 유형 다양성 체크 (R-07) ──
    expert_role_types = set()
    for item in rx.get("expert", []):
        if isinstance(item, dict) and item.get("role"):
            expert_role_types.add(item["role"])
    expected_roles = {"공급자", "피해자", "분석자", "반대입장", "하류", "정책"}
    # 최소 3가지 유형 이상이면 OK, 미만이면 경고
    if rx.get("expert") and len(expert_role_types) < 3:
        warn("reactions.expert", f"전문가 유형 {len(expert_role_types)}종만 포함 "
             f"({expert_role_types}). R-07: 최소 3가지 유형 권장 "
             f"(공급자/피해자/분석자/반대입장/하류/정책)")

    # ── 10. 2차 이해관계자 맵 체크 (R-08) ──
    secondary = fp.get("secondary_stakeholders")
    if not secondary:
        warn("fingerprint.secondary_stakeholders",
             "2차 이해관계자 미기록 — R-08 위반 가능. "
             "'이 이해관계자가 영향 받으면 다음은 누구?'를 1단계 더 추론 필요")

    # ── 11. 침묵 기록 체크 (R-09) ──
    has_silence = False
    for item in rx.get("expert", []):
        if isinstance(item, dict):
            direction = (item.get("direction", "") or "").lower()
            statement = (item.get("statement", "") or "").lower()
            if "침묵" in direction or "침묵" in statement:
                has_silence = True
                break
    for item in rx.get("policy", []):
        if isinstance(item, dict):
            action = (item.get("action", "") or "").lower()
            if "침묵" in action:
                has_silence = True
                break
    if not has_silence and (rx.get("expert") or rx.get("policy")):
        warn("reactions (R-09)",
             "침묵 기록 없음. '말해야 하는데 안 말한 사람/기관'이 정말 0명인지 확인. "
             "없다면 의도적 판단이며, 있다면 R-09 위반")

    # ── 12. F-02: 1차 소스 미확보 감지 ──
    MCP_SOURCE_PATTERNS = [
        "yahoo finance", "fred", "coingecko", "defillama", "coinmetrics",
        "etherscan", "dart", "sec-edgar", "sec edgar", "blockchain",
        "dune", "apify", "firecrawl", "tavily",
    ]
    for i, item in enumerate(rx.get("price", [])):
        if not isinstance(item, dict):
            continue
        source = (item.get("source", "") or "").lower()
        is_mcp = any(p in source for p in MCP_SOURCE_PATTERNS)
        if not is_mcp and source:
            warn(f"reactions.price[{i}] (F-02)",
                 f"'{item.get('asset','')}' source가 MCP 원본이 아님: '{item.get('source','')}'. "
                 f"매체 인용이면 1차 소스 교차확인 필요")

    # ── 13. F-04: 매체 프레임 vs 시장 반응 괴리 자동 감지 ──
    narrative_tones = [
        (item.get("tone", "") or "")
        for item in rx.get("narrative", []) if isinstance(item, dict)
    ]
    price_changes = [
        item.get("change_pct", 0)
        for item in rx.get("price", []) if isinstance(item, dict)
    ]
    if narrative_tones and price_changes:
        neg_ratio = sum(1 for t in narrative_tones if t in ("부", "neg")) / max(len(narrative_tones), 1)
        avg_price_chg = sum(price_changes) / max(len(price_changes), 1)
        # 서사 70%+ 부정인데 가격 평균 변동 ±2% 이내 = 괴리
        if neg_ratio >= 0.7 and abs(avg_price_chg) < 2:
            warn("pattern (F-04)",
                 f"서사 {neg_ratio*100:.0f}% 부정인데 가격 평균 {avg_price_chg:+.1f}%. "
                 f"매체 프레임과 시장 반응 괴리. 매체 과장 가능성 검토 필요")
        pos_ratio = sum(1 for t in narrative_tones if t in ("긍", "pos")) / max(len(narrative_tones), 1)
        if pos_ratio >= 0.7 and avg_price_chg < -2:
            warn("pattern (F-04)",
                 f"서사 {pos_ratio*100:.0f}% 긍정인데 가격 평균 {avg_price_chg:+.1f}%. "
                 f"매체 낙관과 시장 하락 괴리. 호재 미반영 또는 다른 악재 존재")

    # ── 14. F-05: SNS 판단만 하고 미수집 감지 ──
    sns_info = ch.get("sns", {})
    if isinstance(sns_info, dict):
        sns_status = (sns_info.get("status", "") or "").lower()
        sns_collected = sns_info.get("collected", False)
        if sns_status and "비활성" not in sns_status and not sns_collected:
            warn("channels.sns (F-05)",
                 f"SNS 상태가 '{sns_info.get('status','')}' (활성)인데 collected=false. "
                 f"활성 판단 시 최소 프록시 검색 2회 필요")

    # ── 15. fingerprint 품질 체크 ──
    touched = fp.get("touched_assets", [])
    if touched:
        has_type_tag = any("1차" in str(a) or "2차" in str(a) or "대조" in str(a) for a in touched)
        if not has_type_tag:
            warn("fingerprint.touched_assets",
                 "접촉 자산에 1차/2차/대조 구분 태깅 없음. 자산 유형 명시 필요")
    stakeholders = fp.get("stakeholders", [])
    if len(stakeholders) < 3:
        warn("fingerprint.stakeholders",
             f"이해관계자 {len(stakeholders)}건. 최소 3건 이상 권장")

    return issues


# ── 이슈 자동 적재 (2단계: Self-Audit) ──

ISSUES_PATH = Path(__file__).parent.parent / "system-issues.json"

# WARN → 이슈 카테고리 매핑
WARN_TO_CATEGORY = {
    "channels.sns": ("CAT-3", "PROMPT_DRIFT", "SNS 판단 기록 누락"),
    "reactions.expert": ("CAT-1", "SKILL_DEFECT", "전문가 유형/반대입장 부족"),
    "reactions.narrative": ("CAT-1", "SKILL_DEFECT", "서사 반대쪽 매체 누락"),
    "fingerprint.secondary_stakeholders": ("CAT-3", "PROMPT_DRIFT", "2차 이해관계자 미기록"),
    "reactions (R-09)": ("CAT-1", "SKILL_DEFECT", "침묵 기록 누락"),
    "pattern.direction_alignment": ("CAT-4", "LOGIC_HOLE", "방향 판정값 비정규"),
    "pattern.proportionality": ("CAT-4", "LOGIC_HOLE", "비례성 판정값 비정규"),
}


def _load_issues() -> dict:
    if ISSUES_PATH.exists():
        return json.loads(ISSUES_PATH.read_text(encoding="utf-8"))
    return {
        "issues": [],
        "weekly_review": {"last_review": None, "next_review": "", "review_day": "monday"},
        "summary": {"total_open": 0, "by_severity": {}, "by_category": {}},
    }


def _save_issues(data: dict):
    # summary 재계산
    open_issues = [i for i in data["issues"] if i["status"] == "open"]
    data["summary"]["total_open"] = len(open_issues)
    sev = {}
    cat = {}
    for i in open_issues:
        s = i.get("severity", "low")
        sev[s] = sev.get(s, 0) + 1
        c = i.get("category", "CAT-1")
        cat[c] = cat.get(c, 0) + 1
    data["summary"]["by_severity"] = sev
    data["summary"]["by_category"] = cat
    ISSUES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def auto_log_issues(validation_issues: list[dict], state_data: dict) -> int:
    """validate() 결과의 WARN을 system-issues.json에 자동 적재한다.
    중복 방지: 같은 field+message 조합이 이미 open이면 건너뜀.
    Returns: 새로 적재한 이슈 수."""
    warns = [i for i in validation_issues if i["level"] == "WARN"]
    if not warns:
        return 0

    issues_data = _load_issues()
    existing_titles = {
        i["title"] for i in issues_data["issues"]
        if i["status"] in ("open", "duplicate", "fixed", "in_progress")
    }

    today = datetime.now().strftime("%Y-%m-%d")
    week_num = datetime.now().isocalendar()[1]
    added = 0

    for w in warns:
        field = w["field"]
        msg = w["message"]

        # 카테고리 매핑
        cat_info = WARN_TO_CATEGORY.get(field, ("CAT-1", "SKILL_DEFECT", field))
        category, cat_name, short_title = cat_info

        title = f"{short_title}: {msg[:60]}"

        # 중복 체크
        if title in existing_titles:
            continue

        issue_id = f"ISS-RM-2026-W{week_num:02d}-{len(issues_data['issues']) + 1:03d}"
        issue = {
            "id": issue_id,
            "detected_at": today,
            "detected_by": f"core/validate.py → {field}",
            "category": category,
            "severity": "high" if "ERROR" in w.get("level", "") else "medium",
            "title": title,
            "description": msg,
            "evidence": f"validate.py {w['level']}: {field} — {msg}",
            "proposed_fix": f"SKILL.md 또는 수집 프로세스에서 {field} 관련 규칙 보강",
            "target_file": "SKILL.md",
            "status": "open",
            "fixed_at": None,
            "fix_applied": None,
            "related_issues": [],
        }
        issues_data["issues"].append(issue)
        existing_titles.add(title)
        added += 1

    if added:
        # next_review 설정 (다음 월요일)
        now = datetime.now()
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_monday = (now + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
        issues_data["weekly_review"]["next_review"] = next_monday

        _save_issues(issues_data)

    return added


def main():
    # 파일 경로 + 플래그 파싱
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    auto_log = "--auto-log" in flags

    if args:
        path = Path(args[0])
    else:
        path = Path(__file__).parent.parent / "state.json"

    if not path.exists():
        print(f"❌ 파일 없음: {path}")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    issues = validate(data)

    # 결과 출력
    errors = [i for i in issues if i["level"] == "ERROR"]
    warns = [i for i in issues if i["level"] == "WARN"]

    print(f"\n{'=' * 60}")
    print(f"  state.json 스키마 검증 — {path.name}")
    print(f"{'=' * 60}")
    print(f"  ERROR: {len(errors)}건  |  WARN: {len(warns)}건")
    print(f"{'=' * 60}\n")

    if not issues:
        print("  ✅ 모든 검증 통과\n")
    else:
        for i in issues:
            icon = "❌" if i["level"] == "ERROR" else "⚠️"
            print(f"  {icon} [{i['level']}] {i['field']}")
            print(f"     {i['message']}\n")

    # 자동 이슈 적재
    if auto_log and warns:
        added = auto_log_issues(issues, data)
        if added:
            print(f"  📋 system-issues.json에 {added}건 자동 적재")
        else:
            print(f"  📋 새로운 이슈 없음 (중복 또는 이미 적재)")
        print()

    # 요약
    uq = data.get("unresolved", [])
    uq_open = sum(1 for q in uq if isinstance(q, dict) and q.get("status") == "open")
    uq_resolved = sum(1 for q in uq if isinstance(q, dict) and q.get("status") == "resolved")
    uq_str = sum(1 for q in uq if isinstance(q, str))

    print(f"  미해소: {uq_open} open / {uq_resolved} resolved / {uq_str} 미구조화")
    print(f"  쟁점: {data.get('issue', '?')}")
    print(f"  날짜: {data.get('date', '?')}")
    print()

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
