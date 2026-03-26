"""③ Logic Ground — 내부 논리 모순 + KC 전제 유효성.
틀: 규칙 엔진 로드 + 심각도→판정 매핑. 두뇌: LLM이 수치 추출 + 조건 대입 + KC 추출."""

import functools
import json
from pathlib import Path
from core.models import LayerVerdict

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class LogicLayer:

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _load_raw() -> str:
        return (DATA_DIR / "rules.json").read_text(encoding="utf-8")

    @classmethod
    def load_rules(cls, doc_type: str) -> list[dict]:
        data = json.loads(cls._load_raw())
        rules = data.get(doc_type, [])
        rules.extend(data.get("common", []))
        return rules

    @classmethod
    def clear_cache(cls):
        cls._load_raw.cache_clear()

    @classmethod
    def judge(cls, triggered_rules: list[dict], kc_results: list[dict]) -> str:
        """판정.
        triggered_rules: [{"id": "lr_001", "severity": "high"}, ...]
        kc_results: [{"verdict": "🟡"}, ...]
        """
        # 규칙 위반
        has_critical = any(r.get("severity") == "critical" for r in triggered_rules)
        has_high = any(r.get("severity") == "high" for r in triggered_rules)
        medium_count = sum(1 for r in triggered_rules if r.get("severity") == "medium")

        # KC 트리거
        kc_triggered = any(kc.get("verdict") == "🔴" for kc in kc_results)
        kc_uncertain = any(kc.get("verdict") == "🟡" for kc in kc_results)

        if has_critical or kc_triggered:
            return "🔴"
        if has_high:
            return "🔴"
        if medium_count >= 2:
            return "🔴"
        if medium_count >= 1 or kc_uncertain:
            return "🟡"
        if not triggered_rules and not kc_results:
            return "🟢"
        return "🟢"

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Logic 미적용") -> LayerVerdict:
        return LayerVerdict(layer="logic", verdict="N/A", reason=reason)
