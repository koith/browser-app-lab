# 4LEAF 원작 플레이 경험 — 증거 대장 (2026-10-14)

목적: 원본 클라이언트의 실행 데이터(DMP/TIS/CHR/PAK 등)와 당시 발표·개발자 문답·이용자 기록을 교차 검증한다. **발표 당시의 예정 기능을 실제 출시 기능으로 오인하지 않는다.** 2018년 모바일 리메이크는 2001~2003 원작과 별도 게임이다.

## 증거 수준
- VERIFIED-ARCHIVE: 저장소에 추출된 원본 파일·구조로 직접 확인되는 사실. 동작 의미는 별도 검증.
- VERIFIED-CONTEMPORARY: 서비스 당시 기사·개발진 기록에 명시된 사실. 당시 실제 서비스 중인지 예정인지 구별.
- RETROSPECTIVE: 이후 인터뷰·회고 내용. 동시대 자료와 대조 필요.
- INFERRED: 다수 자료의 합리적 해석이나 아직 원본 실행으로 확인되지 않은 사항.
- UNVERIFIED: 아직 충분한 근거가 없는 설명·UI 사양. 임의의 원작 사실로 포장하지 말 것.

## 1. 원본 파일에서 확인한 구조

- `original/maps.js`: DMP 맵의 타일 격자 (x,y), 방향·이벤트/워프 관련 필드. 맵별 경로가 다르므로 고정 나선형 타일 위치로 대체 금지. VERIFIED-ARCHIVE.
- `original/tiles.js`: 맵별 발판 이벤트 유형 및 일부 속성·워프 그룹. VERIFIED-ARCHIVE.
- `original/Tiles/art.js`: 원본 TIS 이미지 145×97, 효과 종류와 타일 리소스 대응. 원본 픽셀의 그림 방향과 전체 렌더러 투영/카메라 방향을 구분해야 함. VERIFIED-ARCHIVE.
- `original/WorldMap/`, `ChatTown/`, `ChatRoom/`, `MainStreet/`, `Registry/`: 화면과 아바타 그래픽. 그래픽 존재가 모든 상호작용 규칙의 입증은 아님. VERIFIED-ARCHIVE.
- `world-map.js`, `social-chat.js`: 현재 웹 재구현. 원작 소스가 아니므로 여기에 적힌 가정은 원작 증거로 쓰지 말 것.

## 2. 동시대/회고 자료에서 복원할 동작

| 화면/시스템 | 확인된 내용 | 증거 상태 | 검증 및 구현 지침 | 출처 |
| --- | --- | --- | --- | --- |
| 전체 포리프 | 채팅을 기본으로 한 커뮤니티 서비스 | VERIFIED-CONTEMPORARY (2002년 개발자 발언) | 월드맵→채팅타운→채팅방 입장 경험을 핵심 경로로 유지 | https://4leafmemorial.tistory.com/category/%EC%9E%90%EB%A3%8C/4LEAF%20%EC%84%B8%EB%AF%B8%EB%82%98 |
| 채팅창 | 0.9 채팅창이 이전보다 좁다는 지적, 위치/크기 조절은 **향후 제공 예정**이라는 답변 | VERIFIED-CONTEMPORARY (발언/계획). 실제 출시 여부 UNVERIFIED | 버전을 고정하고 0.9에 없는 기능을 이미 있던 것으로 취급 금지 | 위 세미나 (이수구 개발자 대화) |
| 채팅실 | 디자인 개편에서 공간을 넓혔다는 설명, 마법/모션 효과는 **개발/예정** 언급 | VERIFIED-CONTEMPORARY (발언/계획) | 캐릭터 좌표/이펙트의 원작 버전별 적용 여부 추가 검증 | 위 세미나 |
| 2인 채팅방 | 운영자가 만든 **2인 전용 채팅방** 입장 이벤트가 실제 2002년 운영 | VERIFIED-CONTEMPORARY (행사 기사) | 2인 정원을 지원하고 입장 시 정원 초과를 차단하는 설계 검토. 모든 방이 2인실이었다고 단정 금지 | https://game.donga.com/13172/ |
| 세미나실 | 일반 채팅방보다 큰 회의 공간, 기사단에 한시 대여한 이벤트 존재 | VERIFIED-CONTEMPORARY (2003년 공지) | 일반실/세미나실을 별도 공간 유형으로 취급; 유료·대여정책을 영구 상설 규칙으로 일반화 금지 | https://4leafmemorial.tistory.com/939 |
| 월드/재화 | GP, FP 별도 개념, FP는 명성·레벨과 관련 | VERIFIED-CONTEMPORARY (세미나) | 현재 GP와 FP 혼동 금지, 보상 지급과 획득 규칙은 버전별 증거 추가 확보 | https://4leafmemorial.tistory.com/category/%EC%9E%90%EB%A3%8C/4LEAF%20%EC%84%B8%EB%AF%B8%EB%82%98 |
| 카드/체스맨 | 실물 창세기전 카드 시리얼 인증 후 4LEAF 계정에 카드 지급, 주잔에서 체스맨 사용 | VERIFIED-CONTEMPORARY (2003년 발표) | 계정 소유 체스맨과 게임 참가 체스맨 구분, 중복 등록 금지 등 검토 | https://game.donga.com/14258/ |
| 원작 게임 규칙 | 고유 주사위 능력치 기반 이동·전투. 후속 모바일판은 캐릭터 성장 추가 | RETROSPECTIVE (2018년 원작 제작진 인터뷰) | 모바일 성장·시나리오 시스템을 역사적 PC 버전으로 역투영 금지 | https://www.dailyesports.com/view.php?ud=2018032215382646897_26 |
| 당시 기사단전 | 실제 1P/3P/5P 대 2P/4P/6P 좌석 사례, 각 체스맨 공격/방어/지력 포지션 | VERIFIED-CONTEMPORARY (당시 경기기록의 보존본) | 팀 사이드 패널 및 좌석 색인과 파티 역할 검증 | https://4leafmemorial.tistory.com/category/%EC%B6%94%EC%96%B5/%ED%8C%AC%EC%82%AC%EC%9D%B4%ED%8A%B8%20%EA%B8%B0%EC%82%AC |
| 원작 매너룰 | 방제/입장 전 선언에 따른 이용자 간 워프 매너 규칙 논쟁 | VERIFIED-CONTEMPORARY (개발자 세미나의 유저 발언) | **커뮤니티 관습**과 게임 엔진의 강제 규칙 구별 | https://4leafmemorial.tistory.com/category/%EC%9E%90%EB%A3%8C/4LEAF%20%EC%84%B8%EB%AF%B8%EB%82%98 |
| 옛 화면 비교 | 켈티카/상점/보드게임 화면이 기록된 이용자 추억 게시글 | RETROSPECTIVE (화면 이미지 출처/촬영시점 검증 필요) | 스크린샷에서 UI 픽셀·창 위치를 추출하고 원본 버전 확인. 화면 전체 붙여넣기 금지 | https://theqoo.net/square/3445314686 |
| 에뮬레이터 | Rust 기반 4Leaf Browser 에뮬레이터 실험 프로젝트 존재, 내장 서버 패킷 캡처 설명 | VERIFIED (저장소 README), **완제품 아님** | 클라이언트 실행/패킷/상태 전이 재현 가능성 검토. 원본 동작 완성된 것으로 간주 금지 | https://github.com/catfoot-dev/emul-4leaf |

## 3. 지금 구현과의 확인된 차이·위험

1. [2026-10-14 수정 완료] `presetRooms()`가 원본 *배경 템플릿* 6종을 가짜 서버 공개방 6개로 표시하던 오류를 제거했다. 현재 방 목록에는 생성되어 공유된 방만 나타난다. **다만 원작 서버의 진짜 방 검색·정렬·페이지 규칙은 여전히 UNVERIFIED.**
2. `social-chat.js`는 동일 출처 탭과 수동 WebRTC 직결에 의존함. 원작 서버 기반 로비의 방 검색/입장/정원 동작과 동일하지 않음. 실제 멀티유저 백엔드는 별도 설계와 검증 필요.
3. `world-map.js` 지역 좌표와 클릭 경계는 수작업으로 설정. 픽셀 일치 검증 전까진 VERIFIED-ARCHIVE 위치라고 부를 수 없음.
4. `game.js`는 DMP 좌표를 자체 월드 투영으로 변환. 145×97 원본 발판과 70×47 화면 표현의 비율은 확인했으나, 원작 렌더링 카메라 및 이웃 타일 겹침/가림 순서는 여전히 UNVERIFIED.
5. 원본 역사적 시점에 따라 0.9~1.0의 UI와 채팅 기능이 달라질 수 있음. 우선 표적 클라이언트 버전과 원본 설치 리소스 버전을 고정할 것.

## 4. 이후 검증 순서

1. 2001~2003 시기별 원작 화면을 보존하고 출처/일자/버전/해상도/각 버튼 상태를 기록.
2. 해당 UI의 동일 진입 경로를 현재 Chromium에서 캡처하고 원본과 창 크기, 좌표, 도트, 화면 전환, 대화창을 분리 비교.
3. `original/` 원본 리소스의 이미지 차원·프레임 순서·알파 키, `maps.js`의 방향코드 등 역분석.
4. 에뮬레이터 패킷/클라이언트 파일로 방 목록·입장·좌석·메시지·이동 프로토콜을 확인. 예정 기능 vs 출시 기능 구분.
5. 테스트는 단순 렌더 성공이 아니라 각 원작 동작의 상태 전이와 UI를 검증. 테스트가 제공하지 않는 지표를 임의의 시각적 유사도 %로 주장하지 않기.

## 관련 동영상 단서
- https://www.youtube.com/watch?v=nEEuY5iMDSQ — 이용자 게시글이 참조한 포리프 영상. 영상 프레임/설명은 아직 별도 검증 필요.

## 5. 채팅방 실제 화면의 레이어와 자리 구조 — 2026-10-14 대조

**같은 버전에서 찍힌 자료라고 가정하지 않는다.** 2000년 KBench 초기 채팅방 스크린샷과 현재 확보한 4LEAF 클라이언트의 ChatRoom.pak 아카이브를 함께 비교했다.

- 원작 사용 당시 사진: https://kbench.com/?q=node%2F4502 (2000-05-17), 별도 이미지 https://images.kbench.com/korean/topnews/2000_05/cat.jpg — 대화실 34번, 독립 상단 도구 모음, 실내 책장·탁자, 탁자 앞/뒤 네 명의 아바타, 머리 위 이름/말풍선, 아래쪽 채팅 로그. VERIFIED-CONTEMPORARY (촬영 시기의 구버전).
- 복원된 원본 아카이브 ChatRoom/room3.png 는 벽·가구·바닥 **배경**이다. ChatRoom/room3t.png 는 별도 녹색 탁자 **전경**이며, 원본 파일 가장자리에는 게임 엔진용 밝은 빨강 chroma-key 색상이 남는다. 동일하게 room4t.png 및 room5t.png 도 독립 탁자 전경이다. VERIFIED-ARCHIVE.
- Registry/sava00.png 원본 캐릭터 이미지 크기 75×141 (투명 부분 포함). 크기가 임의로 61×113으로 축소돼 있으면 원본 사진 대비 비례가 달라진다. VERIFIED-ARCHIVE.
- **필요한 렌더링 순서**: 배경 → 뒷좌석 캐릭터 → 투명색 제거된 전경 탁자 → 앞좌석 캐릭터 → 말풍선·이름 등의 화면 UI. 2000년 스크린샷과 추출된 전경 PNG를 교차 분석한 INFERRED 구현 지침이다.
- `social-chat.js`의 `ROOM_LAYOUTS`은 실제 추출 그래픽 위에서 위치를 잡은 **방별 근사 슬롯 좌표**다. 정확한 원작 픽셀 좌표 또는 슬롯 수가 역해독되었다는 주장이 아니다. INFERRED.
- 채팅방에서 클릭 후 캐릭터가 즉시 자리에 들어갔다는 피드백은 실제 원작 사용 경험에 관한 직접 증언이다. 선형 보간이 아닌 자리 즉시 변경 동작은 복원해야 한다. USER-REPORTED.
- `world-chat.cjs` 브라우저 QA는 원본 책상 리소스가 로드되는지, 빨간 chroma-key가 투명한지, 좌석 앞뒤 z-index가 맞는지, 재배치에 보행 애니메이션이 없는지 확인한다. 이 검사는 **기능 회귀**를 검증하지만 2000년 원작 화면과의 픽셀 단위 동일성을 뜻하지 않는다.

다음 조사 과제: 초기(2000) 화면과 추출 설치 파일의 버전 시차 확인, 실내 그래픽별 정확한 전경 축척과 좌석 앵커를 원본 실행 상태 또는 유효한 스크린샷 시퀀스에서 복원, 이름·말풍선·상단 창 UI의 좌표 비교.


## 6. 2026-10-14 채팅방 동작 교정 및 남은 검증

- \`ChatRoom/room0.png\`는 실제 원본의 독립적인 배경(0번)이다. JavaScript에서 \`Number('0')||2\`로 변환해 2번 배경으로 오염하던 버그를 없앴다. 현재 0~5번 배경 원본을 각각 선택 가능. VERIFIED-ARCHIVE + 코드 회귀 테스트.
- 2002년 2인 전용 채팅방 운영 사례에 따라 선택 가능한 2인 정원을 제공하며, 연결된 사용자 수를 기준으로 추가 입장을 막는다. 4·8·12인 수치는 복원 편의상의 선택지로서 **원작의 정확한 선택 메뉴로 입증된 수치가 아니다.** VERIFIED-CONTEMPORARY (2인 사례) + INFERRED (일반 방 정원).
- 방 소유자 판별을 누구나 같은 값일 수 있는 닉네임이 아니라 탭별 지속 식별자로 바꿨다. 동일 닉네임인 다른 탭에 방 폐쇄 권한을 노출하지 않는다. 중앙 인증 서버의 권한 검사와 동등하지 않다.
- 매직카덴/주사위/도움말로 이동한 사용자가 이전 방의 접속자로 계속 집계되는 문제를 해소했다. 방 복귀 시 현재 인원 표시를 재동기화한다.
- 현행 브라우저간 연결은 BroadcastChannel·동일 브라우저 저장소·수동 WebRTC 한정. **임의의 서로 다른 기기가 자동으로 동일한 공개 채팅방 목록을 공유하는 중앙 로비는 아니다.** 중앙 서버 기반 실사용 인원 및 정원 경쟁 상태를 해결하려면 별도 서버 설계가 필요하다.
- 다음 최우선 조사: 원본 서비스 버전별 채팅방 최대 정원, 원작의 개설/잠금/퇴장/방장 변경/강퇴 프로토콜과 UI, 닉네임/말풍선 위치의 실제 스크린샷 좌표, 채팅타운 각 구역의 실제 방 목록 규칙. 원본 서버 파일·패킷 증거 확보 전까지 재구현 추정치를 역사적 사실로 표시 금지.

## 7. Region/TOWN SELECT와 ChatTown의 분리 (2026-10-14)

**원작 플레이 경험을 직접 기억하는 이용자의 명시적 정정**: 월드맵의 남/북 하이아칸에서 나타나는 `TOWN SELECT` 화면은 채팅방 선택이 아니라 **주사위의 잔영 채널 선택** 화면이다. 내부 화면 문구가 TOWN SELECT라는 이유로 채팅타운/채팅방에 연결하는 것은 잘못된 역해석이다.

원본 PAK 이미지 확인:
- `original/Region/regionback.png` (794×404): 중앙의 TOWN SELECT 글자와 Ispin, Nayntrei, Cloe, Mila, Tichiel, Anis, Benya의 7개 그룹, 각 그룹의 숫자 1·2·3·4를 포함한 게임 채널 화면. **게임 채널 선택용**.
- `original/Region/character.png`, `original/Region/1234.png`: 캐릭터 및 채널 숫자 상태 그래픽. Region 패키지에 들어있으며 ChatRoom 배경과 다름.
- `original/Gif/d1lobby.png`: 게임방 목록 ROOM SELECT와 CREATE/JOIN이 그려진 주사위 게임 대기실.
- `original/Gif/d1waitroom.png`: PLAYER, CHESSMAN INFO, START를 갖춘 주사위 경기 준비실.
- `original/ChatTown/northback.png` 및 `southback.png`: 북/남 하이아칸 실제 채팅 타운 표지와 8개 지역. **채팅 경로용**.

수정 후 화면 전이:
1. 월드맵 북/남 하이아칸 → `dice-channels` (주사위 전용 Region/TOWN SELECT 7×4 선택 UI).
2. 번호 선택 → `lobby` (주사위 게임방 조회/개설), 선택한 채널 및 북/남 지역은 로컬 세션과 경기 데이터에 보존.
3. 게임방 입장/생성 → 준비실 및 `game` 주사위 경기 흐름. 현재 하나의 저장 경기만 남기는 웹 재구현의 한계가 있으며 독립된 원작 서버 로비는 미복원.
4. ChatTown은 독립된 채팅 탭의 `rooms` 화면에서 진입하며, 북/남 채팅 지역 전환은 별도 채팅 버튼으로 처리. 주사위 채널 번호를 채팅방 그룹 분리에 사용하지 않는다.
5. 이전 웹 재구현이 잘못 사용한 `social-chat.js` 채널별 구분은 제거하되 원본 채팅방 객체와 원래 저장 키는 보존. 기존 채널별 채팅 로그는 병합/이관 과제로 남아 있음.

증거 등급: `Region` 원본 그래픽과 `Gif` 원본 데이터는 VERIFIED-ARCHIVE, 주잔 채널 경험 분류는 USER-REPORTED. 주사위 채널을 통한 **실제 원작 서버 로그인/서버 간 인원 분리 프로토콜은 UNVERIFIED**이며 현 웹앱에 원작 중앙 서버가 구현됐다고 주장할 수 없음.

브라우저 검증: `tests/dice-channel.cjs` 와 `tests/world-chat.cjs`에서 두 하이아칸 선택, 주잔 28개 채널, 게임방 화면, 실제 경기의 선택 채널 저장, 다른 채널 게임방 혼입 방지, 별도 ChatTown 실시간 채팅 복원을 시험한다.


## 8. 2026-10-15 채팅타운 공간형 방 복원 — 근거/한계

- **VERIFIED-CONTEMPORARY (2002-02-27)**: 당시 소프트맥스의 0.9 업데이트 공지는 기존 타운당 방 설치 최대 5~80개를 타운당 최대 200개까지 넓힌다고 설명한다. 북/남 하이아칸 신규 지역도 명시한다. 이는 방이 타운 공간에 위치하는 구조를 뒷받침하지만, 언제나 200개 방이 온라인이었다는 증거는 아니다. 원문: https://4leafmemorial.geld.kr/m/774
- **USER-REPORTED**: 당시 채팅지역에는 기본적으로 열려 있는 방들이 공간에 흩어져 있었고, 사용자가 화면을 사방으로 이동해 골라 정원이 남은 방에 입장했다. 2026-10-15 직접 이용 경험 진술.
- **INFERRED RESTORATION (이번 개발)**: `social-chat.js`의 `staticRooms`는 지역별 결정적 ID를 갖는 복원용 기본 공개 공간이다. 총 북/남 하이아칸 × 각 8개 구역 × 각 8개 방을 두었다. **8개/구역, 방 번호, 1480×1120 맵, 각 방 위치, 12인 정원은 원작에서 추출한 수치가 아니다.** 원작 실행 구조를 확인하기 전 임시 값이며 원작의 실제 상설 목록이라고 명명하지 않는다.
- **VERIFIED WEBAPP (코드)**: 생성형 채팅방과 별개인 `staticRooms`는 로컬 저장소에 가짜 이용자/대화 내역을 심지 않는다. `roomById`로 실제 입장하고 BroadcastChannel/수동 RTC를 통해 대화할 수 있으며, 원작 사방 탐색 경험을 흉내 내는 독립 DOM 방 마커, 방향키, 드래그, 휠, 이동 버튼이 있다. 방 정원 검사는 **직접 연결된 사용자에 한정**한다. 서로 다른 기기 사이 서버 권위/정원 원자성은 미구현.
- **VERIFIED WEBAPP (회귀)**: `tests/world-chat.cjs`는 공개방 입장과 비가짜 인원 표시, 2축 지도 이동, 기존 생성 방, 캐릭터 클릭 좌우 반전, 인위적 글로우 미사용을 브라우저에서 검증한다.
- **PENDING**: 원본 ChatTown 버튼 이미지들의 프레임과 도시 화면의 판정 영역을 역해독하고, 실제 동시대 채팅방 배치 사진/동영상 및 원본 실행 파일을 통해 상설 목록 개수, 정확한 좌표, 카메라 이동 폭, 방 규모를 교정한다. 0.9와 초기 버전 동선을 혼동하지 않는다.

- **VERIFIED-ARCHIVE (2026-10-15 재분석)**: `original/IMG/bgtile.png` is an actual recovered native landscape tile (725×485) with trees, paths, huts and escarpments. The chat-space map now uses independent room controls over repeated source landscape pixels rather than a fabricated gradient. Source's exact historical pan dimensions are still unverified.
- **VERIFIED-CONTEMPORARY (2000-06-07)**: https://kbench.com/?q=node%2F5061 includes a period Haiacan area screenshot with independent over-water room-building artwork and room number/occupancy labels. It predates 0.9 and must not be mistaken for the exact later city backdrop. The v0.9 room-map terrain currently uses the recovered `bgtile.png`, not that screenshot pasted beneath hotspots.

- **VERIFIED WEBAPP (2026-10-15)**: 원본 IMG/bgtile 기반 채팅 지역에서 방에 입장한 뒤 목록으로 돌아와도 해당 지역/구역의 좌우·상하 지도 카메라 좌표를 유지한다. Chromium 통합 QA는 방향키 2축 이동과 복귀 후 위치 유지를 검사한다. 원작 정확한 초기 좌표와 이동 한계는 아직 미확인이다.
- **VERIFIED-ARCHIVE (소스 이미지 육안 검토)**: `original/Map/mapback.png`와 `Map/mapbutton.png`는 주사위의 잔영 `ROOM SELECT` 및 `CREATE/JOIN` UI이고, `original/Room/roomback.png`는 `PLAYER/CHESSMAN INFO`를 포함하는 주잔 준비실이다. 파일명만 보고 채팅타운 지형으로 오용하지 않는다.
