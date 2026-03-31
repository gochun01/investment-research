# Tracking System — JSON Schema 정의

> 모든 tracking 파일의 정규 스키마.
> JSON 파일 저장 시 이 스키마를 따른다.
> PostgreSQL DDL은 schema.sql 참조.

---

## 1. TC 카드 (cards/TC-*.json)

### 필수 필드

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `tc_id` | string | TC-NNN. PK | 고유 ID |
| `title` | string | not null | 이슈 제목 |
| `created` | string | ISO date | 생성일 |
| `updated` | string | ISO date | 최종 갱신일 |
| `status` | string | enum: active, archived | 상태 |
| `phase` | integer | 0~5 | 현재 Phase |
| `issue_summary` | string | not null | 요약 |
| `pre_read` | object | {type, scp(0~5), urgency} | 판독 |
| `scenarios` | object | 시나리오별 {label, probability, trigger, kc} | Trigger-KC |
| `tracking_indicators` | array | [{indicator, current, threshold, last_check, next_check}] | 추적 지표 |
| `analysis_ids` | array | string[] | SA-ID 연결 |
| `tags` | array | string[] | 분류 태그 |

### 선택 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `phase_log` | array | [{phase, date, trigger, note}] |
| `rm_watches` | array | [{watch_id, subject, next_check}] |
| `cross_card_links` | array | [{to, link}] |
| `psf_link` | string | **PSF 속성/링크 참조.** 온톨로지 브릿지의 원천. 비어있으면 키워드 추론 사용. |
| `macro_ref` | string | macro 지표 참조 (예: `C7 Brent $112.57`) |
| `source` | string | 최초 SA-ID |
| `close_condition` | string | 종료 조건 |

### pre_read.type enum
`POLICY` `MACRO` `STRUCT` `EVENT` `NARR` `NOISE` 또는 복합(`POLICY×STRUCT`)

### pre_read.urgency enum
`URGENT` `WATCH` `SLOW`

### scenarios.*.trigger 객체 (필수)

trigger는 반드시 **dict** 형식. 문자열 금지.

| 필드 | 필수 | 설명 |
|------|------|------|
| `condition` | ✓ | 충족 조건 (정량+정성 혼합 가능) |
| `source` | | 원천: `구조적` / `통계적` / `서사적` 또는 복합 |
| `distance` | | 현재값과 임계값의 거리 |
| `recalibration` | | 재조정 주기: `정기 M/DD + 비정기(이벤트)` |

```json
"trigger": {
  "condition": "Brent>$115 × 3d + 호르무즈 봉쇄",
  "source": "구조적+통계적",
  "distance": "Brent $2.43 남음",
  "recalibration": "정기 4/15 + 비정기(정전/봉쇄)"
}
```

### scenarios.*.kc 객체 (Trigger-KC 7항목)

3-band + action 필수. action이 없는 KC = 출구 없는 고속도로.

| 필드 | 필수 | 설명 |
|------|------|------|
| `watch` | ✓ | 내곽 밴드 (조기 경보) |
| `alert` | ✓ | 중간 밴드 (×Nd 지속조건) |
| `hard` | ✓ | 외곽 밴드 (×Nd 지속조건) |
| `action` | ✓ | **KC 발동 시 행동** — Phase 전환, 시나리오 전환, 카드 종료 등 |
| `source` | | 원천: 구조적/통계적/서사적 |

```json
"kc": {
  "watch": "정전 합의 보도",
  "alert": "Brent<$100 × 3d",
  "hard": "이란 항복 OR Brent<$85 × 5d",
  "action": "TC-003 Phase 4. 확전 thesis 폐기. B로 전환."
}
```

### heartbeat_thresholds (정량 자동 체크용)

cycle1_daily.py가 자동 체크하는 정량 임계값. tracking_indicators와 별도로 유지.

| 필드 | 필수 | 설명 |
|------|------|------|
| `indicator` | ✓ | 지표명 |
| `symbol` | ✓ | Yahoo Finance 티커 |
| `watch` | ✓ | 내곽 수치 |
| `alert` | ✓ | 중간 수치 |
| `hard` | ✓ | 외곽 수치 |
| `direction` | ✓ | `above` (상향 돌파) / `below` (하향 돌파) |

정량 지표가 없는 TC(POLICY 순수형 등)는 빈 배열 `[]`.

### scenarios 확률 합계

모든 시나리오의 probability 합계는 반드시 **100%**.
db_sync.py가 자동 검증. 100%가 아니면 경고.

### v1 레거시 — 마이그레이션 완료

2026-03-28 전체 TC(001~010) v2 마이그레이션 완료.
v1 형식(top-level trigger/kc, `id`, `status=tracking`)은 더 이상 생성하지 않는다.

| 레거시(금지) | v2(필수) |
|-------------|---------|
| `id` | `tc_id` |
| `status: "tracking"` | `status: "active"` |
| `trigger` (최상위 1개) | `scenarios.*.trigger` (시나리오별 dict) |
| `kc` (최상위 1개) | `scenarios.*.kc` (시나리오별 3-band + action) |
| `scp` (최상위) | `pre_read.scp` |
| `heartbeat_thresholds`만 | `heartbeat_thresholds` + `tracking_indicators` 양쪽 |

---

## 2. SD 카드 (cards/SD-*.json)

| 필드 | 타입 | 필수 | 제약 |
|------|------|------|------|
| `sd_id` | string | ✓ | SD-NNN. PK |
| `title` | string | ✓ | |
| `created` | string | ✓ | ISO date |
| `status` | string | ✓ | enum: watching, promoted, archived |
| `appearance_count` | integer | ✓ | ≥1 |
| `last_seen` | string | ✓ | ISO date |
| `source` | string | | |
| `next_check` | string | | |
| `note` | string | | |
| `promoted_to` | string | | TC-NNN (승격 시) |

---

## 3. Watch (active-watches.json → watches[])

| 필드 | 타입 | 필수 | 제약 |
|------|------|------|------|
| `id` | string | ✓ | W-YYYY-MM-DD-UQ-NNN. PK |
| `created` | string | ✓ | ISO date |
| `subject` | string | ✓ | |
| `type` | string | ✓ | enum: event_tracking, data_check, threshold_watch, policy_watch |
| `status` | string | ✓ | enum: active, resolved, expired |
| `schedule` | object | ✓ | {mode, check_dates[], next_check} |
| `original_context` | object | ✓ | {issue, resolve_condition} |
| `check_template` | object | ✓ | {questions[], data_sources[]} |
| `close_condition` | string | ✓ | |
| `source_report` | string | | |
| `completed_checks` | array | | |
| `closed_at` | string | | |
| `close_reason` | string | | |

---

## 4. Prediction (prediction-ledger.json → predictions[])

| 필드 | 타입 | 필수 | 제약 |
|------|------|------|------|
| `id` | string | ✓ | PRED-YYYYMMDD-NNN. PK |
| `source` | string | ✓ | SA-ID. FK |
| `date` | string | ✓ | ISO date |
| `tc` | string | ✓ | TC-NNN. FK |
| `type` | string | ✓ | POLICY/STRUCT/... |
| `claim` | string | ✓ | 예측 내용 |
| `scenario` | string | ✓ | A/B/C/D |
| `probability` | string | ✓ | "N%" |
| `trigger` | string | ✓ | 충족 조건 |
| `deadline` | string | ✓ | ISO date |
| `status` | string | ✓ | enum: open, hit, miss, partial, expired |
| `outcome` | string | | 대조 결과 |
| `outcome_date` | string | | |
| `lesson` | string | | 학습 내용 |

---

## 5. Evolution (evolution.json)

### quality_trend[] 항목

| 필드 | 타입 | 필수 | 범위 |
|------|------|------|------|
| `date` | string | ✓ | |
| `analysis_id` | string | ✓ | |
| `quality_score` | number | ✓ | 0.0~1.0 |
| `scores.coverage` | number | ✓ | 0.0~1.0 |
| `scores.cross_verification` | number | ✓ | 0.0~1.0 |
| `scores.discovery_rate` | number | ✓ | 0.0~1.0 |
| `scores.freshness` | number | ✓ | 0.0~1.0 |

### learning_log[] 항목

| 필드 | 타입 | 필수 |
|------|------|------|
| `date` | string | ✓ |
| `rule_id` | string | ✓ (D-NN) |
| `pattern` | string | ✓ |
| `correction` | string | ✓ |

---

## 6. SA History 확장 필드

Stereo Analyzer/SCHEMAS.md가 원본. 추가 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `pipeline` | string | 파이프라인 정보 |
| `prior_context` | object | delta 모드 참조 |
| `quality_score` | number | 0.0~1.0 |
| `delta_from_previous` | object | 이전 대비 변화 |
| `cross_card_links` | array | TC 연결 |

---

## 7. FK 관계도

```
tc_cards ──1:N──→ tc_analysis_links ←──N:1── sa_history
    │
    ├──1:N──→ watch_tc_links ←──N:1── watches
    │
    ├──1:N──→ predictions
    │
    └──1:1──← sd_cards (promoted_to)

sa_history ──1:N──→ predictions (source_analysis)
learning_log (독립)
```
