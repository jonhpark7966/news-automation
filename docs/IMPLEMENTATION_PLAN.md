# 구현 계획

smol.ai AI 뉴스를 한국어로 번역하여 자동 발행하는 시스템 구현 계획입니다.

## 목표

1. smol.ai RSS 피드 모니터링
2. 새 뉴스 자동 크롤링
3. 한국어 번역 (LLM 사용)
4. 마크다운 파일 자동 생성
5. web 레포에 자동 커밋/푸시
6. Cloudflare Pages 자동 배포

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        news-automation                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   1. RSS    │───▶│  2. Crawl   │───▶│ 3. Translate│         │
│  │   Monitor   │    │   smol.ai   │    │   (LLM)     │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                               │                 │
│                                               ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  6. Deploy  │◀───│ 5. Git Push │◀───│ 4. Generate │         │
│  │  (자동)     │    │   to web    │    │   Markdown  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 구현 단계

### Phase 1: 수동 파이프라인 (MVP)

CLI 도구로 각 단계를 수동 실행

#### 1.1 RSS 피드 파서
- **파일**: `src/rss.py` 또는 `src/rss.ts`
- **기능**:
  - `https://news.smol.ai/rss.xml` 파싱
  - 새 이슈 URL 추출
  - 이미 처리된 이슈 스킵 (상태 파일 관리)
- **출력**: 처리할 URL 목록

#### 1.2 웹 크롤러
- **파일**: `src/crawler.py` 또는 `src/crawler.ts`
- **기능**:
  - smol.ai 페이지 크롤링
  - HTML → 마크다운 변환
  - 헤드라인 유무 판단
- **출력**: 원문 마크다운 + 메타데이터

#### 1.3 번역기
- **파일**: `src/translator.py` 또는 `src/translator.ts`
- **기능**:
  - LLM API 호출 (Claude API 또는 Codex CLI)
  - 프롬프트 적용 (헤드라인 유무에 따라)
  - 번역 품질 검증
- **출력**: 번역된 마크다운

#### 1.4 마크다운 생성기
- **파일**: `src/generator.py` 또는 `src/generator.ts`
- **기능**:
  - frontmatter 생성
  - 5줄 요약 추출
  - YouTube 템플릿 생성
  - 파일명 생성
- **출력**: 완성된 마크다운 파일

#### 1.5 웹 레포 연동
- **파일**: `src/publisher.py` 또는 `src/publisher.ts`
- **기능**:
  - web 레포 경로로 파일 복사
  - git add, commit, push 실행
- **출력**: 커밋 완료

### Phase 2: CLI 통합

단일 명령어로 전체 파이프라인 실행

```bash
# 단일 URL 처리
news-auto translate https://news.smol.ai/issues/26-01-16-chatgpt-ads/

# RSS에서 새 뉴스 처리
news-auto sync

# 상태 확인
news-auto status
```

### Phase 3: 자동화

#### 3.1 스케줄러 설정
- **방식**: crontab, systemd timer, 또는 GitHub Actions
- **주기**: 매 1시간 또는 매일 1회
- **로직**:
  ```
  1. RSS 피드 확인
  2. 새 이슈 있으면 처리
  3. 없으면 종료
  ```

#### 3.2 알림 시스템 (선택)
- 새 뉴스 발행 시 알림
- Discord 웹훅 또는 Slack

## 기술 스택 옵션

### Option A: Python

```
python 3.11+
├── feedparser        # RSS 파싱
├── httpx            # HTTP 클라이언트
├── beautifulsoup4   # HTML 파싱
├── markdownify      # HTML → Markdown
├── anthropic        # Claude API
├── pydantic         # 데이터 검증
└── typer            # CLI
```

### Option B: TypeScript/Node

```
node 20+
├── rss-parser       # RSS 파싱
├── node-fetch       # HTTP 클라이언트
├── cheerio          # HTML 파싱
├── turndown         # HTML → Markdown
├── @anthropic-ai/sdk # Claude API
├── zod              # 데이터 검증
└── commander        # CLI
```

### Option C: Bash + Claude Code

```bash
# Claude Code를 직접 호출하는 bash 스크립트
# 가장 단순하지만 제어가 어려움
```

## 상태 관리

처리된 뉴스를 추적하기 위한 상태 파일:

```json
// data/processed.json
{
  "lastChecked": "2026-01-18T12:00:00Z",
  "processed": [
    {
      "url": "https://news.smol.ai/issues/26-01-16-chatgpt-ads/",
      "date": "2026-01-16",
      "slug": "chatgpt-ads",
      "processedAt": "2026-01-16T15:30:00Z",
      "status": "published"
    }
  ]
}
```

## 파일 구조 (최종)

```
news-automation/
├── README.md
├── docs/
│   ├── MARKDOWN_GUIDE.md      # 마크다운 작성 가이드
│   └── IMPLEMENTATION_PLAN.md # 이 문서
├── prompts/
│   ├── with-headline.txt      # 헤드라인 있는 날 프롬프트
│   └── no-headline.txt        # 헤드라인 없는 날 프롬프트
├── examples/
│   ├── 2026-01-16-chatgpt-ads.md
│   ├── 2026-01-14-not-much.md
│   └── 2026-01-16.txt
├── src/
│   ├── rss.py                 # RSS 피드 파서
│   ├── crawler.py             # 웹 크롤러
│   ├── translator.py          # 번역기
│   ├── generator.py           # 마크다운 생성기
│   ├── publisher.py           # 웹 레포 연동
│   └── cli.py                 # CLI 엔트리포인트
├── data/
│   └── processed.json         # 처리 상태
├── output/                    # 생성된 파일 임시 저장
├── pyproject.toml             # Python 의존성
└── .env.example               # 환경변수 예시
```

## 환경 변수

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
WEB_REPO_PATH=/home/jonhpark/workspace/web
```

## 구현 우선순위

### 필수 (P0)
1. [ ] 웹 크롤러 - smol.ai 페이지 크롤링
2. [ ] 번역기 - Claude API 호출
3. [ ] 마크다운 생성기 - frontmatter + 본문

### 중요 (P1)
4. [ ] RSS 피드 파서 - 새 뉴스 감지
5. [ ] 상태 관리 - 중복 처리 방지
6. [ ] CLI 통합 - 단일 명령어 실행

### 나중에 (P2)
7. [ ] 웹 레포 자동 푸시
8. [ ] 스케줄러 설정
9. [ ] 알림 시스템

## 고려사항

### smol.ai 크롤링
- URL 형식: `https://news.smol.ai/issues/YY-MM-DD-slug/`
- 2자리 연도 사용 (26 = 2026)
- RSS: `https://news.smol.ai/rss.xml`

### 헤드라인 판단
- 페이지 제목 또는 본문에서 "not much happened" 포함 여부
- 또는 특정 섹션 존재 여부로 판단

### 번역 품질
- 1차: LLM 자동 번역
- 2차: (선택) 다른 LLM으로 검토
- 수동 검토는 선택적

### 에러 처리
- 크롤링 실패: 재시도 또는 스킵
- 번역 실패: 원문 보존 후 수동 처리
- 커밋 실패: 로컬에 파일 보존
