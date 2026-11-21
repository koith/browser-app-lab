# 데이터 계약 v1.0.0 (현재 런타임 호환)
상태: 승인 기준. SPEC.md의 정규화 모델은 미래 목표이며 현재 앱의 실제 v0.1 형식을 먼저 보존한다. 00만 계약 변경 승인.
## 현재 런타임
index.html은 같은 디렉터리 curriculum.json 및 lessons.json을 fetch한다. 기존 key/타입 및 JSON 배열 순서를 깨지 않는다. 실제 앱은 아직 출고 목록을 적용하지 않으므로 03이 구현하고 05가 반드시 검증하기 전 정식 출시 금지.
- curriculum.json: version, status, target, sources(출처 ID→URL), days 배열. 각 day: id=D001..D120, day=1..120, week=1..18, level=A1/A2, theme/title, minutes=60, kind=lesson/review/assessment, contentStatus, reviewStatus, sources[]. 모든 ID 유일, day 오름차순, 월간 30/60/90/120, A1 종합 63. 현재 순서 유지. 상태는 원장/릴리스의 검증 증거를 대신하지 않는다.
- lessons.json: version, status, license, lessons 배열. 각 lesson: id/day 일치, objective/grammar/note/task 문자열, alphabet(선택), words:[[tr,ko]], examples:[[tr,ko]], dialogue:[[role,tr,ko]], questions:[{id,type:"choice",prompt,answer,choices[]}], status/languageReview/audioReview/sources[]. lesson은 반드시 curriculum의 day에 매핑. examples와 dialogue/questions 최소 1개, 복습일 words 비어도 됨. 질문 ID Dxxx-Qn, 보기 중 정답 정확히 하나. NFC, 터키어 특수문자 보전.
- 앱 기존 저장 키 turkce120-v1: a,b 프로필 객체에 done,attempts,cards,seconds,studyDates,departure. 단어 key Dxxx-Vn(배열 순서 기반), 문제 key Dxxx-Qn. **이미 공개된 단어 배열 삽입·정렬·삭제·기존 문제 ID 재사용 금지**. 추가는 끝에만, 내용 변경은 새 revision 및 필요한 마이그레이션. 학습 상태 백업/복원 및 향후 동기화 호환. 개인 기록은 git에 넣지 않는다.
- 스키마: schemas/curriculum.schema.json, schemas/lessons.schema.json, schemas/handoff.schema.json. 구조 검증과 교차 파일/내용 검증을 구분한다.
## 추가 데이터: 호환 방식
기존 필드는 제거하지 않는다. 확장 파일을 별도 두고 03에서 지원한 뒤 사용한다. 최초 7일 출고는 기존 형식 유지. 향후 상세 규격 승인 전 런타임 필수 필드 추가 금지.
01 curriculum-mapping/ : {dayId,objectiveIds,cefrDescriptors[],grammarIds[],vocabTargets[],prerequisiteDayIds[],sourceEvidence[]} 고정 학습목표. 01은 curriculum.json 소유; 상세 매핑에 정의한 식별자는 변경 금지.
02 content/ : grammar/vocab/examples/assessment/lesson metadata 및 상호 참조. lesson revision 또는 새 콘텐츠 ID, source evidence, review 상태. 정규화 데이터 도입은 ADR 후 결정한다. 당장은 기존 lessons.json authoritative authoring file. 한 day를 여러 파일에서 중복 원본 관리하지 않음.
04 audio/manifest.json : {schemaVersion, assets:[{id,lessonId,kind,targetId,text,locale,provider,voice,license,sourceUrl,path,sha256,reviewStatus}]} ; text는 lessons의 정확한 NFC 문자열, locale tr-TR, kind word/example/dialogue/question, targetId는 Dxxx-Vn/Dxxx-En/Dxxx-Tn/Dxxx-Qn. n은 1부터 시작. 고정 발행된 순서/텍스트 변경은 새 asset ID + revision; 음성 파일은 mp3 우선, hash 검증. 합성 음성은 원어민 녹음으로 표기 금지. license 및 영리/재배포 가능성 확인. audio/ 및 conversation/의 runtime 인터페이스는 ADR 승인 후 소비.
05 qa/ : 독립 검수 증거. {entityId,revision,sourceRevision,reviewType,method,reviewer,sourceEvidence,findings,result,at,evidencePath}; author/self-check와 independent review 명확히 구별. 증거는 commit SHA나 blob hash와 시험 환경을 구체적으로 명시한다.
## 콘텐츠 검수
문법/철자/번역/자연스러움/정중도/선수학습/정답/중복/난이도/대상 어휘 범위. 항목별 공식 교육 목표와 사전·문법서·용례 연결. 단순 source ID 나열은 검수 증거 아님. 새 문법 또는 어휘가 먼저 등장할 경우 미리 관용표현으로 설명하고 평가 대상과 구분. 모든 새 ID 참조는 존재해야 하고 학습된 개념 범위 이내.
검수 stage draft → structure_checked → linguistic_reviewed → audio_reviewed → release_ready → published. 각 상태는 검수 유형별 evidence와 정확한 revision에 연결. 오류 수정 시 관련 검수 무효화, 재검수 필요. 오디오 검수가 해당 없는 항목은 이유 적기. 콘텐츠를 독립 검수한 뒤에만 published.
출고: 00만 RELEASE_MANIFEST.json 변경. release-ready day 범위, 정확한 데이터/오디오 revision/hash, 배포 기록 고정. 신규 학습 분량은 기존 진도를 건드리지 않는 minor release, 오타 수정 patch(의미/점수 불변), breaking change major + 이관 계획. appVersion/courseVersion/schemaVersion은 독립. 이미 발행된 점수와 ID 보존; 정답 변경 시 새 문제 revision, 기존 기록 유지 및 공지.
