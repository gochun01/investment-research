"""
Stereo Analyzer MCP Server

입체 분석 자율 사고 엔진을 MCP 도구로 노출한다.
Claude에서 직접 호출하여 기사·쟁점·이슈를 7-Layer로 해부할 수 있다.

도구 목록:
  stereo_analyze       — 입력(URL/텍스트/키워드)을 7-Layer 입체 분석
  stereo_preread       — Pre-Read만 실행 (Type/SCP/Urgency 판독)
  stereo_render        — 분석 JSON → HTML 보고서 생성
  stereo_list          — 분석 이력 목록
  stereo_get           — 특정 분석 결과 조회
  stereo_validate      — 셀프체크 실행
  stereo_errors        — 오류 기록 조회 + 셀프검증 체크리스트

실행:
  python mcp_server.py
  또는 Claude Code settings.json에 등록
"""

import json
import sys
import os
from pathlib import Path
from datetime import date, datetime

# FastMCP import
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("mcp 패키지가 필요합니다: pip install mcp")
    sys.exit(1)

# ── 경로 설정 ──
BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "history"
REPORTS_DIR = BASE_DIR / "reports"
ERRORS_FILE = BASE_DIR / "errors.md"
SCHEMAS_FILE = BASE_DIR / "SCHEMAS.md"

# render_adaptive에서 함수 임포트
sys.path.insert(0, str(BASE_DIR / "core"))
try:
    from render_adaptive import extract_five, design_report, render_html, verify
except ImportError:
    extract_five = None
    design_report = None
    render_html = None
    verify = None

# ── MCP 서버 생성 ──
mcp = FastMCP("stereo-analyzer")


# ══════════════════════════════════════════════════
# 도구 1: stereo_analyze — 7-Layer 입체 분석
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_analyze(
    input_text: str,
    input_type: str = "keyword",
    emotion_note: str = ""
) -> str:
    """
    기사·쟁점·이슈를 7-Layer로 입체 분석한다.

    Args:
        input_text: 분석할 내용 (URL, 기사 제목, 키워드, 질문 등)
        input_type: 입력 유형 ("url", "text", "keyword", "question")
        emotion_note: 감정이 섞인 경우 원문 (예: "이거 심각한 거 아냐?")

    Returns:
        분석 가이드 + Pre-Read 결과 + 분석 지침.
        실제 7-Layer 분석은 LLM이 이 가이드를 따라 수행한다.

    사용 예:
        stereo_analyze("사모대출 위기", "keyword", "심각하게 받아들이는데")
        stereo_analyze("https://example.com/article", "url")
    """
    # Pre-Read 가이드 생성
    guide = []
    guide.append("━━━ Stereo Analyzer v2.0 분석 가이드 ━━━")
    guide.append(f"")
    guide.append(f"📥 입력: [{input_type}] {input_text}")

    if emotion_note:
        guide.append(f"💭 감정 감지: \"{emotion_note}\"")
        guide.append(f"   → 감정 분리 3단계를 실행하세요:")
        guide.append(f"   Step 1: 핵심 불확실성 식별")
        guide.append(f"   Step 2: 검증 가능한 질문으로 변환")
        guide.append(f"   Step 3: 변환된 질문으로 L1~L7 진행")
        guide.append(f"   Step 4: L7에서 원래 걱정에 직접 회답")

    guide.append(f"")
    guide.append(f"🧭 Phase 0: Pre-Read를 먼저 실행하세요:")
    guide.append(f"  0-1. Type 분류: POLICY / MACRO / STRUCT / EVENT / NARR / NOISE")
    guide.append(f"  0-2. SCP (0~5): 구조 변화 잠재력 + 근거 1문장")
    guide.append(f"  0-3. Urgency: URGENT / WATCH / SLOW")
    guide.append(f"  0-4. Context Router로 분석 전략 결정")
    guide.append(f"")
    guide.append(f"📐 분석 전략 결정 후:")
    guide.append(f"  Phase 1: 수집 (Tavily/Firecrawl)")
    guide.append(f"  Phase 2: 7-Layer 해부 (가중치 적용)")
    guide.append(f"  Phase 2.5: 되먹임 순회 (FB-1~4)")
    guide.append(f"  Phase 3: 돌발 질문 생성 (렌즈 5가지)")
    guide.append(f"  Phase 4: 불확실성 지도")
    guide.append(f"")
    guide.append(f"⚠️ 셀프체크 필수 항목:")
    guide.append(f"  □ POLICY/STRUCT이면 FB-2(L5→L3) 필수 (F-01 방어)")
    guide.append(f"  □ L6에 second-order-patterns.md 패턴 1개+ 적용 (L-01 방어)")
    guide.append(f"  □ L2 전부 🟢이면 🟡/🔴 후보 재점검 (L-02 방어)")
    guide.append(f"  □ 한국 노출 시 국내 전이 경로 구체화 (L-03 방어)")
    guide.append(f"  □ 단일 출처 핵심 수치에 ⚠ + 교차검증 소스 명시 (L-04 방어)")
    guide.append(f"  □ 코드 수정 시 SCHEMAS.md 키 대조 (O-01 방어)")
    guide.append(f"")
    guide.append(f"📦 완료 후: stereo_save()로 저장 → stereo_render()로 HTML 생성")
    guide.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(guide)


# ══════════════════════════════════════════════════
# 도구 2: stereo_preread — Pre-Read만 실행
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_preread(input_text: str) -> str:
    """
    Pre-Read만 빠르게 실행한다. Type/SCP/Urgency를 판독한다.

    Args:
        input_text: 분석할 내용

    Returns:
        Pre-Read 판독 가이드 (Type 6가지 + SCP 0~5 + Urgency 3단계)
    """
    guide = []
    guide.append(f"🧭 Pre-Read 판독: \"{input_text}\"")
    guide.append(f"")
    guide.append(f"Type 분류 (가장 구조적 영향이 큰 것을 주 Type으로):")
    guide.append(f"  POLICY  — 정책·규제·법률 변화 → L4+L6 집중")
    guide.append(f"  MACRO   — 매크로/금리/지정학 → L4+L5+L6 집중")
    guide.append(f"  STRUCT  — 산업 구조·밸류체인 변화 → L5+L6+L7 집중")
    guide.append(f"  EVENT   — 실적·인사·단발 이벤트 → L2+L3+L7 집중")
    guide.append(f"  NARR    — 시장 심리·내러티브 전환 → L1+L4+L5 집중")
    guide.append(f"  NOISE   — 반복 보도·재탕 → L1만 → 노이즈 선언 후 종료")
    guide.append(f"")
    guide.append(f"SCP (구조 변화 잠재력):")
    guide.append(f"  0 — 구조와 무관한 노이즈")
    guide.append(f"  1 — 구조 내 일상적 변동")
    guide.append(f"  2 — 구조 내 중요 변수의 변화")
    guide.append(f"  3 — 구조 변화의 초기 신호")
    guide.append(f"  4 — 구조 재편 진행 중")
    guide.append(f"  5 — 구조 파괴/창조")
    guide.append(f"  ★ 근거를 반드시 1문장으로. 수식어를 제거하고 팩트만 놓고 판독.")
    guide.append(f"")
    guide.append(f"Urgency:")
    guide.append(f"  URGENT — 24~72시간 내 판단 필요 → 빠른 모드")
    guide.append(f"  WATCH  — 1~4주 내 추적 필요 → 풀 모드")
    guide.append(f"  SLOW   — 장기 관찰 → 구조 분석 중심")

    return "\n".join(guide)


# ══════════════════════════════════════════════════
# 도구 3: stereo_save — 분석 결과 저장
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_save(analysis_json: str, title: str = "") -> str:
    """
    분석 결과 JSON을 history/에 저장한다.

    Args:
        analysis_json: 분석 결과 JSON 문자열 (SCHEMAS.md 형식)
        title: 파일명에 사용할 짧은 제목 (영문/한글, 예: "private-credit")

    Returns:
        저장 경로 + 검증 결과
    """
    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError as e:
        return f"❌ JSON 파싱 오류: {e}"

    # 파일명 생성
    today = analysis.get("date", date.today().isoformat())
    analysis_id = analysis.get("id", f"SA-{today.replace('-', '')}-000")

    if title:
        filename = f"{today}-{title}.json"
    else:
        filename = f"{today}-{analysis_id}.json"

    # 저장
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    filepath = HISTORY_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    # 기본 검증
    issues = []
    if "pre_read" not in analysis:
        issues.append("⚠ pre_read 누락")
    if "layers" not in analysis:
        issues.append("⚠ layers 누락")
    else:
        layers = analysis["layers"]
        for l in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
            if l not in layers:
                issues.append(f"⚠ {l} 누락")
    if "emergent_questions" not in analysis:
        issues.append("⚠ emergent_questions 누락")
    if "uncertainty_map" not in analysis:
        issues.append("⚠ uncertainty_map 누락")
    if "feedback" not in analysis:
        issues.append("⚠ feedback 누락")

    result = f"✅ 저장: {filepath}\n"
    if issues:
        result += f"⚠ 검증 이슈 {len(issues)}건:\n"
        for issue in issues:
            result += f"  {issue}\n"
    else:
        result += "✅ 스키마 기본 검증 통과\n"

    result += f"\n다음 단계: stereo_render('{filename}') → HTML 보고서 생성"
    return result


# ══════════════════════════════════════════════════
# 도구 4: stereo_render — HTML 보고서 생성
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_render(filename: str) -> str:
    """
    명시된 분석 JSON 파일을 HTML로 변환한다.
    ★ filename 필수. history/에서 자동 탐색하지 않음 (데이터 오염 방지).

    새 분석의 HTML 생성은 stereo_render_direct(json_string)을 사용할 것.

    Args:
        filename: history/ 내 JSON 파일명. 필수.

    Returns:
        Phase 1~4 결과 + 저장 경로
    """
    if not extract_five:
        return "❌ render_adaptive.py import 실패."

    if not filename:
        return "❌ filename 필수. history/에서 자동 탐색하지 않습니다.\n새 분석은 stereo_render_direct(json)를 사용하세요."

    filepath = HISTORY_DIR / filename
    if not filepath.exists():
        return f"❌ 파일 없음: {filepath}"

    with open(filepath, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    # Phase 1~4
    result = []

    five = extract_five(analysis)
    result.append(f"[Phase 1] Core: {five.get('core_finding', '')[:80]}...")
    result.append(f"[Phase 1] Tension: {'있음' if five.get('tension') else '없음'}")
    result.append(f"[Phase 1] Gravity: {five.get('gravity', 'standard')}")

    design = design_report(five, analysis)
    result.append(f"[Phase 2] 유형: {design.get('type_name', '')}")
    result.append(f"[Phase 2] 분류: {design.get('report_class', '')}")
    result.append(f"[Phase 2] 섹션: {design.get('section_count', 0)}개")

    html = render_html(design, analysis, five)

    issues = verify(html, analysis, five)
    if issues:
        result.append(f"[Phase 4] ⚠ 이슈 {len(issues)}건: {', '.join(issues)}")
    else:
        result.append("[Phase 4] ✅ V1~V5 통과")

    # 저장
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    analysis_id = analysis.get("id", "unknown")
    today = analysis.get("date", date.today().isoformat())
    output_name = f"{today}-{analysis_id}-adaptive.html"
    output_path = REPORTS_DIR / output_name
    output_path.write_text(html, encoding="utf-8")

    result.append(f"\n✅ HTML 저장: {output_path}")
    return "\n".join(result)


# ══════════════════════════════════════════════════
# 도구 4-B: stereo_render_direct — dict에서 직접 HTML 생성 (JSON 파일 의존 없음)
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_render_direct(analysis_json: str) -> str:
    """
    분석 결과 dict에서 직접 HTML을 생성한다. JSON 파일 저장 없이 독립 작동.
    JSON은 이력 축적용으로 별도 저장되며, HTML 생성과는 독립.

    Args:
        analysis_json: 분석 결과 JSON 문자열 (SCHEMAS.md 형식)

    Returns:
        Phase 1~4 결과 + HTML 저장 경로
    """
    try:
        from render_adaptive import render_from_dict
    except ImportError:
        try:
            from core.render_adaptive import render_from_dict
        except ImportError:
            return "❌ render_from_dict import 실패."

    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError as e:
        return f"❌ JSON 파싱 오류: {e}"

    html, saved_path = render_from_dict(analysis, save=True)

    if saved_path:
        return f"✅ HTML 생성 완료 (파일 의존 없이 dict에서 직접 생성)\n저장: {saved_path}"
    else:
        return f"✅ HTML 생성 완료 (메모리 전용, 미저장)"


# ══════════════════════════════════════════════════
# 도구 5: stereo_list — 분석 이력 목록
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_list() -> str:
    """
    저장된 분석 이력 목록을 반환한다.

    Returns:
        날짜, 제목, SCP, Type 요약 목록
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)

    if not files:
        return "분석 이력 없음."

    lines = ["📋 Stereo Analyzer 분석 이력", ""]
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            pre = data.get("pre_read", {})
            analysis_id = data.get("id", "?")
            atype = pre.get("type", "?")
            scp = pre.get("scp", "?")
            urgency = pre.get("urgency", "?")
            l1 = data.get("layers", {}).get("L1", {}).get("headline", "")[:50]
            lines.append(f"  {f.name}")
            lines.append(f"    ID: {analysis_id} | {atype} SCP{scp} {urgency}")
            lines.append(f"    L1: {l1}...")
            lines.append("")
        except (json.JSONDecodeError, KeyError):
            lines.append(f"  {f.name} — 파싱 오류")
            lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 도구 6: stereo_get — 특정 분석 결과 조회
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_get(filename: str, section: str = "summary") -> str:
    """
    특정 분석 결과를 조회한다.

    Args:
        filename: history/ 내 JSON 파일명
        section: 조회할 섹션
                 "summary" — Pre-Read + L7 요약
                 "preread" — Pre-Read 상세
                 "layers" — 전체 Layer 요약
                 "tracking" — 추적 지표
                 "questions" — 돌발 질문
                 "uncertainty" — 불확실성 지도
                 "full" — 전체 JSON

    Returns:
        요청한 섹션의 내용
    """
    filepath = HISTORY_DIR / filename
    if not filepath.exists():
        return f"❌ 파일 없음: {filepath}"

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if section == "full":
        return json.dumps(data, ensure_ascii=False, indent=2)

    if section == "preread":
        pre = data.get("pre_read", {})
        return json.dumps(pre, ensure_ascii=False, indent=2)

    if section == "tracking":
        tracking = data.get("layers", {}).get("L7", {}).get("tracking", [])
        if not tracking:
            return "추적 지표 없음."
        lines = ["📡 추적 지표:"]
        for t in tracking:
            name = t.get("metric", t.get("indicator", "?"))
            current = t.get("current", "?")
            trigger = t.get("trigger", "?")
            distance = t.get("distance", "?")
            next_chk = t.get("next_check", "?")
            lines.append(f"  {name}: {current} → 트리거 {trigger} (거리: {distance}) [{next_chk}]")
        return "\n".join(lines)

    if section == "questions":
        qs = data.get("emergent_questions", [])
        if not qs:
            return "돌발 질문 없음."
        lines = ["🔍 돌발 질문:"]
        for q in qs:
            lines.append(f"  [{q.get('lens', '?')}] {q.get('question', '?')}")
            if q.get("answer"):
                lines.append(f"    → {q['answer']}")
        return "\n".join(lines)

    if section == "uncertainty":
        um = data.get("uncertainty_map", {})
        if not um:
            return "불확실성 지도 없음."
        lines = ["📊 불확실성 지도:"]
        for layer in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
            level = um.get(layer, 0)
            bar = "■" * level + "□" * (5 - level)
            lines.append(f"  {layer} [{bar}] {level}/5")
        lines.append(f"  ⚠️ 약한 고리: {um.get('weakest', '?')}")
        lines.append(f"  📡 보강: {um.get('strengthen_by', '?')}")
        return "\n".join(lines)

    if section == "layers":
        layers = data.get("layers", {})
        lines = ["━━ Layer 요약 ━━"]
        for l_name in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
            l_data = layers.get(l_name, {})
            if l_name == "L1":
                lines.append(f"  L1: {l_data.get('headline', '?')[:60]}")
                lines.append(f"      프레이밍: {l_data.get('framing', [])}")
            elif l_name == "L2":
                facts = l_data.get("facts", [])
                unsaid = l_data.get("unsaid", [])
                lines.append(f"  L2: 팩트 {len(facts)}건, 미언급 {len(unsaid)}건")
            elif l_name == "L3":
                players = l_data.get("players", [])
                lines.append(f"  L3: 플레이어 {len(players)}명")
            elif l_name == "L4":
                lines.append(f"  L4: {l_data.get('why_now', '?')[:60]}")
            elif l_name == "L5":
                lines.append(f"  L5: {l_data.get('verdict', '?')} — {l_data.get('system', '?')[:40]}")
            elif l_name == "L6":
                scenarios = l_data.get("scenarios", [])
                lines.append(f"  L6: 시나리오 {len(scenarios)}건")
            elif l_name == "L7":
                lines.append(f"  L7: {l_data.get('signal_or_noise', '?')[:60]}")
        return "\n".join(lines)

    # summary (default)
    pre = data.get("pre_read", {})
    l7 = data.get("layers", {}).get("L7", {})
    fb = data.get("feedback", {})

    lines = [
        f"━━ Stereo 분석 요약: {data.get('id', '?')} ━━",
        f"",
        f"🧭 Pre-Read: {pre.get('type', '?')} SCP{pre.get('scp', '?')} {pre.get('urgency', '?')}",
        f"📌 Core: {data.get('layers', {}).get('L1', {}).get('headline', '?')[:60]}",
        f"🏷️ 구조: {data.get('layers', {}).get('L5', {}).get('verdict', '?')}",
        f"📍 판단: {l7.get('signal_or_noise', '?')[:60]}",
        f"🚨 KC: {l7.get('kill_condition', '?')[:60]}",
        f"🔄 FB-4: {fb.get('fb4_delta', '?')[:60]}",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 도구 7: stereo_validate — 셀프체크 실행
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_validate(filename: str) -> str:
    """
    분석 결과에 대해 셀프검증 체크리스트를 실행한다.

    Args:
        filename: history/ 내 JSON 파일명

    Returns:
        통과/실패 항목 목록
    """
    filepath = HISTORY_DIR / filename
    if not filepath.exists():
        return f"❌ 파일 없음: {filepath}"

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    checks = []
    pre = data.get("pre_read", {})
    layers = data.get("layers", {})
    feedback = data.get("feedback", {})
    eq = data.get("emergent_questions", [])
    um = data.get("uncertainty_map", {})

    # Phase 0
    checks.append(("Pre-Read 실행", bool(pre.get("type"))))
    checks.append(("SCP 근거 1문장", bool(pre.get("scp_basis"))))

    scp = pre.get("scp", 0)
    ptype = pre.get("type", "")
    if scp <= 1 and "NOISE" in ptype:
        checks.append(("NOISE → L1만 종료", "L2" not in layers or not layers["L2"].get("facts")))

    # Phase 2
    l2 = layers.get("L2", {})
    unsaid = l2.get("unsaid", [])
    checks.append(("L2 미언급 2개+", len(unsaid) >= 2))

    facts = l2.get("facts", [])
    all_green = all(
        (f.get("confidence", "") == "🟢" if isinstance(f, dict) else True)
        for f in facts
    )
    checks.append(("L2 전부🟢 아님 (L-02)", not all_green or len(facts) == 0))

    l4 = layers.get("L4", {})
    checks.append(("L4 표면/구조 분리", bool(l4.get("surface_cause")) and bool(l4.get("structural_cause"))))

    l5 = layers.get("L5", {})
    checks.append(("L5 판정+근거", bool(l5.get("verdict")) and bool(l5.get("verdict_basis", l5.get("precedent", "")))))

    l6 = layers.get("L6", {})
    checks.append(("L6 시나리오 존재", bool(l6.get("scenarios"))))

    l7 = layers.get("L7", {})
    checks.append(("L7 시그널/노이즈 조건", bool(l7.get("signal_or_noise"))))

    # FB
    fb_executed = feedback.get("executed", [])
    if "POLICY" in ptype or "STRUCT" in ptype:
        checks.append(("FB-2 실행 (F-01)", "FB-2" in fb_executed))
    checks.append(("FB-4 실행", "FB-4" in fb_executed))

    # EQ
    checks.append(("돌발 질문 1개+", len(eq) >= 1))

    # UM
    checks.append(("불확실성 지도 작성", bool(um.get("weakest"))))

    # 한국 노출 (L-03)
    korea = l6.get("korea_transmission")
    has_korea_mention = "한국" in json.dumps(data, ensure_ascii=False) or "국내" in json.dumps(data, ensure_ascii=False)
    if has_korea_mention:
        checks.append(("한국 전이 경로 구체화 (L-03)", bool(korea)))

    # 결과 출력
    passed = sum(1 for _, v in checks if v)
    total = len(checks)

    lines = [f"📋 셀프검증: {passed}/{total} 통과", ""]
    for name, result in checks:
        icon = "✅" if result else "❌"
        lines.append(f"  {icon} {name}")

    if passed < total:
        failed = [name for name, v in checks if not v]
        lines.append(f"\n⚠ 실패 항목: {', '.join(failed)}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 도구 8: stereo_errors — 오류 기록 조회
# ══════════════════════════════════════════════════
@mcp.tool()
def stereo_errors() -> str:
    """
    errors.md의 오류 기록과 셀프검증 체크리스트를 반환한다.

    Returns:
        오류 기록 테이블 + 방어 규칙 요약
    """
    if not ERRORS_FILE.exists():
        return "errors.md 없음."

    content = ERRORS_FILE.read_text(encoding="utf-8")

    # 오류 기록 부분만 추출
    lines = content.split("\n")
    error_section = []
    in_log = False
    for line in lines:
        if "오류 기록 로그" in line:
            in_log = True
        if in_log:
            error_section.append(line)
        if in_log and line.strip() == "---":
            break

    # 방어 규칙 요약
    defense_rules = [
        "F-01: POLICY/STRUCT → FB-2 필수",
        "L-01: L6에 patterns.md 패턴 1개+ 적용",
        "L-02: L2 전부🟢이면 재점검",
        "L-03: 한국 노출 시 전이 경로 구체화",
        "L-04: 단일 출처 수치 → ⚠ + 교차검증",
        "O-01: 코드↔스키마 키 이름 대조",
    ]

    result = ["━━ 오류 기록 + 방어 규칙 ━━", ""]
    result.append("📋 현행 방어 규칙:")
    for rule in defense_rules:
        result.append(f"  • {rule}")
    result.append("")

    if error_section:
        result.extend(error_section[:20])  # 최근 20줄
    else:
        result.append("오류 기록: 없음")

    return "\n".join(result)


# ══════════════════════════════════════════════════
# 서버 실행
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    print("🔬 Stereo Analyzer MCP Server 시작...")
    print(f"   BASE: {BASE_DIR}")
    print(f"   HISTORY: {HISTORY_DIR}")
    print(f"   도구: stereo_analyze, stereo_preread, stereo_save, stereo_render,")
    print(f"         stereo_list, stereo_get, stereo_validate, stereo_errors")
    mcp.run()
