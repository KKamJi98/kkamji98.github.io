---
title: Docs index
updated: 2026-08-23
type: architecture
status: current
---

# Docs index

문서 하나당 한 줄. 여기 없는 `docs/**/*.md`는 CI가 막는다.

## Architecture

- [Theme overrides registry](THEME_OVERRIDES.md) - gem 테마 위에 얹은 override 레지스트리. `_includes/`나 chirpy scss를 고치면 여기도 고친다.
- [Blog content-quality harness](blog-content-quality-harness.md) - `kkamji_scripts/blog/audit_content_depth.py`의 설계 의도와 사용법.

## Rules

- [Technical post template](blog-post-template.md) - 신규 기술 글의 기본 구조와 유지해야 하는 섹션.

## Evidence

- [Blog refresh backlog](blog-refresh-backlog.md) - `audit_blog_quality.py` 결과 기반 리프레시 우선순위.
