# Stereo Analyzer — JSON 스키마 정의

> 분석 결과의 구조를 정의한다. 코드(render_adaptive.py)와 기억(history/)이 이 스키마를 따른다.

---

## 1. 분석 결과 스키마 (analysis.json)

하나의 분석 세션이 완료되면 이 구조로 저장된다.

```json
{
  "id": "SA-YYYYMMDD-NNN",
  "date": "2026-03-25",
  "version": "2.0",

  "input": {
    "type": "url|text|keyword|question",
    "content": "원본 입력 텍스트 또는 URL",
    "source_urls": ["https://..."],
    "collected_articles": [
      {
        "title": "기사 제목",
        "url": "https://...",
        "source": "언론사명",
        "date": "2026-03-25",
        "method": "firecrawl|tavily|manual"
      }
    ]
  },

  "pre_read": {
    "type": "POLICY|MACRO|STRUCT|EVENT|NARR|NOISE",
    "type_secondary": null,
    "scp": 0,
    "scp_basis": "SCP 판독 근거 1문장",
    "urgency": "URGENT|WATCH|SLOW",
    "urgency_basis": "긴급도 판단 근거",
    "emotion": {
      "detected": false,
      "original": "원래 입력 (감정 포함)",
      "core_uncertainty": "감정의 핵심 불확실성",
      "converted_question": "변환된 검증 가능한 질문"
    },
    "routing": {
      "mode": "full|fast|batch|compare|noise",
      "focus_layers": ["L4", "L6"],
      "skip_layers": [],
      "reduced_layers": ["L2", "L3"],
      "strategy_summary": "어디에 집중하고 어디를 축소하는지 1문장"
    }
  },

  "layers": {
    "L1": {
      "headline": "기사의 문자 그대로의 주장 1~2문장",
      "framing": ["공포", "긴급"],
      "framing_detail": "프레이밍 상세 분석"
    },
    "L2": {
      "facts": [
        {
          "id": 1,
          "fact": "검증 가능한 사실",
          "confidence": "green|yellow|red|black",
          "source": "출처",
          "fb_enhanced": false
        }
      ],
      "unsaid": [
        {
          "item": "기사가 말하지 않은 것",
          "significance": "왜 중요한지",
          "fb_enhanced": false
        }
      ]
    },
    "L3": {
      "players": [
        {
          "name": "플레이어명",
          "position": "입장",
          "benefit": "이익",
          "loss": "손해",
          "hidden_motive": "숨은 동기",
          "fb_enhanced": false
        }
      ],
      "media_motive": "기사 유통 주체의 동기"
    },
    "L4": {
      "why_now": "왜 지금 이 기사가 나왔는가",
      "surface_cause": "표면적 원인",
      "structural_cause": "구조적 원인",
      "timing_factor": "타이밍 요인",
      "causal_tree": "인과체인 트리 텍스트 (├──/└── 형식)"
    },
    "L5": {
      "system": "소속 상위 시스템",
      "concentric_position": "메가트렌드/구조/판/종목",
      "verdict": "repeat|shift|ambiguous",
      "verdict_basis": "판정 근거",
      "precedent": "역사적 전례 (시기, 결과)"
    },
    "L6": {
      "short_term": "단기 효과",
      "mid_term": "중기 효과",
      "long_term": "장기 효과",
      "nonlinear": "비선형 연결 (다른 분야로의 전이)",
      "scenarios": [
        {
          "condition": "만약 X이면",
          "result": "Y가 발생",
          "probability_feel": "높음|중간|낮음",
          "investment_implication": "투자 함의"
        }
      ]
    },
    "L7": {
      "investment_implication": "투자 함의 (행동 지시 아님)",
      "kill_condition": "이 판단이 무효화되는 조건",
      "tracking": [
        {
          "indicator": "추적 지표명",
          "current_value": "현재 값",
          "threshold": "임계값",
          "next_check": "다음 확인일"
        }
      ],
      "signal_or_noise": {
        "signal_condition": "만약 ~하면 → 시그널",
        "noise_condition": "만약 ~하면 → 노이즈"
      },
      "emotion_response": {
        "applicable": false,
        "response": "원래 걱정에 대한 직접 회답"
      }
    }
  },

  "emergent_questions": [
    {
      "question": "돌발 질문",
      "lens": "반전|시간|침묵|규모|역사",
      "answer": "답변 가능하면 제시, 불가능하면 추적 방법",
      "answerable": true
    }
  ],

  "uncertainty_map": {
    "L1": 5,
    "L2": 4,
    "L3": 3,
    "L4": 2,
    "L5": 3,
    "L6": 1,
    "L7": 3,
    "weakest": "L6",
    "weakest_reason": "미래 추론이며 전례 부족",
    "strengthen_by": "보강하려면 확인해야 할 데이터/이벤트"
  },

  "feedback": {
    "executed": ["FB-1", "FB-4"],
    "fb1_result": "L4→L2 재점검 결과",
    "fb2_result": "L5→L3 재점검 결과",
    "fb3_result": "L6→L7 재점검 결과",
    "fb4_delta": "처음과 달라진 점 (같으면 '변화 없음 — 보강 필요')"
  },

  "self_check": {
    "total_items": 12,
    "passed": 11,
    "failed_items": ["실패한 체크 항목"],
    "remediation": "보강 조치 내용"
  },

  "metadata": {
    "analysis_mode": "full|fast|batch|compare|noise",
    "elapsed_phases": ["Phase0", "Phase1", "Phase2", "Phase2.5", "Phase3", "Phase4"],
    "notion_ref": "이전 Notion 분석 ID (있으면)",
    "psf_ref": "PSF 교차 참조 (PSF연결 모드 시)"
  }
}
```

### 필드 규칙

```
필수 필드 (null 불가):
  id, date, version, input.type, input.content,
  pre_read.type, pre_read.scp, pre_read.urgency, pre_read.routing.mode,
  layers.L1, layers.L7,
  uncertainty_map, feedback.fb4_delta, self_check

조건부 필드:
  pre_read.emotion — emotion.detected=true일 때만 나머지 필드 필수
  layers.L2~L6 — routing.mode="noise"이면 L2~L6 null 허용
  pre_read.type_secondary — 복합 분류(POLICY×STRUCT)일 때만

SCP 범위: 정수 0~5
확신도 범위: 정수 1~5
confidence 값: "green" | "yellow" | "red" | "black"
verdict 값: "repeat" | "shift" | "ambiguous"
```

---

## 2. 이력 스냅샷 스키마 (history/YYYY-MM-DD-title.json)

분석 완료 시 history/ 디렉토리에 저장하는 스냅샷.
analysis.json의 축약 버전.

```json
{
  "id": "SA-20260325-001",
  "date": "2026-03-25",
  "title": "이슈 한줄 제목",

  "input_summary": "입력 요약 (50자 이내)",
  "input_type": "url|text|keyword|question",

  "pre_read": {
    "type": "POLICY",
    "scp": 3,
    "urgency": "WATCH",
    "mode": "full",
    "emotion_detected": false
  },

  "core_finding": "한줄 본질 (L7 기반)",

  "layer_summary": {
    "L1": "헤드라인 디코딩 요약",
    "L2": "팩트 스켈레톤 요약 + 미언급 사항 수",
    "L3": "핵심 플레이어 수 + 주요 갈등",
    "L4": "왜 지금 — 핵심 1문장",
    "L5": "구조 판정 (repeat/shift/ambiguous)",
    "L6": "핵심 2차 효과 1문장",
    "L7": "시그널/노이즈 판정 + KC"
  },

  "emergent_questions_count": 2,
  "top_emergent_question": "가장 중요한 돌발 질문",

  "uncertainty": {
    "weakest_layer": "L6",
    "average_confidence": 3.1
  },

  "feedback": {
    "executed": ["FB-1", "FB-4"],
    "fb4_changed": true
  },

  "self_check": {
    "passed": 11,
    "total": 12
  },

  "tags": ["POLICY", "반도체", "수출규제"],
  "related_ids": ["SA-20260320-003"]
}
```

### 파일 명명 규칙

```
history/YYYY-MM-DD-제목키워드.json

예시:
  history/2026-03-25-미중-AI칩-수출규제.json
  history/2026-03-25-한전-적자전환.json
  history/2026-03-25-BTC-10만돌파.json

규칙:
  - 날짜는 분석 실행일 (ISO 8601)
  - 제목은 핵심 키워드 2~4개, 하이픈 연결
  - 한글+영문 혼용 가능
  - 같은 날 같은 제목이면 뒤에 -2, -3 붙임
```

---

## 3. 보고서 메타데이터

HTML 보고서는 reports/ 디렉토리에 저장. 파일명 규칙:

```
reports/YYYY-MM-DD-제목키워드-adaptive.html

보고서 분류 (topbar):
  SCP ≥ 4  → STRUCTURAL SHIFT (red)
  SCP 2~3  → DEEP ANALYSIS (blue)
  SCP 0~1  → QUICK NOTE (navy)
```
