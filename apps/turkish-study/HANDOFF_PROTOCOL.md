# 작업 인수인계 및 원장 운영
## 단일 원장
DEVELOPMENT_LEDGER.json은 00 단독 쓰기. 01~05는 자기 영역의 신규 작업/상태 수정 제안을 handoffs/NN/<YYYYMMDD>-<task-id>-<unique>.json에 작성하고 같은 작업 PR에 포함. 기존 handoff 파일 수정/삭제 금지. 하나의 handoff record.id는 영구 유일. 00은 handoff id를 중앙 원장 적요/processedHandoffs 또는 운영 결정 로그에 기록하고 중복 적용 금지. 최신 main과 실제 증거를 확인 후 병합하고 원장에 반영. 의뢰/검수 요청은 from/to 및 dependencies와 acceptance를 명시한다. 수신자가 별도 대화 시작 시 main과 미병합 PR을 함께 읽는다.
## 중앙 원장 갱신
기존 ID 44개 유지. 요구사항 변경/신규 ID는 00만 승인. 전역 ID 유일. implementation/content/verification 분리. complete=true는 RELEASE_GATES 규칙 충족 시에만 00이 변경. 일감에 담당 1개, 검증 05, 의존성, active PR, 담당자 증거, 최종 결과, 최종 확인 SHA 연결. 임의로 기존 항목 삭제/분할하여 완료율 변경 금지. 하위 일감은 부모 ID와 연결, 집계 대상 명시. 버그 재발 시 complete=false로 되돌리고 이력 보존.
## 인수인계 형식 (JSON)
schemas/handoff.schema.json 참고. 필수: id/from/to/createdAt/taskIds/baseRef/contractVersion/status/summary/changedFiles/verification/requests/ledgerProposals. 선택: PR number/url, dependencies, knownIssues. verification[] 각 항목 result=pass/fail/pending, scope, evidence, revision; scope가 simulated면 real-device로 변경 금지. ledgerProposals[]는 id, implementation, content, verification, evidence[], proposedComplete. 새 일감은 newTaskRequests로 요청(00 승인 전 ID 집계 금지).
완료·검증 실패·차단·인터페이스 변경 모두 기록. 블로커는 실제 경로/오류와 대체 경로 결과 및 해소 필요 조건. PR 본문에 파일 경로와 요청 수신 영역 기재. 독립 검수는 05의 별도 handoff 또는 QA evidence로 기록.
## 설계 변경
ADR 제안은 decisions/proposals/NN/<id>.md로 자신 영역이 작성. 문제, 기존·새 규격, 영향을 받는 파일/학습 기록/릴리스, 대안, migration/rollback, 수용 테스트 포함. 00 승인 기록은 decisions/approved/<id>.md. 승인 전 타 영역 직접 수정 금지. 즉시 수정 필요한 회귀/보안 문제도 00 승인/핫픽스 후 재검증.
## 진행 보고
이번 턴 실제 반영한 commit/PR, 본인이 맡은 항목의 상태, 테스트 수와 범위, 신규 최종 완료(00 검증 전 0), 전체 원장 완료/잔여(조회 시점), 다음 작업과 의존성. 미병합 PR 상태는 미병합으로 보고한다. 시스템이 다음 대화를 자동 실행하거나 인수인계를 자동 푸시한다는 가정 금지.
