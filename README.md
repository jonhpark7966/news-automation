# news-automation

smol.ai AI 뉴스를 한국어로 번역하여 sudoremove.com에 자동 발행하는 시스템

## 개요

[smol.ai AI News](https://news.smol.ai)를 한국어로 번역하고, [sudoremove.com/news](https://sudoremove.com/news)에 게시하기 위한 자동화 도구입니다.

## 현재 상태

🚧 **개발 중** - 아직 구현되지 않음

현재는 문서와 프롬프트만 준비되어 있습니다:
- 번역 프롬프트
- 마크다운 생성 가이드
- 구현 계획

## 디렉토리 구조

```
news-automation/
├── README.md                      # 이 문서
├── docs/
│   ├── MARKDOWN_GUIDE.md          # 마크다운 작성 가이드
│   └── IMPLEMENTATION_PLAN.md     # 구현 계획
├── prompts/
│   ├── with-headline.txt          # 헤드라인 있는 날 번역 프롬프트
│   └── no-headline.txt            # 헤드라인 없는 날 번역 프롬프트
├── examples/
│   ├── 2026-01-16-chatgpt-ads.md  # 예시: 헤드라인 있는 날
│   ├── 2026-01-14-not-much.md     # 예시: 헤드라인 없는 날
│   └── 2026-01-16.txt             # 예시: YouTube 템플릿
└── src/                           # (미구현) 소스 코드
```

## 워크플로우

```
smol.ai RSS 피드 확인
       ↓
새 뉴스 크롤링
       ↓
한국어 번역 (LLM)
       ↓
마크다운 파일 생성
       ↓
web 레포에 푸시
       ↓
Cloudflare Pages 배포
```

## 출력물

### 1. 웹 포스팅

`web/src/content/ainews/ko/YYYY-MM-DD-slug.md`

- 5줄 요약 (상단)
- 헤드라인 (있는 경우)
- AI Twitter/Reddit/Discord Recap
- 원문 링크 (하단)

### 2. YouTube 템플릿

`web/src/content/ainews/youtube/YYYY-MM-DD.txt`

- 5줄 핵심 브리프
- 웹 포스팅 링크

## 문서

- [마크다운 생성 가이드](docs/MARKDOWN_GUIDE.md) - 마크다운 파일 형식 및 규칙
- [구현 계획](docs/IMPLEMENTATION_PLAN.md) - 상세 구현 계획

## 수동 번역 (현재)

구현 전까지는 다음 방식으로 수동 번역:

1. smol.ai 페이지 내용 복사
2. `prompts/` 의 프롬프트와 함께 LLM에 입력
3. 번역 결과를 `examples/` 형식에 맞춰 마크다운 작성
4. web 레포의 `src/content/ainews/ko/`에 저장
5. git commit & push

## 관련 레포

- [web](https://github.com/sudoremove/web) - sudoremove.com 웹사이트

## TODO

- [ ] RSS 피드 파서 구현
- [ ] 웹 크롤러 구현
- [ ] 번역기 구현 (Claude API)
- [ ] 마크다운 생성기 구현
- [ ] CLI 통합
- [ ] 자동화 스케줄러
