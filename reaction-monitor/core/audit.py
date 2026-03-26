"""Self-Audit — 수집 완료 후 자기 검증 자동 실행.

사용:
  python core/audit.py                # state.json 기준 Self-Audit Q1~Q5
  python core/audit.py path/to/file   # 지정 파일 기준

SKILL.md Self-Audit Q1~Q5를 코드로 강제 실행한다.
LLM의 자발적 준수가 아닌 코드 검증.

결과: ✅/⚠ 판정 + 상세 근거. ⚠가 system-issues.json에 적재 가능.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ISSUES_PATH = BASE_DIR / "system-issues.json"

MCP_SOURCES = [
    "yahoo finance", "fred", "coingecko", "defillama", "coinmetrics",
    "etherscan", "dart", "sec-edgar", "sec edgar", "blockchain",
    "dune", "apify", "firecrawl", "tavily", "websearch", "web search",
]


def audit(data: dict) -> list[dict]:
    """Self-Audit Q1~Q5 실행. [{id, question, result, detail}] 반환."""
    results = []
    ch = data.get("channels", {})
    rx = data.get("reactions", {})
    pt = data.get("pattern", {})

    # ── Q1: 채널 선정 이유 전수 기록 (R-02) ──
    missing_reasons = []
    for layer_name in ["price", "narrative", "expert", "policy", "positioning"]:
        for i, item in enumerate(ch.get(layer_name, [])):
            if isinstance(item, dict) and not item.get("reason"):
                asset = (item.get("asset", "") or item.get("source", "") or
                         item.get("name", "") or item.get("institution", "") or
                         item.get("indicator", "") or f"[{i}]")
                missing_reasons.append(f"{layer_name}/{asset}")

    q1_pass = len(missing_reasons) == 0
    results.append({
        "id": "Q1",
        "question": "채널 선정에 선정 이유가 모든 채널에 기록되어 있는가? (R-02)",
        "result": "✅" if q1_pass else "⚠",
        "detail": "전체 채널에 reason 기록됨" if q1_pass else
                  f"reason 누락 {len(missing_reasons)}건: {', '.join(missing_reasons[:5])}",
    })

    # ── Q2: 서사+전문가 양쪽에 반대 입장 1건+ (R-03 + F-01) ──
    narrative_roles = set()
    for item in rx.get("narrative", []):
        if isinstance(item, dict):
            narrative_roles.add(item.get("role", ""))

    expert_roles = set()
    for item in rx.get("expert", []):
        if isinstance(item, dict):
            expert_roles.add(item.get("role", ""))

    has_narrative_counter = "반대쪽" in narrative_roles
    has_expert_counter = "반대입장" in expert_roles
    q2_pass = has_narrative_counter and has_expert_counter

    detail_parts = []
    if not has_narrative_counter:
        detail_parts.append("서사에 반대쪽 매체 없음")
    if not has_expert_counter:
        detail_parts.append("전문가에 반대입장 없음 (F-01)")
    results.append({
        "id": "Q2",
        "question": "서사와 전문가 양쪽에 반대 입장이 1건+ 있는가? (R-03 + F-01)",
        "result": "✅" if q2_pass else "⚠",
        "detail": "양쪽 반대 입장 확인됨" if q2_pass else " / ".join(detail_parts),
    })

    # ── Q3: 서사-가격 괴리 명시 (F-04) ──
    narrative_tones = []
    for item in rx.get("narrative", []):
        if isinstance(item, dict):
            narrative_tones.append(item.get("tone", ""))

    price_changes = []
    for item in rx.get("price", []):
        if isinstance(item, dict):
            price_changes.append(item.get("change_pct", 0))

    q3_pass = True
    q3_detail = "괴리 없음 또는 가격/서사 데이터 부족"

    if narrative_tones and price_changes:
        neg_ratio = sum(1 for t in narrative_tones if t in ("부", "neg")) / max(len(narrative_tones), 1)
        pos_ratio = sum(1 for t in narrative_tones if t in ("긍", "pos")) / max(len(narrative_tones), 1)
        avg_chg = sum(price_changes) / max(len(price_changes), 1)

        has_decoupling = (neg_ratio >= 0.6 and avg_chg > -1) or (pos_ratio >= 0.6 and avg_chg < 1)

        if has_decoupling:
            # 괴리가 있을 때 → pattern에 괴리 언급이 있는지 확인
            rationale = (pt.get("direction_rationale", "") or "").lower()
            has_mention = any(kw in rationale for kw in ["괴리", "불일치", "무반응", "과장", "안 믿"])

            if has_mention:
                q3_pass = True
                q3_detail = f"서사-가격 괴리 감지됨. pattern에 괴리 명시 확인 ✓"
            else:
                q3_pass = False
                q3_detail = (f"서사 부정 {neg_ratio*100:.0f}%/긍정 {pos_ratio*100:.0f}% vs "
                             f"가격 평균 {avg_chg:+.1f}%. 괴리가 있으나 pattern에 미명시 (F-04)")
        else:
            q3_detail = "서사-가격 방향 일치. 괴리 없음"

    results.append({
        "id": "Q3",
        "question": "가격 반응과 서사 프레임이 불일치할 때 괴리를 명시했는가? (F-04)",
        "result": "✅" if q3_pass else "⚠",
        "detail": q3_detail,
    })

    # ── Q4: 침묵 기록 (R-09) ──
    silence_count = 0
    for item in rx.get("expert", []):
        if isinstance(item, dict):
            direction = (item.get("direction", "") or "").lower()
            statement = (item.get("statement", "") or "").lower()
            if "침묵" in direction or "침묵" in statement:
                silence_count += 1
    for item in rx.get("policy", []):
        if isinstance(item, dict):
            action = (item.get("action", "") or "").lower()
            if "침묵" in action:
                silence_count += 1

    # 전문가가 3명+ 있는데 침묵 0건이면 의심
    expert_count = len(rx.get("expert", []))
    q4_pass = silence_count > 0 or expert_count < 3

    results.append({
        "id": "Q4",
        "question": "전문가 선행 목록에서 못 찾은 사람을 침묵으로 기록했는가? (R-09)",
        "result": "✅" if q4_pass else "⚠",
        "detail": f"침묵 기록 {silence_count}건" if silence_count > 0 else
                  (f"전문가 {expert_count}명인데 침묵 0건. 전원 발언 확인? 또는 R-09 누락"
                   if expert_count >= 3 else "전문가 수 적어 침묵 체크 생략"),
    })

    # ── Q5: 핵심 수치 1차 소스 (R-05 + F-02) ──
    total_price = 0
    mcp_price = 0
    non_mcp_assets = []

    for item in rx.get("price", []):
        if not isinstance(item, dict):
            continue
        total_price += 1
        source = (item.get("source", "") or "").lower()
        is_mcp = any(p in source for p in MCP_SOURCES)
        if is_mcp:
            mcp_price += 1
        else:
            non_mcp_assets.append(item.get("asset", "?"))

    if total_price == 0:
        q5_pass = True
        q5_detail = "가격 데이터 없음 (수집 자체 부재)"
    else:
        ratio = mcp_price / total_price
        q5_pass = ratio >= 0.8  # 80% 이상 MCP
        q5_detail = (f"MCP 소스 {mcp_price}/{total_price} ({ratio*100:.0f}%). "
                     + ("✓ 충분" if q5_pass else
                        f"비MCP 자산: {', '.join(non_mcp_assets[:3])}. 1차 소스 확인 필요 (F-02)"))

    results.append({
        "id": "Q5",
        "question": "핵심 수치의 1차 출처가 MCP 또는 원본인가? (R-05 + F-02)",
        "result": "✅" if q5_pass else "⚠",
        "detail": q5_detail,
    })

    return results


def main():
    # 파일 경로
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    auto_log = "--auto-log" in flags

    if args:
        path = Path(args[0])
    else:
        path = BASE_DIR / "state.json"

    if not path.exists():
        print(f"❌ 파일 없음: {path}")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    results = audit(data)

    # 출력
    pass_count = sum(1 for r in results if r["result"] == "✅")
    warn_count = sum(1 for r in results if r["result"] == "⚠")

    print(f"\n{'=' * 60}")
    print(f"  Self-Audit — {data.get('issue', '?')[:40]}")
    print(f"{'=' * 60}")
    print(f"  ✅ {pass_count}건  |  ⚠ {warn_count}건  |  총 {len(results)}건")
    print(f"{'=' * 60}\n")

    for r in results:
        icon = r["result"]
        print(f"  {icon} {r['id']}: {r['question']}")
        print(f"     → {r['detail']}\n")

    # 판정
    if warn_count == 0:
        print(f"  결과: 정상 완료\n")
    elif warn_count <= 2:
        print(f"  결과: ⚠ {warn_count}건. 일회성이면 보고서 내 보완. 시스템성이면 이슈 적재.\n")
    else:
        print(f"  결과: ⚠ {warn_count}건 (3개+). 수집 품질 의심. 보충 수집 검토.\n")

    # 자동 이슈 적재
    if auto_log and warn_count > 0:
        from validate import auto_log_issues, _load_issues
        # audit ⚠를 validate issue 형식으로 변환
        audit_issues = []
        for r in results:
            if r["result"] == "⚠":
                audit_issues.append({
                    "level": "WARN",
                    "field": f"Self-Audit {r['id']}",
                    "message": f"{r['question']} — {r['detail']}",
                })
        added = auto_log_issues(audit_issues, data)
        if added:
            print(f"  📋 system-issues.json에 {added}건 자동 적재\n")
        else:
            print(f"  📋 새로운 이슈 없음 (중복 또는 이미 적재)\n")

    return 1 if warn_count >= 3 else 0


if __name__ == "__main__":
    sys.exit(main())
