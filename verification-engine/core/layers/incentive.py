"""⑤ Incentive Ground — 저자·기관의 이해충돌 탐지.
틀: 체크 항목 + 판정 기준. 두뇌: LLM이 면책 조항 스캔 + DART/SEC 조회."""

from core.models import LayerVerdict


class IncentiveLayer:

    CHECK_ITEMS = {
        "equity_research": [
            "증권사-주간사/인수인 관계",
            "자기매매 부서 보유현황",
            "애널리스트 개인 보유",
        ],
        "crypto_research": [
            "저자/발행처 토큰 보유",
            "프로젝트 후원/자문 관계",
            "에어드랍/보상 수령 여부",
        ],
        "legal_contract": [
            "작성 주체의 계약 편향성",
            "일방에게 유리한 조항 구조",
        ],
        "macro_report": [
            "발행기관의 경제 전망 편향 (정부기관/중앙은행 낙관 편향)",
            "저자의 기관 포지션과 전망 일치 여부",
        ],
        "geopolitical": [
            "분석 기관의 정치적 입장/후원 관계",
            "정보 출처의 편향성 (정부 발표 vs 독립 싱크탱크)",
        ],
    }

    @classmethod
    def get_checks(cls, doc_type: str) -> list[str]:
        return cls.CHECK_ITEMS.get(doc_type, [])

    @classmethod
    def judge(cls, conflict_found: bool, disclosed: bool, info_available: bool) -> str:
        """판정."""
        if not info_available:
            return "⚫"
        if conflict_found and not disclosed:
            return "🔴"
        if conflict_found and disclosed:
            return "🟡"
        return "🟢"

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Incentive 미적용") -> LayerVerdict:
        return LayerVerdict(layer="incentive", verdict="N/A", reason=reason)
