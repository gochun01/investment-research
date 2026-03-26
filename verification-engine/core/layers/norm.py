"""② Norm Ground — 법규·공시 의무 충족 여부.
틀: 체크리스트 로드 + 키워드 스캔 로직. 두뇌: LLM이 문서 스캔."""

import functools
import json
from pathlib import Path
from core.models import LayerVerdict

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class NormLayer:

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _load_raw() -> str:
        return (DATA_DIR / "checklists.json").read_text(encoding="utf-8")

    @classmethod
    def load_checklist(cls, doc_type: str) -> list[dict]:
        data = json.loads(cls._load_raw())
        return data.get("norm", {}).get(doc_type, [])

    @classmethod
    def clear_cache(cls):
        cls._load_raw.cache_clear()

    @classmethod
    def scan(cls, checklist: list[dict], document_text: str) -> tuple[list[str], list[str]]:
        """체크리스트 항목을 문서에서 키워드 스캔. (matched, missed) 반환.

        ⚠ 단순 부분문자열 매칭이므로 false positive 가능:
        - "리스크"가 "리스크를 무시해도 좋다"에서도 매칭됨
        - "보유현황"이 "보유현황을 공시하지 않았다"에서도 matched 처리됨

        실제 검증에서는 LLM(프롬프트)이 문맥을 고려해 판정하므로 이 함수는
        보조적 1차 필터링 용도. 최종 판정은 LLM의 norm_check 프롬프트가 수행한다.
        """
        text_lower = document_text.lower()
        matched, missed = [], []
        for item in checklist:
            found = any(kw.lower() in text_lower for kw in item.get("scan_keywords", []))
            if found:
                matched.append(item["id"])
            else:
                missed.append(item["id"])
        return matched, missed

    @classmethod
    def judge(cls, checklist: list[dict], matched: list[str], missed: list[str]) -> str:
        """판정. 프롬프트(norm_check.md)의 에스컬레이션 규칙과 동일하게 판정한다."""
        missed_items = [i for i in checklist if i["id"] in missed]
        has_high_or_critical = any(i["severity"] in ("high", "critical") for i in missed_items)
        medium_missed_count = sum(1 for i in missed_items if i["severity"] == "medium")

        if not missed_items:
            return "🟢"
        elif has_high_or_critical:
            return "🔴"
        elif medium_missed_count >= 3:
            return "🔴"  # medium 3개+ 에스컬레이션
        elif medium_missed_count >= 1:
            return "🟡"
        else:
            return "🟢"  # low만 누락

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Norm 미적용") -> LayerVerdict:
        return LayerVerdict(layer="norm", verdict="N/A", reason=reason)
