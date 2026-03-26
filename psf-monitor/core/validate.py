"""
psf-monitor state.json 스키마 검증기

사용법:
  python core/validate.py                    # state.json 검증
  python core/validate.py --file state.json  # 특정 파일 검증
  python core/validate.py --fix              # 자동 수정 가능한 항목 수정
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"
PROJECTION_FILE = BASE_DIR / "projection.json"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_by_prefix(layer: dict, prefix: str) -> dict | None:
    """키가 정확히 일치하거나 prefix로 시작하는 항목 찾기."""
    if prefix in layer:
        return layer[prefix]
    for key in layer:
        if key.startswith(prefix) and key != "verdict":
            return layer[key]
    return None


def validate_state(state: dict) -> list[dict]:
    """state.json 스키마 검증. SCHEMAS.md 기준."""
    issues = []

    def warn(field, msg, severity="medium"):
        issues.append({"field": field, "message": msg, "severity": severity})

    # 필수 최상위 필드
    required_top = ["last_updated", "regime", "quality", "observations"]
    for field in required_top:
        if field not in state:
            warn(field, f"필수 필드 '{field}' 누락", "high")

    # 신선도 확인
    if "last_updated" in state:
        try:
            updated = datetime.strptime(state["last_updated"], "%Y-%m-%d")
            age = (datetime.now() - updated).days
            if age > 7:
                warn("last_updated", f"expired: {age}일 전 데이터", "high")
            elif age > 3:
                warn("last_updated", f"stale: {age}일 전 데이터", "medium")
        except ValueError:
            warn("last_updated", "날짜 형식 오류", "high")

    # quality 검증
    quality = state.get("quality", {})
    mcp_count = quality.get("mcp_count", 0)
    estimate_count = quality.get("estimate_count", 0)
    total = mcp_count + estimate_count
    if total > 0:
        ratio = mcp_count / total
        if ratio < 0.5:
            warn("quality.mcp_ratio", f"MCP 비율 {ratio:.0%} < 50% → 관측 품질 낮음", "high")

    # observations 검증
    observations = state.get("observations", [])
    if len(observations) == 0:
        warn("observations", "관측 0건 — 최소 1건 필요", "high")
    for i, obs in enumerate(observations):
        if "source" not in obs:
            warn(f"observations[{i}].source", "출처 태그 누락 (ERR-008)", "medium")
        if "severity" not in obs:
            warn(f"observations[{i}].severity", "심각도 누락", "low")

    # structure S1~S5 검증 (키 형식: "S1" 또는 "S1_real_rate" 등)
    structure = state.get("structure", {})
    for s_prefix in ["S1", "S2", "S3", "S4", "S5"]:
        s_data = _find_by_prefix(structure, s_prefix)
        if not s_data:
            warn(f"structure.{s_prefix}", f"{s_prefix} 누락 (전수 점검 필요)", "high")
            continue
        if "value" not in s_data and "verdict" not in s_data and "status" not in s_data:
            warn(f"structure.{s_prefix}.value", f"{s_prefix} 값/판정/상태 누락", "medium")

    # flow F1~F5 검증
    flow = state.get("flow", {})
    for f_prefix in ["F1", "F2", "F3", "F4", "F5"]:
        f_data = _find_by_prefix(flow, f_prefix)
        if not f_data:
            warn(f"flow.{f_prefix}", f"{f_prefix} 누락", "high")
            continue
        if "verdict" not in f_data and "status" not in f_data:
            warn(f"flow.{f_prefix}.verdict", f"{f_prefix} 판정/상태 누락", "medium")

    # links 검증 (키: "L3" 또는 "L3_energy_inflation" 등 prefix 매칭)
    links = state.get("links", {})
    required_link_prefixes = ["L1", "L2", "L3", "L3.5", "L3_5", "L4", "L5", "L6",
                               "L7_acute", "L7_chronic", "L8", "corrflip"]
    for link_prefix in required_link_prefixes:
        found = False
        for key in links:
            if key == link_prefix or key.startswith(link_prefix):
                found = True
                link_data = links[key]
                if isinstance(link_data, dict) and "status" not in link_data:
                    warn(f"links.{key}.status", f"Link {key} active/inactive 미표기", "medium")
                break
        if not found:
            # L3_5와 L3.5는 동일 (하나만 있으면 OK)
            if link_prefix in ("L3_5", "L3.5"):
                alt = "L3.5" if link_prefix == "L3_5" else "L3_5"
                if any(k == alt or k.startswith(alt) for k in links):
                    continue
            warn(f"links.{link_prefix}", f"Link {link_prefix} 상태 누락", "medium")

    # next_questions 검증
    if "next_questions" not in state:
        warn("next_questions", "next_questions 필드 누락 (빈 배열이라도 필요)", "low")

    # divergences 검증
    if "divergences" not in state:
        warn("divergences", "divergences 필드 누락", "low")

    return issues


def validate_projection(proj: dict) -> list[dict]:
    """projection.json 스키마 검증."""
    issues = []

    def warn(field, msg, severity="medium"):
        issues.append({"field": field, "message": msg, "severity": severity})

    required = ["projection_date", "scenarios", "current_position"]
    for field in required:
        if field not in proj:
            warn(field, f"필수 필드 '{field}' 누락", "high")

    scenarios = proj.get("scenarios", {})
    # scenarios는 배열 또는 객체(dict) 가능
    if isinstance(scenarios, dict):
        scenario_list = list(scenarios.values())
    elif isinstance(scenarios, list):
        scenario_list = scenarios
    else:
        scenario_list = []

    if len(scenario_list) == 0:
        warn("scenarios", "시나리오 0건", "high")

    total_prob = sum(s.get("probability", 0) for s in scenario_list
                     if isinstance(s, dict))
    if scenario_list and abs(total_prob - 1.0) > 0.05:
        warn("scenarios.probability", f"확률 합계 {total_prob:.0%} ≠ 100%", "medium")

    return issues


def print_results(issues: list[dict], filename: str):
    if not issues:
        print(f"✅ {filename}: 검증 통과 (이슈 0건)")
        return

    high = [i for i in issues if i["severity"] == "high"]
    medium = [i for i in issues if i["severity"] == "medium"]
    low = [i for i in issues if i["severity"] == "low"]

    print(f"\n{'='*60}")
    print(f"⚠  {filename}: 이슈 {len(issues)}건 (🔴{len(high)} 🟡{len(medium)} 🟢{len(low)})")
    print(f"{'='*60}")

    for severity, label, items in [("high", "🔴 HIGH", high),
                                     ("medium", "🟡 MEDIUM", medium),
                                     ("low", "🟢 LOW", low)]:
        if items:
            print(f"\n{label}:")
            for issue in items:
                print(f"  [{issue['field']}] {issue['message']}")

    print()


def main():
    args = sys.argv[1:]
    target = None
    for i, arg in enumerate(args):
        if arg == "--file" and i + 1 < len(args):
            target = args[i + 1]

    all_issues = []

    # state.json 검증
    if target is None or target == "state.json":
        state = load_json(STATE_FILE)
        if state is None:
            print(f"❌ {STATE_FILE} 파일 없음")
        else:
            issues = validate_state(state)
            print_results(issues, "state.json")
            all_issues.extend(issues)

    # projection.json 검증
    if target is None or target == "projection.json":
        proj = load_json(PROJECTION_FILE)
        if proj is None:
            print(f"⚠  projection.json 파일 없음 (선택 사항)")
        else:
            issues = validate_projection(proj)
            print_results(issues, "projection.json")
            all_issues.extend(issues)

    # 종합
    if all_issues:
        high_count = sum(1 for i in all_issues if i["severity"] == "high")
        if high_count > 0:
            print(f"🔴 HIGH 이슈 {high_count}건 — 즉시 수정 필요")
            sys.exit(1)
    else:
        print("✅ 전체 검증 통과")


if __name__ == "__main__":
    main()
