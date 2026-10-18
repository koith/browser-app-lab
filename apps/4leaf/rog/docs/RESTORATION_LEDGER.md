# 4LEAF 원작 복원 — 영구 개발원장 운영 규정

> **원본 데이터(단일 진실 공급원)**: [RESTORATION_LEDGER.json](./RESTORATION_LEDGER.json)  
> 원작 외형·게임 플레이 **전체 복원은 미완료**. 다른 문서나 오래된 대화의 '완료' 주장보다 JSON의 수용 조건과 검증 증거를 우선한다.

## 신규 대화에서도 반드시 시작하는 순서

1. GitHub `koith/browser-app-lab`의 현재 `main`을 조회한다. 원장이 없는 옛 커밋이나 대화 답변에서 이어가지 않는다.
2. `node apps/4leaf/rog/tools/restoration-ledger.cjs check` 와 `... open`으로 등록 일감과 미완료 작업을 조회한다.
3. 사용자의 새 개발 요청은 **먼저** 식별자와 수용 조건이 있는 작업으로 등록한다. 기존 항목 재요청도 `intake`에 새 원문을 추가하여 추적한다.
4. 우선순위 P0부터 **실제 원본 조사 → 앱 수정 → 시험 → A/B 비교 → 배포**한다. 대화에 '수정했다'고 답하는 것만으로 상태를 바꾸지 않는다.
5. 원장에 변경 내역과 근거(경로, 시험, 스크린샷, 성공 커밋)를 저장하고 커밋/PR/배포 검증 후 다음 미완료를 다시 조회한다.

## CLI (Node.js 22, 외부 패키지 불필요)

```sh
node apps/4leaf/rog/tools/restoration-ledger.cjs check
node apps/4leaf/rog/tools/restoration-ledger.cjs open
node apps/4leaf/rog/tools/restoration-ledger.cjs report --json
node apps/4leaf/rog/tools/restoration-ledger.cjs add P0-NEW P0 M04 "증상 제목" "원본 수용 기준" "현재 미완료 이유"
node apps/4leaf/rog/tools/restoration-ledger.cjs intake "사용자의 실제 개발 요청" P0-NEW M04
node apps/4leaf/rog/tools/restoration-ledger.cjs set P0-NEW in_progress "브라우저/원본 A/B 조사 착수"
node apps/4leaf/rog/tests/restoration-ledger.cjs
```

- `add`: 유일 ID, 목표 마일스톤, 수용 조건, 초기 미완료 상태, 생성 이벤트를 같은 JSON에 저장.
- `intake`: 요청의 **실제 텍스트**와 연결된 작업 ID를 소실되지 않는 요청 기록으로 추가. 이미 존재하는 작업도 재요청/추가 요구라면 다시 등록.
- `set`: 이전/다음 상태와 사유를 이벤트에 추가. `done`은 `verifiedAcceptance`에 `sourceComparison`, `implementation`, `runtimeTest`, `deployment` 근거가 사전에 없으면 저장 거절.
- `blocked`: 차단 원인, 시도한 대안이 실제로 원장에 기록돼야만 인정. 한 시도 실패는 구현 불가 판정이 아님.
- `check --against <git-ref>`: 이전 Git 기록과 비교해 **작업 삭제·요청문 변경·작업 이력 삭제·상태 무기록 변경**을 자동으로 거부. GitHub Actions [rog-restoration-ledger.yml](../../../../.github/workflows/rog-restoration-ledger.yml)에서 검증.

## 근거 등급

- **VERIFIED-ARCHIVE**: SHA·원본 추출 픽셀/데이터가 확인됨.
- **VERIFIED-WEBAPP**: 실사용/브라우저·테스트·배포로 실제 동작 확인됨.
- **INFERRED**: 2002~2004 원본 구현이 확인되지 않은 웹 투영, 2.5D/3D 추정, 프레임 의미 등의 임시 복원.
- **UNVERIFIED**: 원본과 일치한다는 최종 수용 시험을 통과하지 못함.

원장 `status=done`은 해당 **원작 외형 및 행동 수용 조건 전체**가 검증됐을 때만 사용한다. 기존 스프라이트 추출률, 정상 배포, CSS 보정은 **부분 진도**이지 완료 비율이 아니다.

## 개발에서 절대 소실하지 말아야 할 P0

- `P0-BOARD`: 145×97 TIS 육각 발판의 상하/윗면/겹침/깊이/투영.
- `P0-ACTOR`: 98종 원본 창세기전 OBS 전신, 캐릭터별 방향·상태 애니메이션.
- `P0-PODIUM`: 원본 전투 발판과 카메라·발 접지.
- `P0-DICE`: 원본 주사위 결과별 실제 낙하·반동·정지.
- `P0-CHAT`: 북·남 하이아칸 상설 채팅방 원본 가구/좌석/유저 목록/실시간 채팅.
- `P0-RELEASE`: 동일 게임상태 원작 스크린샷 비교 + 실제 기기/다중 브라우저 + 배포 SHA 통합 수용.

원본 3D 바이너리, 소스 파일, 참고 영상이 부족하면 반드시 추출기/아카이브/패턴 비교 등 우회 경로를 조사하고 `events`에 결과를 남긴다. 원장에 있는 미완료 업무가 사용자 요청 삭제와 함께 사라지면 안 된다.
