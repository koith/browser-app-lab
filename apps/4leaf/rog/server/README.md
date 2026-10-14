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

**검증 수준:** Node HTTP 단위 테스트와 두 개의 완전히 독립적인 Chromium 컨텍스트를 통한 서버형 채팅, 정원 경쟁, 암호방, 방장 권한, 재접속과 기존 게임 회귀 테스트를 자동 실행한다. 컨테이너도 CI에서 직접 빌드·기동해 /api/health를 확인한다.

**구현되었지만 아직 운영 검증이 필요한 부분:** HTML에는 `central-client.js`와 `social-chat.js` 서버 연동이 연결돼 있지만 공개 GitHub Pages의 `<meta name="leaf-central-api" content="">`은 서버 주소가 실제로 확정되기 전까지 빈 값이다. 따라서 공개 주소에서는 여전히 브라우저 탭·수동 WebRTC 모드가 기본이다. GitHub Pages는 백엔드를 실행하는 서버가 아니므로 단독으로 중앙 채팅이 작동한다고 주장하지 않는다.

## 지속형 서버 배포 준비

- `Dockerfile`: Node 22 표준 라이브러리만 사용하는 독립 컨테이너. 10000번 포트, /api/health 응답 및 비특권 사용자로 실행
- `render.yaml`: Render 유료 Starter + 1GB 영구 디스크를 사용하는 **선택형 Blueprint**. 이 파일을 커밋하는 것 자체는 서버 생성이나 결제를 수행하지 않음
- `LEAF_CENTRAL_STORAGE=/var/lib/4leaf/chat-state.json`: 서버 재시작 이후에도 방 생성 정보·암호 해시·대화 내역을 보존할 영구 볼륨. 인메모리 이용자 세션과 실시간 접속 인원은 재시작 후 재로그인이 필요
- `LEAF_CENTRAL_ORIGINS=https://koith.github.io`: 실제 정적 클라이언트의 출처만 CORS 허용

배포된 HTTPS 서버 URL을 확인한 후에만 `index.html`의 `leaf-central-api` 메타 태그에 그 URL을 연결할 수 있다. 실제 다중 기기·배포 주소에서 자동 QA를 통과해야 운영 완료로 처리한다. Render 서비스 생성/영구 디스크에 비용이 발생할 수 있으므로 계정 연결과 비용 승인은 별도의 사용자 판단 사항이다.

본 서버는 **과거 소프트맥스의 계정 체계나 프로토콜과 동일하다고 증명되지 않은 독립 재구현**이며, 주사위 게임방 서버 권위까지 제공하지는 않는다.
