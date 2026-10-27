> ## beta.10 인수인계 — 2026-10-27 KST
> **현재 코드 버전 v0.1.0-beta.10. 아래 beta.9 및 이전 기록은 과거 상태다.**
> 갤러리: https://koith.github.io/browser-app-lab/apps/yui-gallery/?v=0.1.0-beta.10
> beta.10 배포·최종 CI는 작업 PR에서 확인. 직전 로컬 검증 2522개는 다른 모델 18장 제거·검색 팝업 적용 전의 기록이며 최종 검증으로 세지 않는다. 이번 환경에서는 브라우저 실행과 네트워크가 샌드박스로 차단되어 최종 Chromium/WebKit 실검증·소스 285개 재다운로드 SHA-256을 GitHub Actions에서 수행한다.
> 직전 배포: PR #226, 7277b22e2aa99c17f1c5c5d7216caeb24e53bddb. beta.9 실제 배포 2490개 전체 디코딩·저장 링크 23개 해시 및 선택 소스 743개 재다운로드 SHA-256 통과, main Chromium/WebKit CI 40492756050 PASS.
>
> - 사용자 새 우선순위: **높은 실제 해상도 먼저, 같은 해상도에서는 화보 사이트 워터마크가 없다고 확인된 파일 먼저**. 특정 사이트를 무조건 선호하지 않는다. photo_quality_policy.py를 판본 병합과 최종 등록 양쪽에 적용. site_watermark_review는 해당 SHA-256과 검토 근거가 일치해야만 absent/present로 인정하며 나머지는 unknown. 낮은 해상도 무워터마크 파일로 내려가거나 워터마크를 지워 새 파일을 만드는 방식은 사용하지 않는다. 원 입력 판본 모두 보존.
> - 썸네일 스티커: 발행사는 좌상단, 장수는 그 아래 작고 흐리게, 판본은 우상단. 원본 검증이 없으면 웹판으로 표시하며 AI 보정판과 구분. 미확인 발행사는 추측하지 않는다. 목록 카드만 3:4에서 3:2로 바꿔 같은 가로 폭에서 높이를 정확히 절반으로 줄였다. 화보 내부 이미지 그리드는 변경하지 않았다.
> - 사진 열기 오버레이: 전체 불투명도 .55, 배경 알파 .333, 기본 배경의 실효 불투명도 약 .18. 우하단 위치·면적은 유지하며 키보드 포커스/마우스 호버에서 읽기 쉽게 표시한다.
> - 사용자 확인: sexiest18 (The Sexiest Woman) 18장은 다른 모델이므로 공개 등록·수집 대상에서 제거. 출처와 18개 해시를 재수입 차단하고 사설 감사 사본은 보존. 런타임도 모든 공개 manifest에 배제 정책을 적용해 오래된 응답의 재노출을 막는다.
> - 검색은 우측 작은 반투명 돋보기 버튼으로 접고 native dialog 팝업으로 제공. 브라우저 뒤로가기/앞으로가기·ESC·적용·닫기를 지원. 화보 내부 이미지 그리드 크기는 유지.
> - 이번 전체 신규 실파일은 **고유 SHA-256 317개**(아래 두 AI 판본 64개와 4Kup 대체 판본 253개). 입력 사본과 선택본 모두 검증·보존했다.
> - 4Kup의 명시된 확대 링크에서 **Heart Steal 78장 전부 1920px, CREAM 100장 2048px, RAMEN 75장 1920px**을 확보해 동일 사진 전체 화면 대조 후 큰 파일을 선택했다. 발행사 최고 원본 확인은 여전히 미완료다.
> - ArtGravia 실제 신규 실파일 **고유 SHA-256 64개**: ArtGravia 663 AI 보정 공개 웹판의 서로 다른 32장짜리 판본 2개. 32장 전체를 더 큰 1368px 파일로 선택했다. **새 원본/최고 해상도/최신 발행 화보로 주장하지 말 것**. AI라는 표시를 제목과 품질 정보에 유지한다. 같은 작품의 v03/h07/c07 참고 항목을 새 32장 전체 목록에 연결했다.
> - Girl Atlas를 새 무료 공개 HTML 수집 어댑터로 추가: 특정 한국 Yui 태그·제목·공개 개수·visible=True·명시된 !lrg 확대 링크를 검증한다. 로그인 다운로드 버튼이나 숨겨진 원본 경로를 사용하지 않는다. Teddy 97장도 확인했지만 기존 Kaizty 1199px 파일과 정확히 같은 SHA-256이므로 신규 수집/고해상도 교체로 세지 않았다.
> - 갤러리 예정 합계 2504개 항목 / 26개 그룹: 완전한 웹판 21개(ArtGravia AI 포함), 미완료 공개자료 5개. 실제 최종 PR/배포 QA 결과는 해당 PR에 기록한다. 이번 변경 전 검증 숫자를 새 버전 검증으로 표현하지 않는다.
> - 계속해야 할 작업: 공식 MOVIE FANTASY(M.F/H.F), CTEE, BCUT, SWEETBOX, MilkyBomb, Yo-U의 작품명·공개 샘플로 중국어 제목 및 텍스트/이미지 검색과 사진 전체 화면 대조를 수행. MOVIE FANTASY를 MilkFilm과 혼동하지 말 것. 동명이인 UEE, 다른 Yui, Sims 게임 이미지 등 검색 잡음은 제외. 새로 찾은 표지/참고 목록을 실파일 화보 확보로 세지 않는다.
> - 최고 원본·최신 전체 화보·Everyday Life 194장·Teddy 나머지 87장 및 미분류 자료 확보는 여전히 미완료. 비공개/인증/유료 장벽 우회 금지. 개인 영구 클라우드 업로드·재다운로드 검증 0장. 원본 바이트·모든 기존 자료·우상단 작은 버전 표시 유지. 일반 개발/테스트/병합/배포는 승인 질문 없이 진행.
>
> ---

> ## beta.9 인수인계 — 2026-10-27 KST
> **현재 코드 버전 v0.1.0-beta.9. 아래 beta.7/beta.4/beta.3 내용은 과거 기록이다.**
> 갤러리: https://koith.github.io/browser-app-lab/apps/yui-gallery/?v=0.1.0-beta.9
> beta.8 잘못된 모델 제거 배포: PR #225, 602540bb36b3c2a210ac21c65ff4954ba7786a94. 이후 main의 자동 수집 변경도 확인했다.
>
> - 신규 **7개 완전한 공개 웹판 650장** 실파일 수집·SHA-256·디코딩 완료: Kuro Yui 58, Yui Vol.2 42, Yui Vol.3 106, Blackroom 145, Dec 2023 199, PUSSYLET Vol.41 82, The Sexiest Woman 18. 단순 색인/표지 추가가 아니다.
> - 다른 출처까지 실제 내려받은 검증 파일은 이번 작업 기준 **고유 SHA-256 1283개**. 동일 사진의 판본을 포함하므로 신규 사진 1283장이라고 하지 말 것. 이 중 신규 작품 사진 650장과 기존보다 큰 대체 파일 323장을 갤러리에 선택했다.
> - **Kuro Yui 58/58 전부 더 큰 파일로 교체**. 추가로 Dec 2023 113/199, Blackroom 59/145, Tracksuit 93/201을 큰 파일로 교체. 선택 파일은 원 응답 바이트 그대로이며 손실 재압축·업스케일하지 않았다. 근거: verification/beta9-resolution-selections.json.
> - **Teddy Bear는 10장 부분 카드(v04)를 기존 확보 97장 전체에 연결**했다. 기존 10개 2699px 저장 파일은 정확한 SHA-256 폴백으로 계속 사용한다. 새 Kaizty 97장은 전부 1199px로 더 작아서 교체 거부. MissKon 공개 표본도 1024px로 더 작았다. **나머지 87장의 최고 해상도 확보는 여전히 미완료**. 97장 전체를 고해상도로 교체했다고 하지 말 것.
> - album-aliases.json으로 V2PH/중국 색인에서 이미 확보한 작품을 열었을 때 미수집처럼 보이던 연결을 수정. 신규 7개 작품은 기본/전체 목록 어디서나 열린다. 동일 작품 부분 카드를 별도 화보로 중복 집계하지 않는다.
> - 갤러리 **2490개 항목 / 26개 그룹 = 완전한 웹판 21개 + 미완료 공개 자료 5개 그룹**. 실제 사진 고유 개수와 구분할 것. 5개는 huantuji 3, chaotuji 3, yuntu8 4, yingyuge 2, Everyday Life 1장. 인덱스/프로필 사진을 완전한 화보로 취급하지 않는다. Everyday Life는 194장 중 실제 사진 전체를 확보하지 못했다.
> - 해상도 완료 판단의 임의 1920px 기준을 제거했다. 수량이 완전해도 최고 원본 검증은 모두 미완료로 추적한다. AI 보정 판본은 비 AI 판본을 자동 교체할 수 없다. Green은 계속 AI 판본으로 명시.
> - beta.9 로컬 실제 갤러리 2490개 디코딩·저장 링크 SHA-256 23개 통과. 마지막 Dec 2023 추가 대체분은 별도 재검증하며, 최종 PR CI와 실제 배포 결과를 PR에 기록한다. 이 기록만으로 실제 배포/실기기 iPhone 검증을 주장하지 말 것.
> - 잘못된 모델 cn-miaohuaying 3개는 공개 저장소에서 삭제했고 사설 감사 사본만 유지한다. 재수입 차단 정책·소스 제거를 보존한다. 얼굴 인식으로 사람을 식별하지 않는다.
> - 최신 CTEE にゃ〜 공식 페이지는 브라우저에서 공개 API 접근 오류를 재현했다. Bcutrank는 작품 참고 링크이며 성인 인증/구매 장벽을 우회하지 않는다. 새 출처 발견·Teddy/Everyday/기타 최신 작품 원본 탐색은 계속 필요하다.
> - **개인 영구 클라우드 연결·실업로드·원격 재다운로드 검증 0장**. 작업 환경의 실파일과 갤러리 출처 링크는 영구 개인 보관이 아니다. 유일한 원본 사본 삭제 금지. ZIP/사진 압축파일·TinyFish·유료 수집 서비스·카드·월 요금 사용 없음.
> - 현재 실파일: /workspace/yui-private/beta8-pixibb/verified-albums; /workspace/yui-private/beta9-alternatives/{best,작품-kaizty}; /workspace/yui-private/beta9-alternatives-second/{best,작품-kaizty}. 기존 소장 입력도 보존했다.
>
> ---

> ## beta.7 최종 인수인계 — 2026-10-27 UTC
> **현재 배포 버전: v0.1.0-beta.7. 이 절이 최신이며 아래 beta.4/beta.3 기록은 과거 상태다.**
> 갤러리: https://koith.github.io/browser-app-lab/apps/yui-gallery/?v=0.1.0-beta.7
> 병합: PR #222 https://github.com/koith/browser-app-lab/pull/222 · PR #223 https://github.com/koith/browser-app-lab/pull/223 · PR #224 https://github.com/koith/browser-app-lab/pull/224
> **배포 코드 SHA: 50b0b6413447cbca23017c25d9103b25cb62e8a5.** Pages 배포 PASS: https://github.com/koith/browser-app-lab/actions/runs/40460206781
>
> - 이번 작업의 신규 실파일은 **844개 고유 SHA-256**: Tracksuit 201 + Maid 291 + Last Summer 192 = 신규 3개 웹판 684장, Seethrough 프록시 판본 80장, 선택된 직접 주소 판본 80장. 같은 사진의 서로 다른 판본을 신규 사진 160장으로 표현하지 말 것. 물리 파일·SHA·디코딩 검증 후 실제 갤러리에 연결했다.
> - **Seethrough 80장 전부를 기존 장축 1368px에서 2500px로 교체했다.** 15개의 명시적으로 연결된 Kaizty 페이지, 160개 프록시 URL 응답에서 80개 고유 파일을 확인했다. 프록시는 Chromium에서 디코딩에 실패했으므로 원본 페이지의 imgErrorHF가 명시한 직접 주소를 별도로 수집·검증했다. 직접 파일은 프록시와 바이트가 다르므로 이전 해시를 재사용하지 않았다. 80/80 사진을 보수적으로 대조해 정규 순서를 유지했다. 근거: verification/beta7-seethrough-resolution.json.
> - **Teddy Bear 97장 중 10장은 2699px로 교체**했다. 기존 저장 미리보기 10개와 정확히 같은 SHA-256이므로 신규 확보 10장으로 세지 않는다. V2PH CDN이 작업 환경에서 403을 반환하여, 동일 해시의 기존 stored-albums 파일을 갤러리가 우선 사용한다. 작은 썸네일을 대신 쓰는 방식이 아니다. 기존 405장 중 확인된 고해상도 교체는 이 10장이다.
> - 갤러리는 **총 1853개 이미지 항목 / 21개 그룹**: 완전한 웹판 14개와 불완전한 공개 미리보기 7개. 중복 작품 및 같은 파일을 재사용한 항목이 있으므로 고유 사진 1853장으로 표현하지 말 것. 수량·해상도 부채: verification/gallery-coverage.json. 발행사 최고해상도 원본 인증은 여전히 0장이다.
> - UX: 가운데 중복 COLLECTION/Yui Gallery 제거, 좌상단 로고 하나만 유지. 화보명·수량을 작은 고정 상단 정보로 이동. 2열 썸네일 시작점 정렬. 뒤로가기·닫기는 같은 좌상단 위치, 브라우저 Back/Forward 정상 작동. 사진을 빠르게 넘길 때 WebKit History API 제한을 피하도록 주소 갱신을 지연한다.
> - 확대/축소 및 개별 다운로드 버튼과 하단 버튼 공간을 제거했다. 브라우저 기본 핀치 확대와 이미지 우클릭/길게 누르기를 차단하지 않는다. 사진 열기만 이미지 우하단 반투명 버튼으로 유지. 버전은 우상단의 작은 글씨로 유지한다.
> - **최종 main Chromium·WebKit CI 모두 PASS**: https://github.com/koith/browser-app-lab/actions/runs/40460207644 . 각각 1853개 사진 디코딩·모바일 Back/Forward·250회 연속 전환·저장 파일 링크 36회 해시 검사(고유 26개 파일) 통과. PR 검증: https://github.com/koith/browser-app-lab/actions/runs/40459777694 .
> - **배포된 실제 URL에서도 1853개 전부 디코딩 + 링크 해시 36회(고유 26개) PASS**, 오류 0. 근거: verification/beta7-production-qa.json. 관리형 환경의 브라우저 CA 문제 때문에 TLS를 검증하는 requests 브리지를 사용했다. CI는 직접 브라우저 TLS다. 실기기 iPhone의 핀치·저장 메뉴 검증으로 표현하지 말 것.
> - 수집/품질 도구: http_album_collector.py의 Kaizty 공개 페이지 및 사이트가 제공한 직접 주소 경로, quality_alternative_targets.json, merge_higher_resolution.py의 정확한 바이트/픽셀 중복 제거 및 검증 결과 자동 등록. 기존 파일·수량·더 큰 판본을 보존한다. 손실 재압축·인위적 업스케일·사진 압축파일·TinyFish·유료 수집 서비스 사용 없음.
> - **미완료:** 7개 부분 미리보기의 완전한 화보 확보, 나머지 낮은 웹판의 더 큰 판본, 최신 발행사 작품/공개 샘플 추가 수집, 실기기 iPhone QA. 인증·유료 제한은 우회하지 않았다.
> - **개인 영구 클라우드 미연결 / TeraBox 업로드·원격 재다운로드 해시 검증 0장**. 출처 링크와 작업 환경의 파일은 영구 개인 보관 완료가 아니다. 기존 유일한 검증 사본을 삭제하지 말 것. iOS TeraBox QR 로그인은 완료되지 않았으며, 검증되지 않은 스캔 메뉴를 다시 안내하지 말 것.
> - 사용자 지시: 통상적인 개발·수집·테스트·병합·배포는 별도 승인 질문 없이 진행. 비용·계정 권한 변경·데이터 삭제처럼 중요한 결정만 확인. 확보한 모든 화보는 갤러리에 연결할 것.
>
> 작업 환경 원본(환경 유지 시): /workspace/yui-private/beta5-collected/verified-albums/{tracksuit201,maid291,last-summer192}; /workspace/yui-private/beta7-best/seethrough80 (프록시 판본); /workspace/yui-private/beta7-direct-best/seethrough80 (선택 직접 판본); /workspace/yui-private/recovered (기존 405). 입력 판본들은 삭제하지 않았다.
>
> ---

> ## beta.4 인수인계 추가 — 2026-10-27 KST
> 현재 배포 버전은 **v0.1.0-beta.4**. 아래 beta.3 본문은 이전 기록이다.
> **PR #221 병합**: https://github.com/koith/browser-app-lab/pull/221
> 코드 병합 SHA: `86c0a2ecafe8eeb952b64baa28a65f1cb580d7ad`.
> 검증한 Pages 배포 SHA: `3975ef7f758023d205fe24724415cd5513854b72` (출처 인덱스 자동 갱신).
>
> - 기존 405장 전부를 개별 파일로 다시 내려받아 기존 SHA-256과 일치 및 디코딩 검증했다.
> - 신규 다운로드 **844개 실파일**에는 Sweet Dream 다른 판본 106장이 포함된다. 새 고유 화보 **6개 / 선택본 738장**: CREAM 228, Thru Thru 117, Sweet Dream 110, Seethrough 80, RAMEN 125, Heart Steal 78.
> - Sweet Dream 선택본 110장 중 106장은 공개된 전체 크기 링크의 실제 **1920px** 파일을 선택했다. 기존 낮은 판본과 보수적인 사진 매칭 후 큰 파일을 바이트 변경 없이 복사했다. 근거: verification/higher-resolution-web-selections.json. **기존 405장의 고해상도 교체는 0장**, 발행사 원본 확인도 0장이다.
> - additional-source-albums.json에 신규 738장의 실제 수집 파일 해시·픽셀·출처 URL을 등록했다. 갤러리 총 **18개 그룹 / 1169개 이미지 항목** (기존 저장 26 + 기존 출처 405 + 신규 출처 738). 작품 중복 그룹을 포함하므로 고유 사진 1169장이라고 표현하지 않는다.
> - **Chromium 및 WebKit CI 각각 1169개 확대 이미지 디코딩 + 저장 26개 브라우저 다운로드 SHA-256 PASS**: https://github.com/koith/browser-app-lab/actions/runs/40414360257
> - 배포된 실제 주소에서도 1169개 디코딩 및 저장 26개 다운로드 해시 PASS. 관리형 환경에서는 TLS를 검증하는 requests 브리지로 Chromium 프록시 CA 문제를 처리했으며 TLS 검증을 끄지 않았다. **실기기 iPhone QA는 미완료**.
> - HTTP/gallery-dl 수집 완료 시 공유 등록기로 자동 연결한다. 기존 앨범을 보존하고 파일 잠금·원자적 교체로 동시 등록 충돌을 막는다. Jliji 재수집이 같은 앨범 카드를 중복 생성하지 않도록 ID로 병합한다.
> - 사진 확대·개별 다운로드 UI를 추가하고 현재 픽셀을 표시했다. 저장 파일 26개 다운로드는 실제 브라우저 검증, 인증 보관본 다운로드는 로컬 모의 원격 검증이다. **출처 호스팅 이미지의 직접 fetch 다운로드는 사이트 CORS에 제한될 수 있으며 전체 원격 사진 다운로드 성공으로 보고하지 않는다.**
> - cloud/ingest_verified_directories.py의 손실 미리보기 재압축을 제거했다. originals와 preview 경로 모두 수집 바이트를 그대로 보존한다.
> - 무료 수집기: gallery_dl_extractors/pixibb.py, 수정된 jliji.py, http_album_collector.py, http_album_targets.json, build_additional_source_manifest.py, merge_higher_resolution.py. 유료 크롤러·TinyFish·사진 압축파일 생성 없음.
> - CTEE https://ctee.kr/item/store/86995 의 **にゃ〜 | 심유이 YUI** 제목과 Bcutrank 심유이 23편을 확인해 research-sources.json 및 작품 참고 목록에 반영했다. 참고 목록·표지를 실파일 확보로 세지 않는다. 공식 최신 화보 전체 및 공개 샘플 추가 수집은 남아 있다.
> - Maid/Tracksuit는 이번 수집에서 정상 디코딩 파일 0장이며 성공/확보로 세지 않았다. 이미지 호스트 및 응답 원인을 추가 분석해야 한다. Xasiat 두 링크는 영상 스크린샷이므로 화보 사진 수로 세지 않았다. ImgCup은 403으로 우회하지 않았다.
> - **TeraBox 미연결 / 실파일 업로드·원격 SHA-256 재다운로드 검증 0장**. QR 발급 자체는 성공했지만 현재 사용자의 iOS 앱에서 로그인 승인 경로를 완료하지 못했다. 오래된 '아바타 옆 스캔' 안내를 현 iOS UI에서 검증 없이 다시 지시하지 말 것. 공식 OAuth 승인 방식 검토가 필요하다. 공개 출처 링크는 개인 영구 보관소가 아니다.
> - 월 이용료 0원·카드 미등록 원칙 유지. 신규 파일은 작업 환경의 개별 파일 폴더에 있고 원격 영구 보관 완료가 아니다. 기존 유일한 검증 사본은 삭제하지 않았다.
>
> 작업 환경 원본 경로(환경이 유지되는 경우): /workspace/yui-private/recovered (405), /workspace/yui-private/new-albums (신규 및 판본), /workspace/yui-private/pixibb/verified-albums/seethrough80, /workspace/yui-private/new-albums/sweet-dream-best. 원격 계정 연결 후 이 파일들부터 검증·업로드할 것.
>
> ---

# Codex 개발 인수인계서 — 심유이(Yui/심혜성) 화보 아카이빙 갤러리

작성 기준: 2026-10-27 KST
저장소: https://github.com/koith/browser-app-lab
앱: https://koith.github.io/browser-app-lab/apps/yui-gallery/
현재 앱 표시 버전: **v0.1.0-beta.3**
상태 확인 당시 main SHA: **dbfe79b9cd636e36d2a140bc0a15b814ad3634a7** (다른 프로젝트도 같은 main을 수정하므로 최초 작업 전 다시 조회)
기존 인수인계: apps/yui-gallery/HANDOFF_2026-10-26.md (과거 기록이며 ZIP 지시 등 일부가 이미 폐기됨. 본 문서를 최신 기준으로 우선 적용)

## 0. 코덱스에게 직접 지시 — 요약

이 프로젝트의 목적은 **사용자가 iPhone에서 심유이 화보를 직접 볼 수 있는 실사용 개인 갤러리**를 만들고, 아직 수집하지 못한 화보를 **무료 오픈소스 크롤러로 대규모·지속적·증분 수집**하는 것이다. 기존 작업을 초기화하거나 설명/목록만 추가해서 끝내지 마라. 코드를 직접 수정하고 테스트하여 GitHub에 반영하라.

절대 요구사항:
1. **ZIP/압축파일 제작, ZIP 가져오기 UI, 다운로드를 열람의 전제조건으로 만드는 방식 금지.** 이미지 각각을 독립된 파일로 저장한다. 기존 웹판 바이트를 손실 재압축/리인코딩/인위적 업스케일하지 않는다.
2. **사용자가 볼 수 없다면 보관 성과가 아니다.** 개인 보관소는 제3자 접근을 제한해도 소유자는 웹 갤러리에서 실제 파일 전체를 바로 볼 수 있어야 한다. 파일 선택·ZIP 풀기·클라우드 관리자 UI 수동 열기 등을 사용자에게 강요하지 마라.
3. **유료 수집 API·크레딧 기반 크롤러·카드 등록 없이** Python, Playwright, gallery-dl, Scrapy/Crawlee 계열의 직접 실행 가능한 무료 기술을 채택한다. **TinyFish 사용 금지.** Firecrawl 무료 크레딧이나 다른 SaaS 한도에 핵심 파이프라인을 의존시키지 않는다.
4. 출처 조사 수를 5~6곳에서 끝내지 않는다. 사용자는 **500개 사이트 수준을 조사해도 모자랄 정도로 광범위한 발견·비교·기술 적용**을 요구한다. 500개를 조사했다고 허위보고하지 말고, 검증된 사이트/화보/실파일 수를 분리 집계한다. 중복 출처·도메인·게시글은 중복 제거한다.
5. **앱 버전은 화면 우상단에 작은 글씨**로 노출한다. 매 개발 보고 시 버전, 커밋/PR, 갤러리 실제 열람 검증 수, 새로 확보한 실파일 수, 남은 일, QA를 명시한다.
6. 합법적으로 공개·접근 가능한 이미지 또는 사용자가 권한을 가진 이미지만 수집한다. 인증·유료 장벽 우회 금지. **공개 열람 허용과 타인 저작물의 공개 재배포 권한은 다르다.** 상업 화보 파일을 무단으로 공개 GitHub Pages에 미러링하지 않는다.

## 1. 실상 — 숫자와 단계 정확히 구분

- **실제 재수집/검증된 웹판 이미지: 화보 5세트 405장.** 파일의 바이트/픽셀/SHA-256 검사와 목록 생성 CI 성공. **발행사 최고해상도 원본이라고 검증된 것은 0장**이다.
- 현재 GitHub Pages 저장소에 물리 이미지 파일로 존재하는 것은 **26장** (stored-albums.json, stored-albums/). 총 7개 부분 앨범/그룹에 분산.
- source-viewer-albums.json에는 외부 출처 사이트의 이미지 URL로 연결된 **405장 / 5개 화보**가 있다. 갤러리 화면상으로는 **26 + 405 = 431개 이미지 항목 / 12개 그룹**이다. Teddy Bear 등의 **중복/동일 작품**이 있으므로 고유 431장이라고 표현 금지.
- 외부 출처 405장은 **우리 개인 클라우드에 영구 보관된 405개 실물 파일이 아니다**. 서버가 링크를 차단/삭제/만료시키면 갤러리 열람도 깨질 수 있다. 일시적인 직접 열람용 연결이다.
- 갤러리 모바일 Chromium CI가 431개 항목을 렌더링하고 대표 원격 사진(athletic-club104 및 green91) 실제 로딩을 확인해 PASS한 로그가 있다. **전체 405장의 원격 브라우저 실물 로딩 검증, 실기기 iPhone Safari QA는 별도 미완료.**
- 대용량 무료 개인 저장소(TeraBox 후보)는 **실계정 미연결, 업로드 및 원격 SHA-256 재다운로드 검증 0장**. 인증 FastAPI 게이트웨이는 모의 테스트만 완료. GitHub Pages 링크를 영구 보관의 대체물로 보지 않는다.
- 이전에 검증된 별도 임시 안전 사본이 있다. 405장 데이터의 장기 안전성을 확인하기 전 **기존 유일한 검증 사본을 임의 삭제 금지**. 단, 사용자에게 압축파일을 열람 방식으로 요구하거나 앞으로 압축본을 추가 생성하지 않는다.
- 작품 색인에는 현재 59개 항목이 렌더링된 QA 기록이 있으나, 중복·출처별 복제본을 포함한다. **고유 신규 작품 59개 확보로 해석 금지.**

기검증 작품(모두 공개 웹판):
| ID | 화보 | 검증 사진 | 상태 |
|---|---|---:|---|
| yuis-present33 | SWEETBOX Yui's Present | 33/33 | 웹판 |
| athletic-club104 | Yui — Athletic Club | 104/104 | 웹판, 일부 가로 사진 2305px |
| wet-yui80 | Yui — Wet Yui | 80/80 | 웹판 |
| teddy-bear97 | SWEETBOX Yui — Teddy Bear | 97/97 | 웹판, 별도 v04 10장과 중복 가능 |
| green91 | Yui — Green | 91/91 | **AI 보정 웹판**, 원본 취급 금지 |

## 2. 이미 구현한 소스 — 반드시 재사용

앱/목록:
- apps/yui-gallery/index.html — 사진 우선 일반 갤러리, 검색·앨범·사진·전체 작품, 전체화면/스와이프/개별 사진 열기, 우상단 v0.1.0-beta.3 표시.
- apps/yui-gallery/stored-albums.json + stored-albums/ — 저장된 실물 26장.
- apps/yui-gallery/source-viewer-albums.json — 5개 화보 405개 **출처 호스팅 이미지 URL**. 전체 405장 사진 바이트가 아님.
- apps/yui-gallery/albums.json — 여러 출처 화보 색인. 중복 통합 필요.
- apps/yui-gallery/version.json — 버전, 클라우드 미연결, 실제 검증량 등. 숫자 변경 시 반드시 실제 검증 근거와 동기화.
- apps/yui-gallery/cloud.html — 현재 실계정 미연결 클라우드 갤러리. 이상적인 목표는 사용자가 별도 페이지/토큰 설정 없이 일반 갤러리에서 사진을 보는 것.

수집/크롤러:
- apps/yui-gallery/download_jliji_collections.py — Playwright + HTTP 기반 4개 공개 화보를 개별 파일로 수집(314장).
- apps/yui-gallery/download_verified_public_album.py — Green 및 별도 Teddy Bear 웹판 개별 파일로 수집.
- apps/yui-gallery/build_source_viewer_manifest.py — 405개 실제 수집 파일의 SHA-256을 검증하고 출처 URL 열람용 인덱스 생성.
- apps/yui-gallery/archive_engine.py + source_targets.json — 공개 사이트 6개 초기 대상, lazy-loading, 스크롤·페이지네이션 탐색, 파일별 보관.
- apps/yui-gallery/gallery_dl_collector.py — **무료 gallery-dl** CLI 적용, JPEG/WEBP/PNG 등 이미지 독립 파일·SHA-256·SQLite 다운로드 이력.
- apps/yui-gallery/gallery_dl_extractors/jliji.py + gallery_dl_targets.json — Jliji 웹 갤러리를 위한 자체 gallery-dl 외부 추출기와 4세트 타깃. 소스별 추출기 확장 출발점.
- apps/yui-gallery/promote_downloaded_previews.py — 실제 다운로드한 공개 미리보기 중 적법하게 배포 가능한 것만 갤러리 실물 저장소에 등록.

클라우드/검증:
- apps/yui-gallery/cloud/ingest_verified_directories.py — **압축파일 없이** 개별 사진 폴더/manifest.json 입력, 바이트 무변경 originals/, 별도 previews/, metadata/catalog.json 생성.
- apps/yui-gallery/cloud/upload_to_terabox.sh / verify_remote.py — 실제 비공개 계정에 개별 업로드, 원격 재다운로드 후 바이트/SHA-256 확인.
- apps/yui-gallery/cloud/gateway/main.py — 원본 원격 읽기·인증·검증 FastAPI 게이트웨이. 실 배포 여부는 새로 확인.
- apps/yui-gallery/cloud/README.md — 상세 구현 문서. 표제는 beta.2지만 현 앱 기준은 beta.3.
- apps/yui-gallery/test_version.cjs, test_gallery_dl_collector.py, test_source_viewer_manifest.py, cloud/test_ingest_directories.py 등 — 자동검증.

CI:
- .github/workflows/yui-source-viewer-sync.yml — 무료 gallery-dl / 브라우저 수집 / 405장 출처 목록 생성, 공개 Pages에는 링크/메타데이터만.
- .github/workflows/yui-gallery-smoke.yml — 모바일 Chromium 실제 렌더/대표 사진 로딩/버전 위치.
- .github/workflows/yui-dynamic-archive.yml — 기존 6개 공개 출처 주기적 크롤링/소량 미리보기 갱신.
- .github/workflows/yui-cloud-real-albums-dryrun.yml — 405장 클라우드 폴더 스테이징 검증.
- .github/workflows/yui-cloud-integration-qa.yml — 가짜 원격/인증/브라우저/컨테이너 QA.
- .github/workflows/yui-terabox-live-free-upload.yml — TeraBox 실제 계정 토큰이 있을 때만 작동. 실행 버튼 존재만으로 연결 완료 처리하지 말 것.

## 3. 최근 작업과 확인 가능한 증거

- PR #216 (병합) https://github.com/koith/browser-app-lab/pull/216 — ZIP 중심 경로 제거·개별 파일 저장/해시·업로드 폴더 수용·구형 ZIP 뷰어 제거, v0.1.0-beta.2.
- 2026-10-27 이후 main에 beta.3 수집/갤러리 코드가 병합되어 있음. 최근 관련 main 커밋 **e50ca602a8bf**(beta.3), **2d7ae3019ef7**, **baa47d928ce**, **8ed00de08da6**, **6ad811b22c94**. 현재 main은 다른 4LEAF 프로젝트 때문에 이보다 전진했음. 먼저 SHA 갱신.
- 405장 생성/검증 + 무료 수집 파이프라인: https://github.com/koith/browser-app-lab/actions/runs/40353556856 — 성공. 다만 이 로그에서는 새 외부 gallery-dl Jliji 추출기가 ValueError(not enough values to unpack)로 실패하고 기존 Playwright 수집기로 405장을 성공적으로 수집했다. 그 뒤 main에 외부 extractor 메시지 튜플 수정 및 실파일 QA 강화 커밋이 들어왔으므로 **수정 후 현재 extractor의 실사이트 성공 여부는 재실행 로그로 독립 확인할 것**.
- 431개 갤러리 항목 + 대표 외부 이미지 열람 + 우상단 v0.1.0-beta.3 모바일 Chromium: https://github.com/koith/browser-app-lab/actions/runs/40353556865 — 성공, 로그에는 albumCount 12, allPhotos 431, sourceRemoteBrowserQA true.
- 최근 GitHub Pages 배포: main SHA dbfe79b9...의 Pages 워크플로 성공(실제 방문 및 iPhone QA는 별도 점검).
- 구형 PR #213, #215는 열린 상태로 남아 있음. **오래된 UI/ZIP 중심 내용을 현재 main에 덮어쓰지 말 것.** 필요 시 비교 후 닫기.

## 4. P0 — 코덱스가 가장 먼저 완료할 작업

1. 작업 시작 시 main SHA, 버전, 기본 갤러리/클라우드/405 manifest, CI 실결과를 새로 읽는다. 기존 작업을 절대 초기화하지 않는다. beta.3 레이아웃/우상단 버전 유지.
2. **내가 실제로 보는 사진 중심으로 안정화.** 405개 URL이 iOS Safari / Chromium에서 실제로 열리는지 앨범별/파일별 점검한다. HTTP 상태와 decoded image size를 확인하고, 열리지 않는 URL은 다른 공개 출처/정당하게 확보된 실물로 대체한다. 431개 DOM 기록만으로 431장 사용 가능이라고 선언하지 않는다.
3. **이미 획득한 405개 개별 사진을 직접 연결되는 영구 보관소로 옮긴다.** 사용자 비용은 월 0원, 카드 등록 없음, 사진 그대로(비손실 변경 없음), 계정 소유자 iPhone 즉시 접근, 개별 사진 다운로드 필수. 공개 GitHub Pages에 상업 화보 파일을 무단 재배포하지 말 것. 현재 TeraBox 후보 외에도 무료 대용량 공식/비공식 API, 저장소 게이트웨이, 계정 유지·속도·크기 제한을 비교하고 작은 앨범로 실계정 시험. 필요한 최소 **1회 계정 로그인/승인만** 사용자에게 요청; 인증정보를 채팅/리포/로그에 기록하지 않는다.
4. 업로드는 405개 **개별 사진** → 원격 직접 읽기 → 각 파일 길이/SHA-256 일치 → 카탈로그 마지막 확정 → 일반 갤러리 열람 순. 원격 인증·다운로드 실패 시 다른 안전한 경로를 시험하되 사용자 승인 없는 우회/과금 금지.
5. 기본 갤러리(index.html)에 사용자 본인이 바로 접속하면 **해당 405장의 인증된 보관본**이 실제 열리게 한다. 별도 수동 ZIP 선택이나 토큰 복사 반복이 없는 구조. 전체화면·스와이프·원본 개별 다운로드 및 모바일 네트워크 실제 QA.
6. 우상단 작은 버전 표시, 버전 변경 및 카운트/상태 동기화. 기존 소스에는 HTML 태그 옆에 리터럴 역슬래시 n(\\n) 문자열이 남아 있는지 확인하여 필요시 수정할 것.
7. P0 완료 판정은 **영구 원격에 사진 실물이 존재하고 재다운로드 해시 검증, 실제 인증된 iPhone 갤러리 읽기까지 통과했을 때**만 PASS. 외부 링크 405개는 P0 완료가 아님.

## 5. P1 — 남은 화보의 대량 탐색/실파일 확보

1. 기존 색인(중국 화보 사이트, 원발행사, V2PH, SWEETBOX, SNS 원출처, 여러 언어 명칭)을 바탕으로 seed source 목록을 확장한다. 타깃 명칭: 심유이, 심혜성, Yui, 沈惠星 및 실제 검증된 변형. 검색 엔진/사이트 내 검색/목록 pagination/사이트맵/게시 날짜 피드/발행사 DB를 조합한다.
2. 사용자 요구는 **광범위한 출처 발굴**이다. 500개 사이트 조사도 모자랄 수 있다는 요구를 수집기 설계 범위로 받아들이되, 숫자만 채우지 말고 **서로 다른 사이트 호스트/작품 상세 페이지/화보 실물**을 분리 계수한다. 사이트별 접근 가능 여부, 마지막 확인 시각, API/이미지 로딩 기술, 중복률, 저작권/권한 상태까지 추적한다.
3. 무료 gallery-dl의 공식 extractor + 자체 외부 extractor를 우선; 미지원 사이트는 Scrapy/직접 HTML·HTTP/Playwright로 적법한 공개 페이지 탐색. srcset, data-full, lazyload, infinite scroll, next page, 이미지 CDN 변환 URL의 실픽셀 비교로 **실제 취득 가능한 최대 해상도** 확보.
4. 새 수집기의 성공은 다운로드된 정상 디코딩 이미지/바이트/SHA-256과 순번 연속성으로 판정. 로그인 회피, 속도 제한 회피, 유료 자료 침해, 차단 우회 도구 사용 금지. robots/사이트 약관·저작권 존중, 속도·동시성 제한.
5. **고유 작품 원장**: 발행처, 작품 제목/다국어 별명, 발매/게시 날짜, 표기 장수, 공개 웹판 실확보 장수, 발행사 원본 확인 장수, 이미지 URL/실파일 경로, 폭·높이·파일 바이트·SHA-256, AI 보정 여부, 출처/허용 상태, 중복/누락 수. SNS 사진은 화보 작품 실적과 별도.
6. 신규 실파일 확보 → 원격 검증 저장 → 일반 갤러리 자동 목록 갱신까지 연결. URL·미리보기·빈 앨범 카드만 추가한 것을 성과로 보고하지 마라. 수집 실패 시 원인과 보완 후 재실행을 남긴다.
7. 최근 조사에서 5세트 외 추가 화보 예시: CREAM YUI, Seethrough YUI, Sweet Dream, RAMEN, Thru Thru 등. **이름이 검색됐다는 것과 실제 확보/전체 이미지 검증은 별개**다. 유료 원본이면 정당한 권한을 가진 경로를 우선한다.

## 6. P2 — 운영화

- 크롤러 작업 큐/사이트별 adapter/증분 SQLite DB/콘텐츠 해시+지각 해시 중복 제거, 실패 체크포인트·재시도, 재개 기능, 주간 신규 작품 통계.
- 버전/개발원장/작품 수치와 CI 근거를 일치시키고, 우상단 버전은 CSS 소형 크기/모바일에서도 가려지지 않게 유지.
- 무료 사용 한도나 외부 서비스의 가격 변경으로 수집 엔진 전체가 중단되지 않도록 재현 가능한 무료 오픈소스 의존성 고정 및 대체 경로 마련.
- 사용자의 저장 파일을 임의로 삭제하지 않고, 실제 새 저장소·복구 검증 후 오래된 임시 사본 폐기 여부를 결정.
- 최종 UX는 사용자가 **일반 갤러리 하나에서 앨범·사진을 누르는 것만으로 감상**하는 방식.

## 7. 보고/수락 기준 — 반드시 이 형식

매 보고 첫머리에 아래 사실을 적는다:

- 앱 버전 / main SHA / PR 번호 및 병합 여부 / Pages 배포 SHA.
- **유일 작품 수**, 작품별 기대 사진 수 / 실제 취득 파일 수 / 원격 SHA-256 재검증 파일 수 / 사용자 갤러리 실제 로딩 성공 파일 수. 출처 URL 개수와 사진 바이트 개수 구분.
- 소스별 성공·실패율, 신규 실파일 수, 품질(최고 실제 픽셀과 발행사 원본/공개 웹판/AI 보정), 중복 제거 결과.
- 월비용, 카드 등록 여부, 스토리지 실제 원격 경로, iPhone 실기기 QA 여부. 미완료를 PASS라고 쓰지 않는다.
- 문제가 있으면 관측 로그, 수정 커밋, 재실행 결과와 남은 작업을 간결히 기록.

초기 확인용 명령:

    git fetch origin
    git checkout main && git pull --ff-only
    git rev-parse HEAD
    cat apps/yui-gallery/version.json
    python -m pip install Pillow requests playwright gallery-dl
    python -m playwright install chromium
    python apps/yui-gallery/test_gallery_dl_collector.py
    python apps/yui-gallery/test_source_viewer_manifest.py
    node apps/yui-gallery/test_version.cjs
    # 실 사이트 수집은 현재 타깃과 권한/실행량을 검토한 후
    python apps/yui-gallery/gallery_dl_collector.py --max-sources 2 --max-images 3
    python apps/yui-gallery/download_jliji_collections.py
    python apps/yui-gallery/download_verified_public_album.py
    python apps/yui-gallery/build_source_viewer_manifest.py

**실행 지시:** 최초 목표는 이미 확보한 화보의 **실물 개인 보관·직접 감상 완성**, 동시에 **gallery-dl 자체 추출기 실사이트 성공 고정**이다. 그 다음 새 화보를 광범위하게 찾아 실제 개별 사진을 계속 수집하고 자동으로 갤러리에 반영하라. ZIP을 되살리거나 유료 크롤러에 기대지 마라. 설명·제안만 하지 말고 소스 변경, 테스트, 병합·배포, 진짜 사용 가능한 결과를 제출하라.
