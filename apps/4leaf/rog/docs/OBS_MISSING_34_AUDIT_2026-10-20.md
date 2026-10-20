# 4LEAF 원본 OBS 미복원 34종 — 실제 아카이브 진단 (2026-10-20)

**완료 상태:** ACT-01 원작 복원 **미완료**. 이 문서는 설치 파일·PAK 원본과 변환 결과의 실측 보존이며 새 포즈/모델 복원 성공을 주장하지 않는다.

## 신뢰 가능한 자료

- `original/OBS/bulk-source-report.json` (전수 조사 `OBS.pak`, SHA256 `49738a942ffe3856fb86b4c5ce698b7e460bb876b38c31884028b3e2e833d514`).
- 원본 2002 설치 archive.org 4leaf ZIP SHA1 `86526d89679ae39b85fe9808da97ad871b7888d9`를 Actions에서 검증 후 읽기 전용 Cab 추출. **원본 EXE/DLL 실행하지 않음**.
- `decode-original-obs-bulk.py`: 파레트/픽셀 행의 엄격 해독, X 좌표는 중심 보정한 WEB 임시 렌더. **원본 EXE의 run-X 인코딩 미확인**.
- `probe-original-obs-near-rows.py` / `probe-original-obs-640stride.py` / `probe-original-obs-secondary-paks.py`: 미승인 리소스 후보의 격리 조사. 불확실 픽셀을 4LEAF 원본으로 사칭하지 않는다.

## 수량 대조

| 범위 | 확인 수량 | 근거 |
| --- | ---: | --- |
| 원본 체스맨 CardData | 98종 | `original/chessmen.json` |
| 기존 처음 복원 OBS 1042/1045 | 2종 / 13 PNG | `original/OBS/animation-manifest.js` |
| OBS.pak 벌크 대상 CardData 멤버 | 90종 | `bulk-source-report.json.cardMembers`; 1042·1045는 벌크에서 제외 |
| 엄격 해독 성공 멤버 | 62종 / 268 PNG | `bulk-source-report.json.accepted/framePNGs` |
| 총 확보 소스 OBS 몸체 | **64/98종, 281프레임** | 벌크+1042/1045 |
| 해독 실패 실제 PAK 멤버 | **28종** | 아래 28개 파일명 |
| 98 카드에서 원본 미복원 | **34종** | 원본 3D·프레임 전체 복구와는 별개 |
| 위 멤버 총량으로 설명하지 못한 남은 약 6종 | **ID 직접 재대조 필요** | 98−(90+2)=6. 아카이브 멤버 누락 *추론*, 별도 클라이언트 버전/원본 data 파일 확인 전 확정 불가 |

## 해독에 실패한 28개 실제 멤버

**no strictly decoded source frames (24종):** `1046.obs`, `1061.obs`, `1064.obs`, `1085.obs`, `1087.obs`, `1092.obs`, `1096.obs`, `1099.obs`, `1100.obs`, `1128.obs`, `1134.obs`, `1135.obs`, `1137.obs`, `1138.obs`, `1139.obs`, `1143.obs`, `1146.obs`, `1156.obs`, `1161.obs`, `1162.obs`, `1163.obs`, `1164.obs`, `1165.obs`, `1166.obs`

**OBS frame geometry invalid (3종):** `1093.obs`, `1098.obs`, `1159.obs`

**Implausible OBS frame count (1종):** `1095.obs`

**발견된 원인:** 스프라이트 자체가 없다는 뜻이 아니다. 24건은 스캔라인 헤더로 원본 높이와 정확하게 일치하는 행을 복원하지 못했고, 3건은 멤버 프레임 크기/바이트 구조가 현재 디코더 가정과 맞지 않으며, 1건은 현재 위치의 프레임 카운트 값이 타당 범위를 벗어났다. 이는 해당 멤버가 원래 더미였다는 증거도, 유효한 전신 이미지라는 증거도 아니다.

## 다음 합리적인 대체 조사 경로

1. **먼저** 24개 근접-행 실패의 `decodeDiagnostics.nearby`와 원본 `4byte` 헤더를 보존한 다음, 잘못 인식한 행 마커와 픽셀 run 시작 위치를 검증 가능한 파일별 바이트 수식으로 역산한다. 임의 행 삽입·가짜 색상 생성은 격리된 preview까지만 허용한다.
2. `OBS2.pak`, `OBS3.pak`가 실제 포즈 소스인지 중복/별도 자산인지 PAK 이름·파일 헤더·일치 SHA/프레임수로 독립 검증한다.
3. 3개 geometry/1개 frameCount 예외에는 카드/OBS 페이로드 헤더 오프셋과 계수 인코딩을 원본 zip 내 다른 멤버와 교차 비교한다.
4. 다른 버전의 원본 클라이언트 자료·원작 게임 영상과 캐릭터별 실루엣, 방향 및 포즈 변화를 비교해 데이터 프레임 배열의 실제 의미와 재생속도를 확정한다.
5. 검증된 원본 픽셀 SHA와 캐릭터 ID/프레임 인덱스·원점을 `animation-extra.js`에 기록하고 실제 플레이 중 동작·접지·모바일/browser QA 및 배포 SHA까지 입증할 때만 ACT-01/03 세부 완료를 검토한다.

## 2026-10-20 이번 코드 변화와 분리

- **PR #149:** 32종 TIS 실제 source alpha 픽셀 클릭·상하 반전·줌 보강. 실게임 말판 원작 3D 투영 완성은 아님.
- **PR #150:** 이미 복원된 소스 OBS PNG가 503/network transient 후 원본 카드 초상화에 영구 머무르지 않도록 한정 재시도 및 온라인 원본 재로딩. 34종 원본 신규 복구를 의미하지 않음.
- 본 문서는 **ACT-01 출처 재조사**로 기록. 정확한 OBS 몸체 34종 복원, 원본 EXE의 행동별 포즈 표와 MVE 메시·주사위는 미해결.
