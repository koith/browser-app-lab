# Türkçe 120 — 설계 기준 v0.1.0
작성일 2026-11-21. 상태: 초안, 출국 예정일 2027-03-21(가정; 설정에서 수정).
## 목표와 범위
한국어 모어 성인 두 명, 120일/60분. A1 수행 능력 우선, A2 도전. CEFR 인증 아님.
CEFR 2020 https://www.coe.int/en/web/common-european-framework-reference-languages/cefr-descriptors-search
Maarif 2025 https://turkiyemaarif.org/news/turkcenin-yabanci-dil-olarak-ogretimi-programinin-3-baskisi-tamamlandi ; 원문 https://turkiyemaarif.org/uploads/168b69b2349aed.pdf
YEE https://yee.org.tr/tr/turkce-ogretimi/materyaller
무료 강의 참고 https://turkish.yasar.edu.tr/kaynaklar/kaynaklar/?l=en ; https://www.duolingo.com/course/tr/en/Learn-Turkish
분산학습 https://doi.org/10.1111/lang.12479 ; 어휘 인출 https://www.cambridge.org/core/journals/studies-in-second-language-acquisition/article/abs/review-of-laboratory-studies-of-adult-second-language-vocabulary-training/18F0A5D1FFC829CE05931B2EEE83124A
공식 교재 원문 복제 금지. 기준/문법적 사실만 참고. 한국어 모어 학습자의 편의상 SOV와 접미사 개념을 연결하되 한국어 조사/높임말과 일대일 대응시키지 않음. 터키어 발음/모음조화/격/명사문 → 현재 → 과거 → 미래 → 넓은시제/가능/연결 순서. 초기 관용 표현은 덩어리로 학습하고 문법 상세를 나중에 명시.
## 고정 교육 과정
curriculum.json: 120일 초안, 주차별 17주와 마지막 평가. 매주 복습/시험, 30/60/90/120일 월간 평가. 63일에 A1 종합평가. 편집은 버전 분기와 검수 후 발행. 초안 공개 개발판은 정식 학습판 아님. 기존 발행 과정의 ID와 평가 정답은 덮어쓰지 않음.
일일 10분 복습, 10분 어휘, 10분 문법/구성, 15분 듣기/따라 말하기, 10분 실전회화, 5분 확인시험. 평가일에는 시간을 기능별로 조정. 어휘 1000 활용+500 이해 목표(표제어/구문을 구분 집계, 활용형은 별도 항목으로 과대집계하지 않음). 모든 문제는 오늘까지 교육한 개념 또는 명시적 관용표현만 사용.
## 평가 규격 초안
일일 객관식/입력/배열/받아쓰기/말하기. 주차는 60분 내 4개 기능(듣기, 읽기, 쓰기, 말하기/상호작용), 월간은 새로운 상황으로 전이. 영역별 25점, 내부 통과 기준 총 80점 및 각 영역 15점 이상을 파일럿 검증 후 확정. A1: 예측 가능한 대화에서 느린 반복 지원하에 인사, 정보, 주문, 길, 약속 대응. A2: 일상적 정보 교환, 간단한 과거 사건/계획 설명, 대화 수습. 말하기는 과업 충족/이해 가능성/문법 어휘/상호작용 각각 0~3(0 미수행, 1 많은 도움, 2 일부 도움, 3 독립적으로 수행), 25점 환산. 자동 전사 일치율은 발음 정확도/CEFR 평가와 구분. 두 학습자가 상호 역할극 및 자가 평가; 원어민/교사 검토 별도.
## 콘텐츠 모델
course_version {id,status,source_ids,created_at,sha256}; lesson {id,version,day,level,objective,prereq_ids,grammar_ids,vocab_ids,examples,dialogue_ids,exercise_ids,estimated_minutes,source_ids,review_status}; grammar {id,title,ko_explanation,rule,exceptions,examples,prereq_ids,source_ids}; vocabulary {id,lemma,tr,ko,pos,sense_id,inflections,active_or_receptive,first_day,example_ids,audio_id}; example {id,tr,ko,grammar_ids,vocab_ids,register,source_ids}; dialogue {id,scenario,roles,turns,register,alternatives}; assessment {id,level,day,skill,question_ids,rubric_id}; question {id,type,prompt,choices,accepted_answers,explanation,prereq_ids,skill,audio_id,first_day}; audio {id,text,locale,provider,voice,license,path,sha256,review_status}; review {entity_id,version,review_type,reviewer,result,evidence,at}; sources {id,url,title,accessed_at,scope}. Dxxx and question IDs stable. Source reference is not item-level review evidence. Approval statuses separate draft, structure_checked, linguistic_reviewed, audio_reviewed, published; human or independent corroboration and documented evidence required. 
## 웹앱 IA 및 기능 명세
하단 5탭 홈/수업/단어장/복습/설정. 홈: 진도, 출국 D-day, 누적 시간, 연속일, 오늘 및 취약 영역; 수업: 6단계, 단계 이동, 문법/회화/듣기/시험, 복습 연결; 단어장: 검색, 상세 활용형, 예문, 즐겨찾기, SRS; 복습: 오답/기한/취약 영역; 설정: 계정, 속도, 출국일, 다운로드/복원, 오프라인 저장. 문법 교재와 시험·통계는 수업/홈에서 진입. iPhone 390px 세로, 44px 탭, 한국어/터키어 구분, 특수문자 키보드, 녹음 권한 안내; WCAG 대비/키보드 탐색.
## 기술 설계
공개 학습 정적 콘텐츠 GitHub Pages 후보, 앱과 자료를 동일 경로에 배포. 데이터와 비밀키를 공개 저장소에 보관하지 않음. 기존 browser-app-lab 하위 apps/turkish-study만 변경. Supabase Auth 및 독립 DB 선택 우선; 현재 연결 계정에 운영 프로젝트 2개 있으므로 기존 DB 수정 금지. 추가 무료 슬롯/비용 확인 전 신규 프로젝트 생성 보류. 사용자 데이터는 RLS auth.uid() 기반 독립 행; 학습 이벤트 UUID로 중복 방지, 오프라인 큐 재전송, 충돌 해결과 백업 복구 시험. 현 개발판 localStorage는 동기화 또는 영구 보존 아님. 
음성: Web Speech getVoices tr-TR 확인 후만 실행; 실제 기기 미검증. Piper tr_TR 음성별 라이선스 확인 후 MP3/OGG 고정 파일 제작과 청취 검수; Safari에서 MP3 우선. 녹음 MediaRecorder, 음성 안 되는 경우 텍스트 대체; STT SpeechRecognition/webkitSpeechRecognition 기능 탐지, 지원/권한/개인정보 확인. Whisper 서버/로컬 후보(기기 성능/비용 시험). AI 자유 대화는 고정 분기형 회화를 기본으로, 후에 옵션 서버 프록시 Gemini free tier 등 비교; 민감한 음성/메시지 전송 기본 금지, API 키 서버만. 무료 API 제한·데이터 정책 변동, 비용 0원 보장 아님. GPT 구독 API 별개.
https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/getVoices
https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
https://github.com/rhasspy/piper/blob/master/VOICES.md
https://ai.google.dev/gemini-api/docs/pricing
https://supabase.com/kb/faqs/platform/free-postgres-for-side-projects
https://supabase.com/docs/guides/database/postgres/row-level-security
## 제작 순서와 출고 게이트
1 기준 조사/목차/데이터/원장 → 2 첫 7일 학습·앱 수직 구현 → 3 독립 인증/동기화/백업/기기 검증 → 4 A1 전체 초안·검수·출고 → 5 A2 전체 제작·검수 → 6 실전 회화, 듣기, 평가, 출시. 병행 제작은 가능하되 순서는 과정에서 고정.
배포 성공은 실제 URL 응답+화면 렌더링+기능 검증이 필요. 콘텐츠 완료는 120일/어휘/문항/원어민 자연스러움/음성/선수학습 검증 및 출처·검수 기록. 기기 테스트는 iPhone Safari와 PC, 계정 교차 접근 차단, 동기화/오프라인/복원, 마이크/발음. 데이터 검수는 자동 구조 검사와 언어 검수 분리. 
