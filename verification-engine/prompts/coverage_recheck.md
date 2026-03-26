# Phase 2.5: 커버리지 재점검 프롬프트

## 원칙

> 4대 불변 원칙, 판정 체계는 **CLAUDE.md** 참조.
> 아래는 Phase 2.5 전용 규칙만 기술한다.

## 커버리지 재점검 전용 원칙

- **층을 출력에서 빼지 마라** (V-03). 수행 불가하면 ⚫ NO BASIS로 판정하되, 해당 층 자체를 생략하지 않는다.
- 이 Phase는 **감사자(Auditor) 역할**이다. Phase 2의 판정을 바꾸지 않고, 누락만 보완한다.

---

검증이 끝난 후, 아래 미실행 항목을 확인하고 **누락된 층을 실행**하라.

## 미실행 항목 (자동 주입)

{missing_items}

> `["c001/fact: 미실행", "document/norm: 미실행"]` 형태의 string 배열.
> 상세 스키마는 `schemas/io-contracts.md` 참조.

---

## 실행 절차

1. 각 미실행 항목에 대해 해당 층의 프롬프트를 `verify_get_prompt(layer_name)`으로 로드
2. 프롬프트의 지시에 따라 검증 수행
3. 결과를 `verify_set_verdict()` 또는 `verify_set_document_verdict()`로 등록
4. 수행 불가하면 ⚫ NO BASIS로 판정. notes에 "수행 불가 사유: [이유]" 기록

### 수행 불가 판정 기준

| 사유 | 처리 |
|---|---|
| MCP 소스 없음 (해당 도메인 미지원) | ⚫ + notes "MCP 소스 미지원" |
| 체크리스트 미구축 | ⚫ + notes "체크리스트 미구축. self_audit에서 추가 권장" |
| 문서에 해당 정보 없음 | ⚫ + notes "문서에 관련 정보 부재" |
| MCP 호출 3회 실패 | ⚫ + notes "MCP 호출 실패 (3회 재시도)" |

---

## 루프 종료 조건

1. `verify_check_coverage()` 호출하여 `complete=true` 확인
2. `complete=true` → Phase 3+4로 진행
3. `complete=false` → 미실행 항목 재실행 (이 절차 반복)
4. **최대 2회 반복**. 2회 후에도 `complete=false`면:
   - 잔여 미실행 항목을 전부 ⚫ NO BASIS로 처리
   - notes에 "커버리지 재점검 2회 시도 후 미완. ⚫ 처리"
   - Phase 3+4로 진행

---

## 출력

```
각 미실행 항목에 대해:

verify_set_verdict("c001", "fact",
    verdict="⚫",
    notes="커버리지 재점검: MCP 소스 미지원(fund_factsheet). 수행 불가."
)

또는

verify_set_document_verdict("norm",
    verdict="⚫",
    notes="커버리지 재점검: 해당 doc_type 체크리스트 미구축. self_audit에서 추가 권장."
)

완료 후:
verify_check_coverage() 호출 → complete=true 확인
```
