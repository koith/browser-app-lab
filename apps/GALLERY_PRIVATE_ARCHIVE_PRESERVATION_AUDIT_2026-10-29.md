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
- Google Drive에 업로드한 `mimmi-original-new-private-0.actions.zip`을 다시 **실제로 다운로드하여 SHA-256 재계산**했고 Actions 원본과 동일한 `7dacd5839e70735f03d81f1e1901b9518f4839668626233fe286f861fb6c6200`으로 확인했다. 나머지 Drive 파일은 업로드 메타데이터의 크기/비공개 권한을 재조회했으며 전체 Drive 원본 SHA readback까지 검사했다고 주장하지 않는다.

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

## 남은 작업

1. 새 기능 PR의 모든 CI 체크 확인 후 병합·Pages 배포 및 실제 출력 확인.
2. 보존한 Drive ZIP들을 개인 갤러리에 자동 동기화하는 사용자 인증 영구 게이트웨이 구축. 현재는 기기별 ZIP 가져오기 방식.
3. 전체 화보 기대 컷과 확보 컷 사이 누락(심유이 기존 18개, 밈미 기존 59개 및 이후 새 미확보분)을 번호별로 재검증·정상 접근 가능한 출처로 보강.
4. iPhone Safari 실기기에서 대형 Actions ZIP 여러 개를 순차적으로 가져오기, IndexedDB 저장 한도·앱 복귀·오프라인 사진 열기 검증.
