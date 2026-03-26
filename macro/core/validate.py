"""
validate.py — macro indicators/latest.json 검증기

Usage:
    python core/validate.py                          # 기본: indicators/latest.json
    python core/validate.py --file path/to/file.json # 지정 파일
    python core/validate.py --strict                 # 엄격 모드 (WARNING도 실패 처리)

검증 항목:
    1. Top-level 필수 필드 (date, data_basis, regime)
    2. 핵심 27개 지표 존재 (A1-A2, B1-B5, C1-C10, D1-D10)
    3. 각 지표 필수 필드 (name, source, direction; value null 시 note 필수)
    4. regime 필수 필드 (status, score, L7, L8, keystone)
    5. 데이터 신선도 (date vs 오늘)
    6. L7 범위 검증 (0~1)
    7. L7 계산 검증 (원시 데이터 가용 시)
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# ── 상수 ──────────────────────────────────────────────

CORE_INDICATORS = (
    ["A1", "A2"]
    + [f"B{i}" for i in range(1, 6)]
    + [f"C{i}" for i in range(1, 11)]
    + [f"D{i}" for i in range(1, 11)]
)

REQUIRED_TOP_LEVEL = ["date", "data_basis", "regime"]
REQUIRED_REGIME = ["status", "score", "L7", "L8", "keystone"]
REQUIRED_INDICATOR_COMMON = ["name", "source", "direction"]

# Layer별 추가 필수 필드
REQUIRED_LAYER_AB = ["value", "risk_asset", "status"]  # A, B
REQUIRED_LAYER_B_EXTRA = ["unit"]

# L7 정규화 파라미터 (RULES.md §2)
L7_WEIGHTS = {"HY": 0.30, "VIX": 0.25, "SOFR": 0.20, "MOVE": 0.15, "TED": 0.10}
L7_NORM = {
    "HY":   {"low": 250, "high": 800},
    "VIX":  {"low": 12,  "high": 45},
    "SOFR": {"gap_divisor": 50},
    "MOVE": {"low": 80,  "high": 200},
    "TED":  {"low": 10,  "high": 100},
}


# ── 결과 클래스 ──────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.errors = []    # 🔴 HIGH
        self.warnings = []  # 🟡 MEDIUM
        self.info = []      # 🟢 LOW

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self, msg):
        self.info.append(msg)

    @property
    def passed(self):
        return len(self.errors) == 0

    def summary(self):
        total = len(self.errors) + len(self.warnings) + len(self.info)
        return (
            f"검증 완료: {total}개 항목 — "
            f"🔴 {len(self.errors)} / 🟡 {len(self.warnings)} / 🟢 {len(self.info)}"
        )


# ── 검증 함수 ────────────────────────────────────────

def validate_top_level(data, result):
    """Top-level 필수 필드 검증."""
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            result.error(f"🔴 HIGH — Top-level 필수 필드 누락: '{field}'")
        elif field == "date":
            try:
                datetime.strptime(data["date"], "%Y-%m-%d")
                result.ok(f"🟢 LOW — date 형식 정상: {data['date']}")
            except ValueError:
                result.error(f"🔴 HIGH — date 형식 오류: '{data['date']}' (YYYY-MM-DD 필요)")
        elif not data[field]:
            result.error(f"🔴 HIGH — '{field}' 값이 비어 있음")
        else:
            result.ok(f"🟢 LOW — {field} 존재: {str(data[field])[:50]}")


def validate_regime(data, result):
    """regime 객체 검증."""
    regime = data.get("regime")
    if not isinstance(regime, dict):
        result.error("🔴 HIGH — regime이 객체가 아니거나 없음")
        return

    for field in REQUIRED_REGIME:
        if field not in regime:
            result.error(f"🔴 HIGH — regime 필수 필드 누락: '{field}'")
        elif field in ("L7", "L8"):
            val = regime[field]
            if not isinstance(val, (int, float)):
                result.error(f"🔴 HIGH — regime.{field}가 숫자가 아님: {val}")
            elif not (0 <= val <= 1):
                result.warn(f"🟡 MEDIUM — regime.{field} 범위 이상: {val} (0~1 기대)")
            else:
                result.ok(f"🟢 LOW — regime.{field} = {val}")
        elif field == "status":
            status = regime[field]
            valid_prefixes = ["🟢", "🟡", "🔴", "⚫"]
            if not any(status.startswith(p) for p in valid_prefixes):
                result.warn(f"🟡 MEDIUM — regime.status 형식 확인: '{status}'")
            else:
                result.ok(f"🟢 LOW — regime.status = {status}")
        else:
            if not regime[field]:
                result.warn(f"🟡 MEDIUM — regime.{field} 비어 있음")
            else:
                result.ok(f"🟢 LOW — regime.{field} 존재")


def validate_indicators(data, result):
    """핵심 27개 지표 존재 + 필수 필드 검증."""
    missing = []
    for ind_id in CORE_INDICATORS:
        if ind_id not in data:
            missing.append(ind_id)
            continue

        ind = data[ind_id]
        if not isinstance(ind, dict):
            result.error(f"🔴 HIGH — {ind_id}가 객체가 아님")
            continue

        # 공통 필수 필드
        for field in REQUIRED_INDICATOR_COMMON:
            if field not in ind:
                result.error(f"🔴 HIGH — {ind_id} 필수 필드 누락: '{field}'")

        # value가 null이면 note 필수
        if ind.get("value") is None:
            if not ind.get("note"):
                result.warn(f"🟡 MEDIUM — {ind_id} value=null이나 note 없음")

        # Layer A, B 추가 필드
        layer = ind_id[0]
        if layer in ("A", "B"):
            for field in REQUIRED_LAYER_AB:
                if field not in ind and field != "value":
                    result.warn(f"🟡 MEDIUM — {ind_id} 권장 필드 누락: '{field}'")

        # source 검증
        if "source" in ind and not ind["source"]:
            result.warn(f"🟡 MEDIUM — {ind_id} source가 비어 있음")

    if missing:
        result.error(f"🔴 HIGH — 핵심 지표 누락 ({len(missing)}개): {', '.join(missing)}")
    else:
        result.ok(f"🟢 LOW — 핵심 27개 지표 전수 존재")


def validate_freshness(data, result):
    """데이터 신선도 검증."""
    date_str = data.get("date")
    if not date_str:
        return

    try:
        data_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return  # 이미 top-level에서 검증

    today = datetime.now()
    delta = (today - data_date).days

    if delta <= 7:
        result.ok(f"🟢 LOW — 데이터 신선: {delta}일 전 ({date_str})")
    elif delta <= 14:
        result.warn(f"🟡 MEDIUM — 데이터 지연: {delta}일 전 ({date_str}) — STALE")
    else:
        result.error(f"🔴 HIGH — 데이터 만료: {delta}일 전 ({date_str}) — EXPIRED")


def validate_l7_calculation(data, result):
    """L7 계산 교차 검증 (원시 데이터 가용 시)."""
    regime = data.get("regime", {})
    reported_l7 = regime.get("L7")
    if reported_l7 is None:
        return

    # 필요한 원시 데이터 추출
    hy_val = _get_value(data, "B5")
    vix_val = _get_value(data, "C1")
    sofr_val = _get_value(data, "D6")
    dff_val = _get_value(data, "C10")
    move_val = _get_value(data, "C2")

    if None in (hy_val, vix_val, sofr_val, move_val):
        result.ok("🟢 LOW — L7 계산 검증 생략 (일부 원시 데이터 미가용)")
        return

    # 정규화 + 클리핑 [0, 1]
    def clip(x):
        return max(0.0, min(1.0, x))

    hy_n = clip((hy_val - 250) / (800 - 250))
    vix_n = clip((vix_val - 12) / (45 - 12))
    sofr_gap = abs(sofr_val - (dff_val if dff_val else sofr_val))
    sofr_n = clip(sofr_gap / 0.50)  # 50bp = 0.50%
    move_n = clip((move_val - 80) / (200 - 80))
    ted_n = 0.0  # TED 미가용 시 0

    calculated_l7 = (
        0.30 * hy_n + 0.25 * vix_n + 0.20 * sofr_n
        + 0.15 * move_n + 0.10 * ted_n
    )

    diff = abs(calculated_l7 - reported_l7)
    if diff < 0.05:
        result.ok(
            f"🟢 LOW — L7 계산 일치: 보고={reported_l7:.2f}, 계산={calculated_l7:.2f} (차이 {diff:.3f})"
        )
    elif diff < 0.10:
        result.warn(
            f"🟡 MEDIUM — L7 계산 근사: 보고={reported_l7:.2f}, 계산={calculated_l7:.2f} (차이 {diff:.3f})"
        )
    else:
        result.error(
            f"🔴 HIGH — L7 계산 불일치: 보고={reported_l7:.2f}, 계산={calculated_l7:.2f} (차이 {diff:.3f})"
        )


def validate_b_risk_asset_consistency(data, result):
    """B1~B5 risk_asset 판정과 regime.score 일관성 검증."""
    regime = data.get("regime", {})
    score_str = regime.get("score", "")

    risk_count = 0
    for i in range(1, 6):
        ind = data.get(f"B{i}", {})
        ra = ind.get("risk_asset", ind.get("status", ""))
        if ra == "✓":
            risk_count += 1
        elif ra == "△":
            risk_count += 0.5

    # score 파싱 시도
    try:
        if "/" in str(score_str):
            reported_score = float(str(score_str).split("/")[0])
        else:
            reported_score = float(score_str)
    except (ValueError, TypeError):
        result.warn(f"🟡 MEDIUM — regime.score 파싱 불가: '{score_str}'")
        return

    diff = abs(risk_count - reported_score)
    if diff <= 0.5:
        result.ok(f"🟢 LOW — B layer 점수 일치: 계산={risk_count}, 보고={reported_score}")
    else:
        result.warn(
            f"🟡 MEDIUM — B layer 점수 불일치: 계산={risk_count}, 보고={reported_score}"
        )


# ── 유틸리티 ─────────────────────────────────────────

def _get_value(data, ind_id):
    """지표에서 숫자 value 추출. 실패 시 None."""
    ind = data.get(ind_id, {})
    val = ind.get("value")
    if isinstance(val, (int, float)):
        return float(val)
    return None


# ── 메인 ─────────────────────────────────────────────

def validate(file_path, strict=False):
    """전체 검증 실행."""
    result = ValidationResult()

    # 파일 로드
    if not os.path.exists(file_path):
        result.error(f"🔴 HIGH — 파일 없음: {file_path}")
        return result

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.error(f"🔴 HIGH — JSON 파싱 실패: {e}")
        return result

    print(f"\n{'='*60}")
    print(f"  macro validate.py — {file_path}")
    print(f"{'='*60}\n")

    # 검증 실행
    validate_top_level(data, result)
    validate_regime(data, result)
    validate_indicators(data, result)
    validate_freshness(data, result)
    validate_l7_calculation(data, result)
    validate_b_risk_asset_consistency(data, result)

    # 결과 출력
    if result.errors:
        print("── 🔴 HIGH ──")
        for msg in result.errors:
            print(f"  {msg}")
        print()

    if result.warnings:
        print("── 🟡 MEDIUM ──")
        for msg in result.warnings:
            print(f"  {msg}")
        print()

    if result.info:
        print("── 🟢 LOW ──")
        for msg in result.info:
            print(f"  {msg}")
        print()

    print(f"{'='*60}")
    print(f"  {result.summary()}")
    if result.passed:
        print("  결과: ✅ PASS")
    else:
        print("  결과: ❌ FAIL")
    if strict and result.warnings:
        print("  (strict 모드: WARNING도 FAIL 처리)")
    print(f"{'='*60}\n")

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="macro latest.json 검증기")
    parser.add_argument(
        "--file", "-f",
        default=None,
        help="검증할 JSON 파일 경로 (기본: indicators/latest.json)"
    )
    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="엄격 모드: WARNING도 실패 처리"
    )
    args = parser.parse_args()

    # 기본 경로: 스크립트 위치 기준
    if args.file:
        file_path = args.file
    else:
        script_dir = Path(__file__).resolve().parent.parent
        file_path = str(script_dir / "indicators" / "latest.json")

    result = validate(file_path, strict=args.strict)

    if not result.passed:
        sys.exit(1)
    if args.strict and result.warnings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
