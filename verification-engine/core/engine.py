"""6-Layer Verification Engine — 메인 오케스트레이터.
틀(코드): 파이프라인 순서, 데이터 로딩, 집계, 저장.
두뇌(프롬프트): claim 추출, MCP 조회, 비교 서술, KC 추출, BBJ Break 생성.

이 코드는 "어떤 순서로, 어떤 데이터를 준비하여, LLM에게 무엇을 시킬지"를 정의한다.
실제 판단(LLM의 응답)은 prompts/ 폴더의 프롬프트가 유도한다."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

import logging

from core.models import (
    VerificationResult, DocumentMeta, Claim, LayerVerdict,
    aggregate_verdicts, VERDICT_PRIORITY,
)
from core.layers import (
    FactLayer, NormLayer, LogicLayer,
    TemporalLayer, IncentiveLayer, OmissionLayer,
)

logger = logging.getLogger("verification-engine")

DATA_DIR = Path(__file__).parent.parent / "data"

VALID_VERDICTS = {"🟢", "🟡", "🔴", "⚫", "N/A", ""}
VALID_LAYERS = {"fact", "norm", "logic", "temporal", "incentive", "omission"}
VALID_DOC_TYPES = {
    "equity_research", "crypto_research", "legal_contract",
    "fund_factsheet", "regulatory_filing",
    "macro_report", "geopolitical", "news_article",
}

# doc_type → 기본 sector_id 매핑.
# sector_id가 명시적으로 지정되지 않으면 이 매핑을 사용한다.
# Norm은 doc_type으로 조회하지만, Omission은 sector_id로 조회하므로 이 매핑이 필수.
DOC_TYPE_DEFAULT_SECTOR = {
    "macro_report": "매크로",
    "geopolitical": "지정학",
    "crypto_research": "크립토",
    "legal_contract": "법률_계약",
    "regulatory_filing": "산업안전",
    "news_article": "뉴스_공통",
}


class VerificationEngine:
    """6층 검증 엔진 오케스트레이터.

    사용법 (LLM이 직접 호출하는 패턴):
        engine = VerificationEngine()

        # Phase 0: 문서 메타 설정
        engine.set_document(title="...", doc_type="equity_research", ...)

        # Phase 1: claim 추가 (LLM이 추출한 claim을 등록)
        engine.add_claim("c001", "Fed 3.64%", "수치주장", location="§3")

        # Phase 2: 층별 판정 등록 (LLM이 검증한 결과를 등록)
        engine.set_claim_verdict("c001", "fact", verdict="🟢", evidence=[...])
        engine.set_claim_verdict("c001", "temporal", verdict="🟢", ...)

        # Phase 2 (문서 전체): 문서 레벨 판정 등록
        engine.set_document_verdict("norm", verdict="🟡", ...)

        # Phase 2.5: 커버리지 체크
        missing = engine.check_coverage()

        # Phase 3+4: 결과 생성 + 저장
        result = engine.finalize()
        path = engine.save()
    """

    def __init__(self):
        self._result = VerificationResult()
        self._matrix = self._load_matrix()
        self._claim_index: dict[str, int] = {}
        self._created_at = datetime.now()

    @property
    def session_age_minutes(self) -> float:
        return (datetime.now() - self._created_at).total_seconds() / 60

    # ── Phase 0: 문서 설정 ──

    def set_document(self, title: str, doc_type: str, target_id: str = "",
                     sector_id: str = "", author_id: str = "", institution_id: str = "",
                     source_url: str = "", date_published: str = "") -> DocumentMeta:
        """문서 메타 정보를 설정한다."""
        if not title.strip():
            raise ValueError("title은 비어있을 수 없습니다")
        if doc_type not in VALID_DOC_TYPES:
            raise ValueError(
                f"지원하지 않는 doc_type: '{doc_type}'. "
                f"가능한 값: {sorted(VALID_DOC_TYPES)}"
            )
        # sector_id가 비어있으면 doc_type에서 기본 매핑 적용
        effective_sector = sector_id or DOC_TYPE_DEFAULT_SECTOR.get(doc_type, "")
        self._result.document = DocumentMeta(
            title=title, document_type=doc_type, target_id=target_id,
            sector_id=effective_sector, author_id=author_id, institution_id=institution_id,
            source_url=source_url, date_published=date_published,
        )
        # vrf_id 생성 (밀리초 포함 — 동일 초 내 중복 방지)
        now = datetime.now()
        self._result.vrf_id = f"vrf_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{now.strftime('%f')[:3]}"
        return self._result.document

    # ── Phase 1: Claim 등록 ──

    def add_claim(self, claim_id: str, text: str, claim_type: str,
                  evidence_type: str = "fact", location: str = "",
                  depends_on: list[str] | None = None) -> Claim:
        """검증 대상 claim을 등록한다."""
        claim = Claim(
            claim_id=claim_id, text=text, claim_type=claim_type,
            evidence_type=evidence_type, location=location,
            depends_on=depends_on or [],
        )
        # claim_type에 따라 적용/미적용 층을 초기화
        for layer_name in ["fact", "norm", "logic", "temporal", "incentive", "omission"]:
            applies = self._matrix.get(claim_type, {}).get(layer_name, False)
            if applies:
                claim.layers[layer_name] = LayerVerdict(layer=layer_name)
            else:
                claim.layers[layer_name] = LayerVerdict(
                    layer=layer_name, verdict="N/A",
                    reason=f"{claim_type}에 {layer_name} 미적용"
                )

        self._result.claims.append(claim)
        self._claim_index[claim_id] = len(self._result.claims) - 1
        return claim

    # ── Phase 2: 판정 등록 ──

    def set_claim_verdict(self, claim_id: str, layer: str, **kwargs) -> LayerVerdict:
        """개별 claim의 특정 층 판정을 등록한다."""
        if layer not in VALID_LAYERS:
            raise ValueError(
                f"유효하지 않은 layer: '{layer}'. "
                f"가능한 값: {sorted(VALID_LAYERS)}"
            )

        verdict_val = kwargs.get("verdict", "")
        if verdict_val and verdict_val not in VALID_VERDICTS:
            raise ValueError(
                f"유효하지 않은 verdict: '{verdict_val}'. "
                f"가능한 값: {VALID_VERDICTS - {''}}"
            )

        idx = self._claim_index.get(claim_id)
        if idx is None:
            raise ValueError(f"Claim '{claim_id}'을(를) 찾을 수 없습니다")

        claim = self._result.claims[idx]
        existing = claim.layers.get(layer)
        if existing and existing.verdict == "N/A":
            logger.warning(
                f"N/A 층에 강제 판정: claim={claim_id}, layer={layer}, "
                f"verdict={verdict_val}"
            )

        lv = LayerVerdict(layer=layer, **kwargs)
        claim.layers[layer] = lv
        return lv

    def set_document_verdict(self, layer: str, **kwargs) -> LayerVerdict:
        """문서 전체 레벨 판정을 등록한다. (②Norm, ⑤Incentive, ⑥Omission)"""
        valid_doc_layers = {"norm", "incentive", "omission"}
        if layer not in valid_doc_layers:
            raise ValueError(
                f"문서 전체 레벨 판정은 {sorted(valid_doc_layers)}만 가능합니다. "
                f"받은 값: '{layer}'"
            )

        verdict_val = kwargs.get("verdict", "")
        if verdict_val and verdict_val not in VALID_VERDICTS:
            raise ValueError(
                f"유효하지 않은 verdict: '{verdict_val}'. "
                f"가능한 값: {VALID_VERDICTS - {''}}"
            )

        lv = LayerVerdict(layer=layer, **kwargs)
        self._result.document_level_verdicts[layer] = lv
        return lv

    # ── Phase 2.5: 커버리지 체크 ──

    def check_coverage(self) -> list[str]:
        """V-01~V-05 실패 방어 + 층 누락 체크. 미실행 항목 리스트 반환."""
        missing = []

        for claim in self._result.claims:
            for layer_name, lv in claim.layers.items():
                if lv.verdict == "N/A":
                    continue
                # 아직 초기 상태 (verdict가 비어있거나 기본값)
                if not lv.verdict or lv.verdict == "":
                    missing.append(f"{claim.claim_id}/{layer_name}: 미실행")

        # 문서 전체 레벨 체크
        for doc_layer in ["norm", "incentive", "omission"]:
            if doc_layer not in self._result.document_level_verdicts:
                missing.append(f"document/{doc_layer}: 미실행")

        return missing

    # ── Phase 3+4: 결과 생성 + 저장 ──

    def finalize(self) -> VerificationResult:
        """판정을 집계하고 최종 결과를 생성한다."""
        # ── 결함#7 수정: depends_on 전파 ──
        self._propagate_dependency_verdicts()

        # 층별 전체 판정 집계
        for layer_name in ["fact", "norm", "logic", "temporal", "incentive", "omission"]:
            # claim 레벨 판정 수집
            claim_verdicts = [
                c.layers[layer_name].verdict
                for c in self._result.claims
                if layer_name in c.layers
            ]
            # 문서 레벨 판정 추가
            doc_lv = self._result.document_level_verdicts.get(layer_name)
            if doc_lv:
                claim_verdicts.append(doc_lv.verdict)

            self._result.summary_verdicts[layer_name] = aggregate_verdicts(claim_verdicts)

        # critical flags 수집
        self._result.critical_flags = []
        for claim in self._result.claims:
            for lv in claim.layers.values():
                if lv.verdict == "🔴":
                    self._result.critical_flags.append(
                        f"{claim.claim_id}: {lv.notes or claim.text[:50]}"
                    )
        for layer_name, lv in self._result.document_level_verdicts.items():
            if lv.verdict == "🔴":
                self._result.critical_flags.append(f"문서/{layer_name}: {lv.notes}")

        return self._result

    def get_result_dict(self) -> dict:
        """결과를 dict로 반환한다."""
        return self._result.to_dict()

    # ── 데이터 접근 (LLM 프롬프트에서 사용) ──

    def get_fact_sources(self) -> list[dict]:
        """문서 유형에 맞는 MCP 소스 목록."""
        return FactLayer.get_sources(self._result.document.document_type)

    def get_norm_checklist(self) -> list[dict]:
        """문서 유형에 맞는 Norm 체크리스트."""
        return NormLayer.load_checklist(self._result.document.document_type)

    def get_logic_rules(self) -> list[dict]:
        """문서 유형에 맞는 Logic 규칙."""
        return LogicLayer.load_rules(self._result.document.document_type)

    def get_omission_checklist(self, sector: str = "") -> list[dict]:
        """섹터에 맞는 Omission 체크리스트."""
        s = sector or self._result.document.sector_id
        return OmissionLayer.load_checklist(s)

    def get_omission_sectors(self) -> list[str]:
        """가용한 Omission 섹터 목록."""
        return OmissionLayer.get_available_sectors()

    def get_incentive_checks(self) -> list[str]:
        """문서 유형에 맞는 Incentive 체크 항목."""
        return IncentiveLayer.get_checks(self._result.document.document_type)

    def get_claim_matrix(self) -> dict:
        """claim 유형별 적용 층 매트릭스."""
        return self._matrix

    def get_coverage_report(self) -> dict:
        """현재 doc_type/sector의 규칙·체크리스트 커버리지 보고.
        self_audit에서 도메인 커버리지 갭 보고에 사용."""
        doc_type = self._result.document.document_type
        sector = self._result.document.sector_id

        # 전용 규칙 수 (common 제외)
        rules_data = json.loads((DATA_DIR / "rules.json").read_text(encoding="utf-8"))
        dedicated_rules = len(rules_data.get(doc_type, []))
        common_rules = len(rules_data.get("common", []))

        # Norm 체크리스트
        checklists_data = json.loads((DATA_DIR / "checklists.json").read_text(encoding="utf-8"))
        norm_count = len(checklists_data.get("norm", {}).get(doc_type, []))

        # Omission 체크리스트
        omission_count = len(checklists_data.get("omission", {}).get(sector, []))

        # 커버리지 레벨 판정
        if dedicated_rules >= 3 and norm_count >= 3 and omission_count >= 5:
            level = "full"
        elif dedicated_rules >= 1 or (norm_count >= 1 and omission_count >= 1):
            level = "partial"
        else:
            level = "minimal"

        return {
            "doc_type": doc_type,
            "sector": sector,
            "coverage_level": level,
            "dedicated_rules": dedicated_rules,
            "common_rules": common_rules,
            "norm_checklist": norm_count,
            "omission_checklist": omission_count,
            "gaps": self._identify_gaps(doc_type, sector, dedicated_rules, norm_count, omission_count),
            "self_audit_minimum": {
                "requires_limitation": True,
                "requires_coverage_assessment": True,
                "requires_improvement": True,
                "v06_note": "V-06 규칙: '문제 없음' 결론 금지. 최소 1개 한계 + 커버리지 평가 + 1개 개선 권고 필수",
            },
        }

    def _identify_gaps(self, doc_type: str, sector: str,
                       rules: int, norm: int, omission: int) -> list[str]:
        gaps = []
        if rules == 0:
            gaps.append(f"전용 규칙 미구축 — {doc_type}에 common 규칙만 적용됨")
        if norm == 0:
            gaps.append(f"Norm 체크리스트 미구축 — {doc_type} 문서의 형식 요건 검사 불가")
        if omission == 0:
            gaps.append(f"Omission 체크리스트 미구축 — {sector} 섹터의 빠진 리스크 탐지가 BBJ Break에만 의존")

        # 금융 특화 갭
        financial_gaps = {
            "equity_research": ["DCF 터미널 성장률 적정성 검증 규칙 없음", "PER 밴드/EV-EBITDA 비교 규칙 없음"],
            "fund_factsheet": ["펀드 성과 평가 규칙·체크리스트 전면 미구축"],
            "regulatory_filing": ["감사보고서 분석 규칙·체크리스트 전면 미구축"],
        }
        gaps.extend(financial_gaps.get(doc_type, []))

        # 한국 시장 특화 갭
        korean_uncovered = {"2차전지_배터리", "방산", "조선", "자동차", "은행_보험", "리츠_인프라", "유통_소비재", "통신"}
        if sector in korean_uncovered:
            gaps.append(f"한국 주요 섹터 '{sector}' Omission 체크리스트 미구축")

        return gaps

    def validate_self_audit(self, audit_text: str) -> dict:
        """V-06 자기 점검 텍스트의 최소 요건 충족 여부를 검증한다."""
        missing = []

        limitation_keywords = ["한계", "limitation", "제한", "부족", "미구축"]
        if not any(kw in audit_text for kw in limitation_keywords):
            missing.append("한계/제한 사항 언급 없음")

        coverage_keywords = ["커버리지", "coverage", "범위"]
        if not any(kw in audit_text for kw in coverage_keywords):
            missing.append("커버리지 평가 없음")

        improvement_keywords = ["개선", "추가", "보완", "권고"]
        if not any(kw in audit_text for kw in improvement_keywords):
            missing.append("개선 권고 없음")

        return {"valid": len(missing) == 0, "missing": missing}

    @property
    def result(self) -> VerificationResult:
        return self._result

    # ── Internal ──

    def _propagate_dependency_verdicts(self):
        """depends_on 전파: 의존 claim이 🔴이면 종속 claim의 logic을 최소 🟡로 격상.

        예: c001("매출 10조") → fact 🔴.
            c002("매출 성장으로 반등", depends_on=["c001"]) → logic이 🟢이면 🟡로 격상.
        전제가 무너졌는데 결론만 유효한 모순을 방지한다.
        """
        for claim in self._result.claims:
            if not claim.depends_on:
                continue

            # 의존하는 claim들의 최악 판정 확인
            worst_dep_priority = 0
            worst_dep_detail = []
            for dep_id in claim.depends_on:
                dep_idx = self._claim_index.get(dep_id)
                if dep_idx is None:
                    continue
                dep_claim = self._result.claims[dep_idx]
                for layer_name, lv in dep_claim.layers.items():
                    p = VERDICT_PRIORITY.get(lv.verdict, 0)
                    if p > worst_dep_priority:
                        worst_dep_priority = p
                    if lv.verdict == "🔴":
                        worst_dep_detail.append(f"{dep_id}/{layer_name}")

            # 의존 claim에 🔴가 있으면, 종속 claim의 logic/temporal을 최소 🟡로 격상
            if worst_dep_priority >= VERDICT_PRIORITY.get("🔴", 4):
                for target_layer in ["logic", "temporal"]:
                    lv = claim.layers.get(target_layer)
                    if lv and lv.verdict == "🟢":
                        dep_note = f"[전제 붕괴 전파] 의존 claim {worst_dep_detail}이 🔴 — 전제가 무너져 🟡로 격상"
                        lv.verdict = "🟡"
                        lv.notes = f"{lv.notes} {dep_note}".strip() if lv.notes else dep_note
                        logger.info(
                            f"depends_on 전파: {claim.claim_id}/{target_layer} 🟢→🟡 "
                            f"(의존: {worst_dep_detail})"
                        )

    def _load_matrix(self) -> dict:
        path = DATA_DIR / "claim_type_matrix.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {k: v for k, v in data.items() if not k.startswith("_")}
        return {}
