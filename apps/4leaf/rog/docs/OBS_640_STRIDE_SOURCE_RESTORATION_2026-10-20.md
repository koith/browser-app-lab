# 4LEAF OBS 640-stride 원본 체스맨 복구 — 2026-10-20

## 원본 검증

2002 4LEAF 설치 ZIP: SHA1 86526d89679ae39b85fe9808da97ad871b7888d9, 64,537,476 bytes.
원본 Dice/OBS.pak: SHA256 49738a942ffe3856fb86b4c5ce698b7e460bb876b38c31884028b3e2e833d514.

원본 IMG.pak ROLL SPR과 공통인 VIDEO 640-stride, u16 runCount/initialOffset 및 indexed palette 패킷 구조를 OBS에도 엄격 적용한다. 각 패킷의 건너뛴 투명 영역, 원본 픽셀 길이, 640 가상 화면 x/y 좌표, 선언된 native frame bounds, 원본 RGB palette를 보존한다. 과거 WEB 중심 X 추정 배치는 폐기했다. 픽셀·색상·빈 행은 상상해서 추가하지 않았다.

초기 실패 이유: 원본 끝행에는 오른쪽 투명 여백 데이터가 반드시 존재하지 않음. OBS 1128은 239×222 원본 캔버스 일부 행에만 픽셀을 기록함. OBS 1095는 진짜 172 source frame으로 이전 임의 제한 128을 초과함. OBS 1093/1098/1159에는 폭/높이 작은 보조 프레임이 있어 기존 10픽셀 최소 크기 규칙에 막힘. 전부 원본 packet/팔레트와 frame boundaries 조건을 확인한 후에만 복구한다.

## 수량

| 항목 | 이전 | 현재 |
| --- | ---: | ---: |
| OBS.pak 벌크 원본 전신 | 62/90 | 90/90 |
| 벌크 원본 프레임 | 268 PNG | 616 PNG |
| 별도 1042/1045 원본 전신 | 2종/13 PNG | 2종/13 PNG |
| 전체 체스맨 복구 | 64/98 | **92/98** |
| 총 실제 원본 픽셀 프레임 | 281 | **629** |
| 원본 전신 미확보 | 34 | **6** |

구버전에서 실패한 OBS 멤버 28종 모두 새 소스 decoder로 복구해 프레임별 original URL, SHA256, originX/Y 및 frame index를 animation-extra.js에 등록하고 616 PNG를 게임/PWA 리소스로 반영한다.

## 끝까지 미확보인 6종

**0091, 0126, 0129, 0132, 0157, 0168**.

2002 클라이언트에 실재하는 OBS.pak, OBS2.pak, OBS3.pak 세 개를 SHA1 검증 설치판에서 모두 읽었다. 그 6개 카드 ID와 일치하는 원본 1NNN.obs 멤버는 어떤 원본 pack에도 없음. Actions OBS_SECONDARY_ALL_SOURCE_IDS 증거로 남김. 이는 2002 설치판에서의 부재이지 2004 원본 클라이언트 전체에 없다는 뜻이 아니다. 다른 버전의 공식 설치판/패치/다른 모델 경로를 별도로 조사해야 한다.

## 실제 앱 적용과 미완료 범위

기존 Genesis actor renderer는 animation-extra.js와 frame source list를 사용하므로 92종 원본 PNG가 실제 참가자 카드에 자동 연결된다. 새로 복원된 ID는 더 이상 원본 미복원 카드-초상화로 간주하지 않는다. 6종에 한하여 원본 CardData 정지 프레임을 정직하게 표시한다. board 26 DMP/1920 tiles와 원본 주사위 결과, 서버 채팅, PWA 오프라인 상태는 보존한다.

OBS 픽셀/팔레트/프레임/VIDEORLE source X는 **원본 검증**. 실제 idle/walk/attack/hurt/victory 방향별 EXE 테이블 및 재생 타이밍은 **미해독·미완료**. 게임이 여전히 움직이는 원본 프레임을 잠정 역할로 연결하고 있다는 사실과 원작 행동표 복원을 구분한다.

## 2004 레퍼런스 사진으로부터의 제한

apps/4leaf/assets/board.jpg 와 battle.jpg 는 두 개 전투 발판, BATTLE/VS, 공격·방어 주사위가 보이는 원본 **800x600 배틀 장면**이다. 일반 보드의 동일한 DMP 경로/주사위 턴/카메라 화면이 아니므로 이 두 사진을 일반 보드와 같은 상태로 취급해 150x100 웹 중심 간격의 정확성을 주장하면 안 된다. native TIS 145x97 원화, 원본 DMP 정수 좌표, 수평 사각형 겹침 0건, 역상 correction을 보존하되 원작 MVE 3D 투영은 BRD-01~03에 미완료로 남긴다.

실제 배틀에는 원본 355x113 IMG winBattle 두 발판 스프라이트와 원본 OBS 체스맨을 독립 합성한다. 해당 source 2D PNG와 아직 없는 3D podium 메시/카메라를 동일한 것으로 속이지 않는다.

## 다음 일감

1. 유실 6종의 다른 공식 2002~2004 클라이언트/패치의 원본 패키지 해시·멤버 확보.
2. 실행 없이 EXE/native tables를 역분석해 OBS의 진짜 방향/idle/walk/attack/hurt/victory frame ranges와 FPS를 검증.
3. 같은 DMP 맵/같은 플레이 턴을 가진 역사 원본 영상과 웹 화면의 타일 중심/투영/윗면/접지 측정.
4. 실제 D4/D6 source mesh/texture/keyframe 또는 영상 기반 판별 자료 확보 후에만 original animation done 검토.
