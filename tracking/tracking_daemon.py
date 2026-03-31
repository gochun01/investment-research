"""
tracking_daemon.py — 순환 루프 자동 실행 + 텔레그램 알림
==========================================================
cycle1(일일) / cycle2(주별) / cycle3(월별)을 schedule 라이브러리로 자동 호출.
QUAL Watch 만기 시 텔레그램으로 판정 요청, 사용자 응답 수신.

사용법:
  python tracking_daemon.py                # daemon 시작 (24/7)
  python tracking_daemon.py --once         # cycle1 즉시 1회 실행 후 종료
  python tracking_daemon.py --status       # 상태 조회
  python tracking_daemon.py --test-tg      # 텔레그램 연결 테스트

스케줄:
  매일 08:00  — cycle1 (Watch 만기 체크 + Heartbeat 가격 감시)
  매주 월 09:00 — cycle2 (적중률 + conviction template)
  매월 1일 10:00 — cycle3 (TC 수렴 + TH confidence)
"""

import sys
import os
import argparse
import logging
import time
import json
import re
import threading
from datetime import datetime
from pathlib import Path

# ── 경로 ──
TRACKING = Path(__file__).resolve().parent
BASE = TRACKING.parent
LOGS_DIR = TRACKING / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ── 텔레그램 설정 ──
TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8007127959:AAEwETGmQ9VMgPO3y4WDwr34Nl5Lp54RoMg"
)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "5696754698")
TELEGRAM_API = "https://api.telegram.org"

# ── 알림 억제 ──
SENT_LOG_PATH = TRACKING / "alerts" / "sent_log.json"
SUPPRESS_MINUTES = 60

# ── DB (cycle1과 동일) ──
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "invest_ontology",
    "user": "investor",
    "password": "invest2025!secure",
}


# ============================================================
# 로깅
# ============================================================
def setup_logging():
    log_file = LOGS_DIR / f"daemon_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )
    return logging.getLogger("tracking.daemon")


# ============================================================
# 텔레그램 — 발신
# ============================================================
def tg_send(text: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 발송."""
    import requests
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4000],
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        logging.getLogger("tracking.daemon").error(f"TG send failed: {e}")
        return False


def tg_send_alert(level: str, title: str, body: str) -> bool:
    """레벨별 포맷 알림."""
    emoji = {
        "critical": "\U0001f534",
        "warn": "\U0001f7e1",
        "daily": "\U0001f7e2",
        "qual": "\U0001f535",
        "summary": "\U0001f4ca",
    }
    header = f"{emoji.get(level, 'ℹ️')} <b>[Tracking {level.upper()}]</b>"
    msg = f"{header}\n<b>{title}</b>\n\n{body}"
    return tg_send(msg)


# ============================================================
# 텔레그램 — 수신 (polling)
# ============================================================
LAST_UPDATE_ID = 0


def tg_poll(logger):
    """텔레그램 업데이트 polling — 사용자 응답 수신."""
    import requests
    global LAST_UPDATE_ID
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": LAST_UPDATE_ID + 1, "timeout": 30}
    try:
        resp = requests.get(url, params=params, timeout=35)
        if resp.status_code != 200:
            return
        data = resp.json()
        for update in data.get("result", []):
            LAST_UPDATE_ID = update["update_id"]
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if chat_id != TELEGRAM_CHAT_ID:
                continue

            if text.startswith("/status"):
                handle_status_command(logger)
            elif text.startswith("/record"):
                handle_record_command(text, logger)
            elif text.startswith("/detail"):
                handle_detail_command(text, logger)
            elif text.startswith("/help"):
                handle_help_command()
            else:
                logger.debug(f"Ignored message: {text[:50]}")
    except Exception as e:
        logger.debug(f"TG poll error: {e}")


def tg_listener(logger):
    """백그라운드 텔레그램 리스너."""
    logger.info("Telegram listener started")
    while True:
        try:
            tg_poll(logger)
        except Exception as e:
            logger.error(f"Listener error: {e}")
            time.sleep(10)


def handle_help_command():
    tg_send(
        "<b>📋 Tracking Daemon 명령어</b>\n\n"
        "/status — Watch/Prediction/TH 현황\n"
        "/detail W-ID — Watch 상세 근거 조회\n"
        "/record W-ID verdict lesson — Watch 판정 기록\n"
        "  verdict: hit / miss / partial / ongoing\n"
        "  예: /record W-2026-03-24-UQ-010 ongoing 아직 영향 미확인\n\n"
        "/help — 이 도움말"
    )


def handle_detail_command(text: str, logger):
    """특정 Watch의 근거 데이터를 풍부하게 조회."""
    parts = text.split(None, 1)
    if len(parts) < 2:
        tg_send("⚠️ 형식: /detail [Watch-ID]\n예: /detail W-2026-03-24-UQ-010")
        return

    watch_id = parts[1].strip()
    watches_data = load_watches()
    watch_map = {w["id"]: w for w in watches_data.get("watches", [])}
    watch = watch_map.get(watch_id)

    if not watch:
        tg_send(f"⚠️ Watch ID '{watch_id}' 미발견")
        return

    tc_cards = load_tc_cards()
    preds = load_predictions()

    try:
        enriched = build_enriched_alert(watch, tc_cards, preds)
        tg_send_alert("qual", "Watch 상세 조회", enriched)
    except Exception as e:
        logger.error(f"Detail failed: {e}")
        tg_send(f"⚠️ 조회 실패: {e}")


def handle_status_command(logger):
    """현재 상태 요약 발송."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(TRACKING / "cycle1_daily.py"), "--status"],
            capture_output=True, text=True, timeout=30, cwd=str(TRACKING)
        )
        output = result.stdout.strip()
        if len(output) > 3500:
            output = output[:3500] + "\n..."
        tg_send(f"<pre>{output}</pre>")
    except Exception as e:
        logger.error(f"Status command failed: {e}")
        tg_send(f"⚠️ Status 조회 실패: {e}")


def sync_watch_to_predictions(watch_id: str, verdict: str, lesson: str, logger):
    """
    Watch 판정을 연결된 Prediction에도 반영.
    Watch → watch_tc_links → predictions → th_evidence
    ongoing은 prediction을 갱신하지 않음 (아직 미결).
    """
    if verdict == "ongoing":
        return []  # 미결은 prediction 갱신 안 함

    synced = []
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1. Watch → TC 연결 조회
        cur.execute(
            "SELECT tc_id FROM watch_tc_links WHERE watch_id = %s",
            (watch_id,)
        )
        tc_ids = [row[0] for row in cur.fetchall()]

        if not tc_ids:
            conn.close()
            return []

        # 2. 연결된 open predictions 갱신
        for tc_id in tc_ids:
            cur.execute("""
                UPDATE predictions
                SET status = %s, outcome = %s,
                    outcome_date = CURRENT_DATE, lesson = %s
                WHERE tc_id = %s AND status = 'open'
                RETURNING pred_id, tc_id, scenario
            """, (verdict, lesson, lesson, tc_id))

            updated = cur.fetchall()
            for pred_id, tid, scenario in updated:
                synced.append(f"{pred_id}({scenario})")
                logger.info(f"  Prediction {pred_id} → {verdict}")

                # 3. TH evidence 기록 (hit/miss만)
                if verdict in ("hit", "miss"):
                    cur.execute("""
                        SELECT th.th_id, th.confidence
                        FROM th_cards th
                        JOIN th_tc_links tl ON th.th_id = tl.th_id
                        WHERE tl.tc_id = %s
                    """, (tid,))
                    th_rows = cur.fetchall()

                    for th_id, current_conf in th_rows:
                        delta = 0.05 if verdict == "hit" else -0.03
                        new_conf = max(0.0, min(1.0, current_conf + delta))
                        ev_type = "completion_met" if verdict == "hit" else "kill_met"

                        cur.execute("""
                            UPDATE th_cards SET confidence = %s WHERE th_id = %s
                        """, (new_conf, th_id))

                        cur.execute("""
                            INSERT INTO th_evidence
                            (th_id, ev_date, ev_type, description,
                             confidence_delta, confidence_after)
                            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
                        """, (th_id, ev_type,
                              f"{pred_id} {verdict}: {lesson}",
                              delta, new_conf))

                        synced.append(f"TH {th_id} {current_conf:.3f}→{new_conf:.3f}")
                        logger.info(f"  TH {th_id} confidence {current_conf:.3f} → {new_conf:.3f}")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Prediction sync failed: {e}")

    return synced


def handle_record_command(text: str, logger):
    """
    /record W-ID verdict lesson
    Watch 판정 기록 → 연결된 Prediction 갱신 → TH evidence 반영.
    """
    parts = text.split(None, 3)
    if len(parts) < 4:
        tg_send("⚠️ 형식: /record [Watch-ID] [hit|miss|partial|ongoing] [lesson 1문장+]")
        return

    _, watch_id, verdict, lesson = parts
    verdict = verdict.lower()
    if verdict not in ("hit", "miss", "partial", "ongoing"):
        tg_send(f"⚠️ verdict는 hit/miss/partial/ongoing 중 하나: '{verdict}'")
        return
    if len(lesson) < 5:
        tg_send("⚠️ lesson은 1문장 이상 필요합니다.")
        return

    # ── 1. Watch 기록 (active-watches.json) ──
    watches_path = TRACKING / "active-watches.json"
    try:
        with open(watches_path, "r", encoding="utf-8") as f:
            watches_data = json.load(f)

        found = False
        for w in watches_data.get("watches", []):
            if w.get("id") == watch_id:
                found = True
                if "completed_checks" not in w:
                    w["completed_checks"] = []
                w["completed_checks"].append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "verdict": verdict,
                    "evidence": lesson,
                    "source": "telegram"
                })
                if verdict != "ongoing":
                    w["status"] = "closed"
                break

        if not found:
            tg_send(f"⚠️ Watch ID '{watch_id}' 미발견")
            return

        with open(watches_path, "w", encoding="utf-8") as f:
            json.dump(watches_data, f, ensure_ascii=False, indent=2)

        # ── 2. Prediction + TH 연동 ──
        synced = sync_watch_to_predictions(watch_id, verdict, lesson, logger)

        # ── 3. 결과 알림 ──
        msg = f"✅ <b>{watch_id}</b> → {verdict}\n📝 {lesson}"
        if synced:
            msg += f"\n\n🔗 연동: {', '.join(synced)}"
        else:
            msg += "\n\n(연결된 Prediction 없음)"

        logger.info(f"Watch {watch_id} recorded: {verdict} | synced: {synced}")
        tg_send(msg)

    except Exception as e:
        logger.error(f"Record failed: {e}")
        tg_send(f"⚠️ 기록 실패: {e}")


# ============================================================
# 근거 수집 — Watch 판정 지원
# ============================================================
def load_watches():
    """active-watches.json 로딩."""
    path = TRACKING / "active-watches.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"watches": []}


def load_tc_cards():
    """cards/ 디렉토리의 TC 카드 로딩."""
    cards = {}
    cards_dir = TRACKING / "cards"
    if not cards_dir.exists():
        return cards
    for f in cards_dir.glob("TC-*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                card = json.load(fp)
                cards[card.get("tc_id", f.stem)] = card
        except Exception:
            continue
    return cards


def load_predictions():
    """prediction-ledger.json 로딩."""
    path = TRACKING / "prediction-ledger.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"predictions": []}


def fetch_prices(symbols: list) -> dict:
    """yfinance로 현재가 + 5일 변동 조회."""
    results = {}
    try:
        import yfinance as yf
        for sym in symbols[:5]:  # 최대 5개
            try:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period="5d")
                if hist.empty:
                    results[sym] = {"error": "데이터 없음"}
                    continue
                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[0] if len(hist) > 1 else current
                change_pct = ((current - prev) / prev) * 100
                results[sym] = {
                    "price": round(current, 2),
                    "change_5d": round(change_pct, 1),
                    "currency": "KRW" if ".KS" in sym else "USD",
                }
            except Exception as e:
                results[sym] = {"error": str(e)[:50]}
    except ImportError:
        pass
    return results


def extract_tickers_from_watch(watch: dict) -> list:
    """Watch의 data_sources에서 price: 티커 추출."""
    tickers = []
    tpl = watch.get("check_template", {})
    sources = tpl.get("data_sources", [])
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, str) and src.startswith("price:"):
                raw = src.replace("price:", "").strip()
                # 숫자만이면 KRX 종목코드
                if raw.isdigit():
                    tickers.append(f"{raw}.KS")
                else:
                    tickers.append(raw)
    return tickers


def find_linked_predictions(watch_id: str, predictions: dict) -> list:
    """Watch와 연결된 Prediction 조회 (watch_tc_links 기반)."""
    # prediction-ledger에서 직접 매칭은 어려우므로
    # DB의 watch_tc_links를 통해 TC → Prediction 경로로 조회
    linked = []
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        # watch_tc_links에서 TC ID 조회
        cur.execute(
            "SELECT tc_id FROM watch_tc_links WHERE watch_id = %s",
            (watch_id,)
        )
        tc_ids = [row[0] for row in cur.fetchall()]

        if tc_ids:
            # 해당 TC의 prediction 조회
            cur.execute(
                "SELECT id, scenario, probability, claim, status "
                "FROM predictions WHERE tc_id = ANY(%s) AND status = 'open'",
                (tc_ids,)
            )
            for row in cur.fetchall():
                linked.append({
                    "id": row[0], "scenario": row[1],
                    "probability": row[2], "claim": row[3],
                    "status": row[4],
                })
        conn.close()
    except Exception:
        pass
    return linked


def build_enriched_alert(watch: dict, tc_cards: dict, predictions: dict) -> str:
    """
    Watch에 대한 풍부한 판정 지원 알림 생성.
    근거 데이터 + TC 맥락 + 예비 판정 포함.
    """
    w_id = watch.get("id", "?")
    subject = watch.get("subject", "")
    tpl = watch.get("check_template", {})
    questions = tpl.get("questions", [])

    msg = f"<b>{w_id}</b>\n"
    msg += f"❓ {subject}\n\n"

    # ── 1. 가격 데이터 (MIXED Watch) ──
    tickers = extract_tickers_from_watch(watch)
    if tickers:
        prices = fetch_prices(tickers)
        msg += "📊 <b>가격 현황:</b>\n"
        for sym, data in prices.items():
            if "error" in data:
                msg += f"  • {sym}: 조회 실패\n"
            else:
                arrow = "📈" if data["change_5d"] > 0 else "📉" if data["change_5d"] < 0 else "➡️"
                unit = "₩" if data["currency"] == "KRW" else "$"
                price_str = f"{unit}{data['price']:,.0f}" if data["currency"] == "KRW" else f"{unit}{data['price']:,.2f}"
                msg += f"  {arrow} {sym}: {price_str} (5일 {data['change_5d']:+.1f}%)\n"
        msg += "\n"

    # ── 2. TC 카드 맥락 ──
    # watch_id에서 관련 TC 찾기 (check_template의 questions이나 tags로)
    related_tcs = []
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT tc_id FROM watch_tc_links WHERE watch_id = %s", (w_id,)
        )
        related_tcs = [row[0] for row in cur.fetchall()]
        conn.close()
    except Exception:
        pass

    if related_tcs:
        msg += "🗂 <b>연결 TC:</b>\n"
        for tc_id in related_tcs[:3]:
            tc = tc_cards.get(tc_id, {})
            title = tc.get("title", tc_id)
            phase = tc.get("phase", "?")
            scenarios = tc.get("scenarios", {})
            sc_str = " | ".join(
                f"{k}:{v.get('probability', v) if isinstance(v, dict) else v}"
                for k, v in sorted(scenarios.items())
            ) if scenarios else "N/A"
            msg += f"  • {tc_id} (P{phase}): {title[:40]}\n"
            msg += f"    시나리오: {sc_str}\n"
        msg += "\n"

    # ── 3. 연결된 예측 ──
    linked_preds = find_linked_predictions(w_id, predictions)
    if linked_preds:
        msg += "🎯 <b>연결 예측:</b>\n"
        for p in linked_preds[:3]:
            msg += f"  • {p['scenario']}({p['probability']}): {p['claim'][:50]}\n"
        msg += "\n"

    # ── 4. 예비 판정 제안 ──
    preliminary = "ongoing"
    reason = "데이터 부족, 추가 관찰 필요"

    if tickers and prices:
        # 가격 변동 기반 간이 판정
        significant_moves = [
            (sym, d) for sym, d in prices.items()
            if "error" not in d and abs(d.get("change_5d", 0)) > 3.0
        ]
        if significant_moves:
            sym, d = significant_moves[0]
            if d["change_5d"] < -5:
                preliminary = "hit"
                reason = f"{sym} 5일 {d['change_5d']:+.1f}% — 유의미한 하락"
            elif d["change_5d"] > 5:
                preliminary = "hit"
                reason = f"{sym} 5일 {d['change_5d']:+.1f}% — 유의미한 상승"
            else:
                preliminary = "partial"
                reason = f"{sym} 5일 {d['change_5d']:+.1f}% — 약한 움직임"
        else:
            preliminary = "ongoing"
            reason = "5일 가격 변동 ±3% 미만, 아직 반응 미미"

    msg += f"💡 <b>예비 판정: {preliminary}</b>\n"
    msg += f"  근거: {reason}\n\n"

    # ── 5. 판정 입력 안내 ──
    msg += f"<b>판정 입력:</b>\n"
    msg += f"<code>/record {w_id} {preliminary} {reason}</code>\n"
    msg += f"(수정 후 전송하세요)"

    return msg


# ============================================================
# 알림 억제
# ============================================================
def should_suppress(key: str) -> bool:
    """최근 SUPPRESS_MINUTES 이내 동일 키 알림 억제."""
    try:
        if not SENT_LOG_PATH.exists():
            return False
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)
        last = log.get(key)
        if not last:
            return False
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() < SUPPRESS_MINUTES * 60
    except Exception:
        return False


def log_sent(key: str):
    """알림 발송 기록."""
    SENT_LOG_PATH.parent.mkdir(exist_ok=True)
    try:
        log = {}
        if SENT_LOG_PATH.exists():
            with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        log[key] = datetime.now().isoformat()
        with open(SENT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============================================================
# Cycle 실행기
# ============================================================
def run_cycle1(logger, check_all=False):
    """cycle1 실행 + 근거 포함 풍부한 알림 발송."""
    import subprocess
    logger.info("━━ Cycle 1 실행 ━━")

    args = [sys.executable, str(TRACKING / "cycle1_daily.py")]
    if check_all:
        args.append("--check-all")

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=120, cwd=str(TRACKING)
        )
        output = result.stdout.strip()
        logger.info(f"Cycle 1 완료 ({len(output)} chars)")

        # ── cycle1 출력 파싱 ──
        lines = output.split("\n")
        due_count = 0
        qual_ids = []
        heartbeat_alerts = []

        for line in lines:
            if "만기 Watch:" in line:
                try:
                    due_count = int(line.split(":")[1].strip().split("건")[0])
                except:
                    pass
            # Watch ID 추출
            m = re.search(r'\[(QUAL|MIXED)\s*\]\s*(W-\S+)', line)
            if m:
                qual_ids.append(m.group(2))
            if "⚠" in line or "🔴" in line or "CRITICAL" in line.upper():
                heartbeat_alerts.append(line.strip())

        # ── Heartbeat 임계값 위반 (즉시) ──
        for alert in heartbeat_alerts:
            key = f"hb:{alert[:30]}"
            if not should_suppress(key):
                tg_send_alert("critical", "Heartbeat 임계값", alert)
                log_sent(key)

        # ── 풍부한 QUAL Watch 알림 (근거 포함) ──
        if qual_ids:
            watches_data = load_watches()
            tc_cards = load_tc_cards()
            preds = load_predictions()

            # Watch 객체 매칭
            watch_map = {w["id"]: w for w in watches_data.get("watches", [])}

            # 상위 5건: 개별 풍부한 알림
            sent_count = 0
            for w_id in qual_ids[:5]:
                watch = watch_map.get(w_id)
                if not watch:
                    continue
                key = f"qual:{w_id}"
                if should_suppress(key):
                    continue
                try:
                    enriched = build_enriched_alert(watch, tc_cards, preds)
                    tg_send_alert("qual", "Watch 판정 요청", enriched)
                    log_sent(key)
                    sent_count += 1
                    time.sleep(1)  # 텔레그램 rate limit 방지
                except Exception as e:
                    logger.error(f"Enriched alert failed for {w_id}: {e}")

            # 나머지: 요약 알림
            remaining = len(qual_ids) - min(len(qual_ids), 5)
            if remaining > 0:
                summary_list = "\n".join(
                    f"  • {w_id}: {watch_map.get(w_id, {}).get('subject', '?')[:50]}"
                    for w_id in qual_ids[5:15]
                )
                if remaining > 10:
                    summary_list += f"\n  ... 외 {remaining - 10}건"
                tg_send_alert("qual",
                    f"추가 Watch {remaining}건 (요약)",
                    f"{summary_list}\n\n각 Watch 상세는 /detail [Watch-ID]")

        # ── 일일 요약 ──
        summary = (
            f"Watch 만기: {due_count}건\n"
            f"판정 필요: {len(qual_ids)}건 (근거 포함 알림 발송)\n"
            f"Heartbeat 위반: {len(heartbeat_alerts)}건"
        )
        tg_send_alert("daily", f"Cycle 1 완료 ({datetime.now().strftime('%m/%d')})", summary)

        return True
    except subprocess.TimeoutExpired:
        logger.error("Cycle 1 timeout (120s)")
        tg_send_alert("warn", "Cycle 1 Timeout", "120초 초과. 수동 확인 필요.")
        return False
    except Exception as e:
        logger.error(f"Cycle 1 failed: {e}")
        tg_send_alert("warn", "Cycle 1 실패", str(e))
        return False


def run_cycle2(logger):
    """cycle2 주별 실행."""
    import subprocess
    logger.info("━━ Cycle 2 실행 ━━")
    try:
        result = subprocess.run(
            [sys.executable, str(TRACKING / "cycle2_weekly.py"), "--stats"],
            capture_output=True, text=True, timeout=60, cwd=str(TRACKING)
        )
        output = result.stdout.strip()
        logger.info(f"Cycle 2 완료")

        # templates도 실행
        result2 = subprocess.run(
            [sys.executable, str(TRACKING / "cycle2_weekly.py"), "--templates"],
            capture_output=True, text=True, timeout=60, cwd=str(TRACKING)
        )
        templates_output = result2.stdout.strip()

        summary = f"<b>적중률:</b>\n<pre>{output}</pre>"
        if templates_output:
            summary += f"\n\n<b>Conviction:</b>\n<pre>{templates_output[:1000]}</pre>"

        tg_send_alert("summary", f"Cycle 2 주별 리포트 ({datetime.now().strftime('%m/%d')})", summary)
        return True
    except Exception as e:
        logger.error(f"Cycle 2 failed: {e}")
        tg_send_alert("warn", "Cycle 2 실패", str(e))
        return False


def run_cycle3(logger):
    """cycle3 월별 실행."""
    import subprocess
    logger.info("━━ Cycle 3 실행 ━━")
    try:
        # convergence 체크
        result = subprocess.run(
            [sys.executable, str(TRACKING / "cycle3_monthly.py"), "--convergence"],
            capture_output=True, text=True, timeout=60, cwd=str(TRACKING)
        )
        conv_output = result.stdout.strip()

        # TH 상태
        result2 = subprocess.run(
            [sys.executable, str(TRACKING / "cycle3_monthly.py"), "--th-status"],
            capture_output=True, text=True, timeout=60, cwd=str(TRACKING)
        )
        th_output = result2.stdout.strip()

        summary = f"<b>수렴 탐지:</b>\n<pre>{conv_output[:1500]}</pre>"
        summary += f"\n\n<b>TH 현황:</b>\n<pre>{th_output[:1500]}</pre>"

        tg_send_alert("summary", f"Cycle 3 월별 리포트 ({datetime.now().strftime('%m/%d')})", summary)
        return True
    except Exception as e:
        logger.error(f"Cycle 3 failed: {e}")
        tg_send_alert("warn", "Cycle 3 실패", str(e))
        return False


def run_db_sync(logger):
    """DB 동기화."""
    import subprocess
    logger.info("DB sync 실행")
    try:
        result = subprocess.run(
            [sys.executable, str(TRACKING / "db_sync.py")],
            capture_output=True, text=True, timeout=60, cwd=str(TRACKING)
        )
        logger.info(f"DB sync: {result.stdout.strip()[:200]}")
        return True
    except Exception as e:
        logger.error(f"DB sync failed: {e}")
        return False


def run_ontology_bridge(logger):
    """온톨로지 브릿지 실행."""
    import subprocess
    logger.info("온톨로지 브릿지 실행")
    try:
        result = subprocess.run(
            [sys.executable, str(TRACKING / "ontology_bridge.py")],
            capture_output=True, text=True, timeout=120, cwd=str(TRACKING)
        )
        logger.info(f"브릿지: {result.stdout.strip()[-200:]}")
        return True
    except Exception as e:
        logger.error(f"브릿지 failed: {e}")
        return False


def run_quality_check(logger):
    """데이터 품질 자동 진단."""
    import subprocess
    logger.info("품질 진단 실행")
    try:
        result = subprocess.run(
            [sys.executable, str(TRACKING / "quality_check.py"), "--summary"],
            capture_output=True, text=True, timeout=120, cwd=str(TRACKING)
        )
        output = result.stdout.strip()
        logger.info(f"품질 진단: {output[:200]}")

        # CRITICAL이 있으면 텔레그램 알림
        if "CRITICAL" in output and "CRITICAL: 0" not in output:
            tg_send_alert("warn", "품질 진단 CRITICAL 발견", f"<pre>{output[:500]}</pre>")

        return True
    except Exception as e:
        logger.error(f"품질 진단 failed: {e}")
        return False


# ============================================================
# Daemon
# ============================================================
def run_daemon(logger):
    """24/7 daemon — schedule 라이브러리로 cycle 자동 호출."""
    try:
        import schedule as sched
    except ImportError:
        logger.error("'schedule' 라이브러리 필요: pip install schedule")
        sys.exit(1)

    # ── 스케줄 등록 ──
    # 매일 08:00 — cycle1
    sched.every().day.at("08:00").do(run_cycle1, logger=logger)
    # 매일 20:00 — cycle1 (오후 체크)
    sched.every().day.at("20:00").do(run_cycle1, logger=logger)
    # 매주 월요일 09:00 — cycle2
    sched.every().monday.at("09:00").do(run_cycle2, logger=logger)
    # 매월 1일 근사 — 매주 일요일에 날짜 체크 후 1일이면 실행
    sched.every().sunday.at("10:00").do(
        lambda: run_cycle3(logger) if datetime.now().day <= 7 else None
    )
    # 매일 08:05 — DB sync (cycle1 직후)
    sched.every().day.at("08:05").do(run_db_sync, logger=logger)
    # 매일 08:10 — 온톨로지 브릿지 (DB sync 직후)
    sched.every().day.at("08:10").do(run_ontology_bridge, logger=logger)
    # 매일 08:15 — 품질 진단 (브릿지 이후)
    sched.every().day.at("08:15").do(run_quality_check, logger=logger)

    # ── 텔레그램 리스너 스레드 ──
    listener = threading.Thread(target=tg_listener, args=(logger,), daemon=True)
    listener.start()

    # ── 시작 알림 ──
    jobs = sched.get_jobs()
    job_list = "\n".join(f"  • {job}" for job in jobs)
    tg_send_alert("daily", "Tracking Daemon 시작", f"등록된 스케줄:\n<pre>{job_list}</pre>")

    logger.info(f"Daemon 시작. {len(jobs)}개 스케줄 등록.")
    logger.info("텔레그램 명령어: /status /record /help")
    print(f"\n━━ Tracking Daemon ━━")
    print(f"  스케줄: {len(jobs)}개")
    for job in jobs:
        print(f"  • {job}")
    print(f"\n  텔레그램: /status /record /help")
    print(f"  종료: Ctrl+C\n")

    # ── 메인 루프 ──
    try:
        while True:
            sched.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Daemon 종료 (사용자)")
        tg_send_alert("warn", "Tracking Daemon 종료", "사용자에 의해 중단됨.")
        print("\nDaemon 종료.")


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Tracking Daemon — 순환 루프 자동 실행 + 텔레그램 알림"
    )
    parser.add_argument("--once", action="store_true",
                        help="cycle1 즉시 1회 실행 후 종료")
    parser.add_argument("--status", action="store_true",
                        help="현재 상태 조회")
    parser.add_argument("--test-tg", action="store_true",
                        help="텔레그램 연결 테스트")
    parser.add_argument("--cycle", choices=["1", "2", "3"],
                        help="특정 cycle 즉시 실행")
    parser.add_argument("--quality", action="store_true",
                        help="품질 진단 즉시 실행")
    parser.add_argument("--quality-fix", action="store_true",
                        help="품질 진단 + 자동 수정")

    args = parser.parse_args()
    logger = setup_logging()

    if args.test_tg:
        ok = tg_send("✅ Tracking Daemon 텔레그램 연결 테스트 성공!")
        print(f"텔레그램 전송: {'성공' if ok else '실패'}")
        return

    if args.status:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(TRACKING / "cycle1_daily.py"), "--status"],
            capture_output=True, text=True, timeout=30, cwd=str(TRACKING)
        )
        print(result.stdout)
        return

    if args.once:
        logger.info("━━ 1회 실행 모드 ━━")
        run_cycle1(logger, check_all=True)
        return

    if args.quality or args.quality_fix:
        import subprocess
        cmd = [sys.executable, str(TRACKING / "quality_check.py")]
        if args.quality_fix:
            cmd.append("--fix")
        result = subprocess.run(cmd, capture_output=False, timeout=120, cwd=str(TRACKING))
        return

    if args.cycle:
        if args.cycle == "1":
            run_cycle1(logger, check_all=True)
        elif args.cycle == "2":
            run_cycle2(logger)
        elif args.cycle == "3":
            run_cycle3(logger)
        return

    # 기본: daemon 모드
    run_daemon(logger)


if __name__ == "__main__":
    main()
