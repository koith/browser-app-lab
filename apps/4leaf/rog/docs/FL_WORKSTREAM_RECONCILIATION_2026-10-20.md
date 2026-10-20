# 4LEAF FL-01~FL-16 ↔ GitHub 영구 개발원장 대조 (2026-10-20)

## 원본 식별 및 변경 정책

- **기준:** `main/apps/4leaf/rog/docs/RESTORATION_LEDGER.json`의 57건(작업군 M00~M09 10건, P0-* 6건, GOV-LEDGER 1건, 세부 40건), 2026-10-19 마지막 변경.
- **중요:** 사용자가 말한 **FL-01~FL-16의 원문별 제목·수용 조건은 현재 GitHub 코드·문서·Issue 검색에 존재하지 않는다.** 16개라는 수만으로 기존 FL 번호에 새 제목을 꾸며 붙이거나 완료로 처리할 수 없다. 이 문서는 **실재하는 GitHub 원장 작업군 16개의 임시 대조 인덱스**이며, 과거 FL 원본과 동일하다는 주장이 아니다.
- 영구 식별자는 기존 `M00–M09`, `P0-*`, 세부 작업 ID를 유지한다. 원문 확인 후 FL 별칭 매핑을 추가하고, 충돌시 신규 세부 작업을 등록한다.
- 상태 계산은 GitHub JSON만 사용. 이 문서의 초기 수치는 이후 원장 변경 시 갱신 필요.

## 16개 기존 상위 작업군의 임시 대조 인덱스

| 임시 슬롯 | 실제 원장 ID | 원작 수용 목표 | 2026-10-19 상태 |
|---|---|---|---|
| slot-01 | M00 | 원본 자산·출처·리소스 역할 | in_progress |
| slot-02 | M01 | 월드맵·메인프레임 | in_progress |
| slot-03 | M02 | 켈티카·매직카덴 | in_progress |
| slot-04 | M03 | 북/남 하이아칸 상설 채팅 | in_progress |
| slot-05 | M04 | 주잔 DMP/TIS 정밀 보드 | in_progress |
| slot-06 | M05 | 창세기전 OBS 체스맨 원형/방향/동작 | in_progress |
| slot-07 | M06 | 전투 발판/카메라/접지 | in_progress |
| slot-08 | M07 | 결과별 주사위 실제 낙하·반동·정지 | in_progress |
| slot-09 | M08 | 특수칸·전투 규칙·멀티 | in_progress |
| slot-10 | M09 | 스크린샷 동일상태 A/B·배포 수용 | in_progress |
| slot-11 | P0-BOARD | 타일 상하·겹침·윗면·원근 | in_progress |
| slot-12 | P0-ACTOR | 원작 98종 OBS·프레임별 동작 | in_progress |
| slot-13 | P0-PODIUM | 원작 입체 전투 발판·보폭 | in_progress |
| slot-14 | P0-DICE | D4/D6별 진짜 모델·10개 결과 동작 | in_progress |
| slot-15 | P0-CHAT | 2004 원본 채팅방·실접속·실제 자리 이동 | in_progress |
| slot-16 | P0-RELEASE | 역사적 원본 동등성 수용 게이트 | in_progress |

## 실제 검증 완료 — 반복 개발 금지

`GOV-LEDGER`, `BRD-05`, `BTL-01`, `BTL-03`, `DIE-03`, `CHT-01`, `CHT-03`, `CHT-06`, `CHT-07`, `WORLD-03`, `QA-01`, `QA-02`, `QA-04`는 GitHub 원장에 `done`. 완수 범위 이상의 원작 3D/포즈·전체 픽셀 동일성까지 끝난 것은 아니다.

## 미완료 실무 원칙

- `P0-BOARD/BRD-01..03`: 145×97 원본 TIS의 맵 투영·윗면·인접 비겹침·깊이 A/B.
- `P0-ACTOR/ACT-01..04`: 64/98종 실물 OBS 및 미확보 34종, 올바른 scanline 원점·상태 타임라인.
- `P0-PODIUM/BTL-02/04`: 원본 2D winBattle 사용은 검증됐지만 EXE 원본 입체 3D 시점은 미확인.
- `P0-DICE/DIE-01/02/04`: ROLL UI 진품과 낙하 주사위 메시를 구별. WEB 폴백을 원작 결과별 모션 완료로 쓰지 않음.
- `P0-CHAT/CHT-02/04/05`: 같은 방·참가자 상태의 채팅·좌석·가구 클릭 영역 동등성.
- `WORLD-02`: 원본 녹색키 건물 PNG의 투명 픽셀 클릭을 상점으로 오판하는 결함. PR #144는 `main`과 충돌하므로 최신 `main` 기반으로 재적용하여 정확한 실제 마우스/터치 QA 후 통합. 진짜 EXE 핫스팟은 여전히 미해독.
- `EVID-01/02`, `QA-03`: 2004 같은 상태 원본-웹 픽셀·아이폰 Safari 동등성은 닫지 않음.
- 원작 2003년 공식 공지의 `[Non]` 맵 PvP 금지와 랜덤맵 지원은 이미 코드·QA 반영됨. 재개발 말고 회귀 수용 유지.

## 근거

- 원장: [RESTORATION_LEDGER.json](./RESTORATION_LEDGER.json)
- 세부 원작 대비: [RESTORATION_GAP_BACKLOG_2026-10-18.md](./RESTORATION_GAP_BACKLOG_2026-10-18.md)
- 원본 2003.02.21 공식 공지: https://4leafmemorial.geld.kr/m/908
- 릴리스: [app-version.json](../app-version.json)
- 최근 원장 및 Pages 완료 SHA: https://github.com/koith/browser-app-lab/commit/fa86a0e865396b2781f528eee7ad29214068a098
- WORLD-02 충돌 원본 PR: https://github.com/koith/browser-app-lab/pull/144

## 차기 수행

1. WORD-02 오타 없이 **WORLD-02** native bitmap 투명 클릭과 거리 pan QA를 최신 branch/main에서 검사, 원장에 실제 실행·배포 링크 기록.
2. `EVID-01` 원작 `board.jpg`, `battle.jpg`, `chat.jpg`, `chat_ref.jpg` 대비 동일 게임 상태를 구성해 전후 화면 픽셀 앵커 리포트.
3. 원본 OBS 결손 34종·D4/D6 메시·정확한 주사위 낙하 프레임을 클라이언트 바이너리/공식 영상과 교차 검증.
4. 유효한 과거 FL-01~FL-16 원문 확보 전에는 임시 슬롯을 실제 FL 번호로 확정하지 말 것.
