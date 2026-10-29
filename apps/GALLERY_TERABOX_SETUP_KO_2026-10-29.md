# 심유이·밈미 개인 갤러리 — TeraBox 무료 저장소 연결 안내

2026-10-29 기준. 공개 화보 배포가 아닌 본인 전용 비공개 보관과 정상 접근 가능한 공개 사진의 SHA 검증 백업에 한한다.

## 연결 전 확인

- 본인 계정으로 [TeraBox](https://www.terabox.com/)에 로그인한다.
- 기존에 [Google Drive에 백업한 원본 ZIP 13개](GALLERY_PRIVATE_ARCHIVE_PRESERVATION_AUDIT_2026-10-29.md)는 삭제하지 않는다. 연동 실패 시 복구용 보관본이다.
- 공식 TeraBox API가 아니라 커뮤니티의 **비공식** `gulp79/rclone-extra` TeraBox 백엔드를 사용하므로, 세션 만료·서비스 정책 변경·성능 문제가 생길 수 있다.
- 클라우드 계정 비밀번호, 쿠키/NDUS, GitHub Actions secret 값은 절대 채팅·Issue·PR·공개 코드에 복사하지 않는다.

## 1. 본인 PC에서 TeraBox 로그인 쿠키 확보

1. Windows PC Chrome에서 TeraBox에 로그인한다.
2. `F12` → `Network` → 새로고침 → `www.terabox.com`에서 보낸 정상 요청 하나를 선택한다.
3. `Headers` → `Request Headers` → `Cookie`의 **값만** 복사한다. `Cookie:` 같은 헤더 이름 자체는 제외한다.
4. 브라우저 개발자 도구에서 값을 복사한 뒤 다른 곳에 붙여넣지 말고 GitHub Secret 등록 화면에 직접 입력한다. 로그아웃하면 만료되거나 다시 등록해야 할 수 있다.
5. 공식 문서는 [rclone-extra GitHub README](https://github.com/gulp79/rclone-extra#how-to-add-a-terabox-remote-in-rclone-extra)에서 확인할 수 있다.

## 2. GitHub Actions Secret 등록

[이 저장소의 Actions secrets 페이지](https://github.com/koith/browser-app-lab/settings/secrets/actions) → `New repository secret`:

| Name | Secret 값 | 사용하는 워크플로 |
|---|---|---|
| `YUI_TERABOX_COOKIE` | 본인 TeraBox 로그인 쿠키 | `yui-terabox-live-free-upload.yml` |
| `MIMMI_TERABOX_NDUS` | 본인 TeraBox 로그인 쿠키 또는 지원되는 NDUS 값 | `mimmi-private-cloud-sync.yml` |

두 모델을 같은 계정에 저장하려면 같은 쿠키를 두 Secret에 각각 입력한다. 작업 코드의 대상 폴더는 `archive:YuiArchive`와 `archive:MimmiArchive`로 구분한다. **비공개 프로젝트 안에서도 쿠키는 로그인 세션의 권한이 있으므로 절대 공개하지 않는다.**

## 3. 먼저 안전한 연결 검사 실행

[Gallery TeraBox Private Connection Check](https://github.com/koith/browser-app-lab/actions/workflows/gallery-terabox-connection-check.yml) → `Run workflow` → `main` → `both` 선택 → `Run workflow`.

- 초록색 성공 / 작업 Summary에 `YUI`, `MIMMI` 인증 완료가 나오는지 확인한다.
- 빨간색 실패 / `TERABOX_NOT_CONFIGURED`: Secret 이름 또는 등록 여부 확인.
- 빨간색 실패 / `TERABOX_AUTH_FAILED`: TeraBox 사이트에 재로그인한 뒤 새 쿠키로 Secret 갱신.
- 이 검사는 `rclone lsd archive:`로 로그인 및 폴더 목록 접근만 확인한다. **사진 업로드·삭제는 수행하지 않는다.**
- Actions job의 Summary/로그에 쿠키 원문이 표시되지 않도록 구현되어 있다.

## 4. 실제 사진 업로드는 별도로 검증

TeraBox 연결 성공만으로 기존 Drive 원본이 TeraBox에 자동 복사되지는 않는다. 심유이 기존 `Yui Free TeraBox 405 Photo Archive Upload`는 과거 405장 재수집 절차가 먼저 실행돼 451 등 때문에 실패할 수 있으며, 밈미 `Mimmi Private Photo Sync`는 연구 목록에 있는 실제 공개 사진에 대해 바이트 검증 후 개별 저장을 시도한다.

따라서 **원본 Drive ZIP을 제거하거나 완전 동기화로 보고하지 말고**, 현재 확보한 보관본의 정상 다운로드·사진별 SHA와 TeraBox 원격 바이트 재검증을 통과한 뒤에만 모델별 백업 완료로 기록한다. iPhone Safari 실제 사진 표시에도 별도 인증 갤러리 연결이 필요하다.

## 보안 메모

- TeraBox 비공식 클라이언트는 저장소의 체크섬으로 고정한 바이너리만 실행하고, 비밀번호나 쿠키 자체는 GitHub Actions Secret에서만 주입한다.
- 본인 계정 쿠키의 권한이 과도한 서비스 특성상 일회성 테스트 또는 비공개 보관 용도로만 사용하며, 계정 탈취가 의심되면 TeraBox에서 세션을 종료하고 Secret을 갱신한다.
- 개인용 Google Drive 원본 ZIP은 **계속 독립 백업**으로 유지한다. 무료 1TB는 광고 용량이며 장기 용량·속도·정책을 보증하지 않는다.
