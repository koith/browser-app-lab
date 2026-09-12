# 당근 통합검색 v2.1 QA / 운영 기준

## 3. 배포 반영 확인
- production entry: `apps/daangn-search/index.html`
- v2.1 entry: `index.v21.html`
- backend: Vercel `/api/daangn*`
- GitHub Pages는 `index.html`에서 v2.1로 redirect한다.

## 4. 현재 검색 장애 재현/진단
- 백엔드 세 검색 API는 `errors`, `blockedCount`, `okRegionCount`를 반환한다.
- 차단성 작은 HTML은 정상 0건으로 숨기지 않는다.
- 마지막 검색 진단은 브라우저 localStorage `dgn_diag_v21`에 저장한다.

## 5. 21 distinct-region 임계 대응
- 진단 endpoint: `/api/daangn-probe`
- 운영 검색은 3동씩 호출한다.
- 서로 다른 18동 처리마다 10초 안정화 대기를 넣어 관측된 21지역 경계 안쪽에서 파동을 끊는다.

## 6. 운영 설정
- MAX_DONGS: 200
- BATCH: 3
- normal inter-batch gap: 2.5s
- wave: 18 regions
- wave cooldown: 10s
- first-pass failed regions: 8s 후 1회 자동 재시도
- 최종 실패는 수동 `실패 지역 다시 검색`으로 재조회한다.

## 7. 세션 리셋이 충분하지 않은 경우
- 결과를 성공으로 위장하지 않는다.
- 실패 지역 코드를 보존하고 성공 지역 결과는 유지한다.
- 전체 검색을 처음부터 반복하지 않고 실패 지역만 재조회한다.

## 8. 탭별 검증 항목
- 중고거래: title / price / status / image / sortTime / boostedAt / URL
- 모임: title / members / place / description / image / URL
- 동네생활: title / description / image / author / sortTime / URL
- 세 탭 모두 blocked page가 `errors`로 노출되어야 한다.

## 9. 결과 정확도 정책
- URL 기준 중복 제거.
- 정상 크기 HTML의 0건은 진짜 0건으로 인정.
- 작은 차단성 HTML은 0건으로 인정하지 않음.
- 정렬/필터는 수집 완료된 결과에 대해서만 수행.

## 10. 지역/200동 상한
- 구→동 결과는 24시간 TTL 캐시.
- 동 목록 조회 실패 시 1회 짧은 재시도.
- 선택 단계에서 실제 동 개수를 계산해 200동을 넘기지 않는다.

## 11. 실패 UX
- 정상 지역 / 실패 지역 / 차단응답 / 동 목록 실패 수를 별도 표시.
- 첫 실패는 자동 재시도.
- 남은 실패는 버튼으로 실패 지역만 재검색.
- 성공 결과는 실패 재시도 동안 유지.

## 12. 부하 테스트 기준
실제 운영 검색에서 10 / 30 / 60 / 100 / 150 / 200동을 순차 확인한다. 각 검색 뒤 `dgn_diag_v21`에서 `codes`, `ok`, `failed`, `blocked`, `recovered`, `sec`를 기록한다. 목표는 결과 누락을 숨기지 않는 것과 검색 규모가 증가해도 성공 결과를 보존하는 것이다.

## 13. 운영 확정
- 실험용 URL `batch/gap` 조절 방식은 production 기본 동작에서 제거.
- v2.1은 고정된 보수적 운영값과 실패지역 재검색을 사용한다.
- Daangn 렌더링/차단 정책 변화 시 `/api/daangn-probe`와 저장된 진단값을 먼저 확인한 뒤 수치를 조정한다.

## 제한
현재 저장소에는 GitHub Actions 기반 브라우저 E2E가 없다. Vercel/Daangn 실제 네트워크 응답에 의존하는 항목은 배포 후 실제 호출에서 최종 확인해야 한다. 코드가 실패를 정상 0건으로 숨기지 않도록 설계되어 있으므로 이 검증 결과는 화면과 `dgn_diag_v21`에 그대로 드러난다.
