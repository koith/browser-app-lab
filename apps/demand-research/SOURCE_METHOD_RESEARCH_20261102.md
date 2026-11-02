# 교집합 | 유사 SNS 통합검색 서비스 벤치마크와 무료 수집 기술 검증

검증일: 2026-11-02 (GitHub Actions Ubuntu 공개 네트워크). **사이트의 공개 수집 방법/코드가 존재한다는 사실과 교집합 검색어로 실제 새 게시글을 얻었다는 사실은 구분한다.** 비용이나 접근 권한을 우회하는 수집은 범위에서 제외한다.

## 1. 참고한 서비스의 실질적인 아키텍처

| 서비스 / 프로젝트 | 공개적으로 확인한 실제 방식 | 교집합에 전용할 핵심 | 무료·권한의 한계 |
|---|---|---|---|
| Social Searcher | 자체 SNS 크롤링이 아니라 Google 기반 웹 검색을 결합하는 탐색 UI(공식 About) | 사이트별 URL 발견·중복 제거 | 게시물 원본/미디어/실제 날짜를 제공하지 않는다 |
| BuzzGlobe | 각 SNS 도메인의 Google 색인을 병렬 검색 | 플랫폼별 쿼리·원문 링크 정리 | 최신 1~2일 누락, Google 미색인 데이터 누락 |
| RSSHub | 수천 개의 사이트별 커넥터. 특히 Threads 검색 페이지의 `script[data-sjs]` 내 `thread_items` → `post.caption.text`, `post.taken_at`, 미디어 객체 추출 | **키워드 검색 결과의 원문/타임스탬프 검증 파서** | 공개 RSSHub 서버 403; 일부 SNS 피드는 인증 쿠키 필요. AGPL 라이선스 준수 |
| RSS-Bridge | Threads 공개 프로필 JSON에서 글 코드를 찾은 후 각 게시물의 og:description/og:image 등을 읽음 | Threads 개별 게시글의 원문 링크/메타 데이터 확인 | 키워드 전역 검색이 아니라 프로필 중심; Instagram 오래된 GraphQL 코드의 실제 동작은 미검증 |
| OpenMagpie | 각 SNS마다 교체 가능한 수집 커넥터 → 피드 → 관련성 검사 → 전달 | SNS별 커넥터 장애 격리·중복 수집 방지 | X 검색은 계정 세션 쿠키 필요, Instagram은 미구현/로드맵 |
| Harken | 커넥터 공통 `fetch_page(query,cursor,since)` 인터페이스. 날짜·정규화·증분 수집·SQLite | 검색 범위, 날짜 기준, 소스 에러를 분리하는 추상화 | X는 공식 API 토큰, Reddit은 OAuth 요구 |
| Folo | RSS/RSSHub를 모아 하나의 타임라인과 미디어별 레이아웃 구성 | 통합 카드/피드 렌더링과 재수집 절감 | 자체적으로 SNS 키워드 데이터 전체를 발견하는 엔진은 아니다 |
| SearXNG | 다중 검색엔진 메타검색을 자체 호스팅 | 검색엔진별 서로 다른 색인 결과의 합집합 | 무료 소프트웨어이지만 검색엔진 제한·CAPTCHA와 서버 운영비는 별도 |

공개 원문:
- https://www.social-searcher.com/about/
- https://buzzglobe.com/
- https://github.com/DIYgod/RSSHub/blob/master/lib/routes/threads/search.ts
- https://github.com/DIYgod/RSSHub/blob/master/lib/routes/threads/utils.ts
- https://github.com/RSS-Bridge/rss-bridge/blob/master/bridges/ThreadsBridge.php
- https://github.com/obris-dev/openmagpie
- https://github.com/VladUZH/harken/blob/main/src/harken/sources/base.py
- https://github.com/RSSNext/Folo
- https://searxng.org/

## 2. 실제 무료 통신 검증 (계정/토큰 없음)

### Threads 원본 페이지의 구조화된 JSON

직접 `https://www.threads.com/search?q=...`의 `serp_type=recent/tags/default` 페이지를 요청했고, HTML 내 공개 JSON을 **로컬 메모리에서만** 읽었다. 스크립트 내부의 공개 `code`, `caption.text`, `taken_at`, image/video 속성을 읽는 방법은 **코드 및 네트워크 모두 검증**했다.

| 검색어 | 모드 | 원문에 해당 검색어 포함 | 소스 작성일 | 최근 30일 |
|---|---|---:|---:|---:|
| 커피 (대조군) | recent | 19 | 19 | 4 |
| 커피 (대조군) | tags | 17~18 | 19~20 | 4 |
| 일탈계 | recent / tags | 0 | 0 | 0 |
| 뒷계 | recent / default | 0 | 0 | 0 |
| 섹트 | recent | 0 | 19 | 0 |
| 섹트 | default | 0 | 5 | 0 |

표에서 날짜 숫자는 해당 검색어를 포함한 글의 숫자가 아니라 **반환 구조 중 작성일이 있었던 글 수**다. 특히 섹트 결과는 검색어 본문 일치가 없었으므로 수집 성공 건수는 0이다. 결과 노출 부족의 이유가 콘텐츠 제한인지 미색인인지 아직 확인 불가.

### 검색엔진 발견 → Threads 공개 원문 검증

Keenable 무료 무키 검색으로 Threads 정규 링크를 찾은 뒤 **첫 번째 검색 API를 신뢰하지 않고** 원래 `www.threads.com/@handle/post/shortcode` 페이지를 재요청했다. 3개 검색어 × 2개 링크 = **6개 원문 URL**을 확인했다.

- 6/6 원본 페이지 HTTP 200, 원본 코드 일치 및 실제 `taken_at` 추출
- 6/6 게시글 이미지 관련 메타데이터 존재, 일부 og:description 제공
- **0/6 최근 32일**, **0/6 본문 검색어 정확히 일치**

따라서 **공개 원본의 날짜·이미지 추출 가능성은 VERIFIED**지만, 실제 현재 기간의 주제 맞는 게시물 수집 향상은 **미검증**이다.

### 실패 경로

- `rsshub.app/threads/search/*`: HTTP 403 (이 공유 인스턴스 접근 거부; RSSHub 자체 엔진이 불가능하다는 뜻 아님)
- `pixelfed.social/api/v1/timelines/tag/*`: HTTP 401 (이 인스턴스 공개 엔드포인트에서 인증 요구; 다른 인스턴스까지 일반화 불가)
- Google 색인만 쓰는 Social Searcher/BuzzGlobe 전략은 별도의 날짜 검증을 제공하지 않음.
- Instagram 해시태그 API: Meta Business/Creator 계정, Instagram Public Content Access 승인, 7일간 최대 30개의 고유 해시태그 제한.
- Threads 공식 키워드 검색: `threads_keyword_search` 승인 전 다른 사용자 글 검색 제한. 승인되더라도 검색어 또는 콘텐츠 정책에 따른 제한 가능.

## 3. 교집합에서 우선 도입해야 할 설계

1. **소스 탐색기(Discovery)**: 현재 무료 KeenAble/Firecrawl 외에 공식 공개 검색 페이지, 승인된 RSS/Atom, 여러 검색엔진의 각기 다른 결과를 추가. 출처가 여러 개인 동일 원본 URL은 중복 제거한다.
2. **원문 검증기(Hydration)**: 링크를 발견했다고 수집 완료 처리하지 않고, 가능한 경우 해당 SNS의 공개 원문 또는 허용된 공식 API를 직접 읽어 `id/code`, 작성시각, 본문, 공개 여부를 확인한다. Threads는 RSSHub가 쓰는 공개 HTML JSON 파싱을 후보로 둔다.
3. **결과 등급**: `index_candidate`(검색 주소만 있음), `source_metadata_verified`(원본 ID·작성일 확인), `source_content_verified`(원본 내용·검색어·공개 상태 확인). 실제 게시글 수는 마지막 두 등급 중 날짜와 검색어를 검증한 항목만 센다.
4. **증분 갱신 + 요청 제어**: 서비스별 마지막 성공 시각·커서/ETag·실패 사유를 분리하고, 적은 호출로 새 글만 확인. 검색엔진의 결과가 오래됐으면 오래된 원본을 무제한 반복 조회하지 않는다.
5. **모바일 통합 피드**: 사용자가 별도 검색 버튼을 누르지 않아도 결과를 하나의 피드에 표시하되, 날짜/원문 미확인 항목은 시각적으로 구분하고 허위 날짜를 생성하지 않는다.

### 플랫폼별 우선순위

- **X**: 이미 검증된 검색 인덱스 + 공개 단건 원문 검증. 날짜가 오래된 후보를 우선 제외하고 최근 원본 확인에 무료 요청을 집중한다.
- **Threads**: 검색엔진으로 공개 URL 발견 → 공개 원본 JSON/OG로 날짜 확인. 직접 Threads 검색 페이지도 검색어마다 대조. 단, 브라우저에서 원본 사이트 직접 호출 시 CORS가 걸릴 수 있으므로 서버 실행 계층을 별도로 검증한다.
- **Instagram**: 공개 검색 색인 → 공식 임베드/공개 원문 메타데이터 확인(게시 날짜가 실제로 나오는 경우만 확정). 공식 승인 없는 전역 키워드·해시태그 검색 가능성을 과장하지 않는다.
- **Reddit**: 공개 아카이브의 커뮤니티 검색과 승인된 공식 OAuth API를 별도 취급한다. 없는 권한을 우회하지 않는다.
- **Mastodon/Nostr/Misskey/Telegram/YouTube**: 공개 피드·릴레이·공식 API 또는 알려진 공개 채널만 증분 수집. 공개 키워드 검색이 된다는 주장보다 **실제 검색어 일치+최근 날짜+원문**을 기준으로 우선순위를 매긴다.

## 4. 이번 범위에서 구현한 것 / 구현하지 않은 것

**VERIFIED**: GitHub Actions로 Threads HTML 원문 필드·날짜·미디어 구조, Keenable 발견→Threads 원문 재조회, RSSHub 공개 인스턴스 제한과 Pixelfed 인증 응답을 실측했다.

**NOT YET INTEGRATED**: Threads의 자체 HTML 파서를 교집합 실제 프런트엔드/백엔드 운영 파이프라인에 연결하지 않았다. 브라우저와 서버의 접근/CORS 차이, 플랫폼 정책, 기간·검색어 정확도 및 새로운 실제 원문 확보율을 검증한 뒤 연결해야 한다.

검증 명령 (각 실행은 유한한 공개 요청만 생성):

```bash
python apps/demand-research/probe_competitor_sources.py
python apps/demand-research/probe_threads_index_to_original.py
python apps/demand-research/probe_threads_topic_variants.py
```

전체 실험은 **읽기 전용**이며, 사용자명·원본 URL·게시글 본문·미디어를 CI 출력이나 저장소에 기록하지 않는다.
