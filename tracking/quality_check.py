"""
quality_check.py — DB 기반 데이터 품질 자동 진단 시스템
========================================================
TC/SD/Watch/Prediction/TH 파이프라인 전체의 데이터 정합성을 검증.
JSON 파일 + DB 양쪽을 교차 점검.

사용법:
  python quality_check.py                # 전체 진단
  python quality_check.py --category tc  # TC 카드만
  python quality_check.py --fix          # 자동 수정 가능한 항목 수정
  python quality_check.py --json         # JSON 형식 출력
  python quality_check.py --summary      # 요약만

카테고리:
  tc, sd, watch, pred, th, sync, chain, schema

설계 원칙:
  1. 진단은 READ-ONLY. --fix 플래그 없이는 수정 안 함.
  2. 심각도 3단계: CRITICAL / WARNING / INFO
  3. 각 진단 항목에 fix 가능 여부 표시.
  4. 결과는 DB (quality_diagnostics) + JSON + stdout 3중 기록.
"""

import json
import os
import sys
import argparse
from datetime import date, timedelta
from collections import defaultdict

import psycopg2
from psycopg2.extras import Json

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
CARDS_DIR = os.path.join(TRACKING, "cards")
SA_HISTORY_DIR = os.path.join(BASE, "Stereo Analyzer", "history")

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
# 진단 결과 수집기
# ============================================================
class DiagnosticResult:
    """진단 결과 한 건."""
    def __init__(self, category, check_id, severity, message, target=None, fixable=False, fix_action=None):
        self.category = category
        self.check_id = check_id
        self.severity = severity  # CRITICAL / WARNING / INFO
        self.message = message
        self.target = target      # TC-001, W-2026-03-28-UQ-010, etc.
        self.fixable = fixable
        self.fix_action = fix_action  # 자동 수정 SQL 또는 설명
        self.fixed = False

    def to_dict(self):
        return {
            "category": self.category,
            "check_id": self.check_id,
            "severity": self.severity,
            "message": self.message,
            "target": self.target,
            "fixable": self.fixable,
            "fixed": self.fixed,
        }

    def __repr__(self):
        icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(self.severity, "⚪")
        fix = " [fixable]" if self.fixable else ""
        fixed = " ✅" if self.fixed else ""
        target = f" ({self.target})" if self.target else ""
        return f"  {icon} [{self.check_id}]{target} {self.message}{fix}{fixed}"


class DiagnosticCollector:
    """진단 결과 모음."""
    def __init__(self):
        self.results = []

    def add(self, category, check_id, severity, message, **kwargs):
        self.results.append(DiagnosticResult(category, check_id, severity, message, **kwargs))

    def by_category(self):
        grouped = defaultdict(list)
        for r in self.results:
            grouped[r.category].append(r)
        return dict(grouped)

    def by_severity(self):
        grouped = defaultdict(list)
        for r in self.results:
            grouped[r.severity].append(r)
        return dict(grouped)

    def summary(self):
        counts = defaultdict(int)
        for r in self.results:
            counts[r.severity] += 1
        return dict(counts)

    def fixable(self):
        return [r for r in self.results if r.fixable and not r.fixed]

    def to_json(self):
        return json.dumps([r.to_dict() for r in self.results], ensure_ascii=False, indent=2)


# ============================================================
# 1. TC 카드 품질 진단
# ============================================================
def check_tc_cards(collector):
    """TC 카드 JSON 파일 + DB 정합성 점검."""
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(CARDS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")

        # TC-01: tc_id 필드 사용 여부
        if "tc_id" not in d and "id" in d:
            collector.add("tc", "TC-01", "CRITICAL",
                          f"구형 'id' 필드 사용. 'tc_id'로 마이그레이션 필요.",
                          target=tc_id, fixable=True,
                          fix_action=f"JSON: 'id' → 'tc_id' 변환")

        # TC-02: status 값
        status = d.get("status", "")
        if status not in ("active", "archived"):
            collector.add("tc", "TC-02", "CRITICAL",
                          f"status='{status}'. 'active' 또는 'archived'여야 함.",
                          target=tc_id, fixable=True,
                          fix_action=f"status → 'active'")

        # TC-03: pre_read 존재
        if not d.get("pre_read"):
            collector.add("tc", "TC-03", "WARNING",
                          "pre_read 객체 누락. Type/SCP/Urgency 필요.",
                          target=tc_id)

        # TC-04: 시나리오 구조 검증
        scenarios = d.get("scenarios", {})
        if not scenarios:
            collector.add("tc", "TC-04", "WARNING",
                          "scenarios 없음.",
                          target=tc_id)
        else:
            total_prob = 0
            for sk, sv in scenarios.items():
                if not isinstance(sv, dict):
                    continue

                # TC-04a: trigger 형식
                trig = sv.get("trigger")
                if trig is None:
                    collector.add("tc", "TC-04a", "WARNING",
                                  f"시나리오 {sk}: trigger 없음.",
                                  target=tc_id)
                elif isinstance(trig, str):
                    collector.add("tc", "TC-04a", "WARNING",
                                  f"시나리오 {sk}: trigger가 문자열. dict(condition 키) 권장.",
                                  target=tc_id, fixable=True)
                elif isinstance(trig, dict) and "condition" not in trig:
                    collector.add("tc", "TC-04a", "WARNING",
                                  f"시나리오 {sk}: trigger dict에 'condition' 키 없음.",
                                  target=tc_id)

                # TC-04b: KC 3-band + action
                kc = sv.get("kc", {})
                if not isinstance(kc, dict):
                    collector.add("tc", "TC-04b", "WARNING",
                                  f"시나리오 {sk}: kc 없음.",
                                  target=tc_id)
                else:
                    missing_bands = [b for b in ("watch", "alert", "hard") if b not in kc]
                    if missing_bands:
                        collector.add("tc", "TC-04b", "WARNING",
                                      f"시나리오 {sk}: KC 밴드 누락 {missing_bands}",
                                      target=tc_id)
                    if "action" not in kc:
                        collector.add("tc", "TC-04c", "WARNING",
                                      f"시나리오 {sk}: KC action 누락. 발동 시 행동 미정의.",
                                      target=tc_id)

                # TC-04d: 확률 파싱
                prob_str = sv.get("probability") or sv.get("prob", "0%")
                try:
                    prob = int(str(prob_str).replace("%", "").strip())
                    total_prob += prob
                except (ValueError, TypeError):
                    collector.add("tc", "TC-04d", "WARNING",
                                  f"시나리오 {sk}: 확률 파싱 실패 '{prob_str}'",
                                  target=tc_id)

            # TC-05: 확률 합계
            if total_prob > 0 and total_prob != 100:
                collector.add("tc", "TC-05", "CRITICAL",
                              f"시나리오 확률 합계 {total_prob}% (100% 아님)",
                              target=tc_id)

        # TC-06: heartbeat_thresholds 존재
        hb = d.get("heartbeat_thresholds")
        if hb is None:
            collector.add("tc", "TC-06", "WARNING",
                          "heartbeat_thresholds 없음. cycle1 자동 체크 불가.",
                          target=tc_id)

        # TC-07: tracking_indicators 존재
        if not d.get("tracking_indicators"):
            collector.add("tc", "TC-07", "INFO",
                          "tracking_indicators 없음.",
                          target=tc_id)

        # TC-08: cross_card_links 존재
        if not d.get("cross_card_links"):
            collector.add("tc", "TC-08", "INFO",
                          "cross_card_links 없음. 수렴 탐지에서 제외됨.",
                          target=tc_id)

        # TC-09: analysis_ids 존재
        if not d.get("analysis_ids"):
            collector.add("tc", "TC-09", "WARNING",
                          "analysis_ids 없음. SA 이력 연결 끊김.",
                          target=tc_id)

        # TC-10: close_condition 존재
        if not d.get("close_condition"):
            collector.add("tc", "TC-10", "INFO",
                          "close_condition 없음. 종료 기준 미정의.",
                          target=tc_id)

        # TC-11: tags 존재
        if not d.get("tags"):
            collector.add("tc", "TC-11", "INFO",
                          "tags 없음. 수렴 탐지 태그 매칭 불가.",
                          target=tc_id)

        # TC-12: check_log 또는 phase_log 이력
        has_history = d.get("phase_log") or d.get("check_log")
        if not has_history:
            collector.add("tc", "TC-12", "WARNING",
                          "phase_log/check_log 없음. 변경 이력 추적 불가.",
                          target=tc_id)


# ============================================================
# 2. SD 카드 품질 진단
# ============================================================
def check_sd_cards(collector):
    """SD 카드 수명 주기 점검."""
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("SD-") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(CARDS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            d = json.load(f)
        sd_id = d.get("sd_id") or d.get("id")

        # SD-01: 3회 이상 출현인데 미승격
        count = d.get("appearance_count", 0)
        status = d.get("status", "")
        if count >= 3 and status == "watching":
            collector.add("sd", "SD-01", "WARNING",
                          f"출현 {count}회인데 미승격. TC 승격 검토 필요.",
                          target=sd_id)

        # SD-02: next_check 경과
        next_check = d.get("next_check")
        if next_check:
            try:
                nc_date = date.fromisoformat(next_check)
                if nc_date < date.today():
                    days_overdue = (date.today() - nc_date).days
                    collector.add("sd", "SD-02", "WARNING",
                                  f"next_check {next_check} 경과 ({days_overdue}일 초과).",
                                  target=sd_id)
            except ValueError:
                pass

        # SD-03: last_seen 오래됨 (30일+)
        last_seen = d.get("last_seen")
        if last_seen:
            try:
                ls_date = date.fromisoformat(last_seen)
                stale_days = (date.today() - ls_date).days
                if stale_days > 30:
                    collector.add("sd", "SD-03", "INFO",
                                  f"last_seen {stale_days}일 전. 아카이브 검토.",
                                  target=sd_id)
            except ValueError:
                pass


# ============================================================
# 3. Watch 품질 진단
# ============================================================
def check_watches(collector):
    """Watch 수명 주기 + 연결 점검."""
    fpath = os.path.join(TRACKING, "active-watches.json")
    if not os.path.exists(fpath):
        collector.add("watch", "W-00", "WARNING", "active-watches.json 없음.")
        return

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    watches = data.get("watches", [])
    if not watches:
        collector.add("watch", "W-00", "INFO", "활성 Watch 0건.")
        return

    watch_ids = set()
    for w in watches:
        wid = w.get("id", "")
        watch_ids.add(wid)

        # W-01: 만기 경과
        schedule = w.get("schedule", {})
        next_check = schedule.get("next_check")
        if next_check and w.get("status") == "active":
            try:
                nc = date.fromisoformat(next_check)
                overdue = (date.today() - nc).days
                if overdue > 7:
                    collector.add("watch", "W-01", "WARNING",
                                  f"next_check {next_check} ({overdue}일 초과).",
                                  target=wid)
                elif overdue > 0:
                    collector.add("watch", "W-01", "INFO",
                                  f"next_check {next_check} ({overdue}일 경과).",
                                  target=wid)
            except ValueError:
                pass

        # W-02: close_condition 없음
        if not w.get("close_condition"):
            collector.add("watch", "W-02", "WARNING",
                          "close_condition 없음. 종료 기준 미정의.",
                          target=wid)

        # W-03: check_template 없음
        ct = w.get("check_template", {})
        if not ct.get("questions") and not ct.get("data_sources"):
            collector.add("watch", "W-03", "WARNING",
                          "check_template 비어있음. 체크 방법 미정의.",
                          target=wid)

        # W-04: resolved인데 closed_at 없음
        if w.get("status") == "resolved" and not w.get("closed_at"):
            collector.add("watch", "W-04", "WARNING",
                          "status=resolved인데 closed_at 없음.",
                          target=wid, fixable=True)

    # W-05: TC rm_watches가 실제 Watch와 매칭되는지
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")
        for rw in d.get("rm_watches", []):
            rm_id = rw if isinstance(rw, str) else rw.get("watch_id", "")
            if rm_id and rm_id not in watch_ids:
                # 짧은 ID 매칭 시도
                short_key = rm_id.replace("W-", "")
                matched = any(short_key in wid for wid in watch_ids)
                if not matched:
                    collector.add("watch", "W-05", "WARNING",
                                  f"TC의 rm_watches '{rm_id}'가 active-watches.json에 없음.",
                                  target=tc_id)


# ============================================================
# 4. Prediction 품질 진단
# ============================================================
def check_predictions(collector):
    """Prediction 수명 주기 점검."""
    fpath = os.path.join(TRACKING, "prediction-ledger.json")
    if not os.path.exists(fpath):
        collector.add("pred", "P-00", "WARNING", "prediction-ledger.json 없음.")
        return

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = data.get("predictions", [])
    tc_ids_in_cards = set()
    for fname in os.listdir(CARDS_DIR):
        if fname.startswith("TC-") and fname.endswith(".json"):
            with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
                d = json.load(f)
            tc_ids_in_cards.add(d.get("tc_id") or d.get("id"))

    for p in preds:
        pid = p.get("id", "")

        # P-01: deadline 경과 + open
        if p.get("status") == "open" and p.get("deadline"):
            try:
                dl = date.fromisoformat(p["deadline"])
                if dl < date.today():
                    overdue = (date.today() - dl).days
                    collector.add("pred", "P-01", "CRITICAL",
                                  f"deadline {p['deadline']} 경과 ({overdue}일). expired 처리 필요.",
                                  target=pid, fixable=True,
                                  fix_action="status → 'expired'")
            except ValueError:
                pass

        # P-02: hit/miss인데 lesson 없음
        if p.get("status") in ("hit", "miss", "partial") and not p.get("lesson"):
            collector.add("pred", "P-02", "WARNING",
                          f"status={p['status']}인데 lesson 없음. 학습 기록 필수.",
                          target=pid)

        # P-03: TC 존재 확인
        tc = p.get("tc", "")
        if tc and tc not in tc_ids_in_cards:
            collector.add("pred", "P-03", "WARNING",
                          f"tc='{tc}'가 TC 카드에 없음. 고아 Prediction.",
                          target=pid)

        # P-04: trigger 없음
        if not p.get("trigger"):
            collector.add("pred", "P-04", "WARNING",
                          "trigger 없음. 검증 불가능한 예측.",
                          target=pid)


# ============================================================
# 5. TH (Transition Hypothesis) 품질 진단
# ============================================================
def check_th(collector, conn):
    """TH 정합성 점검. DB-first이므로 DB에서 읽음."""
    cur = conn.cursor()

    # 테이블 존재 확인
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'th_cards'
        )
    """)
    if not cur.fetchone()[0]:
        collector.add("th", "TH-00", "CRITICAL",
                       "th_cards 테이블 없음. schema-v2-patch.sql 실행 필요.")
        return

    # TH-01: confidence 범위
    cur.execute("SELECT th_id, confidence FROM th_cards WHERE status = 'active'")
    for th_id, conf in cur.fetchall():
        c = float(conf) if conf else 0
        if c < 0 or c > 1:
            collector.add("th", "TH-01", "CRITICAL",
                          f"confidence={c} (0~1 범위 초과).",
                          target=th_id, fixable=True,
                          fix_action=f"UPDATE th_cards SET confidence = LEAST(1, GREATEST(0, confidence)) WHERE th_id = '{th_id}'")

    # TH-02: 멤버 없는 TH
    cur.execute("""
        SELECT th.th_id
        FROM th_cards th
        LEFT JOIN th_tc_links tl ON th.th_id = tl.th_id
        WHERE th.status = 'active'
        GROUP BY th.th_id
        HAVING count(tl.tc_id) = 0
    """)
    for (th_id,) in cur.fetchall():
        collector.add("th", "TH-02", "WARNING",
                       "수렴 멤버 0개. 근거 없는 TH.",
                       target=th_id)

    # TH-03: 멤버 TC가 실제 존재하는지
    cur.execute("""
        SELECT tl.th_id, tl.tc_id
        FROM th_tc_links tl
        LEFT JOIN tc_cards tc ON tl.tc_id = tc.tc_id
        WHERE tc.tc_id IS NULL
    """)
    for th_id, tc_id in cur.fetchall():
        collector.add("th", "TH-03", "CRITICAL",
                       f"멤버 '{tc_id}'가 tc_cards에 없음. 고아 링크.",
                       target=th_id, fixable=True,
                       fix_action=f"DELETE FROM th_tc_links WHERE th_id='{th_id}' AND tc_id='{tc_id}'")

    # TH-04: next_review 경과
    cur.execute("""
        SELECT th_id, next_review FROM th_cards
        WHERE status = 'active' AND next_review < CURRENT_DATE
    """)
    for th_id, nr in cur.fetchall():
        overdue = (date.today() - nr).days
        collector.add("th", "TH-04", "WARNING",
                       f"next_review {nr} 경과 ({overdue}일).",
                       target=th_id)

    # TH-05: 증거 체인 일관성 (confidence_after가 순서대로인지)
    cur.execute("""
        SELECT th_id FROM th_cards WHERE status = 'active'
    """)
    for (th_id,) in cur.fetchall():
        cur.execute("""
            SELECT ev_date, confidence_after
            FROM th_evidence
            WHERE th_id = %s AND confidence_after IS NOT NULL
            ORDER BY ev_date, id
        """, (th_id,))
        rows = cur.fetchall()
        if len(rows) >= 2:
            prev_after = float(rows[-1][1])
            cur.execute("SELECT confidence FROM th_cards WHERE th_id = %s", (th_id,))
            current = float(cur.fetchone()[0])
            if abs(prev_after - current) > 0.001:
                collector.add("th", "TH-05", "WARNING",
                              f"th_evidence 마지막 confidence_after({prev_after:.3f}) != th_cards.confidence({current:.3f}). 불일치.",
                              target=th_id, fixable=True,
                              fix_action=f"UPDATE th_cards SET confidence = {prev_after} WHERE th_id = '{th_id}'")


# ============================================================
# 6. JSON ↔ DB 동기화 점검
# ============================================================
def check_sync(collector, conn):
    """JSON 파일 ↔ DB row 수 정합성."""
    cur = conn.cursor()

    checks = [
        ("tc_cards", len([f for f in os.listdir(CARDS_DIR) if f.startswith("TC-") and f.endswith(".json")])),
        ("sd_cards", len([f for f in os.listdir(CARDS_DIR) if f.startswith("SD-") and f.endswith(".json")])),
    ]

    watches_path = os.path.join(TRACKING, "active-watches.json")
    if os.path.exists(watches_path):
        with open(watches_path, "r", encoding="utf-8") as f:
            checks.append(("watches", len(json.load(f).get("watches", []))))

    pred_path = os.path.join(TRACKING, "prediction-ledger.json")
    if os.path.exists(pred_path):
        with open(pred_path, "r", encoding="utf-8") as f:
            checks.append(("predictions", len(json.load(f).get("predictions", []))))

    if os.path.exists(SA_HISTORY_DIR):
        checks.append(("sa_history", len([f for f in os.listdir(SA_HISTORY_DIR) if f.endswith(".json")])))

    for table, file_count in checks:
        try:
            cur.execute(f"SELECT count(*) FROM {table}")
            db_count = cur.fetchone()[0]
            if db_count < file_count:
                collector.add("sync", "SYNC-01", "CRITICAL",
                              f"{table}: DB {db_count}건 < File {file_count}건. db_sync 필요.",
                              target=table, fixable=True,
                              fix_action=f"python db_sync.py --table {table[:2]}")
            elif db_count > file_count:
                collector.add("sync", "SYNC-02", "INFO",
                              f"{table}: DB {db_count}건 > File {file_count}건. DB에 추가 데이터 있음.",
                              target=table)
            else:
                collector.add("sync", "SYNC-OK", "INFO",
                              f"{table}: DB {db_count}건 = File {file_count}건.",
                              target=table)
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            collector.add("sync", "SYNC-03", "CRITICAL",
                          f"테이블 '{table}' 없음. DDL 실행 필요.",
                          target=table)


# ============================================================
# 7. 파이프라인 체인 정합성
# ============================================================
def check_chain(collector, conn):
    """SD→TC→Watch→Prediction→TH 체인 연결 점검."""
    cur = conn.cursor()

    # CHAIN-01: TC가 있는데 Prediction이 0건
    try:
        cur.execute("""
            SELECT tc.tc_id, tc.title, tc.phase
            FROM tc_cards tc
            LEFT JOIN predictions p ON p.tc_id = tc.tc_id
            WHERE tc.status = 'active' AND tc.phase >= 1
            GROUP BY tc.tc_id, tc.title, tc.phase
            HAVING count(p.pred_id) = 0
        """)
        for tc_id, title, phase in cur.fetchall():
            collector.add("chain", "CHAIN-01", "WARNING",
                          f"Phase {phase}인데 Prediction 0건. L7에서 예측 생성 필요.",
                          target=tc_id)
    except psycopg2.errors.UndefinedTable:
        conn.rollback()

    # CHAIN-02: Watch가 있는데 TC 연결 없음
    try:
        cur.execute("""
            SELECT w.watch_id, w.subject
            FROM watches w
            LEFT JOIN watch_tc_links wtl ON w.watch_id = wtl.watch_id
            WHERE w.status = 'active'
            GROUP BY w.watch_id, w.subject
            HAVING count(wtl.tc_id) = 0
        """)
        for wid, subject in cur.fetchall():
            collector.add("chain", "CHAIN-02", "INFO",
                          f"Watch에 TC 연결 없음. 고아 Watch.",
                          target=wid)
    except psycopg2.errors.UndefinedTable:
        conn.rollback()

    # CHAIN-03: TH 멤버 TC 중 archived된 것
    try:
        cur.execute("""
            SELECT tl.th_id, tl.tc_id, tc.status
            FROM th_tc_links tl
            JOIN tc_cards tc ON tl.tc_id = tc.tc_id
            JOIN th_cards th ON tl.th_id = th.th_id
            WHERE th.status = 'active' AND tc.status = 'archived'
        """)
        for th_id, tc_id, status in cur.fetchall():
            collector.add("chain", "CHAIN-03", "WARNING",
                          f"활성 TH의 멤버 '{tc_id}'가 archived. TH 재검토 필요.",
                          target=th_id)
    except psycopg2.errors.UndefinedTable:
        conn.rollback()

    # CHAIN-04: SD promoted_to가 실제 TC와 일치하는지
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("SD-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        sd_id = d.get("sd_id") or d.get("id")
        promoted_to = d.get("promoted_to")
        if promoted_to:
            tc_path = os.path.join(CARDS_DIR, f"{promoted_to}*.json")
            tc_files = [f for f in os.listdir(CARDS_DIR) if f.startswith(promoted_to)]
            if not tc_files:
                collector.add("chain", "CHAIN-04", "WARNING",
                              f"promoted_to='{promoted_to}'이지만 TC 카드 파일 없음.",
                              target=sd_id)


# ============================================================
# 8. DB 스키마 정합성
# ============================================================
def check_schema(collector, conn):
    """필수 테이블/뷰 존재 여부 + 누락 인덱스."""
    cur = conn.cursor()

    required_tables = [
        "tc_cards", "sd_cards", "watches", "predictions", "sa_history",
        "watch_tc_links", "tc_analysis_links", "learning_log",
        "th_cards", "th_tc_links", "th_evidence", "th_link_path",
        "tc_ont_links", "tc_metric_links",
        "tc_scenario_history",
        "quality_diagnostics",
        "ont_object", "ont_property", "ont_link", "ont_metric", "ont_threshold",
    ]

    required_views = [
        "v_dashboard", "v_watch_due", "v_prediction_hit_rate",
        "v_quality_trend", "v_tc_convergence",
        "v_transition_dashboard", "v_transition_path",
        "v_transition_timeline",
        "v_quality_summary",
    ]

    for table in required_tables:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s AND table_schema = 'public'
            )
        """, (table,))
        if not cur.fetchone()[0]:
            collector.add("schema", "SCH-01", "CRITICAL",
                          f"테이블 '{table}' 없음.",
                          target=table, fixable=True,
                          fix_action=f"schema-v2-patch.sql 실행")

    for view in required_views:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.views
                WHERE table_name = %s AND table_schema = 'public'
            )
        """, (view,))
        if not cur.fetchone()[0]:
            collector.add("schema", "SCH-02", "WARNING",
                          f"뷰 '{view}' 없음.",
                          target=view, fixable=True,
                          fix_action=f"schema-v2-patch.sql 실행")


# ============================================================
# 9. 자동 수정
# ============================================================
def apply_fixes(collector, conn):
    """fixable 항목 중 안전한 것만 자동 수정."""
    cur = conn.cursor()
    fixed = 0

    for r in collector.fixable():
        if r.check_id == "TC-02" and r.target:
            # status 정규화
            fpath = _find_tc_file(r.target)
            if fpath:
                with open(fpath, "r", encoding="utf-8") as f:
                    d = json.load(f)
                d["status"] = "active"
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
                r.fixed = True
                fixed += 1

        elif r.check_id == "P-01" and r.target:
            # expired 처리
            try:
                cur.execute("""
                    UPDATE predictions SET status = 'expired', outcome_date = CURRENT_DATE,
                    outcome = 'deadline 경과. quality_check 자동 만료.'
                    WHERE pred_id = %s AND status = 'open'
                """, (r.target,))
                if cur.rowcount > 0:
                    r.fixed = True
                    fixed += 1
            except Exception:
                conn.rollback()

        elif r.check_id == "TH-01" and r.fix_action:
            try:
                cur.execute(r.fix_action)
                r.fixed = True
                fixed += 1
            except Exception:
                conn.rollback()

        elif r.check_id == "TH-03" and r.fix_action:
            try:
                cur.execute(r.fix_action)
                r.fixed = True
                fixed += 1
            except Exception:
                conn.rollback()

        elif r.check_id == "TH-05" and r.fix_action:
            try:
                cur.execute(r.fix_action)
                r.fixed = True
                fixed += 1
            except Exception:
                conn.rollback()

    conn.commit()
    return fixed


def _find_tc_file(tc_id):
    """TC ID로 파일 경로 찾기."""
    for fname in os.listdir(CARDS_DIR):
        if fname.startswith(tc_id) and fname.endswith(".json"):
            return os.path.join(CARDS_DIR, fname)
    return None


# ============================================================
# 10. 결과 DB 저장
# ============================================================
def save_to_db(collector, conn):
    """진단 결과를 quality_diagnostics 테이블에 저장."""
    cur = conn.cursor()

    # 테이블 존재 확인
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'quality_diagnostics'
        )
    """)
    if not cur.fetchone()[0]:
        print("  ⚠️ quality_diagnostics 테이블 없음. 결과 저장 스킵.")
        return

    run_date = str(date.today())
    summary = collector.summary()

    cur.execute("""
        INSERT INTO quality_diagnostics (
            run_date, total_checks, critical_count, warning_count, info_count,
            details, fixed_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_date) DO UPDATE SET
            total_checks = EXCLUDED.total_checks,
            critical_count = EXCLUDED.critical_count,
            warning_count = EXCLUDED.warning_count,
            info_count = EXCLUDED.info_count,
            details = EXCLUDED.details,
            fixed_count = EXCLUDED.fixed_count
    """, (
        run_date,
        len(collector.results),
        summary.get("CRITICAL", 0),
        summary.get("WARNING", 0),
        summary.get("INFO", 0),
        Json([r.to_dict() for r in collector.results]),
        len([r for r in collector.results if r.fixed]),
    ))
    conn.commit()
    print(f"  quality_diagnostics 저장 완료 ({run_date})")


# ============================================================
# 11. 출력
# ============================================================
def print_report(collector, summary_only=False):
    """진단 보고서 출력."""
    s = collector.summary()
    total = len(collector.results)
    crit = s.get("CRITICAL", 0)
    warn = s.get("WARNING", 0)
    info = s.get("INFO", 0)

    print(f"\n━━ 데이터 품질 진단 결과 ({date.today()}) ━━")
    print(f"  전체: {total}건 | 🔴 CRITICAL: {crit} | 🟡 WARNING: {warn} | 🔵 INFO: {info}")

    fixable = collector.fixable()
    if fixable:
        print(f"  자동 수정 가능: {len(fixable)}건")

    fixed = [r for r in collector.results if r.fixed]
    if fixed:
        print(f"  자동 수정 완료: {len(fixed)}건")

    if summary_only:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return

    # 카테고리별 출력
    by_cat = collector.by_category()
    cat_names = {
        "tc": "TC 카드", "sd": "SD 카드", "watch": "Watch",
        "pred": "Prediction", "th": "TH 전이 가설",
        "sync": "JSON↔DB 동기화", "chain": "파이프라인 체인",
        "schema": "DB 스키마",
    }

    for cat in ["schema", "sync", "tc", "sd", "watch", "pred", "th", "chain"]:
        items = by_cat.get(cat, [])
        if not items:
            continue

        # CRITICAL/WARNING만 표시 (INFO는 --verbose에서)
        visible = [r for r in items if r.severity in ("CRITICAL", "WARNING")]
        info_count = len(items) - len(visible)

        name = cat_names.get(cat, cat)
        print(f"\n  ── {name} ({len(items)}건) ──")
        for r in visible:
            print(r)
        if info_count > 0:
            print(f"  🔵 INFO: {info_count}건 (생략)")

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ============================================================
# 메인
# ============================================================
CATEGORY_MAP = {
    "tc": check_tc_cards,
    "sd": check_sd_cards,
    "watch": check_watches,
    "pred": check_predictions,
}

DB_CATEGORY_MAP = {
    "th": check_th,
    "sync": check_sync,
    "chain": check_chain,
    "schema": check_schema,
}


def run_diagnostics(categories=None, do_fix=False, json_output=False, summary_only=False):
    """전체 진단 실행."""
    collector = DiagnosticCollector()

    # DB 연결
    conn = None
    try:
        conn = get_conn()
    except Exception as e:
        collector.add("schema", "DB-00", "CRITICAL", f"DB 연결 실패: {e}")
        print_report(collector, summary_only)
        return collector

    try:
        # 파일 기반 진단
        for cat, func in CATEGORY_MAP.items():
            if categories is None or cat in categories:
                func(collector)

        # DB 기반 진단
        for cat, func in DB_CATEGORY_MAP.items():
            if categories is None or cat in categories:
                func(collector, conn)

        # 자동 수정
        if do_fix:
            fixed = apply_fixes(collector, conn)
            print(f"\n  자동 수정: {fixed}건 처리")

        # 결과 저장
        save_to_db(collector, conn)

    except Exception as e:
        collector.add("schema", "RUN-ERR", "CRITICAL", f"진단 중 오류: {e}")
    finally:
        if conn:
            conn.close()

    # 출력
    if json_output:
        print(collector.to_json())
    else:
        print_report(collector, summary_only)

    return collector


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB 기반 데이터 품질 자동 진단")
    parser.add_argument("--category", choices=list(CATEGORY_MAP) + list(DB_CATEGORY_MAP),
                        help="특정 카테고리만 진단")
    parser.add_argument("--fix", action="store_true", help="자동 수정 가능한 항목 수정")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    parser.add_argument("--summary", action="store_true", help="요약만 출력")
    args = parser.parse_args()

    cats = [args.category] if args.category else None
    run_diagnostics(categories=cats, do_fix=args.fix, json_output=args.json, summary_only=args.summary)
