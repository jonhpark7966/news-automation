# 마크다운 생성 가이드

sudoremove.com의 AI 뉴스 섹션에 게시하기 위한 마크다운 파일 작성 가이드입니다.

## 파일 위치

번역 완료된 마크다운은 **web 레포**의 다음 위치에 저장해야 합니다:

```
web/src/content/ainews/
├── ko/                              # 웹 포스팅용 마크다운
│   └── YYYY-MM-DD-slug.md           # 예: 2026-01-16-chatgpt-ads.md
└── youtube/                         # YouTube 커뮤니티 템플릿
    └── YYYY-MM-DD.txt               # 예: 2026-01-16.txt
```

## 파일명 규칙

- 형식: `YYYY-MM-DD-slug.md`
- slug는 smol.ai 원문 URL에서 가져옴
- 예: `https://news.smol.ai/issues/26-01-16-chatgpt-ads/` → `2026-01-16-chatgpt-ads.md`

## Frontmatter 스키마

### 필수 필드

```yaml
---
title: "뉴스 제목 (한국어)"
summary:
  - "요약 1줄"
  - "요약 2줄"
  - "요약 3줄"
  - "요약 4줄"
  - "요약 5줄"
date: 2026-01-16
originalUrl: "https://news.smol.ai/issues/26-01-16-slug/"
hasHeadline: true
---
```

### 선택 필드

```yaml
headline: "헤드라인 제목"   # hasHeadline이 true일 때만
tags:
  - OpenAI
  - Claude
isFeatured: false          # 기본값: false
```

## 필드 상세 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `title` | string | O | 뉴스 제목 (한국어) |
| `summary` | string[] | O | **정확히 5줄** - 핵심 요약 |
| `date` | date | O | 뉴스 날짜 (YYYY-MM-DD) |
| `originalUrl` | string | O | smol.ai 원문 URL |
| `hasHeadline` | boolean | O | 헤드라인 유무 |
| `headline` | string | X | 헤드라인 제목 (hasHeadline=true일 때) |
| `tags` | string[] | X | 태그 목록 |
| `isFeatured` | boolean | X | 주요 뉴스 여부 |

## 본문 구조

### 헤드라인이 있는 날

```markdown
---
(frontmatter)
---

## 헤드라인: [제목]

헤드라인 상세 내용...

---

## AI Twitter Recap

### 소제목 1
내용...

### 소제목 2
내용...

---

## AI Reddit Recap

### r/LocalLLama & r/localLLM
내용...

---

## AI Discord Recap

### 소제목
내용...

---

**핵심 요약:** 마무리 문장
```

### 헤드라인이 없는 날

```markdown
---
(frontmatter)
---

## 주요 소식

### 소제목 1
내용...

### 소제목 2
내용...

---

## AI Reddit Recap
내용...

---

## AI Discord Recap
내용...
```

## YouTube 템플릿 형식

```
AI 뉴스 브리프 (YYYY.MM.DD)

- 요약 1줄
- 요약 2줄
- 요약 3줄
- 요약 4줄
- 요약 5줄

더보기: https://sudoremove.com/news/YYYY-MM-DD-slug
```

## 번역 규칙

1. **URL 보존**: 마크다운 링크 `[텍스트](URL)`에서 URL은 절대 수정하지 않음
2. **사용자명 유지**: `@username`, `#hashtag`는 그대로 유지
3. **기술 용어 병기**: "추론(inference)", "미세조정(fine-tuning)"
4. **고유명사 유지**: OpenAI, Claude, GPT-4 등 원문 그대로
5. **이미지 링크 유지**: `[image](URL)` 형태 그대로 유지
6. **섹션 구조 유지**: 원문의 계층 구조 완벽 보존
7. **객관적 번역**: 자의적 해석이나 의견 추가 금지

## 예시 파일

`examples/` 디렉토리에서 실제 예시 확인:
- `2026-01-16-chatgpt-ads.md` - 헤드라인 있는 케이스
- `2026-01-14-not-much.md` - 헤드라인 없는 케이스
- `2026-01-16.txt` - YouTube 템플릿

## 배포 흐름

```
1. 마크다운 파일 생성
   ↓
2. web 레포의 src/content/ainews/ko/에 복사
   ↓
3. git add, commit, push
   ↓
4. Cloudflare Pages 자동 배포
   ↓
5. https://sudoremove.com/news/ 에서 확인
```
