# 2004 원작 상설 채팅방 `room4` 원본 배경·가구 위치 검증

검증일: 2026-10-19 KST. **이 검증은 실제 사용자의 접속 인원을 조작하거나 JPEG를 게임 배경으로 붙여넣는 방식이 아니다.**

## 원작의 동일 실내를 찾아낸 근거

2004년 두 원본 캡처 [chat.jpg](../../assets/chat.jpg)·[chat_ref.jpg](../../assets/chat_ref.jpg)는 아치형 액자, 왼쪽 경사 목재 바닥, 상단 오른쪽 창가, 중앙 하단 탁자가 같은 목재 실내이다. 복구된 2002 클라이언트의 `original/ChatRoom/room4.png`가 바로 이 방의 진짜 794×528 배경 PNG다.

- 사진 2장 각각의 픽셀 데이터와 진짜 `ChatRoom/room4t.png`의 **115×103 원본 알파 탁자** 1,011개 소스 표본 픽셀을 비교했다.
- 원본 `chat_ref.jpg`에서 최적 탁자 위치 **(427,425)**, 1:1 배율. `chat.jpg`에서도 **(427,425)**, 1:1 배율. 원본의 112% 확대 등은 오차가 더 크다.
- 실제 게임의 전경 탁자는 **left=427, top=425, width=115, height=103**, bitmap=115×103, painter z=80이다. 상호 정렬 **0px 오차**.
- 원본 `room4.png`의 배경은 게임 엔진에서 독립된 방 맵으로 로드한다. 원본 캡처 JPEG는 **실제 게임에 사용하지 않는다**.
- 방 컨테이너 794×528, 채팅 오버레이 x=16 y=0 w=407, 실제 참가자 목록 x=623 y=9, EXIT x=728 y=503. 게임 내 소스 크기 유지.
- 살아 있는 `Registry` 캐릭터, 채팅, 참가자 목록, 의자 앞뒤 가림, 링 메뉴, 원본 액션을 실제 별도 DOM/캔버스 객체로 처리한다.

## 실제 브라우저 검증

- `tests/chatroom-furniture-registration.cjs`: [Chromium World + Chat 통합 검사 성공](https://github.com/koith/browser-app-lab/actions/runs/39178101196), 정확히 일치하는 두 원작 스크린샷과 탁자 픽셀 정합, 이름표 baseline 512.16, top 329.16, 글자 색 `rgb(86, 107, 198)`.
- `tests/visual-fourleaf-room-source.cjs`: 원본 room4 배경, 창·채팅·참가자 패널·퇴장 버튼이 모두 실제 794×528 좌표에 있는지 검사한다.
- `tests/world-chat.cjs`: 실제 입장·좌석 이동·본인 아바타 클릭/채팅, 원본 2004 툴바/멀티 이용자 인터랙션을 회귀 검사한다.
- 배포: [4LEAF GitHub Pages 앱](https://koith.github.io/browser-app-lab/apps/4leaf/rog/)의 `main`에 원본 실내 PNG, 렌더링 모듈, 검사 코드 게시 (검증 당시 기준 배포 [eaf6b274](https://github.com/koith/browser-app-lab/commit/eaf6b274ad9bacb32c443f20baf8646f0f7486b0) 포함).

## 완료 범위 및 남은 작업

**CHT-01 — 원작 동일 방 배경·가구·프레임 앵커 대응**은 검증 완료. 원작 캡처의 10~11명 사용자를 가짜 NPC로 채우지 않으며, 실제 1명 접속 시 1명만 표시하는 것이 정상이다.

**CHT-02/03/04/05, P0-CHAT, EVID-01/02는 별도 미완료**: 검정 대화창 글꼴/스크롤, 실제 다인 접속 목록, 표정·좌석 전체 상태, 모든 방의 가구 가림, 본인이 찍은 실기기 A/B 스크린샷 추가 검증은 계속 필요하다. 배경 픽셀 일치가 곧 채팅 전체 복원 완료는 아니다.
