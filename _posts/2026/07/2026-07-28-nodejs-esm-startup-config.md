---
title: "Node.js ESM 모듈 경계와 startup configuration validation"
date: 2026-07-28 13:57:00 +0900
author: kkamji
categories: [Node.js, System]
tags: [nodejs, esm, modules, configuration, startup, environment-variables, validation]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

HTTP handler의 Promise 오류 경계를 잘 설계해도, 잘못된 설정으로 포트를 먼저 열면 process startup은 안전하지 않습니다. 이 글은 Node.js v26에서 ESM module graph가 준비되는 범위와 application이 configuration을 검증하고 `server.listen()`을 호출하는 범위를 분리합니다.

> **TL;DR**<br>  
> - `package.json`의 `"type"`은 package scope 안의 `.js` 해석을 정합니다. `.mjs`는 항상 ESM이고 `.cjs`는 항상 CommonJS입니다.<br>  
> - Node ESM의 상대 및 절대 import에는 `./config.mjs`처럼 확장자를 명시합니다. 이것은 ECMAScript 일반 규칙이 아니라 Node resolver 규칙입니다.<br>  
> - `--env-file`은 값을 `process.env`에 넣을 뿐입니다. 필수값, port 범위, URL 형식은 application startup policy로 `listen()` 전에 검증합니다.<br>  
> - static module resolution 또는 evaluation 실패는 application validation보다 먼저 발생할 수 있습니다. `server`의 `error` listener도 `listen()` 전에 등록합니다.  
{: .prompt-info}

---

## 1. Phase 1보다 앞선 startup 경계

[Phase 1](/posts/nodejs-async-http-handling/)은 HTTP request가 handler에 들어온 뒤 Promise rejection, timeout, client disconnect를 response policy로 바꾸는 경계를 다뤘습니다. 이번 글의 대상은 request가 오기 전입니다. process가 module을 load하고, configuration을 parse하고, TCP port bind를 시도하는 과정입니다.

request lifetime은 client가 request를 보내고 response가 끝날 때까지의 범위입니다. process startup lifetime은 Node CLI가 program을 시작해 `listening` 상태에 도달하거나 실패하고 종료할 때까지의 범위입니다. invalid configuration은 HTTP 500이 아닙니다. `listen()` 전이라면 client에 response를 보낼 HTTP server 자체가 없습니다.

이 글은 native `node:http`와 Node.js v26의 ESM 규칙을 기준으로 합니다. Event Loop 내부 scheduling, Worker Pool, framework dependency injection, hot reload, secret manager 선택은 다음 주제입니다.

---

## 2. 시작 순서와 실패 시점을 분리합니다

![Node.js ESM startup configuration flow](/assets/img/nodejs/node-esm-startup-config-flow.webp)
_Node CLI가 environment 값을 제공한 뒤 ESM module graph를 load합니다. module graph가 통과하면 application이 configuration을 검증하고, valid configuration에서만 server error listener를 등록한 뒤 `listen()`을 호출합니다._

그림의 핵심은 application validation이 모든 startup 오류의 첫 관문은 아니라는 점입니다. static import의 resolution 또는 module evaluation이 실패하면 `main.mjs`의 application code가 실행되기 전에 process가 실패할 수 있습니다. 반면 configuration failure와 port bind failure는 서로 다른 관측 지점과 대응이 필요합니다.

| 발생 지점 | application code가 할 수 있는 일 | HTTP response |
| --- | --- | --- |
| module resolution 또는 evaluation | validation 실행 전이므로 Node의 module error를 진단 | 없음 |
| configuration validation | safe startup error를 남기고 non-zero 종료 | 없음 |
| port bind | 미리 등록한 server `error` listener에서 safe error 처리 | 없음 |
| request handler | Phase 1의 request error boundary로 response policy 적용 | 가능 |

startup error log에는 안정적인 error code와 필요한 실행 환경 식별자만 남깁니다. raw `process.env`, connection URL, token, Authorization header, secret 원문은 출력하지 않습니다.

---

## 3. Node v26에서 module system을 명시합니다

Node는 filename extension과 가장 가까운 `package.json`의 `"type"`으로 JavaScript file의 module system을 결정합니다. service source는 implicit default에 기대지 말고 package type 또는 extension을 명시하는 편이 경계를 읽기 쉽습니다.

| 입력 | Node의 해석 | 사용할 때 |
| --- | --- | --- |
| `.mjs` | 항상 ESM | ESM entry 또는 extension으로 경계를 고정할 때 |
| `.cjs` | 항상 CommonJS | legacy CommonJS bridge가 꼭 필요할 때 |
| `.js` + `"type": "module"` | ESM | ESM project의 일반 source file |
| `.js` + `"type": "commonjs"` | CommonJS | CommonJS project의 일반 source file |

`"type"`이 없는 `.js`는 Node v26의 ambiguous input 처리와 syntax detection 영향을 받을 수 있습니다. 따라서 "type 없는 `.js`는 언제나 CommonJS"라고 단정하지 않습니다. 교육용 또는 운영 service에는 `"type": "module"`이나 `"type": "commonjs"`를 package 경계에 명시합니다.

ECMAScript specification은 imported module을 가져오는 host operation을 정의합니다. relative extension, `package.json`, `node_modules`, `exports` 해석은 Node가 제공하는 host-specific resolver입니다. 브라우저와 Node에서 같은 source text를 쓰더라도 resolution 규칙까지 같다고 가정하면 안 됩니다.

---

## 4. import 경계와 package API 경계를 구분합니다

Node ESM에서 relative 또는 absolute specifier는 파일 확장자를 포함해야 합니다. `./config`나 `./startup/index` 대신 `./config.mjs`, `./startup/index.mjs`처럼 씁니다. bare specifier는 `node:http`나 설치한 package처럼 package name을 가리킬 때 사용합니다.

```js
import http from 'node:http';
import { loadConfig } from './config.mjs';
import { createServer } from './server.mjs';
```

library 또는 monorepo package는 `package.json`의 `exports`로 외부 소비자가 쓸 public entry point를 제한할 수 있습니다. `imports`는 `#`으로 시작하는 package 내부 alias를 위한 경계입니다. `imports`는 외부 consumer의 public API가 아닙니다. 이미 deep import를 사용하던 consumer는 `exports`를 추가한 뒤 path를 찾지 못할 수 있으므로 migration 전에 영향 범위를 확인합니다.

ESM에서 CommonJS를 import할 때 default export는 제공되지만, named export 감지는 static analysis에 의존합니다. 반대로 CommonJS `require()`가 ESM을 load하는 경우에는 top-level `await`가 없는 synchronous module graph 같은 조건이 있습니다. ESM과 CommonJS를 대칭적이고 자유롭게 섞을 수 있다고 설명하지 않습니다.

---

## 5. `--env-file`과 validation은 다른 책임입니다

Node CLI의 `--env-file`은 file의 값을 `process.env`에 제공합니다. 값이 제공된 뒤에도 environment variable은 text입니다. 예를 들어 `APP_PORT=3000`은 number가 아니고 `DEBUG=false`도 boolean이 아닙니다. `Boolean(process.env.DEBUG)`는 문자열 `"false"`도 truthy로 처리하므로 configuration parser로 쓰면 안 됩니다.

application은 startup에서 값을 읽고 required field, range, enum, URL, field 조합을 검증한 뒤 typed configuration object로 변환합니다. 이 검증은 Node가 자동으로 강제하는 schema가 아니라 service가 선택한 startup policy입니다.

```js
export class ConfigurationError extends Error {}

export function loadConfig(env) {
  if (typeof env.APP_PORT !== 'string' || env.APP_PORT.trim() === '') {
    throw new ConfigurationError('APP_PORT is required');
  }

  const port = Number(env.APP_PORT);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new ConfigurationError('APP_PORT must be an integer from 0 through 65535');
  }

  return Object.freeze({ host: env.APP_HOST ?? '127.0.0.1', port });
}
```

`Object.freeze()`는 application 안에서 configuration object를 우연히 바꾸는 일을 줄이는 한 가지 선택입니다. secret 자체는 error message나 readiness log에 넣지 않습니다.

---

## 6. valid configuration에서만 port bind를 시도합니다

transport module은 server를 만들되 module evaluation 중 socket을 열지 않습니다. bootstrap entry가 configuration validation, server creation, `error` listener 등록, `listen()`을 순서대로 조립합니다. 그러면 configuration failure가 listener를 열기 전에 끝납니다.

```js
import { loadConfig, ConfigurationError } from './config.mjs';
import { createServer } from './server.mjs';

try {
  const config = loadConfig(process.env);
  const server = createServer(config);

  server.once('error', (error) => {
    console.error(`SERVER_ERROR ${error.code ?? error.message}`);
    process.exitCode = 1;
  });

  server.listen(config.port, config.host, () => {
    const address = server.address();
    console.log(`READY ${config.host} ${address.port}`);
  });
} catch (error) {
  if (error instanceof ConfigurationError) {
    console.error(`CONFIG_ERROR ${error.message}`);
    process.exitCode = 1;
  } else {
    throw error;
  }
}
```

`listen()`은 synchronous bind success를 반환하는 API가 아닙니다. bind failure는 server의 `error` event로 전달될 수 있으므로 listener를 `listen()`보다 앞에 둡니다. listener 없는 EventEmitter의 `error` event는 process를 종료시킬 수 있습니다. readiness log도 `listen()` 호출 직후가 아니라 callback 또는 `listening` event 이후에 남깁니다.

configuration validation은 module resolution failure를 가로채지 못합니다. static import graph가 먼저 resolve되고 evaluate된 뒤에 entry module body가 실행될 수 있기 때문입니다. 운영 runbook은 module graph, configuration, port bind, request handling을 각각 다른 startup 또는 runtime error class로 분리해야 합니다.

---

## 7. 검증된 ESM startup lab

이 글의 lab은 `/tmp/phase2-esm-startup-lab`에서 Node test runner로 직접 실행했습니다. `package.json`은 `"type": "module"`을 선언하고, entry file은 `./config.mjs`와 `./server.mjs`를 extension까지 포함해 import합니다. `server.mjs`는 transport만 만들고 module evaluation 중에는 socket을 열지 않습니다.

```text
$ npm run test

1..2
# tests 2
# pass 2
# fail 0
```

첫 test는 `APP_GREETING`이 없는 child process를 실행합니다. process는 exit code `1`과 `CONFIG_ERROR missing required environment value: APP_GREETING`을 남기고, 예약했던 localhost port에는 connection을 받지 않습니다. 이는 invalid configuration이 port binding 전에 실패했다는 증거입니다.

둘째 test는 `APP_HOST=127.0.0.1`, `APP_PORT=0`, `APP_GREETING=hello-esm`으로 child process를 시작합니다. `READY 127.0.0.1 <ephemeral-port>`가 나온 뒤 HTTP request를 보내면 status `200`과 body `hello-esm\n`을 받습니다. response가 끝난 뒤 lab server가 close되고 child process도 exit code `0`으로 종료됩니다.

lab은 configuration failure와 valid HTTP greeting을 의도적으로 두 test로 분리합니다. 이미 사용 중인 production port, secret, shared environment는 사용하지 않습니다. port bind failure test를 추가한다면 실제 port 충돌을 만들기보다 child process와 ephemeral port를 사용하고, `SERVER_ERROR EADDRINUSE`처럼 code만 assertion하는 방식이 안전합니다.

---

## 8. cache와 state를 loader identity 기준으로 봅니다

CommonJS는 resolved filename을 기준으로 module을 cache합니다. ESM은 URL을 기준으로 별도의 cache를 사용합니다. 따라서 ESM specifier의 query 또는 fragment가 달라지면 같은 file도 별도로 load될 수 있습니다.

```js
import './state.mjs?first';
import './state.mjs?second';
```

위처럼 URL identity가 달라지면 module-level state가 두 번 초기화될 수 있습니다. "module은 process 전체에서 언제나 한 번만 실행된다"는 보장은 아닙니다. test isolation, hot reload, cache invalidation은 loader identity와 side effect를 추가로 검토해야 하는 별도 주제입니다.

---

## 9. startup에서 확인할 경계

package boundary에서는 `"type"` 또는 `.mjs`, `.cjs` extension을 명시하고, ESM relative import에는 file extension을 포함해야 합니다. environment variable은 startup에서 parse하고 validation한 immutable configuration으로 한 번만 만들며, configuration failure는 `listen()` 전에 non-zero exit로 끝나는지 test로 확인하는 편이 안전합니다.

server `error` listener는 `listen()`보다 먼저 등록합니다. startup log는 운영자가 process가 왜 뜨지 않았는지 확인하는 channel이고, request error response는 client contract이므로 같은 오류 정보를 두 곳에 복사하지 않습니다.

---

## 10. Reference

- [Node.js Documentation - ECMAScript modules](https://nodejs.org/docs/latest-v26.x/api/esm.html)
- [Node.js Documentation - Modules: Packages](https://nodejs.org/docs/latest-v26.x/api/packages.html)
- [Node.js Documentation - Command-line API](https://nodejs.org/docs/latest-v26.x/api/cli.html)
- [Node.js Documentation - Environment Variables](https://nodejs.org/docs/latest-v26.x/api/environment_variables.html)
- [Node.js Documentation - Net](https://nodejs.org/docs/latest-v26.x/api/net.html)
- [Node.js Documentation - Events](https://nodejs.org/docs/latest-v26.x/api/events.html)
- [Node.js Documentation - Test runner](https://nodejs.org/docs/latest-v26.x/api/test.html)
- [ECMA-262 - HostLoadImportedModule](https://tc39.es/ecma262/#sec-hostloadimportedmodule)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
