"""⑥ Omission Ground — 빠진 리스크·반론 탐지.
틀: 체크리스트 키워드 스캔 + BBJ Break 규칙. 두뇌: LLM이 Break 생성 + 문서 대조."""

import functools
import json
from pathlib import Path
from core.models import LayerVerdict

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class OmissionLayer:

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _load_raw() -> str:
        return (DATA_DIR / "checklists.json").read_text(encoding="utf-8")

    @classmethod
    def load_checklist(cls, sector: str) -> list[dict]:
        data = json.loads(cls._load_raw())
        return data.get("omission", {}).get(sector, [])

    @classmethod
    def get_available_sectors(cls) -> list[str]:
        data = json.loads(cls._load_raw())
        return list(data.get("omission", {}).keys())

    @classmethod
    def clear_cache(cls):
        cls._load_raw.cache_clear()

    @classmethod
    def scan(cls, checklist: list[dict], document_text: str) -> tuple[list[str], list[str]]:
        """체크리스트 항목 키워드 스캔. (covered, missing) 반환.

        ⚠ 단순 부분문자열 매칭이므로 false positive 가능 (NormLayer.scan과 동일).
        실제 검증에서는 LLM(프롬프트)이 문맥을 고려해 판정하므로 이 함수는
        보조적 1차 필터링 용도. 최종 판정은 LLM의 omission_check 프롬프트가 수행한다.
        """
        text_lower = document_text.lower()
        covered, missing = [], []
        for item in checklist:
            found = any(kw.lower() in text_lower for kw in item.get("keywords", []))
            if found:
                covered.append(item["id"])
            else:
                missing.append(item["id"])
        return covered, missing

    @classmethod
    def judge(cls, checklist: list[dict], missing: list[str], bbj_breaks_unmentioned: int) -> str:
        """판정."""
        missing_items = [i for i in checklist if i["id"] in missing]
        has_critical = any(i["impact"] == "critical" for i in missing_items)
        has_high = any(i["impact"] == "high" for i in missing_items)

        if has_critical or bbj_breaks_unmentioned >= 2:
            return "🔴"
        if has_high or bbj_breaks_unmentioned >= 1:
            return "🟡"
        if not missing_items and bbj_breaks_unmentioned == 0:
            return "🟢"
        return "🟡"

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Omission 미적용") -> LayerVerdict:
        return LayerVerdict(layer="omission", verdict="N/A", reason=reason)

    # BBJ Break 규칙
    BBJ_RULES = {
        "max_breaks": 2,
        "forbidden": [
            "극단적/비현실적 시나리오",
            "문서 주제와 무관한 리스크",
            "문서가 이미 다룬 리스크",
        ],
        "ranking_criteria": "임팩트 × 발생가능성",
    }
