# 4LEAF 무료 멀티클라우드 권장 설계서

작성일: 2026-10-15. 상태: 목표 설계(미배포). 원작 월드맵, ChatTown, ChatRoom, 주잔의 UI·동작 보존을 최우선으로 한다.

## 목표 및 불변 조건

- GitHub Pages의 원작 그래픽/정적 화면/오프라인 실행을 유지한다.
- 유료 서버와 디스크를 승인 없이 만들지 않는다.
- 하나의 채팅방 또는 주잔 게임방에는 단 하나의 authoritative writer만 존재한다.
- 장애 시 가짜 접속자, 유령 좌석, 중복 입장, 중복 주사위 판정을 생성하지 않는다.
- 북/남 하이아칸의 ChatTown과 주잔의 TOWN SELECT를 혼동하지 않는다.
- 원작 ChatRoom의 클릭 위치 이동은 즉시 처리하며 좌표 보간 애니메이션을 추가하지 않는다.

## 서비스 배치

| 구성 | 역할 | 저장과 주의점 |
|---|---|---|
| GitHub Pages | 원작 화면, 이미지, 음향, 정적 JS, 오프라인 게임 | Git 버전 관리 및 SW 캐시 |
| Cloudflare Worker | 공개 API, 요청 검증, 라우팅, 사용량 제한 | 서버 단독 인증·권한 검사 |
| ChatRoom Durable Object | 방마다 단일 입장·퇴장·좌석·메시지 권한 | SQLite 방 설정·메시지·시퀀스, 활성 연결 TTL |
| DiceRoom Durable Object | 게임방별 턴·주사위 판정·승패 | SQLite 상태 및 이벤트 로그 |
| Supabase Auth/Postgres (선택) | 계정, 캐릭터, 친구, 영구 프로필 | RLS·최소 정보 수집, 무료 프로젝트 중단 대비 |
| Render Free (보조) | 현재 Node 중앙 서버의 호환성 시험 | 유휴 절전, 재시작 시 파일 소실; 운영용 영구 DB 아님 |

## 데이터 및 API 계약

현재 central-client.js의 API 계약을 우선 보존한다.

- POST /api/session: 세션 발급·재개, 만료 시간 및 서버 확인 입장 방 반환.
- GET /api/rooms?region=&district=: 실제 방과 정원·인원 조회.
- POST /api/rooms: 방 이름·정원·배경·비밀번호 검증 후 생성.
- POST /api/rooms/:id/join: 방 단위 원자적 정원 확인 및 예약.
- POST /api/rooms/:id/close: 서버의 소유자 검증.
- POST /api/leave, POST /api/presence, POST /api/chat.
- GET /api/snapshot?after=: 기존 폴링 호환. 추후 WebSocket 이벤트 전송을 추가.

방 명령에 requestId를 부여해 재시도 중복을 막고, epoch와 단조 증가 seq를 사용해 서버 재시작과 순서 누락을 검출한다. 클라이언트가 연결을 잃으면 재접속 후 서버 스냅샷으로 복구한다. 방 비밀번호는 강한 해시로 저장하고 토큰은 로그에 남기지 않는다. CORS는 인증을 대신하지 않으므로 모든 권한을 서버에서 확인한다.

## 장애 정책

- Cloudflare 요청 실패/429: 제한된 지수 백오프와 jitter 후 재연결. 쓰기 재시도는 멱등 처리.
- Durable Object 재시작: SQLite에서 방과 기록 복구, 접속자 재인증 및 좌석 재예약.
- Render Free 절전: 보조 시험 서버로만 사용. 운영 중인 Cloudflare 방에 대한 쓰기 권한을 가져가지 않음.
- Supabase 중단: 프로필/로그인 기능만 제한하고 익명 채팅과 오프라인 실행은 유지하도록 분리.
- 네트워크 분할: 다른 제공업체에 임의로 이중 쓰기하지 않고 오류·재연결 상태 표시.
- 저장·요청 무료 한도: 기록 보존 정책, 요청 제한, 알림. 유료 자동 승격 금지.

## 이행 계획 및 완료 기준

1. P0 [완료] 기존 Node 중앙 서버, 브라우저 테스트, Render 무료 무디스크 Blueprint 작성.
2. P0 [대기] 무료 Render 실배포 후 HTTPS/CORS/절전/재시작 및 데이터 소실을 검증.
3. P1 [미완료] Worker 및 SQLite-backed ChatRoom Durable Object 구현; 기존 REST 계약 유지.
4. P1 [미완료] 지역별 방 디렉터리, WebSocket, heartbeat, reconnect 구현.
5. P1 [미완료] 서로 다른 브라우저에서 13명 동시 입장 시 정원 12명만 허용; 방장·비밀번호·메시지 순서·좌석 이동 검증.
6. P2 [미완료] 주잔 게임방 권한 서버와 매칭/턴/주사위 판정/재접속 테스트.
7. P3 [조건부] 원작 요구가 확인되면 Supabase 계정·친구 기능 도입.
8. P4 [미완료] 공개 앱 연결, 외부 기기 E2E, 장애 및 무료 한도 초과 훈련.

**최종 완료 판정:** 공개 URL에서 독립 기기 두 대 이상이 실제 방 인원·메시지·좌석을 동기화하고, 원작 인터페이스가 유지되며, 서버 재시작·연결 끊김 시 정해진 보존/복구 정책이 검증되어야 한다.

## 참고

- https://github.com/cloudflare/templates/tree/main/durable-chat-template
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/limits/
- https://render.com/docs/free
- https://supabase.com/docs/guides/realtime/limits
- https://supabase.com/docs/guides/platform/free-project-pausing
- docs/original-experience-evidence.md
- docs/free-multicloud-architecture.md

무료 제공량 및 이용 조건은 배포 시 공식 문서에서 다시 확인한다.
