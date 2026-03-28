"""
cycle1_daily.py — 일일 Watch 체크 + Prediction 갱신 + 매크로 스냅샷 누적
=========================================================================
순환 루프 Cycle 1: Watch 만기 체크 → 정량 자동 판정 + 정성 알림 → Prediction 갱신
                  + daily_macro 시계열 누적 (매일 1행씩 INSERT)
                  + prediction 자동 검증 (정량 trigger 체크)

사용법:
  python cycle1_daily.py                # 오늘 만기 Watch 전체 처리 + 매크로 스냅샷
  python cycle1_daily.py --check-all    # 만기 무관 전체 Watch 체크
  python cycle1_daily.py --expire-only  # deadline 경과 Prediction만 만료 처리
  python cycle1_daily.py --status       # 현재 상태만 조회
  python cycle1_daily.py --macro-only   # daily_macro 스냅샷만 수집
  python cycle1_daily.py --verify       # prediction 자동 검증만 실행

데이터 질 원칙:
  정량 trigger (가격/지표) → MCP 자동 수집 → 자동 판정 → 수치 근거 기록
  정성 trigger (정책/공시) → 알림 생성 → 사용자가 맥락+판단+시사점 구조화 입력
  "1-click yes/no" 금지. lesson 1문장 이상 포함 필수.
"""

import json
import os
import sys
import re
import argparse
from datetime import date, datetime, timedelta

import psycopg2
from psycopg2.extras import Json

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
CARDS_DIR = os.path.join(TRACKING, "cards")

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
# 1. 만기 Watch 조회
# ============================================================
def get_due_watches(conn, check_all=False):
    """오늘 만기 Watch 목록 조회. check_all이면 전체 active Watch."""
    cur = conn.cursor()
    if check_all:
        cur.execute("""
            SELECT watch_id, subject, watch_type, schedule, check_template,
                   completed_checks, source_uq
            FROM watches WHERE status = 'active'
            ORDER BY watch_id
        """)
    else:
        cur.execute("""
            SELECT watch_id, subject, watch_type, schedule, check_template,
                   completed_checks, source_uq
            FROM watches WHERE status = 'active'
            AND (schedule->>'next_check')::date <= %s
            ORDER BY watch_id
        """, (str(date.today()),))

    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ============================================================
# 2. Watch 정량/정성 분류
# ============================================================
def classify_watch(watch):
    """Watch의 data_sources를 기반으로 정량/정성/혼합 분류.

    Returns:
        'QUANT': 가격 데이터만 (자동 판정 가능)
        'QUAL':  서사/정책/전문가만 (알림만, 사용자 판단)
        'MIXED': 혼합 (정량 부분만 자동, 나머지 알림)
    """
    sources = watch.get("check_template", {}).get("data_sources", [])
    has_quant = any(s.startswith("price:") for s in sources)
    has_qual = any(
        s.startswith(("narrative:", "expert:", "policy:", "positioning:", "data:"))
        for s in sources
    )

    if has_quant and not has_qual:
        return "QUANT"
    elif has_qual and not has_quant:
        return "QUAL"
    elif has_quant and has_qual:
        return "MIXED"
    return "QUAL"


def extract_price_symbols(watch):
    """Watch의 data_sources에서 price: 티커 추출.

    Returns:
        list of str: Yahoo Finance 티커 목록
    """
    sources = watch.get("check_template", {}).get("data_sources", [])
    symbols = []
    for s in sources:
        if s.startswith("price:"):
            ticker = s.replace("price:", "").strip()
            # 한국 종목코드 → Yahoo 형식
            if ticker.isdigit() and len(ticker) == 6:
                ticker = f"{ticker}.KS"
            symbols.append(ticker)
    return symbols


# ============================================================
# 3. 정량 heartbeat 체크 (TC 임계값 vs 현재가)
# ============================================================
def get_heartbeat_thresholds(conn):
    """전체 TC 카드의 heartbeat_thresholds + tracking_indicators를 수집.

    heartbeat_thresholds (정량 3-band) 우선 수집 후,
    tracking_indicators에서 symbol이 있고 heartbeat에 없는 항목을 추가 수집.

    Returns:
        dict: {symbol: [{tc_id, indicator, watch, alert, hard, direction}, ...]}
    """
    cur = conn.cursor()
    cur.execute("SELECT tc_id, tracking_indicators FROM tc_cards WHERE status = 'active'")

    thresholds = {}
    seen_keys = set()  # (tc_id, symbol) 중복 방지

    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")

        # 1차: heartbeat_thresholds (정량 3-band, 우선)
        for hb in d.get("heartbeat_thresholds", []):
            symbol = hb.get("symbol", "")
            if not symbol:
                continue
            if symbol not in thresholds:
                thresholds[symbol] = []
            thresholds[symbol].append({
                "tc_id": tc_id,
                "indicator": hb.get("indicator", ""),
                "watch": hb.get("watch"),
                "alert": hb.get("alert"),
                "hard": hb.get("hard"),
                "direction": hb.get("direction", "above"),
            })
            seen_keys.add((tc_id, symbol))

        # 2차: tracking_indicators에서 symbol이 있고 heartbeat에 없는 항목
        for ti in d.get("tracking_indicators", []):
            symbol = ti.get("symbol", "")
            if not symbol or (tc_id, symbol) in seen_keys:
                continue
            if symbol not in thresholds:
                thresholds[symbol] = []
            thresholds[symbol].append({
                "tc_id": tc_id,
                "indicator": ti.get("indicator", ""),
                "watch": ti.get("watch"),
                "alert": ti.get("alert"),
                "hard": ti.get("hard"),
                "direction": ti.get("direction", "above"),
                "threshold_text": ti.get("threshold", ""),
            })
            seen_keys.add((tc_id, symbol))

        # 3차: 시나리오별 KC에서 정량 임계값 추출 (heartbeat에 없는 것만)
        for sk, sv in d.get("scenarios", {}).items():
            if not isinstance(sv, dict):
                continue
            kc = sv.get("kc", {})
            if not isinstance(kc, dict):
                continue
            # kc.watch/alert/hard에 숫자가 있으면 정량 임계값으로 간주
            for band in ("watch", "alert", "hard"):
                val = kc.get(band, "")
                if isinstance(val, (int, float)):
                    # 시나리오 KC에 수치가 있으면 해당 시나리오의 indicator를 찾아 등록
                    # (tracking_indicators에서 매칭되는 symbol 활용)
                    pass  # 현재는 text 기반 KC가 대부분이므로 향후 확장

    return thresholds


def check_heartbeat_band(current_price, threshold, direction):
    """현재가가 어떤 밴드에 있는지 판정.

    Note: 3-Band 설계상 alert/hard는 N일 지속(duration) 후 발동이 원칙.
          현재는 snapshot 판정만 수행. duration 체크는 completed_checks 이력 기반으로
          연속 breach 일수를 카운트하여 판정해야 함 (TODO: duration 확장).

    Args:
        current_price: 현재 가격/수치 (None이면 판정 불가)
        threshold: {watch, alert, hard, direction} dict
        direction: 'above' (상향 돌파) or 'below' (하향 돌파)

    Returns:
        'normal', 'watch', 'alert', 'hard', 'unknown' (값 없을 때)
    """
    if current_price is None:
        return "unknown"

    watch_val = threshold.get("watch")
    alert_val = threshold.get("alert")
    hard_val = threshold.get("hard")

    # 수치형이 아닌 임계값은 판정 불가
    if not isinstance(watch_val, (int, float)):
        return "unknown"

    if direction == "above":
        if hard_val is not None and isinstance(hard_val, (int, float)) and current_price >= hard_val:
            return "hard"
        elif alert_val is not None and isinstance(alert_val, (int, float)) and current_price >= alert_val:
            return "alert"
        elif current_price >= watch_val:
            return "watch"
        return "normal"
    else:  # below
        if hard_val is not None and isinstance(hard_val, (int, float)) and current_price <= hard_val:
            return "hard"
        elif alert_val is not None and isinstance(alert_val, (int, float)) and current_price <= alert_val:
            return "alert"
        elif current_price <= watch_val:
            return "watch"
        return "normal"


# ============================================================
# 4. Prediction 만료 처리
# ============================================================
def expire_overdue_predictions(conn):
    """deadline 경과 + status=open인 Prediction을 expired로 전환."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE predictions
        SET status = 'expired',
            outcome_date = CURRENT_DATE,
            outcome = 'deadline 경과. trigger 미충족 상태에서 만료.'
        WHERE status = 'open' AND deadline < %s
        RETURNING pred_id, tc_id, claim
    """, (str(date.today()),))

    expired = cur.fetchall()
    conn.commit()

    if expired:
        print(f"\n  ⏰ 만료 처리: {len(expired)}건")
        for pred_id, tc_id, claim in expired:
            print(f"    {pred_id} ({tc_id}): {claim[:50]}")
    else:
        print("  ⏰ 만료 대상 없음")

    return len(expired)


# ============================================================
# 5. Watch → TC → Prediction 연결 조회
# ============================================================
def get_watch_prediction_chain(conn, watch_id):
    """Watch → TC → Prediction 체인 조회.

    Returns:
        list of dict: [{tc_id, pred_id, claim, scenario, probability, trigger_condition, status}, ...]
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT wtl.tc_id, p.pred_id, p.claim, p.scenario,
               p.probability, p.trigger_condition, p.status
        FROM watch_tc_links wtl
        JOIN predictions p ON p.tc_id = wtl.tc_id
        WHERE wtl.watch_id = %s AND p.status = 'open'
        ORDER BY wtl.tc_id, p.scenario
    """, (watch_id,))

    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ============================================================
# 6. 일일 체크 메인 로직
# ============================================================
def run_daily_check(check_all=False):
    """일일 Watch 체크 실행.

    Returns:
        dict: 실행 결과 요약
    """
    conn = get_conn()
    today = str(date.today())
    results = {
        "date": today,
        "watches_checked": 0,
        "quant_auto": 0,
        "qual_alerts": [],
        "predictions_expired": 0,
        "heartbeat_alerts": [],
    }

    try:
        print(f"━━ Cycle 1 Daily Check ({today}) ━━\n")

        # Step 1: 만기 Watch 조회
        watches = get_due_watches(conn, check_all)
        print(f"  만기 Watch: {len(watches)}건")

        if not watches:
            print("  체크 대상 없음.")
        else:
            for w in watches:
                wid = w["watch_id"]
                cat = classify_watch(w)
                symbols = extract_price_symbols(w)

                print(f"\n  [{cat:5}] {wid}")
                print(f"         {w['subject'][:60]}")

                if cat in ("QUANT", "MIXED") and symbols:
                    # 정량 부분: 티커 목록만 출력 (MCP 호출은 파이프라인에서)
                    print(f"         정량 티커: {symbols}")
                    results["quant_auto"] += 1

                if cat in ("QUAL", "MIXED"):
                    # 정성 부분: 알림 생성
                    chain = get_watch_prediction_chain(conn, wid)
                    alert = {
                        "watch_id": wid,
                        "subject": w["subject"],
                        "questions": w.get("check_template", {}).get("questions", []),
                        "data_sources": w.get("check_template", {}).get("data_sources", []),
                        "linked_predictions": [
                            {
                                "pred_id": p["pred_id"],
                                "tc_id": p["tc_id"],
                                "claim": p["claim"],
                                "scenario": p["scenario"],
                                "trigger": p["trigger_condition"],
                            }
                            for p in chain
                        ],
                    }
                    results["qual_alerts"].append(alert)

                    if chain:
                        print(f"         연결된 Prediction: {len(chain)}건")
                        for p in chain:
                            print(f"           {p['pred_id']} ({p['tc_id']}/{p['scenario']}): {p['trigger_condition'][:50]}")
                    else:
                        print("         연결된 Prediction: 없음")

                results["watches_checked"] += 1

        # Step 2: Heartbeat 임계값 현황 (정량 자동 체크용 기반 데이터)
        thresholds = get_heartbeat_thresholds(conn)
        if thresholds:
            print(f"\n  ━━ Heartbeat 임계값 모니터링 ({len(thresholds)}개 심볼) ━━")
            for symbol, ths in thresholds.items():
                for t in ths:
                    print(f"    {t['tc_id']} | {t['indicator']} ({symbol})")
                    print(f"      watch={t['watch']} alert={t['alert']} hard={t['hard']} ({t['direction']})")
                    results["heartbeat_alerts"].append({
                        "symbol": symbol,
                        "tc_id": t["tc_id"],
                        "indicator": t["indicator"],
                        "thresholds": {
                            "watch": t["watch"],
                            "alert": t["alert"],
                            "hard": t["hard"],
                        },
                        "direction": t["direction"],
                    })

        # Step 3: daily_macro 시계열 스냅샷
        print(f"\n  ━━ daily_macro 스냅샷 ━━")
        macro_count = collect_daily_macro_snapshot(conn)
        results["macro_indicators"] = macro_count

        # Step 4: 만료 처리
        results["predictions_expired"] = expire_overdue_predictions(conn)

        # Step 5: Prediction 자동 검증
        verify_results = verify_predictions_auto(conn)
        results["verify_candidates"] = len(verify_results)

        # Step 6: 정성 알림 요약 출력
        if results["qual_alerts"]:
            print(f"\n  ━━ 사용자 판정 필요 ({len(results['qual_alerts'])}건) ━━")
            for i, alert in enumerate(results["qual_alerts"], 1):
                print(f"\n  [{i}] {alert['watch_id']}")
                print(f"      질문: {alert['questions'][0] if alert['questions'] else alert['subject']}")
                if alert["linked_predictions"]:
                    for lp in alert["linked_predictions"]:
                        print(f"      → {lp['pred_id']} trigger: {lp['trigger'][:60]}")
                print(f"      판정 입력 필요: outcome + lesson + confidence_delta")

        # 최종 요약
        print(f"\n━━ 요약 ━━")
        print(f"  체크 완료: {results['watches_checked']}건")
        print(f"  정량 자동: {results['quant_auto']}건")
        print(f"  정성 알림: {len(results['qual_alerts'])}건")
        print(f"  매크로 스냅샷: {results.get('macro_indicators', 0)}개 지표")
        print(f"  만료 처리: {results['predictions_expired']}건")
        print(f"  검증 후보: {results.get('verify_candidates', 0)}건")
        print(f"  Heartbeat: {len(results['heartbeat_alerts'])}개 심볼 모니터링")
        print(f"━━━━━━━━━━━")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Cycle 1 실패: {e}")
        raise
    finally:
        conn.close()

    return results


# ============================================================
# 7. 사용자 판정 입력 (정성 trigger용)
# ============================================================
def record_outcome(pred_id, outcome, lesson, confidence_delta=None):
    """사용자가 판정한 Prediction outcome을 DB에 기록.

    Args:
        pred_id: 예측 ID (e.g., "PRED-20260326-001")
        outcome: "hit" | "miss" | "partial" | "expired"
        lesson: 시사점 1문장 이상 (필수)
        confidence_delta: TH confidence 변동값 (optional)
    """
    if not lesson or len(lesson) < 5:
        print("❌ lesson은 1문장 이상 필요합니다.")
        return False

    if outcome not in ("hit", "miss", "partial", "expired"):
        print(f"❌ outcome은 hit/miss/partial/expired 중 하나여야 합니다: {outcome}")
        return False

    conn = get_conn()
    cur = conn.cursor()

    try:
        # Prediction 갱신
        cur.execute("""
            UPDATE predictions
            SET status = %s, outcome = %s, outcome_date = %s, lesson = %s
            WHERE pred_id = %s AND status = 'open'
            RETURNING pred_id, tc_id
        """, (outcome, lesson, str(date.today()), lesson, pred_id))

        result = cur.fetchone()
        if not result:
            print(f"⚠️ {pred_id}: open 상태가 아니거나 존재하지 않음")
            return False

        pred_id_out, tc_id = result
        print(f"✅ {pred_id}: {outcome} 기록 완료 (TC: {tc_id})")

        # TH confidence 갱신 (연결된 TH가 있으면)
        if confidence_delta is not None and confidence_delta != 0:
            cur.execute("""
                SELECT th.th_id, th.confidence
                FROM th_cards th
                JOIN th_tc_links tl ON tl.th_id = th.th_id
                WHERE tl.tc_id = %s AND th.status = 'active'
            """, (tc_id,))

            for th_id, current_conf in cur.fetchall():
                new_conf = max(0, min(1, float(current_conf) + confidence_delta))
                cur.execute("""
                    UPDATE th_cards SET confidence = %s WHERE th_id = %s
                """, (new_conf, th_id))

                # 증거 기록
                ev_type = "completion_met" if outcome == "hit" else "kill_met" if outcome == "miss" else "manual"
                cur.execute("""
                    INSERT INTO th_evidence (th_id, ev_date, ev_type, description,
                                            confidence_delta, confidence_after)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    th_id, str(date.today()), ev_type,
                    f"{pred_id} {outcome}: {lesson}",
                    confidence_delta, new_conf,
                ))
                print(f"  → TH {th_id} confidence: {current_conf:.3f} → {new_conf:.3f} (delta: {confidence_delta:+.3f})")

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ 기록 실패: {e}")
        return False
    finally:
        conn.close()


# ============================================================
# 8. daily_macro 시계열 누적 (매일 1행 INSERT)
# ============================================================

# macro 시스템 경로
MACRO_DIR = os.path.join(os.path.dirname(BASE), "macro")

# macro indicator ID → daily_macro 컬럼 매핑
_MACRO_FIELD_MAP = {
    "A1": "core_pce_yoy",
    "B1": "tips_10y_real", "B2": "dxy_index", "B3": "usd_jpy",
    "B4": "fed_balance_sheet", "B5": "hy_oas",
    "C1": "vix", "C2": "move_index", "C3": "yield_spread",
    "C4": "us_m2", "C5": "ism_pmi", "C6": "unemployment_rate",
    "C7": "brent_crude", "C8": "bei_10y", "C9": "usd_cny", "C10": "fed_funds_rate",
    "D2": "bank_reserves", "D3": "rrp_balance", "D4": "tga_balance",
    "D5": "fed_balance_sheet", "D6": "sofr_rate", "D8": "term_premium",
}
_TEXT_FIELD_MAP = {"D1": "sloos", "D10": "fed_watch", "A2": "china_credit"}
_PARSE_NUMERIC_MAP = {"D7": "fiscal_deficit_gdp", "D9": "cftc_jpy_net"}


def _load_macro_json():
    """macro 시스템의 최신 JSON을 탐색하여 로드."""
    candidates = [
        os.path.join(MACRO_DIR, "indicators"),
        MACRO_DIR,
    ]
    for cand in candidates:
        if not os.path.exists(cand):
            continue
        for fname in ["latest.json", "state.json", "macro_snapshot.json"]:
            fpath = os.path.join(cand, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f), fpath
    return None, None


def _extract_macro_values(macro_data):
    """macro JSON에서 daily_macro 컬럼 값을 추출."""
    values = {}
    for layer_key in ["layer_A", "layer_B", "layer_C", "layer_D"]:
        layer = macro_data.get(layer_key, {})
        for ind_key, ind_val in layer.items():
            if not isinstance(ind_val, dict):
                continue
            raw_val = ind_val.get("value")
            if raw_val is None:
                continue
            db_col = _MACRO_FIELD_MAP.get(ind_key)
            if db_col:
                try:
                    values[db_col] = float(raw_val)
                except (ValueError, TypeError):
                    pass
            text_col = _TEXT_FIELD_MAP.get(ind_key)
            if text_col:
                values[text_col] = str(raw_val)[:200]
            parse_col = _PARSE_NUMERIC_MAP.get(ind_key)
            if parse_col:
                try:
                    cleaned = str(raw_val).replace("%", "").replace(",", "").strip()
                    values[parse_col] = float(cleaned)
                except (ValueError, TypeError):
                    pass
    return values


def collect_daily_macro_snapshot(conn):
    """daily_macro에 오늘 날짜로 1행 INSERT/UPDATE.

    1차: macro/indicators/latest.json에서 데이터 추출
    2차: Stereo 분석(history/*.json)에서 최신 MCP 데이터 보충

    매일 실행 시 시계열이 자동 누적됨.
    """
    cur = conn.cursor()
    today = str(date.today())

    # Step 1: macro 시스템 데이터 로드
    macro_data, src = _load_macro_json()
    values = _extract_macro_values(macro_data) if macro_data else {}
    source = f"macro_bridge+{os.path.basename(src)}" if src else "cycle1_daily"

    # Step 2: Stereo history에서 최신 MCP 수치 보충 (macro에 없는 것만)
    history_dir = os.path.join(BASE, "Stereo Analyzer", "history")
    if os.path.exists(history_dir):
        # 오늘 날짜 파일에서 L2 facts 탐색
        today_files = sorted([
            f for f in os.listdir(history_dir)
            if f.startswith(today) and f.endswith(".json")
        ], reverse=True)

        stereo_map = {
            "VIX": "vix", "^VIX": "vix",
            "HY OAS": "hy_oas", "BAMLH0A0HYM2": "hy_oas",
            "MOVE": "move_index", "^MOVE": "move_index",
            "SOFR": "sofr_rate",
            "10Y": "us_10y_yield", "^TNX": "us_10y_yield",
            "BEI": "bei_10y", "T10YIE": "bei_10y",
            "Brent": "brent_crude", "BZ=F": "brent_crude",
            "Gold": "gold_price", "GC=F": "gold_price",
            "DXY": "dxy_index",
            "RRP": "rrp_balance", "RRPONTSYD": "rrp_balance",
            "10Y-2Y": "yield_spread", "T10Y2Y": "yield_spread",
            "EFFR": "fed_funds_rate",
        }

        for fname in today_files[:3]:  # 최신 3개만
            try:
                with open(os.path.join(history_dir, fname), "r", encoding="utf-8") as f:
                    sa = json.load(f)
                facts = []
                l2 = sa.get("layers", {}).get("L2", {})
                if isinstance(l2, dict):
                    facts = l2.get("facts", [])
                for fact in facts:
                    if not isinstance(fact, dict):
                        continue
                    fact_text = fact.get("fact", "")
                    confidence = fact.get("confidence", "")
                    if confidence != "green":
                        continue
                    # "VIX 31.05" 형태에서 숫자 추출
                    for key, col in stereo_map.items():
                        if col in values:
                            continue  # macro 데이터 우선
                        if key in fact_text:
                            nums = re.findall(r'[\d,]+\.?\d*', fact_text)
                            if nums:
                                try:
                                    val = float(nums[-1].replace(",", ""))
                                    if val > 0:
                                        values[col] = val
                                except ValueError:
                                    pass
                            break
            except (json.JSONDecodeError, KeyError):
                continue

    if not values:
        print("  daily_macro: 수집 가능한 데이터 없음")
        return 0

    # Step 3: INSERT/UPDATE
    cols = ["snapshot_date", "source"] + list(values.keys())
    vals = [today, source] + list(values.values())
    placeholders = ", ".join(["%s"] * len(vals))
    col_str = ", ".join(cols)

    try:
        cur.execute(f"""
            INSERT INTO daily_macro ({col_str})
            VALUES ({placeholders})
            ON CONFLICT (snapshot_date) DO UPDATE SET
                {', '.join(f'{c} = EXCLUDED.{c}' for c in values.keys())},
                source = EXCLUDED.source
        """, vals)
        conn.commit()
        print(f"  daily_macro: {today} 저장 ({len(values)}개 지표)")
        return len(values)
    except Exception as e:
        conn.rollback()
        print(f"  daily_macro: 저장 실패 — {e}")
        return 0


# ============================================================
# 9. Prediction 자동 검증 (정량 trigger 체크)
# ============================================================

def verify_predictions_auto(conn):
    """정량 trigger가 있는 open prediction을 자동 체크.

    heartbeat_thresholds의 현재 band와 prediction의 trigger를 비교.
    trigger 충족이 감지되면 사용자에게 검증 후보로 제시.

    자동 hit/miss 판정은 하지 않음 — 후보 제시 + 사용자 확인.
    """
    cur = conn.cursor()
    today = str(date.today())

    # 1. 만기 7일 이내 prediction 조회
    cur.execute("""
        SELECT pred_id, tc_id, claim, scenario, probability,
               trigger_condition, deadline
        FROM predictions
        WHERE status = 'open'
        AND deadline <= %s
        ORDER BY deadline
    """, (str(date.today() + timedelta(days=7)),))

    columns = [desc[0] for desc in cur.description]
    upcoming = [dict(zip(columns, row)) for row in cur.fetchall()]

    if not upcoming:
        print("  prediction 검증: 7일 이내 만기 없음")
        return []

    # 2. heartbeat 현재 상태와 대조
    thresholds = get_heartbeat_thresholds(conn)

    # 3. TC별 최신 시나리오 확률 조회
    cur.execute("""
        SELECT DISTINCT ON (tc_id, scenario) tc_id, scenario, probability, kc_status
        FROM tc_scenario_history
        ORDER BY tc_id, scenario, created_at DESC
    """)
    latest_scenarios = {}
    for tc_id, scenario, prob, kc in cur.fetchall():
        latest_scenarios[(tc_id, scenario)] = {"probability": prob, "kc_status": kc}

    # 4. 검증 후보 생성
    verify_candidates = []
    for pred in upcoming:
        tc_id = pred["tc_id"]
        scenario = pred["scenario"]
        deadline = pred["deadline"]
        days_left = (deadline - date.today()).days if deadline else 999

        # 시나리오 현재 상태
        sc_info = latest_scenarios.get((tc_id, scenario), {})
        kc_status = sc_info.get("kc_status", "unknown")

        # 판정 근거 수집
        evidence = []
        if kc_status in ("watch", "alert", "hard"):
            evidence.append(f"KC band: {kc_status}")
        if days_left <= 3:
            evidence.append(f"만기 {days_left}일 남음")

        # heartbeat에서 해당 TC의 돌파 여부 확인
        for symbol, ths in thresholds.items():
            for t in ths:
                if t["tc_id"] == tc_id:
                    evidence.append(f"{t['indicator']}({symbol}) 모니터링 중")

        if evidence:
            verify_candidates.append({
                "pred_id": pred["pred_id"],
                "tc_id": tc_id,
                "scenario": scenario,
                "claim": pred["claim"],
                "deadline": str(deadline),
                "days_left": days_left,
                "kc_status": kc_status,
                "evidence": evidence,
                "action": "사용자 확인 필요: record_outcome(pred_id, outcome, lesson)"
            })

    # 5. 결과 출력
    if verify_candidates:
        print(f"\n  ━━ Prediction 검증 후보 ({len(verify_candidates)}건) ━━")
        for i, vc in enumerate(verify_candidates, 1):
            print(f"\n  [{i}] {vc['pred_id']} ({vc['tc_id']}/{vc['scenario']})")
            print(f"      claim: {vc['claim'][:70]}")
            print(f"      deadline: {vc['deadline']} ({vc['days_left']}일 남음)")
            print(f"      kc_status: {vc['kc_status']}")
            print(f"      근거: {', '.join(vc['evidence'])}")
            print(f"      → record_outcome('{vc['pred_id']}', 'hit|miss|partial', 'lesson')")
    else:
        print("  prediction 검증: 검증 후보 없음")

    return verify_candidates


# ============================================================
# 10. 현재 상태 조회
# ============================================================
def show_status():
    """현재 순환 루프 상태 요약."""
    conn = get_conn()
    cur = conn.cursor()

    print("━━ 순환 루프 현황 ━━\n")

    # Predictions 상태
    cur.execute("""
        SELECT status, count(*) FROM predictions GROUP BY status ORDER BY status
    """)
    print("  Predictions:")
    for status, cnt in cur.fetchall():
        print(f"    {status}: {cnt}건")

    # 다음 만기 Watch
    cur.execute("""
        SELECT count(*), min((schedule->>'next_check')::date)
        FROM watches
        WHERE status = 'active'
        AND (schedule->>'next_check')::date <= CURRENT_DATE
    """)
    due_count, earliest = cur.fetchone()
    print(f"\n  오늘 만기 Watch: {due_count}건 (최근: {earliest})")

    # TH 상태
    cur.execute("""
        SELECT th_id, hypothesis, confidence,
               (SELECT count(*) FROM th_evidence WHERE th_evidence.th_id = th_cards.th_id) as ev_count
        FROM th_cards WHERE status = 'active'
    """)
    print("\n  전이 가설:")
    for th_id, hyp, conf, ev_count in cur.fetchall():
        print(f"    {th_id} (confidence: {conf:.3f}, 증거: {ev_count}건)")
        print(f"      {hyp[:60]}")

    # Watch-TC-Prediction 체인 통계
    cur.execute("SELECT count(*) FROM watch_tc_links")
    link_count = cur.fetchone()[0]
    print(f"\n  Watch↔TC 연결: {link_count}건")

    # Heartbeat 모니터링 심볼 수
    thresholds = get_heartbeat_thresholds(conn)
    print(f"  Heartbeat 모니터링: {len(thresholds)}개 심볼")

    print("\n━━━━━━━━━━━━━━━━━━")
    conn.close()


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cycle 1: Daily Watch Check")
    parser.add_argument("--check-all", action="store_true",
                        help="만기 무관 전체 Watch 체크")
    parser.add_argument("--expire-only", action="store_true",
                        help="deadline 경과 Prediction만 만료 처리")
    parser.add_argument("--status", action="store_true",
                        help="현재 상태만 조회")
    parser.add_argument("--record", nargs=3, metavar=("PRED_ID", "OUTCOME", "LESSON"),
                        help="판정 입력: PRED_ID hit|miss|partial 'lesson'")
    parser.add_argument("--delta", type=float, default=None,
                        help="--record와 함께 사용: TH confidence_delta")
    parser.add_argument("--macro-only", action="store_true",
                        help="daily_macro 스냅샷만 수집")
    parser.add_argument("--verify", action="store_true",
                        help="prediction 자동 검증만 실행")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.expire_only:
        conn = get_conn()
        expire_overdue_predictions(conn)
        conn.close()
    elif args.record:
        pred_id, outcome, lesson = args.record
        record_outcome(pred_id, outcome, lesson, args.delta)
    elif args.macro_only:
        conn = get_conn()
        collect_daily_macro_snapshot(conn)
        conn.close()
    elif args.verify:
        conn = get_conn()
        verify_predictions_auto(conn)
        conn.close()
    else:
        run_daily_check(check_all=args.check_all)
