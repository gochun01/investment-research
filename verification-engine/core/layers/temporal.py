"""④ Temporal Ground — 데이터 기준 시점과 현재 정합성.
틀: 유효 기간 규칙 + gap 계산. 두뇌: LLM이 기준 시점 추출 + 변화 판단."""

from datetime import datetime, timedelta
from core.models import LayerVerdict


class TemporalLayer:

    VALIDITY_PERIODS = {
        "equity_research": {"개별종목": 90, "매크로": 30, "섹터": 60},
        "crypto_research": {"토큰": 14, "프로토콜": 14, "매크로": 30},
        "legal_contract": {"계약": 365},
        "macro_report": {"매크로": 30, "개별지표": 14},
        "geopolitical": {"분석": 14, "매크로": 30},
    }

    @classmethod
    def calculate_gap(cls, reference_date: str) -> int:
        """기준 시점과 현재의 일수 차이."""
        try:
            ref = datetime.strptime(reference_date, "%Y-%m-%d")
            return (datetime.now() - ref).days
        except (ValueError, TypeError):
            return -1

    @classmethod
    def get_validity(cls, doc_type: str, scope: str = "매크로") -> str:
        """유효 기간 반환 (YYYY-MM-DD)."""
        periods = cls.VALIDITY_PERIODS.get(doc_type, {"default": 30})
        days = periods.get(scope, 30)
        return (datetime.now().date() + timedelta(days=days)).strftime("%Y-%m-%d")

    @classmethod
    def judge(cls, gap_days: int, material_change: bool) -> str:
        """판정."""
        if gap_days < 0:
            return "⚫"  # 기준 시점 불명
        if material_change:
            return "🔴"
        if gap_days <= 7:
            return "🟢"
        if gap_days <= 30:
            return "🟡"
        return "🔴"  # 30일 초과: 데이터 노후화

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Temporal 미적용") -> LayerVerdict:
        return LayerVerdict(layer="temporal", verdict="N/A", reason=reason)
