"""Finding Card 수정 적용 엔진.

Phase 4.5에서 생성된 Finding Card의 suggested_fix를
원본 분석 보고서에 적용하고, 버전 관리하여 저장한다.

수정 정책:
- definitive (확정): 자동 적용 (MCP 1차 소스로 확인된 팩트 수정)
- recommended (권고): 사용자 승인 시 적용
- advisory (참고): 사용자 명시 요청 시만 적용
"""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass, field
from pathlib import Path

HISTORY_DIR = Path(__file__).parent.parent / "output" / "history"


@dataclass
class FindingCard:
    """검증 과정에서 발견된 수정 제안."""
    finding_id: str            # F-001
    layer: str                 # fact, norm, logic, temporal, incentive, omission
    verdict: str               # 🟡 or 🔴
    claim_id: str = ""         # 연결된 claim ID (c001 등)
    location: str = ""         # 문서 내 위치
    original_text: str = ""    # 문제가 된 원문
    error_type: str = ""       # factual_error, missing_source, logic_gap, temporal_outdated, disclosure_missing, omission_gap
    evidence: str = ""         # 판단 근거
    fix_confidence: str = ""   # definitive, recommended, advisory
    suggested_fix: str = ""    # 수정 제안

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "layer": self.layer,
            "verdict": self.verdict,
            "claim_id": self.claim_id,
            "location": self.location,
            "original_text": self.original_text,
            "error_type": self.error_type,
            "evidence": self.evidence,
            "fix_confidence": self.fix_confidence,
            "suggested_fix": self.suggested_fix,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FindingCard":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class CorrectionEngine:
    """Finding Card를 원본 보고서에 적용하는 엔진."""

    @classmethod
    def categorize_findings(cls, findings: list[FindingCard]) -> dict:
        """Finding Card를 fix_confidence별로 분류.
        Returns: {definitive: [...], recommended: [...], advisory: [...]}"""
        result = {"definitive": [], "recommended": [], "advisory": []}
        for f in findings:
            bucket = f.fix_confidence if f.fix_confidence in result else "advisory"
            result[bucket].append(f)
        return result

    @classmethod
    def apply_corrections(
        cls,
        original_report: dict,
        findings: list[FindingCard],
        approved_ids: list[str],
        auto_apply_definitive: bool = True,
    ) -> dict:
        """수정을 원본 보고서에 적용.

        Returns: {
            corrected_report: dict,
            applied: [FindingCard.to_dict()],
            skipped: [FindingCard.to_dict()],
            corrections_log: [str],
        }
        """
        corrected = copy.deepcopy(original_report)
        applied = []
        skipped = []
        log = []
        categorized = cls.categorize_findings(findings)

        for finding in findings:
            should_apply = False

            if finding.fix_confidence == "definitive" and auto_apply_definitive:
                should_apply = True
            elif finding.finding_id in approved_ids:
                should_apply = True

            if should_apply:
                success = cls._apply_single(corrected, finding)
                if success:
                    applied.append(finding)
                    log.append(
                        f"[적용] {finding.finding_id} ({finding.fix_confidence}): "
                        f"{finding.error_type} @ {finding.claim_id or finding.location}"
                    )
                else:
                    skipped.append(finding)
                    log.append(
                        f"[실패] {finding.finding_id}: 적용 대상을 찾을 수 없음"
                    )
            else:
                skipped.append(finding)
                log.append(
                    f"[미승인] {finding.finding_id} ({finding.fix_confidence}): 승인 목록에 없음"
                )

        return {
            "corrected_report": corrected,
            "applied": [f.to_dict() for f in applied],
            "skipped": [f.to_dict() for f in skipped],
            "corrections_log": log,
        }

    @classmethod
    def _apply_single(cls, report: dict, finding: FindingCard) -> bool:
        """단일 수정을 보고서에 적용. 성공 시 True."""
        if not finding.suggested_fix:
            return False

        # 1) claim_id로 직접 찾기
        if finding.claim_id:
            claims = report.get("claims", [])
            for claim in claims:
                if claim.get("claim_id") == finding.claim_id:
                    return cls._apply_to_claim(claim, finding)

        # 2) document_level_verdicts에서 찾기
        if finding.layer in ("norm", "incentive", "omission"):
            doc_verdicts = report.get("document_level_verdicts", {})
            if finding.layer in doc_verdicts:
                lv = doc_verdicts[finding.layer]
                lv["notes"] = f"[수정됨] {finding.suggested_fix}"
                if finding.verdict == "🔴" and finding.error_type == "factual_error":
                    lv["verdict"] = "🟡"  # 팩트 수정 시 RED→YELLOW 격상
                return True

        # 3) original_text로 텍스트 검색 (폴백)
        if finding.original_text:
            return cls._text_replace_recursive(report, finding.original_text, finding.suggested_fix)

        return False

    @classmethod
    def _apply_to_claim(cls, claim: dict, finding: FindingCard) -> bool:
        """claim 딕셔너리에 수정 적용."""
        # claim text 수정
        if finding.error_type == "factual_error":
            claim["text"] = f"[수정됨] {finding.suggested_fix}"
            # 해당 layer verdict 업데이트
            layers = claim.get("layers", {})
            if finding.layer in layers:
                lv = layers[finding.layer]
                if lv.get("verdict") == "🔴":
                    lv["verdict"] = "🟡"
                lv["notes"] = f"[수정 반영] {finding.suggested_fix}"
            return True

        elif finding.error_type in ("logic_gap", "omission_gap"):
            layers = claim.get("layers", {})
            if finding.layer in layers:
                lv = layers[finding.layer]
                lv["notes"] = f"[보완됨] {lv.get('notes', '')} | {finding.suggested_fix}"
                return True

        elif finding.error_type == "missing_source":
            layers = claim.get("layers", {})
            if finding.layer in layers:
                lv = layers[finding.layer]
                lv["notes"] = f"[소스 보완] {finding.suggested_fix}"
                return True

        # 기타: notes에 추가
        layers = claim.get("layers", {})
        if finding.layer in layers:
            lv = layers[finding.layer]
            lv["notes"] = f"{lv.get('notes', '')} [수정: {finding.suggested_fix}]".strip()
            return True

        return False

    @classmethod
    def _text_replace_recursive(cls, obj: dict | list, old: str, new: str) -> bool:
        """딕셔너리/리스트를 재귀 탐색하여 텍스트 치환."""
        if isinstance(obj, dict):
            for key in obj:
                if isinstance(obj[key], str) and old in obj[key]:
                    obj[key] = obj[key].replace(old, f"[수정됨] {new}")
                    return True
                elif isinstance(obj[key], (dict, list)):
                    if cls._text_replace_recursive(obj[key], old, new):
                        return True
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    if cls._text_replace_recursive(item, old, new):
                        return True
        return False

    @classmethod
    def find_next_version(cls, vrf_id: str) -> int:
        """다음 수정 버전 번호를 결정."""
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        existing = list(HISTORY_DIR.glob(f"{vrf_id}_corrected_v*.json"))
        if not existing:
            return 1
        versions = []
        for f in existing:
            try:
                v = int(f.stem.split("_v")[-1])
                versions.append(v)
            except ValueError:
                pass
        return max(versions, default=0) + 1

    @classmethod
    def save_corrected(cls, vrf_id: str, corrected_report: dict, version: int) -> Path:
        """수정된 보고서를 저장."""
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        path = HISTORY_DIR / f"{vrf_id}_corrected_v{version}.json"
        path.write_text(
            json.dumps(corrected_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
