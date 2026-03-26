"""Verification Engine 데이터 모델.
Claim, LayerVerdict, VerificationResult — 검증 파이프라인의 데이터 구조."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VERDICT_PRIORITY = {"🔴": 4, "⚫": 3, "🟡": 2, "🟢": 1, "N/A": 0}


@dataclass
class Evidence:
    source: str = ""
    query: str = ""
    value: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> dict:
        return {"source": self.source, "query": self.query, "value": self.value, "retrieved_at": self.retrieved_at}


@dataclass
class KCExtracted:
    kc_id: str = ""
    premise: str = ""
    current_status: str = ""
    verdict: str = "🟡"

    def to_dict(self) -> dict:
        return {"kc_id": self.kc_id, "premise": self.premise, "current_status": self.current_status, "verdict": self.verdict}


@dataclass
class BBJBreak:
    break_text: str = ""
    in_document: bool | str = False
    verdict: str = ""

    def to_dict(self) -> dict:
        return {"break_text": self.break_text, "in_document": self.in_document, "verdict": self.verdict}


@dataclass
class LayerVerdict:
    """단일 층의 판정 결과."""
    layer: str                          # "fact", "norm", "logic", "temporal", "incentive", "omission"
    verdict: str = ""                   # 🟢, 🟡, 🔴, ⚫, N/A, "" (미실행)
    reason: str = ""                    # N/A인 이유 (A-3 보완)
    evidence: list[dict] = field(default_factory=list)
    notes: str = ""
    # layer-specific
    checklist_matched: list[str] = field(default_factory=list)
    checklist_missed: list[str] = field(default_factory=list)
    rules_triggered: list[str] = field(default_factory=list)
    kc_extracted: list[dict] = field(default_factory=list)
    data_reference_date: str = ""
    gap_days: int = 0
    material_change: bool = False
    valid_until: str = ""
    relationships_checked: list[str] = field(default_factory=list)
    disclosure_in_document: bool = False
    checklist_result: dict = field(default_factory=dict)
    bbj_breaks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"verdict": self.verdict, "reason": self.reason, "notes": self.notes}
        if self.evidence:
            d["evidence"] = self.evidence
        if self.checklist_matched or self.checklist_missed:
            d["checklist_matched"] = self.checklist_matched
            d["checklist_missed"] = self.checklist_missed
        if self.rules_triggered:
            d["rules_triggered"] = self.rules_triggered
        if self.kc_extracted:
            d["kc_extracted"] = self.kc_extracted
        if self.data_reference_date:
            d["data_reference_date"] = self.data_reference_date
            d["gap_days"] = self.gap_days
            d["material_change"] = self.material_change
        if self.valid_until:
            d["valid_until"] = self.valid_until
        if self.relationships_checked:
            d["relationships_checked"] = self.relationships_checked
            d["disclosure_in_document"] = self.disclosure_in_document
        if self.checklist_result:
            d["checklist_result"] = self.checklist_result
        if self.bbj_breaks:
            d["bbj_breaks"] = self.bbj_breaks
        return d


@dataclass
class Claim:
    """검증 대상 단일 주장."""
    claim_id: str
    text: str
    claim_type: str                     # 수치주장, 인과주장, 예측, 사실진술, 의견, 조항
    evidence_type: str = "fact"         # fact, estimate, opinion, survey — CFA V(A) 근거유형 구분
    location: str = ""
    depends_on: list[str] = field(default_factory=list)  # C-1 보완
    layers: dict[str, LayerVerdict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "evidence_type": self.evidence_type,
            "location": self.location,
            "depends_on": self.depends_on,
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
        }


@dataclass
class DocumentMeta:
    """검증 대상 문서 메타 정보."""
    title: str = ""
    document_type: str = ""             # equity_research, crypto_research, legal_contract, fund_factsheet, regulatory_filing
    target_id: str = ""
    sector_id: str = ""
    author_id: str = ""
    institution_id: str = ""
    source_url: str = ""
    date_published: str = ""
    date_accessed: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_dict(self) -> dict:
        return {
            "title": self.title, "document_type": self.document_type,
            "target_id": self.target_id, "sector_id": self.sector_id,
            "author_id": self.author_id, "institution_id": self.institution_id,
            "source_url": self.source_url, "date_published": self.date_published,
            "date_accessed": self.date_accessed,
        }


@dataclass
class VerificationResult:
    """전체 검증 결과. E-1 보완: 문서 전체 판정과 claim별 판정 분리."""
    vrf_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    document: DocumentMeta = field(default_factory=DocumentMeta)
    # E-1: 문서 전체 레벨 판정 (②Norm, ⑤Incentive, ⑥Omission)
    document_level_verdicts: dict[str, LayerVerdict] = field(default_factory=dict)
    # claim별 판정
    claims: list[Claim] = field(default_factory=list)
    # 종합
    summary_verdicts: dict[str, str] = field(default_factory=dict)
    critical_flags: list[str] = field(default_factory=list)
    valid_until: str = ""
    validity_condition: str = ""
    invalidation_triggers: list[dict] = field(default_factory=list)  # NIST AI RMF 기반 자동 무효화 트리거
    # C-2 보완: 이전 검증 참조
    previous_verification: str = ""
    changes_since_previous: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "meta": {
                "id": self.vrf_id,
                "schema_version": "v2.0",
                "created_at": self.created_at,
                "engine_version": "6layer_v2",
                "document": self.document.to_dict(),
                "previous_verification": self.previous_verification,
            },
            "document_level_verdicts": {k: v.to_dict() for k, v in self.document_level_verdicts.items()},
            "claims": [c.to_dict() for c in self.claims],
            "summary": {
                "layer_verdicts": self.summary_verdicts,
                "critical_flags": self.critical_flags,
                "valid_until": self.valid_until,
                "validity_condition": self.validity_condition,
                "invalidation_triggers": self.invalidation_triggers,
                "disclaimer": "본 결과는 법률/투자 자문이 아님. 검토 보조용",
            },
        }

    # save() 삭제됨 — 결과는 Phase 5 HTML 보고서로 출력

    def get_json_path(self) -> str:
        """JSON 저장 경로 생성.
        예: verification_store/macro_report/20260317_vrf_20260317_143052.json"""
        doc_type = self.document.document_type or "unknown"
        date_str = datetime.now().strftime("%Y%m%d")
        return f"verification_store/{doc_type}/{date_str}_{self.vrf_id}.json"


def aggregate_verdicts(verdicts: list[str]) -> str:
    """A-2 보완: claim별 판정 → 전체 판정 집계.
    ""(미실행)과 "N/A"는 집계에서 제외한다."""
    filtered = [v for v in verdicts if v not in ("N/A", "", None)]
    if not filtered:
        return "N/A"
    return max(filtered, key=lambda v: VERDICT_PRIORITY.get(v, 0))
