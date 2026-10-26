# 심유이 비공개 클라우드 아카이브 — 설계 및 현재 상태

## 저장소 선정

- 원본 저장소: TeraBox (무료 최대 1TB 표방). 공식 한국어 요금표에서는 1024GB를 '기간 한정'으로 표시하므로 영구 보장 아님. 실제 계정은 아직 연결되지 않았음. 무료 계정 파일당 4GB 업로드 제한.
- 갤러리 브라우저: /apps/yui-gallery/cloud.html
- 미디어 게이트웨이: /apps/yui-gallery/cloud/gateway/main.py (비공개, Bearer 인증)
- GitHub Pages에는 전체 상업 화보 파일이나 TeraBox 쿠키를 넣지 않음.
- 선택적 캐시: Cloudflare R2 Standard는 월 10GB-month까지만 무료. 초과 비용 발생에 사전 동의 없으면 사용하지 않음.
- 대안: MEGA 무료 20GB와 공식 rclone backend (자동화는 더 안정적이나 용량이 부족함).

## 현재 작동 상태

기술 연결부·원격 SHA256 검증 코드는 구현했지만 실제 TeraBox 저장 및 온라인 게이트웨이 배포는 아직 안 됨. 모의 테스트 및 공개 웹판 스테이징 성공은 실계정 업로드 성공이 아님.
계정 생성, 사용자 로그인, TeraBox 쿠키 발급, Render workspace 선택, API 서비스 생성도 하지 않았음.
현재 공개 웹사이트에 있는 다른 갤러리 파일들을 실제 1TB 업로드로 착각하지 말 것.

## 데이터 처리

1. 화보 원본 ZIP(검증된 manifest.json과 images/파일) 수집.
2. cloud/ingest_verified_zips.py 가 ZIP 안의 물리 파일과 SHA256/이미지 디코딩을 재검증.
3. 픽셀 크기와 출처를 기록하고 바이트를 그대로 originals/ 아래 저장.
4. 검색·미리보기용 520px 썸네일을 previews/ 아래 별도로 생성.
5. metadata/catalog.json에 작품별 실물 보유 장수와 품질·원본 및 미리보기 SHA256 기록. 미연결 스테이징의 storage_provider는 pending_external_upload.
6. cloud/upload_to_terabox.sh 가 실계정에 파일을 업로드하고 cloud/verify_remote.py 가 원본·미리보기 **모든 파일**을 rclone cat으로 재다운로드하여 바이트 길이와 SHA256을 검증. remote-verification.json 감사 기록을 저장한 뒤 카탈로그를 마지막에 업로드하고 그 카탈로그도 재다운로드 해시 검증.
7. cloud/gateway/main.py 가 인증된 사용자에게만 TeraBox로부터 사진 **전체 바이트**를 읽고 카탈로그에 적힌 길이·SHA256과 일치할 때만 전송.
8. cloud.html은 그 API에서 실물 파일을 열람/확대/개별 다운로드.

## 설정: 사용자가 실제로 한 번 승인해야 하는 작업

1. 본인 TeraBox 계정을 선택해 로그인.
2. 서버용 안전한 방식으로 TeraBox ndus 세션을 비밀 환경변수 RCLONE_CONFIG_ARCHIVE_COOKIE에 설정.
3. 별도의 갤러리 인증토큰 GALLERY_ACCESS_TOKEN을 서버 비밀 환경변수에 저장.
4. Render workspace를 사용자 지정 후 cloud/gateway Dockerfile을 배포. 환경변수 RCLONE_CONFIG_ARCHIVE_TYPE=terabox, ARCHIVE_REMOTE=archive:YuiArchive.
5. cloud.html 화면에 비공개 게이트웨이 URL과 갤러리 토큰을 입력.
계정 쿠키·비밀번호는 채팅이나 공용 저장소에 붙여넣지 말 것. 사이트가 비공식 백엔드를 차단하면 연동이 깨질 수 있음.

## 품질 및 권리

- 공개 웹사이트 이미지 97/97은 공개 웹 변형본 97장을 의미한다. 출판사 원본 8192px 확보를 뜻하지 않는다.
- 실제 파일의 width, height, bytes, sha256을 기록. 가상 업스케일을 원본이라고 표시하지 않음.
- 웹 이미지의 무단 재게시 의혹은 출판사 저작권을 소멸시키지 않는다. 정당하게 보유한 원본과 자유 공개물을 우선 저장하며, 공개 공유/배포 권한은 별도 검토.
- Render 무료 웹 서비스는 유휴 시 잠들 수 있고, TeraBox 비공식 rclone fork는 SLA가 없다.
- 계정 쿠키가 노출되면 계정 접근 권한이 넘어갈 수 있어 유출 시 즉시 재인증/폐기해야 한다.

## 자료 근거

TeraBox fork: https://github.com/gulp79/rclone-extra
TeraBox backend: https://github.com/derrundetisch/rclone-extra/blob/master/docs/content/terabox.md
R2 pricing: https://developers.cloudflare.com/r2/pricing/
MEGA rclone backend: https://rclone.org/mega/

## 로컬 파이프라인 예

python apps/yui-gallery/cloud/ingest_verified_zips.py folder/album1.zip folder/album2.zip --out cloud-stage
bash apps/yui-gallery/cloud/upload_to_terabox.sh cloud-stage

실제 TeraBox 쿠키 없이 마지막 명령을 실행하면 명확한 미연결 오류로 종료되도록 설계. 모든 파일의 원격 재다운로드가 시간 제한 내에 끝나지 않거나 해시가 불일치하면 카탈로그 공개를 중단한다. 실계정에서 대량 처리 시간·세션 유지·쿼터 제한은 별도 검증 필요.
공식 TeraBox 플랜: https://www.terabox.com/korean/cloud-storage-pricing-plans?lang=ko
