"""규칙 활성도 추적.

각 규칙이 실전에서 몇 번 trigger되었는지, 마지막으로 언제 trigger되었는지 추적한다.
6개월 이상 trigger 0회인 규칙은 "죽은 규칙" 후보로 식별한다.

저장: data/rule_activity.json
원칙: rules.json은 건드리지 않음. 별도 파일로 활성도만 추적."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("verification-engine.rule_tracker")

ACTIVITY_PATH = Path(__file__).parent.parent / "data" / "rule_activity.json"


def _load_activity() -> dict:
    if ACTIVITY_PATH.exists():
        return json.loads(ACTIVITY_PATH.read_text(encoding="utf-8"))
    return {}


def _save_activity(data: dict):
    ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVITY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def record_rule_activity(
    triggered_rules: list[str],
    all_applicable_rules: list[str],
    vrf_id: str,
):
    """검증에서 trigger된 규칙과 적용되었으나 trigger 안 된 규칙을 기록한다.
    verify_finalize() 후 자동 호출."""

    activity = _load_activity()
    today = datetime.now().strftime("%Y-%m-%d")

    # trigger된 규칙
    for rule_id in triggered_rules:
        # 규칙 ID에서 핵심 ID 추출 (예: "lr_031: perception_as_reality" → "lr_031")
        clean_id = rule_id.split(":")[0].strip() if ":" in rule_id else rule_id.strip()

        if clean_id not in activity:
            activity[clean_id] = {
                "trigger_count": 0,
                "applied_count": 0,
                "first_triggered": "",
                "last_triggered": "",
                "last_applied": "",
                "triggered_in": [],
            }

        entry = activity[clean_id]
        entry["trigger_count"] += 1
        entry["last_triggered"] = today
        if not entry["first_triggered"]:
            entry["first_triggered"] = today

        # 최근 5건만 유지
        entry["triggered_in"].append(vrf_id)
        entry["triggered_in"] = entry["triggered_in"][-5:]

    # 적용되었으나 trigger 안 된 규칙
    triggered_clean = set()
    for r in triggered_rules:
        triggered_clean.add(r.split(":")[0].strip() if ":" in r else r.strip())

    for rule_id in all_applicable_rules:
        clean_id = rule_id.split(":")[0].strip() if ":" in rule_id else rule_id.strip()

        if clean_id not in activity:
            activity[clean_id] = {
                "trigger_count": 0,
                "applied_count": 0,
                "first_triggered": "",
                "last_triggered": "",
                "last_applied": "",
                "triggered_in": [],
            }

        activity[clean_id]["applied_count"] += 1
        activity[clean_id]["last_applied"] = today

    _save_activity(activity)


def get_rule_activity() -> dict:
    """전체 규칙 활성도 반환."""
    return _load_activity()


def get_dead_rules(days_threshold: int = 180) -> list[dict]:
    """지정 기간 동안 한 번도 trigger되지 않은 규칙 목록.
    applied_count > 0 (적용은 됐으나) trigger_count = 0 인 규칙."""

    activity = _load_activity()
    dead = []

    for rule_id, data in activity.items():
        if data["applied_count"] > 0 and data["trigger_count"] == 0:
            dead.append({
                "rule_id": rule_id,
                "applied_count": data["applied_count"],
                "trigger_count": 0,
                "last_applied": data["last_applied"],
                "status": "never_triggered",
            })

    return dead


def get_hot_rules(min_triggers: int = 3) -> list[dict]:
    """자주 trigger되는 핵심 규칙 목록."""

    activity = _load_activity()
    hot = []

    for rule_id, data in activity.items():
        if data["trigger_count"] >= min_triggers:
            hot.append({
                "rule_id": rule_id,
                "trigger_count": data["trigger_count"],
                "applied_count": data["applied_count"],
                "trigger_rate": round(data["trigger_count"] / max(data["applied_count"], 1) * 100, 1),
                "last_triggered": data["last_triggered"],
            })

    hot.sort(key=lambda x: -x["trigger_count"])
    return hot
