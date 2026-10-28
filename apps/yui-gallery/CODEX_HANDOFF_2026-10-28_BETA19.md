# 심유이 갤러리 인수인계 — beta.19 / 2026-10-28 UTC

## 1. 최우선 상태와 해결하지 못한 이유

**사용자의 iPhone에서 사진이 정상적으로 보이지 않는 문제는 미해결이다. beta.19는 이미지 접근 복구 릴리스가 아니다.**

현재 갤러리는 수집된 사진의 메타데이터와 외부 출처 URL을 연결하는 구조다. 개별 실파일을 확보했다는 사실, 개인 저장소에 영구 보관했다는 사실, 사용자의 갤러리에서 그 파일이 열린다는 사실은 서로 다르다. 이 세 단계를 연결하는 작업을 완료하지 못했다.

- 사용자가 제공한 Safari 화면은 `cdn.jliji.com`에서 한국 내 법적 접근 제한인 HTTP 451을 반환한다. 앱의 문법 오류·이미지 파일 손상으로만 설명할 수 없다. 캐시 등으로 일부 사진이 보일 가능성은 있지만 실제 캐시 원인은 확인하지 않았다.
- 개인 보관본용 게이트웨이와 브라우저 연동 코드는 있으나, 현재 운영 저장소·게이트웨이 인증 연결 및 실파일 제공을 완료하지 못했다. `version.json`의 TeraBox 상태도 `not_connected`다.
- 담당 에이전트는 확인된 법적 접근 제한을 피하기 위한 프록시·미러·우회 도메인 구성을 수행하지 않았다. 이를 “개인 갤러리 또는 보유 파일 연결 자체가 기술적으로 불가능하다”거나 “항상 구매 증명을 받아야 한다”는 뜻으로 확대해서 설명하지 말 것.
- 오류 안내와 실패 썸네일 정렬만 수정한 것은 사용자의 “오류 없이 사진 열람” 요구를 충족하지 못했다. 추가 안내 UI나 CI 통과를 접근 복구로 보고하지 말 것.

확보 파일의 실제 위치와 소유자 저장소 기록은 별도 비공개 인수인계서에 남겼다. 다음 작업자는 먼저 그 기록을 읽고 확인 가능한 내용을 사용자에게 다시 묻지 않는다. 작업 공간 파일을 영구 클라우드 보관본으로 표현하지 않는다.

## 2. 버전·기준 커밋·릴리스

저장소: [koith/browser-app-lab](https://github.com/koith/browser-app-lab). 앱: `apps/yui-gallery`.

| 항목 | 확인값 |
| --- | --- |
| 앱 버전 | `v0.1.0-beta.19` |
| beta.18 릴리스 | [PR #239](https://github.com/koith/browser-app-lab/pull/239), `6672e904d8700b6a5a3631c50a8520c2ddb80bd6` |
| beta.19 릴리스 | [PR #259](https://github.com/koith/browser-app-lab/pull/259), `834db3591898c31cf96a643a10cb5189237c1401` |
| 이 문서 작성 전 확인한 최신 main | `b27034cc27d73d5b65f6c6b852224445a7904e4a` |
| 갤러리 항목 / 열람 그룹 | 2,922 / 34 — 정상 열람 보장 수가 아님 |
| 발행처 분류 / 브랜드 자산 | 12 / 9 |
| beta.19 신규 사진 파일 / 고해상도 교체 / 접근 복구 검증 | 0 / 0 / 0 |
| 실기기 iPhone 검증 | 미완료. 사용자 오류 보고와 에뮬레이션 검사를 구분 |

[공개 갤러리](https://koith.github.io/browser-app-lab/apps/yui-gallery/?v=0.1.0-beta.19). 재개 시 최신 main부터 확인한다. 다른 앱에서 main 변경이 계속 들어오므로 이전 전체 tree로 초기화하지 않는다. 문서 작성 시 beta.19 이후 Yui 앱·관련 검증 workflow의 코드 차이는 없었고, 다른 앱 변경은 보존했다.

기존 `CODEX_HANDOFF_2026-10-27.md`의 맨 위는 beta.16 이력이다. 해당 문서를 함께 읽되 beta.17~19와 최신 CI 상태는 이 문서를 우선한다. `version.json`에도 초기 405장 및 과거 세션 누적 카운터가 섞여 있으므로 현재 실적은 해당 릴리스의 검증 JSON·manifest·PR과 대조한다.

## 3. HTTP 451 관련 연결 범위

현재 선택된 manifest에서 `https://cdn.jliji.com/` URL을 쓰는 항목은 다음과 같다. **등록 URL 수이며, 사용자 기기에서 이 수만큼 모두 실패했다는 검증 결과가 아니다.**

| 작품 ID | 해당 출처 URL 수 | 현재 연결 상태 |
| --- | ---: | --- |
| `athletic-club104` | 104 | 해당 작품 전부가 이 출처 URL 사용 |
| `yuis-present33` | 33 | 해당 작품 전부가 이 출처 URL 사용 |
| `teddy-bear97` | 17 | 나머지 80장은 기존 다른 선택 파일 유지 |
| `wet-yui80` | 1 | 나머지 79장은 beta.18에서 더 큰 파일 선택 |
| 합계 | 155 | 접근 복구 미완료 |

교차 출처 `<img>`의 error 이벤트는 HTTP 상태를 노출하지 않는다. 일반 연결 실패를 모두 451로 단정하지 말 것. 한국 사용자에게 확인된 법적 접근 제한과 다른 CDN의 일시적 타임아웃을 구분한다. 해외 CI에서 같은 URL이 열렸다는 사실은 한국에서 접근 가능하다는 증거가 아니다.

## 4. beta.18의 실제 확보·선택 실적

수집 입력은 개별 이미지 683개이며, 기존 사진과 전체 프레임 비교 후 고유 SHA-256 427개를 더 큰 파일로 교체했다. **신규 작품 전체본 0, 신규 갤러리 사진 항목 0, 발행처 최고 원본 검증 0**이다. 원 파일의 바이트·해시를 유지했고 손실 재압축·업스케일을 하지 않았다.

| 기존 작품 | 더 큰 파일 교체 | 유지한 파일에 대한 주의 |
| --- | ---: | --- |
| Thru Thru | 117 / 117 | 긴 변 1,874px. 발행처 최고 원본 인증 아님 |
| Yui Vol.2 | 42 / 42 | 긴 변 1,600px. 발행처 최고 원본 인증 아님 |
| Wet | 79 / 80 | 2번은 1,024px 전체 프레임 유지. 큰 크롭 파일로 대체하지 않음 |
| RAMEN | 50 / 125 | 기존 더 큰 1,920px 75장 유지 |
| Kuro | 35 / 58 | 기존 더 큰 2,331px 23장 유지 |
| Yui Vol.3 | 104 / 106 | 기존 50번 2,400px, 81번 2,048px 유지 |

근거: `verification/beta18-acquisition.json`, `beta18-resolution-selections.json`, `beta18-gallery-qa.json`, `beta18-discovery.json`. 교체본 원격 재다운로드 SHA 427/427 PASS는 **출처 서버 readback**이며 개인 클라우드 업로드 검증이 아니다. 로컬 실제 교체 사진 427장 열람도 별도로 통과했다.

동일 사진의 여러 판본을 서로 다른 포즈로 오판하던 매칭과 저장 방향 90/270도 비교를 보완했다. `display_rotation`과 CSS로 방향만 바로잡으며 사진 열기·저장 URL과 실제 파일 인코딩 방향은 그대로다. Sweet Dream 추가 판본 62개는 기존보다 작아서 교체하지 않았다.

## 5. beta.19가 바꾼 것과 바꾸지 않은 것

`index.html`은 카드·사진 격자의 실패 상태와 작은 안내를 표시하고, 실패한 사진도 셀 비율 2:3을 유지한다. 초기 WebKit 픽스처에서 깨진 이미지 높이가 달라지는 문제를 발견해 컨테이너 자체에 비율을 지정했다.

`reportedRestrictedHosts` / `failedRestrictedImages`는 보고된 출처에서 이미 실패한 URL을 확대 화면 진입만으로 자동 재요청하지 않도록 한다. 원본 사진 열기 링크는 유지한다. 다음 정상 사진으로 이동하면 실패 상태를 해제한다. 출처 URL·SHA·해상도·사진 순서·사진 파일을 바꾸지 않았다. 프록시나 다른 출처로의 전환을 추가하지 않았다.

`test_image_error_states.py`는 실제 앱에서 합성 이미지와 451/503 응답을 사용해 실패 안내, 정상 사진 복귀, 셀 정렬, 반복 요청 방지, 원본 링크, Back, touch 설정을 검증한다. **이 테스트의 외부 사진 요청과 실제 화보 열람 검증 수는 0**이다. 이를 실제 사진 접근 복구 실적으로 세지 않는다.

## 6. 최종 CI와 배포 결과

| 범위 | 실행 / 결과 | 해석 |
| --- | --- | --- |
| beta.18 PR 최종 전체 검사 | [40703435316](https://github.com/koith/browser-app-lab/actions/runs/40703435316) PASS | 두 엔진 각각 2,922항목·원본 링크 SHA 25개. 출처 readback 427개 PASS |
| beta.18 main 재실행 | [40710352767](https://github.com/koith/browser-app-lab/actions/runs/40710352767) FAIL | Chromium 및 실제 production 2,922개 PASS. WebKit은 Maid 177번 타임아웃, 해당 실행 2,807/2,922 |
| beta.19 PR 오류 처리 검사 | [40741436962](https://github.com/koith/browser-app-lab/actions/runs/40741436962) PASS | Chromium / WebKit 합성 오류 픽스처. 실제 사진 검증 아님 |
| beta.19 main 오류 처리 검사 | [40741829933](https://github.com/koith/browser-app-lab/actions/runs/40741829933) PASS | 두 엔진 통과 |
| beta.19 main 전체 검사 | [40741829867](https://github.com/koith/browser-app-lab/actions/runs/40741829867) **FAIL** | 출처 SHA 427개 PASS. WebKit job123033231379 전체 2,922항목·링크 SHA25 PASS. Chromium job123033231363은 Blackroom 73번·Kuro 42번 `cdn1.thismore.fun` 타임아웃 |
| beta.19 Pages | [40741829869](https://github.com/koith/browser-app-lab/actions/runs/40741829869) PASS | 병합본과 공개 코드·버전·기존 manifest/표지 설정 8개 SHA 일치 확인 |
| beta.19 Browser Smoke / Cloud Connector | [40741829865](https://github.com/koith/browser-app-lab/actions/runs/40741829865) / [40741829994](https://github.com/koith/browser-app-lab/actions/runs/40741829994) PASS | UI·연동 코드 검사. 운영 저장소 연결 성공 증거가 아님 |

원본 URL·기대 장수·해상도·SHA를 낮추거나 실패 사진을 건너뛰어 전체 검사를 성공으로 만들지 않는다. 외부 CDN 재다운로드→브라우저 엔진 순서로 직렬화한 workflow를 유지한다. 출처 427개 재다운로드가 필요한 데이터 변경과 단순 문서 검증을 구분하며 불필요한 직접 CDN 재요청을 추가하지 않는다.

## 7. 재개에 필요한 코드와 미완료 작업

| 경로 | 역할 / 주의 |
| --- | --- |
| `index.html` | 목록·발행처·사진·이력·확대·실패 표시. 실제 제공 경로 미연결을 해결한 것으로 오인하지 않음 |
| `owner-media.js` | 세션 기반 비공개 `/api/catalog` 및 `/api/media/.../original` 연결. 수신 크기·SHA 검증 후 blob URL 사용 |
| `cloud.html`, `cloud/gateway/main.py` | 개인 보관본 연결 UI와 인증 게이트웨이. 구현과 운영 배포/연결은 별개 |
| `cloud/ingest_verified_directories.py`, `cloud/verify_remote.py` | 개별 파일 stage·원격 검증. 오래된 README의 수량·예시를 현재 완료 상태로 읽지 않음 |
| `public_photo_archive.py`, `collect_public_sources.py` | 무료 수집·사이트 어댑터·접근/속도 제한 처리 |
| `merge_higher_resolution.py`, `photo_quality_policy.py` | 전체 프레임 비교, 실제 해상도 우선, 동일 해상도에서 확인된 무워터마크 우선 |
| `identity-exclusions.json` | `sexiest18`, `cn-miaohuaying` 등 사용자 배제 작품의 재등록 방지 |
| `qa_gallery.py`, `qa_album_covers.py`, `qa_mobile_navigation.py`, `qa_publishers.py` | 실제 사진·표지·이력·발행처 검증. 픽스처와 범위 구분 |

우선 미완료는 실제 안정적 제공 경로와 한국 모바일 열람 검증이다. 소유자 파일 기록·현재 연결 상태부터 확인하고, 이미 알려진 파일 위치를 다시 사용자에게 묻지 않는다. 접근이 허용된 제공 경로·계정 연결은 소유자 범위에서 검토하며 법적/인증 제한을 회피하는 구성을 만들지 않는다. 새 보관본은 실제 업로드와 원격 재다운로드 SHA가 통과한 뒤 갤러리에서 실파일 열람을 확인해야 완료로 센다. 새 경로가 검증될 때까지 유일 사본·기존 판본을 삭제하지 않는다.

신규/최신 전체 화보, 소수 사진만 등록된 작품의 전장 보충, Wet 2번 전체 프레임 고해상도, 발행처 최고 원본, 실제 iPhone 핀치·저장·Back 검증은 계속 미완료다. 이전 조사 후보·썸네일·유료/VIP 목록을 확보 실적으로 세지 않는다. B컷 참고 목록의 제목·SKU만으로 다른 사이트의 영문 작품과 동일하다고 확정하지 않는다.

사용자의 유지 조건: 기존 UI 초기화 금지, 사진을 중심으로 작은 메타 정보, 얼굴이 잘리지 않도록 목록 표지 채움, 발행처/화보 전환과 이름 오름차순, 상세 사진 격자 유지, 원본/AI 구분과 발행처 스티커, 작은 우상단 버전, native Back·핀치·길게 누르기, 반투명 사진 열기 버튼. 사진 압축파일 생성/불러오기/열람·손실 재압축·TinyFish·유료 크롤러·무료 크레딧 의존·카드·월 요금 도입 금지. 정기 개발 보고에는 버전·커밋/PR·신규 실파일·실제 열람 수·CI·미완료를 모두 적는다.

이번 인수인계는 문서만 작성한다. 앱 버전·사진·UI·제공 경로를 변경하거나 접근 복구를 완료한 것으로 보고하지 않는다.
