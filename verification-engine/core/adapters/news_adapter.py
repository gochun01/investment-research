"""news-essence-analyzer 마크다운 출력 → claim 리스트 변환 어댑터.

세 가지 출력 형식(속보카드 / 브리프 / 풀분석)을 자동 감지하고,
검증 대상 claim을 추출하여 verify_add_claim() 호환 딕셔너리 리스트를 반환한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ── 상수 ──

EVIDENCE_MAP = {
    "MCP 확인": "fact",
    "MCP확인": "fact",
    "추론": "estimate",
    "미확인": "opinion",
}

SECTION_TO_CLAIM_TYPE = {
    "지각": "사실진술",
    "주의": "의견",
    "패턴": "사실진술",
    "추론": "인과주장",
    "인과 체인": "인과주장",
    "수혜/피해": "예측",
    "수혜": "예측",
    "피해": "예측",
    "반전": "예측",
    "KC": "예측",
    "시사점": "의견",
    "투자 시사점": "의견",
    "기억": "사실진술",
    "데이터": "수치주장",
}

DOC_TAG_TO_TYPE = {
    "기업_실적": "equity_research",
    "기술_혁신": "equity_research",
    "규제_정책": "regulatory_filing",
    "지정학": "geopolitical",
    "M&A_제휴": "equity_research",
    "시장_동향": "macro_report",
}


@dataclass
class ParsedMeta:
    """파싱된 기사 메타 정보."""
    title: str = ""
    date: str = ""
    tags: list[str] = None
    who: str = ""
    what: str = ""
    format_type: str = ""  # sokbo, brief, full

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class NewsAnalysisAdapter:
    """news-essence-analyzer 마크다운을 claim 리스트로 변환."""

    @classmethod
    def detect_format(cls, markdown: str) -> str:
        """출력 형식 감지. 단일 포맷(full)만 사용."""
        return "full"

    @classmethod
    def parse(cls, markdown: str) -> tuple[list[dict], ParsedMeta]:
        """메인 진입점. claim 리스트 + 메타 정보 반환."""
        meta = cls._extract_meta(markdown, "full")
        claims = cls._parse_full(markdown)

        # claim_id 부여
        for i, c in enumerate(claims):
            c["claim_id"] = f"c{i + 1:03d}"

        return claims, meta

    @classmethod
    def infer_doc_type(cls, markdown: str) -> str:
        """기사 성격 태그로 doc_type 추론."""
        for tag, dtype in DOC_TAG_TO_TYPE.items():
            if tag in markdown:
                return dtype
        return "macro_report"

    @classmethod
    def infer_sector(cls, markdown: str) -> str:
        """기사 내용으로 sector_id 추론."""
        sector_keywords = {
            "반도체": "반도체", "AI": "반도체", "크립토": "크립토",
            "비트코인": "크립토", "바이오": "바이오", "제약": "바이오",
            "부동산": "부동산", "금리": "매크로", "환율": "매크로",
            "스타트업": "매크로", "창업": "매크로", "VC": "매크로",
            "지정학": "지정학", "전쟁": "지정학", "관세": "지정학",
        }
        for kw, sector in sector_keywords.items():
            if kw in markdown:
                return sector
        return "매크로"

    # ── 내부: 메타 추출 ──

    @classmethod
    def _extract_meta(cls, markdown: str, fmt: str) -> ParsedMeta:
        meta = ParsedMeta(format_type=fmt)

        # 제목: # 으로 시작하는 첫 번째 줄
        title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
        if title_match:
            meta.title = title_match.group(1).strip()

        # 날짜
        date_match = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', markdown)
        if date_match:
            meta.date = date_match.group(1)

        # WHO / WHAT
        who_match = re.search(r'\*\*WHO\*\*:\s*(.+)', markdown)
        if who_match:
            meta.who = who_match.group(1).strip()
        what_match = re.search(r'\*\*WHAT\*\*:\s*(.+)', markdown)
        if what_match:
            meta.what = what_match.group(1).strip()

        # 태그
        for tag in DOC_TAG_TO_TYPE:
            if tag in markdown:
                meta.tags.append(tag)

        return meta

    # ── 내부: 풀분석 파싱 ──

    @classmethod
    def _parse_full(cls, markdown: str) -> list[dict]:
        claims = []
        sections = cls._split_sections(markdown)

        for section_name, content in sections.items():
            claim_type = cls._section_to_claim_type(section_name)
            section_claims = cls._extract_claims_from_section(content, claim_type, section_name)
            claims.extend(section_claims)

        # 테이블에서 수치주장 추출
        table_claims = cls._extract_table_claims(markdown)
        claims.extend(table_claims)

        return claims if claims else [cls._make_claim(markdown[:300], "사실진술", "fact", "전문")]

    # ── 내부: 공통 헬퍼 ──

    @classmethod
    def _split_sections(cls, markdown: str) -> dict[str, str]:
        """## 헤더로 섹션 분리."""
        sections = {}
        current = ""
        current_content = []

        for line in markdown.split('\n'):
            header_match = re.match(r'^##\s+(.+)', line)
            if header_match:
                if current and current_content:
                    sections[current] = '\n'.join(current_content)
                current = header_match.group(1).strip()
                # 콜론 뒤 부분 제거 (예: "지각: 무엇이 일어났나" → "지각")
                colon_idx = current.find(':')
                if colon_idx > 0:
                    current = current[:colon_idx].strip()
                current_content = []
            else:
                current_content.append(line)

        if current and current_content:
            sections[current] = '\n'.join(current_content)

        return sections

    @classmethod
    def _extract_claims_from_section(cls, content: str, claim_type: str, section_name: str) -> list[dict]:
        """섹션 내용에서 claim 추출."""
        claims = []

        # 인과 체인: 1차/2차/3차 블록
        if claim_type == "인과주장":
            chain_blocks = re.findall(
                r'###?\s*(1차|2차|3차|직접|간접|구조적).*?\n([\s\S]*?)(?=###?\s|$)',
                content
            )
            for label, block in chain_blocks:
                # 코드 블록 안의 체인 추출
                chain_text = re.sub(r'```\n?', '', block).strip()
                if chain_text:
                    ev_type = cls._detect_evidence_type(chain_text)
                    claims.append(cls._make_claim(
                        chain_text[:300], "인과주장", ev_type, f"인과 {label}"
                    ))

            # 코드블록이 직접 있는 경우
            if not chain_blocks:
                code_blocks = re.findall(r'```\n?([\s\S]*?)```', content)
                for block in code_blocks:
                    if block.strip():
                        ev_type = cls._detect_evidence_type(block)
                        claims.append(cls._make_claim(
                            block.strip()[:300], "인과주장", ev_type, section_name
                        ))

        # 수혜/피해 매트릭스: 테이블 행
        elif "수혜" in section_name or "피해" in section_name:
            rows = re.findall(r'\|\s*\*\*(?:수혜|피해)\*\*\s*\|(.+?)\|', content)
            for row in rows:
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if cells:
                    text = ' → '.join(cells[:3])
                    claims.append(cls._make_claim(text, "예측", "estimate", section_name))

        # 반전 탐지
        elif "반전" in section_name:
            # 멍거/수혜자/KC 블록
            sub_blocks = re.split(r'###\s+', content)
            for block in sub_blocks:
                block = block.strip()
                if not block:
                    continue
                # > 인용 블록 추출
                quotes = re.findall(r'>\s*\*\*(.+?)\*\*:?\s*([\s\S]*?)(?=\n\n|\n>|\Z)', block)
                for label, text in quotes:
                    combined = f"{label}: {text.strip()[:200]}"
                    claims.append(cls._make_claim(combined, "예측", "estimate", f"반전/{label}"))

                if not quotes:
                    # > 블록 전체
                    quote_text = re.findall(r'>\s*(.+)', block)
                    if quote_text:
                        full_text = ' '.join(q.strip() for q in quote_text)[:300]
                        claims.append(cls._make_claim(full_text, "예측", "estimate", section_name))

        # KC
        elif "KC" in section_name:
            items = re.findall(r'\d+\.\s*\*\*(.+?)\*\*:?\s*(.*)', content)
            for label, text in items:
                claims.append(cls._make_claim(
                    f"{label}: {text.strip()}"[:200], "예측", "estimate", "KC"
                ))

        # 일반 텍스트 섹션: bullet points와 bold 문장
        else:
            # - **WHO**: / - **WHAT**: 패턴
            labeled = re.findall(r'-\s*\*\*(\w+)\*\*:\s*(.+)', content)
            for label, text in labeled:
                if label in ("WHO", "WHAT", "WHY", "SIGNIFICANCE"):
                    claims.append(cls._make_claim(
                        text.strip()[:200], "사실진술",
                        cls._detect_evidence_type(text), section_name
                    ))

            # 일반 bullet
            if not labeled:
                bullets = re.findall(r'^[-*]\s+(.{20,})', content, re.MULTILINE)
                for b in bullets[:5]:  # 최대 5개
                    claims.append(cls._make_claim(
                        b.strip()[:200], claim_type,
                        cls._detect_evidence_type(b), section_name
                    ))

        return claims

    @classmethod
    def _extract_table_claims(cls, markdown: str) -> list[dict]:
        """마크다운 테이블에서 수치가 포함된 행을 수치주장으로 추출."""
        claims = []
        # 테이블 행 패턴: | ... | 숫자 | ...
        rows = re.findall(r'\|(.+)\|', markdown)
        for row in rows:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            # 헤더행/구분행 스킵
            if not cells or all(c.startswith('-') for c in cells):
                continue
            # 숫자가 포함된 행만
            has_number = any(re.search(r'[\d,]+\.?\d*[%조억만건]', c) for c in cells)
            if has_number and len(cells) >= 2:
                text = ' | '.join(cells[:4])
                ev_type = cls._detect_evidence_type(text)
                claims.append(cls._make_claim(text[:200], "수치주장", ev_type, "데이터 테이블"))

        return claims[:10]  # 최대 10개

    @classmethod
    def _detect_evidence_type(cls, text: str) -> str:
        """텍스트 내 근거 라벨 감지."""
        for label, ev_type in EVIDENCE_MAP.items():
            if label in text:
                return ev_type
        return "estimate"  # 기본값

    @classmethod
    def _section_to_claim_type(cls, section_name: str) -> str:
        """섹션 이름 → claim_type 매핑."""
        for key, ctype in SECTION_TO_CLAIM_TYPE.items():
            if key in section_name:
                return ctype
        return "의견"

    @classmethod
    def _make_claim(cls, text: str, claim_type: str, evidence_type: str, location: str) -> dict:
        """claim 딕셔너리 생성."""
        # 마크다운 강조 제거
        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        clean = re.sub(r'\*(.+?)\*', r'\1', clean)
        clean = clean.strip()

        return {
            "claim_id": "",  # 나중에 부여
            "text": clean,
            "claim_type": claim_type,
            "evidence_type": evidence_type,
            "location": location,
            "depends_on": [],
        }
