-- ============================================================
-- TC/SD 카드 초기 적재 + SA 링크 + 텔레그램 확인
-- ============================================================

-- TC-001
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, rm_watches, cross_card_links, source, close_condition, tags) VALUES
('TC-001', 'Section 301 — 관세 법체계 3단 진화', '2026-03-26', '2026-03-27', 'active', 1,
 '301 청문회(4/28) → 관세 범위 확정. Section 122(15%) + Section 301 병행. IEEPA $167B 환급 혼란.',
 '{"type":"POLICY","scp":4,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"교란해소+역풍지연","probability":"25%"},"B":{"label":"교착+역풍가시화","probability":"35%","base":true},"C":{"label":"이중충격","probability":"15%"},"D":{"label":"교란해소+역풍동시","probability":"25%","key":true}}'::jsonb,
 '[{"indicator":"Brent","current":"$100.70","threshold":"$120","last_check":"2026-03-27","next_check":"2026-04-01"},{"indicator":"DXY","current":"99.90","threshold":"103","last_check":"2026-03-27","next_check":"2026-04-01"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"첫 분석","note":"SA-20260326-001"},{"phase":1,"date":"2026-03-27","trigger":"파이프라인 풀 실행","note":"core BURIED 확인"}]'::jsonb,
 '["W-UQ-030","W-UQ-031","W-UQ-032","W-UQ-033"]'::jsonb,
 '[{"to":"TC-006","link":"301 전자장비=반도체"},{"to":"TC-002","link":"ADR 달러 유입 → KRW 역방향"}]'::jsonb,
 'SA-20260326-001',
 '301 관세 확정 OR 철회 OR 6개월 무변화 → 아카이브',
 ARRAY['POLICY','관세','Section301','Section122','IEEPA']);

-- TC-002
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, source, close_condition, tags) VALUES
('TC-002', 'KRW 구조적 고환율 — NPS 70% + 3단계 누적', '2026-03-26', '2026-03-26', 'active', 1,
 'KRW 1,506. NPS 해외투자 70%. 구조적 달러 수요. WGBI 편입 미결정.',
 '{"type":"MACRO","scp":3,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"KRW 추가 약세","probability":"40%","trigger":"KRW 1,550+ × 5d","kc":{"watch":"KRW 1,450×3d","alert":"NPS 축소 정책","hard":"KRW 1,400×5d"}},"B":{"label":"WGBI 편입 → 구조적 반전","probability":"30%"},"C":{"label":"현상유지","probability":"30%"}}'::jsonb,
 '[{"indicator":"KRW","current":"1,506","threshold":"1,530","last_check":"2026-03-26","next_check":"2026-04-03"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"첫 분석","note":"SA-20260326-002"}]'::jsonb,
 'SA-20260326-002',
 'WGBI 편입 확정 OR KRW 1,400↓ OR 6개월 무변화',
 ARRAY['MACRO','KRW','환율','NPS','WGBI']);

-- TC-003
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, source, close_condition, tags) VALUES
('TC-003', '이란 전쟁 교란 — 역풍 부상', '2026-03-26', '2026-03-27', 'active', 1,
 '이란 전쟁 격화. Brent $100+. 호르무즈 toll booth. 탄그시리 사살. 트럼프 에너지 시설 공격 위협.',
 '{"type":"EVENT","scp":4,"urgency":"URGENT"}'::jsonb,
 '{"A":{"label":"de-escalation","probability":"20%","trigger":"휴전 합의 OR Brent<$80×5d","kc":{"watch":"Brent $120","alert":"Brent $135×3d","hard":"Brent $150×3d OR 호르무즈 완전 재봉쇄"}},"B":{"label":"격화 → 확전","probability":"30%","trigger":"에너지 시설 공격 + 이란 보복"},"C":{"label":"교착 지속","probability":"50%","trigger":"데드라인 재연장 + Brent $95~105"}}'::jsonb,
 '[{"indicator":"Brent","current":"$100.70","threshold":"$110","last_check":"2026-03-27","next_check":"2026-03-28"},{"indicator":"VIX","current":"27.44","threshold":"30","last_check":"2026-03-27","next_check":"2026-03-28"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"첫 분석","note":"SA-20260326-003"},{"phase":1,"date":"2026-03-27","trigger":"P3 🔴 격화 복귀","note":"탄그시리 사살. 시나리오 B 상향."}]'::jsonb,
 'SA-20260326-003',
 '휴전 확정 OR Brent $150 → 확전 카드 전환',
 ARRAY['EVENT','이란','전쟁','유가','Brent','호르무즈']);

-- TC-004
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, source, close_condition, tags) VALUES
('TC-004', 'ISA→ETF 구조 전환 — 807만 명의 행동 변화', '2026-03-26', '2026-03-26', 'active', 0,
 'ISA 64조, 807만 가입. 해외ETF 53.2%. 개인 투자자의 구조적 행동 변화.',
 '{"type":"STRUCT","scp":3,"urgency":"SLOW"}'::jsonb,
 '{"A":{"label":"ISA 100조+ 구조 확정","probability":"50%","trigger":"ISA 80조+ OR 가입자 1,000만"},"B":{"label":"고점 시그널","probability":"20%","trigger":"월간 유입 마이너스 × 2개월"},"C":{"label":"현상유지","probability":"30%"}}'::jsonb,
 '[{"indicator":"ISA 잔액","current":"64조","threshold":"80조","last_check":"2026-03-26","next_check":"2026-04-15"}]'::jsonb,
 '[{"phase":0,"date":"2026-03-26","trigger":"첫 분석","note":"데이터 추가 필요"}]'::jsonb,
 'SA-20260326-004',
 'ISA 100조+ OR KOSPI -30% OR 1년 무변화',
 ARRAY['STRUCT','ISA','ETF','개인투자자']);

-- TC-005
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, source, close_condition, tags) VALUES
('TC-005', 'VW-방산 전환 — 유럽 자동차→방산 80년 역전', '2026-03-26', '2026-03-26', 'active', 0,
 'VW-라파엘 방산 협력 협상. 유럽 자동차 → 방산 전환의 구조적 시작.',
 '{"type":"STRUCT","scp":4,"urgency":"SLOW"}'::jsonb,
 '{"A":{"label":"VW-라파엘 계약 체결","probability":"40%","trigger":"계약 체결 + 셰플러-헬싱 양산","kc":{"watch":"유럽 방산주 -15%","alert":"IG Metall 반대","hard":"독일 방산 예산 삭감"}},"B":{"label":"협상 결렬","probability":"30%"},"C":{"label":"지연","probability":"30%"}}'::jsonb,
 '[]'::jsonb,
 '[{"phase":0,"date":"2026-03-26","trigger":"FT 보도","note":"협상 확인. 노동자 동의 미확인."}]'::jsonb,
 'SA-20260326-005',
 'VW-라파엘 계약 확정 OR 협상 결렬 OR 2026년말',
 ARRAY['STRUCT','방산','VW','자동차','유럽','MT-02']);

-- TC-006
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, cross_card_links, source, close_condition, tags) VALUES
('TC-006', 'SK하이닉스 ADR — 밸류에이션 체계 전환', '2026-03-26', '2026-03-26', 'active', 1,
 'SK하이닉스 SEC F-1 제출(3/24). 연내 ADR 상장 목표. PER 20x+ 재평가 기대.',
 '{"type":"STRUCT","scp":3,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"ADR 성공 + 재평가","probability":"50%","trigger":"ADR 상장 + PER 20x+","kc":{"watch":"ADR $100억 미만","alert":"301 반도체 관세 + ADR 면제 불포함","hard":"HBM 점유율 50%↓ OR ADR 철회"}},"B":{"label":"ADR + 301 동시","probability":"30%"},"C":{"label":"ADR 규모 부족","probability":"20%"}}'::jsonb,
 '[{"indicator":"SK하이닉스","current":"₩1,000,000","threshold":"₩850,000","last_check":"2026-03-26","next_check":"2026-04-15"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"SEC F-1 제출","note":"주총 100조 선언"}]'::jsonb,
 '[{"to":"TC-001","link":"301 전자장비=반도체"},{"to":"TC-002","link":"ADR 달러 유입 → KRW 역방향"}]'::jsonb,
 'SA-20260326-006',
 'ADR 상장 완료 OR ADR 철회 OR 6개월 무변화',
 ARRAY['STRUCT','반도체','SK하이닉스','ADR','HBM']);

-- TC-007
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, source, close_condition, tags) VALUES
('TC-007', '인플레 공포에 미 장기채 ETF 투자자 눈물', '2026-03-26', '2026-03-26', 'active', 1,
 '이란전쟁발 인플레 공포 → 장기채 투매 → TLT/TMF 급락. 재정적자+관세+인하기대붕괴의 텀 프리미엄 팽창.',
 '{"type":"MACRO×NARR","scp":2,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"전쟁 장기화 + 유가 $110+","probability":"35%","trigger":"Brent>$110×5d","kc":{"watch":"Brent<$90","alert":"Brent<$85×3d","hard":"Brent<$80×3d"}},"B":{"label":"휴전 → 장기채 반등","probability":"25%","trigger":"이란 휴전 + 30Y<4.5%","kc":{"watch":"30Y>4.7%","alert":"30Y>4.9%×3d","hard":"30Y>5.0%×5d"}},"C":{"label":"현상유지 횡보","probability":"40%","trigger":"30Y 4.8~5.0% 밴드 2주+"}}'::jsonb,
 '[{"indicator":"30Y 금리","current":"4.94%","threshold":"5.0%","last_check":"2026-03-26","next_check":"2026-03-28"},{"indicator":"Brent","current":"$103.79","threshold":"$110","last_check":"2026-03-26","next_check":"2026-03-28"},{"indicator":"FedWatch 인상","current":"23.4%","threshold":"30%","last_check":"2026-03-26","next_check":"2026-04-02"},{"indicator":"5Y BEI","current":"2.51%","threshold":"2.7%","last_check":"2026-03-26","next_check":"2026-03-28"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"첫 분석. 30Y 4.94%","note":"SA-20260326-001"}]'::jsonb,
 'SA-20260326-001',
 '30Y 5.5% → 위기 카드 OR 휴전+30Y<4.3% → 해소',
 ARRAY['MACRO','NARR','장기채','TLT','TMF','인플레','텀프리미엄']);

-- TC-008
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, rm_watches, cross_card_links, source, close_condition, tags) VALUES
('TC-008', '한국 자동차 삼중 포위 — 관세+EU+BYD', '2026-03-26', '2026-03-26', 'active', 2,
 '미 IEEPA 15→25%, EU IAA 역내생산, 중국 BYD 공세 동시 임계. 수출→현지생산 전환 가속.',
 '{"type":"POLICY×STRUCT","scp":4,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"관세 25% + EU IAA → 구조전환","probability":"40%","trigger":"IEEPA 25% 시행","kc":{"watch":"현대차 ₩430K","alert":"₩400K×3d","hard":"₩370K×5d"}},"B":{"label":"관세 협상 타결(15%)","probability":"15%"},"C":{"label":"삼중 압박 극대화","probability":"30%","trigger":"25%+BYD 유럽1위+이란3개월+","kc":{"watch":"₩420K","alert":"₩380K×3d","hard":"₩350K×5d"}},"D":{"label":"SDV 경쟁 부상","probability":"15%"}}'::jsonb,
 '[{"indicator":"미국 관세율","current":"15%","threshold":"25%","last_check":"2026-03-26","next_check":"2026-04-02"},{"indicator":"현대차","current":"₩490,000","threshold":"₩430K","last_check":"2026-03-26","next_check":"2026-04-02"},{"indicator":"BYD 유럽","current":"연속 1위","threshold":"분기1위 확정","last_check":"2026-03-26","next_check":"2026-04-15"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-26","trigger":"매경 칼럼+pipeline","note":"SA-20260326-002"},{"phase":2,"date":"2026-03-26","trigger":"풀 실행. SCP 3→4","note":"SA-20260326-007. 시나리오 D 추가."}]'::jsonb,
 '[{"watch_id":"W-UQ-060","subject":"한미 관세 15% vs 25%","next_check":"2026-03-31"},{"watch_id":"W-UQ-061","subject":"EU IAA 역내산","next_check":"2026-06-30"}]'::jsonb,
 '[{"to":"TC-001","link":"301 관세 직격"},{"to":"TC-003","link":"이란→중동수출+유가"},{"to":"TC-005","link":"VW 방산 = 유럽 자동차 판 붕괴 증거"}]'::jsonb,
 'SA-20260326-002',
 '관세 25% 시행 → Phase 3 OR 협상 타결 → KC OR 1년 무변화',
 ARRAY['POLICY','STRUCT','자동차','현대차','기아','관세','EU','IAA','BYD','SDV','MT-07','pipeline-full']);

-- TC-009
INSERT INTO tc_cards (tc_id, title, created, updated, status, phase, issue_summary, pre_read, scenarios, tracking_indicators, phase_log, rm_watches, cross_card_links, source, close_condition, tags) VALUES
('TC-009', 'EU 제3극 통상 자율성 — ACI 보복권한', '2026-03-27', '2026-03-27', 'active', 1,
 'EU 의회 관세 딜(15%) 조건부 승인(417:154:71). sunset 18개월 + ACI 보복권한.',
 '{"type":"POLICY×STRUCT","scp":4,"urgency":"WATCH"}'::jsonb,
 '{"A":{"label":"이사회 승인 → ACI 미발동","probability":"40%","trigger":"EU 이사회 최종 승인","kc":{"watch":"이사회 심의 개시","alert":"ACI 발동 검토","hard":"ACI 발동 확정"}},"B":{"label":"ACI 발동 → 미-EU 긴장","probability":"25%","trigger":"EU ACI 공식 발동"},"C":{"label":"IAA 발효 → 한국 역내산 부족","probability":"25%","trigger":"IAA+70% 역내산 요건"},"D":{"label":"sunset 만료 → EU 보복","probability":"10%"}}'::jsonb,
 '[{"indicator":"EU 이사회","current":"의회 통과, 이사회 대기","threshold":"이사회 승인","last_check":"2026-03-27","next_check":"2026-04-10"},{"indicator":"ACI 발동","current":"미검토","threshold":"공식 검토 개시","last_check":"2026-03-27","next_check":"2026-04-24"}]'::jsonb,
 '[{"phase":1,"date":"2026-03-27","trigger":"EU 의회 투표 417:154:71","note":"core D-3 PASS. MT-07."}]'::jsonb,
 '[{"watch_id":"W-UQ-072","subject":"EU 이사회 최종 승인","next_check":"2026-04-10"}]'::jsonb,
 '[{"to":"TC-001","link":"301과 EU 딜 동시 진행"},{"to":"TC-008","link":"IAA 발효 시 현대·기아 압박"}]'::jsonb,
 'SA-20260327-001',
 'EU 이사회 승인 OR ACI 발동 OR sunset 결과 확정',
 ARRAY['POLICY','STRUCT','EU','ACI','IAA','sunset','제3극','MT-07','pipeline-full']);

-- ============================================================
-- SD 카드 3장
-- ============================================================

INSERT INTO sd_cards (sd_id, title, created, status, appearance_count, last_seen, source, next_check, note, close_condition) VALUES
('SD-001', 'GENIUS Act 스테이블코인 규제 시행 (Q2)', '2026-03-26', 'watching', 1, '2026-03-26',
 'scanner backlog BL-001', '2026-04-02',
 'Q2 시행. 전쟁에 묻히지만 크립토 제도화의 구조적 변화.',
 '3회+ → TC 승격 OR 6개월 미등장 → 아카이브');

INSERT INTO sd_cards (sd_id, title, created, status, appearance_count, last_seen, source, next_check, note, close_condition) VALUES
('SD-002', 'AI 투자 심리 분열 — 승자/패자 가려지는 구간', '2026-03-26', 'watching', 2, '2026-03-26',
 'scanner backlog BL-002', '2026-04-02',
 '2회째: SK하이닉스 ADR에서 재등장. 1회 더 → TC 승격.',
 '3회+ → TC 승격 OR 6개월 미등장 → 아카이브');

INSERT INTO sd_cards (sd_id, title, created, status, appearance_count, last_seen, source, next_check, note, close_condition) VALUES
('SD-003', '글로벌 자동차→방산 전환 추가 사례', '2026-03-26', 'watching', 1, '2026-03-26',
 'SA-20260326-005 파생', '2026-04-15',
 'VW 외 셰플러/도요타/테슬라 추가 사례 모니터링. MT-02×MT-07.',
 '3건+ 사례 → TC-005 보강 OR 6개월 미등장 → 아카이브');

-- ============================================================
-- TC ↔ SA 분석 연결
-- ============================================================

INSERT INTO tc_analysis_links VALUES ('TC-001', 'SA-20260326-001');
INSERT INTO tc_analysis_links VALUES ('TC-001', 'SA-20260327-001');
INSERT INTO tc_analysis_links VALUES ('TC-002', 'SA-20260326-002');
INSERT INTO tc_analysis_links VALUES ('TC-003', 'SA-20260326-003');
INSERT INTO tc_analysis_links VALUES ('TC-004', 'SA-20260326-004');
INSERT INTO tc_analysis_links VALUES ('TC-005', 'SA-20260326-005');
INSERT INTO tc_analysis_links VALUES ('TC-006', 'SA-20260326-006');
INSERT INTO tc_analysis_links VALUES ('TC-007', 'SA-20260326-001');
INSERT INTO tc_analysis_links VALUES ('TC-008', 'SA-20260326-002');
INSERT INTO tc_analysis_links VALUES ('TC-008', 'SA-20260326-007');
INSERT INTO tc_analysis_links VALUES ('TC-009', 'SA-20260327-001');
