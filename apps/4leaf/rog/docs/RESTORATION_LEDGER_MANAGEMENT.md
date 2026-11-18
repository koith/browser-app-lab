# 4LEAF 원작 복원 — 개발원장 운영 방식 (2026-11-16 개편)

## 한눈에 보는 구조

- **일감의 기준:** [GitHub Issues 검색](https://github.com/koith/browser-app-lab/issues?q=is%3Aissue+%5B4LEAF%5D) — 제목의 `[4LEAF][ID]`를 고유 식별자로 사용
- **경량 상태:** [RESTORATION_STATUS.json](./RESTORATION_STATUS.json) — 60건의 ID/우선순위/상태/Issue 링크만 유지. 자동 생성이며 **직접 편집 금지**
- **과거 근거 보관:** [RESTORATION_LEDGER.json](./RESTORATION_LEDGER.json) — 기존 101건 요청·486건 이벤트·상세 검증 증거를 보존한 **레거시 기록물**. 일반 작업 중 전체 파일 조회·이력 추가 금지
- **새 대화 인수:** [CHAT_HANDOFF_BRIEF.json](./CHAT_HANDOFF_BRIEF.json) — Issues 상태와 동시 자동 생성되는 초경량 파일. 수치가 어긋나면 GitHub Issue 실시간 상태가 우선. 전체 원장·과거 채팅 전문은 불러오지 않음

원본 60건을 GitHub Issue로 전부 이관: **43건 기존 완료(닫힘), 16건 진행, 1건 시작 전**. 이는 기록 이관이며 새 기능 완료 실적이 아니다.

## 운영 절차

1. 시작: `RESTORATION_STATUS.json`만 확인해 미완료 ID·우선순위 추출. 불일치하면 GitHub Issues 실시간 상태가 우선
2. 작업: 해당 Issue의 **원작 수용 조건** 확인. 필요할 때만 기존 원장의 해당 증거를 찾아 읽기
3. 코드: 별도 PR에서 수정, 테스트·원작 화면 비교, 공개 배포 확인을 검증 증거로 남기기
4. 완료: 해당 Issue에 구체적 코드/PR·브라우저 검증·원작 비교 증거를 추가하고 검수한 다음 닫기. **PR 병합만으로 완료 판정 금지**
5. 보고: 이번 회차 신규 완료 ID와 근거, 기존 완료 누계, 남은 ID를 분리해서 짧게 보고
6. 새 요청: 기존 ID 중복 검사 후 Issue 생성. 기존 60건의 코어 일감과 하위 버그를 중복 완료 실적으로 세지 않기

## 수용 조건 자동 게이트

과거 원장에서 `done`으로 이관한 43건은 과거 근거에 따라 닫힘 상태를 보존한다. **이후 새로운 완료**는 Issue 본문에 다음 표시와 실제 테스트·원본 비교 근거 URL이 있어야 경량 상태에서 `done`으로 계산한다.

```text
<!-- 4LEAF-ACCEPTED-WITH-EVIDENCE -->
검증: PR/CI 링크, Chromium 및 WebKit 브라우저 시나리오, 원작 스크린샷 비교, 공개 배포 확인
```

닫힌 Issue라도 요건이 없으면 `review_required`로 분류하며 완료 누계에 넣지 않는다. 검증 링크는 존재 여부만 자동 판별하므로 실제 근거의 타당성은 추가 수용 검토가 필요하다.

## 동기화와 실패 방지

- 생성기: `../scripts/sync_restoration_issues.py` (STATUS와 HANDOFF를 한 번에 생성) (Python 표준 라이브러리만 사용)
- 회귀 테스트: `python -m unittest discover -s apps/4leaf/rog/scripts -p test_sync_restoration_issues.py -v`
- Actions: `.github/workflows/4leaf-restoration-status-sync.yml` — Issue 변경과 워크플로 수동 실행 시 재생성. 주기적 빈 자동 실행 없음
- 보호: GitHub 검색 결과가 비어 있거나 불완전하면 파일을 덮어쓰지 않음. 기존 ID 누락·중복이 있으면 실패하도록 설정
- GitHub Actions 쓰기 권한이 차단되면 동기화는 실패할 수 있음. 이 경우 상태는 Issues가 기준이며 스냅샷은 마지막 성공 값임. 워크플로 로그부터 확인
- 오래된 대화 전체·58만 자 원장·장문의 테스트 로그를 ChatGPT 대화로 출력하지 않음

**주의:** 기존 `RESTORATION_LEDGER.json` 경로를 참조하는 구형 자동화의 사용처는 전수 확인되지 않았다. 호환성 파괴를 피하기 위해 기존 파일은 삭제·축약하지 않았으며, 새 관리 경로로 전환한 뒤 의존성 검증 없이 제거하지 않는다.
