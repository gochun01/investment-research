"""
ontology_bridge.py — 온톨로지 ↔ 추적 계층 브릿지 자동화
=======================================================
TC 카드의 텍스트 참조(psf_link, macro_ref, heartbeat)를 정규화하여
온톨로지 브릿지 테이블(tc_ont_links, tc_metric_links)을 채운다.
TH 인과 경로(th_link_path)를 생성한다.
ont_link 활성화 상태를 TC 카드 증거 기반으로 판정한다.

사용법:
  python ontology_bridge.py                # 전체 실행
  python ontology_bridge.py --bridge       # tc_ont_links + tc_metric_links만
  python ontology_bridge.py --activate     # ont_link 활성화 판정만
  python ontology_bridge.py --th-path      # th_link_path만
  python ontology_bridge.py --status       # 현황 조회
  python ontology_bridge.py --macro-sync   # macro JSON → daily_macro

설계 원칙:
  1. TC 카드 JSON이 진실의 원천. DB는 정규화된 그림자.
  2. 텍스트 파싱은 best-effort. 매칭 안 되면 경고 후 스킵.
  3. 멱등성: 여러 번 실행해도 동일 결과 (ON CONFLICT).
"""

import json
import os
import re
import sys
import argparse
from datetime import date
from collections import defaultdict

import psycopg2
from psycopg2.extras import Json

# ── 경로 ──
BASE = r"C:\Users\이미영\Downloads\에이전트\01-New project"
TRACKING = os.path.join(BASE, "tracking")
CARDS_DIR = os.path.join(TRACKING, "cards")
MACRO_DIR = os.path.join(BASE.replace("01-New project", ""), "에이전트", "macro")

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
# 1. TC → ont_link 매핑 (psf_link 파싱)
# ============================================================

# psf_link 텍스트에서 링크/속성 참조를 추출하는 패턴
LINK_PATTERN = re.compile(r'(L[1-8])\s*(활성|active|★|🔴|격화|재강화|방향전환)?', re.IGNORECASE)
PROPERTY_PATTERN = re.compile(r'(P[1-4]|S[1-5]|F[1-5])\s*(🔴|🟡|🟢|격화|완화|활성)?', re.IGNORECASE)


def parse_psf_link(psf_link_text):
    """psf_link 텍스트에서 ont_link/ont_property 참조 추출.

    예: "P3 🔴(격화), P5 🔴, L5 활성★(재강화), L3 활성★(BEI 방향전환)"
    → links: [('L5', 'trigger'), ('L3', 'impact')]
    → properties: [('P3', '격화'), ('P5', '')]
    """
    if not psf_link_text:
        return [], []

    links = []
    for m in LINK_PATTERN.finditer(psf_link_text):
        link_id = m.group(1)
        state = m.group(2) or ""
        # 활성/★ → trigger, 그 외 → context
        role = "trigger" if any(k in state for k in ("활성", "active", "★", "재강화")) else "context"
        links.append((link_id, role, state))

    properties = []
    for m in PROPERTY_PATTERN.finditer(psf_link_text):
        prop_id = m.group(1)
        state = m.group(2) or ""
        properties.append((prop_id, state))

    return links, properties


def parse_macro_ref(macro_ref_text):
    """macro_ref 텍스트에서 macro 지표 참조 추출.

    예: "C7 Brent $112.57, C8 BEI 2.34%"
    → [('C7', 'Brent'), ('C8', 'BEI')]
    """
    if not macro_ref_text:
        return []

    refs = []
    # 패턴: A1, B2, C7, D5 등
    for m in re.finditer(r'([A-D]\d+)\s*(\w+)?', macro_ref_text):
        macro_id = m.group(1)
        name = m.group(2) or ""
        refs.append((macro_id, name))
    return refs


# ============================================================
# 2. 브릿지 채우기
# ============================================================

# ont_link별 키워드 사전 — TC 텍스트에서 인과 체인을 추론할 때 사용
LINK_KEYWORDS = {
    "L1": ["정책", "Fed", "금리인상", "금리인하", "FOMC", "기준금리", "pivot", "hawkish", "dovish"],
    "L2": ["관세", "지정학", "제재", "301", "IEEPA", "통상", "전쟁", "충격"],
    "L3": ["인플레", "BEI", "PCE", "유가", "Brent", "에너지", "물가"],
    "L4": ["실질금리", "달러", "DXY", "유동성위축", "TIPS"],
    "L5": ["신용경색", "HY스프레드", "SOFR", "게이트", "OAS"],
    "L6": ["자금흐름", "포지션", "ETF", "MMF", "ISA", "배분"],
    "L7": ["VIX", "디레버리징", "역류", "패닉", "청산", "MOVE"],
    "L8": ["긴급유동성", "정책개입", "구제", "SOFR스파이크"],
}


def _collect_tc_text(d):
    """TC 카드의 모든 텍스트를 하나의 문자열로 수집."""
    parts = [
        d.get("title", ""),
        d.get("issue_summary", ""),
        d.get("psf_link") or "",
        d.get("macro_ref") or "",
        " ".join(t for t in (d.get("tags") or []) if t),
    ]
    for sk, sv in d.get("scenarios", {}).items():
        if not isinstance(sv, dict):
            continue
        trig = sv.get("trigger", {})
        if isinstance(trig, dict):
            parts.append(trig.get("condition", ""))
        elif isinstance(trig, str):
            parts.append(trig)
        kc = sv.get("kc", {})
        if isinstance(kc, dict):
            parts.append(kc.get("action", ""))
    for ccl in d.get("cross_card_links", []):
        parts.append(ccl.get("link", ""))
    return " ".join(parts)


def _infer_links_by_keywords(text_pool, valid_links, max_links=3):
    """TC 텍스트에서 키워드 매칭으로 ont_link를 추론.

    Returns:
        list of (link_id, role, note)
    """
    scored = []
    for link_id, keywords in LINK_KEYWORDS.items():
        if link_id not in valid_links:
            continue
        score = sum(1 for kw in keywords if kw in text_pool)
        if score >= 1:
            scored.append((link_id, score))
    scored.sort(key=lambda x: -x[1])

    results = []
    for link_id, score in scored[:max_links]:
        role = "trigger" if score >= 2 else "context"
        results.append((link_id, role, f"keyword_score={score}"))
    return results


def fill_tc_ont_links(conn):
    """TC 카드 → tc_ont_links 매핑.

    3단계:
      1) psf_link 텍스트 파싱 (명시적 참조)
      2) cross_card_links에서 L1~L8 참조 추출
      3) TC 전체 텍스트에서 키워드 추론 (1-2에서 매핑 안 된 TC용)
    """
    cur = conn.cursor()

    cur.execute("SELECT link_id FROM ont_link")
    valid_links = {row[0] for row in cur.fetchall()}

    count = 0
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")
        mapped_links = set()  # 이미 매핑된 (link_id, role)

        # --- 1단계: psf_link 파싱 (명시적) ---
        psf_link = d.get("psf_link", "") or ""
        links, _ = parse_psf_link(psf_link)
        for link_id, role, state in links:
            if link_id not in valid_links:
                continue
            cur.execute("""
                INSERT INTO tc_ont_links (tc_id, link_id, role, note)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tc_id, link_id, role) DO UPDATE SET note = EXCLUDED.note
            """, (tc_id, link_id, role, state or None))
            mapped_links.add((link_id, role))
            count += 1

        # --- 2단계: cross_card_links에서 L참조 추출 ---
        for ccl in d.get("cross_card_links", []):
            link_text = ccl.get("link", "")
            for m in LINK_PATTERN.finditer(link_text):
                link_id = m.group(1)
                if link_id in valid_links and (link_id, "impact") not in mapped_links:
                    cur.execute("""
                        INSERT INTO tc_ont_links (tc_id, link_id, role, note)
                        VALUES (%s, %s, 'impact', %s)
                        ON CONFLICT (tc_id, link_id, role) DO NOTHING
                    """, (tc_id, link_id, link_text[:100]))
                    mapped_links.add((link_id, "impact"))
                    count += 1

        # --- 3단계: 키워드 추론 (1-2에서 매핑이 0건인 TC) ---
        if not mapped_links:
            text_pool = _collect_tc_text(d)
            inferred = _infer_links_by_keywords(text_pool, valid_links)
            for link_id, role, note in inferred:
                cur.execute("""
                    INSERT INTO tc_ont_links (tc_id, link_id, role, note)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tc_id, link_id, role) DO UPDATE SET note = EXCLUDED.note
                """, (tc_id, link_id, role, note))
                count += 1

    conn.commit()
    print(f"  tc_ont_links: {count}건 upsert")
    return count


def fill_tc_metric_links(conn):
    """TC 카드의 heartbeat_thresholds를 파싱하여 tc_metric_links에 INSERT."""
    cur = conn.cursor()

    # symbol → metric_id 매핑
    cur.execute("SELECT metric_id, source_detail FROM ont_metric WHERE source_detail IS NOT NULL")
    symbol_to_metric = {}
    for metric_id, source_detail in cur.fetchall():
        if source_detail:
            symbol_to_metric[source_detail] = metric_id

    count = 0
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")

        for hb in d.get("heartbeat_thresholds", []):
            symbol = hb.get("symbol", "")
            if not symbol:
                continue

            metric_id = symbol_to_metric.get(symbol)
            if not metric_id:
                # Yahoo ticker는 ont_metric에 없을 수 있음 (KRW=X, 005380.KS 등)
                continue

            # 가장 가까운 band 결정 (watch가 기본)
            band = "watch"
            watch_val = hb.get("watch")
            direction = hb.get("direction", "above")

            cur.execute("""
                INSERT INTO tc_metric_links (tc_id, metric_id, band, threshold_value, threshold_direction, duration_days)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tc_id, metric_id) DO UPDATE SET
                    band = EXCLUDED.band,
                    threshold_value = EXCLUDED.threshold_value,
                    threshold_direction = EXCLUDED.threshold_direction
            """, (
                tc_id, metric_id, band,
                watch_val, direction, None,
            ))
            count += 1

    conn.commit()
    print(f"  tc_metric_links: {count}건 upsert")
    return count


# ============================================================
# 3. ont_link 활성화 판정
# ============================================================

def activate_ont_links(conn):
    """TC 카드의 psf_link 증거를 기반으로 ont_link is_active를 판정.

    규칙:
      - TC 카드에서 "L5 활성★" 등으로 참조되면 → is_active = true
      - 참조가 없으면 → is_active = false (유지)
      - 변경 시 ont_link_log에 이력 기록
    """
    cur = conn.cursor()

    # 현재 상태
    cur.execute("SELECT link_id, is_active FROM ont_link")
    current_state = {row[0]: row[1] for row in cur.fetchall()}

    # TC 카드에서 활성 증거 수집
    active_evidence = defaultdict(list)  # link_id → [tc_id, ...]

    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")
        if d.get("status") != "active":
            continue

        psf_link = d.get("psf_link", "")
        links, _ = parse_psf_link(psf_link)
        for link_id, role, state in links:
            if role == "trigger" or "활성" in state or "★" in state:
                active_evidence[link_id].append(tc_id)

    # 판정 + 갱신
    changed = 0
    for link_id, was_active in current_state.items():
        should_be_active = link_id in active_evidence
        if should_be_active != was_active:
            evidence_text = ", ".join(active_evidence.get(link_id, ["no TC evidence"]))
            cur.execute("""
                UPDATE ont_link
                SET is_active = %s,
                    activation_evidence = %s,
                    activated_at = CASE WHEN %s THEN now() ELSE activated_at END,
                    state_updated_at = now()
                WHERE link_id = %s
            """, (should_be_active, evidence_text, should_be_active, link_id))

            # 이력 기록
            cur.execute("""
                INSERT INTO ont_link_log (link_id, log_date, prev_active, new_active, evidence)
                VALUES (%s, CURRENT_DATE, %s, %s, %s)
            """, (link_id, was_active, should_be_active, evidence_text))

            changed += 1
            state_str = "활성화" if should_be_active else "비활성화"
            print(f"    {link_id}: {state_str} (증거: {evidence_text})")

    conn.commit()
    if changed == 0:
        print("  ont_link: 변경 없음")
    else:
        print(f"  ont_link: {changed}건 상태 변경")
    return changed


# ============================================================
# 4. TH 인과 경로 채우기
# ============================================================

def fill_th_link_path(conn):
    """TH의 수렴 멤버 TC가 공유하는 ont_link 경로를 th_link_path에 기록.

    규칙:
      TH 멤버 TC들이 tc_ont_links에 등록한 링크를 수집.
      공유 빈도가 높은 링크 순으로 step_order 부여.
      is_active는 ont_link의 현재 상태를 복사.
    """
    cur = conn.cursor()

    # 활성 TH
    cur.execute("SELECT th_id FROM th_cards WHERE status = 'active'")
    th_ids = [row[0] for row in cur.fetchall()]

    if not th_ids:
        print("  th_link_path: 활성 TH 없음")
        return 0

    count = 0
    for th_id in th_ids:
        # TH 멤버 TC
        cur.execute("SELECT tc_id FROM th_tc_links WHERE th_id = %s", (th_id,))
        member_tcs = [row[0] for row in cur.fetchall()]

        if not member_tcs:
            continue

        # 멤버 TC들이 참조하는 ont_link 수집
        link_counts = defaultdict(int)
        link_notes = defaultdict(list)

        for tc_id in member_tcs:
            cur.execute("""
                SELECT link_id, role, note FROM tc_ont_links WHERE tc_id = %s
            """, (tc_id,))
            for link_id, role, note in cur.fetchall():
                link_counts[link_id] += 1
                link_notes[link_id].append(f"{tc_id}({role})")

        if not link_counts:
            continue

        # 공유 빈도 순으로 step_order
        sorted_links = sorted(link_counts.items(), key=lambda x: -x[1])

        for step, (link_id, freq) in enumerate(sorted_links, 1):
            cur.execute("SELECT is_active FROM ont_link WHERE link_id = %s", (link_id,))
            row = cur.fetchone()
            is_active = row[0] if row else False

            note = f"freq={freq}, {', '.join(link_notes[link_id])}"

            cur.execute("""
                INSERT INTO th_link_path (th_id, link_id, step_order, is_active, note)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (th_id, link_id) DO UPDATE SET
                    step_order = EXCLUDED.step_order,
                    is_active = EXCLUDED.is_active,
                    note = EXCLUDED.note
            """, (th_id, link_id, step, is_active, note[:200]))
            count += 1

    conn.commit()
    print(f"  th_link_path: {count}건 upsert")
    return count


# ============================================================
# 5. macro JSON → daily_macro 동기화
# ============================================================

def sync_macro_to_db(conn):
    """macro 시스템의 최신 수집 결과를 daily_macro에 INSERT.

    macro 시스템의 출력 파일을 탐색:
      1. macro/output/latest.json (있으면)
      2. macro/state.json (있으면)
      3. psf/state.json (있으면)
    """
    cur = conn.cursor()

    # macro 출력 경로 탐색
    candidates = [
        os.path.join(BASE, "macro", "indicators"),
        os.path.join(BASE, "macro"),
    ]

    macro_data = None
    source_path = None

    for cand in candidates:
        if not os.path.exists(cand):
            continue
        # latest.json 또는 state.json 탐색
        for fname in ["latest.json", "state.json", "macro_snapshot.json"]:
            fpath = os.path.join(cand, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    macro_data = json.load(f)
                source_path = fpath
                break
        if macro_data:
            break

    if not macro_data:
        print("  daily_macro: macro 출력 파일 없음. 스킵.")
        print(f"    탐색 경로: {candidates}")
        return 0

    print(f"  macro 소스: {source_path}")

    # macro JSON 구조: layer_A.A1.value, layer_B.B1.value, ...
    # macro indicator ID → daily_macro 컬럼 매핑 (46개 전체)
    MACRO_FIELD_MAP = {
        # layer_A
        "A1":  "core_pce_yoy",
        # layer_B
        "B1":  "tips_10y_real",
        "B2":  "dxy_index",
        "B3":  "usd_jpy",
        "B4":  "fed_balance_sheet",   # Net Liquidity
        "B5":  "hy_oas",
        # layer_C
        "C1":  "vix",
        "C2":  "move_index",
        "C3":  "yield_spread",
        "C4":  "us_m2",
        "C5":  "ism_pmi",
        "C6":  "unemployment_rate",
        "C7":  "brent_crude",
        "C8":  "bei_10y",
        "C9":  "usd_cny",
        "C10": "fed_funds_rate",
        # layer_D
        "D2":  "bank_reserves",
        "D3":  "rrp_balance",
        "D4":  "tga_balance",
        "D5":  "fed_balance_sheet",   # WALCL (D5 우선, B4는 Net Liq)
        "D6":  "sofr_rate",
        "D8":  "term_premium",
    }

    # 정성 지표 (text 컬럼) — DB에서 TEXT 타입인 것만
    TEXT_FIELD_MAP = {
        "D1":  "sloos",
        "D10": "fed_watch",
        "A2":  "china_credit",
    }

    # 문자열→숫자 변환이 필요한 지표
    PARSE_NUMERIC_MAP = {
        "D7": "fiscal_deficit_gdp",   # "5.8%" → 5.8
        "D9": "cftc_jpy_net",         # "-67780" → -67780
    }

    values = {}

    for layer_key in ["layer_A", "layer_B", "layer_C", "layer_D"]:
        layer = macro_data.get(layer_key, {})
        for ind_key, ind_val in layer.items():
            if not isinstance(ind_val, dict):
                continue
            raw_val = ind_val.get("value")
            if raw_val is None:
                continue

            # 정량 매핑
            db_col = MACRO_FIELD_MAP.get(ind_key)
            if db_col:
                try:
                    values[db_col] = float(raw_val)
                except (ValueError, TypeError):
                    pass

            # 정성 매핑 (text)
            text_col = TEXT_FIELD_MAP.get(ind_key)
            if text_col:
                values[text_col] = str(raw_val)[:200]

            # 문자열→숫자 변환
            parse_col = PARSE_NUMERIC_MAP.get(ind_key)
            if parse_col:
                try:
                    cleaned = str(raw_val).replace("%", "").replace(",", "").strip()
                    values[parse_col] = float(cleaned)
                except (ValueError, TypeError):
                    pass

    # B4(Net Liquidity)는 D5(Fed B/S)와 별도 — B4 값이 있으면 우선
    b4 = macro_data.get("layer_B", {}).get("B4", {})
    if isinstance(b4, dict) and b4.get("value"):
        try:
            net_liq = float(b4["value"])
            values["fed_balance_sheet"] = net_liq
        except (ValueError, TypeError):
            pass

    # D8 term premium from regime if not in layer_D
    if "term_premium" not in values:
        regime = macro_data.get("regime", {})
        d3_text = regime.get("disruption_3", "")
        tp_match = re.search(r"[Tt]erm\s+[Pp]remium\s+(\d+\.\d+)%", d3_text)
        if tp_match:
            try:
                values["term_premium"] = float(tp_match.group(1))
            except ValueError:
                pass

    if not values:
        print("  daily_macro: 추출 가능한 값 없음. macro JSON 구조 확인 필요.")
        return 0

    # snapshot_date — meta.date 또는 meta.market_date
    meta = macro_data.get("meta", {})
    snap_date = meta.get("date") or meta.get("market_date") or macro_data.get("date", str(date.today()))

    # INSERT
    cols = ["snapshot_date", "source"] + list(values.keys())
    vals = [snap_date, "macro_bridge"] + list(values.values())
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
        print(f"  daily_macro: {snap_date} 저장 ({len(values)}개 지표)")
        return 1
    except Exception as e:
        conn.rollback()
        print(f"  daily_macro: 저장 실패 — {e}")
        return 0


# ============================================================
# 6. ont_status_log 스냅샷 (PSF 속성 상태 기록)
# ============================================================

def snapshot_ont_status(conn):
    """PSF 속성 상태를 ont_status_log에 기록.

    2가지 소스를 결합:
      1) v_macro_to_ontology 뷰 (macro 데이터 기반 자동 판정) — 정량
      2) TC 카드의 psf_link 텍스트 — 정성

    정량 판정이 있으면 우선. 없으면 정성 fallback.
    """
    cur = conn.cursor()

    cur.execute("SELECT property_id, object_id FROM ont_property")
    prop_to_obj = {row[0]: row[1] for row in cur.fetchall()}

    property_states = {}  # property_id → (value, text, direction, verdict, source)

    # --- 소스 1: macro 정량 판정 (v_macro_to_ontology) ---
    try:
        cur.execute("""
            SELECT property_id, current_value, property_verdict, direction, metric_name
            FROM v_macro_to_ontology
        """)
        for prop_id, val, verdict, direction, metric_name in cur.fetchall():
            if val is not None:
                property_states[prop_id] = (
                    val,
                    f"{metric_name}={val} → {verdict}",
                    direction,
                    verdict,
                    "macro",
                )
    except Exception:
        conn.rollback()

    # --- 소스 2: TC psf_link 정성 (fallback) ---
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")
        if d.get("status") != "active":
            continue

        psf_link = d.get("psf_link", "") or ""
        _, properties = parse_psf_link(psf_link)

        for prop_id, state in properties:
            # 이미 macro 정량이 있으면 스킵
            if prop_id in property_states and property_states[prop_id][4] == "macro":
                continue

            severity = {"🔴": 3, "격화": 3, "🟡": 2, "완화": 1, "🟢": 1, "활성": 2}
            new_sev = severity.get(state, 0)
            if prop_id in property_states:
                old_sev = severity.get(property_states[prop_id][1], 0)
                if new_sev <= old_sev:
                    continue

            direction_map = {"🔴": "worsening", "격화": "worsening", "🟡": "neutral", "🟢": "improving", "완화": "improving"}
            verdict_map = {"🔴": "alert", "격화": "alert", "🟡": "watch", "🟢": "normal", "완화": "improving"}
            property_states[prop_id] = (
                None,
                f"{state} (from {tc_id})",
                direction_map.get(state, "unknown"),
                verdict_map.get(state, "unknown"),
                "psf_link",
            )

    if not property_states:
        print("  ont_status_log: 속성 참조 없음.")
        return 0

    count = 0
    for prop_id, (val, text, direction, verdict, source) in property_states.items():
        obj_id = prop_to_obj.get(prop_id)
        if not obj_id:
            continue

        cur.execute("""
            INSERT INTO ont_status_log (snapshot_date, object_id, property_id, value, text_value, direction, verdict)
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_date, property_id) DO UPDATE SET
                value = EXCLUDED.value,
                text_value = EXCLUDED.text_value,
                direction = EXCLUDED.direction,
                verdict = EXCLUDED.verdict
        """, (obj_id, prop_id, val, text[:200] if text else None, direction, verdict))
        count += 1

    conn.commit()
    print(f"  ont_status_log: {count}건 스냅샷 (macro 정량 + psf_link 정성)")
    return count


# ============================================================
# 7. ont_regime_log 동기화
# ============================================================

def sync_tc_mt_links(conn):
    """TC 카드의 tags에서 MT-XX 코드를 추출하여 tc_mt_links에 INSERT.

    TC의 tags 배열에 MT-01~MT-07 등이 포함되어 있으면 자동 연결.
    role은 기본 'evidence'. 기존 연결은 유지.
    """
    cur = conn.cursor()

    # 유효 MT 목록
    cur.execute("SELECT mt_id FROM ont_megatrend")
    valid_mts = {row[0] for row in cur.fetchall()}

    if not valid_mts:
        print("  tc_mt_links: ont_megatrend 비어있음. 스킵.")
        return 0

    count = 0
    for fname in sorted(os.listdir(CARDS_DIR)):
        if not fname.startswith("TC-") or not fname.endswith(".json"):
            continue
        with open(os.path.join(CARDS_DIR, fname), "r", encoding="utf-8") as f:
            d = json.load(f)
        tc_id = d.get("tc_id") or d.get("id")

        for tag in d.get("tags", []):
            if tag in valid_mts:
                cur.execute("""
                    INSERT INTO tc_mt_links (tc_id, mt_id, role, note)
                    VALUES (%s, %s, 'evidence', 'auto: tag match')
                    ON CONFLICT (tc_id, mt_id) DO NOTHING
                """, (tc_id, tag))
                count += 1

    conn.commit()
    print(f"  tc_mt_links: {count}건 upsert")
    return count


def sync_regime_log(conn):
    """macro latest.json의 regime 판정을 ont_regime_log에 기록."""
    cur = conn.cursor()

    # macro 파일 탐색
    candidates = [
        os.path.join(BASE, "macro", "indicators", "latest.json"),
        os.path.join(BASE, "macro", "latest.json"),
    ]
    macro_data = None
    for fpath in candidates:
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                macro_data = json.load(f)
            break

    if not macro_data:
        print("  ont_regime_log: macro 파일 없음. 스킵.")
        return 0

    meta = macro_data.get("meta", {})
    regime = macro_data.get("regime", {})
    if not regime:
        print("  ont_regime_log: regime 데이터 없음. 스킵.")
        return 0

    snap_date = meta.get("date") or str(date.today())
    verdict = regime.get("verdict", "UNKNOWN")
    risk_count = regime.get("risk_asset_count", "")
    quadrant = regime.get("quadrant", "")
    l7 = regime.get("l7_score")
    l8 = regime.get("l8_score")
    narrative = (regime.get("narrative") or "")[:500]

    # keystone 추출
    keystone_text = regime.get("keystone", "")
    ks_match = re.search(r"(\d+\.\d+)%", keystone_text)
    ks_value = float(ks_match.group(1)) if ks_match else None
    ks_dir = "REVERSE" if "REVERSE" in keystone_text.upper() else "NORMAL"

    # 이미 같은 날짜에 같은 regime이 있으면 스킵
    cur.execute("SELECT regime FROM ont_regime_log WHERE log_date = %s", (snap_date,))
    existing = cur.fetchone()
    if existing and existing[0] == verdict:
        print(f"  ont_regime_log: {snap_date} 이미 존재 ({verdict}). 스킵.")
        return 0

    cur.execute("""
        INSERT INTO ont_regime_log (log_date, regime, risk_asset_count, quadrant,
                                    keystone_value, keystone_direction, narrative,
                                    l7_score, l8_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (snap_date, verdict, risk_count, quadrant, ks_value, ks_dir, narrative, l7, l8))
    conn.commit()
    print(f"  ont_regime_log: {snap_date} {verdict} (keystone {ks_value}% {ks_dir})")
    return 1


# ============================================================
# 8. 현황 조회
# ============================================================

def show_status(conn):
    """온톨로지 브릿지 현황."""
    cur = conn.cursor()
    print("\n━━ 온톨로지 브릿지 현황 ━━\n")

    # ont_link 활성 상태
    cur.execute("SELECT link_id, name, is_active, activation_evidence FROM ont_link ORDER BY link_id")
    print("  인과 링크 (ont_link):")
    for lid, name, active, evidence in cur.fetchall():
        icon = "🟢" if active else "⚪"
        ev = f" — {evidence[:40]}" if evidence else ""
        print(f"    {icon} {lid} {name}{ev}")

    # 브릿지 현황
    for table, label in [
        ("tc_ont_links", "TC↔Link"),
        ("tc_metric_links", "TC↔Metric"),
        ("th_link_path", "TH↔Path"),
    ]:
        cur.execute(f"SELECT count(*) FROM {table}")
        cnt = cur.fetchone()[0]
        print(f"\n  {label}: {cnt}건")
        if cnt > 0 and table == "tc_ont_links":
            cur.execute("""
                SELECT tc_id, link_id, role FROM tc_ont_links ORDER BY tc_id, link_id
            """)
            for tc_id, link_id, role in cur.fetchall():
                print(f"    {tc_id} → {link_id} ({role})")

    # ont_status_log
    cur.execute("SELECT count(*) FROM ont_status_log")
    cnt = cur.fetchone()[0]
    print(f"\n  속성 상태 이력: {cnt}건")
    if cnt > 0:
        cur.execute("""
            SELECT snapshot_date, property_id, text_value, direction, verdict
            FROM ont_status_log ORDER BY snapshot_date DESC, property_id LIMIT 10
        """)
        for sd, pid, tv, dir_, ver in cur.fetchall():
            print(f"    {sd} {pid}: {tv} ({dir_}/{ver})")

    # daily_macro
    cur.execute("SELECT count(*), max(snapshot_date) FROM daily_macro")
    cnt, latest = cur.fetchone()
    print(f"\n  daily_macro: {cnt}건 (최신: {latest})")

    # v_transition_path 뷰
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM th_link_path LIMIT 1
        )
    """)
    has_path = cur.fetchone()[0]
    if has_path:
        print("\n  전이 인과 경로:")
        cur.execute("""
            SELECT th_id, link_name, step_order, link_currently_active, from_obj, to_obj
            FROM v_transition_path ORDER BY th_id, step_order
        """)
        for th_id, name, step, active, from_obj, to_obj in cur.fetchall():
            icon = "🟢" if active else "⚪"
            print(f"    {th_id} step {step}: {icon} {name} ({from_obj} → {to_obj})")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ============================================================
# 메인
# ============================================================

def run_full(conn):
    """전체 브릿지 실행."""
    today = str(date.today())
    print(f"━━ Ontology Bridge ({today}) ━━\n")

    print("  [1/5] TC → ont_link 브릿지")
    fill_tc_ont_links(conn)

    print("\n  [2/5] TC → ont_metric 브릿지")
    fill_tc_metric_links(conn)

    print("\n  [3/5] ont_link 활성화 판정")
    activate_ont_links(conn)

    print("\n  [4/5] TH 인과 경로")
    fill_th_link_path(conn)

    print("\n  [5/5] PSF 속성 상태 스냅샷")
    snapshot_ont_status(conn)

    print("\n  [6/8] macro → daily_macro")
    sync_macro_to_db(conn)

    print("\n  [7/8] macro → ont_regime_log")
    sync_regime_log(conn)

    print("\n  [8/8] TC → MT 연결")
    sync_tc_mt_links(conn)

    show_status(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ontology Bridge")
    parser.add_argument("--bridge", action="store_true", help="tc_ont_links + tc_metric_links만")
    parser.add_argument("--activate", action="store_true", help="ont_link 활성화 판정만")
    parser.add_argument("--th-path", action="store_true", help="th_link_path만")
    parser.add_argument("--macro-sync", action="store_true", help="macro → daily_macro")
    parser.add_argument("--status", action="store_true", help="현황 조회")
    args = parser.parse_args()

    conn = get_conn()
    try:
        if args.bridge:
            fill_tc_ont_links(conn)
            fill_tc_metric_links(conn)
        elif args.activate:
            activate_ont_links(conn)
        elif args.th_path:
            fill_th_link_path(conn)
        elif args.macro_sync:
            sync_macro_to_db(conn)
        elif args.status:
            show_status(conn)
        else:
            run_full(conn)
    finally:
        conn.close()
