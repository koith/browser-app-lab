# AIOS Kernel v0.1

> AIOS는 AI를 호출하는 프로그램이 아니다. **AI 조직을 운영하는 운영체제**다.
> 출판사·게임 스튜디오는 이 커널 위에서 실행되는 App일 뿐이다.

커널이 제공하는 시스템콜은 6개뿐:
**Task 생성 → Agent 선택 → 회의 → 반론/토론 → 결론 → 회고/경험 저장.**
콘텐츠 생성은 커널에 없다.

## 실행

```bash
cd apps/AIOS
python3 main.py                 # LLM 없이(MockProvider) 전체 흐름 데모
pip install pytest && pytest    # SQLite/JSON 양쪽 저장소로 전 테스트 실행
```

데모에서 확인되는 것:
1. Task 하나로 회의(제안→반론→재반론→결론→회고→경험저장)가 이벤트로 완주
2. 편집장 피드백 "제목이 너무 길다" ×3 → Rule 승격
3. 다음 회의부터 기획 AI 프롬프트에 해당 Rule 자동 주입
4. 같은 커널 위에서 GameStudioApp 동작 (커널 수정 0줄, Rule 격리)

## 구조

```
aios/kernel/     커널 코어 — App은 수정 금지. 모듈 간 통신은 MessageBus만.
aios/drivers/    HAL — LLMProvider(Mock/Anthropic), Storage(SQLite/JSON)
aios/plugin/     Plugin SDK — OrgApp, AppLoader
aios/apps/       사용자 공간 — publishing, gamestudio (예시 조직)
tests/           DoD 검증 (E2E, Rule 승격, 저장소 Liskov)
docs/DESIGN.md   전체 설계 문서 (아키텍처·클래스/시퀀스 다이어그램·로드맵)
```

핵심 설계 원칙:
- **Event Driven**: Agent끼리는 물론 커널 내부 모듈도 서로 직접 호출하지 않는다.
- **Experience ≠ 학습**: 인간 피드백 → 교훈 정규화 → 후보 누적 → 임계(3회) 도달 시 Rule 승격.
- **Rule의 쓰기 경로는 승격 하나뿐**. RuleMemory는 읽기전용 뷰, 편집장은 deactivate 거부권 보유.
- **SOLID 교체 지점**: LLMProvider / Storage / ConsensusPolicy / AgentSelector.

상세 설계는 [docs/DESIGN.md](docs/DESIGN.md) 참고.

## 모바일 웹 콘솔 (iPhone)

`web/index.html` — 커널의 JavaScript 포트. 서버 없이 브라우저 단독으로 동작하며
규칙·경험·이벤트는 기기 localStorage에 저장된다.

- GitHub Pages: `https://koith.github.io/browser-app-lab/apps/AIOS/web/`
- Safari에서 열고 공유 → **홈 화면에 추가** 하면 전체화면 웹앱(웹뷰)으로 실행
- 기본은 Mock 엔진(오프라인). 설정(⚙︎)에서 Anthropic API 키를 넣으면 실제 Claude가 회의 진행
