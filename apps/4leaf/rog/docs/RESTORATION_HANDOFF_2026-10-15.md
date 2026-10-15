# 4LEAF 웹앱 원작 복원 — 개발 인수인계서 (2026-10-15)

> **현재 완료 아님.** 테스트 성공/배포 성공은 원작 외형·플레이·네트워크의 정밀 복원 완료를 의미하지 않는다. 이 문서는 기존 작업이 끊긴 뒤에도 자료·코드·요구 조건·남은 업무를 되찾을 수 있도록 유지하는 재개 기준점이다.

## 1. 저장소 및 검증된 상태

- 소스: https://github.com/koith/browser-app-lab
- 배포: https://koith.github.io/browser-app-lab/apps/4leaf/rog/
- 프로젝트 코드: `apps/4leaf/rog/`
- **마지막 확인 main:** `20ef39c3485af37fa8239c36a1cf0fb8b85e98df` — PR #63 원작 WorldMap 만월·검은 배경.
- 위 커밋의 GitHub Pages 배포 성공: https://github.com/koith/browser-app-lab/actions/runs/38709066189
- 위 커밋의 **공개 URL Chromium** 검증 성공: https://github.com/koith/browser-app-lab/actions/runs/38709150398
- 월드맵/채팅·WebRTC·중앙 서버·주잔 스모크·오프라인 워크플로도 같은 SHA에서 success로 확인.
- 문서 작성 시점 열린 PR 0개. **다음 대화에서 반드시 다시 확인**해야 한다.
- 사용자 요구: 외형·동작이 원작과 아직 한참 다르다. 채팅으로 작업을 대체하지 말고 **실제 구현→Chromium 검사→병합→Pages 공개 검사**까지 처리한다. 가장 중요한 우선순위는 **월드맵과 북·남 하이아칸 채팅**이며, 주잔은 차순위.

## 2. 원작 복원 불변 원칙

1. **진짜 원본 PNG/TIS/DMP/실행 화면 우선.** 전체 스크린샷을 붙이고 보이지 않는 클릭 영역을 얹는 눈속임 금지. 실제 파츠와 이벤트/게임 상태를 렌더링한다.
2. 원본에서 확인한 것은 **VERIFIED**, 플레이 사진을 참고해 CSS/Canvas로 만든 것은 **INFERRED**. 단상·달·카메라 등의 추론을 원본 코드/3D 모델 복구로 과장하지 않는다.
3. 채팅방 **자리 이동은 즉시 순간이동**, 좌표 선형 보간 금지.
4. 하이아칸 ChatTown 화면과 주잔 `Region/regionback.png`의 `TOWN SELECT` 채널 선택은 서로 다른 기능이다.
5. 원본에 없는 공용 채팅방·사용자·NPC·접속 인원·게임방 상태를 생성해 실제처럼 표시하지 않는다. 방장·정원·메시지·인원은 실제 데이터로 동기화.
6. 기존 월드맵/켈티카/매직카덴/주잔/채팅/입체 TIS/주사위·전투/중앙 서버·WebRTC의 작동을 보존한다.
7. 무료 호스팅 원칙 유지. 유료 자동 전환·단일 방 이중 authoritative writer 금지. 오류/503/429·유휴절전/데이터 소실은 처리/안내한다.
8. 병렬 PR/브랜치와 메인 변경 충돌에 주의. **최신 main에서 시작하고 다른 복원 작업을 덮어쓰지 말 것.**

## 3. 원작 소스와 실제 사진

가장 중요한 참고 문서: **[original-experience-evidence.md](./original-experience-evidence.md)**. 1~38 이상의 누적 근거가 있다(일부 번호 중복; 제목/리소스명으로 검색).

| 파일 | 출처/의미 |
|---|---|
| `original/WorldMap/` | 실제 지역 월드맵 PNG/각 지역 4프레임 스프라이트; 배경 약 796×528 |
| `original/ChatTown/` | 북/남 하이아칸 794×404 원본 지형·지역 선택 |
| `original/ChatRoom/room*.png` | 6종 794×528 방 실내 |
| `original/ChatRoom/chatbaredit.png` / `userlist.png` | 원본 407×21 채팅 입력 / 150×38 참가자 타이틀 |
| `original/ChatRoom/ringbtn.png` / `scrollbar.png` | 원본 104×330 캐릭터 메뉴 / 52×40 채팅 스크롤 버튼 |
| `original/IMG/title.png` / `chatwnd.png` / `minimap.png` | 주잔 800×600 프레임 / 406×152 채팅 / 172×152 미니맵 |
| `original/IMG/bgtile.png` | **주잔 경기 원본 숲/절벽/중앙 건물 배경 725×485**. 채팅 마을 자산이라고 오분류했던 잘못은 #55에서 수정 |
| `original/IMG/selector.png` / `abilitybar.png` | 원본 222×152 게임 아이콘 / 92×64 ABILITY 버튼 |
| `original/Tiles/*.png` | 원본 145×97 TIS 입체 발판 |
| `original/Registry/sava*.png` | 원본 75×141 캐릭터 PNG. **알파가 이미 투명**하므로 중복 크로마키 처리 불필요 |
| `original/CardData/chm_*.png` | 진짜 체스맨 얼굴 카드 |
| `original/maps.js`, `tiles.js`, `chessmen.js` | 추출/변환한 원본 경로·발판 이벤트·체스맨 데이터 |
| `../assets/board.jpg`, `battle.jpg`, `sky.jpg`, `chat_ref.jpg`, `chat.jpg` | 당시 실제 플레이 스크린샷. `../assets/previews/*.b64.txt` 미리보기도 존재 |

**중대한 교훈:** #55 이전에 실제 주잔 배경 `IMG/bgtile.png`를 잘못 분류해 없앴던 적이 있다. PR #57의 합성 숲은 원본을 가리므로 **닫힘/미병합**. 실제 원본 위에 또 가짜 숲을 덮지 말 것.

## 4. 주요 코드 지도

- `index.html`: 화면/원본 이미지·CSS/JS 로드. **CSS 로드 순서 중요**.
- `game.js`: 실제 주잔 맵/턴/주사위/아이템/어빌리티/전투/저장·복귀.
- `world-map.js`, `world-map-source-moon.css`: 원본 6개 월드 지역, 원작 사진 기반 달 레이어.
- `street-world.js`: 켈티카 거리와 실제 건물 파츠.
- `social-chat.js`, `world-social.css`: 북남 하이아칸 방/캐릭터/접속자/말풍선/실시간 메시지.
- `chatroom-native-panels.js/.css`, `chatroom-native-ringbtn.css`, `chatroom-native-scrollbar.js/.css`: 실제 채팅 DOM을 방 안에 위치시키는 레이아웃, 원본 캐릭터 메뉴·원본 채팅 스크롤 UI.
- `lobby-ui.js`, `dice-native-stage.js`: **주잔 전용** 채널/방/준비실.
- `dice-native-client-frame.css/.js`: 800×600 주잔 크기/실제 채팅 입력·미니맵 캔버스.
- `dice-native-chessmen-hud.css`, `dice-original-selector.css`: 게임 실제 2×2 파티와 원본 선택 아이콘.
- `dice-native-tis-clean.css`, `board-camera.js`: 실제 원본 발판·카메라.
- `dice-native-battle-podium.css`, `dice-native-player-portraits.css`: 원작 사진 참고 **추정 2.5D 전투 단상** 및 진짜 Registry 캐릭터.
- `shop-native.js` 및 `cardshop-*`: 매직카덴.
- `central-client.js`: Node/Render 중앙 ChatRoom API와 세션.
- `network.js`: 별도의 실제 WebRTC 경기 연결.
- `sw.js`: PWA 리비전 및 오프라인 캐시.

## 5. 완료된 구현과 큰 미완료 사항

**구현·테스트 확인:** 원본 월드맵 6개 지역 클릭/북남 채팅 진입, 원본 방 배경 6종/실제 방 생성·입퇴장/참여자 목록/좌석 순간이동/원본 입력·말풍선/캐릭터 메뉴·스크롤바, 켈티카 거리/매직카덴 UI, 주잔 800×600 레이아웃/25개 원본 DMP 맵/진짜 TIS/숲/2×2 카드/실제 전투·아이템, 2브라우저 WebRTC, 중앙 ChatRoom 테스트, Pages 배포 및 공개 브라우저 QA.

**P0 — 월드맵/ChatTown/ChatRoom (사용자 우선순위):** 원본 `sky.jpg` / `chat_ref.jpg` / `chat.jpg` 대비 794×528 공통 좌표계 스크린샷 정밀 비교. 창틀/캐릭터 크기·모션/방 선택·가구 전경 레이어/좌석 표시/북·남 구역 선택 및 음향 차이를 **실제 UI 코드를 바꿔** 교정. 검증되지 않은 채팅방 수와 참석자 데이터는 가짜로 만들지 말 것.

**P1 — 원작 주잔 3D:** 지형 고저차, 3D 메시/조명/카메라·모델 프레임·공격 연출, 로비·경기 UI의 원본 프레임 상태 등은 상당 부분 미복원. CSS 전투 단상은 원작 3D 모델이 아니라 **추론적 2.5D**. 원본 725×485 숲/실제 맵 경로를 보존하며 원본 모델 데이터를 더 확보하고 구현.

**P2 — 실제 무료 서버 권한/유지:** 중앙 API 현재 설정 `https://fourleaf-central-chat-free.onrender.com`; 정적 웹앱은 GitHub Pages. Node 중앙 서버와 WebRTC 검사가 돌아도 실제 서버 24시간 가용성·방 영구 보존·동시 사용자 한도는 보장되지 않음. [무료 운영 검토](./free-multicloud-architecture.md)와 [권장 멀티클라우드 설계](./recommended-multicloud-design.md) 참고. Worker + SQLite Durable Object는 **목표 설계/미배포**. 무분별한 failover 및 방 이중쓰기 금지.

## 6. 재개 전 핵심 PR

- [#55](https://github.com/koith/browser-app-lab/pull/55) 주잔 원본 숲 재복원.
- [#57](https://github.com/koith/browser-app-lab/pull/57) **미병합/폐기** 추정 숲 레이어.
- [#60](https://github.com/koith/browser-app-lab/pull/60) 실제 전투 DOM 위 추정 2.5D 단상.
- [#61](https://github.com/koith/browser-app-lab/pull/61) ChatRoom 원본 ringbtn 메뉴·실제 좌석 이동.
- [#62](https://github.com/koith/browser-app-lab/pull/62) 원본 ChatRoom 스크롤바/실제 메시지 연동.
- [#63](https://github.com/koith/browser-app-lab/pull/63) 원작 월드맵 만월, 가짜 캡션 제거.

그 이전 #39~#56의 UI·기능·테스트 근거는 [증거 대장](./original-experience-evidence.md)에서 찾아볼 것. **현재 UI를 원작 완성이라고 선언하지 말 것.**

## 7. 매번 실제로 진행할 순서

1. 최신 `main`/열린 PR/실제 Pages 배포/최근 CI를 조회.
2. 원본 PNG/실제 사진/근거 대장으로 **화면 간격·좌표·입력**을 확인; 변경할 큰 차이를 선정.
3. 충돌 없는 작업 브랜치에서 실제 CSS/DOM/게임 로직 수정. 정적 전체 스크린샷 덮기 금지.
4. Playwright/Chromium으로 원본 자산·상태·실제 클릭/실사용자·즉시 이동·모바일과 네트워크 회귀 테스트 수행.
5. GitHub Actions 경로 트리거와 PWA 캐시 갱신. PR 병합 이후 Pages 배포 확인. **실제 공개 URL Chromium 테스트도 반드시 성공**해야 결과 보고.
6. 변경 파일·실제 캡처·검증 링크·원작과 남은 차이를 분명하게 보고. 검증 실패나 서버 장애 시 회피하지 말고 원인 수정.

주요 검사 위치: `tests/world-chat.cjs`, `world-map-moon.cjs`, `chat-native-scrollbar.cjs`, `dice-native-frame.cjs`, `archive-coverage.cjs`, `dice-battle-podium.cjs`, `dice-chessmen-hud.cjs`, `network.cjs`. 공개 배포 검사 `.github/workflows/rog-chat-live.yml`, 일반 회귀 `rog-world-chat.yml` 및 `rog-archive-coverage.yml` 참고.

## 8. 다음 담당자의 첫 실제 작업

**월드맵/북남 하이아칸 채팅부터** 최신 공개 화면을 Chromium 캡처하고, 원작 `sky.jpg`, `chat_ref.jpg`, `chat.jpg`와 같은 크기로 나란히 비교해 가장 큰 공간/캐릭터/방 레이어 차이 **한 건을 실제 구현+테스트+배포로 끝낸다**. 원본에 이미 있는 그림을 잘못 분류하거나 이미 끝난 작은 아이콘 수정만 반복하지 않는다. 그다음 큰 차이를 지속 해결한다.

**종결 판단:** 원본 플레이 화면 및 조작과 아직 현저한 차이가 있으므로 원작 복원은 **진행 중/미완성**이다.
