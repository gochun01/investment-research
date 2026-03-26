"""후처리 파이프라인 — 수집 완료 후 전체 도구 체인 1회 실행.

사용:
  python core/pipeline.py              # 전체 실행 (validate → audit → render → watch)
  python core/pipeline.py --adaptive   # adaptive report (자율 판단 보고서)
  python core/pipeline.py --auto-log   # + WARN/⚠ 이슈 자동 적재
  python core/pipeline.py --adaptive --auto-log  # 둘 다

실행 순서:
  1. validate.py       → 스키마 검증 (11개+ 규칙)
  2. audit.py          → Self-Audit Q1~Q5
  3. render.py 또는 render_adaptive.py → HTML 보고서 생성
  4. watch.py          → Watch 제안 출력

울타리: validate+audit = Green. render+watch = Yellow (승인 필요).
"""

import subprocess
import sys
from pathlib import Path

CORE_DIR = Path(__file__).parent
BASE_DIR = CORE_DIR.parent
PYTHON = sys.executable


def run(script: str, args: list[str] = None, label: str = "") -> int:
    """코어 스크립트 실행."""
    cmd = [PYTHON, str(CORE_DIR / script)] + (args or [])
    print(f"\n{'━' * 60}")
    print(f"  [{label}]  python core/{script} {' '.join(args or [])}")
    print(f"{'━' * 60}")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    return result.returncode


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    auto_log = "--auto-log" in flags
    adaptive = "--adaptive" in flags

    render_script = "render_adaptive.py" if adaptive else "render.py"
    render_label = "자율 판단 HTML 보고서" if adaptive else "고정 구조 HTML 보고서"

    print(f"\n{'═' * 60}")
    print(f"  reaction-monitor 후처리 파이프라인")
    if adaptive:
        print(f"  [ADAPTIVE MODE] 데이터가 보고서 구조를 결정합니다")
    print(f"{'═' * 60}")

    validate_args = ["--auto-log"] if auto_log else []
    audit_args = ["--auto-log"] if auto_log else []

    # 1. validate
    rc1 = run("validate.py", validate_args, "1/4 GREEN  스키마 검증")

    # 2. audit
    rc2 = run("audit.py", audit_args, "2/4 GREEN  Self-Audit Q1~Q5")

    # 3. render (Yellow — 파일 생성)
    rc3 = run(render_script, [], f"3/4 YELLOW {render_label}")

    # 4. watch propose (Yellow — 제안만)
    rc4 = run("watch.py", ["propose"], "4/4 YELLOW Watch 제안")

    # 요약
    print(f"\n{'═' * 60}")
    print(f"  파이프라인 완료")
    print(f"{'═' * 60}")
    results = [
        ("스키마 검증", rc1),
        ("Self-Audit", rc2),
        (render_label, rc3),
        ("Watch 제안", rc4),
    ]
    for name, rc in results:
        icon = "✅" if rc == 0 else "⚠" if rc == 1 else "❌"
        print(f"  {icon} {name}")

    # 다음 행동 안내
    print(f"\n  다음 행동:")
    print(f"  • Watch 등록: python core/watch.py register (승인 필요)")
    print(f"  • 이벤트 등록: python core/events.py create [--parent EVT-ID] (승인 필요)")
    print(f"  • 이벤트 체인: python core/events.py chain")
    print()

    return max(rc1, rc2)


if __name__ == "__main__":
    sys.exit(main())
