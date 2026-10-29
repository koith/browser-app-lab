# 심유이·밈미 원본 ZIP 비공개 보존 감사 — 2026-10-29

이 문서는 **이미지 파일의 개인용 비공개 보관**과 **실제 공개 Pages 출력**을 엄격히 구분한다. GitHub Actions 임시 ZIP에 있던 확인된 바이트만 개인 Google Drive 폴더에 복사했으며, 이 작업만으로 공개 갤러리 이미지 수가 증가하거나 클라우드 인증 갤러리 동기화가 구현되는 것은 아니다.

## 보존 결과

- 13개 Actions wrapper ZIP을 모델별 **소유자 비공개** Drive 폴더로 업로드했다. 각 파일의 Drive 업로드 이후 메타데이터 크기는 GitHub Actions 기록과 일치하고, 파일 공유 상태는 `shared=false`이다.
- 검증에 사용한 15개 원본/분할 wrapper ZIP은 외부 SHA-256이 Actions 기록과 일치한다.
- 모든 wrapper 내의 총 62개 `*-private-import.zip`을 해제해 이미지 4,108개 항목(중복 포함)의 manifest 사진 SHA-256·바이트 크기·실제 이미지 해독·가로세로 크기를 전부 검사했다. **오류 0건.**
- 모델별 중복 SHA를 제외한 이번 15개 ZIP 내부 수는 Yui **2,749개**, Mimmi **252개**. 이 숫자는 공개 라이브 이미지 장수가 아니다.
- 초과 크기 두 wrapper 대신 아래 실제 **동등 분할 아카이브**를 백업했다.
  - `yui-original-verified-pixibb-large` 684개 항목 ↔ `maid291` + `last-summer192` + `tracksuit201` 684개. 모델/앨범 ID/사진 번호/SHA/바이트/차원 전수 일치.
  - `yui-original-verified-public-editorial` 418개 ↔ `sns-1-180` + `sns-181-361` + `non-sns-editorial` 418개. 번호·SHA 등 전수 일치.
- **2026-10-29 후속 실제 Drive 재다운로드 감사 완료:** 보관 ZIP 13개 모두 Drive에서 다시 내려받아 SHA-256과 바이트 크기를 Actions 원본 감사값과 전수 비교했고 **13/13 일치·오류 0건**이다. 비공개 접근 상태는 그대로 유지한다. 개별 ZIP 안의 이미지 무결성 전수 감사 결과는 기존 4,108개 항목 오류 0건과 구분해 기록한다.

## Drive 보존본 (13개)

| 모델 | Actions 보관본 파일 이름 | 크기(B) |
|---|---|---:|
| Yui | yui-green91-real-private-files.actions.zip | 7,546,918 |
| Yui | yui-private-editorial-sns-1-180.actions.zip | 55,087,490 |
| Yui | yui-private-editorial-sns-181-361.actions.zip | 57,288,305 |
| Yui | yui-private-editorial-non-sns-editorial.actions.zip | 25,904,759 |
| Yui | yui-original-verified-source-variety-two.actions.zip | 70,704,032 |
| Yui | yui-original-verified-pixibb-other.actions.zip | 97,560,916 |
| Yui | yui-original-verified-source-variety-one.actions.zip | 100,921,339 |
| Yui | yui-verified-album-last-summer192.actions.zip | 57,613,700 |
| Yui | yui-verified-album-maid291.actions.zip | 64,417,510 |
| Yui | yui-verified-album-tracksuit201.actions.zip | 75,355,124 |
| Mimmi | mimmi-original-new-private-0.actions.zip | 6,971,909 |
| Mimmi | mimmi-original-new-private-1.actions.zip | 5,332,737 |
| Mimmi | mimmi-original-new-private-2.actions.zip | 50,357,440 |

원본 Drive 폴더는 소유자만 접근 가능하도록 유지한다. 이 공개 GitHub 문서에는 개인 Drive URL/공유 토큰/자격 증명을 기록하지 않는다.

## 웹 갤러리 연동 및 QA

- PR #279: `apps/photo-vault.js` + 두 모델 배포용 복제본에 Actions wrapper ZIP의 중첩 `-private-import.zip`을 해제·검증·IndexedDB에 저장하는 코드. 중복 SHA라도 앨범 사진 **번호**는 유지한다.
- ZIP 내부 `manifest.json`의 모델/물리 수량/사진 SHA 확인은 그대로 수행한다. 다른 모델 ZIP은 거절한다.
- `apps/test_photo_vault.cjs`: 고정 수치 대신 `stored-albums.json`을 기반으로 실제 공개 파일 수 계산. Chromium/WebKit에서 중첩 압축된 wrapper ZIP, 무결성 실패, 새로고침 후 보존 및 외부 이미지 요청 0건 검증하도록 추가했다.
- iPhone 실기기 QA와 새 ZIP을 13개 모두 iPhone Safari에 통합 가져와 출력하는 실제 성능/쿼터 테스트는 **아직 수행되지 않았다**.

## 후속 개발·검증 결과 (동일 날짜)

- **PR #283** 병합 SHA `a5bcd8840982128e7f3b123b1018de069d78eaac`: 양 모델에 `내 Drive 원본 연결` 화면 도입. 소유자 Google 계정의 읽기 전용 OAuth 권한으로 비공개 ZIP 실제 다운로드 → 중첩 압축 해제·SHA 검증 → 기기 IndexedDB 저장; 검증 완료 ZIP별 재다운로드 생략. 실제 본인 Google 웹 OAuth 클라이언트 ID·Drive API 설정과 계정 동의는 아직 필요하며, **13개가 실제 사용자 폰에 동기화됐다고 주장하지 않는다**.
- GitHub Pages 실제 반영 확인: 심유이 `v0.1.0-beta.25`, 밈미 `v0.1.0-mimmi.14`. Chromium/WebKit 양쪽에서 모의 Google 인증·실제 바이트 ZIP 전송·장기 저장·중복 다운로드 방지 및 외부 화보 서버 이미지 요청 0건 통과. 실제 iPhone 단말/실제 Google 계정 동기화는 아직 테스트하지 못함.
- **PR #284** 병합 SHA `650e678cd70bf72fac0e6d9df497b28a109fafa8`: 밈미 수집기의 전역 SHA 중복 제외를 `(화보 ID, 사진 번호, SHA)` 기준으로 수정. 서로 다른 위치에 쓰이는 동일 바이트도 보존하고 이미 저장된 동일 위치만 건너뛰도록 개선. 신규 Python 회귀 8건과 기존 수집 QA 검사 통과. 새 사진을 확보했다는 의미는 아님.
- **화보별 불충분 검증:** Yui 비공개 ZIP 27개 화보 / 저장된 고유 사진 번호 위치 2,754 / 기대 2,772 / 확인된 빈 칸 18. 밈미 비공개 ZIP 23개 화보 / 저장 위치 252; 해당 23개 화보의 공개 저장본+비공개 ZIP을 번호로 합친 실제 저장 위치 603 / 기대 2,384 / 빈 칸 **1,781**. 이 수치는 **해당 23개에만 한정**되며 모든 화보의 최종 총량이 아니고, 기존 공개 미리보기와 비공개 ZIP을 별개로 합산해서 부풀리지 않는다.
- 상세 누락 추적: [Issue #281](https://github.com/koith/browser-app-lab/issues/281). 로컬 다운로드 감사 JSON: `gallery_drive_readback_sha256_20261029.json`, 화보별 비공개 저장 완성도: `gallery_private_album_completeness_20261029.json` (대화 생성 아티팩트; 공개 소스에 개인 Drive ID는 넣지 않음).

## 남은 작업

1. 구현된 개인 Drive OAuth 화면을 본인 계정에 연결하여 **실제 보관 ZIP 전량을 PC·iPhone에서 내려받고** 기기 저장·열람 확인. 현재는 UI·모의 검증만 완료.
2. 보존한 Drive ZIP의 사용자 인증 기반 기기 동기화 기능을 실제 계정으로 개통하고, 정기 신규 업로드/클라우드 양방향 자동화와 장애 복구를 후속 검토. 현재는 사용자 클릭 후 기기별 읽기 전용 동기화.
3. 전체 화보 기대 컷과 확보 컷 사이 누락(심유이 기존 18개, 밈미 기존 59개 및 이후 새 미확보분)을 번호별로 재검증·정상 접근 가능한 출처로 보강.
4. iPhone Safari 실기기에서 대형 Actions ZIP 여러 개를 순차적으로 가져오기, IndexedDB 저장 한도·앱 복귀·오프라인 사진 열기 검증.
