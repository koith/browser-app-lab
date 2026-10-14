# 4LEAF 무료 멀티클라우드 운영 검토 (2026-10-15)

## 검증한 구현 사례

- [Cloudflare 공식 Durable Chat](https://github.com/cloudflare/templates/tree/main/durable-chat-template): 채팅방마다 Durable Object 하나를 두고 WebSocket과 SQLite로 메시지를 저장·전파. 4LEAF의 방별 인원 제한/좌석 상태에 적합.
- [parsi-srikanth/multiplayer-games](https://github.com/parsi-srikanth/multiplayer-games/blob/main/docs/ARCHITECTURE.md): 무료 티어를 목표로 정적 자산 + stateless Worker + room별 authoritative Durable Object를 결합. 주잔 서버 확장에 참고.
- [Cloudflare Durable Objects 무료 요금](https://developers.cloudflare.com/durable-objects/platform/pricing/): SQLite-backed DO 사용 가능, 한도 초과 요청은 오류 처리. [한도](https://developers.cloudflare.com/durable-objects/platform/limits/)는 계정당 저장 5GB 등.
- [Render 무료 서버](https://render.com/docs/free): 15분 유휴 시 중지, 재기동 지연, 재배포/재시작/절전 시 파일 소실. 무료 Postgres는 30일 후 만료. Render 무료 Key Value도 재시작 시 데이터 소실.
- [Supabase Realtime 제한](https://supabase.com/docs/guides/realtime/limits): 무료 동시 접속 200, 초당 메시지 100. [무료 프로젝트](https://supabase.com/docs/guides/platform/free-project-pausing)는 7일 저활동 시 중지될 수 있음.

## 4LEAF 적용 결정

1. **정적 자산**: 기존 GitHub Pages 유지. 별도 유료 호스팅 불필요.
2. **ChatTown 실시간 권한**: 장기적으로 Cloudflare Worker + SQLite-backed Durable Object를 *방 단위 단일 권한*으로 배치. 입장/퇴장/정원 검사/메시지 순서/좌석을 한 DO에서 처리. 클라이언트의 재시도는 중복 입장을 만들지 않아야 함.
3. **영구 계정/캐릭터**: 실제 필요가 확인될 때 Supabase Auth/Postgres를 검토. 지금은 사용자 계정 및 민감 데이터 이전 금지. 무료 일시정지와 쿼터 감시 필요.
4. **기존 Node 서버**: Render 무료 서비스에서 기능 검증 및 개발용 대체 경로로 활용 가능. 단, 현재 중앙 서버의 `LEAF_CENTRAL_STORAGE` 파일은 무료 Render에서 **영구 보존되지 않음**. 빈 저장 경로를 사용하면 재시작 후 사용자 생성 방과 채팅 기록은 초기화됨.
5. **주잔 멀티플레이**: 별도의 authoritative game-room 서비스로 분리하되, 주사위 판정과 턴 순서의 이중 권한 방지. 현행 WebRTC 수동 교환은 중앙 매칭 대체물이 아님.

## 자동 장애 전환의 금지 조건

- 서로 다른 Render/Cloudflare 서버가 **같은 방에 동시에 입장 허가**하면 정원 초과·유령 좌석·메시지 분기 발생. 클라이언트가 임의로 다른 서버에 쓰기 전환하는 방식 금지.
- 실시간 방 서버 장애 시 **읽기 전용/재연결 상태**를 표시하고, 단일 권한 서비스가 복구된 뒤 서버 기준으로 상태를 다시 동기화.
- 다른 서비스로 쓰기 권한을 넘기려면 공유 저장소 기반 리더 임대/펜싱 토큰과 단조 증가 epoch, 이전 리더 차단, 멱등 명령이 필요. 무료 MVP에서는 복잡한 자동 failover 대신 명확한 재접속을 선택.
- 개인정보, 세션 토큰, 비밀번호를 브라우저 URL 또는 공개 저장소에 기록하지 말 것.
- 약관 위반 가능성이 있는 다중 계정 무료 한도 우회, 유료 플랜 자동 승격, 자동 과금 금지.

## 단계별 검증

- **단계 A**: Render 무료 Docker 웹 서비스로 기존 중앙 API를 공개 테스트. 유휴 복구/재배포/세션 만료/방 목록 초기화의 사용자 안내를 확인. 프로덕션 영구 저장이라고 표시하지 않음.
- **단계 B**: Cloudflare 계정 연결 후 room-per-DO 프로토타입 구축. 기존 `central-client.js`의 REST 계약과 브라우저 테스트 재사용.
- **단계 C**: 서로 다른 브라우저에서 동시 입장 13명→정원 12명, 방장 권한, 재접속, 메시지 순서, 배포 중단, 429/503/무료 한도 초과 등을 자동 검증.
- **단계 D**: 원작 ChatTown 복원 화면을 유지하면서 실시간 기능만 점진 전환. 원작과 무관한 새로운 UI를 임의 도입하지 않음.

## 비용 주의

무료 플랜이어도 Render에서 결제 수단이 등록된 경우 전송량/빌드 분 초과분 청구 가능. 계정별 사용량·청구 설정 확인 전 자동 서버 생성 금지. 무료 제공량과 제한은 변동 가능.
