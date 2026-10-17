# 4LEAF 원작 웹앱 복원 — 개발 인수인계서 (2026-10-17)

> **상태: 원작 복원 진행 중, 미완성.** GitHub CI/Pages 배포가 성공했다는 뜻은 기능 회귀 검사를 통과했다는 뜻이지, 2001~2004년 4LEAF 원작과 시각적으로 같다는 뜻이 아니다. 이 문서는 다음 대화나 개발자가 사용자의 반복 설명 없이 **실제 코드 수정 → 정량 비교/Chromium QA → 병합 → 공개 배포 확인**을 계속하기 위한 작업 기준점이다.

## 0. 즉시 인수해야 하는 사용자 요구

- 목표는 **원작과 동일한 외형과 실제 조작·플레이 경험**이다. 데모/모형/현대식 게임으로 만족하지 않으며, 작은 CSS 패치나 현황 보고만 하고 중단하지 말 것.
- **우선순위:** 월드맵 및 북·남 하이아칸 ChatTown/ChatRoom의 외형·실제 채팅을 최우선으로 계속 교정하고, 동시에 사용자가 직접 지적한 **주잔 육각 말판이 부정확하게 겹치는 현상과 캐릭터가 창세기전식 8등신 게임 캐릭터가 아니라 채팅용 아바타처럼 보이는 문제**를 첫 게임 화면 P0에 반영한다. 주잔의 실제 3D 지형·캐릭터·전투도 반드시 복원 과제로 이어갈 것.
- 정적 원작 화면 **스크린샷 한 장을 배경으로 붙이고 투명 버튼만 얹는 방식은 금지**. 원본 개별 PNG/타일/DMP/실제 조작 상태를 살아 있는 DOM/Canvas/WebGL 요소로 연결한다.
- 실제 자료가 없는 곳에 **가짜 채팅방, 사용자, NPC, 접속 인원, 원작 높이값, MVE 메시, 전투 애니메이션**을 만들어 놓고 원작 복원이라고 표시하지 않는다. 원본에서 확인된 정보와 개발상 추정은 명시적으로 분리한다.
- 채팅방 좌석 클릭은 원작처럼 **즉시 순간이동**, 선형 이동 연출 금지. 실제 서버에서 확인된 방/사람만 표시.
- 원본 기능을 해치지 않는 수정이어야 한다. **월드맵, 켈티카, 매직카덴, 북·남 채팅, 레코르다블, 주잔, 실제 2브라우저 통신, 무료 중앙 서버 및 오프라인 패키지** 보존.
- 원인 분석과 테스트는 개발의 일부이지 개발을 대체하지 않는다. **작게 고친 뒤 바로 종료하거나 사용자가 같은 지시를 반복하게 만들지 말 것.**

## 1. 작업 저장소 / 최신 확인 시점

| 구분 | 정확한 위치 또는 상태 |
| --- | --- |
| GitHub | https://github.com/koith/browser-app-lab |
| 정적 공개 웹앱 | https://koith.github.io/browser-app-lab/apps/4leaf/rog/ |
| 게임 소스 루트 | `apps/4leaf/rog/` |
| 원본 추출 리소스 | `apps/4leaf/rog/original/` |
| 당시 게임 스크린샷 | `apps/4leaf/assets/` |
| 핵심 근거 대장 | `apps/4leaf/rog/docs/original-experience-evidence.md` |
| 이전 인수인계 | `apps/4leaf/rog/docs/RESTORATION_HANDOFF_2026-10-15.md` |
| 이 문서 작성 시점의 최신 **게임 코드** main | `b32d7424733a552f384ddfaa35a2d0ff18e061a5`, PR #91 |
| 문서 작성 시 열린 PR | **0개** |
| PWA / Service Worker | `sw.js` — `4leaf-revival-pwa-v56` |
| 주의 | 인수인계 문서 커밋 이후 최신 `main` SHA는 변하므로 다음 개발은 반드시 다시 조회 |

### 최신 게임 코드 `b32d742` 기준 확인한 실제 워크플로 성공

- GitHub Pages 정적 배포: https://github.com/koith/browser-app-lab/actions/runs/38993091578 — **success**
- 배포 후 공개 URL 실제 Chromium 브라우저 QA: https://github.com/koith/browser-app-lab/actions/runs/38993114157 — **success**
- WorldMap·ChatRoom 통합: https://github.com/koith/browser-app-lab/actions/runs/38993091546 — **success**
- 25개 원본 맵/원본 게임 자료 검증: https://github.com/koith/browser-app-lab/actions/runs/38993091630 — **success**
- 게임 스모크: https://github.com/koith/browser-app-lab/actions/runs/38993091509 — **success**
- 중앙 채팅 인증/정원/2브라우저: https://github.com/koith/browser-app-lab/actions/runs/38993091619 — **success**
- WebRTC 실제 다중 참가자: https://github.com/koith/browser-app-lab/actions/runs/38993091515 — **success**
- 오프라인/PWA 자산·게임: https://github.com/koith/browser-app-lab/actions/runs/38993091596 — **success**

**엄격한 해석:** 위 성공은 각 자동화 검사의 주장에 한정된다. 3D 모델, 전체 원본 스크린샷 픽셀 유사도, 영구 운영 서버, 역사적 원본 조작 프로토콜의 완전 재현을 검증하지 않는다. 이 문서를 업데이트하는 GitHub 문서 전용 커밋은 게임 코드 기준점과 구별한다.

## 2. 원본 근거 등급

- **VERIFIED-ARCHIVE:** 리포지터리의 추출 원본 PNG, `original/maps.js`, `tiles.js`, `chessmen.js`, RGBA 픽셀/원본 크기.
- **VERIFIED-SCREENSHOT:** 2003~2004 실제 사진/캡처에서 육안 또는 정량적으로 확인된 위치·상태. 사진에서 보인 외형이 코드 수준 원본 구현을 뜻하지는 않는다.
- **VERIFIED-CODE/QA:** 실제 소스·Chromium 검사가 보여 준 현행 웹앱 동작. 원작 동일성 자체의 입증과 별개.
- **INFERRED WEB UX:** 데이터가 없어서 임시로 구성한 위치·키 바인딩·화면 그림자·표정 메시지 전송·2.5D 무대·미니맵 카메라 테두리.
- **UNVERIFIED / NOT RECOVERED:** 원본 EXE 이벤트/서버 프로토콜, 채팅공간 전체 지형 좌표, 실제 MVE 기반 3D 메쉬·높이·애니메이션·조명·카메라 투영.

**가장 흔한 사고:** 원본 리소스가 있는 것과 **그 이미지를 어느 화면에서 어떻게 조합했는지 아는 것**은 다르다. 원본을 잘못 분류하거나 1:1 스프라이트의 표시 크기/깊이를 바꿔 원작과 다른 화면을 만들지 말 것.

## 3. 원본 자료 — 장면과 역할을 혼동하지 말 것

| 실제 파일 | 장면 / 검증된 용도 |
| --- | --- |
| `original/WorldMap/` | 원본 월드맵, 6개 진입 지역, 약 796×528 화면 |
| `original/WorldMap/notice.png` | 원본 날개 달린 Notice 184×61, 역사적 화면 약 (23,9) 상시 안내판 |
| `original/MainFrame/toolbarbtn.png` | 원본 120×270, 30×30 스프라이트 4상태 × 9행; 개별 버튼의 원래 EXE 이벤트 매핑은 미확보 |
| `original/MainFrame/pannel.png` | 원본 323×124 패널 타일. **323×240으로 착각했다가 실제 PNG 검사로 정정됨** |
| `original/MainFrame/title.png` | 원본 680×54 제목 파츠 |
| `original/ChatTown/northback.png`, `southback.png` | **북·남 하이아칸 지역 선택 794×404**; 둘 각각 8구역 |
| `original/ChatRoom/room1..room6.png` | 6개 원본 794×528 채팅방 실내 |
| `original/ChatRoom/room3t.png` / `room4t.png` / `room5t.png` | 독립 전경 가구: 272×102 / 115×103 / 176×128. 4번은 실제 사진 기반 좌표 검증, 3·5번은 추정 좌표 |
| `original/ChatRoom/chatbaredit.png`, `userlist.png` | 원본 채팅 입력 407×21 / 참가자 목록 150×38 |
| `original/ChatRoom/ringbtn.png`, `scrollbar.png` | 원본 캐릭터 메뉴 104×330 / 메시지 스크롤바 52×40 |
| `original/ChatRoom/ownerdialog.png` | 방장 개설 338×282 원본 아틀라스: 실제 입력·확인·취소에 연결 |
| `original/ChatRoom/expdialogbtn.png` | 원본 196×267 표정 버튼 6종; 웹 복원 표정 메시지/원본 얼굴 표시 |
| `original/Registry/avatardialog1..3.png` | 원본 캐릭터 선택/정보 패널 PNG, 실제 참가자 캐릭터를 선택 |
| `original/Registry/savaNN.png` | **75×141 원본 스탠딩 캐릭터**. 일부는 이미 투명 RGBA. **주잔의 잃어버린 8등신 3D 모델을 확보했다는 뜻이 아님** |
| `original/KnightTown/knightback.png` / `sea01..`·`snow01`·`plain01..` | 레코르다블 지역 선택 **794×404** 및 6종 568×74(142×74 × 4프레임) 원본 표지판 |
| `original/Map/mapback.png` | **주잔 GAME ROOM SELECT**. ChatRoom 방 선택 화면으로 잘못 전용하지 말 것 |
| `original/Region/regionback.png` | **주잔 TOWN SELECT 채널 화면**. 북남 하이아칸 채팅 선택과 관계없음 |
| `original/IMG/title.png`, `chatwnd.png`, `minimap.png` | 주잔 800×600 메인 / 406×152 채팅 / 172×152 미니맵 |
| `original/IMG/bgtile.png` | **주잔 경기 725×485 숲 지형**; ChatTown 원본 지형이라고 잘못 적용했던 이력 있음 |
| `original/Tiles/*.png` | 실제 145×97 TIS **이미 입체적인 림이 그려진** 플랫폼 그림. 원본 DMP 격자 중심 간격은 70×47 |
| `original/maps.js` / `tiles.js` | 25개 원본 DMP 맵, 좌표/칸 코드, 이벤트/유효 워프 연결 |
| `original/IMG/dialog.png` / `eventmsgbox.png` | 주잔 대화창 292×110 / 실제 경기 상태 표시 244×52 |
| `original/CardData/chm_*.png` | 원본 체스맨 카드 |
| `apps/4leaf/assets/sky.jpg`, `chat.jpg`, `chat_ref.jpg` | 실제 원작 월드맵·채팅 캡처 |
| `apps/4leaf/assets/board.jpg`, `battle.jpg`, `dice_ref.png`, `dice_ref2.png` | 실제 주잔 말판·전투 화면 참고 |
| `apps/4leaf/assets/intro.jpg`, `street.jpg`, `town_ref.jpg`, `shop_ref.png` | 로그인/거리/마을/상점 비교 자료 |

**중요 조사 결과:** 현재 `main`의 Git 파일 트리를 실제로 검색했으나 `.mve`, `.tis`, `.dmp`, `.pak`, `.exe` 원본 바이너리는 발견되지 않았다. 해당 형식의 실시간 3D 모델·높이 정보를 이미 확보했다고 주장하면 안 된다. 현재 추출본은 주로 PNG/JS/JSON이다.

## 4. 현재 구현 — 실제 코드와 검증 수준

### 4.1 월드맵 / 하이아칸 / 레코르다블 (원작 외형 P0)

- `world-map.js`와 `world-map-source-moon.css`: 월드 6개 지역 실제 클릭, 원작 사진에서 참고한 만월; 원본 Notice 상시 프레임.
- `mainframe-native-toolbar.css`와 `mainframe-native-snapshot.js`: 원본 MainFrame 타이틀/30×30 도구모음/원본 워터마크. 원래 EXE의 버튼·명령 매핑은 일부 추정.
- `social-chat.js`, `world-social.css`: 북·남 하이아칸 8구역, 지역 선택, **실제로 생성된/중앙 서버에서 받은 방만 표시**, 채팅방 입장·퇴장·참여자 수·메시지·클릭 좌석 순간이동, 실사용자 동기화. 원작 1480×1120 공간형 지역 지형 자체는 **미확보**: 임의로 만든 지도와 과거의 128개 가짜 방은 제거됨. 정확한 역사적 방 배치와 건물 외형은 **미복원**.
- `chatroom-native-panels.js/.css`, `chatroom-native-ringbtn.css`, `chatroom-native-scrollbar.js/.css`: 6개 실제 배경, 원본 채팅 입력·스크롤·사용자 좌석/원본 메뉴. `room4t` 가구는 역사적 사진 대비 등록, `room3t`·`room5t`는 원본 픽셀 크기만 정확하고 앵커는 추정.
- `chatroom-native-owner-dialog.js/.css`: 실제 원본 소스 방장 팝업 + 진짜 공개/비공개·정원·비밀번호, 임시 503 오류 대응.
- `registry-native-avatar-dialog.js/.css`: 12개 실제 캐릭터 선택, 원본 3조각 캐릭터 선택 패널, 두 브라우저 간 실제 아바타 변경 동기화. 원본의 모든 전신 자세·프레임/걷기 애니메이션은 없음.
- `chatroom-native-expressions.js/.css`: 진짜 6종 표정 그림과 실제 전송. `[표정] ...` 텍스트 전송은 역사적 패킷 복원이 아니라 웹 방식.
- `knighttown-native.js/.css`: 레코르다블 794×404 원본 6지역 이미지와 원본 표지판, 원본 배경과 소스 픽셀 상관계수로 위치 검증. 입장 이후 게시판은 **웹 복원**, 원래 지역 서버 로직은 미복구.
- `street-world.js`, `shop-native.js`, `cardshop-*`: 켈티카 거리·매직카덴 카드샵 기능 유지, 원본 사진 대비 추가 교정 필요.

### 4.2 주사위의 잔영 게임 (사용자 제보로 게임 화면 P0 상향)

- `game.js`: 실제 생성/저장/재개, 25개 원본 맵, 104칸 예시 DMP 경로, 2인 수동 기본 턴, 아이템/어빌리티/판정/전투/보상, 원본 원정대 카드/채팅.
- `dice-native-client-frame.css/.js`: 실제 원본 800×600 주잔·게임/채팅/172×152 미니맵 프레임.
- `dice-native-tis-depth.css`, `dice-native-tis-alpha.js`: 실제 **145×97** TIS 원본을 같은 DMP 칸 중심 **70×47** 피치 위에 별도 DOM으로 표시. 인접 그림의 일부 **겹침은 원본 스프라이트의 자연스러운 크기 관계**다. 그러나 과도한 시각적 중첩·뒤집힌 육각형·상호 클릭 방해 문제는 **사용자 제보가 있는 별도 미해결 품질 항목**이므로 자동 검사 통과만으로 종결 금지.
- `dice-native-tis-orientation.css`: PR #85에서 뒤집혔던 발판 PNG만 `scaleY(-1)` 처리; 배우·맵·게임 좌표 전체 뒤집기는 금지. 실제 스크린샷과 방향이 완전히 일치하는지 추가 육안·픽셀 비교 필요.
- `dice-native-pawn-dmp-depth.css`: 원본 75×141 Registry 이미지와 원본 145×97 TIS를 하나의 DMP 깊이 정렬 평면에 배치. 큰 가짜 청록 포털 삭제. **원작의 8등신 3D 캐릭터/액션 모델로 대체된 상태가 아님**.
- `board-camera.js`, `dice-dmp-camera-controls.css`: 1450×1120 실제 DMP 전체 카메라 이동, 0.65~2.4 줌, 드래그/휠/모바일 핀치/방향키/현재 플레이어 따라가기.
- `dice-native-minimap-navigation.css`와 `game.js::drawMinimap()`: 원본 172×152 미니맵에서 실제 월드 카메라 이동·뷰포트 사각형·마우스/키보드·터치 작동. 2003년 원래 조작법과 뷰포트 테두리 모양은 추정.
- `dice-source-dmp-terrain-explorer.js/.css`: 104개 실제 소스 타일의 좌표·칸 코드·이벤트·워프 연결을 실게임 상태 변경 없이 확인, 워프 칸과 연결 지점에 실제 카메라 포커스. 원본 `IMG/eventmsgbox.png` 배경을 활용하나 **웹 추가 탐색 도구**이고 옛 원본 게임 조작 인터페이스라고 주장하지 않는다.
- `dice-native-battle-podium.css`, `dice-native-battle-dice.css`: 진짜 판정 값에서 흰색 주사위 핍과 2.5D 단상을 렌더링. **스크린샷 기반 추정 CSS**이지 MVE 3D 전투 메시/원본 카메라/움직임/광원 완성본이 아님.
- `dice-ai-autoplay.css`: 새 경기는 실제 사람 손으로 주사위 두 번 굴리는 hotseat 수동 턴 기본; 이전 저장 AI 경기 역시 자동 롤링 보류, 사용자의 명시적 활성화만 허용.
- 오프라인 캐시 `sw.js` v56는 원본 TIS/Registry/DMP·새 카메라 도구까지 패키징한다.

### 4.3 멀티플레이·무료 호스팅

- GitHub Pages: 정적 파일 배포/접속. `central-client.js`: 옵트인 Node 중앙 API, 공개 HTML 메타에 지정된 HTTPS 주소를 사용. 확인된 개발 구성은 `https://fourleaf-central-chat-free.onrender.com`; **다음 담당자가 공개 서버의 현재 가용성과 실제 CORS를 재확인**해야 한다.
- `server/central.cjs`: 서버가 실제 방 생성/정원/방장 권한/세션/메시지 순서를 판단. `tests/central-browser.cjs`와 `server/central.test.cjs` 통과. 이 성공은 **Render 무료 서비스의 데이터 영구 저장이나 24시간 가용성 보장 아님**.
- `network.js`: 별도의 WebRTC DataChannel 수동 신호교환형 주잔 P2P; 중앙 채팅 API와 무조건 같은 기능이 아니다.
- 장기 개선 설계 `docs/free-multicloud-architecture.md`, `docs/recommended-multicloud-design.md`: Cloudflare Worker + SQLite-backed Durable Object, 필요 시 Supabase 프로필. **아직 목표 설계/미배포**. 무료/결제 원칙을 지키고 단일 방에 두 개의 authoritative writer를 세우지 말 것.
- 무료 서비스 절전, 429/503, 재시도·읽기 전용/재접속, 저장 소실, 실사용자 데이터 프라이버시를 정량 테스트로 처리. 사용자가 명시적 승인하지 않은 유료 승격/자동 과금 금지.

## 5. 최근 주요 PR / 이어서 볼 근거 문서

### 원본 UI와 채팅의 복원

- #65 가짜 128개 공용방 제거, 잘못된 주잔 지형 재주입 차단.
- #67 채팅방 4번 원본 가구/좌석, #68 월드맵 184×61 Notice, #69 채팅방 3·5번 원본 가구 크기.
- #70 원본 Room Master 생성 창, #71 진짜 표정 6종.
- #72 레코르다블 원본 KnightTown 6지역, #73 6종 표지판 실제 픽셀 매칭.
- #74 주잔 실제 대화창·이벤트 표시, #75 MainFrame 원본 툴바, #79 실제 Registry 캐릭터 선택창.

### 주잔 말판과 3D 유사 표현 교정 — #80~#91 (최근)

| PR | 실제로 교정한 것 | 놓치면 안 되는 미완성 |
| --- | --- | --- |
| [#80](https://github.com/koith/browser-app-lab/pull/80) | 원본 145×97 TIS 독립 발판, 실제 DMP y-깊이/중첩 | 3D 메쉬/투영 미확보 |
| #82~#84 | 원본 이미지별 RGBA 알파 판정, 불필요한 색상 제거 방지, 캐릭터-발판 같은 깊이 평면 | 실제 3D 높이/조명 미확보 |
| [#85](https://github.com/koith/browser-app-lab/pull/85) | 육각 발판 방향 재교정, 수동 턴 기본 | 원본 실제 기울기/카메라 미검증 |
| #86~#87 | 저장 경기 AI의 뜻하지 않은 자동 주사위 중단, 특수 칸 수동 선택 존중 | 세부 역사적 이벤트 규칙 검증 필요 |
| [#88](https://github.com/koith/browser-app-lab/pull/88) | 실제 1450×1120 DMP 전체 카메라, 드래그/키/핀치/턴 추적 | 역사적 카메라 매트릭스 미확보 |
| [#89](https://github.com/koith/browser-app-lab/pull/89) | 실제 172×152 미니맵에 카메라 이동/뷰포트/모바일 | 원작 입력 매핑 추정 |
| [#90](https://github.com/koith/browser-app-lab/pull/90) | 실제 판정값에 따른 흰색 6면 주사위 핍/핑크 1점 | 원본 3D 주사위 모델·회전 없음 |
| [#91](https://github.com/koith/browser-app-lab/pull/91) | 실제 DMP 원본 칸/워프 연결을 보는 실제 게임 카메라 탐색, 경기 기록/말 위치 변경 없음 | 원본 높이·3D 지형·EXE 입력 미확보 |

핵심 최신 근거 문서:
- [원본 겹친 TIS 및 깊이](./genesis-original-tis-source-size-and-dmp-depth-2026-10-16.md)
- [말판 뒤집힘/수동 턴/AI 저장경기](./dice-manual-orientation-resume-20261017.md)
- [원본 DMP 1450×1120 카메라](./dmp-camera-source-geometry-2026-10-17.md)
- [원본 미니맵/실제 카메라](./genesis-source-minimap-camera-2026-10-17.md)
- [실제 DMP 워프 탐색/게임 상태 불변](./dmp-native-terrain-interaction-2026-10-17.md)
- [전투 핍 주사위의 검증/추정 구분](./genesis-battle-dice-source-evidence-2026-10-17.md)
- [원본 채팅방 역사적 근거](./original-experience-evidence.md)
- [원본 레코르다블 구분/표지판 좌표](./knighttown-original-regions.md)

## 6. 사용자가 재지적한 **가장 중요한 미해결 작업** — 코드 단위로 이어갈 것

### P0-A. 원작 주잔 육각 말판의 실제 시각적 배치 / 8등신 캐릭터

**문제:** 사용자 눈에는 실제 원작과 비교해 타일들이 부정확하게 겹치고 주잔 캐릭터가 채팅용 아바타처럼 보인다. 신규 코드 #80~#91은 *일부* 구조적 수정을 했지만, 원본 스크린샷 픽셀 비교로 원작 유사도를 완성한 증거가 없다.

**다음 담당자의 첫 실제 작업 제안:**

1. 실제 `apps/4leaf/assets/board.jpg` / `battle.jpg` 및 원본 동영상/자료를 기준으로 **800×600 동일 뷰포트**에서 최신 공개 주잔 게임 장면을 Chromium으로 캡처한다. 가능하면 동일한 DMP 맵/카메라/턴을 맞춰 비교한다.
2. `game.js::drawBoard()`, `dice-native-tis-depth.css`, `dice-native-tis-orientation.css`, `dice-native-pawn-dmp-depth.css`, `board-camera.js`의 타일 **145×97 실제 원본, 중심 피치 70×47, z-sort, clip/hitbox, scaleY(-1), 카메라 변환**을 함께 검증한다. 자연스러운 원본 스프라이트 겹침과 **실제 화면에서 잘못된 중복/가림**을 구분한다. 예쁜 척하려고 원본 크기를 다시 70×47로 축소하지 말 것.
3. 원본 아카이브에 실제 **창세기전 8등신 전신/애니메이션/3D 모델과 프레임 소스**가 있는지 별도 자산 조사/검색(사용자가 제공한 바이너리 또는 공개 원본 근거 포함). 현재 확인된 `Registry/savaNN.png` 75×141 스탠딩 이미지는 **ChatRoom과 주잔의 3D 캐릭터를 동일하게 만들라는 증거가 아님**. 원본의 실제 모델/텍스처를 찾아 모델/프레임 로더를 구현해야 함. 원본 소스 확보 없이 길쭉한 CSS 아바타를 만들어 "8등신 원본 완성"으로 보고하지 말 것.
4. 주잔 3D의 실제 높이·카메라 회전·조명·공격 모션 구현은 별도 리버스 엔지니어링 과제. **DMP의 세 번째 코드`record[2]`를 높이값으로 추측하면 안 된다**. 원본 데이터 의미를 증명하거나 외부 실제 실행/영상과 계측해야 한다.
5. Playwright에서 겹침/클릭 행렬, 가려야 할 타일의 y-정렬, 턴/아이템/워프, 실제 캐릭터 타입, 모바일·2브라우저·오프라인·게임 카메라를 반복 검증한다. QA 성공 외에 **원작/현재의 실제 캡처 비교표**와 미복원 수치를 남긴다.

### P0-B. 북·남 하이아칸 채팅 외형과 실제 거주 공간

1. `assets/sky.jpg`, `chat_ref.jpg`, `chat.jpg`와 실제 배포 화면을 **원본 794×528 채팅방 / 794×404 구역 화면**에 맞춰 비교. 단순 안내창·버튼 소소한 수정보다 캐릭터 크기, 역사적 움직임, 실제 방 배치·전경 가구·채팅 인터랙션 등 큰 격차 먼저 처리.
2. 원본 공간형 채팅방 지역 지형/건물·방 점유 데이터가 확보되지 않은 상태다. **주잔 `IMG/bgtile.png`를 ChatTown 배경으로 재사용하거나 128개 가짜 방을 재도입하면 안 된다.**
3. 좌석 순간이동 및 실제 원본 75×141 배우/메시지/방장 권한, 실사용자 두 명 이상, 지형/창 좌표를 함께 검사. 실제 원작의 전신 표정/모션 프레임이 있으면 별도 수집/분석하여 적용.
4. 켈티카/매직카덴/레코르다블 원본 화면도 사진 대비 큰 영역 레이아웃 차이를 계속 계량하고 개선한다.

### P1. 실제 3D 엔진/모델 복구 연구

- 현재 추출 자료만으로 MVE 진짜 높이·삼각형 메시·카메라 매트릭스·모션·3D 전투를 완전히 재구성할 수 없다. 이전 CI가 보증하는 2.5D를 "3D 원작 완성"이라고 서술 금지.
- 원본 실행 파일/자산의 **합법적으로 확보된** 바이너리 포맷/프레임·외부 시대 영상/기술 자료 조사 → 포맷 명세 검증 → 별도 실제 데이터 로더 → WebGL/Three.js 등으로 독립 카메라/모델/높이 구현 → 캡처 검증. 자료가 없으면 미확보라고 표시.
- 기존 게임 규칙·위치·워프·멀티플레이는 실제 데이터로 유지하고 가짜 플레이 결과·숨겨진 샘플 NPC·자동 결과를 섞지 말 것.

### P2. 무료 권한 서버와 실제 운영 내구성

- Render 절전·리셋, 정원 원자성, 유령 좌석, 메시지 중복·순서, 재접속 및 429/503을 실기기로 검증. 무료 가격/쿼터/약관은 배포 전 갱신 확인.
- Cloudflare Durable Objects는 설계만 있고 **실서비스 구축 완료라고 말하지 말 것**. 권한 서버는 항상 방마다 하나, 다중 클라우드 임의 이중 쓰기 금지.
- 이 과제 때문에 원작 월드맵/채팅/주잔의 거대한 미완성 외형 작업을 무기한 미루지 말 것.

## 7. 핵심 실제 코드/검사 경로

### 코드

| 파일 | 목적 |
| --- | --- |
| `apps/4leaf/rog/index.html` | 모든 CSS/JS 로딩 순서. 신규 규칙은 기존 `!important` 규칙과 순서 충돌 주의 |
| `apps/4leaf/rog/game.js` | 주잔 실제 경기 상태/턴/배틀/타일/아바타 렌더 |
| `apps/4leaf/rog/board-camera.js` | 진짜 DMP 월드/카메라/뷰포트/미니맵 이동 |
| `apps/4leaf/rog/dice-native-tis-alpha.js` | 원본 RGBA 보존, 필요할 때만 외곽 배경 제거 |
| `apps/4leaf/rog/dice-native-tis-depth.css`, `dice-native-tis-orientation.css` | 145×97 플랫폼·상하 방향·중첩 표현 |
| `apps/4leaf/rog/dice-native-pawn-dmp-depth.css` | Registry 배우와 DMP 발판의 z-깊이 |
| `apps/4leaf/rog/dice-source-dmp-terrain-explorer.js/.css` | 최신 #91 실제 DMP/워프 카메라 점검, 경기 상태 불변 |
| `apps/4leaf/rog/social-chat.js`, `world-social.css` | 월드·북남 채팅 방·좌석·참여자/화면 |
| `apps/4leaf/rog/world-map.js`, `knighttown-native.js`, `street-world.js` | 월드맵/레코르다블/거리 |
| `apps/4leaf/rog/central-client.js`, `server/central.cjs`, `network.js` | 실제 중앙 채팅/게임 P2P |
| `apps/4leaf/rog/sw.js` | 오프라인 파일과 서비스 워커 리비전 (현재 v56) |

### 필수 E2E

- 말판/캐릭터/카메라: `tests/dice-native-tis-depth.cjs`, `dice-native-tis-alpha.cjs`, `dice-native-orientation-manual.cjs`, `dice-native-pawn-dmp-depth.cjs`, `dice-dmp-full-camera.cjs`, `dice-native-minimap-navigation.cjs`, `dice-source-dmp-terrain-explorer.cjs`.
- 실제 경기·전투·주사위: `tests/board-layout.cjs`, `dice-battle-podium.cjs`, `dice-native-battle-dice.cjs`, `dice-ai-resume-guard.cjs`, `dice-native-frame.cjs`, `archive-coverage.cjs` (25개 원본 맵).
- 하이아칸/월드/캐릭터: `tests/world-chat.cjs`, `world-map-moon.cjs`, `chatroom-furniture-registration.cjs`, `chat-native-scrollbar.cjs`, `registry-native-avatar-dialog.cjs`, `knighttown-original.cjs`.
- 통신·오프라인: `tests/social-network.cjs` (실제 WebRTC DataChannel), `tests/central-browser.cjs` (실제 중앙 서버 두 브라우저), `tests/native-offline-cache.cjs`.
- CI: `.github/workflows/rog-world-chat.yml`, `rog-archive-coverage.yml`, `rog-central-chat.yml`, `rog-chat-live.yml` (Pages 배포 후 공개 URL 바이트 단위 확인 + Chromium).

### 로컬 빠른 실행 예시

`bash
# 저장소 루트에서, Node 22 및 Chromium/Playwright 설치
npm install --no-save playwright
npx playwright install chromium
python3 -m http.server 8765 --bind 127.0.0.1 --directory apps/4leaf/rog
# 별도 터미널에서:
node apps/4leaf/rog/tests/world-chat.cjs
node apps/4leaf/rog/tests/dice-native-tis-depth.cjs
node apps/4leaf/rog/tests/dice-source-dmp-terrain-explorer.cjs
node apps/4leaf/rog/tests/dice-native-pawn-dmp-depth.cjs
node apps/4leaf/rog/tests/dice-native-minimap-navigation.cjs
`

중앙 서버 통합 테스트는 `rog-central-chat.yml`의 Node 서버 포트/테스트 순서를 따른다. `file://`에서는 Chromium의 Canvas CORS 규칙 때문에 PNG 알파값 직접 읽기가 제한될 수 있다. **진짜 공개 HTTP(S) 또는 로컬 HTTP**에서 원본 파일 픽셀을 검증해야 하며, `file://` fallback은 지원하되 원본 알파가 복원됐다고 꾸미지 말 것.

## 8. 다음 대화에서 실제로 해야 할 순서

1. GitHub `main` SHA/열린 PR/각 CI/Pages 공개 사이트를 **다시 조회**. 개인 기억이나 이 문서 날짜만으로 최신이라고 주장하지 않는다.
2. 가장 큰 외형 오차를 실원본 스크린샷과 **동일 장면/뷰포트**로 측정해 P0 문제 하나를 구체화. 당장 사용자의 타일 겹침과 8등신 캐릭터 이슈부터 재현/원인 분리. 월드맵·북남 채팅 큰 차이는 최우선 트랙으로 유지.
3. 추출 자산을 열어 **원래 장면/크기/투명/상태프레임/사용 위치**를 확인한다. 임의 이미지 검색 결과, 사진 땜질, 오분류 금지.
4. 최신 `main`에서 작업 브랜치를 만들고 **실제 화면·조작 코드**를 수정. 원본 규칙/참여자/선택·턴/중앙 서버 훼손 금지.
5. 필요시 새 Playwright E2E 추가: **픽셀 크기/실제 DOM/스크린샷 정량 비교/사용자 클릭·턴/모바일·오프라인·WebRTC**. 기존 테스트 가정이 잘못됐으면 테스트 자체도 원본 근거에 맞춰 수정.
6. `sw.js` PWA 버전/자산 리스트 갱신. 관련 GitHub Actions `paths` 트리거 및 공개 Pages byte-match 확인. **CI success → PR 병합 → Pages deploy success → 새 커밋 공개 URL Chromium success**까지 검증.
7. 실제 수정 파일, PR/머지 SHA, CI 링크, before/after 캡처, VERIFIED/INFERRED/UNVERIFIED 분리해서 보고. **성공하지 않은 배포/검사를 성공이라고 말하지 말고**, 고쳐서 끝낸다.
8. 같은 반복 지시에 대해 계획/상황 보고만 하고 종료하지 말고 다른 실제 P0 외형 차이를 연속해서 해결한다.

## 9. 다음 담당자에게 그대로 전달할 재개 지시문

> **4LEAF 원작 복원 개발을 지금 이어라.** `koith/browser-app-lab` 저장소 `apps/4leaf/rog/`의 `docs/RESTORATION_HANDOFF_2026-10-17.md`를 읽은 뒤 최신 `main`, 열린 PR, 공개 Pages와 Chromium CI를 검증하라. 사용자가 원하는 것은 원작과 거의 같은 화면과 실제 조작이며, 이미 여러 차례 **주잔 육각판의 부정확한 중첩과 창세기전 8등신 캐릭터 부재**, 북남 하이아칸/월드맵의 큰 외형 차이를 지적했다. 원본 `board.jpg`/`battle.jpg`/`chat_ref.jpg`/`sky.jpg`와 145×97 TIS, 실제 DMP, 75×141 Registry 그림을 똑바로 구분하고, 사진/코드/실제 게임을 정밀 비교해 **실제 코드를 교정하라**. MVE/3D 모델·높이 정보가 없으면 수집·디코딩 연구를 수행하고 없는 정보를 가짜로 채우지 말 것. 북남 채팅 좌석 순간이동, 실제 방/사용자, 25맵/턴/워프/중앙서버/WebRTC/오프라인을 보존한다. **반드시 코드 변경 → Chromium/원작 비교 → PR 병합 → Pages 배포 → 공개 브라우저 QA**를 반복하고, 원작 미완성을 완성이라고 보고하지 마라.

**최종 판정: 미완성.** 최신 `b32d742`에 구현된 실제 소스기반 DMP 카메라·탐색과 UI 진척은 보존하되, 2003~2004년 원작의 3D 세계·8등신 캐릭터·실제 복원 지형·애니메이션과 역사적 ChatTown 공간은 여전히 근본적인 차이가 남는다.
