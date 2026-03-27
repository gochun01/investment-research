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
| `source` | string | 최초 SA-ID |
| `close_condition` | string | 종료 조건 |

### pre_read.type enum
`POLICY` `MACRO` `STRUCT` `EVENT` `NARR` `NOISE` 또는 복합(`POLICY×STRUCT`)

### pre_read.urgency enum
`URGENT` `WATCH` `SLOW`

### scenarios.*.kc 객체 (Trigger-KC 7항목)
| 필드 | 필수 | 설명 |
|------|------|------|
| `watch` | ✓ | 내곽 밴드 |
| `alert` | ✓ | 중간 밴드 (×Nd 지속조건) |
| `hard` | ✓ | 외곽 밴드 (×Nd 지속조건) |
| `source` | | 원천: 구조적/통계적/서사적 |
| `action_on_kc` | | KC 작동 시 행동 |
| `recalibration` | | 재조정 주기 |

### 레거시(v1) → v2 마이그레이션

| 레거시 | 대체 | 방법 |
|--------|------|------|
| `id` | `tc_id` | 복사 |
| `type` | 삭제 | |
| `scp` (최상위) | `pre_read.scp` | 이동 |
| `trigger` (최상위) | `scenarios.*.trigger` | 시나리오 내부로 |
| `kc` (최상위) | `scenarios.*.kc` | 시나리오 내부로 |
| `heartbeat_thresholds` | `tracking_indicators` | 구조 변환 |
| `cross_refs` | `cross_card_links` | string→{to, link} |
| `events` | 삭제 | rm events/ 대체 |
| `open_questions` | 삭제 | Watch 대체 |

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
