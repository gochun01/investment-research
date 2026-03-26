"""패턴 등록부 — 반복 검증 실패를 건별로 누적 추적.

상태 전이:
  flag (1회) → candidate (2회) → proposed (≥3회) → promoted (규칙 추가 완료) / dismissed (기각)

저장: data/pattern_registry.json
원칙: 분석은 코드, 시각화는 Notion. JSON이 원본."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("verification-engine.pattern")

PATTERN_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "pattern_registry.json"

VALID_STATUSES = {"flag", "candidate", "proposed", "promoted", "dismissed"}
PROMOTION_THRESHOLD = 3


def _load_registry() -> list[dict]:
    if PATTERN_REGISTRY_PATH.exists():
        return json.loads(PATTERN_REGISTRY_PATH.read_text(encoding="utf-8"))
    return []


def _save_registry(data: list[dict]):
    PATTERN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PATTERN_REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def record_triggered_rules(
    vrf_id: str,
    target_id: str,
    author_id: str,
    sector_id: str,
    doc_type: str,
    triggered_rules: list[str],
) -> list[dict]:
    """검증에서 trigger된 규칙들을 패턴 레지스트리에 기록한다.
    verify_finalize() 후 자동 호출.

    Returns: 업데이트/생성된 패턴 목록 (proposed 이상이면 승격 제안 포함)"""

    if not triggered_rules:
        return []

    registry = _load_registry()
    today = datetime.now().strftime("%Y-%m-%d")
    updated_patterns = []

    for rule_id in triggered_rules:
        # 기존 패턴 탐색: 같은 규칙 + 같은 기관(또는 ALL)
        existing = None
        for entry in registry:
            matched_rules = entry.get("matched_rules", [])
            if rule_id in matched_rules:
                scope_author = entry.get("author_scope", "ALL")
                if scope_author == author_id or scope_author == "ALL":
                    existing = entry
                    break

        if existing:
            # 기존 패턴 업데이트
            existing["detection_count"] = existing.get("detection_count", 0) + 1
            existing["last_detected"] = today
            existing.setdefault("evidence_list", []).append({
                "vrf_id": vrf_id,
                "target": target_id,
                "date": today,
            })

            # 상태 전이
            count = existing["detection_count"]
            if existing["status"] not in ("promoted", "dismissed"):
                if count >= PROMOTION_THRESHOLD:
                    existing["status"] = "proposed"
                elif count >= 2:
                    existing["status"] = "candidate"

            updated_patterns.append(existing)
            logger.info(
                f"패턴 업데이트: {existing['pattern_id']} "
                f"({rule_id}) count={count} → {existing['status']}"
            )

        else:
            # 신규 패턴 생성
            pattern_id = f"pt_{len(registry) + 1:03d}"
            new_pattern = {
                "pattern_id": pattern_id,
                "pattern_type": _infer_pattern_type(rule_id),
                "description": f"{author_id} — {rule_id} trigger",
                "author_scope": author_id or "ALL",
                "sector_scope": sector_id or "ALL",
                "doc_type_scope": doc_type,
                "matched_rules": [rule_id],
                "detection_count": 1,
                "status": "flag",
                "first_detected": today,
                "last_detected": today,
                "evidence_list": [{
                    "vrf_id": vrf_id,
                    "target": target_id,
                    "date": today,
                }],
                "proposed_action": "",
                "promoted_as": "",
            }
            registry.append(new_pattern)
            updated_patterns.append(new_pattern)
            logger.info(f"패턴 신규: {pattern_id} ({rule_id}) → flag")

    _save_registry(registry)
    return updated_patterns


def get_proposed_patterns() -> list[dict]:
    """승격 대기(proposed) 패턴 목록 반환."""
    registry = _load_registry()
    return [p for p in registry if p["status"] == "proposed"]


def get_patterns_for_author(author_id: str) -> list[dict]:
    """특정 기관의 패턴 목록 반환."""
    registry = _load_registry()
    return [
        p for p in registry
        if p.get("author_scope") == author_id
        and p["status"] not in ("dismissed",)
    ]


def promote_pattern(pattern_id: str, promoted_as: str) -> dict | None:
    """패턴을 규칙으로 승격 완료 처리."""
    registry = _load_registry()
    for entry in registry:
        if entry["pattern_id"] == pattern_id:
            entry["status"] = "promoted"
            entry["promoted_as"] = promoted_as
            _save_registry(registry)
            logger.info(f"패턴 승격: {pattern_id} → {promoted_as}")
            return entry
    return None


def dismiss_pattern(pattern_id: str) -> dict | None:
    """패턴을 기각."""
    registry = _load_registry()
    for entry in registry:
        if entry["pattern_id"] == pattern_id:
            entry["status"] = "dismissed"
            _save_registry(registry)
            logger.info(f"패턴 기각: {pattern_id}")
            return entry
    return None


def get_all_patterns() -> list[dict]:
    """전체 패턴 목록 반환."""
    return _load_registry()


def _infer_pattern_type(rule_id: str) -> str:
    """규칙 ID에서 패턴 유형 추론."""
    if "lr_005" in rule_id or "omission" in rule_id.lower():
        return "omission_repeat"
    if "lr_031" in rule_id or "lr_032" in rule_id:
        return "logic_gap"
    if "lr_news" in rule_id:
        return "author_bias"
    if "lr_033" in rule_id:
        return "omission_repeat"
    return "logic_gap"


def generate_promotion_suggestions(patterns: list[dict]) -> list[dict]:
    """proposed 패턴에 대한 승격 제안 생성."""
    suggestions = []
    for p in patterns:
        if p["status"] != "proposed":
            continue

        evidence_summary = ", ".join(
            f'{e["target"]}({e["date"]})'
            for e in p.get("evidence_list", [])[-5:]
        )

        suggestions.append({
            "pattern_id": p["pattern_id"],
            "description": p.get("description", ""),
            "author_scope": p.get("author_scope", "ALL"),
            "matched_rules": p.get("matched_rules", []),
            "detection_count": p["detection_count"],
            "evidence": evidence_summary,
            "suggested_action": (
                f'verify_add_rule()로 "{p["author_scope"]}" 기관 검증 시 '
                f'{", ".join(p.get("matched_rules", []))} 자동 우선 점검 규칙 추가'
            ),
        })

    return suggestions
