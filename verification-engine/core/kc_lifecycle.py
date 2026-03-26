"""KC (Kill Condition) 생명주기 추적.

KC의 상태를 4단계로 관리한다:
  active → approaching (gap ≤ 10%) → resolved (조건 충족) → revived (다시 미충족)

저장: data/kc_registry.json
원칙: 로직은 코드, 시각화는 Notion. JSON이 원본."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("verification-engine.kc")

KC_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "kc_registry.json"

# 상태 전이 규칙
# active → approaching: gap ≤ 10%
# approaching → resolved: 조건 충족
# active → resolved: 조건 충족 (approaching 건너뜀)
# resolved → revived: 다시 미충족 → cycle_count++
# revived → active: 자동 전이
VALID_STATUSES = {"active", "approaching", "resolved", "revived"}
VALID_ONTOLOGY_LAYERS = {"plate", "structure", "flow"}

# 온톨로지 층위 자동 추론 키워드
_PLATE_KEYWORDS = ["레짐", "패러다임", "체제", "질서", "전환기", "사이클", "regime", "paradigm", "메가트렌드", "인구", "고령화", "저출생"]
_STRUCTURE_KEYWORDS = ["공급망", "구조", "금리구조", "커브", "스프레드", "규제", "시장구조", "재편", "밸류에이션", "supply chain"]
_FLOW_KEYWORDS = ["흐름", "유입", "유출", "가격", "환율", "순매수", "거래량", "flow", "자금", "수출", "수입", "ASP"]


def _infer_ontology_layer(premise: str, indicator: str = "") -> str:
    """KC의 premise와 indicator에서 온톨로지 층위를 자동 추론."""
    text = f"{premise} {indicator}".lower()

    plate_score = sum(1 for kw in _PLATE_KEYWORDS if kw.lower() in text)
    structure_score = sum(1 for kw in _STRUCTURE_KEYWORDS if kw.lower() in text)
    flow_score = sum(1 for kw in _FLOW_KEYWORDS if kw.lower() in text)

    if plate_score > structure_score and plate_score > flow_score:
        return "plate"
    if structure_score > flow_score:
        return "structure"
    if flow_score > 0:
        return "flow"
    return "flow"  # 기본값: 대부분의 KC는 흐름 레벨


def _load_registry() -> list[dict]:
    if KC_REGISTRY_PATH.exists():
        return json.loads(KC_REGISTRY_PATH.read_text(encoding="utf-8"))
    return []


def _save_registry(data: list[dict]):
    KC_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    KC_REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def register_kc(
    kc_id: str,
    premise: str,
    indicator: str = "",
    indicator_source: str = "",
    threshold: dict | None = None,
    current_value: float | None = None,
    sector_scope: list[str] | None = None,
    ontology_layer: str = "",  # plate / structure / flow
    related_targets: list[str] | None = None,
    origin_vrf_id: str = "",
) -> dict:
    """새 KC를 등록하거나, 기존 KC를 업데이트한다."""
    registry = _load_registry()

    # 기존 KC 탐색 (kc_id 또는 premise 매칭)
    existing = None
    for entry in registry:
        if entry["kc_id"] == kc_id or entry["premise"] == premise:
            existing = entry
            break

    today = datetime.now().strftime("%Y-%m-%d")

    if existing:
        # 기존 KC 업데이트 — vrf_id 추가
        if origin_vrf_id and origin_vrf_id not in existing.get("all_vrf_ids", []):
            existing.setdefault("all_vrf_ids", []).append(origin_vrf_id)
        if current_value is not None:
            existing["current_value"] = current_value
            existing["current_value_date"] = today
            _update_status(existing)
        logger.info(f"KC 업데이트: {existing['kc_id']} → {existing['status']}")
        _save_registry(registry)
        return existing

    # 신규 KC 생성
    new_kc = {
        "kc_id": kc_id,
        "premise": premise,
        "indicator": indicator,
        "indicator_source": indicator_source,
        "threshold": threshold or {},
        "current_value": current_value,
        "current_value_date": today if current_value is not None else "",
        "status": "active",
        "trend_direction": "unknown",
        "sector_scope": sector_scope or [],
        "related_targets": related_targets or [],
        "cycle_count": 0,
        "ontology_layer": ontology_layer or _infer_ontology_layer(premise, indicator),
        "created_at": today,
        "resolved_at": "",
        "revived_at": "",
        "origin_vrf_id": origin_vrf_id,
        "all_vrf_ids": [origin_vrf_id] if origin_vrf_id else [],
    }

    if current_value is not None:
        _update_status(new_kc)

    registry.append(new_kc)
    _save_registry(registry)
    logger.info(f"KC 신규 등록: {kc_id} → {new_kc['status']}")
    return new_kc


def update_kc_value(kc_id: str, current_value: float) -> dict | None:
    """KC의 현재값을 갱신하고 상태 전이를 수행한다."""
    registry = _load_registry()

    for entry in registry:
        if entry["kc_id"] == kc_id:
            entry["current_value"] = current_value
            entry["current_value_date"] = datetime.now().strftime("%Y-%m-%d")
            _update_status(entry)
            _save_registry(registry)
            logger.info(f"KC 값 갱신: {kc_id} = {current_value} → {entry['status']}")
            return entry

    return None


def _update_status(kc: dict):
    """threshold 대비 current_value로 상태 전이."""
    threshold = kc.get("threshold", {})
    current = kc.get("current_value")
    today = datetime.now().strftime("%Y-%m-%d")

    if current is None or not threshold:
        return

    operator = threshold.get("operator", ">")
    target_value = threshold.get("value")

    if target_value is None:
        return

    # 조건 충족 여부 판정
    if operator == ">":
        condition_met = current > target_value
        gap_pct = abs(target_value - current) / abs(target_value) * 100 if target_value != 0 else 0
    elif operator == "<":
        condition_met = current < target_value
        gap_pct = abs(current - target_value) / abs(target_value) * 100 if target_value != 0 else 0
    elif operator == ">=":
        condition_met = current >= target_value
        gap_pct = abs(target_value - current) / abs(target_value) * 100 if target_value != 0 else 0
    elif operator == "<=":
        condition_met = current <= target_value
        gap_pct = abs(current - target_value) / abs(target_value) * 100 if target_value != 0 else 0
    else:
        return

    old_status = kc["status"]

    if condition_met:
        if old_status in ("active", "approaching", "revived"):
            kc["status"] = "resolved"
            kc["resolved_at"] = today
            kc["trend_direction"] = "resolved"
    else:
        if old_status == "resolved":
            # 부활
            kc["status"] = "revived"
            kc["revived_at"] = today
            kc["cycle_count"] = kc.get("cycle_count", 0) + 1
            kc["trend_direction"] = "diverging"
        elif gap_pct <= 10:
            kc["status"] = "approaching"
            kc["trend_direction"] = "approaching"
        else:
            if old_status == "revived":
                kc["status"] = "active"  # revived → active 자동 전이
            kc["trend_direction"] = "diverging" if old_status == "approaching" else "flat"

    if old_status != kc["status"]:
        logger.info(f"KC 상태 전이: {kc['kc_id']} {old_status} → {kc['status']}")


def get_active_kcs(sector: str = "") -> list[dict]:
    """활성(active/approaching/revived) KC 목록 반환."""
    registry = _load_registry()
    active_statuses = {"active", "approaching", "revived"}
    results = []
    for kc in registry:
        if kc["status"] not in active_statuses:
            continue
        if sector and sector not in kc.get("sector_scope", []):
            continue
        results.append(kc)
    return results


def get_all_kcs() -> list[dict]:
    """전체 KC 목록 반환."""
    return _load_registry()


def extract_and_register_kcs(result_json: dict, vrf_id: str):
    """검증 결과에서 KC를 추출하여 registry에 등록/업데이트한다.
    verify_finalize() 후 자동 호출."""
    claims = result_json.get("claims", [])
    doc = result_json.get("meta", {}).get("document", {})
    sector = doc.get("sector_id", "")
    target = doc.get("target_id", "")

    registered = []
    for claim in claims:
        logic = claim.get("layers", {}).get("logic", {})
        for kc in logic.get("kc_extracted", []):
            kc_id = kc.get("kc_id", "")
            if not kc_id:
                continue

            entry = register_kc(
                kc_id=kc_id,
                premise=kc.get("premise", ""),
                sector_scope=[sector] if sector else [],
                related_targets=[target] if target else [],
                origin_vrf_id=vrf_id,
            )
            registered.append(entry)

    if registered:
        logger.info(f"KC {len(registered)}건 등록/업데이트 (vrf: {vrf_id})")
    return registered
