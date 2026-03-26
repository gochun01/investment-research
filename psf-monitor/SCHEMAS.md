# JSON Schemas — psf-monitor 기억 계층 데이터 구조

> psf-monitor의 모든 JSON 파일 스키마 정의.
> 파일 생성/읽기 시 이 문서를 참조한다.

---

## 1. state.json (단기 기억 — 현재 관측값)

PSF 관측 완료 시 덮어쓰기. 가장 핵심적인 기억.

```json
{
  "last_updated": "2026-03-23",
  "updated_by": "psf (프로토콜 버전명)",
  "freshness": "fresh|stale|expired",
  "quality": {
    "sources_used": ["FRED", "CoinGecko", "DeFiLlama", "Tavily"],
    "sources_attempted_failed": ["CoinMetrics NUPL (403 forbidden)"],
    "mcp_count": 10,
    "estimate_count": 3,
    "mcp_ratio": 0.77,
    "note": "수집 품질 메모"
  },
  "regime": "🟢 정상 | 🟡 경계 | 🟡 경계 (강화) | 🔴 위기",

  "macro_interface": {
    "macro_date": "2026-03-22",
    "macro_regime": "🟡 Transition (3.5/5)",
    "alignment": "정상|주의|역설|이행|악화|회복|위기",
    "macro_auto_triggered": false,
    "trigger_reason": null
  },

  "observations": [
    {
      "rank": 1,
      "signal": "변화 내용 (수치 포함)",
      "source": "MCP:소스명 또는 뉴스:출처",
      "magnitude": "변동 크기 + 역사적 맥락",
      "cause": "원인 (관측 가능한 경로만, 해석 아님)",
      "path": "P→S→F 전파 경로",
      "axis_relevance": "축 관련성 (어떤 축에 어떤 영향)",
      "severity": "critical|high|medium|low"
    }
  ],

  "plates": {
    "P1_fiscal": {"signal": "🟢🟡🔴⚫", "summary": "1줄 요약"},
    "P2_geopolitics": {"signal": "🟢🟡🔴⚫", "summary": "..."},
    "P3_technology": {"signal": "🟢🟡🔴⚫", "summary": "..."},
    "P4_population": {"signal": "🟢🟡🔴⚫", "summary": "..."},
    "P5_resources": {"signal": "🟢🟡🔴⚫", "summary": "..."},
    "verdict": "안정|변동|전환"
  },

  "structure": {
    "S1": {"label": "실질금리", "value": 1.88, "direction": "→↑", "verdict": "건전|긴장|균열"},
    "S2": {"label": "HY OAS", "value": 327, "direction": "→", "verdict": "건전|긴장|균열"},
    "S3": {"label": "SOFR-FF", "value": 1, "unit": "bp", "verdict": "건전|긴장|균열"},
    "S4": {"label": "ISM PMI", "value": 49, "direction": "↓", "verdict": "건전|긴장|균열"},
    "S5": {"label": "T10Y2Y", "value": 0.51, "direction": "→", "verdict": "건전|긴장|균열"},
    "verdict": "건전|긴장|균열"
  },

  "flow": {
    "F1": {"label": "DXY", "value": 99.50, "direction": "↑", "verdict": "정체|이동|이탈"},
    "F2": {"label": "Net Liq", "value": "5.80T", "direction": "→", "verdict": "정체|이동|이탈"},
    "F3": {"label": "EM/DM", "direction": "EM약세", "verdict": "정체|이동|이탈"},
    "F4": {"label": "크립토", "btc": 70000, "tvl": "93.1B", "stablecoin": "315B", "verdict": "정체|이동|이탈|수축"},
    "F5": {"label": "VIX", "value": 26.78, "move": 108.84, "verdict": "안정|정상|경계|패닉"},
    "verdict": "정체|이동|이탈"
  },

  "links": {
    "L1": {"status": "active|inactive", "note": "..."},
    "L2": {"status": "active|inactive", "note": "..."},
    "L3": {"status": "active|inactive", "evidence": "BEI +29bp"},
    "L3_5": {"status": "active|inactive", "evidence": "Brent $107"},
    "L4": {"status": "active|inactive", "note": "..."},
    "L5": {"status": "active|inactive", "evidence": "호르무즈 최후통첩"},
    "L6": {"status": "active|inactive", "note": "..."},
    "L7_acute": {"status": "active|inactive", "note": "..."},
    "L7_chronic": {"status": "active|inactive|approaching", "note": "VIX 25+ 지속"},
    "L8": {"status": "active|inactive", "note": "..."},
    "corrflip": {"status": "active|inactive", "note": "..."}
  },

  "divergences": [
    {
      "type": "P↔S|P↔F|S↔F|F내부",
      "description": "불일치 내용",
      "severity": "high|medium|low"
    }
  ],

  "unclassified": [
    {
      "id": "UC-001",
      "signal": "설명 안 되는 신호",
      "hypotheses": ["가설1", "가설2"],
      "status": "open|resolved",
      "resolved_at": null
    }
  ],

  "axis_status": {
    "1_ai": {"status": "건재|감속|훼손", "kc": "KC 조건", "note": "..."},
    "2_energy": {"status": "건재|감속|훼손", "kc": "...", "note": "..."},
    "3_aging": {"status": "건재|감속|훼손", "kc": "...", "note": "..."},
    "4_blockchain": {"status": "건재|감속|훼손", "kc": "...", "note": "..."},
    "9_fiscal": {"status": "가속|유지|둔화", "note": "..."},
    "8_uscn": {"status": "격화|유지|완화", "note": "..."}
  },

  "next_questions": [
    {
      "id": "NQ-001",
      "question": "질문 내용",
      "deadline": "2026-03-30",
      "resolve_type": "date|condition|data|threshold",
      "resolve_condition": "해소 조건",
      "check_sources": ["Tavily", "FRED"],
      "status": "open|resolved|expired"
    }
  ],

  "accumulation": {
    "weekly": {
      "period": "2026-W12 (3/17~3/23)",
      "signal_counts": {"axis_1": 1, "axis_2": -2, "axis_4": 1, "axis_9": 2},
      "unresolved_count": 4,
      "questions_open": 4
    },
    "monthly": {
      "period": "2026-03",
      "signal_counts": {},
      "unresolved_count": 0
    }
  },

  "step6_audit": {
    "gaps_found": 5,
    "gaps_resolved": 5,
    "critical_discovery": "6단계에서 발견한 핵심 사항",
    "verdict": "Full audit supplements open-form blind spots"
  }
}
```

---

## 2. projection.json (단기 기억 — 12개월 투영)

Q Loop에서 전면 재구성. M Loop에서 확률 조정.

```json
{
  "projection_date": "2026-03-23",
  "horizon": "2026-Q2 ~ 2027-Q1",
  "next_full_review": "2026-Q2 (July)",
  "next_probability_adjust": "2026-04",

  "current_position": {
    "macro": "🟡 Transition (점수)",
    "psf": "🟡 경계 (요약)",
    "axis": "4축 건재, ⑨ 가속",
    "alignment": "macro 🟡 + PSF 🟡 = 이행"
  },

  "scenarios": [
    {
      "name": "Base Case 시나리오명",
      "probability": 0.40,
      "rationale": "시나리오 근거",
      "trigger": "분기 조건 (관측 가능, 판단 가능)",
      "quarterly": {
        "Q2_2026": {"regime": "🟡", "summary": "..."},
        "Q3_2026": {"regime": "🟡→🟢", "summary": "..."},
        "Q4_2026": {"regime": "🟢", "summary": "..."},
        "Q1_2027": {"regime": "🟢", "summary": "..."}
      },
      "asset_implications": {
        "equities": "+10~15%",
        "gold": "0~5%",
        "btc": "+25~40%",
        "bonds_10y": "3.8~4.0%"
      }
    }
  ],

  "cycle_position": {
    "economic": {"phase": "late-expansion|recession|...", "direction": "..."},
    "credit": {"phase": "...", "direction": "..."},
    "liquidity": {"phase": "...", "direction": "..."}
  },

  "axis_velocity": {
    "1_ai": {"s_curve_stage": "3-4", "12m_catalyst": "...", "speed": "가속|유지|감속"},
    "2_energy": {"s_curve_stage": "3-4", "12m_catalyst": "...", "speed": "..."},
    "3_aging": {"s_curve_stage": "4", "12m_catalyst": "...", "speed": "..."},
    "4_blockchain": {"s_curve_stage": "3", "12m_catalyst": "...", "speed": "..."}
  },

  "branch_conditions": [
    {
      "condition": "분기 조건 (관측 가능)",
      "if_met": "어떤 시나리오로 분기",
      "monitoring": "어떤 지표로 추적",
      "status": "unmet|approaching|met"
    }
  ]
}
```

---

## 3. history/YYYY-MM-DD.json (중기 기억 — 일일 스냅샷)

state.json의 그날 스냅샷 + delta_vs_prev.

```json
{
  "date": "2026-03-23",
  "source": "psf D Loop",

  "regime": "🟡 경계 (강화)",
  "macro_regime": "🟡 Transition (3.5/5)",
  "alignment": "이행+이행",

  "observations_top3": [
    {"rank": 1, "signal": "BEI +29bp", "severity": "high"},
    {"rank": 2, "signal": "호르무즈 48시간 최후통첩", "severity": "critical"},
    {"rank": 3, "signal": "DeFi TVL -7.3%", "severity": "medium"}
  ],

  "links_active": ["L3", "L3_5", "L5"],
  "divergences_count": 3,
  "unclassified_count": 3,
  "questions_open": 4,

  "axis_snapshot": {
    "1_ai": "건재", "2_energy": "건재", "3_aging": "건재",
    "4_blockchain": "건재", "9_fiscal": "가속"
  },

  "delta_vs_prev": {
    "prev_date": "2026-03-22",
    "regime_changed": false,
    "new_links": [],
    "closed_links": [],
    "notable_changes": [
      "BEI 2.34% → 2.63% (+29bp)",
      "DeFi TVL $100.4B → $93.1B (-7.3%)"
    ]
  }
}
```

---

## 4. history/YYYY-W##-summary.json (중기 기억 — 주간 요약)

W Loop 완료 시 저장. accumulation.weekly에서 추출.

```json
{
  "week": "2026-W12",
  "period": "2026-03-17 ~ 2026-03-23",
  "source": "psf W Loop",

  "regime_start": "🟡 경계",
  "regime_end": "🟡 경계 (강화)",
  "regime_changed": false,

  "signal_counts": {
    "axis_1_ai": 1,
    "axis_2_energy": -2,
    "axis_3_aging": 0,
    "axis_4_blockchain": 1,
    "axis_8_uscn": 1,
    "axis_9_fiscal": 2
  },

  "top_observations": [
    "BEI +29bp (에너지→인플레 전파 확인)",
    "호르무즈 48시간 최후통첩",
    "DeFi TVL -7.3%",
    "사우디-이란 정상화 종료"
  ],

  "questions_resolved": [],
  "questions_new": ["NQ-001", "NQ-002", "NQ-003", "NQ-004"],
  "unclassified_resolved": 0,
  "unclassified_new": 3,

  "errors_reviewed": {
    "new_errors": 0,
    "recurring_errors": [],
    "rules_added": []
  },

  "axis_psf_alignment": {
    "matrix": "축 건재 + PSF 🟡 = 감시",
    "note": "판이 축을 일시 차단. 축 자체 건재."
  }
}
```

---

## 5. history/YYYY-MM-summary.json (중기 기억 — 월간 요약)

M Loop 완료 시 저장.

```json
{
  "month": "2026-03",
  "source": "psf M Loop",

  "regime_trajectory": ["🟡 (W10)", "🟡 (W11)", "🟡 강화 (W12)", "🟡 강화 (W13)"],
  "dominant_theme": "이란-미국 전쟁 + 에너지 충격",

  "axis_monthly": {
    "1_ai": {"trend": "건재", "note": "..."},
    "2_energy": {"trend": "건재 (판 차단)", "note": "..."},
    "4_blockchain": {"trend": "건재 (규제 호재 + 가격 역풍)", "note": "..."},
    "9_fiscal": {"trend": "가속", "note": "..."}
  },

  "pipe_changes": "병목 변화 요약",
  "regime_9_update": "⑨ 재정지배 환경 변화 요약",
  "kc_validity": "감시 중인 KC가 아직 유효한가",
  "projection_adjusted": false,
  "projection_note": "확률 조정 내역 (있으면)"
}
```

---

## 6. reports/*-briefing.html (중기 기억 — 보고서)

HTML 형식. 스키마 없음 (자유 형식).
다크 테마, 720px max-width, 모바일 대응.
구조는 SKILL.md 출력 형식 참조.

---

## 7. reports/*-projection.html (중기 기억 — 투영 보고서)

Q Loop에서 생성. HTML 형식.
시나리오 비교, 사이클 포지션, 축 속도 시각화.

---

## 스키마 검증 규칙

```
state.json 필수 필드:
  ✅ last_updated (날짜)
  ✅ regime (국면 판정)
  ✅ quality.mcp_count (MCP 사용 수)
  ✅ observations (1건 이상)
  ✅ structure.S1~S5 (전부 값 존재)
  ✅ flow.F1~F5 (전부 값 존재)
  ✅ links (L1~L8 + corrflip 상태)
  ✅ next_questions (0건이어도 빈 배열)

모든 S/F Property 필수 필드:
  ✅ value 또는 "미확인 — [사유]"
  ✅ direction (↑/→/↓)
  ✅ verdict

출처 태깅:
  모든 observation.source에 "MCP:소스" 또는 "뉴스:출처" 또는 "[추정]"
  quality.mcp_ratio = mcp_count / (mcp_count + estimate_count)
  mcp_ratio < 0.5 → "[관측 품질: 낮음]" 태그 필수
```
