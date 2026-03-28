"""
db_sync.py — JSON → PostgreSQL 동기화 모듈
==========================================
각 시스템이 JSON 저장 직후 호출. tracking/ 파일 → DB upsert.

사용법:
  python db_sync.py                  # 전체 flush
  python db_sync.py --table tc       # TC 카드만
  python db_sync.py --table watches  # Watches만
  python db_sync.py --table pred     # Predictions만
  python db_sync.py --table sa       # SA History만
  python db_sync.py --table sd       # SD 카드만
  python db_sync.py --dry-run        # 연결 테스트만

Claude Code에서 호출:
  Bash: python "C:/.../tracking/db_sync.py" --table tc
  또는 from db_sync import flush_all; flush_all(["tc"])
"""

import json
import os
import sys
import argparse
from datetime import date

import psycopg2
from psycopg2.extras import Json

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
CARDS_DIR = os.path.join(TRACKING, "cards")
SA_HISTORY_DIR = os.path.join(BASE, "Stereo Analyzer", "history")

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
# TC Cards
# ============================================================
def _validate_scenario_probabilities(tc_id, scenarios):
    """시나리오 확률 합계를 검증. 100%가 아니면 경고 출력."""
    total = 0
    for sk, sv in scenarios.items():
        if not isinstance(sv, dict):
            continue
        prob_str = sv.get("probability") or sv.get("prob", "0%")
        try:
            prob = int(str(prob_str).replace("%", "").strip())
            total += prob
        except (ValueError, TypeError):
            pass
    if total > 0 and total != 100:
        print(f"  ⚠️ {tc_id}: 시나리오 확률 합계 {total}% (100% 아님)")


def _normalize_tc(d):
    """구형/신형 TC JSON을 DB 컬럼에 맞게 정규화.

    구형: id, status=tracking, trigger/kc 객체, check_log, scp, heartbeat_thresholds
    신형: tc_id, status=active, pre_read, phase_log, tracking_indicators, cross_card_links
    """
    tc_id = d.get("tc_id") or d.get("id")

    # status 정규화 (DB CHECK: active / archived)
    raw_status = d.get("status", "active")
    status = "active" if raw_status in ("active", "tracking") else "archived"

    # updated: 신형은 있고, 구형은 check_log 마지막 날짜 또는 created
    updated = d.get("updated")
    if not updated:
        check_log = d.get("check_log", [])
        if check_log:
            updated = check_log[-1].get("date", d.get("created", str(date.today())))
        else:
            updated = d.get("created", str(date.today()))

    # issue_summary: 신형은 있고, 구형은 trigger.condition으로 생성
    issue_summary = d.get("issue_summary", "")
    if not issue_summary:
        trigger = d.get("trigger", {})
        if isinstance(trigger, dict):
            issue_summary = trigger.get("condition", d.get("title", ""))

    # pre_read: 신형은 있고, 구형은 scp/type에서 구성
    pre_read = d.get("pre_read", {})
    if not pre_read:
        pre_read = {}
        if d.get("scp") is not None:
            pre_read["scp"] = d["scp"]
        if d.get("type"):
            pre_read["type"] = d["type"]

    # tracking_indicators: 신형은 있고, 구형은 heartbeat_thresholds에서 변환
    tracking_indicators = d.get("tracking_indicators")
    if not tracking_indicators and d.get("heartbeat_thresholds"):
        tracking_indicators = d["heartbeat_thresholds"]

    # phase_log: 신형은 있고, 구형은 check_log에서 변환
    phase_log = d.get("phase_log")
    if not phase_log and d.get("check_log"):
        phase_log = d["check_log"]

    # rm_watches: 양쪽 다 있지만 형식이 다를 수 있음 (배열 vs 객체 배열)
    rm_watches = d.get("rm_watches")

    # cross_card_links
    cross_card_links = d.get("cross_card_links")

    # tags: 구형에는 없을 수 있음
    tags = d.get("tags")

    # scenarios 확률 합계 검증
    scenarios = d.get("scenarios", {})
    _validate_scenario_probabilities(tc_id, scenarios)

    return {
        "tc_id": tc_id,
        "title": d.get("title", ""),
        "created": d.get("created", str(date.today())),
        "updated": updated,
        "status": status,
        "phase": d.get("phase", 1),
        "issue_summary": issue_summary,
        "pre_read": pre_read,
        "scenarios": scenarios,
        "tracking_indicators": tracking_indicators,
        "phase_log": phase_log,
        "rm_watches": rm_watches,
        "cross_card_links": cross_card_links,
        "source": d.get("source"),
        "close_condition": d.get("close_condition"),
        "tags": tags,
        "analysis_ids": d.get("analysis_ids", []),
    }


def sync_tc_cards(conn):
    """tracking/cards/TC-*.json → tc_cards + tc_analysis_links"""
    cur = conn.cursor()
    count = 0

    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(CARDS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)

        r = _normalize_tc(d)
        cur.execute("""
            INSERT INTO tc_cards (
                tc_id, title, created, updated, status, phase,
                issue_summary, pre_read, scenarios,
                tracking_indicators, phase_log, rm_watches,
                cross_card_links, source, close_condition, tags
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (tc_id) DO UPDATE SET
                title = EXCLUDED.title,
                updated = EXCLUDED.updated,
                status = EXCLUDED.status,
                phase = EXCLUDED.phase,
                issue_summary = EXCLUDED.issue_summary,
                pre_read = EXCLUDED.pre_read,
                scenarios = EXCLUDED.scenarios,
                tracking_indicators = EXCLUDED.tracking_indicators,
                phase_log = EXCLUDED.phase_log,
                rm_watches = EXCLUDED.rm_watches,
                cross_card_links = EXCLUDED.cross_card_links,
                source = EXCLUDED.source,
                close_condition = EXCLUDED.close_condition,
                tags = EXCLUDED.tags
        """, (
            r["tc_id"],
            r["title"],
            r["created"],
            r["updated"],
            r["status"],
            r["phase"],
            r["issue_summary"],
            Json(r["pre_read"]),
            Json(r["scenarios"]),
            Json(r["tracking_indicators"]),
            Json(r["phase_log"]),
            Json(r["rm_watches"]),
            Json(r["cross_card_links"]),
            r["source"],
            r["close_condition"],
            r["tags"],
        ))
        count += 1

        # tc_analysis_links
        for sa_id in r["analysis_ids"]:
            cur.execute("""
                INSERT INTO tc_analysis_links (tc_id, analysis_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (r["tc_id"], sa_id))

    conn.commit()
    print(f"  tc_cards: {count}건 upsert")
    return count


# ============================================================
# SD Cards
# ============================================================
def sync_sd_cards(conn):
    """tracking/cards/SD-*.json → sd_cards"""
    cur = conn.cursor()
    count = 0

    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("SD-") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(CARDS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)

        sd_id = d.get("sd_id") or d.get("id")
        cur.execute("""
            INSERT INTO sd_cards (
                sd_id, title, created, status, appearance_count,
                last_seen, source, next_check, note,
                close_condition, promoted_to
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sd_id) DO UPDATE SET
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                appearance_count = EXCLUDED.appearance_count,
                last_seen = EXCLUDED.last_seen,
                source = EXCLUDED.source,
                next_check = EXCLUDED.next_check,
                note = EXCLUDED.note,
                close_condition = EXCLUDED.close_condition,
                promoted_to = EXCLUDED.promoted_to
        """, (
            sd_id,
            d.get("title", ""),
            d.get("created", str(date.today())),
            d.get("status", "watching"),
            d.get("appearance_count", 1),
            d.get("last_seen", str(date.today())),
            d.get("source"),
            d.get("next_check"),
            d.get("note"),
            d.get("close_condition"),
            d.get("promoted_to"),
        ))
        count += 1

    conn.commit()
    print(f"  sd_cards: {count}건 upsert")
    return count


# ============================================================
# Watches
# ============================================================
def sync_watches(conn):
    """tracking/active-watches.json → watches"""
    cur = conn.cursor()
    fpath = os.path.join(TRACKING, "active-watches.json")
    if not os.path.exists(fpath):
        print("  watches: active-watches.json 없음 — 스킵")
        return 0

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # status 정규화 맵 (DB CHECK: active/resolved/expired)
    WATCH_STATUS_MAP = {
        "active": "active",
        "resolved": "resolved",
        "expired": "expired",
        "closed": "resolved",      # closed → resolved
        "completed": "resolved",   # completed → resolved
    }

    count = 0
    for w in data.get("watches", []):
        raw_status = w.get("status", "active")
        db_status = WATCH_STATUS_MAP.get(raw_status, "active")

        cur.execute("""
            INSERT INTO watches (
                watch_id, created, subject, watch_type, status,
                schedule, original_context, check_template,
                close_condition, source_report, source_uq,
                completed_checks, closed_at, close_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (watch_id) DO UPDATE SET
                subject = EXCLUDED.subject,
                status = EXCLUDED.status,
                schedule = EXCLUDED.schedule,
                completed_checks = EXCLUDED.completed_checks,
                closed_at = EXCLUDED.closed_at,
                close_reason = EXCLUDED.close_reason
        """, (
            w["id"],
            w["created"],
            w["subject"],
            w["type"],
            db_status,
            Json(w["schedule"]),
            Json(w["original_context"]),
            Json(w["check_template"]),
            w.get("close_condition"),
            w.get("source_report"),
            w.get("source_uq"),
            Json(w.get("completed_checks", [])),
            w.get("closed_at"),
            w.get("close_reason"),
        ))
        count += 1

    conn.commit()
    print(f"  watches: {count}건 upsert")
    return count


# ============================================================
# Predictions
# ============================================================
def sync_predictions(conn):
    """tracking/prediction-ledger.json → predictions"""
    cur = conn.cursor()
    fpath = os.path.join(TRACKING, "prediction-ledger.json")
    if not os.path.exists(fpath):
        print("  predictions: prediction-ledger.json 없음 — 스킵")
        return 0

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for p in data.get("predictions", []):
        cur.execute("""
            INSERT INTO predictions (
                pred_id, source_analysis, pred_date, tc_id,
                pred_type, claim, scenario, probability,
                trigger_condition, deadline, status,
                outcome, outcome_date, lesson
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pred_id) DO UPDATE SET
                status = EXCLUDED.status,
                outcome = EXCLUDED.outcome,
                outcome_date = EXCLUDED.outcome_date,
                lesson = EXCLUDED.lesson
        """, (
            p["id"],
            p["source"],
            p["date"],
            p.get("tc"),
            p["type"],
            p["claim"],
            p["scenario"],
            p["probability"],
            p["trigger"],
            p["deadline"],
            p["status"],
            p.get("outcome"),
            p.get("outcome_date"),
            p.get("lesson"),
        ))
        count += 1

    conn.commit()
    print(f"  predictions: {count}건 upsert")
    return count


# ============================================================
# SA History
# ============================================================
def _to_jsonb(val):
    """dict/list → Json 래퍼. None이면 None. 이미 문자열이면 그대로."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return Json(val)
    return Json(val)


def sync_sa_history(conn):
    """Stereo Analyzer/history/*.json → sa_history

    SA ID 중복 처리:
      - 같은 파일이 DB에 이미 있으면 → UPDATE (ON CONFLICT)
      - 다른 파일이 같은 ID를 쓰면 → 재번호 (010, 011, ...)
    파일별 고유 키: (sa_id + filename)으로 추적.
    """
    cur = conn.cursor()

    if not os.path.exists(SA_HISTORY_DIR):
        print("  sa_history: history/ 디렉토리 없음 — 스킵")
        return 0

    files = sorted(os.listdir(SA_HISTORY_DIR))

    # 1단계: 모든 파일의 원본 ID를 수집하고 충돌 감지
    file_entries = []  # (fname, raw_data, original_id)
    for fname in files:
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(SA_HISTORY_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)
        sa_id = d.get("id", "")
        if sa_id:
            file_entries.append((fname, d, sa_id))

    # 2단계: 중복 ID 재번호 — 파일 간 충돌만 처리 (DB 기존 데이터는 UPDATE)
    assigned_ids = {}  # sa_id → fname (선점)
    final_entries = []  # (fname, raw_data, final_sa_id)

    for fname, d, original_id in file_entries:
        sa_id = original_id
        if sa_id in assigned_ids and assigned_ids[sa_id] != fname:
            # 같은 ID를 다른 파일이 이미 선점 → 재번호
            base = sa_id.rsplit("-", 1)[0]
            for i in range(10, 100):
                candidate = f"{base}-{i:03d}"
                if candidate not in assigned_ids:
                    sa_id = candidate
                    print(f"    재번호: {original_id} → {sa_id} ({fname})")
                    break
        assigned_ids[sa_id] = fname
        final_entries.append((fname, d, sa_id))

    # 3단계: DB upsert
    count = 0
    for fname, d, sa_id in final_entries:
        title = (
            d.get("input", {}).get("title", "")
            or d.get("title", "")
            or fname.replace(".json", "")
        )
        raw_pipeline = d.get("pipeline") or d.get("pipeline_mode")
        pipeline = raw_pipeline if isinstance(raw_pipeline, str) else json.dumps(raw_pipeline, ensure_ascii=False) if raw_pipeline else None
        core_finding = d.get("one_line") or d.get("core_finding")

        # Layer summary — 각 레이어의 1줄 요약 추출
        layers = d.get("layers", {})
        layer_summary = {}
        for lk, lv in layers.items():
            if isinstance(lv, dict):
                val = lv.get("one_line") or lv.get("summary")
                layer_summary[lk] = str(val)[:200] if val else str(lv)[:200]
            elif isinstance(lv, str):
                layer_summary[lk] = lv[:200]

        # Scenarios from L7
        scenarios = d.get("scenarios")
        if not scenarios:
            # L7 내부, cross_scenario, cross_analysis 등 다양한 위치에서 탐색
            for key in ("L7", "l7"):
                l7 = layers.get(key, {})
                if isinstance(l7, dict):
                    scenarios = l7.get("scenarios") or l7.get("investment_implications")
                    if scenarios:
                        break
        if not scenarios:
            scenarios = d.get("cross_scenario") or d.get("cross_analysis")

        uncertainty = d.get("uncertainty_map") or d.get("uncertainty")
        feedback = d.get("feedback") or d.get("feedback_loops")
        prior_context = d.get("prior_context") or d.get("gate_context") or d.get("phase0_gate")

        quality_score = d.get("quality_score")
        quality_detail = None  # JSONB: coverage, cross_verify, discovery_rate, freshness
        if quality_score is None:
            sc = d.get("self_check", {})
            if isinstance(sc, dict):
                quality_score = sc.get("quality_score")
        # quality_score가 dict면 구조 분해 저장 + 총점 추출
        if isinstance(quality_score, dict):
            quality_detail = {
                "coverage": quality_score.get("coverage"),
                "cross_verify": quality_score.get("cross_verify"),
                "discovery_rate": quality_score.get("discovery_rate"),
                "freshness": quality_score.get("freshness"),
                "note": quality_score.get("note"),
            }
            quality_score = quality_score.get("total") or quality_score.get("score") or quality_score.get("overall") or quality_score.get("quality_score")
        # 최종적으로 숫자가 아니면 None
        if quality_score is not None:
            try:
                quality_score = float(quality_score)
            except (ValueError, TypeError):
                quality_score = None

        raw_tags = d.get("tags") or None
        if isinstance(raw_tags, list):
            tags = [str(t) for t in raw_tags]
        else:
            tags = None

        raw_related = d.get("related_ids") or d.get("analysis_ids") or None
        if isinstance(raw_related, list):
            related_ids = [str(r) for r in raw_related]
        else:
            related_ids = None

        try:
            cur.execute("""
                INSERT INTO sa_history (
                    sa_id, sa_date, title, pipeline, pre_read,
                    core_finding, layer_summary, scenarios,
                    uncertainty, feedback, prior_context,
                    quality_score, quality_detail, tags, related_ids
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sa_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    pipeline = EXCLUDED.pipeline,
                    pre_read = EXCLUDED.pre_read,
                    core_finding = EXCLUDED.core_finding,
                    layer_summary = EXCLUDED.layer_summary,
                    scenarios = EXCLUDED.scenarios,
                    uncertainty = EXCLUDED.uncertainty,
                    feedback = EXCLUDED.feedback,
                    prior_context = EXCLUDED.prior_context,
                    quality_score = EXCLUDED.quality_score,
                    quality_detail = EXCLUDED.quality_detail,
                    tags = EXCLUDED.tags,
                    related_ids = EXCLUDED.related_ids
            """, (
                sa_id,
                d.get("date", str(date.today())),
                title,
                pipeline,
                _to_jsonb(d.get("pre_read") or d.get("phase0_gate", {}).get("gate3_context") or {}),
                core_finding if isinstance(core_finding, str) else json.dumps(core_finding, ensure_ascii=False) if core_finding else None,
                _to_jsonb(layer_summary or None),
                _to_jsonb(scenarios),
                _to_jsonb(uncertainty),
                _to_jsonb(feedback),
                _to_jsonb(prior_context),
                quality_score,
                _to_jsonb(quality_detail),
                tags,
                related_ids,
            ))
            count += 1
        except Exception as e:
            conn.rollback()
            print(f"    ⚠️ {sa_id} ({fname}): {e}")
            continue

    conn.commit()
    print(f"  sa_history: {count}건 upsert")
    return count


# ============================================================
# TC Scenario History (시나리오 확률 변화 이력)
# ============================================================
def record_scenario_snapshot(conn, tc_id, scenario, probability,
                              prev_probability, delta_reason,
                              source_analysis=None, trigger_distance=None,
                              kc_status="normal", snapshot_date=None):
    """TC 시나리오 확률 변화를 이력 테이블에 기록.

    Stereo가 TC를 갱신할 때마다 호출.
    delta_reason은 필수 (빈 문자열 금지).
    """
    if not delta_reason or len(delta_reason.strip()) < 3:
        print(f"  ⚠️ delta_reason 필수: {tc_id}/{scenario}")
        return False

    cur = conn.cursor()
    snap_date = snapshot_date or str(date.today())

    cur.execute("""
        INSERT INTO tc_scenario_history
            (tc_id, snapshot_date, scenario, probability, prev_probability,
             delta_reason, source_analysis, trigger_distance, kc_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tc_id, snapshot_date, scenario) DO UPDATE SET
            probability = EXCLUDED.probability,
            prev_probability = EXCLUDED.prev_probability,
            delta_reason = EXCLUDED.delta_reason,
            source_analysis = EXCLUDED.source_analysis,
            trigger_distance = EXCLUDED.trigger_distance,
            kc_status = EXCLUDED.kc_status
    """, (
        tc_id, snap_date, scenario, str(probability),
        str(prev_probability) if prev_probability else None,
        delta_reason, source_analysis, trigger_distance, kc_status,
    ))
    conn.commit()
    return True


def sync_scenario_history(conn):
    """tc_scenario_history 테이블 현재 상태 확인."""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM tc_scenario_history")
    count = cur.fetchone()[0]
    cur.execute("SELECT count(DISTINCT tc_id) FROM tc_scenario_history")
    tc_count = cur.fetchone()[0]
    print(f"  tc_scenario_history: DB {count}건 ({tc_count}개 TC)")
    return count


# ============================================================
# Watch-TC Links (TC rm_watches → watch_tc_links)
# ============================================================
def sync_watch_tc_links(conn):
    """TC 카드의 rm_watches를 파싱하여 watch_tc_links에 upsert"""
    cur = conn.cursor()

    # DB에 존재하는 watch_id 목록
    cur.execute("SELECT watch_id FROM watches")
    valid_watches = {row[0] for row in cur.fetchall()}

    count = 0
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(CARDS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)

        tc_id = d.get("tc_id") or d.get("id")
        rm_watches = d.get("rm_watches", [])
        if not isinstance(rm_watches, list):
            continue

        for w in rm_watches:
            # watch_id 추출 (문자열 or dict)
            if isinstance(w, str):
                wid = w
            elif isinstance(w, dict) and "watch_id" in w:
                wid = w["watch_id"]
            else:
                continue

            # 짧은 ID → 전체 ID 매칭 (W-UQ-030 → W-2026-03-26-UQ-030)
            matched_id = wid
            if wid not in valid_watches:
                short_key = wid.replace("W-", "")
                # 완전 suffix 매칭 우선 (UQ-030이 -UQ-030으로 끝나는 것)
                exact_suffix = [v for v in valid_watches if v.endswith(f"-{short_key}")]
                if len(exact_suffix) == 1:
                    matched_id = exact_suffix[0]
                elif exact_suffix:
                    # 복수 매칭 시 가장 최근 날짜 우선
                    matched_id = sorted(exact_suffix)[-1]
                else:
                    # fallback: 부분 포함 매칭
                    partial = [v for v in valid_watches if short_key in v]
                    if len(partial) == 1:
                        matched_id = partial[0]
                    elif partial:
                        matched_id = sorted(partial)[-1]
                        print(f"    ⚠️ Watch ID 부분 매칭: {wid} → {matched_id} (후보 {len(partial)}개)")
                    else:
                        continue

            cur.execute("""
                INSERT INTO watch_tc_links (watch_id, tc_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (matched_id, tc_id))
            count += 1

    conn.commit()
    print(f"  watch_tc_links: {count}건 upsert")
    return count


# ============================================================
# TH Cards (전이 가설)
# ============================================================
def sync_th_cards(conn):
    """th_cards 테이블 현재 상태 확인 (DB-first, 파일 동기화 아님)"""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM th_cards")
    count = cur.fetchone()[0]
    print(f"  th_cards: DB {count}건 (DB-first)")
    return count


def sync_th_evidence(conn):
    """th_evidence 테이블 현재 상태 확인"""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM th_evidence")
    count = cur.fetchone()[0]
    print(f"  th_evidence: DB {count}건 (DB-first)")
    return count


def sync_learning_log(conn):
    """learning_log 테이블 현재 상태 확인"""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM learning_log")
    count = cur.fetchone()[0]
    print(f"  learning_log: DB {count}건 (DB-first)")
    return count


# ============================================================
# Dashboard sync (JSON → DB count 대조)
def verify_counts(conn):
    """DB row count vs JSON file count 대조"""
    cur = conn.cursor()
    results = {}

    # DB counts
    for table in ["tc_cards", "sd_cards", "watches", "predictions", "sa_history",
                   "tc_scenario_history", "watch_tc_links",
                   "th_cards", "th_evidence", "learning_log"]:
        cur.execute(f"SELECT count(*) FROM {table}")
        results[table] = {"db": cur.fetchone()[0]}

    # File counts (JSON 소스가 있는 테이블만)
    tc_files = len([f for f in os.listdir(CARDS_DIR) if f.startswith("TC-")])
    sd_files = len([f for f in os.listdir(CARDS_DIR) if f.startswith("SD-")])
    results["tc_cards"]["file"] = tc_files
    results["sd_cards"]["file"] = sd_files

    watches_path = os.path.join(TRACKING, "active-watches.json")
    if os.path.exists(watches_path):
        with open(watches_path, "r", encoding="utf-8") as f:
            results["watches"]["file"] = len(json.load(f).get("watches", []))
    else:
        results["watches"]["file"] = 0

    pred_path = os.path.join(TRACKING, "prediction-ledger.json")
    if os.path.exists(pred_path):
        with open(pred_path, "r", encoding="utf-8") as f:
            results["predictions"]["file"] = len(json.load(f).get("predictions", []))
    else:
        results["predictions"]["file"] = 0

    sa_files = len([f for f in os.listdir(SA_HISTORY_DIR) if f.endswith(".json")])
    results["sa_history"]["file"] = sa_files

    # DB-first 테이블 (JSON 소스 없음, DB 건수만 표시)
    for t in ["tc_scenario_history", "watch_tc_links", "th_cards", "th_evidence", "learning_log"]:
        if t in results:
            results[t]["file"] = "-"

    print("\n━━ DB Sync 검증 ━━")
    all_ok = True
    for table, counts in results.items():
        if counts.get("file") == "-":
            print(f"  📊 {table}: DB {counts['db']}건 (DB-first)")
        else:
            match = "✅" if counts["db"] >= counts["file"] else "⚠️"
            if counts["db"] < counts["file"]:
                all_ok = False
            print(f"  {match} {table}: DB {counts['db']}건 / File {counts['file']}건")
    print("━━━━━━━━━━━━━━━━━")

    return all_ok


# ============================================================
# flush_all — 메인 진입점
# ============================================================
def flush_all(tables=None):
    """전체 또는 지정 테이블 DB flush.

    Args:
        tables: None이면 전체.
                ['tc', 'sd', 'watches', 'pred', 'sa', 'links', 'th', 'learn'] 중 선택.
    Returns:
        dict: 테이블별 upsert 건수
    """
    conn = get_conn()
    results = {}

    try:
        print("━━ DB Flush 시작 ━━")

        if tables is None or "tc" in tables:
            results["tc_cards"] = sync_tc_cards(conn)
        if tables is None or "sd" in tables:
            results["sd_cards"] = sync_sd_cards(conn)
        if tables is None or "watches" in tables:
            results["watches"] = sync_watches(conn)
        if tables is None or "pred" in tables:
            results["predictions"] = sync_predictions(conn)
        if tables is None or "sa" in tables:
            results["sa_history"] = sync_sa_history(conn)
        if tables is None or "history" in tables:
            results["tc_scenario_history"] = sync_scenario_history(conn)
        if tables is None or "links" in tables:
            results["watch_tc_links"] = sync_watch_tc_links(conn)
        if tables is None or "th" in tables:
            results["th_cards"] = sync_th_cards(conn)
            results["th_evidence"] = sync_th_evidence(conn)
        if tables is None or "learn" in tables:
            results["learning_log"] = sync_learning_log(conn)

        verify_counts(conn)
        print("\n✅ DB Flush 완료")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ DB Flush 실패: {e}")
        raise
    finally:
        conn.close()

    return results


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JSON → PostgreSQL flush")
    parser.add_argument("--table",
                        choices=["tc", "sd", "watches", "pred", "sa", "history", "links", "th", "learn"],
                        help="특정 테이블만 flush")
    parser.add_argument("--dry-run", action="store_true",
                        help="연결 테스트만 (flush 안 함)")
    args = parser.parse_args()

    if args.dry_run:
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT version()")
            print(f"✅ DB 연결 성공: {cur.fetchone()[0][:50]}")
            conn.close()
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
        sys.exit(0)

    tables = [args.table] if args.table else None
    flush_all(tables)
