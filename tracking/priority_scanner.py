"""
priority_scanner.py — DB 기반 이슈 우선순위 진단
=================================================
Scanner S5(사용자 선택) 전에 호출하여,
"전이 경로의 빈 곳"을 진단하고 이슈에 우선순위를 부여.

사용법:
  python priority_scanner.py                    # 빈 곳 진단만 (이슈 없이)
  python priority_scanner.py --issues issues.json  # 이슈 목록과 매칭
  python priority_scanner.py --format brief     # 1줄 요약만

Scanner 연동:
  Scanner S5 제시 전에 이 스크립트의 diagnose_gaps()를 호출.
  반환된 gaps를 이슈 목록과 교차하여 우선순위 표시.
"""

import json
import os
import sys
import argparse
from datetime import date, timedelta
from collections import defaultdict

import psycopg2

# ── DB ──
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "invest_ontology",
    "user": "investor",
    "password": "invest2025!secure",
}

CARDS_DIR = r"C:\Users\이미영\Downloads\에이전트\01-New project\tracking\cards"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ============================================================
# 1. 빈 곳 진단 (Gap Diagnosis)
# ============================================================
def diagnose_gaps(conn):
    """DB를 스캔하여 전이 경로의 빈 곳을 진단.

    Returns:
        dict: {
            gaps: [
                {type, severity, description, keywords, boost}
            ],
            context: {
                th_directions, tc_count, psf_layers, sd_candidates, urgent_tc
            }
        }
    """
    cur = conn.cursor()
    gaps = []

    # ── 1. TH 방향 분포 ──
    cur.execute("""
        SELECT to_regime, count(*), avg(confidence)
        FROM th_cards WHERE status = 'active'
        GROUP BY to_regime
    """)
    th_directions = {}
    for regime, cnt, conf in cur.fetchall():
        th_directions[regime] = {"count": cnt, "avg_confidence": float(conf)}

    known_directions = {"risk-off", "risk-on", "transition"}
    missing_directions = known_directions - set(th_directions.keys())

    for direction in missing_directions:
        keywords = {
            "risk-on": ["완화", "금리인하", "유동성", "QE", "Fed", "rally", "MMF", "SOFR"],
            "risk-off": ["긴축", "관세", "전쟁", "인플레", "위기", "VIX"],
            "transition": ["전환", "재편", "AI", "에너지", "탈탄소", "디지털"],
        }
        gaps.append({
            "type": "th_direction_missing",
            "severity": "high",
            "description": f"TH '{direction}' 방향 부재. 전이 경로에 이 분기가 없음.",
            "keywords": keywords.get(direction, []),
            "boost": 30,  # 우선순위 가산점
        })

    # ── 2. PSF 3층 분포 ──
    cur.execute("SELECT tc_id, tags FROM tc_cards WHERE status = 'active' AND tags IS NOT NULL")
    layer_count = {"pan": 0, "structure": 0, "flow": 0}
    pan_tags = {"POLICY", "관세", "규제", "법", "WTO", "통상"}
    struct_tags = {"STRUCT", "구조", "전환", "재편", "산업", "AI", "에너지"}
    flow_tags = {"MACRO", "금리", "유동성", "환율", "자본", "MMF", "Fed", "크립토"}

    for tc_id, tags in cur.fetchall():
        if tags:
            tag_set = set(tags)
            if tag_set & pan_tags:
                layer_count["pan"] += 1
            if tag_set & struct_tags:
                layer_count["structure"] += 1
            if tag_set & flow_tags:
                layer_count["flow"] += 1

    # tags 없는 TC도 제목 기반 분류
    cur.execute("SELECT tc_id, title FROM tc_cards WHERE status = 'active' AND (tags IS NULL OR tags = '{}')")
    for tc_id, title in cur.fetchall():
        t = title.lower() if title else ""
        if any(kw in t for kw in ["관세", "301", "eu", "통상", "규제"]):
            layer_count["pan"] += 1
        if any(kw in t for kw in ["전환", "구조", "adr", "방산", "isa"]):
            layer_count["structure"] += 1
        if any(kw in t for kw in ["금리", "환율", "krw", "인플레", "채", "유동성"]):
            layer_count["flow"] += 1

    for layer, count in layer_count.items():
        if count == 0:
            layer_keywords = {
                "pan": ["관세", "규제", "법안", "WTO", "무역", "통상", "제재"],
                "structure": ["전환", "재편", "AI", "에너지", "산업", "공급망"],
                "flow": ["금리", "유동성", "환율", "자본", "MMF", "Fed", "QT", "크립토"],
            }
            gaps.append({
                "type": "psf_layer_empty",
                "severity": "high",
                "description": f"PSF '{layer}' 계층 TC 0개. 전이 경로의 한 축이 비어있음.",
                "keywords": layer_keywords.get(layer, []),
                "boost": 25,
            })
        elif count == 1:
            gaps.append({
                "type": "psf_layer_thin",
                "severity": "medium",
                "description": f"PSF '{layer}' 계층 TC {count}개. 수렴 판단에 부족.",
                "keywords": [],
                "boost": 10,
            })

    # ── 3. TC 갱신 급한 것 ──
    urgent_tc = []
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")

        # check_log / phase_log에서 next_check 추출
        next_check = None
        for log_entry in reversed(d.get("check_log", d.get("phase_log", []))):
            if isinstance(log_entry, dict) and "next_check" in log_entry:
                next_check = log_entry["next_check"]
                break

        # tracking_indicators에서 next_check 추출
        if not next_check:
            for ind in d.get("tracking_indicators", []):
                if isinstance(ind, dict) and "next_check" in ind:
                    nc = ind["next_check"]
                    if not next_check or nc < next_check:
                        next_check = nc

        if next_check:
            try:
                nc_date = date.fromisoformat(next_check)
                days_until = (nc_date - date.today()).days
                if days_until <= 3:
                    urgency = "urgent"
                    boost = 20
                elif days_until <= 7:
                    urgency = "soon"
                    boost = 10
                else:
                    urgency = "normal"
                    boost = 0

                if urgency in ("urgent", "soon"):
                    title = d.get("title", tc_id)
                    urgent_tc.append({
                        "tc_id": tc_id,
                        "title": title,
                        "next_check": next_check,
                        "days_until": days_until,
                        "urgency": urgency,
                    })
                    gaps.append({
                        "type": "tc_update_urgent",
                        "severity": urgency,
                        "description": f"{tc_id} 갱신 필요 ({next_check}, {days_until}일 후). {title[:30]}",
                        "keywords": title.split()[:3] if title else [],
                        "boost": boost,
                        "tc_id": tc_id,
                    })
            except ValueError:
                pass

    # ── 4. SD 승격 후보 ──
    cur.execute("""
        SELECT sd_id, title, appearance_count
        FROM sd_cards WHERE status = 'watching' AND appearance_count >= 2
    """)
    sd_candidates = []
    for sd_id, title, count in cur.fetchall():
        sd_candidates.append({"sd_id": sd_id, "title": title, "count": count})
        gaps.append({
            "type": "sd_promotion_candidate",
            "severity": "medium",
            "description": f"{sd_id} ({title[:30]}) {count}회 출현. 1회 더 반복 시 TC 승격.",
            "keywords": title.split()[:3] if title else [],
            "boost": 15,
        })

    # ── 5. Prediction 집중 영역 ──
    cur.execute("""
        SELECT tc_id, count(*) as pred_count
        FROM predictions WHERE status = 'open'
        GROUP BY tc_id ORDER BY pred_count DESC
    """)
    pred_concentration = dict(cur.fetchall())

    # 예측이 많은 TC = 검증이 급한 TC
    for tc_id, count in pred_concentration.items():
        if count >= 3:
            gaps.append({
                "type": "prediction_dense",
                "severity": "medium",
                "description": f"{tc_id}에 open 예측 {count}건. 검증 데이터 필요.",
                "keywords": [],
                "boost": 8,
                "tc_id": tc_id,
            })

    # 정렬: severity(high→medium→low) + boost 내림차순
    severity_order = {"high": 0, "urgent": 1, "medium": 2, "soon": 3, "low": 4}
    gaps.sort(key=lambda g: (severity_order.get(g["severity"], 9), -g["boost"]))

    return {
        "gaps": gaps,
        "context": {
            "th_directions": th_directions,
            "missing_directions": sorted(missing_directions),
            "tc_count": len([f for f in os.listdir(CARDS_DIR) if f.startswith("TC-")]),
            "psf_layers": layer_count,
            "sd_candidates": sd_candidates,
            "urgent_tc": urgent_tc,
            "pred_concentration": pred_concentration,
        },
    }


# ============================================================
# 2. 이슈 매칭 (Scanner 이슈 × 빈 곳)
# ============================================================
def match_issues(gaps_result, issues):
    """Scanner가 발견한 이슈에 빈 곳 기반 우선순위를 부여.

    Args:
        gaps_result: diagnose_gaps() 결과
        issues: list of dict [{title, summary, keywords, ...}]

    Returns:
        list of dict: 우선순위 정렬된 이슈 [{..., priority_score, priority_reasons}]
    """
    gaps = gaps_result["gaps"]

    for issue in issues:
        score = 0
        reasons = []

        issue_text = " ".join([
            issue.get("title", ""),
            issue.get("summary", ""),
            " ".join(issue.get("keywords", [])),
        ]).lower()

        for gap in gaps:
            # 키워드 매칭
            matched_keywords = [kw for kw in gap.get("keywords", []) if kw.lower() in issue_text]
            if matched_keywords:
                score += gap["boost"]
                reasons.append({
                    "gap_type": gap["type"],
                    "description": gap["description"],
                    "matched_keywords": matched_keywords,
                    "boost": gap["boost"],
                })

            # TC 갱신 급한 것과 제목 매칭
            if gap.get("tc_id"):
                # TC 제목과 이슈 제목 유사도 (간단한 키워드 매칭)
                tc_keywords = gap.get("keywords", [])
                tc_matched = [kw for kw in tc_keywords if kw.lower() in issue_text]
                if tc_matched:
                    score += gap["boost"] // 2
                    reasons.append({
                        "gap_type": "tc_related",
                        "description": f"{gap['tc_id']} 관련 이슈",
                        "matched_keywords": tc_matched,
                        "boost": gap["boost"] // 2,
                    })

        issue["priority_score"] = score
        issue["priority_reasons"] = reasons

    # 정렬: priority_score 내림차순
    issues.sort(key=lambda i: -i["priority_score"])
    return issues


# ============================================================
# 3. 출력
# ============================================================
def print_diagnosis(gaps_result, format_type="full"):
    """빈 곳 진단 결과 출력."""
    gaps = gaps_result["gaps"]
    ctx = gaps_result["context"]
    today = str(date.today())

    if format_type == "brief":
        print(f"━━ 전이 경로 빈 곳 ({today}) ━━")
        for g in gaps[:5]:
            icon = {"high": "🔴", "urgent": "🟠", "medium": "🟡"}.get(g["severity"], "⚪")
            print(f"  {icon} {g['description'][:70]}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return

    print(f"━━ 전이 경로 빈 곳 진단 ({today}) ━━\n")

    # 현황
    print(f"  TC: {ctx['tc_count']}개 | TH: {len(ctx['th_directions'])}개 방향")
    print(f"  PSF 분포: Pan={ctx['psf_layers']['pan']} Struct={ctx['psf_layers']['structure']} Flow={ctx['psf_layers']['flow']}")
    if ctx["th_directions"]:
        for regime, info in ctx["th_directions"].items():
            print(f"  TH → {regime}: {info['count']}건 (conf avg: {info['avg_confidence']:.2f})")
    if ctx["missing_directions"]:
        print(f"  TH 빈 방향: {', '.join(ctx['missing_directions'])}")

    # 빈 곳 상세
    if gaps:
        print(f"\n  ━━ 빈 곳 {len(gaps)}건 (우선순위순) ━━")
        for i, g in enumerate(gaps, 1):
            icon = {"high": "🔴", "urgent": "🟠", "medium": "🟡", "soon": "🟡"}.get(g["severity"], "⚪")
            print(f"\n  [{i}] {icon} {g['description']}")
            print(f"      유형: {g['type']} | boost: +{g['boost']}점")
            if g["keywords"]:
                print(f"      매칭 키워드: {', '.join(g['keywords'][:8])}")
    else:
        print(f"\n  빈 곳 없음. 전이 경로 커버리지 양호.")

    # SD 승격 후보
    if ctx["sd_candidates"]:
        print(f"\n  ━━ SD 승격 후보 ━━")
        for sd in ctx["sd_candidates"]:
            print(f"    {sd['sd_id']}: {sd['title'][:40]} ({sd['count']}회 출현)")

    # 급한 TC
    if ctx["urgent_tc"]:
        print(f"\n  ━━ 갱신 급한 TC ━━")
        for tc in ctx["urgent_tc"]:
            icon = "🔴" if tc["urgency"] == "urgent" else "🟡"
            print(f"    {icon} {tc['tc_id']}: {tc['title'][:40]} (next: {tc['next_check']}, {tc['days_until']}일 후)")

    # 선별 가이드
    print(f"\n  ━━ 이슈 선별 가이드 ━━")
    if ctx["missing_directions"]:
        print(f"    1순위: {', '.join(ctx['missing_directions'])} 방향 이슈 (TH 분기 추가)")
    if any(g["type"] == "psf_layer_empty" for g in gaps):
        empty = [g["description"].split("'")[1] for g in gaps if g["type"] == "psf_layer_empty"]
        print(f"    2순위: PSF {', '.join(empty)} 계층 이슈 (3층 균형)")
    if ctx["urgent_tc"]:
        urgent_ids = [tc["tc_id"] for tc in ctx["urgent_tc"]]
        print(f"    3순위: {', '.join(urgent_ids)} 관련 이슈 (갱신 시급)")
    if ctx["sd_candidates"]:
        sd_ids = [sd["sd_id"] for sd in ctx["sd_candidates"]]
        print(f"    4순위: {', '.join(sd_ids)} 반복 출현 확인 (TC 승격 후보)")

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def print_prioritized_issues(issues):
    """우선순위 매칭된 이슈 목록 출력."""
    print(f"\n  ━━ 이슈 우선순위 (전이 경로 기준) ━━\n")
    for i, issue in enumerate(issues, 1):
        score = issue.get("priority_score", 0)
        if score >= 20:
            icon = "🔴"
        elif score >= 10:
            icon = "🟡"
        else:
            icon = "⚪"

        title = issue.get("title", "제목 없음")[:60]
        print(f"  [{i}] {icon} +{score:2d}점 | {title}")

        for reason in issue.get("priority_reasons", []):
            print(f"        ← {reason['description'][:50]} (키워드: {', '.join(reason['matched_keywords'][:3])})")

    if not issues:
        print("  이슈 없음")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB-based Issue Priority Scanner")
    parser.add_argument("--issues", type=str, help="이슈 목록 JSON 파일 경로")
    parser.add_argument("--format", choices=["full", "brief"], default="full")
    args = parser.parse_args()

    conn = get_conn()
    result = diagnose_gaps(conn)
    print_diagnosis(result, format_type=args.format)

    if args.issues:
        with open(args.issues, "r", encoding="utf-8") as f:
            issues = json.load(f)
        matched = match_issues(result, issues)
        print_prioritized_issues(matched)

    conn.close()
