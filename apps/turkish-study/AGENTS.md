# Türkçe 120 — 공통 개발 지침 v1.0.0
발효: 2026-11-21. 모든 작업 대화는 먼저 main의 이 파일을 실제로 다시 읽는다.
## 단일 기준
repo: koith/browser-app-lab / root: apps/turkish-study/ / integration: main.
이 프로젝트 폴더 밖 수정 금지. 같은 저장소의 4LEAF, 기타 앱, 공용 Pages 설정 및 기존 운영 DB는 보전한다. 전역 설정 변경은 00의 별도 승인.
우선순위: 최신 사용자 지시 > AGENTS.md + GOVERNANCE.json + DATA_CONTRACT.md + RELEASE_GATES.md > 승인된 변경결정 > SPEC.md(설계 초안) > 예전 대화. 충돌하면 00에 ADR 요청; 승인 없이 해석 변경 금지.
목표: 한국어 모어 성인 2명, 120일/하루 60분, A1 우선/A2 도전, 에스키셰히르 실전교류, 무료 우선. 고정된 수업과 자체 제작 콘텐츠, 즉석 생성에 진도 의존 금지. CEFR 인증 아님. 초기 7일을 먼저 실제 공개·검수하여 학습 개시, 전체 120일 완성까지 기다리지 않는다.
## 시작/작업 규칙
1. main에서 공통 파일 4개와 DEVELOPMENT_LEDGER.json, SPEC.md, 관련 데이터/코드 및 자신에게 향한 handoffs를 읽는다. 현재 blob/commit SHA, 열린 PR과 작업 범위 확인. 이전 대화 기억을 기준으로 사용하지 않는다.
2. GOVERNANCE.json의 단일 파일 작성자/일감 책임자를 준수. 한 작업 브랜치는 한 영역/작업 단위. turkish/NN-<task>-<unique> 형태, 최신 main에서 분기. 같은 파일을 수정하는 열린 PR이 있으면 해당 소유자의 작업과 합류하거나 기다리는 대신 겹치지 않는 일감 진행. 동일 영역 내부 중복 작업도 금지.
3. 다른 영역 소유 파일, 계약/스키마, 원장, main 직접 수정 금지(00의 관리 파일 및 AUTO_DEVELOPMENT.md에 명시된 ops/LEASES.json의 CAS 조정 예외 제외). 인터페이스 변경은 ADR 제안 → 00 승인 → 소비자/생산자 호환 테스트 → 통합 PR. 00은 필요시 소유권을 기록하여 명시적으로 변경할 수 있다.
4. 실제 파일 저장, 의미 있는 커밋, PR 생성. 기대 blob SHA 검사, 강제 push/overwrite 금지. PR에는 담당 ID, 변경 파일, 입출력 계약 버전, 근거, 독립 검증 상태, 잔여 작업, 인수인계 ID, 해당 commit SHA 기재.
5. 05는 검증하고 증거 파일을 PR로 남긴다. 00만 main 병합/릴리스 승인/원장 정리한다. 00은 소유권, 최신 base, diff, 테스트, 충돌/후방 호환을 확인한 후 병합한다. 검증되지 않은 초안은 격리된 상태로 main에 통합할 수 있으나 학습 공개 허용 목록에 넣지 않는다. merge-ready와 운영 완료는 다름. 동일 파일에 대한 오래된 PR은 최신 main 반영 후 재검증하며 자동 강제 병합 금지.
6. 작업 내용이 완료되거나 막히면 HANDOFF_PROTOCOL.md대로 인수인계/원장 변경 제안을 파일로 기록. 다른 대화 실행/자동 전달을 가정하지 않는다. 해당 대화가 다음 실행 시 main의 문서와 열린 PR을 읽는다. 사용자가 다시 실행을 지시하기 전 백그라운드 진행을 약속하지 않는다.
## 보안 및 검증
접근키, 개인 학습기록, 실사용 계정 정보, 녹음은 공개 git에 절대 저장 금지. Supabase 기존 2개 운영 프로젝트 수정/삭제 금지. 별도 인프라의 무료 한도/비용 확인 전에 과금 또는 리소스 생성하지 않는다. 개인정보 전송 기본 금지. 외부 교재/음성 무단 복제 금지.
실제 테스트 증거를 남긴다. VERIFIED(검사 범위 명시), INFERRED, UNVERIFIED 분리. 모의 DOM/구문/구조 통과는 iPhone Safari 실제 검증과 다르다. URL HTTP 200만으로 렌더링 완료 아님. 원어민 검수 없으면 원어민 검수라고 표기 금지. 실패는 FAILED_PATH로 남기고 대체 경로 조사한다.
모든 진행 보고: 신규 완료/전체 완료/잔여 + PR/commit/증거 + 다음 작업/막힘. 중앙 원장 숫자를 임의 수정하거나 부분 완료를 최종 완료로 부풀리지 않는다.
## 공통 파일
GOVERNANCE.json: 소유권/작업 책임. DATA_CONTRACT.md 및 schemas/: 데이터 규격. HANDOFF_PROTOCOL.md: 변경 제안·인수인계. RELEASE_GATES.md 및 RELEASE_MANIFEST.json: 출시 규칙·실제 공개 상태. DEVELOPMENT_LEDGER.json: 00만 수정하는 중앙 원장. BOOTSTRAP_PROMPTS.md: 신규 대화 초기 작업 지시.

## 자기 선택형 개발 및 예약 실행 (2026-11-21)
사용자가 '개발 계속해'라고 하면 해당 역할의 다음 작업을 최신 main의 AUTO_DEVELOPMENT.md, ops/WORK_QUEUE.json, ops/DEFECTS.json, ops/LEASES.json과 미처리 handoff/PR로부터 스스로 선택하고 실제 작업한다. 먼저 role lease 획득; 작업자 간 수동 복사 전달 불필요. 예약 실행기 역시 이 파일의 권한/검증 절차 준수, 운영/작업 기록은 GitHub, 사용자 알림은 AUTO_DEVELOPMENT.md의 중요한 상태 변화만. 예약 등록은 별도 수행. 이 규칙은 백그라운드 실행을 시작한 것으로 간주하지 않는다.
