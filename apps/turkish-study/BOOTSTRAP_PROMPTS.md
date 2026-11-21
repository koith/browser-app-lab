# 01~05 신규 대화 초기 지시문

## 01_교육과정 설계

공통: GitHub koith/browser-app-lab의 apps/turkish-study/만 사용한다. 이 메시지는 독립 대화의 초기 작업 지시다. 반드시 GitHub main에서 AGENTS.md, GOVERNANCE.json, DATA_CONTRACT.md, HANDOFF_PROTOCOL.md, RELEASE_GATES.md, RELEASE_MANIFEST.json, DEVELOPMENT_LEDGER.json, SPEC.md 및 관련 파일/열린 PR/인수인계를 실제 조회한 뒤 최신 상태로 실행한다. 다른 대화 기억에 의존하지 않는다. 자기 소유 파일만 최신 main에서 turkish/NN-<task>-<unique> 브랜치로 작업하고 실제 commit+PR+handoffs/NN/<unique>.json 저장. 본인이 main 병합/중앙 원장/규격/출고 목록 변경 금지(00 단독). 검수 증거·PR·신규 완료/잔여를 보고하며 목표 달성까지 실제 작업한다. 자동 업데이트나 후속 대화 자동 실행을 전제하지 않는다. P0 첫 7일 검수·공개 배포를 최우선, 다음 7일 공급 병행. 기존 기록·ID·무료 인프라·기타 앱 보호.

영역: 01_교육과정 설계. 소유: curriculum.json, curriculum-mapping/**. 담당 일감: RES-03, CUR-01~03, CON-10.

첫 작업: D001~D007의 실제 수업 목표·선수학습·관용 표현·CEFR/Maarif 세부 성취기준·60분 학습 분량·주간 평가 범위를 먼저 검토하고 매핑 파일로 저장한다. D008~D014를 이어서 설계한다. 120일 순서와 평가일 및 ID를 임의 변경하지 않는다. 출처 원문 위치와 근거를 기록하고 02·05에 인수인계한다.

계획 설명만 하지 말고 실제 파일·테스트·PR을 남긴다. 타 영역 의존성은 HANDOFF_PROTOCOL.md에 맞춰 기록한다.

## 02_교육 콘텐츠 제작

공통: GitHub koith/browser-app-lab의 apps/turkish-study/만 사용한다. 이 메시지는 독립 대화의 초기 작업 지시다. 반드시 GitHub main에서 AGENTS.md, GOVERNANCE.json, DATA_CONTRACT.md, HANDOFF_PROTOCOL.md, RELEASE_GATES.md, RELEASE_MANIFEST.json, DEVELOPMENT_LEDGER.json, SPEC.md 및 관련 파일/열린 PR/인수인계를 실제 조회한 뒤 최신 상태로 실행한다. 다른 대화 기억에 의존하지 않는다. 자기 소유 파일만 최신 main에서 turkish/NN-<task>-<unique> 브랜치로 작업하고 실제 commit+PR+handoffs/NN/<unique>.json 저장. 본인이 main 병합/중앙 원장/규격/출고 목록 변경 금지(00 단독). 검수 증거·PR·신규 완료/잔여를 보고하며 목표 달성까지 실제 작업한다. 자동 업데이트나 후속 대화 자동 실행을 전제하지 않는다. P0 첫 7일 검수·공개 배포를 최우선, 다음 7일 공급 병행. 기존 기록·ID·무료 인프라·기타 앱 보호.

영역: 02_교육 콘텐츠 제작. 소유: lessons.json, content/**. 담당 일감: CON-01~09.

첫 작업: D001~D007의 교재 내용을 먼저 정확히 점검·보강한다. 날마다 60분 학습 가능한 어휘·한국어 문법 설명·예문·듣기·따라 말하기·실전 회화·문제·정답·해설을 제작하고 첫 주 종합 평가를 보완한다. 출처 및 항목별 검수 근거를 저장하고 05에 독립 검수 요청한다. 동시에 D008~D014 초안을 제작해 공급 여유를 확보한다. 01의 학습 순서와 기존 데이터 계약 유지. 원어민 검수 미실시를 숨기지 않는다.

계획 설명만 하지 말고 실제 파일·테스트·PR을 남긴다. 타 영역 의존성은 HANDOFF_PROTOCOL.md에 맞춰 기록한다.

## 03_웹앱 개발

공통: GitHub koith/browser-app-lab의 apps/turkish-study/만 사용한다. 이 메시지는 독립 대화의 초기 작업 지시다. 반드시 GitHub main에서 AGENTS.md, GOVERNANCE.json, DATA_CONTRACT.md, HANDOFF_PROTOCOL.md, RELEASE_GATES.md, RELEASE_MANIFEST.json, DEVELOPMENT_LEDGER.json, SPEC.md 및 관련 파일/열린 PR/인수인계를 실제 조회한 뒤 최신 상태로 실행한다. 다른 대화 기억에 의존하지 않는다. 자기 소유 파일만 최신 main에서 turkish/NN-<task>-<unique> 브랜치로 작업하고 실제 commit+PR+handoffs/NN/<unique>.json 저장. 본인이 main 병합/중앙 원장/규격/출고 목록 변경 금지(00 단독). 검수 증거·PR·신규 완료/잔여를 보고하며 목표 달성까지 실제 작업한다. 자동 업데이트나 후속 대화 자동 실행을 전제하지 않는다. P0 첫 7일 검수·공개 배포를 최우선, 다음 7일 공급 병행. 기존 기록·ID·무료 인프라·기타 앱 보호.

영역: 03_웹앱 개발. 소유: index.html, manifest.webmanifest, sw.js, icon.svg, app/**, assets/ui/**, schema-proposal.sql, db/**, deploy/**. 담당 일감: APP-01~08, DB-01~05, DEP-01~02.

첫 작업: 공개 URL 404 원인을 먼저 실제 확인하고 Pages 또는 무료 대안으로 독립 배포한다. RELEASE_MANIFEST.json을 로드하고 미승인 일자 수업·시험·완료를 차단한다(테스트판은 명확히 구분). 첫 7일 학습 가능 UI, 음성 재생, 시험·복습, 두 로컬 프로필 분리와 백업/복원을 실제 검증한다. 04와 음성 통합을 조율하고 05에게 공개 URL/테스트 evidence를 제공한다. 독립 클라우드 저장은 병행하되 기존 운영 DB·다른 앱·공통 Pages 설정을 건드리지 않으며 과금하지 않는다.

계획 설명만 하지 말고 실제 파일·테스트·PR을 남긴다. 타 영역 의존성은 HANDOFF_PROTOCOL.md에 맞춰 기록한다.

## 04_음성 및 회화 시스템

공통: GitHub koith/browser-app-lab의 apps/turkish-study/만 사용한다. 이 메시지는 독립 대화의 초기 작업 지시다. 반드시 GitHub main에서 AGENTS.md, GOVERNANCE.json, DATA_CONTRACT.md, HANDOFF_PROTOCOL.md, RELEASE_GATES.md, RELEASE_MANIFEST.json, DEVELOPMENT_LEDGER.json, SPEC.md 및 관련 파일/열린 PR/인수인계를 실제 조회한 뒤 최신 상태로 실행한다. 다른 대화 기억에 의존하지 않는다. 자기 소유 파일만 최신 main에서 turkish/NN-<task>-<unique> 브랜치로 작업하고 실제 commit+PR+handoffs/NN/<unique>.json 저장. 본인이 main 병합/중앙 원장/규격/출고 목록 변경 금지(00 단독). 검수 증거·PR·신규 완료/잔여를 보고하며 목표 달성까지 실제 작업한다. 자동 업데이트나 후속 대화 자동 실행을 전제하지 않는다. P0 첫 7일 검수·공개 배포를 최우선, 다음 7일 공급 병행. 기존 기록·ID·무료 인프라·기타 앱 보호.

영역: 04_음성 및 회화 시스템. 소유: audio/**, conversation/**, assets/audio/**. 담당 일감: AUD-01~04, AI-01~02.

첫 작업: D001~D007 터키어 음성부터 실제 확보/생성·정확성·라이선스·Safari 재생 호환을 검증한다. TTS 및 고정 음성 파일 대안 비교, 음성 manifest 작성, 듣기 및 따라말하기·녹음 비교에 필요한 인터페이스를 제공한다. 03 소유 index.html은 직접 수정하지 말고 통합 요청한다. 05에 청취 검수와 음성 증거 전달. 이후 D008~D014 음성, 고정 분기 회화 및 STT/AI 비용·개인정보·평가 타당성 순으로 진행한다.

계획 설명만 하지 말고 실제 파일·테스트·PR을 남긴다. 타 영역 의존성은 HANDOFF_PROTOCOL.md에 맞춰 기록한다.

## 05_통합 검증

공통: GitHub koith/browser-app-lab의 apps/turkish-study/만 사용한다. 이 메시지는 독립 대화의 초기 작업 지시다. 반드시 GitHub main에서 AGENTS.md, GOVERNANCE.json, DATA_CONTRACT.md, HANDOFF_PROTOCOL.md, RELEASE_GATES.md, RELEASE_MANIFEST.json, DEVELOPMENT_LEDGER.json, SPEC.md 및 관련 파일/열린 PR/인수인계를 실제 조회한 뒤 최신 상태로 실행한다. 다른 대화 기억에 의존하지 않는다. 자기 소유 파일만 최신 main에서 turkish/NN-<task>-<unique> 브랜치로 작업하고 실제 commit+PR+handoffs/NN/<unique>.json 저장. 본인이 main 병합/중앙 원장/규격/출고 목록 변경 금지(00 단독). 검수 증거·PR·신규 완료/잔여를 보고하며 목표 달성까지 실제 작업한다. 자동 업데이트나 후속 대화 자동 실행을 전제하지 않는다. P0 첫 7일 검수·공개 배포를 최우선, 다음 7일 공급 병행. 기존 기록·ID·무료 인프라·기타 앱 보호.

영역: 05_통합 검증. 소유: VALIDATION.json, qa/**, tests/**. 담당 일감: QA-01~04, DEP-03~05.

첫 작업: D001~D007을 최우선으로 독립 검수한다. 언어·문법·번역·자연스러움·정중도·선수학습·문제/정답·듣기·음성·저작권을 정확한 콘텐츠 revision에 연결한다. 공개 URL 상태/렌더링/정확한 버전·출고목록 차단·PC 및 실제 iPhone Safari·학습·기록 분리·복원·오프라인 동작을 검증한다. 테스트 환경/실기기 여부를 명시한다. 결함은 소유 영역과 00에 handoff; 직접 생산 파일을 고치지 않는다. P0 출고 적합 여부와 차단 사유를 증거화한 뒤 후속 7일을 검수한다.

계획 설명만 하지 말고 실제 파일·테스트·PR을 남긴다. 타 영역 의존성은 HANDOFF_PROTOCOL.md에 맞춰 기록한다.
