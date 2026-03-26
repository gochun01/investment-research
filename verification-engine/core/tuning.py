"""미세조정 엔진 — 검증 결과와 outcome을 분석하여 규칙·체크리스트 조정을 제안한다.

4가지 미세조정:
  1. 규칙 정밀도 조정 — outcome 대비 과잉/미탐지 분석 → severity 조정 제안
  2. 매체별 검증 강도 조정 — 매체별 판정 패턴 → 검증 초점 조정 제안
  3. 수집 검색어 효과 분석 — 검증 가치가 높은/낮은 수집 경로 식별
  4. 체크리스트 가중치 조정 — trigger 빈도 + 정확도 → impact 조정 제안

저장: data/tuning_state.json
원칙: 조정 제안만 한다. 실제 반영은 사용자 승인 필수."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from collections import Counter

logger = logging.getLogger("verification-engine.tuning")

TUNING_PATH = Path(__file__).parent.parent / "data" / "tuning_state.json"
HISTORY_DIR = Path(__file__).parent.parent / "output" / "history"
RULE_ACTIVITY_PATH = Path(__file__).parent.parent / "data" / "rule_activity.json"
PATTERN_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "pattern_registry.json"


def _load_tuning() -> dict:
    if TUNING_PATH.exists():
        return json.loads(TUNING_PATH.read_text(encoding="utf-8"))
    return {"rule_accuracy": {}, "media_profile": {}, "last_tuned": ""}


def _save_tuning(data: dict):
    TUNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["last_tuned"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    TUNING_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_all_verifications() -> list[dict]:
    """모든 검증 결과 + outcome을 로드."""
    results = []
    if not HISTORY_DIR.exists():
        return results

    for f in sorted(HISTORY_DIR.glob("vrf_*.json")):
        if "_corrected_" in f.name or "_outcome" in f.name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            vrf_id = data.get("vrf_id", f.stem)
            rj = data.get("result_json", {})
            doc = rj.get("meta", {}).get("document", {})

            entry = {
                "vrf_id": vrf_id,
                "title": doc.get("title", ""),
                "doc_type": doc.get("document_type", ""),
                "author_id": doc.get("author_id", ""),
                "layer_verdicts": data.get("summary", {}).get("layer_verdicts", {}),
                "claims": rj.get("claims", []),
            }

            # outcome 매칭
            outcome_path = HISTORY_DIR / f"{vrf_id}_outcome.json"
            if outcome_path.exists():
                outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
                entry["has_outcome"] = True
                entry["outcome"] = outcome
            else:
                entry["has_outcome"] = False

            results.append(entry)
        except Exception:
            continue

    return results


def analyze_rule_accuracy() -> list[dict]:
    """규칙별 정확도 분석. outcome이 있는 검증에서 trigger된 규칙이 실제로 맞았는지."""
    verifications = _load_all_verifications()
    outcome_vfs = [v for v in verifications if v["has_outcome"]]

    if not outcome_vfs:
        return []

    # 규칙별 trigger 횟수 + outcome에서 "해당 규칙 관련 언급" 여부
    rule_stats = {}

    for v in outcome_vfs:
        outcome_notes = v["outcome"].get("notes", "").lower()
        outcome_result = v["outcome"].get("actual_result", "").lower()

        for claim in v["claims"]:
            for layer, lv in claim.get("layers", {}).items():
                for rule in lv.get("rules_triggered", []):
                    clean_id = rule.split(":")[0].strip()

                    if clean_id not in rule_stats:
                        rule_stats[clean_id] = {
                            "triggered_with_outcome": 0,
                            "mentioned_in_outcome": 0,
                            "layer": layer,
                        }

                    rule_stats[clean_id]["triggered_with_outcome"] += 1

                    # outcome notes에서 해당 규칙/층 관련 언급 여부 (간이 판단)
                    if layer in outcome_notes or clean_id in outcome_notes:
                        rule_stats[clean_id]["mentioned_in_outcome"] += 1

    suggestions = []
    for rule_id, stats in rule_stats.items():
        total = stats["triggered_with_outcome"]
        mentioned = stats["mentioned_in_outcome"]

        if total >= 3 and mentioned == 0:
            suggestions.append({
                "rule_id": rule_id,
                "type": "possible_false_positive",
                "triggered": total,
                "confirmed_by_outcome": mentioned,
                "suggestion": f"{rule_id}가 {total}회 trigger됐으나 outcome에서 0회 확인. 과잉 탐지 가능성. severity 하향 검토.",
            })
        elif total >= 3 and mentioned >= total * 0.8:
            suggestions.append({
                "rule_id": rule_id,
                "type": "high_accuracy",
                "triggered": total,
                "confirmed_by_outcome": mentioned,
                "suggestion": f"{rule_id}가 {total}회 trigger, {mentioned}회 outcome 확인. 정확도 높음. 핵심 규칙으로 유지.",
            })

    return suggestions


def analyze_media_profile() -> list[dict]:
    """매체별 검증 프로필 분석. 어떤 층에서 주로 걸리는지."""
    verifications = _load_all_verifications()

    media_stats = {}
    for v in verifications:
        author = v.get("author_id", "")
        if not author:
            continue

        if author not in media_stats:
            media_stats[author] = {
                "total": 0,
                "layer_reds": Counter(),
                "layer_yellows": Counter(),
                "rules_triggered": Counter(),
                "doc_types": Counter(),
            }

        stats = media_stats[author]
        stats["total"] += 1
        stats["doc_types"][v.get("doc_type", "unknown")] += 1

        for layer, verdict in v.get("layer_verdicts", {}).items():
            if verdict == "🔴":
                stats["layer_reds"][layer] += 1
            elif verdict == "🟡":
                stats["layer_yellows"][layer] += 1

        for claim in v["claims"]:
            for layer, lv in claim.get("layers", {}).items():
                for rule in lv.get("rules_triggered", []):
                    clean_id = rule.split(":")[0].strip()
                    stats["rules_triggered"][clean_id] += 1

    profiles = []
    for author, stats in media_stats.items():
        total = stats["total"]
        if total < 1:
            continue

        # 가장 자주 🔴인 층
        worst_layer = stats["layer_reds"].most_common(1)
        best_layers = [l for l in ["fact", "norm", "logic", "temporal", "incentive", "omission"]
                       if stats["layer_reds"].get(l, 0) == 0 and stats["layer_yellows"].get(l, 0) == 0]

        # 가장 자주 trigger되는 규칙
        top_rules = stats["rules_triggered"].most_common(3)

        profile = {
            "author": author,
            "total_verifications": total,
            "strength": f"{', '.join(best_layers)} 층에서 문제 없음" if best_layers else "모든 층에서 문제 발견",
            "weakness": f"{worst_layer[0][0]} 층에서 {worst_layer[0][1]}/{total}회 🔴" if worst_layer else "🔴 없음",
            "top_triggered_rules": [{"rule": r, "count": c} for r, c in top_rules],
            "suggestion": "",
        }

        # 검증 강도 조정 제안
        if worst_layer and worst_layer[0][1] >= total * 0.5:
            weak = worst_layer[0][0]
            profile["suggestion"] = (
                f"{author}의 문서는 {weak} 층에서 {worst_layer[0][1]}/{total}회(≥50%) 🔴. "
                f"{weak} 층 검증을 강화하고, 나머지 층은 경량화 가능."
            )
        elif not worst_layer or (worst_layer and worst_layer[0][1] == 0):
            profile["suggestion"] = (
                f"{author}의 문서는 🔴 0건. 이 매체에서 새로운 규칙이 발견될 확률이 낮음. "
                f"수집 우선순위를 낮추고 다른 매체 수집을 늘릴 것을 권고."
            )

        profiles.append(profile)

    return profiles


def analyze_collection_effectiveness() -> list[dict]:
    """수집 경로별 검증 가치 분석. 어떤 doc_type/소스에서 수집한 건이 검증 학습에 기여했는지."""
    verifications = _load_all_verifications()

    type_stats = {}
    for v in verifications:
        dt = v.get("doc_type", "unknown")
        if dt not in type_stats:
            type_stats[dt] = {
                "total": 0,
                "red_count": 0,
                "rules_triggered_total": 0,
                "unique_rules": set(),
            }

        stats = type_stats[dt]
        stats["total"] += 1

        red_layers = sum(1 for verdict in v.get("layer_verdicts", {}).values() if verdict == "🔴")
        stats["red_count"] += red_layers

        for claim in v["claims"]:
            for layer, lv in claim.get("layers", {}).items():
                for rule in lv.get("rules_triggered", []):
                    clean_id = rule.split(":")[0].strip()
                    stats["rules_triggered_total"] += 1
                    stats["unique_rules"].add(clean_id)

    effectiveness = []
    for dt, stats in type_stats.items():
        total = stats["total"]
        if total < 1:
            continue

        avg_reds = round(stats["red_count"] / total, 1)
        unique_rules = len(stats["unique_rules"])

        value = "high" if avg_reds >= 1.5 or unique_rules >= 3 else "medium" if avg_reds >= 0.5 else "low"

        effectiveness.append({
            "doc_type": dt,
            "total": total,
            "avg_reds_per_verification": avg_reds,
            "unique_rules_triggered": unique_rules,
            "learning_value": value,
            "suggestion": (
                f"학습 가치 {value}. "
                + (f"🔴 평균 {avg_reds}건/검증, 고유 규칙 {unique_rules}종 활성화. 수집 유지." if value == "high"
                   else f"🔴 평균 {avg_reds}건/검증. 수집량 유지하되 다른 하위 유형 탐색." if value == "medium"
                   else f"🔴 거의 없음. 이 유형에서 새로운 규칙이 발견될 확률 낮음. 수집 비중 축소 고려.")
            ),
        })

    effectiveness.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["learning_value"], 3))
    return effectiveness


def run_full_tuning() -> dict:
    """전체 미세조정 분석 실행."""
    rule_accuracy = analyze_rule_accuracy()
    media_profiles = analyze_media_profile()
    collection_effectiveness = analyze_collection_effectiveness()

    tuning_state = _load_tuning()
    tuning_state["rule_accuracy"] = rule_accuracy
    tuning_state["media_profiles"] = media_profiles
    tuning_state["collection_effectiveness"] = collection_effectiveness
    _save_tuning(tuning_state)

    logger.info(
        f"미세조정 분석 완료: 규칙 정확도 {len(rule_accuracy)}건, "
        f"매체 프로필 {len(media_profiles)}건, "
        f"수집 효과 {len(collection_effectiveness)}건"
    )

    return {
        "rule_accuracy": rule_accuracy,
        "media_profiles": media_profiles,
        "collection_effectiveness": collection_effectiveness,
        "total_verifications": sum(e["total"] for e in collection_effectiveness),
        "has_outcomes": any(r["triggered"] > 0 for r in rule_accuracy) if rule_accuracy else False,
    }
