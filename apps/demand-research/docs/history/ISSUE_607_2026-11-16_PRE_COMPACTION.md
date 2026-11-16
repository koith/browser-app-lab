# 교집합 Issue #607 — 2026-11-16 정리 전 원문 영구 스냅샷

출처: https://github.com/koith/browser-app-lab/issues/607

이 파일은 **원본 23,674자 이슈 본문을 변경하지 않고 보존**합니다. 71개 기존 댓글은 GitHub 원래 이슈에 그대로 남습니다.

---

2026-11-03 사용자 지정 장기 작업 목록입니다. **코드 병합 또는 합성 CI만으로 체크하지 않으며**, GitHub Actions 운영 실행 로그·원격 바이트 재읽기·실사용 화면에서 성공을 확인한 후 체크합니다. 상세 증빙은 [OPERATIONS_BACKLOG.md](https://github.com/koith/browser-app-lab/blob/main/apps/demand-research/OPERATIONS_BACKLOG.md)에 갱신합니다.

## P0 — 실운영 핵심
- [ ] **INT-01** 테라박스 실제 저장 장애 해결: 새 게시글 및 원본 미디어 원격 SHA256 읽기 검증, 다회차 저장 실패 0 및 오류 분류/복구
- [ ] **INT-02** 공개 상태의 게시글 빠른 수집: 5분 실행 실제 간격/누락률 측정, 제한 전 저장 지연·누락 최소화
- [ ] **INT-03** 원본 첨부파일 누락 재확보: 원 게시글과 첨부 순번·원본 링크 매칭, 기존 부분 저장본 회복, 타 이미지 대체 금지
- [ ] **INT-04** 원격 파일과 웹 조회 목록 정합성: journal/catalog/first capture/media 실제 SHA/건수 일치 및 손상 항목 명시

## P1 — 서비스 완성
- [ ] **INT-05** 개인용 TeraBox 조회 서버 HTTPS 인증 배포 및 실제 저장본 열람
- [ ] **INT-06** 본문 검색·SNS/첨부 상태 필터·더 보기·사진/영상 보기의 운영 데이터 검증
- [ ] **INT-07** 피드/상세/랭킹 원본 이미지 일치 여부와 사진 1~N장 순서, iPhone 실기 검증
- [ ] **INT-08** GitHub Pages 배포 및 PC·iPhone QA, 무료 인프라 유지

## P2 — 수집·랭킹
- [ ] **INT-09** 여러 SNS 원문 출처 검증 및 실제 게시글 수집량·누락 점검
- [x] **INT-10** 기존/신규 활동 랭킹 분류, PC 10열·모바일 5열, 상세 조회 검증 — 2026-11-13 LIVE SNS 실데이터 검증 PASS (#43413717379: Chromium PC 기존/신규 167/77, WebKit 모바일 107/57, 10열/5열·상세·더보기 통과; 실제 iPhone 기기 검증은 INT-07·08에서 계속 미완료)

## 이번 회차에서 완료한 하위 개발 작업 (2026-11-03)

> 아래 **[x]는 기능별 하위 개발·검증**이고 INT-01~INT-10 전체 항목의 완료를 뜻하지 않습니다. 운영 재검증 이전에는 위의 10개 체크를 그대로 비워둡니다.

- [x] PR #598 — 원 게시글이 아닌 다른 이미지를 표시하는 폴백 제거 및 자동 테스트 통과
- [x] PR #604 — 테라박스 이중 엔드포인트 checksum·폴더 readiness 검증 코드 병합
- [x] PR #608 — 폴더 생성 실패 시 대체 엔드포인트 복구 코드 병합
- [x] PR #610 — 실패한 업로드의 재시도 지연 축소, CI 통과
- [x] [PR #614](https://github.com/koith/browser-app-lab/pull/614) — 첫 공개 관측 자료를 보존하는 **불변 flat 메타데이터 경로** 추가, 원본 사라진 뒤 복구 회귀 테스트 통과, main 병합 `2722c1972b0b6dbcd5c8ba83d15d90bb0e3a1b5f`
- [x] [PR #618](https://github.com/koith/browser-app-lab/pull/618) — 실패한 `main` 캡처 완료 즉시 해당 실행의 **암호화된 원본 자료만** 읽어 TeraBox SHA 재검증을 자동 시작하는 워크플로; 원본 실자료/토큰은 공개하지 않음. CI 2개 성공, main `f66ef370ebbdfd5b710ff84f68fbc426ee9f7942` 병합. **운영 재전송 성공 확인 전 INT-01 미완료**.
- [x] [Actions #41629506950](https://github.com/koith/browser-app-lab/actions/runs/41629506950): 신규 7개 중 4개 TeraBox 검증 성공 / 3개 업로드 실패, 그러나 **암호화 복구 파일 3개(보관물 총 3,540,865바이트)**가 실제 Actions artifact로 생성됨을 별도 조회 검증. **3개는 아직 TeraBox 영구보관 미검증.**
- [x] [PR #617](https://github.com/koith/browser-app-lab/pull/617) — 테라박스 사전 연결 점검 실패/3회 연속 저장 실패에도 공개 원문·해당 글 원본 이미지를 암호화 임시 보관으로 제한적 수집 지속. 최대 24개 고유 원본/회차로 제한하고 TeraBox 미검증 자료는 성공에서 제외. CI 75개 통과, main f3493a0e823f6ac754ba174cb7e62b3f28a31941 병합. **실운영 0 미복구 확인 전 INT-01 미완료.**
- [x] [PR #616](https://github.com/koith/browser-app-lab/pull/616) — AES-256-GCM 암호화 실패 버퍼, 최초 공개 원문·원본 이미지 선보존, GitHub Actions 임시 보관, 수집 종료 후 테라박스 자동 재전송과 SHA 검증 구현. **오프라인 테스트 72개 통과, main df440c7167ce3d8ce26d54f21854859350f9a519 병합**. 운영 성공과 구분.
- [x] [PR #615](https://github.com/koith/browser-app-lab/pull/615) — 저장 목록의 첫 조회가 예전 버전을 반환할 때 독립 재조회·최대 4회 재검증을 수행하고, 계속 불일치하면 실패로 처리. 합성 회귀 테스트 통과, main 병합 `63e4ab718d726914adcd36cafb86bad5c468c53f` (INT-04 전체 완료 아님).
- [x] [Pages 배포 #41621602175](https://github.com/koith/browser-app-lab/actions/runs/41621602175) — 배포 작업 성공 (INT-08의 아이폰 실사용 QA는 별도)
- [ ] INT-01 **운영 저장 장애 종결** — 신규 실데이터 0실패 다회차 재읽기 전
- [ ] INT-04 **저장 목록과 원격 기록 완전 일치** — 전수 확인 전

**최근 운영 증빙:** [캡처 #41616060145](https://github.com/koith/browser-app-lab/actions/runs/41616060145)는 신규 검증 4건·업로드 실패 3건, [복구 #41616060341](https://github.com/koith/browser-app-lab/actions/runs/41616060341)는 저장 목록과 기록 사이 일시적 8건 차이가 났고 후속 검사에선 62건으로 일치했습니다. 새로운 [#614 운영 캡처 #41623325173](https://github.com/koith/browser-app-lab/actions/runs/41623325173)는 최종 확인 전입니다.

## 최근 진행과 미해결 장애
- [PR #598](https://github.com/koith/browser-app-lab/pull/598): 정확한 게시글 이미지 및 부분 첨부 재수집 코드는 병합. 실데이터 완결 여부 미확인.
- [PR #604](https://github.com/koith/browser-app-lab/pull/604): 대체 TeraBox 엔드포인트 SHA 검증, 폴더 생성 전파 확인, 10개 작업 원장 — 병합 및 오프라인 테스트 통과. 실운영 후속 검증 중.
- 실운영 캡처 #41610415087에는 **write_first_snapshot:backend_missing_path 2건**, **write_post_and_verify_media:backend_missing_path 1건**, **원격 읽기 확인 2건**이 기록됐음. 사용자 식별 정보/개인 원문은 로그에 인용하지 않음.

**금지:** 삭제/비공개 접근 제한 우회, 다른 게시글 이미지 대체, 기존 테라박스 객체 삭제/덮어쓰기, 공개 저장소에 비공개 원문·토큰·이미지 게시, 검증 없는 완료 표기.

**운영 완료 게이트:** VERIFIED/FAILED/UNVERIFIED/CODE_ONLY를 명확히 구분하고 작업 종료시 근거 링크를 남긴다.

## 2026-11-04 INT-01 복구 코드 하위 개발

- [x] **INT-01 하위 개발 — 테라박스 암호화 보관 묶음 자체 복구 코드**: [PR #675](https://github.com/koith/browser-app-lab/pull/675) 병합 `5a55dfb86cde8e5faa3b4217a089e2a65b4e8e95`, [복구 CI #41760906565](https://github.com/koith/browser-app-lab/actions/runs/41760906565) / [수집 CI #41760906643](https://github.com/koith/browser-app-lab/actions/runs/41760906643) 성공. 14일짜리 GitHub 임시 아티팩트가 없어져도 TeraBox SHA256 검증을 거친 AES 암호화 원본 묶음에서 게시글·동일 첨부를 다시 복원하도록 기존 복구 코드 개선. 손상·경로 변조·다른 작업 아티팩트 혼입 테스트. **CODE_ONLY: 운영 전체 복구 성공 주장 아님.**
- [ ] **INT-01 최종 운영 게이트 유지**: 최신 운영 복구 실행에서 원본 글·미디어 원격 SHA256 검증, 보관된 암호화 원본 미복구 0, 다회차 신규 저장 실패 0, reader와 catalog 일치 확인 후에만 상단 INT-01을 체크할 것. 현재 운영 재생은 별도 실행 [#41761099176](https://github.com/koith/browser-app-lab/actions/runs/41761099176)에서 검증 중.


## 2026-11-04 독립 수행 가능한 UI 오류 수정

- [x] **INT-06·09 하위 개발 — 검증된 SNS 원문 수량 오류 수정**: [PR #679](https://github.com/koith/browser-app-lab/pull/679), main `a5108009c09b1b5946e9dcae1b2f9d4ded725867`. 검색 색인 후보 3건과 검증된 게시글 1건이 동시에 있을 때 `-2건`으로 나오던 실제 피드 숫자 오류 수정. 날짜 변경으로 게시글 0건이어도 `-3건`으로 표시하지 않음. 인덱스 후보는 별도 `원문 미확인 링크 N건`으로 유지하며 실제 게시글로 가장하지 않음. 브라우저·광고 필터·랭킹·검색 회귀 CI 6개 통과. **상위 INT-06·09 전체 완료 아님.**
- [x] **INT-06·09 코드 배포·데스크톱/모바일 WebKit QA 확인**: [Pages #41763516060](https://github.com/koith/browser-app-lab/actions/runs/41763516060) PASS 및 [배포본 Chromium/WebKit QA #41763516178](https://github.com/koith/browser-app-lab/actions/runs/41763516178) PASS. **물리적 아이폰 및 실제 SNS/테라박스 운영 데이터 QA는 별도 미완료; INT-06·09 상위 일감 전체 완료 아님.**


## 2026-11-04 다중 SNS 게시글 ID 충돌 복구

- [x] **INT-09 하위 개발 — 서비스별 게시글 ID 충돌로 Threads·Instagram 링크가 숨겨지는 오류 수정**: [PR #681](https://github.com/koith/browser-app-lab/pull/681) 병합 `fa3f1bc9ceb10c57994c94473e69f14a05bcb610`. 검증된 X 게시글과 같은 게시글 ID 문자열을 사용하더라도 Threads/Instagram 원문 미확인 링크를 숨기지 않음. 같은 X 게시글의 중복 검색 링크는 기존대로 제외. 소스별 URL·게시일 검증은 유지하고 원문 미확인 링크를 게시글로 위장하지 않음. 기존 브라우저·광고필터·랭킹·검색·계정 아카이브 회귀 CI 6개 PASS, main 코드 재조회 확인. **CODE/CI VERIFIED, 상위 INT-09 전체 완료 아님.**
- [x] **INT-09 하위 개발의 Pages 배포·배포본 브라우저 QA 확인 (2026-11-04)**: [Pages #41764096661](https://github.com/koith/browser-app-lab/actions/runs/41764096661) `fa3f1bc9` 배포 PASS; [배포본 QA #41764096487](https://github.com/koith/browser-app-lab/actions/runs/41764096487) `PAGES_DEPLOYED_MAIN_BYTES_SHA256_PASS` 및 Chromium 데스크톱·WebKit 모바일 시뮬레이션의 `PAGES_PUBLIC_UI_PASS` 확인. 테스트는 합성 랭킹 카드 1개/팝업 열기·닫기·반응형 레이아웃이며, **실제 다중 SNS API 수집량·누락률 및 물리적 iPhone 실기 검증은 미완료**. 따라서 INT-09·08 상위 체크 미완료.


## 2026-11-04 INT-06·11 독립 신속 수정 — 개인용 아카이브 화면 요청 경합

- [x] **INT-06·11 하위 개발 — 탭·계정 전환/댓글 상세 비동기 요청 경합 수정**: [PR #684](https://github.com/koith/browser-app-lab/pull/684) main 병합 `b1d326a4837c484f159806c7a7570947041bce97`. 이전 탭의 늦은 피드 응답이 새 탭의 loading 상태나 목록을 덮어쓰지 않으며, 이전 게시글의 늦은 댓글 응답이 다른 게시글 상세에 나타나지 않도록 세대별 요청 일치 검증. 기존 저장 데이터·수집기·자격증명 변경 없음.
- [x] **CI/브라우저 검증**: [Actions #41766555950](https://github.com/koith/browser-app-lab/actions/runs/41766555950), Python 단위 86개 PASS + 데스크톱 Chromium 및 모바일 WebKit `ACCOUNT_ARCHIVE_BROWSER_PASS` 각각 확인. GitHub main에 수정 파일 반영된 내용 별도 재조회 확인. **CODE/CI VERIFIED**.
- [x] **PR #684 병합본 main Pages 배포 확인**: [GitHub Pages #41766744423](https://github.com/koith/browser-app-lab/actions/runs/41766744423) `b1d326a4837c484f159806c7a7570947041bce97`, `Deploy to GitHub Pages` 성공 및 전체 워크플로 완료. **정적 Pages 배포 성공은 별도 HTTPS 인증 개인용 아카이브 서버 배포·실데이터 열람 증거가 아님.**
- [ ] **INT-06·11 상위 운영 조건 미완료**: HTTPS 인증 서버에 실제 TeraBox 보관본 연결·원격 SHA 재읽기·실계정 이력/모바일 기기 검증이 아직 필요. 코드/합성 브라우저 성공을 저장·전체 아카이브 완료로 취급하지 않음.


## 2026-11-04 빠른 개발 일감 처리 — #689 / #690

- [x] **INT-06·11 하위 개발 — 보관 게시글 더 보기 실패 시 기존 목록 보존·정확한 오프셋 재시도**: [PR #689](https://github.com/koith/browser-app-lab/pull/689) main squash `dad6d0430fe68eded42ee11601dd7cc7c5777b68`. 추가 페이지가 HTTP 503으로 실패해도 기존 보관본 카드를 지우지 않고 실패한 위치에서 재시도. 첫 페이지 오류도 재시도 가능, 형식 오류와 빈 페이지의 무한 더 보기 방지. [회귀 CI #41768796504](https://github.com/koith/browser-app-lab/actions/runs/41768796504) Python 86개 + Chromium/WebKit PASS. main 파일 재읽기 검증. **CODE/CI VERIFIED**, 실 TeraBox 보관본 운영 데이터는 미검증.
- [x] **INT-10 하위 개발 — Mastodon·Misskey 서버별 동일 게시글 ID 충돌 해결**: [PR #690](https://github.com/koith/browser-app-lab/pull/690) main squash `f4caec7bf4f236e0f180b692402d946c99ac6c35`. 플랫폼+로컬 ID 단독 기준 대신 동일 플랫폼·공개 계정 프로필·게시글 ID 단위로 중복 제거. 서로 다른 인스턴스/계정의 활동을 누락시키지 않으며 같은 계정의 중복글은 계속 제외. [랭킹 CI #41768927160](https://github.com/koith/browser-app-lab/actions/runs/41768927160) PASS, main 코드 재조회 검증. **CODE/CI VERIFIED**.
- [ ] **INT-06·11·10 최종 운영 게이트 유지**: 실제 SNS/개인 테라박스 운영 데이터, 전체 오프셋 이어받기, PC·물리 iPhone 실사용 검증이 아직 필요. 합성 QA 성공만으로 상위 과제를 완료 처리하지 않음.


## 2026-11-04 INT-13 — 공개 영상 트렌드·아카이브 분석 (Twidouga 참고)

참고: [twidouga 24시간 랭킹](https://www.twidouga.net/ko/ranking_t1.php) / [3시간 급상승](https://www.twidouga.net/ko/ranking_hot.php). 해당 서비스의 자체 **저장 횟수**와 교집합에서 관찰하는 SNS의 공개 **반응 수**는 다른 지표이며, 수집 성공량이나 개인 구매 의도로 동일시하지 않는다. 원문 삭제·비공개 이후 재생·복구를 보장하지 않는다.

- [x] **INT-13-A 영상 트렌드 패널 1차 개발·CI**: [PR #694](https://github.com/koith/browser-app-lab/pull/694) main squash `1f9995bbabf957de99827eb62f89b2c9c1424478`. 검증된 기존 공개 SNS 게시글만 재사용해 최근 3시간/24시간/7일/30일/최신/월별(현재 불러온 기록만) 동영상 분류. 중복 제거·출처 원문 링크·다중영상 개수·공개반응 제공 여부·더 보기. 광고·접근 제한·원문 미확인 링크·개인 TeraBox 데이터 제외. 새 네트워크 수집·영구 원본 다운로드 없음. [랭킹/영상 CI #41769826723](https://github.com/koith/browser-app-lab/actions/runs/41769826723)에서 `PUBLIC_VIDEO_TRENDS_QA_PASS`, `PUBLIC_ACTIVITY_RANKING_QA_PASS` 로그 확인; 기존 게시글 브라우저·광고 필터 CI도 통과. main 코드 재조회 완료. **CODE/CI VERIFIED, 운영 전체 완료 아님.**
- [ ] **INT-13-B 최신 Pages 배포·실운영 영상 데이터 QA**: [배포 #41770338666](https://github.com/koith/browser-app-lab/actions/runs/41770338666), [배포본 Chromium/WebKit #41770338689](https://github.com/koith/browser-app-lab/actions/runs/41770338689)의 최종 결과 확인. 실제 SNS 영상 수집량/플랫폼별 누락과 물리적 iPhone 사용성 검증 전까지 미완료.
- [ ] **INT-13-C 진짜 급상승 속도 측정**: 별도 시각에 관측된 동일 공개 영상의 반응 수 변화·시간당 변화량과 최초 관측 시점/표본 커버리지 기록. **단일 시점 반응 합계는 '급상승'으로 단정하지 않는다.** 미제공 반응은 0으로 채우지 않는다.
- [ ] **INT-13-D 과거 월별 원본 검증 아카이브**: 실 TeraBox에 저장된 공개 원본과 메타데이터를 월별로 조회, SHA 재읽기·원본 게시글 링크 일치·삭제/접근제한 상태 표시. 현재 1차 UI의 월별 목록은 단지 **불러온 게시글** 대상.
- [ ] **INT-13-E 선택 URL 보관/연속 검토**: 공개 원문 URL로 개별 영상 확인, 여러 영상 순서와 연속 보기 지원 검토. 보관은 INT-01 저장 복구/인증 기반 서버 준비 후 제공자 이용조건·권리·접근 제약을 확인하여 수행. 원본 삭제/비공개 우회·무단 재배포 없음.
- [ ] **INT-13-F 지표 교차 비교**: 출처별 영상 수/유효 반응 제공률/관측 추세와 외부 서비스의 공개 집계(이용허락·출처 확인된 경우)를 다른 축으로 표시. 외부 저장 수치를 자체 통계로 가장하거나 소비·구매 전환을 확정 추론하지 않는다.


## 2026-11-04 독립 소형 작업 연속 완료 — PR #697~#701

- [x] **INT-13-F 하위 기능 — 영상 SNS 출처별 게시글 수·공개 반응 제공률**: [PR #697](https://github.com/koith/browser-app-lab/pull/697), main squash `f55a752c8e026a7c8ef00140f399df94272b10eb`. 검증된 공개 영상만 플랫폼별로 집계하고 SNS별 선택 필터 및 실제 반응 제공 건수/전체 건수 표시. 저장 횟수·조회수를 추정하지 않음. [랭킹+영상 CI #41778044044](https://github.com/koith/browser-app-lab/actions/runs/41778044044)와 기존 게시글·광고·계정 아카이브 회귀 PASS. **CODE/CI VERIFIED**. 외부 비교 사이트 저장량과의 직접 계량 비교는 여전히 미완료.
- [x] **INT-08·13-B 배포본 영상 UI QA 강화**: [PR #698](https://github.com/koith/browser-app-lab/pull/698), main `ba694a4240a5cffdcd7c8a95f7d568e1fb160f56`. 배포 HTML·랭킹·영상 JS 3종의 실제 SHA256 일치, 실제 Pages에서 합성 SNS 2곳의 영상 카드·출처 필터·게시글 링크·기간/월별 선택·PC Chromium·모바일 WebKit 검증. [Pages #41778625867](https://github.com/koith/browser-app-lab/actions/runs/41778625867) SUCCESS, [배포본 QA #41778625724](https://github.com/koith/browser-app-lab/actions/runs/41778625724) `PAGES_PUBLIC_VIDEO_TRENDS_PASS` 데스크톱/모바일 각 1회, `PAGES_DEPLOYED_MAIN_BYTES_SHA256_PASS`. **정적 배포 UI VERIFIED**, 실제 SNS 영상 수집률/물리 iPhone/TeraBox 원본 아카이브는 별개.
- [x] **INT-06·09 실제 SNS별 수량 불일치 수정**: [PR #699](https://github.com/koith/browser-app-lab/pull/699), main `ab824a267a81ed7e15be207944d9127b35c20d34`. 기존에는 게시글 필터 후 1,027건 표시와 별개로 원시 Bluesky 2,422건을 출처 집계에 표시했음. 실제 표시되는 필터 통과 게시글만 SNS별 집계하고 Threads/Instagram 출처 합계도 0건 포함 표기. [실제 공개 API 브라우저 CI #41778594796](https://github.com/koith/browser-app-lab/actions/runs/41778594796) **PASS**: 총 1,004건 = B1002 + X2, 나머지 M/L/K/R/T/I=0 (해당 검증 시점에만 해당). 합성 테스트도 총 307 = B294 + M3 + L3 + K3 + R3 + X1. **LIVE UI COUNT VERIFIED**, 여러 SNS에서 0건이 나온 원인·지속 수집은 INT-09 미완료.
- [x] **INT-13 한국시간 날짜·월말 경계 보정**: [PR #700](https://github.com/koith/browser-app-lab/pull/700), main `8ec21bb3d2cd900b16055053e3adc739870357a4`. 10/31 16:30 UTC가 한국시간 11/01 01:30으로 올바르게 11월 아카이브 분류됨을 테스트; 게시 시각 KST 표시. [영상 회귀 CI #41778813100](https://github.com/koith/browser-app-lab/actions/runs/41778813100) PASS; [Pages #41778924394](https://github.com/koith/browser-app-lab/actions/runs/41778924394) SUCCESS. **CODE/CI/Pages VERIFIED**, 모든 실제 SNS 개별 게시 시각 검증은 미완료.
- [x] **INT-08·13 배포 검증 트리거 누락 보완**: [PR #701](https://github.com/koith/browser-app-lab/pull/701), main `5cc6fcb53a19f9b9614f1d597b6d2735e873e4be`. 영상 JS만 수정해도 기존 Pages Chrome/WebKit SHA 검사가 main push에 연동되도록 기존 workflow 경로 필터 추가. [PR QA #41779254268](https://github.com/koith/browser-app-lab/actions/runs/41779254268) 코드 검증 SUCCESS. 새 자동화·유료 인프라 없음. **CODE/CI VERIFIED**.
- [ ] **최신 main 합성 배포본 독립 재검증**: [Pages #41779393312](https://github.com/koith/browser-app-lab/actions/runs/41779393312), [배포 QA #41779393264](https://github.com/koith/browser-app-lab/actions/runs/41779393264)의 최종 상태 확인. 실제 SNS별 원본 영상 완전성/물리 iPhone/개인 TeraBox 복원은 미검증.
- [ ] **P0 남은 실제 저장·예약 장애 유지**: [최근 캡처 #41745222160](https://github.com/koith/browser-app-lab/actions/runs/41745222160) 발견 42·테라박스 원격 검증 3·저장 실패 21·AES 보관 21, 예약 간격 약 273.8분. 새로운 수집 작업 다회차 실패 0, 암호화 미복구 0, media SHA 원격 일치 전 INT-01~04를 완료 처리하지 않는다. Render 연결 서비스 2곳은 각각 화보/4LEAF용으로, 교집합 개인 HTTPS gateway 운영 배포도 입증되지 않음.


## 2026-11-04 INT-02 실제 예약 공백 대응 — 두 계층 재조회 상한

- [x] **INT-02 하위 개발 — 274분 실제 예약 공백을 재조회에 반영**: [PR #702](https://github.com/koith/browser-app-lab/pull/702), main squash `c968ad628a3e4f14463388b1a882ff0f29b594f6`. [예약 수집 #41745222160](https://github.com/koith/browser-app-lab/actions/runs/41745222160) 실제 로그는 `observed_gap_minutes=273.8`인데, 기존 스케줄 분석과 수집 실행 코드 양쪽에서 재조회 범위를 180분으로 제한해 이전 94분가량이 누락 가능했음. 양쪽 모두 360분 상한으로 조정하고, 274분 공백에 최근 16분 여유를 포함한 290분 재조회가 보장되는 합성 회귀를 추가. [PR 수집 CI #41779711323](https://github.com/koith/browser-app-lab/actions/runs/41779711323) **Python 99개 PASS**, main에 코드 반영 재조회. 사용자 정보·공개 글 원문 변경 없음. **CODE/CI VERIFIED**.
- [ ] **INT-02 실운영 게이트 유지**: [신규 main 실제 수집 #41779847157](https://github.com/koith/browser-app-lab/actions/runs/41779847157)에서 `effective_lookback_minutes`가 충분한지, 후속 예약 실행 실제 간격·원격 SHA 저장 성공·누락 완화 관측 후 검증. GitHub cron의 매 5분 정확성은 미입증이며, TeraBox의 `storage_failures=0`도 아직 달성하지 못함.


## 2026-11-04 신속 후속 개발 — 영상 순차 검토·TeraBox 복구 진단

- [x] **INT-13-E 하위 UI — 확인된 공개 영상의 순차 검토**: [PR #704](https://github.com/koith/browser-app-lab/pull/704) main `e955ec3e8f0d0234c79a3d750e587c731636b774`. 기존 기간·SNS·광고 필터를 통과한 공개 영상만 순서대로 확인, 이전/다음, 건수, KST, 반응 제공 여부, 검증된 원문 HTTPS 링크 표시. SNS 내 재생/저장만 안내하며 제3자 iframe/다운로드·영구 원본 보관은 수행하지 않음. 랭킹/영상·광고·개인 아카이브·게시글 브라우저 PR CI 전부 PASS. **CODE/CI VERIFIED.**
- [x] **INT-01 복구 차단 원인 세분류(비밀 보호)**: [PR #706](https://github.com/koith/browser-app-lab/pull/706) main `f334ff90e9ee775c3a78df533eb2c954a7efce83`. 암호화 원본 복구의 실패 집계를 실패 원문 대신 허용 목록의 인증·용량·속도 제한·원격 경로·SHA 충돌·타임아웃·미제공 등 집계 건수로 기록. 중첩 원인 체인도 검사하되 원본·계정·URL·비밀번호·경로는 절대 출력하지 않음. PR 복구·수집 회귀 CI PASS; [실제 과거 복구 #41763256103](https://github.com/koith/browser-app-lab/actions/runs/41763256103)는 원격 1건 검증/실패 1건, [#41761099176](https://github.com/koith/browser-app-lab/actions/runs/41761099176)는 원격 5건 검증/실패 5건/미처리 버퍼 223건으로 **실운영 복구 FAILED 유지**.
- [ ] **INT-01 최종 게이트 유지**: 위 진단 코드 main 기준 실제 복구 실행 결과에서 원인별 수치를 확인하고, 손상 원본·AES 보관본 잔여 0, TeraBox remote SHA 검증, 신규 수집 다회차 오류 0 달성 이전에는 INT-01을 체크하지 않음.
- [ ] **INT-13-E 전체 완료 아님**: SNS 원문 검토 UI는 완료했지만, 허용된 원본 다운로드·실 TeraBox 보관 및 실제 영상 바이트 확인은 INT-01/03/05 선행 조건에 의존함.


## 2026-11-04 원본 영상 완결성·강제 종료 진단 — #709 / #712

- [x] **INT-03 하위 코드 — Bluesky 영상이 미보관인데 ‘완료’로 표시되는 오류 해결**: [PR #709](https://github.com/koith/browser-app-lab/pull/709), main squash `5523674d3289334978a90e293d731c73237c1609`. 기존 수집기는 AppView의 이미지 링크만 추출하여 **영상만 포함된 공개 게시글을 `media_expected=0`, `archive_complete=True`로 오인할 위험**이 있었음. 실제 조회된 영상 playlist의 HTTPS 호스트·게시 작성자 DID·CID를 함께 검증해 원본 증빙 링크만 보존하고, HLS playlist 바이트는 원본 MP4로 저장·계산하지 않음. PDS 원본 blob SHA 확인 전 해당 영상은 `media_saved=0`, `archive_complete=False`로 표기. 타 계정 영상 대체 금지. 원본 첨부 슬롯을 기존 6→16으로 확장하며 17개 이상 입력은 완결로 위장하지 않고 누락으로 표시. [CI #41781626056](https://github.com/koith/browser-app-lab/actions/runs/41781626056) **Python 102 passed**, main 수정된 수집 파일 별도 재조회. **CODE/CI VERIFIED**, 과거 MP4 실파일 저장·복원 미완료.
- [x] **INT-01·02 하위 코드 — 18분 실행 제한 전에 암호화 원본/집계 출력**: [실제 캡처 #41779847157](https://github.com/koith/browser-app-lab/actions/runs/41779847157) 종료 코드 124, 18분 뒤 강제 종료되면서 `DEMAND_CAPTURE_AGGREGATE_ONLY` 없음. 대신 암호화 원본 9개만 Actions artifact에 살아있음을 마지막 로그에서 확인. [PR #712](https://github.com/koith/browser-app-lab/pull/712) main `c66e472d92b941d6b43619b0b2585a669612e93c`: 내부 720초 소프트 제한을 도입, 더 긴 개별 원격 처리가 진행되기 전에 새 수집 시작 중단, 이전에 AES로 봉인된 파일 보존, checkpoint 및 집계 기록, `soft_time_budget_exhausted=true`라면 정상 완료로 보고하지 않음. 합성 클라우드 장애·모든 외부 저장이 정상인 경우에도 불완전 구간 실패 처리 테스트. [CI #41782387036](https://github.com/koith/browser-app-lab/actions/runs/41782387036) **Python 104 passed**, main 반영 확인. **CODE/CI VERIFIED**.
- [ ] **실운영 게이트 유지**: [새 main 캡처 #41782497876](https://github.com/koith/browser-app-lab/actions/runs/41782497876)에서 부정확한 완료 표기가 사라졌는지와 최종 집계 출력 여부를 확인. TeraBox 모든 원본·미디어의 독립 SHA256 readback, 과거 AES 잔여 0, 다회차 신규 저장 실패 0 및 물리 iPhone 데이터 확인 전 INT-01~04/07/08 체크 금지.


## 2026-11-04 TeraBox 안전한 최상위 암호화 보관 대체 경로 — PR #713

- [x] **INT-01 하위 개발 — 원격 metadata 경로 오류 시 같은 개인 TeraBox의 최상위 경로로 AES-GCM 암호화 복구 묶음 저장·SHA 재읽기**: [PR #713](https://github.com/koith/browser-app-lab/pull/713) squash main `b9959bc8308ce445a5ba0e3c2a228faed0648997`. [실제 복구 #41781257598](https://github.com/koith/browser-app-lab/actions/runs/41781257598)의 `batch_error_categories.missing_remote_path=2`에 직접 대응. `metadata/recovery-pack-<SHA>.zip` 쓰기에 *원격 경로 없음*만 발생한 경우, 같은 비공개 루트의 `recovery-pack-<SHA>.zip`로 immutable 직접 저장 후 실제 바이트 SHA256 재검증. 원격 보관 목록과 추출 로직이 기존 metadata·신규 루트 위치 모두를 처리하도록 변경. 기존 보관 파일 삭제·덮어쓰기 없음. 인증·용량·rate limit·기존 원본 무결성 충돌은 우회 금지. 암호화 배치에 평문 원본·계정·키 출력 없음. [복구 테스트 #41783145934](https://github.com/koith/browser-app-lab/actions/runs/41783145934) **37 passed**, [수집·복구 테스트 #41783145935](https://github.com/koith/browser-app-lab/actions/runs/41783145935) **104 passed**, 실제 main 코드 재조회 확인. **CODE/CI VERIFIED.**
- [ ] **INT-01 운영 대체경로 확인**: [main 복구 #41783414649](https://github.com/koith/browser-app-lab/actions/runs/41783414649) / [후속 복구 #41783420436](https://github.com/koith/browser-app-lab/actions/runs/41783420436)에서 root AES pack SHA 저장 성공 및 정확한 원본 게시글/첨부 원격 SHA 전수 검증, 기존 지연 214개 버퍼 잔여 0건, 신규 수집 다회차 실패 0 확인 전까지 전체 INT-01 미완료. 복구 큐 동시성·운영 시간 초과 가능성은 별도 확인.


## 2026-11-04 — 테라박스 백업 버튼 활성화 및 배포본 확인 (#740)

- [x] **INT-11·05 하위 UI 오류 — 공개 Pages에서 백업 버튼 영구 비활성화 해결**: [PR #740](https://github.com/koith/browser-app-lab/pull/740), main squash `041a8ed397f60f0376710b7c6bc28930d192828d`. 공개 `koith.github.io`에는 비공개 `/api/target-archive/status` 엔드포인트가 없어 기존 JS가 오류 시 `submit.disabled=true`를 영구 적용하던 문제. Bluesky/Mastodon 공개 계정 주소의 유효성을 확인하면 버튼이 활성화됨. 비공개 서버와 Actions write 권한이 있는 경우 원래대로 same-origin POST를 통한 실제 workflow **접수(QUEUED)**. 서버가 없는 Pages에서는 'GitHub에서 백업 실행'으로 명확히 표시하고 공개 계정 주소 복사/기존 소유자 인증 GitHub Actions 화면 열기; 최종 `Run workflow` 누르기 전에는 요청 접수·테라박스 저장 완료를 주장하지 않음. GitHub 키/테라박스 쿠키를 public JS에 추가하지 않음.
- [x] **INT-11·08 버튼 PC/모바일 합성 회귀·실배포 코드 무결성**: [PR CI #41850327592](https://github.com/koith/browser-app-lab/actions/runs/41850327592) Python **86 PASS**, `TARGET_BACKUP_BUTTON_BROWSER_PASS` Chromium/WebKit 각 public Pages/private gateway 모드 PASS; 광고/게시글/랭킹/인덱스 기존 회귀 PASS. [Pages 배포 #41852489849](https://github.com/koith/browser-app-lab/actions/runs/41852489849) SUCCESS, [실배포 QA #41852489520](https://github.com/koith/browser-app-lab/actions/runs/41852489520)에서 `PAGES_DEPLOYED_MAIN_BYTES_SHA256_PASS` (HTML/랭킹/영상/백업 JS 4개), `PAGES_BACKUP_BUTTON_ENABLED_PASS` 데스크톱 Chromium·모바일 WebKit 시뮬레이션 각각 확인. **CODE/CI/DEPLOYED_STATIC_UI VERIFIED**.
- [ ] **INT-05·11 실제 원클릭 보관 완료 조건 유지**: 현재 연결된 Render에는 화보 뷰어·4LEAF 서비스만 있으며 교집합 인증 HTTPS gateway는 미배포. 따라서 공개 Pages에서는 직접 백업을 큐에 넣을 수 없고 사용자가 GitHub Actions `Run workflow`에서 최종 승인해야 함. 추후 교집합 gateway에 인증·Actions write 권한을 안전하게 구성하고 실계정 백업 요청 → GitHub 워크플로 → TeraBox 원본/첨부 원격 SHA256 재읽기 성공 및 모바일 실기 확인 전에는 INT-05·11의 운영 완료로 체크하지 않는다. 유료 서비스·새 정기 자동화·공개 접근 토큰 미도입.


## 2026-11-05 백업 버튼 모바일 재현 수정·원본 미디어 정확성

- [x] **INT-11·08 버튼 재수정 — 비어 있는 입력에서도 누를 수 있고 모바일 새 창 차단 회피**: [PR #741](https://github.com/koith/browser-app-lab/pull/741), main squash `dde37996ad8e33805e4b65aeb3e0c238445ea0a5`. 종전 #740은 입력값이 비어 있으면 `disabled`로 사용자가 도움말을 확인할 수 없었고 공개 Pages 대체 경로에서 `window.open` 팝업이 차단되면 무반응처럼 보일 수 있었음. 계정 입력 여부와 무관하게 버튼 클릭 가능(요청할 유효 공개 계정은 필수로 검증)→실패 시 입력란 포커스와 형식 예시 안내, 계정 유효 시 같은 탭에서 소유자 GitHub Actions 실행 화면으로 이동하고 선택 계정 클립보드 복사 시도. JS 캐시 버전을 `20261105-touch-navigation`으로 변경. 비공개 gateway에서는 원래 same-origin POST 요청·QUEUED 상태 유지. JS 문법 확인·실제 최신 파일에 대한 외부 종속성 없는 DOM 상태·클릭 기능 테스트에서 공개/비공개 모드 모두 PASS, main 코드 재조회 완료. [GitHub Actions PR QA #41862950111](https://github.com/koith/browser-app-lab/actions/runs/41862950111), [배포본 QA #41862950453](https://github.com/koith/browser-app-lab/actions/runs/41862950453)가 작성 당시 GH 전체 Actions 큐에 있어 **CI/새 Pages 배포 UNVERIFIED**. 이후 확인 필요. 공개 Pages는 비밀키를 저장하지 않으므로 실제 자동 접수는 여전히 인증 gateway 선행 조건. 단순 GitHub 페이지 이동을 ‘테라박스 백업 완료’로 오표시하지 않음.
- [x] **INT-03·07 하위 수정 — Lemmy 썸네일을 원본으로 잘못 저장하던 문제**: 기존 검증된 미해결 PR [#714](https://github.com/koith/browser-app-lab/pull/714) main squash `06c824e006bfdaf517dda9b7a62925d75a34be74`. 원 게시글의 `thumbnail_url`은 생성된 미리보기일 수 있으므로 원본으로 취급하지 않고, post-owned 원본 `post.url`이 이미지/동영상 직접 링크인 경우만 수집. Lemmy 원본 pictrs 확장자 없는 링크 허용, 타 글·광고·블로그 썸네일 대체 금지. PR 수집 CI offline-tests PASS(이전 실행), 실제 새 main 파일/테스트 존재 재조회 완료. **CODE/CI VERIFIED**, 실 원본 TeraBox SHA readback 별도.
- [ ] **INT-11 백업 버튼 종단 간 운영 검증**: GitHub Actions 대기 해소 후 최신 Pages SHA256 readback 및 PC Chromium·모바일 WebKit 클릭→동일 탭 이동, iPhone 실기. 실제 owner 인증 gateway 배포/Actions write 설정/보관 작업 접수/테라박스 원본 SHA 성공 전 최종 완료 주장 금지.


## 2026-11-05 추적 중인 계정 → 백업 대상 바로 선택

- [x] **INT-11 편의성 — 추적 카드에서 공개 계정을 백업 대상으로 채우기**: [PR #743](https://github.com/koith/browser-app-lab/pull/743), main squash `3be5da8fdea3076527835e31cabd01fd7dce260f`. 검증된 추적 공개 계정 중 Bluesky/Mastodon 카드에 `백업 대상으로 선택` 추가. 선택 시 해당 플랫폼과 정확한 공개 프로필 주소를 백업 폼에 자동 입력, 표준 input/change 이벤트로 기존 검증 규칙 재활용, 해당 폼으로 스크롤. 미지원 X/Threads/Instagram 등의 백업 요청 버튼은 생성하지 않으며 선택만으로 GitHub Actions 또는 TeraBox 업로드는 시작되지 않음. 기존 계정 확인·추적 흐름 보존. 정적 JS 문법 및 실제 PR 코드의 선택 함수에 대한 공개 계정 두 종류/미지원 플랫폼/이벤트 전파 기능검증 PASS; 새로운 GitHub Actions 브라우저 QA는 현재 대기 중이므로 **CODE/MOCK VERIFIED, CI·새 Pages 배포 UNVERIFIED**.
- [ ] **최신 Pages·실기 운영 확인**: [버튼 #741](https://github.com/koith/browser-app-lab/pull/741), [계정 선택 #743](https://github.com/koith/browser-app-lab/pull/743) 포함 main 배포 [#41864723515](https://github.com/koith/browser-app-lab/actions/runs/41864723515) 완료/원본 HTML·JS SHA 재읽기, Chromium·WebKit 클릭 흐름, 실물 iPhone 내부 브라우저에서 복사·동일 탭 이동을 검증하기 전 최종 완료하지 않음. 공개 Pages에서 직접 원클릭 백업은 보안 비밀값 부재로 별도의 인증 gateway 배포가 필요하고, 현재는 소유자 인증 GitHub Actions에서 최종 `Run workflow` 확인 단계가 존재함.


### 2026-11-13 INT-10 상위 완료 실증
- [x] **INT-10 FIRST VERIFIED PARENT CLOSURE**: main에 병합된 [PR #1069](https://github.com/koith/browser-app-lab/pull/1069)과 실운영 배포본 [#43413717379](https://github.com/koith/browser-app-lab/actions/runs/43413717379)의 `real-ranking-browser` **success**. 실데이터 기반 Chromium PC 318건/1 SNS, 기존 167·신규/미확인 77, 10열·상세·더보기 전부 PASS; WebKit 모바일 시뮬레이션 222건/2 SNS, 기존 107·신규/미확인 57, 5열·상세·더보기 전부 PASS. 새/기존 공개 이력 증빙과 카드 카운트 확인. 다른 플랫폼의 미수집·출처 검증은 INT-09, 물리적 iPhone 실기는 INT-07/08로 유지. **실사용량 전체 전수나 iPhone 실기까지 완료했다고 주장하지 않음**.

