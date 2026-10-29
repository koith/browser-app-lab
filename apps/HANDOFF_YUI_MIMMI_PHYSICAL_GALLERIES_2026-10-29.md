# 심유이·밈미 다운로드 기반 개인 화보 갤러리 — 통합 인수인계서

- **작성 기준:** 2026-10-29 15:04 KST 이후 GitHub·Actions·Google Drive 재조회 결과
- **저장소:** `koith/browser-app-lab`
- **점검 당시 `main` HEAD:** `510ddcc60a7bc3afbc1933ba250ce73417ee9180` (이 문서를 커밋하면 HEAD는 바뀜)
- **대상:** `apps/yui-gallery/`, `apps/mimmi-gallery/`, `apps/photo-vault.js`
- **운영 URL:** [심유이](https://koith.github.io/browser-app-lab/apps/yui-gallery/) / [밈미](https://koith.github.io/browser-app-lab/apps/mimmi-gallery/)
- **완료 판정:** **진행 중.** 외부 이미지 중계 제거와 개인 ZIP 가져오기 기능은 반영됐으나, 수집한 모든 파일의 장기 저장 및 갤러리 실제 출력은 끝나지 않았음.

## 1. 반드시 지킬 사용자 요구

1. 두 갤러리는 **원본 화보사이트의 이미지 주소를 대신 보여주는 중계 뷰어가 아니라, 사진 파일을 실제 다운로드해 보관하고 그 저장 파일을 보여주는 개인 아카이브**여야 한다.
2. 갤러리·화보 카드·사진 수량에는 **실제로 저장되어 출력 가능한 파일만** 포함한다. URL 발견, SHA만 기록, 원격 브라우저 디코딩, 수집 예정, 임시 CI 결과 등을 실제 갤러리 성과처럼 표시하면 안 된다.
3. 화보마다 임의로 3장·10장 제한을 걸지 말 것. 여러 페이지·스크롤·대체 공개 출처까지 확인하여 **번호 순서와 실제 확보 장수를 유지**한다. 미확보/실패는 별도로 추적한다.
4. 두 갤러리는 같은 모바일 UI 원칙을 적용하고 서로 이동할 수 있어야 한다. 심유이↔밈미 전환은 별도 탭 열기를 사용한다.
5. 무료 도구·정상 공개된 출처를 우선한다. HTTP 451 등 **접근 제한을 우회하지 않는다.** 특정 외부 서버가 거부해도 이미 적법하게 보유한 사진을 개인 저장소에서 열람하는 작업까지 중단하지 않는다.
6. 비공개 원본이나 이용 권한이 확인되지 않은 사진을 공개 GitHub Pages·공개 버킷에 게시하지 않는다. 디바이스 보관본과 공개 정적 파일, GitHub Actions 임시 업로드는 구분한다.
7. 완료 보고에는 실제 파일 수, 화보별 확보/기대 수, SHA/바이트/이미지 해독, Chromium·WebKit·실기기 QA 여부, PR, HEAD SHA, 실제 배포 상태를 명시한다. **WebKit 에뮬레이션은 실물 iPhone QA가 아니다.**

## 2. 현재 실제 보관/출력 현황 (각 수량은 서로 단순 합산 금지)

| 구분 | 심유이(Yui) | 밈미(Mimmi) | 증거·해석 |
|---|---:|---:|---|
| 공개 Pages 실파일 manifest | **23장 / 6개 화보** | **2,242장 / 64개 화보** | `apps/*-gallery/stored-albums.json` 최신 `main` 실물 파일 목록. 웹 표시 계층은 저장본만 사용하도록 수정됨 |
| 복구된 비공개 Google Drive 개별 JPEG | **218장 / 68,957,163바이트** | 동일 항목 없음 | 폴더 `Yui_public_individual_2026-10-28`; 파일의 SHA-256 및 이미지 해독 검증. **217장 SNS, 1장 일본 ACOSTA 행사 기록** |
| 심유이 별도 GitHub Actions 임시 ZIP | **SNS 361/361, Green 91/91** | 해당 없음 | 각각 실제 다운로드·해시 검증 성공. SNS 361장은 Drive 218장 가운데 SNS 217장과 중복되므로 합산 금지 |
| 광범위 공개 출처 수집 | **2,663/2,681 이미지 항목 확보, 18개 미확보** | 해당 없음 | Yui 26개 소스 목록, 5개 배치·GitHub Actions 임시 ZIP. 여러 화보 사이 SHA 중복 가능. **2,663은 고유 사진 수나 온라인 출력 장수가 아님** |
| 밈미 추가 미저장 출처 수집 | 해당 없음 | **252개 항목 저장, 59개 실패** | 3개 임시 ZIP 배치: 13 + 15 + 224. 당시 조사 대상 미저장 SHA 311개. 현재 Pages 2,242장과 중복 가능성 검사 전이므로 합산 금지 |
| 사용자의 기기 내 ZIP 가져오기 | **지원** | **지원** | 브라우저 IndexedDB를 사용하므로 **그 기기에 직접 가져온 뒤에만** 추가 사진 출력. 타 기기로 자동 동기화되지 않음 |
| 개인 인증 원격 원본 서버 | **실서비스 연결 미완료** | **전체 수집본 영구 연결 미완료** | 임시 Actions ZIP을 영구 저장소로 착각하지 말 것 |

**중요:** `apps/yui-gallery/version.json`의 `source_hosted_gallery_image_entries`, `physically_acquired_web_images` 등은 과거 수집/연구 기록일 수 있다. 실제 라이브 공개 갤러리는 위 **23장**부터 계산한다. 밈미는 예전 2,162장·2,221장 기준이 아니라 **점검 시점의 2,242장**으로 갱신되어 있다.

## 3. 현재 구현된 구조와 파일

- `apps/yui-gallery/index.html` — Yui **v0.1.0-beta.21**, 공개 실파일 + 인증된 개인 저장본 + 기기 내 ZIP 파일을 갤러리 목록에 표시. 외부 출처 URL을 열람 사진으로 자동 합치던 기능 제거.
- `apps/mimmi-gallery/index.html` — Mimmi **v0.1.0-mimmi.10**, 같은 저장본 우선 정책 및 ZIP 보관본 가져오기. 양쪽 화면의 모델 전환 링크 확인.
- `apps/photo-vault.js` — 공통 SHA-256 ZIP→IndexedDB 도입부. `apps/yui-gallery/photo-vault.js` 및 `apps/mimmi-gallery/photo-vault.js`는 독립 정적 호스팅 테스트를 위해 같은 파일 복제본. **세 파일의 내용이 정확히 동일해야 함**.
- ZIP 수용 형식: 하위 경로에 `manifest.json`, `model: "yui"|"mimmi"`, `albums:[{id,title,images:[{number,url,sha256,bytes,width,height}]}]`; `number >= 1`, `url=photos/<sha256>.jpg` 등, 원본 바이트 해시 및 크기 검사. iPhone Safari 대응을 위해 **ZIP_STORED(무압축)** 권장.
- `apps/*-gallery/stored-albums.json`, `stored-albums/` — 공개 정적 저장 사진의 증거 원장. URL만 있는 `source-viewer-albums.json`, `additional-source-albums.json`은 수집기용 연구 목록이며 라이브 사진이 아니다.
- `apps/yui-gallery/owner-media.js`, `cloud/gateway/` — 인증 개인 보관소 연동 경로가 있으나 실제 영구 저장 원본이 전부 연결된 상태가 아니다.
- `apps/test_photo_vault_fixture.py`, `apps/test_photo_vault.cjs`, `.github/workflows/shared-private-vault.yml` — 양 모델의 실파일 ZIP 가져오기·SHA 위변조·기기별 보관·번호 유지·모바일 WebKit QA.

### 수집기 및 자동화
- Yui: `collect_verified_source_privately.py`, `collect_private_batch.py`; Actions `yui-public-sns-archive.yml`, `yui-private-bulk-archive.yml`, 관련 분할 ZIP workflow.
- Mimmi: `archive_private_missing.py`, `publish_stored_public.py`; Actions `mimmi-stored-public-gallery.yml`, `mimmi-private-missing-archive.yml`.
- Mimmi의 저장본 자동 게시 Actions는 정해진 시간에 돌아갈 수 있으므로 중복 브랜치 수정/강제 push/현재 실행 취소를 피하고 최신 `main`을 매번 다시 읽을 것.

## 4. 수집 완료한 **실제 바이트**의 현재 위치 및 만료 위험

### 심유이
1. **Green 91장, SNS 361장**: [Actions #40797099087](https://github.com/koith/browser-app-lab/actions/runs/40797099087)에서 각각 `PRIVATE_ARCHIVE_CREATED ... verified 91 of 91`, `verified 361 of 361` 확인. 아티팩트: `yui-green91-real-private-files`(7,546,918B), `yui-sns361-real-private-files`(112,373,595B). **2026-11-28 만료 예정**.
2. **Yui 기타 26개 공개 출처 목록**: [Actions #40798481649](https://github.com/koith/browser-app-lab/actions/runs/40798481649). 항목별 658/658, 418/418, 458/458, 445/463, 684/684, 합계 **2,663/2,681**, 18개 누락. 아티팩트 5종: `yui-original-verified-source-variety-one`, `source-variety-two`, `pixibb-other`, `pixibb-large`, `public-editorial`. **2026-11-28 만료 예정**. 성공한 저장 항목은 전체 화보/발행사 원본이란 뜻이 아니다.
3. **100MiB 초과 ZIP 분할본**: [Actions #40799605977](https://github.com/koith/browser-app-lab/actions/runs/40799605977) — `maid291`, `last-summer192`, `tracksuit201` 개별 ZIP. [Actions #40824628019](https://github.com/koith/browser-app-lab/actions/runs/40824628019) — SNS 1–180, SNS 181–361, 기타 editorial 분할본. 이 **분할 아티팩트는 2026-11-12 만료 예정**. 파일별 SHA·개수 재검증 후 개인 Drive로 적재해야 한다.
4. **Drive 실파일 218장**: 비공개 Google Drive 폴더 [Yui_public_individual_2026-10-28](https://drive.google.com/drive/folders/18Y0PToB2_Ns8c4WSafg6LVyZMK_OEVFV) 안에 존재하고, 이전 작업 중 전부 다운로드·SHA 검증됨. `public-yui-sns` 217장 + `acosta-japan-public-report` 1장으로 분류.
5. **Drive 아카이브 목표 폴더**: `Yui_verified_private_archives_2026-10-29` ID `1xElTOp2taNApyfU15zFwDQ0IXoMlmRM9`. 이번 조회에서 **내부 파일 0개**. 생성된 임시 ZIP이 실제 Drive에 영구 업로드된 것이라고 주장 금지.

### 밈미
- [Actions #40798481730](https://github.com/koith/browser-app-lab/actions/runs/40798481730): `mimmi-original-new-private-0` **13개**, `...-1` **15개**, `...-2` **224개** 검증 저장(총 252개), **59개 미확보**. Actions 아티팩트는 **2026-11-28 만료 예정**. 결과가 Pages `stored-albums.json`에 반영돼 실제 열리는 것인지, 이후 자동 게시된 80장과 중복되는지 먼저 대조해야 한다.

### ChatGPT 대화에서 생성한 218장 ZIP 주의
- 이전 `yui_218_import_ready.zip`에는 `acosta-japan-public-report`의 유일한 사진 번호가 **0**이어서 브라우저 `PhotoVault.validate`(사진 번호 >= 1)를 통과하지 못하는 오류가 있었다.
- **수정본 `yui_218_import_ready_FIXED.zip`**: 번호 1로 수정, 218개 실 JPEG 바이트의 SHA/크기 및 `ZIP_STORED` 전수검증 통과. **이 대화의 첨부 파일**에 있으며 아직 영구 Drive 업로드/온라인 갤러리 자동 적용은 미확인.
- 기존 `yui_verified_218_offline_gallery.zip`은 오프라인 HTML 보기는 가능하더라도 **ZIP 가져오기용으론 위 수정본**을 사용해야 한다.
- SNS 361장에서 이 217장에 해당하는 SHA는 중복 계산하지 않는다.

## 5. PR·Actions·QA 현황

| 변경 | 상태 | 증거 |
|---|---|---|
| [PR #272](https://github.com/koith/browser-app-lab/pull/272) | 병합 | Yui/Mimmi 외부 URL 중계 제거, 물리 파일만 노출. SHA `73a2c4ec17030c7cd9bf0b8d31e58ecc7c5776b1` |
| [PR #274](https://github.com/koith/browser-app-lab/pull/274) | 병합 | 두 모델 ZIP 개인 보관소, SHA 검사, IndexedDB 지속. [브라우저 QA #40795905768](https://github.com/koith/browser-app-lab/actions/runs/40795905768) Chromium·WebKit 성공 |
| [PR #275](https://github.com/koith/browser-app-lab/pull/275) / [#276](https://github.com/koith/browser-app-lab/pull/276) | 병합 | Green 91/SNS 361 다운로드 검증 완료·임시 ZIP |
| [PR #277](https://github.com/koith/browser-app-lab/pull/277) | 병합 | 번호별 동일 SHA 보존, 증분 ZIP 병합, 두 모델 미저장 수집기 |
| [PR #278](https://github.com/koith/browser-app-lab/pull/278) | 병합 | 100MiB 초과 Yui editorial 아카이브 분할 |

**현재 확실한 QA 구분**
- GitHub Pages 최근 배포: [Actions #40824628003](https://github.com/koith/browser-app-lab/actions/runs/40824628003) **성공**. 단, 사용자의 물리 iPhone에서 218장 개인 ZIP이 갤러리 안에서 열리는지 확인한 기록은 **없음**.
- **공유 ZIP QA 회귀 실패**: [Actions #40798481706](https://github.com/koith/browser-app-lab/actions/runs/40798481706)에서는 밈미 공개 저장 사진 수가 이미 **2,221장**인데 테스트 `apps/test_photo_vault.cjs`가 **2,162장**을 고정 기대하여 `Baseline not saved physical count mimmi`로 실패. 현재는 2,242장이므로 **manifest에서 기대 개수를 동적으로 읽도록 변경**해야 한다. 기능의 사진 수 증가를 실패로 착각하지 말되 이 실패를 무시해도 안 된다.
- `feat/shared-private-zip-vault-20261029` 브랜치 HEAD `5dc31a782434d49f071e76c8f951eb4d5db886c9`에는 후속 QA 개선이 있으나 **현재 main과 분기된 오래된 브랜치**다. [해당 브랜치 ZIP QA #40796225741](https://github.com/koith/browser-app-lab/actions/runs/40796225741)는 성공했지만, 이 브랜치를 통째로 병합하여 새 `main` 수집기/manifest를 덮어쓰지 말 것. 필요한 테스트 수정만 최신 main에 선별 반영.
- 물리 iPhone Safari에서 신규 218장 ZIP 가져오기·화보 카드·상세 뷰·원본 보기·새로고침·오프라인 동작은 아직 직접 실기기 검증되지 않았다.

## 6. 다음 담당자가 바로 실행할 우선순위

**P0 — 임시 원본 보존:** GitHub Actions의 만료 전 Yui/Mimmi 모든 검증 ZIP을 내려받아 비공개 영구 Drive 등으로 업로드. 아티팩트 이름과 byte count 기록, 각각 `manifest.json`의 SHA-256/크기/실제 이미지 해독 검사. 새 저장소가 끝까지 열리는지 다시 읽기. ZIP 분할본끼리 중복 SHA는 제거하되 **번호가 다른 동일 SHA 사진의 앨범 순서는 보존**.

**P1 — 실제 갤러리 연결:** 온라인 Yui 23장/밈미 2,242장과 비공개 실파일을 구분해 연결. 사용자가 ZIP 버튼으로 넣은 파일만 해당 기기의 IndexedDB에서 보여주며, 기기 동기화와 개인 원본 장기 저장은 별개로 구현. 새 원본을 공개 Pages에 무단으로 재게시하지 않는다.

**P2 — 남은 실제 미확보 사진:** Yui 2,681개 인덱스의 실패 18개를 파일별로 감사하고 정상 공개 출처·합법적 보유본에서 실제 파일을 확보·검증. Mimmi는 먼저 이미 다운로드된 252개 임시 파일을 영구화한 뒤 당시 미확보 59개 및 최신 남은 SHA를 재계산. 전체 화보 기대 장수와 실제 저장본 차이를 화보별로 기록.

**P3 — 테스트 복구:** `apps/test_photo_vault.cjs`에서 하드코딩된 Mimmi 2,162장 및 Yui 23장 기대를 `stored-albums.json` 데이터로 동적 계산. GitHub CI에서 Chromium+WebKit 실제 ZIP 실파일 가져오기, SHA 위변조 거부, 증분 합치기, 1-based 사진 번호, 동일 SHA 다른 번호 유지, 기기간 모델 분리, 새로고침 후 보존을 재검증. 소스 사이트로 향하는 **이미지 요청 수 0**이어야 한다.

**P4 — 사용자 실기기 QA 및 보고:** iPhone Safari 2열 화보, 앨범/전체화면, 모델 전환, 메모리·저장 공간, PIN/확대·스와이프, 탭 복귀, 로그아웃/사이트 데이터 삭제 영향 검증. 갤러리 표시 장수는 저장+로드 확인된 것만 기재. 실제 Pages HEAD·PR·SHA·테스트 결과를 보고.

## 7. 다음 작업 시 금지할 잘못된 완료 주장

- `source-viewer-albums.json`에 2,909개 URL이 있으므로 갤러리가 2,909장 저장됐다는 주장.
- GitHub Actions `success` 또는 브라우저에서 이미지를 디코딩한 것만으로 **영구 개인 저장소 연결·iPhone 실기기 출력·모델 화보 전체 완성**이라고 주장.
- Drive 빈 폴더나 임시 30일 아티팩트를 영구 저장소로 계산.
- 중복 SHA 217장 + SNS 361장을 신규 578장으로 합산.
- 앨범마다 이미지를 3장이나 10장만 임의 저장하고 전체 화보처럼 등록.
- 문제가 생겼다고 다른 코드 작업자의 저장소 변경을 무작정 덮어쓰기.
- HTTP 451을 이유로 이미 확보한 사진의 개인 보관본 제공까지 포기.

---

### 인수인계 결론

**기능 골격은 동작하지만 전체 수집/영구 연결 작업은 미완료.** 가장 시급한 것은 **GitHub Actions 임시 보관본이 만료되기 전에 원본 파일을 비공개 영구 저장소로 옮기고, 두 모델 모두 그 실파일을 실제 갤러리에서 열어 검증하는 것**이다. 이후 빠진 18개 및 59개와 신규 미확보분을 이어서 채운다. 기존 ZIP 번호 0 결함은 이 대화에서 1로 수정한 새 218장 ZIP으로 해결했으며, 정식 수집기·임포터 회귀 테스트에도 반영해야 한다.
