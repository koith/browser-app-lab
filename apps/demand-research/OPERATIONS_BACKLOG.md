# 교집합(INTERSECTION) — 미완료 개발 일감 원장

**유지 원칙:** 이 파일은 사용자가 2026-11-03 지시한 후속 작업의 영구 체크리스트다. 작업 완료 선언은 **코드 병합 + CI + 운영 실데이터 검증** 근거가 모두 있을 때만 한다. 실패하면 원인·우회 경로와 검증 상태를 갱신한다. 임의로 항목을 삭제하거나 미검증 작업을 완료로 표시하지 않는다.

**운영 우선순위:** 실제 공개 게시글·해당 게시글에 첨부된 원본 미디어를 정확히 수집해 적법하게 보존하고, TeraBox에서 개인용 웹페이지로 검색/조회 가능하게 한다. 관련 없는 사진 대체, 비공개 접근 우회, 개인정보 및 민감 자료의 공개 업로드, 기존 원본 삭제·덮어쓰기는 금지. 전체 게시글 무누락 확보를 보장하지 않는다.

## P0 — 저장·복원 핵심

- [ ] **INT-01 테라박스 실제 저장 장애 종결.** GitHub Actions의 실운영 캡처에서 신규 원본 글/미디어 각각의 원격 SHA256 재읽기 성공, 실패 0을 여러 회차에 걸쳐 확인. 실패 수와 단계/안전한 오류 코드 기록, 기존 보관 데이터 보존. 최신 확정 근거: 이전 운영 실행 #41607742899 신규 2건 읽기 확인, 3건 실패. PR #598·#602 병합. 후속 운영 증거 필요.
- [ ] **INT-02 공개 상태에서 수집 지연·누락 최소화.** 5분 주기 실행의 실제 발동 간격/처리 소요/중복/오류와 과거 누락 범위 측정. 허용된 공개 소스만 사용. 신규 공개 게시물 삭제·접근 제한 전 저장의 확률을 높이는 재시도/안전한 장애 복구 검증.
- [ ] **INT-03 게시글별 원본 첨부 누락 복구.** URL-게시글ID-원본 첨부 순번 일치 검증. 미확보 사진은 동일 게시글의 원본 링크 또는 해당 첨부에 대해 과거 SHA 검증된 TeraBox staging에서 재시도. 타 이미지·계정 아바타로 대체 금지. 기존 부분 보관 자료 전수 조사 및 복구 가능 건 확인.
- [ ] **INT-04 저장 목록과 실파일 일치 복원.** TeraBox 게시글 post.json, entries, versioned catalog, staged media의 SHA 및 개수 대조. 손상/누락은 별도 기록. catalog 0건인데 journal 양수인 상황 재발 방지; 신선한 별도 reader로 실제 저장본 조회 검증.

## P1 — 사용 가능 서비스

- [ ] **INT-05 개인용 TeraBox 조회 서버 운영.** 인증된 FastAPI gateway를 안전한 HTTPS 호스팅에 배포, 비밀값은 서버 쪽에만 두고 동작하는 URL에서 실제 저장본 읽기 확인. 현재 Render 연결 서비스 목록에는 교집합 전용 배포가 확인되지 않음. 비용 및 민감정보 노출을 피할 것.
- [ ] **INT-06 저장본 검색·필터 실제 확인.** 본문 검색, 서비스별 조회, 첨부 보관 완료/미완료, 페이지네이션, 원문 링크, 이미지/영상 갤러리, 모바일 사용성. 실제 TeraBox 데이터(비공개)로 확인.
- [ ] **INT-07 게시글 원본 이미지 정확성 실사용 검증.** 피드 카드·상세·랭킹의 모든 미디어가 해당 게시글 출처와 일치, 이미지 1~N장 순서/실패 표시 검증. PR #598 코드는 병합됐고 정적 QA 통과; 실제 SNS 브라우저/모바일 확인 필요.
- [ ] **INT-08 웹앱 배포 안정성.** Pages 최신 main 반영 여부 및 PC/iPhone 화면·링크·팝업·로딩 실제 QA. Vercel 무료 빌드 rate limit과 GitHub Pages 배포를 구분; 무료 유지.

## P2 — 수집 확장과 분석 신뢰성

- [ ] **INT-09 SNS별 공개 게시글 수집 확대·검증.** Bluesky/Mastodon/Misskey/Lemmy 및 사용 가능한 X/Threads/Instagram/Reddit 소스의 확인된 원문/미디어 수집량과 시간대 누락률 점검. 검색 색인 미확인 링크를 실제 게시글로 가장하지 말 것.
- [ ] **INT-10 기존·신규활동 랭킹 실데이터 QA.** 기존 계정이 실제 나타나는지, 신규 분류 기준과 중복 제거 및 활동 지표 확인. 데스크톱 10열/모바일 5열의 레이아웃과 카드 상세/더 보기 테스트.

## 검증 상태 구분

- **VERIFIED**: 실파일/운영 로그/배포 페이지를 별도로 읽어 확인.
- **CODE_ONLY**: 코드·PR·CI 통과, 운영 관측은 아직 없음.
- **FAILED**: 운영 장애·테스트 실패를 확인.
- **UNVERIFIED**: 검증 근거 없음.
- 항목별 체크박스 변경 시 **근거 PR/SHA/Actions Run ID, 변경 시각, 성공·실패·한계**를 함께 기재.


## 2026-11-03 19:45 KST 재점검 — 완료된 하위 작업만 체크

아래의 **[x]는 하위 개발 작업의 완료**를 뜻한다. 위의 INT-01~INT-10 전체 완료를 의미하지 않는다. 해당 10개 최종 완료 체크박스는 모두 미체크 상태다.

- [x] PR #598: 원 게시글이 아닌 대체 사진을 쓰지 않도록 수정, 정적 브라우저 테스트 통과.
- [x] PR #604: 다중 엔드포인트 SHA 검증과 부모 폴더 준비 경로 개선, CI 통과.
- [x] PR #608: 기본 호스트 폴더 생성 실패 시 대체 호스트 복구, CI 통과.
- [x] PR #610: 반복 업로드 실패 시 외부 재시도 단축, CI 통과.
- [x] [Actions #41621602175](https://github.com/koith/browser-app-lab/actions/runs/41621602175): Pages 최신 배포 작업 성공. **아이폰 실사용 검증을 포함한 INT-08은 아직 미완료.**
- [x] [Actions #41616060341](https://github.com/koith/browser-app-lab/actions/runs/41616060341): 첫 관측 기록 3건 및 journal 기록 5건 복원, 저장된 catalog SHA 검증. **복구 전체 작업은 실패**했으며 이 항목을 INT-04 전체 완료로 취급하면 안 됨.

**운영 장애의 최신 확인 값:**
- [Actions #41616060145](https://github.com/koith/browser-app-lab/actions/runs/41616060145): fetched=7, new_verified=4, write_failures=3, 모두 `write_first_snapshot:backend_upload_missing`; **INT-01 = FAILED**.
- [Actions #41616060341](https://github.com/koith/browser-app-lab/actions/runs/41616060341): 재발행 직후 snapshot=54, journal=62, 뒤이은 독립 조회 snapshot=62, journal=62, 샘플8/8 SHA 통과. 원인 확정 전 **INT-04 = UNVERIFIED**.
- [x] PR #614: 비공개 metadata 경로에 원문 불변 저장 코드 병합 및 합성 CI 통과. **실운영 실패가 남아 INT-01/03 최종 완료는 아님.**

## 재사용할 검증 근거

- [PR #598 — 정확한 원본 이미지·부분 첨부 재시도·비공개 검색 UI](https://github.com/koith/browser-app-lab/pull/598): 코드 병합 및 사전 CI 통과. 별도 운영 실증 필요.
- [PR #602 — 대체 도메인을 이용한 TeraBox 업로드 재검증](https://github.com/koith/browser-app-lab/pull/602): 코드 병합. 실제 글 전체 저장 성공은 별도 판단.
- [Actions #41607742899](https://github.com/koith/browser-app-lab/actions/runs/41607742899): 2건 확인, 3건 실패를 집계한 기존 운영 기록.
- [Actions #41611359428](https://github.com/koith/browser-app-lab/actions/runs/41611359428): GitHub Pages 배포 성공. 정확한 게시글 원본 렌더링은 별도 QA.


## 2026-11-03 P0-01 후속 확인 — 최종 완료 아님

- [x] [PR #616](https://github.com/koith/browser-app-lab/pull/616), [#617](https://github.com/koith/browser-app-lab/pull/617), [#618](https://github.com/koith/browser-app-lab/pull/618): AES-256-GCM 암호화 원본 보존 및 복구 코드 병합.
- [x] [PR #624](https://github.com/koith/browser-app-lab/pull/624): 잔여 암호화 아티팩트 선택·메인 브랜치 출처 확인·재전송 도입, 캡처 CI 78개 및 복구 CI 19개 통과.
- [x] [PR #626](https://github.com/koith/browser-app-lab/pull/626): GitHub Actions 6시간 간격 재전송 재시도 경로 CI 통과·병합.
- [x] [PR #628](https://github.com/koith/browser-app-lab/pull/628): 건별 복구 시간 상한과 3회 연속 실패 시 서킷 브레이커, 합성 CI 통과 및 main 병합(f6a703bdf922e95fbe5eab16ef3f6717b52c42f8).
- [x] [운영 #41629506950](https://github.com/koith/browser-app-lab/actions/runs/41629506950): 원본 3건 긴급 AES-GCM 아티팩트 존재를 확인했으나 테라박스 저장 미검증.
- [x] [운영 #41630564927](https://github.com/koith/browser-app-lab/actions/runs/41630564927): 발견 25건, 원격 검증 5건, 암호화 보관 19건, 실운영 실패.
- [x] [운영 #41636436888](https://github.com/koith/browser-app-lab/actions/runs/41636436888): 발견 23건, 원격 검증 3건, 암호화 보관 18건, 실운영 실패.
- [x] [자동 복구 #41633484793](https://github.com/koith/browser-app-lab/actions/runs/41633484793): 장시간 재전송 후 잡 취소 확인, 복구 완료 아님.
- [ ] **INT-01 최종 게이트**: 원문과 원본 첨부의 테라박스 SHA256 재읽기 실패 0을 여러 운영 회차 검증, 암호화 잔여 파일 전수 복구, 원격 무결성·손실 0 증빙.
- [ ] 새 코드 [캡처 #41640004233](https://github.com/koith/browser-app-lab/actions/runs/41640004233)·[복구 #41639213292](https://github.com/koith/browser-app-lab/actions/runs/41639213292)의 실제 최종 집계 확인.
- 사용자 문의에 따라 별도 대화를 생성하던 ChatGPT 정기 작업 자동화 6ae9d47392dc8191aef2037762a8d83b 비활성화 확인. GitHub Actions 서버측 수집·복구 워크플로는 유지.

**현재 판정: CODE_ONLY(개발·CI) + FAILED(실운영), INT-01 최종 미완료.** 본문·개인정보·비밀값은 저장소에 기재하지 않음.

## 2026-11-03 순차 처리 체크 (실제 검증 기준)

- [x] **INT-10 하위 개발** — [PR #632](https://github.com/koith/browser-app-lab/pull/632) main 병합 `cf8a25c8eead84ee1cbf355dc18d3008efbf230a`. 검증된 과거 공개 글·프로필 근거로 기존/신규 분류 개선, 실패한 프로필 메타데이터 조회 재시도, 초기 빈 랭킹 방지, PC 10장/모바일 5장 동일 크기 및 마지막 줄 중앙 정렬. [랭킹 CI #41654447298](https://github.com/koith/browser-app-lab/actions/runs/41654447298), [브라우저 CI #41654447263](https://github.com/koith/browser-app-lab/actions/runs/41654447263), 계정 인덱스·제품 증거 CI 모두 PASS. **INT-10 전체 완료와 별도.**
- [x] **INT-08 배포 자동 QA 하위 개발·실운영 검증** — [PR #633](https://github.com/koith/browser-app-lab/pull/633) main 병합 `1c1b3c71087a1400d473f539a17a0c6fa820204a`, [Pages 실제 배포 #41655917301](https://github.com/koith/browser-app-lab/actions/runs/41655917301) PASS, [배포 HTML/JS SHA 읽기·데스크톱 Chromium·모바일 WebKit #41655917420](https://github.com/koith/browser-app-lab/actions/runs/41655917420) PASS. 외부 SNS 호출 없이 합성 계정으로 UI만 검증. **물리적 아이폰 사용성은 UNVERIFIED.**
- [ ] **INT-10 전체 완료** — 실제 운영 SNS 게시글로 기존/신규 분포, 필터·더 보기·순위 상세, 실제 모바일 사용성 별도 확인 전.
- [ ] **INT-08 전체 완료** — 물리적 아이폰 실사용 PASS 및 배포 주요 기능 종합 QA 전.
- [ ] **INT-02 5분 운영 주기** — Actions 예약 실행 전체 184건(조회 당시) 중 교집합 Fast Capture 예약 실행은 1건[#41636436888](https://github.com/koith/browser-app-lab/actions/runs/41636436888)만 존재함. `cron` 설정값 5분을 실측 5분으로 취급하지 않음. GitHub 예약 지연/누락과 20분가량 점유되는 저장 실패 작업을 분리 진단할 것. **FAILED/UNVERIFIED: 실제 5분 주기 불입증.**

## 2026-11-03 INT-02 지연 복구 하위 개발 검증

- [x] [PR #634](https://github.com/koith/browser-app-lab/pull/634) — 예약 실행 간격을 GitHub Actions 실기록에서 계산하며, **5분 cron 설정**을 **실제 5분 주기 성공**으로 허위 표기하지 않음. 실행 간격이 확인된 지연분만 최대 180분까지 과거 공개 게시글 추가 검색. 직전 16분 현재 공개글 수집 우선, 같은 게시글 중복 저장 방지 및 기존 24건 암호화 보관 상한 유지. [PR 오프라인 테스트 #41657330360](https://github.com/koith/browser-app-lab/actions/runs/41657330360) PASS, main 병합 `62a8c1b76781e6852aec481ebcb09c45c6232524`.
- [ ] **INT-02 최종 완료** — 실제 다음 예약 실행들에서 `INTERSECTION_CAPTURE_SCHEDULE_HEALTH`와 신규 원본 저장/복구 간격 및 누락률 재측정 전. **GitHub 예약 실행의 엄격한 5분 정시성은 검증되지 않음.**

## 2026-11-03 INT-03 동일 원본 첨부 증명 하위 개발

- [x] [PR #635](https://github.com/koith/browser-app-lab/pull/635) — 게시글별 원본 CDN URL과 첨부 순번을 SHA 검증된 staging marker에 불변 결합하고, 재시도 시 정확히 같은 링크만 허용. 기존 URL 없는 과거 marker는 최초 공개 관측 기록의 **동일 게시글·동일 첨부 번호** 링크를 통해 입증될 때만 재사용. 원본 URL 변경·손상·누락은 다른 사진으로 대체하지 않으며 기존 staging 바이트를 삭제하지 않음. [오프라인/회귀 CI #41658926885](https://github.com/koith/browser-app-lab/actions/runs/41658926885) PASS, main 병합 `93d5d4af7dc58300d5d322ed1bba0b1c99b0f45f`. **CODE_ONLY**.
- [ ] **INT-03 전체 완료** — 기존 누락 원본의 실운영 TeraBox readback SHA 전수 검증과 출처 일치, 복구 가능한 항목 0 미완료 입증 전.

## 2026-11-03 INT-04 원격 정합성 하위 검증

- [x] [PR #636](https://github.com/koith/browser-app-lab/pull/636) — 암호화 아티팩트 재전송과 catalog/journal 정비를 하나의 20분 job에서 연속 수행하던 구조를 분리, 재전송은 기존 독립 예약 workflow와 동일 maintenence 직렬화 그룹을 계속 사용. PR CI를 운영 TeraBox 유지보수 큐에서 분리. SHA 검증된 게시글 표본에 한해 **정확한 해당 게시글 미디어의 SHA 원격 재읽기 표본**을 최대 8MB로 수행, 미검증·크기제한 제외 별도 집계. `full_integrity_claim=False`, 원본·URL·계정 ID를 로그에 출력하지 않음. [오프라인 QA #41660215777](https://github.com/koith/browser-app-lab/actions/runs/41660215777) 성공, main 병합 `be8c295b6bd2d05a66c051b07a477ed7e64247a9`. **CODE_ONLY / 운영 검증 대기**.
- [ ] **INT-04 전체 완료** — 운영 journal/catalog/first-observation/첨부 SHA·개수 전수 일치 및 손상 항목 0 실증 전.

## 2026-11-04 추가 과제 — INT-11 특정 공개 SNS 계정 전체 아카이브·웹뷰

- [x] **기존 하위 완료 상태 보존** — INT-10 랭킹 코드/QA(#632), INT-08 배포 브라우저 QA(#633), INT-02 공개 수집 지연 보완(#634), INT-03 원본 URL 결합(#635), INT-04 복구/정비 분리 및 표본 SHA 검증(#636). 위쪽에 기록된 각 증빙과 `[x]`는 변경하지 않음.
- [ ] **INT-11 프로필 보관** — 선택 SNS의 공개 계정 ID·핸들·표시명·소개글·계정 필드·프로필 사진·헤더 배경 이미지·공개 활동 집계의 TeraBox 보관 및 원격 SHA 재읽기. 공개 프로필 원본 파일 미제공 시 `unavailable`로 표시.
- [ ] **INT-11 공개 관계 목록** — 팔로워·팔로잉 공개 API의 페이지별 명단/다음 커서/조회 시점·비공개 또는 제공 제한 여부. 계정의 실제 팔로워 수와 API에서 조회 가능한 페이지 수가 다를 수 있음을 별도 명시.
- [ ] **INT-11 전체 이력** — 작성 게시글·작성 답글·원본 이미지/영상/오디오 및 SNS 원본 구조화 기록을 계정별 전용 비공개 테라박스 공간에 보존. 페이지별 SHA 검증, 중단 후 이어받기, 중복/누락/실패 항목 구분. 삭제·비공개로 이미 접근 불가능한 내용은 복구했다고 주장하지 않음.
- [ ] **INT-11 대화/댓글** — 각 글의 조회 가능한 공개 댓글·답글 대화 흐름을 별도 스냅샷으로 보존. 제공자 응답의 페이지 수 제한 및 타인 댓글 미디어 원본의 보존 여부를 분리 표시.
- [ ] **INT-11 전용 웹뷰** — 비공개 세션 전용 `/account-archive`에서 프로필 헤더·사진·소개, 게시글 피드/상세, 원본 이미지·오디오·영상, 댓글, 팔로워·팔로잉 조회. 외부 제3자 스크립트나 공개 Pages 안에 인증 토큰 없음.
- [ ] **INT-11 최종 운영 게이트** — PR 병합/배포를 넘어 실제 지정 계정에 대해 TeraBox 원격 재읽기·표시·손실 없는 페이지 이어받기 및 모바일 실기 검증 완료. 현재 특정 실계정은 지정되지 않았고, **합성 CI PASS ≠ 실계정 전체 백업 완료**.

검증 기준: [PR #637](https://github.com/koith/browser-app-lab/pull/637) 공개 소스 API 기반 첫 개발. Bluesky와 Mastodon부터 지원. OAuth/플랫폼 권한이 없는 비공개 게시글·숨긴 명단·삭제물·DM은 수집하지 않음. 사용자 또는 플랫폼의 삭제·보관 제한 정책을 준수하고 대체 인물 정보로 빈칸을 채우지 않음.

## 2026-11-04 확인 — 광고 필터 회귀 및 지정 계정 아카이브

- [x] **INT-12 광고 필터 누락 재현** — [y2ujhh.bsky.social](https://bsky.app/profile/y2ujhh.bsky.social) / [gxzmcg.bsky.social](https://bsky.app/profile/gxzmcg.bsky.social): 공식 공개 `getProfile`/`getAuthorFeed`에서 계정별 최근 50개 중 영상 50개, 본문 6종 교대, 영상 `alt` 동일 문구(`nimi.wiki 실시간 SNS 영상 랭킹 프로모션 티저`) 50개 확인. 정확한 원인은 `getMedia`에서 video `alt` 소실, 28자 미만 반복 문구 미집계, gateway 피드/공개 계정 분석 필터 불일치.
- [x] **INT-12 수정 코드·회귀 CI** — [PR #638](https://github.com/koith/browser-app-lab/pull/638), `main` squash `781e63a88bff0255b0d716ba8c3c67862bcbf5f4`. 영상 `alt` 복원, 명시적 광고 설명 및 짧은 본문+미디어 반복 복합 신호, 공용/개인용 게시글 피드 및 공개 계정 분석 동일 필터. 특정 핸들 영구 차단·게시글 삭제 없음. [전용 QA #41734215370](https://github.com/koith/browser-app-lab/actions/runs/41734215370) **100건 광고 의심 탐지 + 정상 대조군 PASS**, [브라우저 QA #41734215297](https://github.com/koith/browser-app-lab/actions/runs/41734215297) PASS.
- [x] **INT-12 배포 검증** — [Pages #41734837884](https://github.com/koith/browser-app-lab/actions/runs/41734837884) 및 [배포 HTML/JS SHA + Chromium/WebKit #41734837937](https://github.com/koith/browser-app-lab/actions/runs/41734837937) 성공(광고 필터 병합본). 후속 PR #637을 병합한 최신 조합의 배포 검증 결과는 별도 확인 필요.
- [x] **INT-11 코드·합성 테스트 완료** — [PR #637](https://github.com/koith/browser-app-lab/pull/637), `main` squash `8b4c35305623d9cd50c56752357537dc09b10108`. Bluesky/Mastodon 공개 계정 지정, 원본 사진/영상/음성 및 작성 글·댓글·공개 대화·프로필 헤더·팔로워/팔로잉 명단의 TeraBox SHA 기반 보관 코드와 인증 전용 `/account-archive` 웹뷰, 피드/상세/댓글 탭. [합성 CI #41735015243](https://github.com/koith/browser-app-lab/actions/runs/41735015243): Python 86개 통과, Chromium·모바일 WebKit 화면 PASS. **CODE/CI 검증**이며 실제 보관 및 개인용 서버 배포 성공과는 별개.
- [ ] **INT-11 실운영 완료** — 현재 확인된 Render 서비스 목록에 교집합 전용 게이트웨이가 없고, 실계정 타깃 지정·TeraBox 인증·원본 SHA 전체 재읽기·iPhone 실기 시험도 아직 미입증. 비공개/삭제 데이터나 접근 제한된 관계 명단은 포함 완전성 주장 금지. 기존 `[ ]` 하위 운영 조건 유지.
- [ ] **INT-01 실운영 저장·복구 장애** — 최신 실패 [빠른 수집 #41706181750](https://github.com/koith/browser-app-lab/actions/runs/41706181750): 발견 29, 테라박스 검증 5, storage_failures 19, 암호화 보관 19, DEGRADED_STORAGE. [복구 #41709127089](https://github.com/koith/browser-app-lab/actions/runs/41709127089): 실제 원본+미디어 SHA 검증 2, 실패 3, 잔여 14. 원격 전체 복구를 `[x]`로 표시하지 않음.
