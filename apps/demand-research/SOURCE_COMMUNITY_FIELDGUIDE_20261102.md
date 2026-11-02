# 교집합 | SNS 추가 수집 기술·커뮤니티 논의·실측 보고서

조사: 2026-11-02. 대상: GitHub 오픈소스와 Issues·PR·댓글, Reddit r/rss·r/OSINT 사용 후기, DEV 개발기, 공식 API·무료 요금·쿼터 문서, GitHub Actions에서의 실제 무료 통신.

**목표:** 유료 SocialCrawl 없이, 신규 공개 SNS 게시글의 발견 → 원본 내용·게시일 확인 → 정확한 중복 제거 → 교집합 통합 피드 표시를 개선한다. 인덱스 링크 후보를 원문 수집 완료로 계산하지 않는다. 이번 PR은 연구·테스트이며 운영 수집 엔진은 바꾸지 않는다.

## 확인한 프로젝트·도구와 적용 가능성

| 기술 | 역할 | 유용한 기능 | 실제 조건·한계 |
|---|---|---|---|
| RSSHub | SNS별 공개 페이지 전용 추출기 | Threads 검색 HTML의 JSON 내 글·작성일·미디어 필드; Instagram 공개 프로필 | 일부 공용 RSSHub 403, Instagram 비로그인 IP별 접근 편차; 해시태그에 쿠키 |
| RSS-Bridge | 공개 홈페이지 → 피드 | Threads 프로필에서 개별 글·OG·게시일, 다수 사이트별 브리지 | 전역 키워드 검색이 아니라 프로필 단위 |
| gallery-dl | 공개 원문 링크의 미디어·메타데이터 추출 | X·Instagram·Reddit 등 여러 추출기 | 일부 쿠키 필요, 링크 발견 기능은 별도 |
| yt-dlp | 동영상 메타정보 | TikTok·Instagram·X·YouTube 영상의 형식과 메타정보를 다운로드 없이 점검 가능 | 소스·시기별 불안정; 글로벌 키워드 검색 해결 안 됨 |
| Harken | 소스별 커서·날짜·오류 분리 | 페이지별 수집 인터페이스와 증분·SQLite | X 토큰/Reddit OAuth |
| OpenMagpie | 커넥터·피드·필터 | 소스별 독립 장애 처리, 정규화 | 일부 SNS 인증과 유지보수 |
| Grass | 검색 키워드 원샷 CLI/CI | 플랫폼별 RSS/검색, SQLite, GitHub Actions 잡 구조 | 소스별 API 제한 |
| Huginn | 오픈소스 워크플로 | RSS/웹 감지→이벤트→변경분 처리 | 직접 원본 검색을 만들어 주지는 않음 |
| changedetection.io | 공개 URL 감시 | 알려진 공개 계정·사이트의 새 글 알림·변경점 | SaaS는 유료, 자체 호스팅 필요 |
| Crawlee·Scrapy·Playwright | HTTP/동적 HTML 파서·URL 큐 | 전용 커넥터의 재시도·저장·검증·테스트 | 무료 라이브러리지만 서버·브라우저 실행 자원 필요 |
| Bluesky Jetstream v2 | 공개 실시간·리플레이·스냅샷 | 검색 AppView의 최신성 누락 보완 | Bluesky 전용, 전역 스트림 처리 필요 |
| Mastodon/Pixelfed 해시태그 | 공개 인스턴스별 태그 피드 | 직접 글·시각 추출 | 전체 네트워크 풀텍스트가 아니며 서버별 접근 제한 |
| Nostr NIP-50 | 여러 릴레이 분산 키워드 검색 | 서로 다른 릴레이 결과를 합집합 | 일부 릴레이만 지원, 한국어 대상 성과 낮음 |
| Arctic Shift | Reddit 공개 자료 아카이브 | subreddit 범위 제목·본문·기간 검색, 댓글 트리, RSS/JSONFeed, 대량 덤프 | 검색에 subreddit/author 범위 제약, 429/시간초과, Reddit 약관 고려 |
| Telegram t.me/s | 선택된 공개 채널 웹 피드 | 최근 공개 메시지 HTML | 전체 Telegram 검색이 아님 |
| Cloudflare Workers + D1 Free | 수집 캐시 API·작은 DB | 브라우저별 중복 API 6회 호출 절약, 0원 무료 사용 범위 | Worker CPU 10ms/요청; D1 일간 한도; 계정 연결/배포 필요 |

추가 경로: Meta 공식 설명에 따르면 공개 Threads 계정이 **Fediverse 공유를 선택적으로 켜면** Mastodon 등 ActivityPub 서버가 그 게시글을 볼 수 있다. 이 경우 Threads 키워드 검색과 별개의 공개 수집 경로가 생길 가능성이 있다. **일반 Threads 계정 전체의 게시물을 무료로 읽는다는 뜻이 아니며, 교집합의 이 경로 실측은 미완료**.

근거 및 자료실:
- https://github.com/DIYgod/RSSHub
- https://github.com/RSS-Bridge/rss-bridge
- https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md
- https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
- https://github.com/VladUZH/harken
- https://github.com/obris-dev/openmagpie
- https://github.com/jaxxstorm/grass
- https://github.com/huginn/huginn
- https://github.com/dgtlmoon/changedetection.io
- https://crawlee.dev/python/docs/quick-start
- https://bsky.network/docs/jetstream/
- https://github.com/nostr-protocol/nips/blob/master/50.md
- https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md
- https://about.fb.com/news/2024/06/what-is-the-fediverse/

## 실제 개발자 댓글·PR·논의에서 얻은 사실

| 공개 자료 | 논의·수정의 핵심 | 교집합에 주는 교훈 |
|---|---|---|
| RSSHub #23652 + #23653 (2026-10-21) | Instagram GraphQL 주소 변경으로 공개 계정 수집이 중단. 유지보수자가 비로그인 공개 계정 두 곳에서 각각 33건 조회했다고 댓글. 다른 사용자는 쿠키가 있어도 실패 | 익명 공개 계정 수집은 가능 사례가 있으나 IP·세션 편차 큼. 단일 경로에 의존 금지 |
| twscrape #295 (2026-03~10) | X 최신 검색 커서가 멈춰 같은 글을 반복. 0.20.0 이후 정체 커서 감지/중복 처리 개선, 결과 상한은 남음 | 커서 진전 감시, 중복 방지, 검색 결과 실제 수집률 별도 측정 |
| twscrape #306, #309 (2026-05) | X GraphQL 변경 뒤 404/빈 객체, 아바타 빈 문자열 등 스키마 오류를 커뮤니티가 수정 | 소스 파서 버전별 검증, 결측 문자열을 “없음”으로 간주 금지 |
| Instaloader #2544 (2025~2026) | 로그인/세션이 있어도 태그 조회 403, 댓글 LoginRequired 등의 보고 | 계정 기반 유틸을 무키 무료 수집으로 분류 금지 |
| DEV Threads 검색 사례 (2026-09/10) | 검색 결과가 하나의 글이 아닌 대화와 답글 묶음을 포함. 일치하지 않는 상위 글을 수집하면 과대 집계, 루트 글만 읽으면 답글 누락 | 모든 답글에 원문 검색어 검증, root/reply 구분과 ID dedup |
| DEV Threads 모니터 (2026-09/10) | 직전 ID/고유 code를 저장해 새 글만 추가하는 증분 모니터. 빈 결과에 무한 반복하지 않음 | 최초 수집/재방문 분리, 마지막 ID·작성시각·건너뛴 ID 보존 |
| BrandBastion Threads KB (2026-08) | 민감한 검색어는 검색에서 제외될 수 있고 답글 크롤링도 제약 | 뒷계/섹트/일탈계 공백은 검색·색인 정책일 수 있음. 실제 차단어인지 확정 안 됨 |
| Reddit r/rss (2026-03) | RSS.app 웹페이지를 읽어 피드화한 방식은 유용하지만 비싸다는 사용자 경험, RSS-Bridge도 로그인 게이트로 실패 사례 | 광고성 “무료”와 실질 무료를 구분; 공개 콘텐츠 접근 조건에 따른 차단 가능 |
| Reddit r/OSINT (2025-04) | 공개 소스 코드·API 명시·진짜 무료 여부를 게시물 품질 기준으로 요구 | 과금 없는 공식 근거, 코드·실행 로그로 검증 |
| RSS-Bridge #5144/#5137 (2026-10) | XSS 필터와 임의 URL SSRF 취약점 제보 | 원문 HTML 그대로 삽입 금지, 서버 요청 도메인/경로 allowlist 필요 |

원문 댓글·문제 보고:
- https://github.com/DIYgod/RSSHub/issues/23652
- https://github.com/DIYgod/RSSHub/pull/23653
- https://github.com/vladkens/twscrape/issues/295
- https://github.com/vladkens/twscrape/issues/306
- https://github.com/vladkens/twscrape/issues/309
- https://github.com/instaloader/instaloader/issues/2544
- https://dev.to/matveyg/a-threads-search-result-is-a-thread-not-a-post-39b8
- https://dev.to/matveyg/scraping-meta-threads-without-a-login-what-the-search-page-actually-returns-2ngk
- https://www.reddit.com/r/rss/comments/1rp3fb5/twitter_instagram_threads/
- https://www.reddit.com/r/OSINT/comments/1jw2m5l/posting_about_new_toolsapps/
- https://github.com/RSS-Bridge/rss-bridge/issues/5144
- https://github.com/RSS-Bridge/rss-bridge/issues/5137
- https://help.brandbastion.com/en/articles/12087059-listen-to-keywords-on-threads

## 실제 무료 통신 테스트 — GitHub Actions

첫 실행:

| 테스트 | HTTP/결과 | VERIFIED 수준의 결론 |
|---|---|---|
| Instagram 공개 프로필 익명 웹 JSON 2개 | 429 × 2 | 이 러너에서는 해당 익명 API 차단 |
| Instagram 공개 프로필 HTML | 200, 약 418KB, JSON 스크립트 43개, OG 이미지 있음 | HTML 공개 진입과 일부 메타데이터만 확인; 게시글 33건 직접 확보는 아님 |
| Mastodon 공개 해시태그 coffee | 200, 10건·날짜 10개·본문 키워드 8개 | 무료 직접 수집 경로 확인 (대조군) |
| Mastodon 프로젝트 해시태그 | 200, 결과 0 | 프로젝트 키워드 신규 수집 확인 안 됨 |
| Telegram 공개 채널 | 200, 메시지 블록 20개 | 공개 채널의 자료 추출 가능 (글로벌 검색 아님) |
| Bluesky public.api.bsky.app | 403 | 이 호스트/요청 경로만 실패 |
| Arctic Shift subreddit 없는 제목·기간 검색 | 400 | 필수 범위 누락 가능; 방법 전체 불가능 아님 |

대체 경로 재시험:

| 테스트 | HTTP/결과 | 평가 |
|---|---|---|
| Bluesky api.bsky.app | 200, 공개 글 70개 | 정상 검색 성공. 표본 내 X/Threads/Instagram 게시글 정규 URL 공유 0개 |
| Bluesky bsky.social PDS 경로 | 401 | AppView가 아닌 호스트를 대신 사용하면 안 됨 |
| Instagram 익명 HTML 재조회 | 429 | 익명 HTML도 일정한 이용 가능성 보장 못함 |
| Arctic Shift subreddit=Coffee + title=coffee + 기간 | **200, 글 3개·작성일 3개** | 문서의 필수 subreddit 범위 보완 후 무료 실제 검색 성공 |
| Arctic Shift subreddit=Coffee 기본 피드 | **200, 글 3개·작성일 3개** | 커뮤니티 단위 새 글 수집 가능 |
| Arctic Shift subreddit=korea + query=일탈계 | 422 | 해당 한국어 검색 조합은 미검증, 다른 쿼리까지 일반화 금지 |

**특기사항:** Arctic Shift는 기존의 400 실패만 보고 배제했으나, 공식 문서가 제목 검색에 subreddit 또는 author 범위를 요구함을 확인하고 쿼리를 수정해 200으로 검증했다. 문서도 일부 오래됐음을 인정하므로 운영 시 요청 매개변수/정밀도 테스트 필요.

이전 PR #499에서 검증: Threads HTML 내 본문·날짜·미디어 추출은 일반 대조 검색어에서 성공. 프로젝트 검색어는 실제 원문 키워드 일치 0건. 검색인덱스 링크 → Threads 6개 원문에서 ID/시간/미디어 추출은 성공했지만 최근 32일·키워드 정확 일치 결과 0건.

## 정책·무료 이용 조건

- Threads 공식 키워드 검색은 threads_keyword_search 권한 승인 후 타인 공개 게시글 검색 가능. 승인 전에는 자신의 게시물에 제한. 일부 민감/공격적 용어는 빈 결과일 수 있다. 2,200 쿼리/유저/일, 반환 최대 100건 등 제한을 준수해야 한다.
- Instagram 비즈니스/크리에이터 해시태그 검색은 7일에 고유 해시태그 최대 30개. 자유로운 전체 본문 검색이 아니다.
- Mastodon 풀텍스트는 인스턴스 ElasticSearch·인증·공개 검색 동의에 의존한다. 공개 해시태그 검색과 혼동 금지.
- Reddit Data API는 OAuth 및 용도에 따른 승인, 특히 상업적 이용 시 별도 계약 조건이 있을 수 있다. Arctic Shift 공개 아카이브에서도 콘텐츠 재배포 정책을 별도로 검토해야 한다.
- Cloudflare Workers Free: 요청 100,000/일, CPU 10ms/요청, 50 서브요청/실행. 대형 Threads HTML을 매번 바로 JSON 파싱하는 작업에 CPU 한도가 걸릴 수 있다.
- Cloudflare D1 Free: 5,000,000 행 읽기/일, 100,000 행 쓰기/일, 데이터 5GB. 초과하면 자동 과금보다는 실패 처리한다.
- GitHub Actions schedule은 고부하 시간 지연·드롭 가능. 장기 실시간 수집 보장 엔진으로 단독 사용 부적합.

공식 자료:
- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data
- https://docs.joinmastodon.org/methods/search/
- https://support.hootsuite.com/hc/en-us/articles/1260804309709-Create-an-Instagram-stream
- https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md

## 우선순위 및 구현 제안

**P0. 신규 검증 글 수 증가에 직접 연결할 가능성이 높은 방법**

1. 다중 Discovery: 이미 검증된 무료 색인 KeenAble/Firecrawl에 공식 공개 페이지·태그·승인받은 피드를 추가해 소스별 URL 후보 확보.
2. Hydration 분리: 공개 출처마다 ID·본문·작성시각·미디어 메타를 소스에서 다시 가져온다. X FxEmbed 공개 단건 및 Threads 공개 원본 JSON/OG를 우선 확장.
3. 엄격한 정확도: Threads 답글/루트 글 구분 후 항목마다 본문/태그 검색어 검사. 원본 시간이 없는 검색인덱스 링크는 확정 건수에서 제외한다.
4. Arctic Shift 공식 파라미터 기반의 subreddit·기간 검색을 보조 공개 Reddit 피드로 구현하되 정책/공개삭제 준수.
5. 이미 본 소스 ID·커서·성공시각·ETag/마지막 변경을 서버측으로 보존해 새로 추가된 글만 보여준다. 일 방문자당 매번 외부 검색 API 6회를 다시 실행하는 현재 구조의 사용량을 줄인다.

**P1. 조건부 개발 / 일반 SNS 검색과 별도 모듈**

- 공개 Threads 계정의 ActivityPub opt-in 게시물, Mastodon/Pixelfed 여러 인스턴스, Nostr NIP-50 다중 릴레이, Telegram 공개 채널.
- Instagram 공개 사용자 피드(2026 유지보수 성공 사례, 해당 앱에서 HTTP 429). 한 IP 실패를 일반화하지 말고 별도 합법적·공개 대체 API/원문 HTML 추출을 검증.
- gallery-dl/yt-dlp 메타데이터 단건 추출, Crawlee URL 큐, Huginn/changedetection.io 변경 알림, Bluesky Jetstream v2.
- Cloudflare Worker+D1 Free를 작은 API/공유 캐시로 검토하되 **현행 계정 연결/호스팅이 배포된 것은 아니다**.

**P2. 단독 도입 효과 낮거나 현재 요구와 맞지 않음**

- 표본 70개에서 관련 외부 링크 0개였던 Bluesky 역교차링크 방식.
- Instagram 익명 REST/HTML만을 전용 단일 수집기로 지정(429 반복).
- RSSHub 공개 인스턴스 HTTP 403을 다른 인스턴스까지 일반화하거나 반대로 무제한 무료 수집 가능하다고 주장하는 것.
- 로그인 쿠키·토큰이 필요한 X 수집기를 키 없이 무제한 검색되는 도구처럼 설명하는 것.
- 유료 API·과금 자동 전환·인증우회·비공개 계정·무단 미디어 저장.

## 앞으로의 검증 지표

같은 기간과 같은 키워드 뒷계, 섹트, 일탈계에 대해 각 수집기별 **독립 고유 URL 후보 / 원본 텍스트 일치 / 실제 작성일 / 최근 기간 내 검증 글 / 기존 엔진 대비 추가 글 / 플랫폼별 403·429·타임아웃 / 요청당 비용**을 집계한다. 검증 안 된 검색엔진 스니펫을 수집 완료로 부풀리지 않는다.

실험 코드:
- apps/demand-research/probe_community_methods.py
- apps/demand-research/probe_community_second_paths.py
- 앞선 조사: apps/demand-research/SOURCE_METHOD_RESEARCH_20261102.md (PR #499)

**VERIFIED:** 위 실제 통신 표의 응답/건수 및 GitHub 공개 코드·이슈 댓글 인용. **INFERRED:** 후보를 조합한 새 아키텍처의 효과. **UNVERIFIED:** 3개 대상 키워드에 대한 신규 원문 확보율 상승, Instagram 익명 IP별 성공 일반화, Fediverse Threads 실수집, Cloudflare 운영 배포.
