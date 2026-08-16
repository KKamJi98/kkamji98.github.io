---
title: "Vite Overview - Native ESM과 Rolldown 빌드 도구"
date: 2026-08-10 09:00:00 +0900
author: kkamji
categories: [Frontend, Build Tool]
tags: [vite, frontend, bundler, esm, rolldown, build-tool, javascript]
comments: true
image:
  path: /assets/img/javascript/vite/vite.webp
---

프로젝트가 커질수록 dev server 시작이 느려집니다. webpack 기반 dev server는 애플리케이션 전체를 사전에 번들링한 뒤 브라우저에 서빙하므로, 모듈이 수백 개를 넘어가면 `npm run dev` 한 번에 수십 초를 기다려야 합니다. 파일 하나를 저장할 때마다 HMR이 전체 번들을 다시 만들지는 않지만, dependency graph를 순회하고 변경 영향 범위를 계산하는 데 시간이 걸립니다.

Vite는 이 문제를 브라우저가 이미 가지고 있는 Native ESM으로 접근합니다. 브라우저가 `import`를 통해 모듈을 요청할 때마다 서버가 해당 파일만 transform해서 반환하면, dev server 시작 시간을 애플리케이션 크기와 무관하게 만들 수 있습니다. Evan You가 2020년 4월에 시작한 이 프로젝트는 2026년 8월 기준 GitHub 82,297 stars, 주간 npm 다운로드 6,500만 건을 기록하며 Nuxt, SvelteKit, Astro, React Router, SolidStart 등 주요 프레임워크의 빌드 레이어로 채택되었습니다. 현재 안정 버전은 Vite 8.2.1입니다.

---

## 1. bundle 기반 dev server와 Vite의 접근 차이

![Bundle-first dev server vs Vite dev server](/assets/img/javascript/vite/vite-dev-server-on-demand-transform.webp)
_두 경로 모두 브라우저에서 끝난다. 차이는 dev server가 첫 요청에 응답하기 전에 무엇을 끝내야 하는가다. Vite 쪽의 양방향 화살표는 브라우저가 모듈마다 따로 요청한다는 뜻이다._

webpack이나 Create React App 같은 bundle 기반 dev server는 애플리케이션 전체를 하나의 번들로 만든 뒤 브라우저에 서빙합니다. 모듈이 늘어날수록 번들링 시간이 길어지고, dev server 시작이 느려집니다. HMR도 변경된 모듈에서 시작해 dependency graph를 따라가며 영향받는 모든 모듈을 다시 번들링해야 하므로, 프로젝트가 크면 hot update도 느려집니다.

Vite는 dependencies와 source code를 분리해 처리합니다. 자주 바뀌지 않는 라이브러리는 미리 번들링(pre-bundling)하고, 개발자가 편집하는 애플리케이션 코드는 브라우저가 `import`로 요청할 때마다 개별적으로 transform하여 서빙합니다. dev server가 애플리케이션 전체를 한 번에 번들링하지 않으므로, 시작 시간이 애플리케이션 크기와 무관하게 거의 즉시 이루어집니다.

---

## 2. Dependency pre-bundling이 필요한 이유

Vite가 source code를 Native ESM으로 서빙한다면, 왜 dependencies는 별도로 번들링할까요? 두 가지 이유가 있습니다.

첫째, npm 패키지 중에는 아직 CommonJS나 UMD 형식으로 배포되는 것이 많습니다. 브라우저의 `import`는 ESM만 이해하므로, CommonJS/UMD 모듈을 ESM으로 변환해야 합니다.

둘째, ESM으로 배포되는 패키지라도 내부 모듈이 너무 많으면 문제가 됩니다. `lodash-es`를 예로 들면 600개 이상의 내부 모듈을 가지고 있습니다. pre-bundling 없이 브라우저가 직접 `import`하면 600개 이상의 HTTP 요청이 동시에 발생해 페이지 로드가 느려집니다. pre-bundling은 이를 하나의 모듈로 병합해 HTTP 요청 수를 줄입니다.

Vite 7까지는 esbuild가 이 역할을 담당했습니다. Vite 8부터는 Rolldown이 pre-bundling을 수행합니다. pre-bundling된 의존성은 `node_modules/.vite` 디렉토리에 캐시되며, lockfile이나 `vite.config.js`가 변경되면 다시 실행됩니다. 브라우저 측에서는 `max-age=31536000,immutable` HTTP 헤더로 강력하게 캐시됩니다.

---

## 3. Native ESM dev server의 동작 방식

Vite dev server는 `index.html`을 entry point로 사용합니다. `index.html` 안의 `<script type="module" src="...">`를 만나면, 브라우저가 해당 모듈을 서버에 요청하고 서버는 요청받은 파일만 transform하여 반환합니다.

예를 들어 `App.tsx`를 편집하면 Vite는 해당 파일만 TypeScript transpile과 JSX transform을 수행해 브라우저에 보냅니다. 다른 파일은 건드리지 않습니다. Transform target을 `esnext`로 설정해 syntax lowering을 방지하고 원본 소스에 가깝게 서빙하므로, 불필요한 변환 단계를 줄입니다. Vite 8부터는 Oxc Transformer가 TypeScript transpile을 담당하며, HMR 업데이트가 브라우저에 반영되기까지 50ms 미만의 시간이 걸립니다.

---

## 4. HMR: 페이지 리로드 없이 모듈을 교체하는 방법

Vite의 HMR(Hot Module Replacement)은 Native ESM 위에서 동작합니다. 파일이 변경되면 Vite는 변경된 모듈의 HMR boundary를 찾고, boundary 안에서만 모듈을 교체합니다. 전체 페이지를 리로드하지 않습니다.

HMR API는 `import.meta.hot` 객체로 노출됩니다. `accept()`를 호출한 모듈은 HMR boundary가 되며, 해당 모듈까지만 업데이트가 전파되고 상위 importer는 알림을 받지 않습니다. `dispose()`는 모듈이 교체되기 전 정리 작업을, `prune()`은 모듈이 제거될 때 호출됩니다.

Vue Single File Components와 React Fast Refresh는 Vite의 HMR API를 활용하는 first-party 통합입니다. Preact는 `@prefresh/vite` 플러그인으로 통합됩니다. 개발자가 직접 HMR API를 다룰 필요 없이, 프레임워크가 제공하는 HMR 통합을 사용하면 됩니다.

---

## 5. 프로덕션 빌드: Rollup에서 Rolldown으로

Vite는 dev와 production에서 서로 다른 bundler를 사용해 왔습니다. Dev에서는 esbuild로 dependency pre-bundling을, production 빌드에서는 Rollup을 사용했습니다. 두 파이프라인을 유지하면서 변환 동작 불일치, 별도 plugin 시스템 관리, glue code 증가 같은 문제가 있었습니다.

Vite 8(2026년 3월 12일 출시)에서 이 듀얼 구조를 Rolldown이라는 단일 Rust bundler로 교체했습니다. Rolldown은 Rollup plugin interface 호환성을 유지하면서 esbuild 수준의 속도를 제공합니다. Parsing, transforming, minifying에는 Oxc(Rust 기반 JavaScript toolchain)를 사용하고, CSS minification은 Lightning CSS가 담당합니다.

Vite 8 발표에서 밝힌 바에 따르면, 벤치마크에서 Rolldown은 Rollup 대비 10-30배 빠른 빌드 속도를 보입니다. 실제 프로젝트에서는 Linear가 프로덕션 빌드 시간을 46초에서 6초로 단축했고, Ramp는 57%, Beehiiv는 64% 빌드 시간을 감소시켰습니다. 기존 Vite plugin의 대부분은 수정 없이 Vite 8에서 그대로 작동합니다.

---

## 6. Plugin 생태계와 Framework 지원

Vite의 plugin 시스템은 Rollup plugin API의 상위 집합(superset)입니다. Vite 8에서 plugin은 Rolldown plugin interface를 확장하지만, Rollup plugin 호환성을 유지하므로 기존 plugin이 대부분 그대로 작동합니다. Vite 전용 hook으로는 `config`, `configResolved`, `configureServer`, `transformIndexHtml`, `handleHotUpdate` 등이 있으며, 이는 Rollup에서 무시됩니다. Plugin 정렬은 `enforce` 속성(`pre`/`post`)과 `apply` 속성(`serve`/`build`)으로 제어합니다.

`create-vite` 템플릿을 통해 vanilla, vue, react, react-ts, preact, lit, svelte, solid, qwik 프로젝트를 빠르게 생성할 수 있습니다. Vite를 빌드 레이어로 채택한 프레임워크로는 Nuxt, SvelteKit, Astro, React Router, Analog, SolidStart가 있으며, Vitest와 Storybook도 Vite 위에 구축되었습니다. Backend 프레임워크인 Laravel과 Ruby on Rails도 Vite를 frontend asset pipeline으로 통합하고 있습니다. Plugin Registry(registry.vite.dev)에서 Vite, Rolldown, Rollup plugin을 검색할 수 있습니다.

---

## 7. Environment API: client와 SSR을 넘어선 다중 환경

Vite 5까지는 `client`와 `ssr` 두 개의 암묵적 환경(environment)만 있었습니다. Vite 6(2024년 11월)에서 Environment API를 공식화하면서, 프레임워크 작성자가 edge runtime, service worker 등 custom environment를 정의할 수 있게 되었습니다.

단일 Vite dev server가 여러 환경에서 동시에 코드를 실행할 수 있습니다. Cloudflare 팀이 Vite 7에서 Environment API 기반 Cloudflare Vite plugin 1.0을 발표했으며, React Router v7을 공식 지원합니다. SPA나 MPA에서는 environment 개념이 노출되지 않으며, Vite 5 config가 그대로 작동하므로 기존 프로젝트에 영향이 없습니다.

Vite 8 기준 Environment API는 여전히 release candidate 단계이며, 일부 API는 experimental입니다.

---

## 8. Vite를 둘러싼 생태계: Vite vs Next.js vs Astro

Vite는 빌드 도구이지 meta-framework가 아닙니다. Routing, data fetching, SSR rendering을 Vite 자체가 제공하지 않습니다. Next.js, Remix, Nuxt 같은 meta-framework가 이 기능을 제공하며, 그중 Nuxt와 Remix 계열(React Router v7)은 Vite를 빌드 레이어로 사용합니다.

Next.js는 자체 빌드 시스템(webpack/Turbopack)을 사용하므로 Vite와 직접 비교하기보다 서로 다른 생태계로 이해하는 것이 맞습니다. Astro는 Vite를 기반으로 하면서 content-focused 정적 사이트에 최적화된 프레임워크입니다.

Vite를 직접 사용하는 경우는 SPA, 라이브러리 개발, 커스텀 SSR 구성, 또는 Vite 기반 meta-framework 없이 가벼운 개발 환경이 필요할 때입니다. 프로덕션에서 SSR, routing, data fetching이 필요하다면 Vite 위에 구축된 meta-framework를 선택하는 것이 일반적입니다.

---

## 9. Vite는 어디로 가고 있는가

Vite 8에서 Rolldown으로 단일 파이프라인을 구축한 후, Vite 팀이 탐색 중인 방향은 두 가지입니다.

첫째, 매우 큰 코드베이스에서 unbundled network request가 너무 많아 dev server 페이지 로드가 느려지는 문제를 해결하기 위해, dev server에서도 production처럼 번들링하는 full bundle mode를 검토하고 있습니다. 둘째, Environment API를 통해 client/SSR 외에 edge runtime, service worker 등 다양한 실행 환경을 지원하도록 확장하고 있습니다.

Vite는 빌드 도구로 시작했지만, 현재는 Vitest(테스트), Storybook(컴포넌트 개발), Rolldown(bundler), Oxc(parser/transformer/minifier)을 아우르는 VoidZero 생태계의 중심에 있습니다. OpenAI, Google, Apple, Microsoft, NASA, Shopify, Cloudflare, GitLab, Reddit, Linear 등이 Vite를 사용하고 있습니다.

---

## 10. Reference

- [Vite Getting Started](https://vite.dev/guide/)
- [Why Vite](https://vite.dev/guide/why.html)
- [Vite Features](https://vite.dev/guide/features.html)
- [Dependency Pre-Bundling](https://vite.dev/guide/dep-pre-bundling.html)
- [HMR API](https://vite.dev/guide/api-hmr.html)
- [Plugin API](https://vite.dev/guide/api-plugin.html)
- [Environment API](https://vite.dev/guide/api-environment.html)
- [Vite 8 Announcement (2026-03-12)](https://vite.dev/blog/announcing-vite8)
- [Vite 6 Announcement (2024-11-26)](https://vite.dev/blog/announcing-vite6)
- [Vite GitHub Repository](https://github.com/vitejs/vite)
- [Plugin Registry](https://registry.vite.dev/plugins)
- [Rolldown](https://rolldown.rs/)
- [Oxc](https://oxc.rs/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
