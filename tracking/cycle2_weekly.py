"""
cycle2_weekly.py — 주별 적중률 학습 + 자기강화
================================================
순환 루프 Cycle 2: Prediction 적중률 → 편향 보정 + conviction template

사용법:
  python cycle2_weekly.py              # 전체 실행 (적중률+편향+강점)
  python cycle2_weekly.py --stats      # 적중률만 조회
  python cycle2_weekly.py --templates  # conviction template 목록 조회
  python cycle2_weekly.py --evolution  # evolution.json 갱신

설계 원칙:
  편향 보정 (피드백): miss 패턴 → 확률 하향 보정
  강점 증폭 (자기강화): hit 패턴 → conviction template → 선제 boost
  최소 표본 5건 이상에서만 작동. 3건 미만은 무시.
"""

import json
import os
import sys
import argparse
from datetime import date
from collections import defaultdict

import psycopg2

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
EVOLUTION_PATH = os.path.join(TRACKING, "evolution.json")

# ── DB 연결 ──
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "invest_ontology",
    "user": "investor",
    "password": "invest2025!secure",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ============================================================
# 1. 적중률 산출
# ============================================================
def calculate_hit_rates(conn):
    """pred_type별 적중률 산출.

    Returns:
        dict: {
            pred_type: {
                total, open, hit, miss, partial, expired,
                hit_rate, resolved_count,
                predictions: [{pred_id, scenario, claim, status, outcome, lesson}, ...]
            }
        }
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT pred_id, pred_type, scenario, claim, probability,
               trigger_condition, status, outcome, lesson, tc_id
        FROM predictions
        ORDER BY pred_type, pred_date
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    stats = defaultdict(lambda: {
        "total": 0, "open": 0, "hit": 0, "miss": 0,
        "partial": 0, "expired": 0,
        "hit_rate": None, "resolved_count": 0,
        "predictions": [],
    })

    for r in rows:
        pt = r["pred_type"]
        stats[pt]["total"] += 1
        stats[pt][r["status"]] += 1
        if r["status"] in ("hit", "miss", "partial", "expired"):
            stats[pt]["resolved_count"] += 1
        stats[pt]["predictions"].append(r)

    # 적중률 계산
    for pt, s in stats.items():
        resolved = s["resolved_count"]
        if resolved > 0:
            # hit=1.0, partial=0.5, miss=0, expired=0
            score = s["hit"] * 1.0 + s["partial"] * 0.5
            s["hit_rate"] = round(score / resolved, 3)

    return dict(stats)


# ============================================================
# 2. 편향 탐지 (피드백)
# ============================================================
def detect_bias(stats):
    """pred_type별 체계적 편향 탐지.

    Returns:
        list of dict: [{
            type: 'overestimate' | 'underestimate',
            pred_type, hit_rate, resolved_count,
            correction_factor, description
        }]
    """
    biases = []

    for pt, s in stats.items():
        resolved = s["resolved_count"]
        if resolved < 3:  # 최소 표본
            continue

        hr = s["hit_rate"]
        if hr is None:
            continue

        if hr < 0.3 and resolved >= 5:
            biases.append({
                "type": "overestimate",
                "pred_type": pt,
                "hit_rate": hr,
                "resolved_count": resolved,
                "correction_factor": round(hr - 0.5, 3),  # 음수
                "description": f"{pt} 유형에서 체계적 과대추정. "
                               f"적중률 {hr:.1%} ({resolved}건). "
                               f"시나리오 확률 하향 보정 필요.",
            })

        if hr > 0.7 and resolved >= 5:
            biases.append({
                "type": "underestimate",
                "pred_type": pt,
                "hit_rate": hr,
                "resolved_count": resolved,
                "correction_factor": round(hr - 0.5, 3),  # 양수
                "description": f"{pt} 유형에서 체계적 과소추정. "
                               f"적중률 {hr:.1%} ({resolved}건). "
                               f"시나리오 확률 상향 보정 가능.",
            })

    return biases


# ============================================================
# 3. Conviction Template 추출 (자기강화)
# ============================================================
def extract_conviction_templates(stats):
    """적중률 높은 패턴에서 conviction template 추출.

    hit_rate >= 0.6이고 resolved >= 5인 패턴에서:
      - 공통 속성 분석 (pred_type, scenario 레이블, 시간 범위)
      - conviction boost 계산

    Returns:
        list of dict: [{
            pred_type, hit_rate, resolved_count,
            conviction_boost, pattern_description,
            hit_predictions: [pred_id, ...],
            scenario_distribution: {A: n, B: n, ...}
        }]
    """
    templates = []

    for pt, s in stats.items():
        resolved = s["resolved_count"]
        hr = s["hit_rate"]

        if hr is None or hr < 0.6 or resolved < 5:
            continue

        # hit인 예측들의 공통 속성 분석
        hit_preds = [p for p in s["predictions"] if p["status"] == "hit"]
        partial_preds = [p for p in s["predictions"] if p["status"] == "partial"]

        # 시나리오 분포
        scenario_dist = defaultdict(int)
        for p in hit_preds + partial_preds:
            scenario_dist[p["scenario"]] += 1

        # 가장 강한 시나리오
        strongest_scenario = max(scenario_dist, key=scenario_dist.get) if scenario_dist else None

        # conviction boost 계산
        # (hit_rate - 0.5) * boost_factor
        # boost_factor는 초기 0.5, hit 지속 시 증가
        base_boost = round((hr - 0.5) * 0.5, 3)
        # 표본 가중: 10건 이상이면 full weight
        weight = min(resolved / 10, 1.0)
        conviction_boost = round(base_boost * weight * 100, 1)  # %p 단위

        templates.append({
            "pred_type": pt,
            "hit_rate": hr,
            "resolved_count": resolved,
            "conviction_boost": f"+{conviction_boost}%p",
            "conviction_boost_raw": conviction_boost,
            "strongest_scenario": strongest_scenario,
            "scenario_distribution": dict(scenario_dist),
            "pattern_description": (
                f"{pt} 유형, 시나리오 {strongest_scenario} 강세. "
                f"적중률 {hr:.1%} ({resolved}건). "
                f"유사 패턴 발견 시 확률 +{conviction_boost}%p boost."
            ),
            "hit_predictions": [p["pred_id"] for p in hit_preds],
        })

    return templates


# ============================================================
# 4. Learning Log 기록
# ============================================================
def record_learning(conn, biases, templates):
    """편향 보정 규칙과 conviction template을 DB에 기록.

    규칙 ID 체계:
      LR-NNN: 편향 보정 규칙 (Learning Rule)
      LS-NNN: 강점 패턴 (Learning Strength)
    """
    cur = conn.cursor()

    # 기존 rule_id 최대값 조회
    cur.execute("SELECT rule_id FROM learning_log ORDER BY rule_id")
    existing = {row[0] for row in cur.fetchall()}

    count = 0

    # 편향 보정 규칙
    for i, bias in enumerate(biases):
        rule_id = f"LR-{i+1:03d}"
        # 기존에 같은 pred_type 규칙이 있으면 갱신
        existing_rule = None
        for eid in existing:
            if eid.startswith("LR-"):
                cur.execute(
                    "SELECT rule_id FROM learning_log WHERE rule_id = %s AND pred_type = %s",
                    (eid, bias["pred_type"]),
                )
                if cur.fetchone():
                    existing_rule = eid
                    break

        if existing_rule:
            cur.execute("""
                UPDATE learning_log
                SET pattern = %s, correction = %s,
                    hit_rate_before = %s, source_predictions = %s
                WHERE rule_id = %s
            """, (
                bias["description"],
                f"확률 보정: {bias['correction_factor']:+.1%}",
                bias["hit_rate"],
                [p["pred_id"] for p in biases[i:i+1]],  # placeholder
                existing_rule,
            ))
        else:
            while rule_id in existing:
                i += 1
                rule_id = f"LR-{i+1:03d}"
            cur.execute("""
                INSERT INTO learning_log (rule_id, created, pattern, correction,
                                         pred_type, hit_rate_before, source_predictions)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rule_id) DO UPDATE SET
                    pattern = EXCLUDED.pattern, correction = EXCLUDED.correction,
                    hit_rate_before = EXCLUDED.hit_rate_before
            """, (
                rule_id, str(date.today()),
                bias["description"],
                f"확률 보정: {bias['correction_factor']:+.1%}",
                bias["pred_type"],
                bias["hit_rate"],
                None,
            ))
            existing.add(rule_id)
        count += 1

    # Conviction Templates
    for i, tmpl in enumerate(templates):
        rule_id = f"LS-{i+1:03d}"
        while rule_id in existing:
            i += 1
            rule_id = f"LS-{i+1:03d}"

        cur.execute("""
            INSERT INTO learning_log (rule_id, created, pattern, correction,
                                     pred_type, hit_rate_before, source_predictions)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (rule_id) DO UPDATE SET
                pattern = EXCLUDED.pattern, correction = EXCLUDED.correction,
                hit_rate_before = EXCLUDED.hit_rate_before,
                source_predictions = EXCLUDED.source_predictions
        """, (
            rule_id, str(date.today()),
            tmpl["pattern_description"],
            f"conviction boost: {tmpl['conviction_boost']}",
            tmpl["pred_type"],
            tmpl["hit_rate"],
            tmpl["hit_predictions"],
        ))
        existing.add(rule_id)
        count += 1

    conn.commit()
    return count


# ============================================================
# 5. Evolution.json 갱신
# ============================================================
def update_evolution(stats, biases, templates):
    """evolution.json의 prediction_stats와 learning_log 갱신."""
    if os.path.exists(EVOLUTION_PATH):
        with open(EVOLUTION_PATH, "r", encoding="utf-8") as f:
            evo = json.load(f)
    else:
        evo = {
            "created": str(date.today()),
            "quality_trend": [],
            "prediction_stats": {},
            "learning_log": [],
            "milestones": [],
        }

    # prediction_stats 갱신
    total = sum(s["total"] for s in stats.values())
    outcomes = {
        "hit": sum(s["hit"] for s in stats.values()),
        "miss": sum(s["miss"] for s in stats.values()),
        "partial": sum(s["partial"] for s in stats.values()),
        "expired": sum(s["expired"] for s in stats.values()),
        "open": sum(s["open"] for s in stats.values()),
    }
    resolved = total - outcomes["open"]
    overall_hr = None
    if resolved > 0:
        overall_hr = round(
            (outcomes["hit"] * 1.0 + outcomes["partial"] * 0.5) / resolved, 3
        )

    hit_rate_by_type = {}
    for pt, s in stats.items():
        if s["hit_rate"] is not None:
            hit_rate_by_type[pt] = {
                "hit_rate": s["hit_rate"],
                "resolved": s["resolved_count"],
                "total": s["total"],
            }

    evo["prediction_stats"] = {
        "total_predictions": total,
        "outcomes": outcomes,
        "overall_hit_rate": overall_hr,
        "hit_rate_by_type": hit_rate_by_type,
        "last_calculated": str(date.today()),
    }

    # learning_log에 이번 주기 기록 추가
    if biases or templates:
        entry = {
            "date": str(date.today()),
            "biases_detected": len(biases),
            "conviction_templates": len(templates),
            "details": [],
        }
        for b in biases:
            entry["details"].append({
                "type": "bias",
                "pred_type": b["pred_type"],
                "direction": b["type"],
                "hit_rate": b["hit_rate"],
                "correction": b["correction_factor"],
            })
        for t in templates:
            entry["details"].append({
                "type": "conviction",
                "pred_type": t["pred_type"],
                "hit_rate": t["hit_rate"],
                "boost": t["conviction_boost"],
                "strongest_scenario": t["strongest_scenario"],
            })
        evo["learning_log"].append(entry)

    evo["last_updated"] = str(date.today())

    with open(EVOLUTION_PATH, "w", encoding="utf-8") as f:
        json.dump(evo, f, ensure_ascii=False, indent=2)

    print(f"  evolution.json 갱신 완료")
    return evo


# ============================================================
# 6. Conviction Template 조회 (Stereo Pre-Read용)
# ============================================================
def get_active_templates(conn):
    """활성 conviction template 목록 조회.

    Stereo Pre-Read에서 호출:
      from cycle2_weekly import get_active_templates
      templates = get_active_templates(conn)
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT rule_id, pattern, correction, pred_type,
               hit_rate_before, source_predictions
        FROM learning_log
        WHERE rule_id LIKE 'LS-%'
        ORDER BY hit_rate_before DESC NULLS LAST
    """)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_active_biases(conn):
    """활성 편향 보정 규칙 조회."""
    cur = conn.cursor()
    cur.execute("""
        SELECT rule_id, pattern, correction, pred_type,
               hit_rate_before
        FROM learning_log
        WHERE rule_id LIKE 'LR-%'
        ORDER BY rule_id
    """)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ============================================================
# 7. 메인 실행
# ============================================================
def run_weekly(update_evo=True):
    """주별 학습 사이클 실행."""
    conn = get_conn()
    today = str(date.today())

    try:
        print(f"━━ Cycle 2 Weekly Learning ({today}) ━━\n")

        # Step 1: 적중률 산출
        stats = calculate_hit_rates(conn)
        print("  ━━ 적중률 ━━")
        for pt, s in stats.items():
            hr_str = f"{s['hit_rate']:.1%}" if s['hit_rate'] is not None else "N/A"
            print(f"    {pt}: {hr_str} "
                  f"(hit:{s['hit']} miss:{s['miss']} partial:{s['partial']} "
                  f"expired:{s['expired']} open:{s['open']})")

        # Step 2: 편향 탐지
        biases = detect_bias(stats)
        if biases:
            print(f"\n  ━━ 편향 탐지: {len(biases)}건 ━━")
            for b in biases:
                icon = "📉" if b["type"] == "overestimate" else "📈"
                print(f"    {icon} {b['pred_type']}: {b['description']}")
        else:
            print(f"\n  편향 탐지: 해당 없음 (표본 부족 또는 정상 범위)")

        # Step 3: Conviction Template 추출
        templates = extract_conviction_templates(stats)
        if templates:
            print(f"\n  ━━ Conviction Templates: {len(templates)}건 ━━")
            for t in templates:
                print(f"    🎯 {t['pred_type']}: {t['pattern_description']}")
        else:
            print(f"\n  Conviction Templates: 해당 없음 (적중률 60%+ & 5건+ 필요)")

        # Step 4: Learning Log 기록
        if biases or templates:
            recorded = record_learning(conn, biases, templates)
            print(f"\n  Learning Log: {recorded}건 기록")
        else:
            print(f"\n  Learning Log: 기록 대상 없음")

        # Step 5: Evolution 갱신
        if update_evo:
            update_evolution(stats, biases, templates)

        # 요약
        total_preds = sum(s["total"] for s in stats.values())
        total_resolved = sum(s["resolved_count"] for s in stats.values())
        total_open = sum(s["open"] for s in stats.values())
        print(f"\n━━ 요약 ━━")
        print(f"  총 예측: {total_preds}건 (resolved: {total_resolved}, open: {total_open})")
        print(f"  편향 규칙: {len(biases)}건 | Conviction: {len(templates)}건")
        if total_resolved > 0:
            overall = (sum(s["hit"] for s in stats.values()) * 1.0 +
                       sum(s["partial"] for s in stats.values()) * 0.5) / total_resolved
            print(f"  전체 적중률: {overall:.1%}")
        else:
            print(f"  전체 적중률: N/A (resolved 예측 없음)")
        print(f"━━━━━━━━━━━")

        return {
            "stats": stats,
            "biases": biases,
            "templates": templates,
        }

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Cycle 2 실패: {e}")
        raise
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cycle 2: Weekly Learning")
    parser.add_argument("--stats", action="store_true",
                        help="적중률만 조회")
    parser.add_argument("--templates", action="store_true",
                        help="conviction template 목록 조회")
    parser.add_argument("--evolution", action="store_true",
                        help="evolution.json만 갱신")
    args = parser.parse_args()

    if args.stats:
        conn = get_conn()
        stats = calculate_hit_rates(conn)
        for pt, s in stats.items():
            hr_str = f"{s['hit_rate']:.1%}" if s['hit_rate'] is not None else "N/A"
            print(f"{pt}: hit_rate={hr_str} total={s['total']} resolved={s['resolved_count']}")
        conn.close()
    elif args.templates:
        conn = get_conn()
        tmpls = get_active_templates(conn)
        if tmpls:
            for t in tmpls:
                print(f"{t['rule_id']}: {t['pattern']}")
                print(f"  boost: {t['correction']} | hit_rate: {t['hit_rate_before']}")
        else:
            print("활성 conviction template 없음")
        conn.close()
    elif args.evolution:
        conn = get_conn()
        stats = calculate_hit_rates(conn)
        biases = detect_bias(stats)
        templates = extract_conviction_templates(stats)
        update_evolution(stats, biases, templates)
        conn.close()
    else:
        run_weekly()
