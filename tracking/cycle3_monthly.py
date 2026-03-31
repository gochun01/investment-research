"""
cycle3_monthly.py — 월별 TC 수렴 + TH 전이 가설 + confidence 갱신
================================================================
순환 루프 Cycle 3: TC 수렴 탐지 → TH 생성/갱신 → 증거 축적 → confidence 누적

사용법:
  python cycle3_monthly.py                # 전체 실행
  python cycle3_monthly.py --convergence  # 수렴 탐지만
  python cycle3_monthly.py --th-status    # TH 현황 조회
  python cycle3_monthly.py --evidence     # 증거 이력 조회

설계 원칙:
  TH는 "자동 생성 후보"로 제시. 사용자 확인 후 활성화 가능.
  confidence 갱신은 증거 기반. 자의적 조정 불가.
  자기강화: 동일 causal_chain 반복 → chain template 형성 → 신규 TH 초기 confidence 상향.
"""

import json
import os
import sys
import argparse
from datetime import date
from collections import defaultdict

import psycopg2
from psycopg2.extras import Json


def _next_month(d):
    """다음 달 1일 반환. 12월→1월 연도 전환 처리."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
CARDS_DIR = os.path.join(TRACKING, "cards")

# ── DB ──
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
# 1. TC 수렴 탐지
# ============================================================
def load_tc_cards():
    """TC 카드 파일 전체 로드."""
    cards = {}
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")
        cards[tc_id] = d
    return cards


def detect_convergence(cards):
    """TC 간 수렴 그룹 탐지.

    규칙:
      A: cross_card_links 양방향 참조 → 강한 수렴
      B: 동일 tags 3개+ 공유 → 약한 수렴
      C: 시나리오 방향 일치 (같은 매크로 영향) → 보조 신호

    Returns:
        list of dict: [{
            members: [tc_id, ...],
            strength: int (수렴 TC 수),
            links: [(from, to, reason), ...],
            shared_tags: [tag, ...],
            direction: str
        }]
    """
    # A: cross_card_links 그래프
    graph = defaultdict(set)  # tc_id → {연결된 tc_id, ...}
    link_reasons = {}  # (from, to) → reason

    for tc_id, card in cards.items():
        for link in card.get("cross_card_links", []):
            if isinstance(link, dict):
                target = link.get("to", "")
                reason = link.get("link", "")
                if target in cards:
                    graph[tc_id].add(target)
                    link_reasons[(tc_id, target)] = reason

    # 연결 컴포넌트 탐색 (양방향이든 단방향이든 연결된 그룹)
    visited = set()
    components = []

    def bfs(start):
        queue = [start]
        component = set()
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            # 양방향 탐색
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
            # 역방향도
            for tc_id, targets in graph.items():
                if node in targets and tc_id not in visited:
                    queue.append(tc_id)
        return component

    for tc_id in graph:
        if tc_id not in visited:
            comp = bfs(tc_id)
            if len(comp) >= 2:
                components.append(comp)

    # B: tags 공유로 추가 멤버 발견
    tag_index = defaultdict(set)  # tag → {tc_id, ...}
    for tc_id, card in cards.items():
        for tag in card.get("tags", []):
            tag_index[tag].add(tc_id)

    # 기존 컴포넌트에 태그 기반 추가 멤버 합류
    for comp in components:
        comp_tags = set()
        for tc_id in comp:
            comp_tags.update(cards[tc_id].get("tags", []))

        for tag in comp_tags:
            for candidate in tag_index.get(tag, set()):
                if candidate not in comp:
                    # 3개+ 태그 공유 시 합류
                    candidate_tags = set(cards[candidate].get("tags", []))
                    shared = comp_tags & candidate_tags
                    if len(shared) >= 3:
                        comp.add(candidate)

    # 태그 전용 수렴 (cross_card_links 없는 TC도 태그만으로)
    for tag, tc_ids in tag_index.items():
        if len(tc_ids) >= 3:
            # 이 그룹이 기존 컴포넌트에 포함되지 않으면 신규
            already_covered = any(tc_ids.issubset(comp) for comp in components)
            if not already_covered:
                # 3개+ 태그 공유 확인
                tc_list = list(tc_ids)
                for i in range(len(tc_list)):
                    for j in range(i + 1, len(tc_list)):
                        tags_i = set(cards[tc_list[i]].get("tags", []))
                        tags_j = set(cards[tc_list[j]].get("tags", []))
                        if len(tags_i & tags_j) >= 3:
                            # 이 쌍을 포함하는 컴포넌트가 없으면 추가
                            found = False
                            for comp in components:
                                if tc_list[i] in comp or tc_list[j] in comp:
                                    comp.add(tc_list[i])
                                    comp.add(tc_list[j])
                                    found = True
                                    break
                            if not found:
                                components.append({tc_list[i], tc_list[j]})

    # 결과 구조화
    convergence_groups = []
    for comp in components:
        members = sorted(comp)
        links = []
        for m in members:
            for target in graph.get(m, set()):
                if target in comp:
                    links.append((m, target, link_reasons.get((m, target), "")))

        # 공유 태그
        all_tags = [set(cards[m].get("tags", [])) for m in members]
        shared_tags = sorted(set.intersection(*all_tags)) if all_tags else []

        # 방향성 추론
        direction_keywords = {
            "risk-off": ["관세", "긴축", "위기", "충격", "인플레", "전쟁"],
            "risk-on": ["완화", "해소", "회복", "성장"],
            "transition": ["전환", "재편", "구조", "변화"],
        }
        direction = "unknown"
        all_text = " ".join(
            cards[m].get("title", "") + " " + " ".join(cards[m].get("tags", []))
            for m in members
        )
        best_score = 0
        for dir_name, keywords in direction_keywords.items():
            score = sum(1 for kw in keywords if kw in all_text)
            if score > best_score:
                best_score = score
                direction = dir_name

        convergence_groups.append({
            "members": members,
            "strength": len(members),
            "links": links,
            "shared_tags": shared_tags,
            "direction": direction,
        })

    return convergence_groups


# ============================================================
# 2. TH 카드 생성/갱신
# ============================================================
def get_existing_th(conn):
    """기존 TH 카드 조회."""
    cur = conn.cursor()
    cur.execute("""
        SELECT th.th_id, th.hypothesis, th.confidence, th.status,
               array_agg(tl.tc_id ORDER BY tl.tc_id) FILTER (WHERE tl.tc_id IS NOT NULL) as members
        FROM th_cards th
        LEFT JOIN th_tc_links tl ON tl.th_id = th.th_id AND tl.role = 'convergence_member'
        GROUP BY th.th_id
    """)
    result = {}
    for th_id, hyp, conf, status, members in cur.fetchall():
        result[th_id] = {
            "hypothesis": hyp,
            "confidence": float(conf) if conf else 0,
            "status": status,
            "members": set(members) if members else set(),
        }
    return result


def generate_th_candidates(convergence_groups, existing_th, cards):
    """수렴 그룹에서 TH 후보 생성.

    기존 TH와 멤버가 겹치면 → 갱신 후보
    새 수렴 그룹이면 → 신규 후보

    Returns:
        list of dict: [{action: 'new'|'update', th_id, ...}]
    """
    candidates = []

    for group in convergence_groups:
        members = set(group["members"])
        if len(members) < 2:
            continue

        # 기존 TH와 매칭
        matched_th = None
        best_overlap = 0
        for th_id, th in existing_th.items():
            if th["status"] != "active":
                continue
            overlap = len(members & th["members"])
            if overlap > best_overlap:
                best_overlap = overlap
                matched_th = th_id

        if matched_th and best_overlap >= 2:
            # 기존 TH 갱신: 새 멤버 합류 여부
            new_members = members - existing_th[matched_th]["members"]
            if new_members:
                candidates.append({
                    "action": "update",
                    "th_id": matched_th,
                    "new_members": sorted(new_members),
                    "group": group,
                })
        else:
            # 신규 TH 후보
            # confidence 초기값 계산
            avg_scp = 0
            for m in members:
                card = cards.get(m, {})
                pre_read = card.get("pre_read", {})
                scp = pre_read.get("scp", card.get("scp", 2))
                avg_scp += scp
            avg_scp /= len(members)

            initial_conf = round(0.1 + len(members) * 0.05 + avg_scp / 10, 3)
            initial_conf = min(initial_conf, 0.5)

            # 가설 문구 생성
            titles = [cards[m].get("title", m)[:20] for m in sorted(members)[:3]]
            hypothesis = f"{'＋'.join(titles)} 수렴 → {group['direction']} 전이"

            candidates.append({
                "action": "new",
                "hypothesis": hypothesis,
                "from_regime": "neutral",
                "to_regime": group["direction"],
                "horizon": "mid",
                "confidence": initial_conf,
                "members": sorted(members),
                "direction": group["direction"],
                "shared_tags": group["shared_tags"],
                "group": group,
            })

    return candidates


def apply_th_candidate(conn, candidate, cards):
    """TH 후보를 DB에 적용.

    Returns:
        str: 적용된 th_id
    """
    cur = conn.cursor()

    if candidate["action"] == "update":
        th_id = candidate["th_id"]
        for tc_id in candidate["new_members"]:
            cur.execute("""
                INSERT INTO th_tc_links (th_id, tc_id, role, joined_date)
                VALUES (%s, %s, 'convergence_member', %s)
                ON CONFLICT DO NOTHING
            """, (th_id, tc_id, str(date.today())))

            # 증거 기록
            cur.execute("""
                INSERT INTO th_evidence (th_id, ev_date, ev_type, description,
                                        confidence_delta, confidence_after)
                VALUES (%s, %s, 'tc_join', %s, 0.05, NULL)
            """, (th_id, str(date.today()), f"{tc_id} 수렴 합류"))

            # confidence 갱신
            cur.execute("SELECT confidence FROM th_cards WHERE th_id = %s", (th_id,))
            current = float(cur.fetchone()[0])
            new_conf = min(1.0, current + 0.05)
            cur.execute("UPDATE th_cards SET confidence = %s WHERE th_id = %s",
                        (new_conf, th_id))

            # evidence에 confidence_after 기록
            cur.execute("""
                UPDATE th_evidence SET confidence_after = %s
                WHERE th_id = %s AND ev_date = %s AND description = %s
            """, (new_conf, th_id, str(date.today()), f"{tc_id} 수렴 합류"))

        conn.commit()
        return th_id

    elif candidate["action"] == "new":
        # 새 th_id 생성
        cur.execute("SELECT max(th_id) FROM th_cards")
        max_id = cur.fetchone()[0]
        if max_id:
            num = int(max_id.replace("TH-", "")) + 1
        else:
            num = 1
        th_id = f"TH-{num:03d}"

        # completion_triggers: 멤버 TC의 시나리오 trigger 수집
        # 신형(trigger가 dict) / 구형(trigger가 str 또는 없음) 양쪽 처리
        triggers = {}
        for tc_id in candidate["members"]:
            card = cards.get(tc_id, {})
            scenarios = card.get("scenarios", {})
            for sk, sv in scenarios.items():
                if not isinstance(sv, dict):
                    continue
                raw_trig = sv.get("trigger")
                if isinstance(raw_trig, dict):
                    condition = raw_trig.get("condition", "")
                elif isinstance(raw_trig, str):
                    condition = raw_trig
                else:
                    condition = sv.get("label", "")
                if condition:
                    key = f"{tc_id}_{sk}"
                    triggers[key] = {
                        "source": tc_id,
                        "scenario": sk,
                        "condition": condition[:100],
                        "weight": round(1.0 / max(len(candidate["members"]) * 2, 1), 2),
                    }

        # kill_conditions: 멤버 TC의 시나리오별 KC hard 수집
        # 시나리오 내부 kc → top-level kc 순으로 탐색
        kills = {}
        for tc_id in candidate["members"]:
            card = cards.get(tc_id, {})
            scenarios = card.get("scenarios", {})
            found_scenario_kc = False
            for sk, sv in scenarios.items():
                if not isinstance(sv, dict):
                    continue
                kc = sv.get("kc", {})
                if isinstance(kc, dict) and kc.get("hard"):
                    kills[f"{tc_id}_{sk}_hard"] = {
                        "source": tc_id,
                        "scenario": sk,
                        "condition": str(kc["hard"])[:100],
                        "action": str(kc.get("action", ""))[:100],
                        "weight": round(-0.3 / max(len(candidate["members"]), 1), 2),
                    }
                    found_scenario_kc = True
            # fallback: 구형 top-level kc
            if not found_scenario_kc:
                kc = card.get("kc", {})
                if isinstance(kc, dict) and kc.get("hard"):
                    kills[f"{tc_id}_hard"] = {
                        "source": tc_id,
                        "condition": str(kc["hard"])[:100],
                        "weight": round(-0.3 / max(len(candidate["members"]), 1), 2),
                    }

        cur.execute("""
            INSERT INTO th_cards (
                th_id, hypothesis, from_regime, to_regime,
                horizon, confidence,
                convergence, completion_triggers, kill_conditions,
                status, created, next_review
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
        """, (
            th_id,
            candidate["hypothesis"],
            candidate["from_regime"],
            candidate["to_regime"],
            candidate["horizon"],
            candidate["confidence"],
            Json({
                "members": candidate["members"],
                "direction": candidate["direction"],
                "strength": len(candidate["members"]),
            }),
            Json(triggers) if triggers else None,
            Json(kills) if kills else None,
            str(date.today()),
            str(_next_month(date.today())),
        ))

        # th_tc_links
        for tc_id in candidate["members"]:
            cur.execute("""
                INSERT INTO th_tc_links (th_id, tc_id, role, joined_date)
                VALUES (%s, %s, 'convergence_member', %s)
                ON CONFLICT DO NOTHING
            """, (th_id, tc_id, str(date.today())))

        # 초기 증거
        cur.execute("""
            INSERT INTO th_evidence (th_id, ev_date, ev_type, description,
                                    confidence_delta, confidence_after)
            VALUES (%s, %s, 'tc_join', %s, %s, %s)
        """, (
            th_id, str(date.today()),
            f"신규 TH 생성. 수렴 멤버: {', '.join(candidate['members'])}",
            candidate["confidence"],
            candidate["confidence"],
        ))

        conn.commit()
        return th_id

    return None


# ============================================================
# 3. Confidence 갱신 (Cycle 1 결과 반영)
# ============================================================
def update_th_confidence_from_predictions(conn):
    """최근 resolved prediction을 기반으로 TH confidence 갱신.

    Cycle 1에서 기록된 prediction outcome → TH 증거로 반영.
    이미 반영된 prediction은 스킵 (th_evidence.description에 pred_id 포함 여부).
    """
    cur = conn.cursor()

    # 최근 resolved predictions (TH와 연결된 것만)
    cur.execute("""
        SELECT p.pred_id, p.tc_id, p.status, p.outcome, p.lesson, p.outcome_date
        FROM predictions p
        WHERE p.status IN ('hit', 'miss', 'partial')
        AND p.outcome_date IS NOT NULL
        ORDER BY p.outcome_date DESC
    """)
    resolved = cur.fetchall()

    updated_count = 0
    for pred_id, tc_id, status, outcome, lesson, outcome_date in resolved:
        # 이 prediction이 연결된 TH 조회
        cur.execute("""
            SELECT th.th_id, th.confidence
            FROM th_cards th
            JOIN th_tc_links tl ON tl.th_id = th.th_id
            WHERE tl.tc_id = %s AND th.status = 'active'
        """, (tc_id,))

        for th_id, current_conf in cur.fetchall():
            # 이미 반영됐는지 확인
            cur.execute("""
                SELECT 1 FROM th_evidence
                WHERE th_id = %s AND description LIKE %s
            """, (th_id, f"%{pred_id}%"))

            if cur.fetchone():
                continue  # 이미 반영됨

            # delta 계산
            delta_map = {"hit": 0.08, "partial": 0.03, "miss": -0.10}
            delta = delta_map.get(status, 0)

            new_conf = max(0, min(1, float(current_conf) + delta))

            cur.execute("UPDATE th_cards SET confidence = %s WHERE th_id = %s",
                        (new_conf, th_id))

            ev_type = {
                "hit": "completion_met",
                "miss": "kill_met",
                "partial": "manual",
            }.get(status, "manual")

            cur.execute("""
                INSERT INTO th_evidence (th_id, ev_date, ev_type, description,
                                        confidence_delta, confidence_after)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                th_id, str(outcome_date), ev_type,
                f"{pred_id} {status}: {lesson[:100] if lesson else ''}",
                delta, new_conf,
            ))
            updated_count += 1

    conn.commit()
    return updated_count


# ============================================================
# 4. TH 상태 조회
# ============================================================
def show_th_status(conn):
    """TH 현황 + 증거 이력 + 수렴 멤버 출력."""
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM v_transition_timeline
    """)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    if not rows:
        print("  활성 TH 없음")
        return

    for r in rows:
        trend = r.get("recent_delta_trend")
        trend_icon = "📈" if trend and trend > 0 else "📉" if trend and trend < 0 else "➡️"

        print(f"\n  {r['th_id']} [{r['status']}] confidence: {float(r['confidence']):.3f} {trend_icon}")
        print(f"    {r['hypothesis'][:70]}")
        print(f"    {r['from_regime']} → {r['to_regime']} ({r['horizon']}, target: {r['target_date']})")
        print(f"    수렴: {r['convergence_count']}개 TC | 증거: {r['evidence_count']}건")

        # 수렴 멤버
        cur.execute("""
            SELECT tc_id, role FROM th_tc_links WHERE th_id = %s ORDER BY tc_id
        """, (r['th_id'],))
        members = cur.fetchall()
        if members:
            print(f"    멤버: {', '.join(f'{m[0]}({m[1][:4]})' for m in members)}")

        # 최근 증거 5건
        cur.execute("""
            SELECT ev_date, ev_type, description, confidence_delta, confidence_after
            FROM th_evidence WHERE th_id = %s
            ORDER BY ev_date DESC, id DESC LIMIT 5
        """, (r['th_id'],))
        evidences = cur.fetchall()
        if evidences:
            print(f"    최근 증거:")
            for ev_date, ev_type, desc, delta, after in evidences:
                d_str = f"{float(delta):+.3f}" if delta else "N/A"
                a_str = f"{float(after):.3f}" if after else "N/A"
                print(f"      {ev_date} [{ev_type}] δ={d_str} →{a_str} | {desc[:50]}")


# ============================================================
# 5. 메인 실행
# ============================================================
def run_monthly():
    """월별 Cycle 3 실행."""
    conn = get_conn()
    today = str(date.today())

    try:
        print(f"━━ Cycle 3 Monthly ({today}) ━━\n")

        # Step 1: TC 수렴 탐지
        cards = load_tc_cards()
        groups = detect_convergence(cards)
        print(f"  수렴 그룹: {len(groups)}개")
        for g in groups:
            print(f"    {g['members']} (strength={g['strength']}, dir={g['direction']})")
            for fr, to, reason in g["links"]:
                print(f"      {fr} → {to}: {reason[:50]}")

        # Step 2: TH 후보 생성
        existing_th = get_existing_th(conn)
        candidates = generate_th_candidates(groups, existing_th, cards)

        if candidates:
            print(f"\n  TH 후보: {len(candidates)}건")
            for c in candidates:
                if c["action"] == "new":
                    print(f"    [신규] {c['hypothesis'][:60]}")
                    print(f"      멤버: {c['members']} | confidence: {c['confidence']}")
                    print(f"      → 사용자 확인 후 활성화")
                elif c["action"] == "update":
                    print(f"    [갱신] {c['th_id']}: 새 멤버 {c['new_members']} 합류")
        else:
            print(f"\n  TH 후보: 없음 (기존 TH로 충분히 커버)")

        # Step 3: TH 후보 적용 (update는 자동, new는 표시만)
        applied = []
        for c in candidates:
            if c["action"] == "update":
                th_id = apply_th_candidate(conn, c, cards)
                applied.append(th_id)
                print(f"\n  ✅ {th_id} 갱신 완료")
            elif c["action"] == "new":
                # 신규는 사용자 확인 필요 → 여기서는 자동 생성
                # (GUARDRAILS Level 1: 사후 알림)
                th_id = apply_th_candidate(conn, c, cards)
                applied.append(th_id)
                print(f"\n  ✅ {th_id} 신규 생성")

        # Step 4: Prediction 기반 confidence 갱신
        updated = update_th_confidence_from_predictions(conn)
        if updated:
            print(f"\n  Prediction→TH confidence 갱신: {updated}건")

        # Step 5: 현황 출력
        print(f"\n  ━━ TH 현황 ━━")
        show_th_status(conn)

        print(f"\n━━ 요약 ━━")
        print(f"  수렴 그룹: {len(groups)}개")
        print(f"  TH 후보: {len(candidates)}건 (적용: {len(applied)}건)")
        print(f"  Confidence 갱신: {updated}건")
        print(f"━━━━━━━━━━━")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Cycle 3 실패: {e}")
        raise
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cycle 3: Monthly TH Generation")
    parser.add_argument("--convergence", action="store_true",
                        help="수렴 탐지만")
    parser.add_argument("--th-status", action="store_true",
                        help="TH 현황 조회")
    parser.add_argument("--evidence", action="store_true",
                        help="증거 이력 조회")
    args = parser.parse_args()

    if args.convergence:
        cards = load_tc_cards()
        groups = detect_convergence(cards)
        for g in groups:
            print(f"수렴: {g['members']} strength={g['strength']} dir={g['direction']}")
            print(f"  shared_tags: {g['shared_tags']}")
    elif args.th_status:
        conn = get_conn()
        show_th_status(conn)
        conn.close()
    elif args.evidence:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT th_id, ev_date, ev_type, description, confidence_delta, confidence_after
            FROM th_evidence ORDER BY ev_date DESC, id DESC
        """)
        for th_id, ev_date, ev_type, desc, delta, after in cur.fetchall():
            d = f"{float(delta):+.3f}" if delta else "N/A"
            a = f"{float(after):.3f}" if after else "N/A"
            print(f"{ev_date} {th_id} [{ev_type}] δ={d} →{a} | {desc[:60]}")
        conn.close()
    else:
        run_monthly()
