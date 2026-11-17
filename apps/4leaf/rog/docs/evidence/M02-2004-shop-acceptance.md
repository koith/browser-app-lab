# M02 — 켈티카 거리 / 매직카덴, 2004년 원작 화면 수용 근거

## 원작 자료
- 원본 캡처: `apps/4leaf/assets/shop_ref.png` (541×402, 브라우저 4LEAF 당시 상점 화면)
- 실제 거리 자산: `original/MainStreet/back.png` (1938×404), `MainStreet/card.png` 등 원본 건물 7개
- 2002 상점 자산: `original/CardShop/cardshopback.png` (794×404), `cardshopbutton.png`
- 2004 상점은 2002년 3×3 PAK 배경과 **다른 4×2 UI**이므로, PAK를 원본 2004 화면이라고 잘못 표시하지 않음.

## 2004 원작 스크린샷 대응 좌표

캡처 좌표에서 원작 794×404 장면으로 환산한 값. 2004 원본 캡처의 축척은 약 541/794.

| 2004 원작 요소 | 원본 794px 장면 좌표 (x, y) | 실제 HTML 구현 대상 |
| --- | --- | --- |
| Normal / Valuable / Rare | (32,15) / (134,15) / (233,15) | `.group-tab[data-group]` |
| 첫 카드 / 2열 첫 카드 | (47,56) / (47,145) | `#shop-grid .shop-card` |
| 착용목록 | (402,32) | `.shop-equipped` |
| 보유 GP | (402,294) | `.shop-keeper .money` |
| Card Info | (32,260) | `.shop-detail` 및 원작 표제 |
| 구매하기 / 판매하기 | (402,333) / (505,333) | `#shop-buy` / `#shop-sell` |

정량 비교의 통과 기준: 두 브라우저의 실제 장면 좌표를 source 794×404로 역변환한 10개 기준 지점의 최대 위치 오차 4px 이내. 실제 2004 캡처와 같은 4×2 카드 구성 및 세 등급 탭을 사용.

## 기능 연결 및 비원작 요소 분리

- 월드맵 → 켈티카 거리 → 원본 MainStreet 건물의 불투명 픽셀 클릭 → 매직카덴 진입. 문은 단순 메뉴 링크가 아니라 해당 원본 건물 아트의 실제 클릭 영역.
- 구매·판매·GP 저장은 기존 `game.js` 거래 경로를 유지하며, 별도 `SHOP-02`에서 경제 규칙의 원본 일치 여부를 추적한다.
- 임의의 `전체` 및 2002/2004 연도·시세 비교 UI, 자료 출처 안내는 **원작 그림 밖 MainFrame 툴바**에만 배치. 해당 UI를 원작 요소로 위장하지 않음.
- CardData 인물의 얼굴 `chm_N` 실제 매핑은 미확보. 해당 자료 수용은 별도의 `ACT-05`에서 진행한다. M02의 UI 위치 검증을 원본 초상화 복원으로 혼동하지 않는다.
- 2002년형 3×3 원본 상점도 연도 전환으로 유지한다.

## 실제 검증

- M02 원본 UI 선행 E2E: https://github.com/koith/browser-app-lab/actions/runs/44065966157 (Chromium/WebKit 실제 켈티카 문 클릭·2002/2004 상점 진입)
- 정량 A/B 소스 좌표 검사 및 2004 화면 스크린샷: `tests/m02-real-scene-snapshot.cjs` / `.github/workflows/4leaf-m02-original-shop-acceptance.yml`
- 기존 카드 구매·판매 내구성 검증: https://github.com/koith/browser-app-lab/actions/runs/44044382651
- 공개 Pages 배포 일치 확인: `.github/workflows/4leaf-public-pages-mobile-gate.yml`에서 버전과 상점 JS·CSS/거리 스크립트의 실제 배포 바이트 대조.

**주의:** 이 문서는 M02 상점·문·구매 UI 수용 범위의 근거이다. 원본 2004 EXE의 미수집 상품·초상화·경제 규칙이나 다른 원장의 일감을 자동으로 완료 처리하는 자료가 아니다.
