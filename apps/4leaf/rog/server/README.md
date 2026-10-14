# 4LEAF 중앙 채팅타운 서비스 (실제 다중기기용 백엔드)

현재 GitHub Pages의 BroadcastChannel/수동 WebRTC 한계를 제거하기 위한 **서버 권위 기반 서비스 코드**. Node.js 22+ 표준 라이브러리만 사용한다.

```sh
LEAF_CENTRAL_ORIGINS=https://koith.github.io LEAF_CENTRAL_STORAGE=./private/chat-state.json PORT=8787 node apps/4leaf/rog/server/central.cjs
node --test apps/4leaf/rog/server/central.test.cjs
```

이 서버는 인증 토큰을 각 세션에 부여하며, 실제 하이아칸 지역별 공개방 8개(원작에서 **개수 미검증인 복원용 항목**)와 사용자 생성방을 구분한다. 여러 기기에서 **동시에** 같은 방에 입장할 때 마지막 정원은 서버가 원자적으로 검사한다. 방장만 방 폐쇄를 요청할 수 있고, 암호방의 원문 비밀번호를 저장하지 않는다. 방별 메시지/접속자 정보는 해당 방에 실제 입장한 인증 세션만 읽을 수 있다. 세션은 45초 안에 상태 조회 또는 갱신이 없으면 만료된다. 원본 2000년대 서버 프로토콜과 정확히 동일하다고 주장하지 않는다.

## API

| API | 동작 |
|---|---|
| `POST /api/session` | 세션 생성; 토큰/ID 수령 |
| `GET /api/rooms?region=north&district=...` | 권한 있는 방 목록과 실제 접속자 수 |
| `POST /api/rooms` | 새 방 생성; 서버 방장 지정 |
| `POST /api/rooms/:id/join` | 서버측 정원·비밀번호 검사와 입장 예약 |
| `POST /api/rooms/:id/close` | 방장 전용 폐쇄 |
| `POST /api/leave` | 퇴장 |
| `POST /api/presence` | 이름·캐릭터·좌우 방향·즉시 위치 갱신 |
| `POST /api/chat` | 입장한 방에만 채팅 송신 |
| `GET /api/snapshot?after=0` | 해당 방의 실제 사용자 상태와 새 메시지 |
| `GET /api/health` | 작동 확인 |

`/api/session`을 제외한 모든 API는 `Authorization: Bearer <token>`을 요구하며, 브라우저 CORS 허용 출처는 `LEAF_CENTRAL_ORIGINS`로 제한된다. 백엔드는 HTTPS 역방향 프록시 또는 인증된 HTTPS 런타임 뒤에 배포해야 한다. `LEAF_CENTRAL_STORAGE`를 지정하지 않으면 사용자 생성방과 메시지 기록은 서버 재시작 때 사라진다.

**검증 수준:** Node HTTP 수준의 13명 동시 정원 경쟁, 빈방, 채팅 가시성 분리, 좌우 방향/슬롯, 방장 권한, 암호, 저장소, 출처 제한은 자동 검증한다. **운영 미완료:** 아직 공개 도메인의 중앙 서버에 배포하거나 기존 브라우저 클라이언트의 방 UI에 연결하지 않았다. 기존 GitHub Pages 실행 자체를 중앙 서버로 간주하지 않는다. 연결, 재접속, 서버 재시작 후 소유권 보존 및 원본 규칙 검증을 이어서 수행해야 한다.
