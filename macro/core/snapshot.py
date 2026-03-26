"""
snapshot.py — macro 스냅샷 관리자

Usage:
    python core/snapshot.py save                    # latest.json → YYYY-MM-DD.json 저장
    python core/snapshot.py delta                   # latest vs 직전 스냅샷 비교
    python core/snapshot.py delta --date 2026-03-15 # latest vs 특정 날짜 비교
    python core/snapshot.py list                    # 전체 스냅샷 목록
    python core/snapshot.py list --last 10          # 최근 10개만

기능:
    save  — indicators/latest.json을 indicators/YYYY-MM-DD.json으로 복사 + delta 계산
    delta — latest.json과 직전(또는 지정) 스냅샷 간 변화 출력
    list  — indicators/ 폴더의 모든 스냅샷 날짜순 출력
"""

import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# ── 경로 설정 ────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent.parent
INDICATORS_DIR = SCRIPT_DIR / "indicators"
LATEST_FILE = INDICATORS_DIR / "latest.json"

# ── 핵심 지표 ID ─────────────────────────────────────

CORE_IDS = (
    ["A1", "A2"]
    + [f"B{i}" for i in range(1, 6)]
    + [f"C{i}" for i in range(1, 11)]
    + [f"D{i}" for i in range(1, 11)]
)


# ── 유틸리티 ─────────────────────────────────────────

def load_json(path):
    """JSON 파일 로드."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    """JSON 파일 저장 (한글 보존, 들여쓰기 2)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_snapshots():
    """indicators/ 폴더에서 날짜 스냅샷 파일 목록 반환 (날짜순)."""
    snapshots = []
    if not INDICATORS_DIR.exists():
        return snapshots

    for f in INDICATORS_DIR.iterdir():
        if f.suffix == ".json" and f.name != "latest.json":
            # YYYY-MM-DD.json 패턴 확인
            stem = f.stem
            try:
                datetime.strptime(stem, "%Y-%m-%d")
                snapshots.append(f)
            except ValueError:
                continue

    snapshots.sort(key=lambda p: p.stem)
    return snapshots


def get_previous_snapshot(exclude_date=None):
    """가장 최근 스냅샷 경로 반환. exclude_date가 있으면 해당 날짜 제외."""
    snapshots = get_snapshots()
    if exclude_date:
        snapshots = [s for s in snapshots if s.stem != exclude_date]
    return snapshots[-1] if snapshots else None


def compute_delta(current, previous):
    """두 스냅샷 간 지표 변화 계산."""
    changes = []

    # regime 비교
    curr_regime = current.get("regime", {})
    prev_regime = previous.get("regime", {})

    if curr_regime.get("status") != prev_regime.get("status"):
        changes.append({
            "id": "REGIME",
            "field": "status",
            "prev": prev_regime.get("status"),
            "curr": curr_regime.get("status"),
            "severity": "HIGH"
        })

    for field in ("L7", "L8"):
        cv = curr_regime.get(field)
        pv = prev_regime.get(field)
        if cv is not None and pv is not None:
            diff = cv - pv
            if abs(diff) >= 0.01:
                changes.append({
                    "id": "REGIME",
                    "field": field,
                    "prev": pv,
                    "curr": cv,
                    "diff": round(diff, 3),
                    "severity": "HIGH" if abs(diff) >= 0.10 else "LOW"
                })

    # 지표 비교
    for ind_id in CORE_IDS:
        curr_ind = current.get(ind_id, {})
        prev_ind = previous.get(ind_id, {})

        curr_val = curr_ind.get("value")
        prev_val = prev_ind.get("value")

        if curr_val is None or prev_val is None:
            if curr_val != prev_val:
                changes.append({
                    "id": ind_id,
                    "name": curr_ind.get("name", prev_ind.get("name", "")),
                    "prev": prev_val,
                    "curr": curr_val,
                    "diff": None,
                    "severity": "MEDIUM"
                })
            continue

        if isinstance(curr_val, (int, float)) and isinstance(prev_val, (int, float)):
            diff = round(curr_val - prev_val, 4)
            if abs(diff) > 0:
                # 50%+ 변화 = HIGH
                pct = abs(diff / prev_val) * 100 if prev_val != 0 else 0
                severity = "HIGH" if pct >= 50 else ("MEDIUM" if pct >= 10 else "LOW")
                changes.append({
                    "id": ind_id,
                    "name": curr_ind.get("name", ""),
                    "prev": prev_val,
                    "curr": curr_val,
                    "diff": diff,
                    "pct": round(pct, 1),
                    "severity": severity
                })
        elif str(curr_val) != str(prev_val):
            changes.append({
                "id": ind_id,
                "name": curr_ind.get("name", ""),
                "prev": prev_val,
                "curr": curr_val,
                "diff": None,
                "severity": "MEDIUM"
            })

    return changes


# ── 명령어: save ──────────────────────────────────────

def cmd_save():
    """latest.json → YYYY-MM-DD.json 복사 + delta 출력."""
    if not LATEST_FILE.exists():
        print(f"오류: {LATEST_FILE} 없음")
        sys.exit(1)

    data = load_json(LATEST_FILE)
    date_str = data.get("date")
    if not date_str:
        print("오류: latest.json에 date 필드 없음")
        sys.exit(1)

    snapshot_path = INDICATORS_DIR / f"{date_str}.json"

    if snapshot_path.exists():
        print(f"⚠️  이미 존재: {snapshot_path.name}")
        print("   덮어쓰기합니다.")

    save_json(data, snapshot_path)
    print(f"✅ 스냅샷 저장: {snapshot_path.name}")

    # delta 출력
    prev = get_previous_snapshot(exclude_date=date_str)
    if prev:
        print(f"\n── 변화 (vs {prev.stem}) ──\n")
        prev_data = load_json(prev)
        changes = compute_delta(data, prev_data)
        _print_changes(changes)
    else:
        print("   (비교할 이전 스냅샷 없음)")

    return snapshot_path


# ── 명령어: delta ─────────────────────────────────────

def cmd_delta(target_date=None):
    """latest vs 이전 스냅샷 변화 출력."""
    if not LATEST_FILE.exists():
        print(f"오류: {LATEST_FILE} 없음")
        sys.exit(1)

    current = load_json(LATEST_FILE)

    if target_date:
        target_path = INDICATORS_DIR / f"{target_date}.json"
        if not target_path.exists():
            print(f"오류: 스냅샷 없음 — {target_path.name}")
            sys.exit(1)
        previous = load_json(target_path)
        prev_label = target_date
    else:
        prev_path = get_previous_snapshot()
        if not prev_path:
            print("비교할 이전 스냅샷 없음")
            sys.exit(0)
        previous = load_json(prev_path)
        prev_label = prev_path.stem

    print(f"\n{'='*60}")
    print(f"  Delta: latest ({current.get('date', '?')}) vs {prev_label}")
    print(f"{'='*60}\n")

    changes = compute_delta(current, previous)
    _print_changes(changes)


# ── 명령어: list ──────────────────────────────────────

def cmd_list(last_n=None):
    """스냅샷 목록 출력."""
    snapshots = get_snapshots()
    if not snapshots:
        print("스냅샷 없음")
        return

    if last_n:
        snapshots = snapshots[-last_n:]

    print(f"\n{'='*50}")
    print(f"  스냅샷 목록 ({len(snapshots)}개)")
    print(f"{'='*50}\n")

    for s in snapshots:
        try:
            data = load_json(s)
            regime = data.get("regime", {}).get("status", "?")
            l7 = data.get("regime", {}).get("L7", "?")
            print(f"  {s.stem}  |  {regime}  |  L7={l7}")
        except Exception:
            print(f"  {s.stem}  |  (읽기 실패)")

    print()


# ── 출력 헬퍼 ────────────────────────────────────────

def _print_changes(changes):
    """변화 목록 출력."""
    if not changes:
        print("  변화 없음")
        return

    # 심각도 순 정렬
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    changes.sort(key=lambda c: severity_order.get(c.get("severity", "LOW"), 9))

    for c in changes:
        sev = c.get("severity", "LOW")
        icon = "🔴" if sev == "HIGH" else ("🟡" if sev == "MEDIUM" else "🟢")
        ind_id = c["id"]
        name = c.get("name", "")

        if c.get("diff") is not None:
            pct_str = f" ({c['pct']:+.1f}%)" if "pct" in c else ""
            print(
                f"  {icon} {ind_id:6s} {name:20s}  "
                f"{c['prev']} → {c['curr']} (Δ{c['diff']:+}){pct_str}"
            )
        else:
            print(f"  {icon} {ind_id:6s} {c.get('field', name):20s}  {c.get('prev')} → {c.get('curr')}")

    high = sum(1 for c in changes if c.get("severity") == "HIGH")
    med = sum(1 for c in changes if c.get("severity") == "MEDIUM")
    low = sum(1 for c in changes if c.get("severity") == "LOW")
    print(f"\n  합계: {len(changes)}개 변화 (🔴{high} / 🟡{med} / 🟢{low})")


# ── 메인 ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="macro 스냅샷 관리자")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("save", help="latest.json → 날짜 스냅샷 저장")

    delta_p = sub.add_parser("delta", help="latest vs 이전 스냅샷 비교")
    delta_p.add_argument("--date", "-d", help="비교 대상 날짜 (YYYY-MM-DD)")

    list_p = sub.add_parser("list", help="스냅샷 목록")
    list_p.add_argument("--last", "-n", type=int, help="최근 N개만 표시")

    args = parser.parse_args()

    if args.command == "save":
        cmd_save()
    elif args.command == "delta":
        cmd_delta(args.date)
    elif args.command == "list":
        cmd_list(args.last)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
