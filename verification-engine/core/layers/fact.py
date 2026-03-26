"""① Fact Ground — 수치·데이터를 1차 소스와 직접 비교.
틀: MCP 소스 매핑 + 판정 기준. 두뇌: LLM이 수치 추출 + 비교 서술."""

from core.models import LayerVerdict


class FactLayer:
    """MCP 소스 매핑과 판정 기준을 제공. 실제 비교는 LLM(프롬프트)이 수행."""

    # 문서 유형별 MCP 소스 매핑
    MCP_SOURCES = {
        "equity_research": [
            {"source": "DART", "coverage": "한국 기업 재무제표, 공시"},
            {"source": "SEC-EDGAR", "coverage": "미국 10-K, 10-Q"},
            {"source": "Yahoo Finance", "coverage": "주가, PER, PBR, 배당"},
            {"source": "FRED", "coverage": "금리, GDP, CPI"},
        ],
        "news_article": [
            {"source": "Yahoo Finance", "coverage": "주가, 지수, 시장 데이터 — 기사 수치 교차검증"},
            {"source": "FRED", "coverage": "금리, GDP, CPI, 환율 — 매크로 수치 교차검증"},
            {"source": "DART", "coverage": "한국 기업 재무 — 기업 실적 관련 기사 검증"},
            {"source": "Tavily/Firecrawl", "coverage": "여론조사 원문, 조사기관 신뢰도, 관련 보도"},
        ],
        "crypto_research": [
            {"source": "CoinGecko", "coverage": "토큰 가격, MCap, 거래량"},
            {"source": "DeFiLlama", "coverage": "TVL, DEX 볼륨, Fees"},
            {"source": "CoinMetrics", "coverage": "온체인 지표, MVRV, NVT"},
            {"source": "Etherscan", "coverage": "컨트랙트, 토큰 전송"},
        ],
        "legal_contract": [
            {"source": "내부 정합성", "coverage": "수수료율, 기한, 한도 — 외부 소스 불필요"},
        ],
        "macro_report": [
            {"source": "FRED", "coverage": "금리(FEDFUNDS, FEDTARMD), GDP(A191RL1Q225SBEA), CPI(CPIAUCSL), PCE(PCEPILFE), 실질금리(REAINTRATREARAT10Y), 달러지수(DTWEXBGS), 스프레드(BAMLH0A0HYM2)"},
            {"source": "Firecrawl/Tavily", "coverage": "IMF WEO 전망치(imf.org/en/Publications/WEO), OECD Economic Outlook(data-explorer.oecd.org)"},
            {"source": "Yahoo Finance", "coverage": "시장 금리, 국채 수익률, 주요 지수"},
        ],
        "geopolitical": [
            {"source": "Tavily", "coverage": "지정학 뉴스, 제재·분쟁 동향, 싱크탱크 분석"},
            {"source": "FRED", "coverage": "원유(DCOILWTICO), 천연가스(DHHNGSP), 에너지 가격 지표"},
            {"source": "Firecrawl", "coverage": "GPR Index(geopoliticalrisk.com), BGRI 스크래핑"},
        ],
    }

    # 판정 기준
    THRESHOLDS = {
        "verified": 0.02,    # ±2% 이내 → 🟢
        "flagged": 0.05,     # >5% 또는 방향 반대 → 🔴
    }

    @classmethod
    def get_sources(cls, doc_type: str) -> list[dict]:
        return cls.MCP_SOURCES.get(doc_type, cls.MCP_SOURCES["equity_research"])

    @classmethod
    def judge(cls, actual_value: float, reported_value: float,
              evidence_type: str = "fact") -> str:
        """수치 비교 → 판정.
        evidence_type이 'estimate'이면 🟢 상한을 🟡로 제한한다.
        (추정치는 1차 소스와 정확히 일치해도 미래 불확실성이 있으므로)
        evidence_type이 'survey'이면 🟢 상한을 🟡로 제한한다.
        (설문 데이터는 1차 소스 교차검증이 불가하므로)"""
        if reported_value == 0:
            return "⚫"
        diff = abs(actual_value - reported_value) / abs(reported_value)
        if diff <= cls.THRESHOLDS["verified"]:
            # estimate는 🟢 상한 제한 → 🟡 하향
            return "🟡" if evidence_type in ("estimate", "survey") else "🟢"
        elif diff <= cls.THRESHOLDS["flagged"]:
            return "🟡"
        else:
            return "🔴"

    @classmethod
    def create_na(cls, reason: str = "이 claim 유형에 Fact 미적용") -> LayerVerdict:
        return LayerVerdict(layer="fact", verdict="N/A", reason=reason)
