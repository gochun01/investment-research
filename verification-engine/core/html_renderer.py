"""검증 결과 HTML 렌더러.

result_json → 단일 파일 HTML 보고서 생성.
template-verification.html의 플레이스홀더를 실제 데이터로 치환한다.

7+1 섹션:
I.   Executive Summary (항상)
II.  6-Layer 판정 (full-only)
III. Actionable Findings (항상)
IV.  Fact Check Detail (full-only)
V.   Logic & KC (full-only)
VI.  Omission Ground (full-only)
VII. 수정 대시보드 (항상)
"""

from __future__ import annotations

import json
import html as html_mod
from datetime import datetime
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "output" / "template-verification.html"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

VERDICT_CLASS = {"🟢": "g", "🟡": "y", "🔴": "r", "⚫": "k", "N/A": "k", "": "k"}
VERDICT_LABEL = {"🟢": "VERIFIED", "🟡": "PLAUSIBLE", "🔴": "FLAGGED", "⚫": "NO BASIS", "N/A": "N/A", "": "—"}
LAYER_NAMES = {
    "fact": ("L1", "Fact Ground"),
    "norm": ("L2", "Norm Ground"),
    "logic": ("L3", "Logic Ground"),
    "temporal": ("L4", "Temporal Ground"),
    "incentive": ("L5", "Incentive Ground"),
    "omission": ("L6", "Omission Ground"),
}


def _esc(text: str) -> str:
    """HTML 이스케이프."""
    return html_mod.escape(str(text)) if text else ""


def _badge(verdict: str) -> str:
    """판정 배지 HTML."""
    cls = VERDICT_CLASS.get(verdict, "k")
    label = VERDICT_LABEL.get(verdict, verdict)
    return f'<span class="v {cls}">{verdict} {label}</span>'


class VerificationHTMLRenderer:
    """result_json → HTML 보고서 렌더러."""

    def __init__(self, result_json: dict):
        self.data = result_json
        self.meta = result_json.get("meta", {})
        self.doc = self.meta.get("document", {})
        self.claims = result_json.get("claims", [])
        self.doc_verdicts = result_json.get("document_level_verdicts", {})
        self.summary = result_json.get("summary", {})
        self.layer_verdicts = self.summary.get("layer_verdicts", {})
        self.critical_flags = self.summary.get("critical_flags", [])
        self.findings = self._generate_findings()

    def render(self) -> str:
        """메인: 완성된 HTML 문자열 반환."""
        tpl = TEMPLATE_PATH.read_text(encoding="utf-8")

        # 헤더 메타
        tpl = self._render_header(tpl)
        # 7개 섹션
        tpl = self._render_s1_summary(tpl)
        tpl = self._render_s2_layer_table(tpl)
        tpl = self._render_s3_findings(tpl)
        tpl = self._render_s4_fact_check(tpl)
        tpl = self._render_s5_logic_kc(tpl)
        tpl = self._render_s6_omission(tpl)
        tpl = self._render_s7_dashboard(tpl)
        # 푸터
        tpl = self._render_footer(tpl)

        return tpl

    def save(self, path: str = "") -> Path:
        """HTML 저장. 경로 미지정 시 자동 생성."""
        html_str = self.render()

        if path:
            out = Path(path)
        else:
            slug = self._slugify(self.doc.get("title", "untitled"))
            date_str = datetime.now().strftime("%Y-%m-%d")
            out = OUTPUT_DIR / f"{slug}-verification-{date_str}.html"

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_str, encoding="utf-8")
        return out

    # ── 헤더 ──

    def _render_header(self, tpl: str) -> str:
        title = _esc(self.doc.get("title", ""))
        doc_type = _esc(self.doc.get("document_type", ""))
        valid_until = _esc(self.summary.get("valid_until", ""))
        date = _esc(self.doc.get("date_published", datetime.now().strftime("%Y-%m-%d")))

        # 종합 판정에 따른 report-class 배경색
        worst = "🟢"
        for v in self.layer_verdicts.values():
            if v == "🔴":
                worst = "🔴"
                break
            if v == "🟡":
                worst = "🟡"
        verdict_color = {
            "🔴": "var(--red)",
            "🟡": "var(--gold)",
            "🟢": "var(--green)",
        }.get(worst, "var(--gold)")
        tpl = tpl.replace('style="background:var(--gold)">VERIFICATION REPORT',
                          f'style="background:{verdict_color}">VERIFICATION REPORT')

        tpl = tpl.replace("[TITLE]", title)
        tpl = tpl.replace("[문서 제목]", title)
        tpl = tpl.replace("[문서명]", title)
        tpl = tpl.replace("[문서 유형 설명]", f"Document Type: {doc_type}")
        tpl = tpl.replace("[DATE]", date)
        tpl = tpl.replace("[doc_type]", doc_type)
        tpl = tpl.replace("[~VALID_UNTIL]", valid_until)
        tpl = tpl.replace("[VALID_UNTIL]", valid_until)
        return tpl

    # ── Section I: Executive Summary ──

    def _render_s1_summary(self, tpl: str) -> str:
        # 최고 심각도 판정
        worst = "🟢"
        for v in self.layer_verdicts.values():
            if v == "🔴":
                worst = "🔴"
                break
            if v == "🟡":
                worst = "🟡"

        verdict_text = {
            "🟢": "전체 검증 통과 — 주요 문제 없음",
            "🟡": "조건부 수용 — 일부 수정 권고 사항 존재",
            "🔴": "주의 필요 — 사실 오류 또는 중대 누락 발견",
        }.get(worst, "판정 미완료")

        summary_html = f'<p>{_badge(worst)} <strong>{_esc(verdict_text)}</strong></p>'

        # 레이어별 요약
        summary_html += '<p style="margin-top:10px;font-size:13px;">'
        for layer, (code, name) in LAYER_NAMES.items():
            v = self.layer_verdicts.get(layer, "")
            summary_html += f'{_badge(v)} {code} '
        summary_html += '</p>'

        tpl = tpl.replace(
            '<p><strong>[전체 판정 + 요약]</strong></p>',
            summary_html
        )

        # Critical flags → alert-box
        alert_html = ""
        if self.critical_flags:
            alert_html = '<div class="alert-box"><div class="exec-label">CRITICAL FLAGS</div>'
            for flag in self.critical_flags:
                alert_html += f'<p>{_esc(flag)}</p>'
            alert_html += '</div>'

        # Finding 카운트
        red_count = sum(1 for f in self.findings if f["verdict"] == "🔴")
        yellow_count = sum(1 for f in self.findings if f["verdict"] == "🟡")
        total = len(self.findings)

        tpl = tpl.replace(
            '<p><strong>총 Finding N건</strong> — 🔴 X건 · 🟡 Y건 · ⚠️ Z건</p>',
            f'{alert_html}<p><strong>총 Finding {total}건</strong> — '
            f'🔴 {red_count}건 · 🟡 {yellow_count}건</p>'
        )

        return tpl

    # ── Section II: 6-Layer 판정 ──

    def _render_s2_layer_table(self, tpl: str) -> str:
        rows = ""
        for layer, (code, name) in LAYER_NAMES.items():
            v = self.layer_verdicts.get(layer, "")
            # 주요 노트 수집 (🔴 우선)
            notes = self._collect_layer_notes(layer)
            rows += f'<tr><td>{code}</td><td>{_esc(name)}</td><td>{_badge(v)}</td><td>{_esc(notes[:200])}</td></tr>'

        # depends_on 전파가 있으면 설명 추가
        propagation_note = ""
        for claim in self.claims:
            deps = claim.get("depends_on", [])
            if deps:
                for layer, lv in claim.get("layers", {}).items():
                    notes = lv.get("notes", "")
                    if "전제 붕괴 전파" in notes or "전파" in notes:
                        propagation_note = (
                            '<p style="font-size:12px;color:var(--dim);margin-top:8px;">'
                            '※ 일부 층의 판정이 개별 claim은 🟢이나 종합이 🟡인 경우: '
                            'depends_on 전파 규칙에 의해 의존 claim이 🔴이면 종속 claim의 판정이 최소 🟡로 격상됩니다.'
                            '</p>'
                        )
                        break
            if propagation_note:
                break

        table = f'''<div class="table-wrap"><table class="monitor-table">
<thead><tr><th>LAYER</th><th>NAME</th><th>VERDICT</th><th>KEY NOTES</th></tr></thead>
<tbody>{rows}</tbody></table></div>{propagation_note}'''

        tpl = tpl.replace('<!-- [monitor-table] -->', table)
        return tpl

    # ── Section III: Findings ──

    def _render_s3_findings(self, tpl: str) -> str:
        if not self.findings:
            cards = '<p style="color:var(--dim)">발견된 수정 사항이 없습니다.</p>'
        else:
            cards = ""
            for f in self.findings:
                cards += self._finding_card_html(f)

        tpl = tpl.replace('<!-- [finding-card 배치: 🔴→🟡→⚠️] -->', cards)
        return tpl

    # ── Section IV: Fact Check ──

    def _render_s4_fact_check(self, tpl: str) -> str:
        cards = '<div class="channel-grid">'
        for claim in self.claims:
            fact = claim.get("layers", {}).get("fact", {})
            if not fact or fact.get("verdict") == "N/A":
                continue

            v = fact.get("verdict", "")
            cls_name = {"🟢": "ch-green", "🟡": "ch-gold", "🔴": "ch-red"}.get(v, "ch-blue")
            evidence_html = ""
            for ev in fact.get("evidence", []):
                evidence_html += (
                    f'<div style="font-size:12px;margin:4px 0;">'
                    f'<strong>{_esc(ev.get("source", ""))}</strong>: {_esc(ev.get("value", ""))}'
                    f'</div>'
                )

            cards += f'''<div class="channel-card {cls_name}">
<div class="ch-header"><div class="ch-name">{_esc(claim.get("claim_id", ""))}: {_esc(claim.get("text", "")[:80])}</div>
<div class="ch-tags">{_badge(v)}</div></div>
<div class="ch-detail" style="max-height:none;padding-top:8px;">
<p>{_esc(fact.get("notes", ""))}</p>
{evidence_html}
</div><div class="ch-expand">▼ 상세 보기</div></div>'''

        cards += '</div>'
        tpl = tpl.replace('<!-- [channel-card] -->', cards)
        return tpl

    # ── Section V: Logic & KC ──

    def _render_s5_logic_kc(self, tpl: str) -> str:
        content = ""

        # KC 테이블
        kc_rows = ""
        for claim in self.claims:
            logic = claim.get("layers", {}).get("logic", {})
            for kc in logic.get("kc_extracted", []):
                kc_rows += (
                    f'<tr><td>{_esc(kc.get("kc_id", ""))}</td>'
                    f'<td>{_esc(kc.get("premise", ""))}</td>'
                    f'<td>{_esc(kc.get("current_status", ""))}</td>'
                    f'<td>{_badge(kc.get("verdict", ""))}</td></tr>'
                )

        if kc_rows:
            content += f'''<div class="subsection"><div class="subsection-title">Kill Conditions (KC)</div>
<div class="table-wrap"><table class="monitor-table">
<thead><tr><th>KC ID</th><th>PREMISE</th><th>STATUS</th><th>VERDICT</th></tr></thead>
<tbody>{kc_rows}</tbody></table></div></div>'''

        # Logic 노트
        logic_notes = ""
        for claim in self.claims:
            logic = claim.get("layers", {}).get("logic", {})
            if logic.get("notes"):
                logic_notes += (
                    f'<div class="ch-chain">'
                    f'<strong>{_esc(claim.get("claim_id", ""))}</strong>: '
                    f'{_esc(logic["notes"][:200])}'
                    f'</div>'
                )

        if logic_notes:
            content += f'<div class="subsection"><div class="subsection-title">Logic Chain Notes</div>{logic_notes}</div>'

        if not content:
            content = '<p style="color:var(--dim)">Logic/KC 데이터 없음.</p>'

        tpl = tpl.replace('<!-- [KC 체인, 규칙 위반] -->', content)
        return tpl

    # ── Section VI: Omission ──

    def _render_s6_omission(self, tpl: str) -> str:
        content = ""

        # 문서 레벨 BBJ Breaks
        doc_omission = self.doc_verdicts.get("omission", {})
        bbj_breaks = doc_omission.get("bbj_breaks", [])

        if bbj_breaks:
            content += '<div class="channel-grid">'
            for bbj in bbj_breaks:
                v = bbj.get("verdict", "🟡")
                cls_name = {"🟢": "ch-green", "🟡": "ch-gold", "🔴": "ch-red"}.get(v, "ch-blue")
                in_doc = "문서 내 언급" if bbj.get("in_document") else "문서 내 미언급"
                content += f'''<div class="channel-card {cls_name}">
<div class="ch-header"><div class="ch-name">BBJ Break</div>
<div class="ch-tags">{_badge(v)} <span class="ch-tag med">{in_doc}</span></div></div>
<p style="font-size:13.5px;color:var(--sub);margin-top:8px;">{_esc(bbj.get("break_text", ""))}</p>
</div>'''
            content += '</div>'

        # claim 레벨 omission
        for claim in self.claims:
            om = claim.get("layers", {}).get("omission", {})
            if not om or om.get("verdict") == "N/A":
                continue

            om_v = om.get("verdict", "")
            claim_bbjs = om.get("bbj_breaks", [])
            om_notes = om.get("notes", "")

            if claim_bbjs:
                for bbj in claim_bbjs:
                    # break_text 또는 break 키 모두 지원
                    break_text = bbj.get("break_text", "") or bbj.get("break", "")
                    perspective = bbj.get("perspective", "")
                    impact = bbj.get("impact", "")
                    mentioned = bbj.get("mentioned_in_doc", bbj.get("in_document", False))
                    mention_label = "문서 내 언급" if mentioned else "문서 내 미언급"
                    mention_cls = "verified" if mentioned else "high"

                    content += f'''<div class="channel-card ch-red" style="margin:8px 0;">
<div class="ch-header"><div class="ch-name">{_esc(claim.get("claim_id",""))}: BBJ Break — {_esc(perspective)}</div>
<div class="ch-tags"><span class="ch-tag {mention_cls}">{mention_label}</span> <span class="ch-tag high">Impact: {_esc(impact)}</span></div></div>
<p style="font-size:13.5px;color:var(--sub);margin-top:8px;">{_esc(break_text)}</p>
</div>'''
            elif om_notes and om_v in ("🔴", "🟡"):
                # BBJ 없지만 omission notes가 있는 경우
                cls_name = "ch-red" if om_v == "🔴" else "ch-gold"
                content += f'''<div class="channel-card {cls_name}" style="margin:8px 0;">
<div class="ch-header"><div class="ch-name">{_esc(claim.get("claim_id",""))}: Omission</div>
<div class="ch-tags">{_badge(om_v)}</div></div>
<p style="font-size:13px;color:var(--sub);margin-top:6px;">{_esc(om_notes[:300])}</p>
</div>'''

        # 문서 전체 omission notes (체크리스트 누락 등)
        doc_om_notes = doc_omission.get("notes", "")
        doc_om_v = doc_omission.get("verdict", "")
        missed = doc_omission.get("checklist_missed", [])
        if doc_om_notes and doc_om_v in ("🔴", "🟡"):
            cls_name = "ch-red" if doc_om_v == "🔴" else "ch-gold"
            missed_html = ""
            if missed:
                missed_html = '<div style="margin-top:8px;font-size:12px;"><strong>누락 항목:</strong> ' + ", ".join(_esc(m) for m in missed) + '</div>'
            content += f'''<div class="channel-card {cls_name}" style="margin:8px 0;">
<div class="ch-header"><div class="ch-name">문서 전체: Omission 종합</div>
<div class="ch-tags">{_badge(doc_om_v)}</div></div>
<p style="font-size:13px;color:var(--sub);margin-top:6px;">{_esc(doc_om_notes[:400])}</p>
{missed_html}
</div>'''

        if not content:
            content = '<p style="color:var(--dim)">Omission/BBJ Break 없음.</p>'

        tpl = tpl.replace('<!-- [BBJ Break, 생략 테이블] -->', content)
        return tpl

    # ── Section VII: 수정 대시보드 ──

    def _render_s7_dashboard(self, tpl: str) -> str:
        content = ""

        # Finding 집계 테이블
        if self.findings:
            by_type = {}
            for f in self.findings:
                et = f.get("error_type", "기타")
                by_type.setdefault(et, {"count": 0, "red": 0, "yellow": 0})
                by_type[et]["count"] += 1
                if f["verdict"] == "🔴":
                    by_type[et]["red"] += 1
                else:
                    by_type[et]["yellow"] += 1

            rows = ""
            for et, counts in by_type.items():
                rows += (
                    f'<tr><td>{_esc(et)}</td>'
                    f'<td class="val-current">{counts["count"]}</td>'
                    f'<td class="val-alert">{counts["red"]}</td>'
                    f'<td class="val-warn">{counts["yellow"]}</td></tr>'
                )

            content += f'''<div class="table-wrap"><table class="monitor-table">
<thead><tr><th>ERROR TYPE</th><th>TOTAL</th><th>🔴 RED</th><th>🟡 YELLOW</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''

        # 최종 판정
        validity = self.summary.get("validity_condition", "")
        valid_until = self.summary.get("valid_until", "")
        triggers = self.summary.get("invalidation_triggers", [])

        content += f'''<div class="exec-box" style="margin-top:20px;">
<div class="exec-label">VALIDITY</div>
<p><strong>유효기간:</strong> {_esc(valid_until)}</p>
<p><strong>조건:</strong> {_esc(validity)}</p>'''

        if triggers:
            content += '<p style="margin-top:8px;"><strong>무효화 트리거:</strong></p>'
            for t in triggers:
                content += (
                    f'<p style="font-size:12.5px;">• {_esc(t.get("event",""))} '
                    f'({_esc(t.get("expected_date",""))}) → {_esc(t.get("impact",""))}</p>'
                )
        content += '</div>'

        # disclaimer
        content += f'''<div class="key-finding" style="margin-top:16px;">
<p><strong>Disclaimer:</strong> {_esc(self.summary.get("disclaimer", ""))}</p></div>'''

        tpl = tpl.replace('<!-- [scenario-grid + monitor-table + exec-box] -->', content)
        return tpl

    # ── 푸터 ──

    def _render_footer(self, tpl: str) -> str:
        # 이미 헤더에서 [DATE], [VALID_UNTIL] 치환됨
        return tpl

    # ── Finding 생성 ──

    def _generate_findings(self) -> list[dict]:
        """claims + doc_verdicts에서 🟡/🔴 항목을 Finding Card로 변환."""
        findings = []
        idx = 1

        # claim 레벨
        for claim in self.claims:
            for layer, lv in claim.get("layers", {}).items():
                v = lv.get("verdict", "")
                if v in ("🔴", "🟡"):
                    findings.append({
                        "finding_id": f"F-{idx:03d}",
                        "layer": layer,
                        "verdict": v,
                        "claim_id": claim.get("claim_id", ""),
                        "location": claim.get("location", ""),
                        "original_text": claim.get("text", "")[:150],
                        "error_type": self._infer_error_type(layer, v, lv),
                        "evidence": lv.get("notes", "")[:200],
                        "fix_confidence": "definitive" if v == "🔴" and layer == "fact" else "recommended" if v == "🔴" else "advisory",
                        "suggested_fix": self._auto_suggest_fix(layer, v, lv, claim),
                    })
                    idx += 1

        # 문서 레벨
        for layer, lv in self.doc_verdicts.items():
            v = lv.get("verdict", "")
            if v in ("🔴", "🟡"):
                findings.append({
                    "finding_id": f"F-{idx:03d}",
                    "layer": layer,
                    "verdict": v,
                    "claim_id": "",
                    "location": "document",
                    "original_text": lv.get("notes", "")[:150],
                    "error_type": self._infer_error_type(layer, v, lv),
                    "evidence": lv.get("notes", "")[:200],
                    "fix_confidence": "recommended" if v == "🔴" else "advisory",
                    "suggested_fix": self._auto_suggest_fix(layer, v, lv, {}),
                })
                idx += 1

        # 정렬: 🔴 먼저, 그다음 🟡
        findings.sort(key=lambda f: (0 if f["verdict"] == "🔴" else 1, f["finding_id"]))
        return findings

    def _finding_card_html(self, finding: dict) -> str:
        """Finding Card HTML 생성."""
        v = finding["verdict"]
        cls_name = "f-red" if v == "🔴" else "f-gold" if v == "🟡" else "f-blue"
        conf = finding.get("fix_confidence", "advisory")
        conf_cls = {"definitive": "definitive", "recommended": "recommended", "advisory": "advisory"}.get(conf, "advisory")
        layer_code, layer_name = LAYER_NAMES.get(finding["layer"], ("?", finding["layer"]))

        fix_html = ""
        if finding.get("suggested_fix"):
            fix_html = f'''<div class="finding-fix">
<div class="finding-fix-header {conf_cls}">{conf.upper()} FIX</div>
{_esc(finding["suggested_fix"])}</div>'''

        return f'''<div class="finding-card {cls_name}">
<div class="finding-header">
<div class="finding-id">{_esc(finding["finding_id"])} · {_esc(finding.get("claim_id",""))}</div>
{_badge(v)} <span class="v k">{layer_code}</span>
</div>
<div class="finding-row"><span class="finding-label">📍</span> {_esc(finding.get("location",""))}</div>
<div class="finding-row"><span class="finding-label">📝</span> {_esc(finding.get("original_text",""))}</div>
<div class="finding-row"><span class="finding-label">🔍</span> {_esc(finding.get("evidence",""))}</div>
<div class="finding-impact">{_esc(finding.get("error_type",""))}</div>
{fix_html}
</div>'''

    # ── 헬퍼 ──

    def _collect_layer_notes(self, layer: str) -> str:
        """특정 레이어의 주요 노트 수집. 🔴 항목을 우선 표시."""
        red_notes = []
        yellow_notes = []
        # 문서 레벨
        doc_lv = self.doc_verdicts.get(layer, {})
        if doc_lv.get("notes"):
            v = doc_lv.get("verdict", "")
            if v == "🔴":
                red_notes.append(doc_lv["notes"][:120])
            elif v == "🟡":
                yellow_notes.append(doc_lv["notes"][:100])
        # claim 레벨
        for claim in self.claims:
            lv = claim.get("layers", {}).get(layer, {})
            if lv.get("notes"):
                v = lv.get("verdict", "")
                if v == "🔴":
                    red_notes.append(f'{claim.get("claim_id","")}: {lv["notes"][:100]}')
                elif v == "🟡":
                    yellow_notes.append(lv["notes"][:80])
        # 🔴 우선, 그다음 🟡 (최대 3개)
        all_notes = red_notes + yellow_notes
        return " | ".join(all_notes[:3])

    @staticmethod
    def _infer_error_type(layer: str, verdict: str, lv: dict) -> str:
        """Finding의 error_type 추론."""
        if layer == "fact":
            return "factual_error" if verdict == "🔴" else "missing_source"
        if layer == "logic":
            return "logic_gap"
        if layer == "temporal":
            return "temporal_outdated"
        if layer == "incentive":
            return "disclosure_missing"
        if layer == "omission":
            return "omission_gap"
        if layer == "norm":
            return "factual_error" if verdict == "🔴" else "missing_source"
        return "factual_error"

    @staticmethod
    def _auto_suggest_fix(layer: str, verdict: str, lv: dict, claim: dict) -> str:
        """Finding의 수정 제안을 자동 생성."""
        notes = lv.get("notes", "")
        rules = lv.get("rules_triggered", [])

        if layer == "fact" and verdict == "🔴":
            return "문서의 해당 수치를 MCP 1차 소스 값으로 정정하거나, 괴리 사유를 명시하세요."
        if layer == "fact" and verdict == "🟡":
            evidence = lv.get("evidence", [])
            if not evidence:
                return "MCP 1차 소스로 교차검증하세요. 소스 접근 불가 시 출처와 한계를 명시하세요."
            return "추가 소스로 교차검증하거나, 데이터의 한계(survey, estimate 등)를 명시하세요."

        if layer == "logic" and verdict == "🔴":
            if any("perception_as_reality" in str(r) or "lr_031" in str(r) for r in rules):
                return "설문/인식 데이터를 실제 행동의 근거로 사용하려면, 실제 자금흐름·거래량 등 실증 데이터를 함께 제시하세요."
            if any("minority_framed" in str(r) or "lr_032" in str(r) for r in rules):
                return "응답 비율이 과반 미달이면 '1위'로 표현하되, 나머지 응답 비율도 함께 제시하고 '다수'/'국민' 등 일반화 표현을 피하세요."
            if any("lr_005" in str(r) for r in rules):
                return "상방 시나리오만 제시했습니다. 하방 시나리오(리스크 요인)를 최소 1개 추가하세요."
            return "논리적 비약 또는 규칙 위반을 수정하세요. 위반된 규칙 ID의 조건을 확인하세요."

        if layer == "logic" and verdict == "🟡":
            if any("counter_trend" in str(r) or "lr_033" in str(r) for r in rules):
                return "전망과 반대되는 직근 추세를 언급하고, 왜 전망이 여전히 유효한지 설명을 추가하세요."
            return "논리 근거를 보강하거나, 불확실성을 명시하세요."

        if layer == "norm":
            missed = lv.get("checklist_missed", [])
            if missed:
                return f"누락된 항목을 보완하세요: {', '.join(str(m) for m in missed[:3])}"
            return "문서 형식 요건을 확인하고 누락 항목을 보완하세요."

        if layer == "temporal":
            return "기준 시점을 최신 데이터로 갱신하거나, 데이터 노후화 사유를 명시하세요."

        if layer == "incentive":
            return "이해충돌 가능성을 공시하거나, 독립성을 증명할 근거를 추가하세요."

        if layer == "omission":
            missed = lv.get("checklist_missed", [])
            if missed:
                return f"누락된 리스크/항목을 추가하세요: {', '.join(str(m) for m in missed[:3])}"
            bbj = lv.get("bbj_breaks", [])
            if bbj:
                unmentioned = [b for b in bbj if not b.get("mentioned_in_doc", False)]
                if unmentioned:
                    return "BBJ Break(반론 시나리오)가 문서에 언급되지 않았습니다. 해당 리스크를 추가하세요."
            return "빠진 리스크 요인을 추가하세요."

        return ""

    @staticmethod
    def _slugify(text: str) -> str:
        """한글 포함 문자열을 URL-safe slug로 변환."""
        import re
        slug = re.sub(r'[^\w가-힣-]', '-', text)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug[:50] if slug else "untitled"
