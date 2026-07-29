---
title: "Node.js Overview: 서버 런타임의 특성과 연재 학습 지도"
date: 2026-07-26 09:00:00 +0900
author: kkamji
categories: [Node.js, System]
tags: [nodejs, javascript-runtime, server, asynchronous-io, event-driven, libuv, http]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

Node.js 서버를 운영하거나 성능 문제를 진단하려면 `async` 문법, HTTP framework, Kubernetes manifest보다 먼저 실행 경계를 구분해야 합니다. Node.js는 JavaScript 언어 자체도, browser도, Express나 NestJS 같은 web framework도 아닙니다. Node.js는 OS process 안에서 JavaScript와 core API를 실행하는 runtime이며, network I/O를 포함한 event-driven application을 만들 수 있는 환경입니다.

> **TL;DR**<br>  
> - Node.js는 JavaScript runtime입니다. browser API, HTTP framework, Kubernetes runtime을 포함하지 않습니다.<br>  
> - Node.js server는 application code, Node.js process, OS network listener라는 서로 다른 책임 경계 위에서 동작합니다.<br>  
> - I/O를 기다리는 작업과 main JavaScript thread를 오래 점유하는 CPU 작업은 다른 문제입니다. 비동기 API 호출만으로 CPU blocking이 사라지지는 않습니다.<br>  
> - 이 글은 전체 mental model과 학습 지도를 다룹니다. HTTP 요청 경로, Promise 오류, ESM startup, Event Loop scheduling의 상세는 각각 다음 글에서 분리합니다.  
{: .prompt-info}

---

## 1. 이 글의 범위와 연재에서의 위치

이 글의 독자는 JavaScript와 HTTP의 존재는 알지만 Node.js를 browser JavaScript, web framework, OS process와 구분하지 못하는 개발자 및 DevOps 엔지니어입니다. 읽은 뒤에는 Node.js가 어떤 실행 환경인지, 어떤 workload에서 강점과 주의점이 생기는지, 이후 글을 어떤 순서로 읽어야 하는지 설명할 수 있어야 합니다.

이번 글은 foundation과 series overview 역할을 함께 합니다. TCP stream, keep-alive, container 종료, Promise rejection, ESM resolver, Event Loop phase, Worker Pool, Worker Threads의 내부 동작은 의도적으로 상세 설명하지 않습니다. 각 주제는 다음 글에서 재현 실험과 운영 경계를 포함해 따로 다룹니다.

---

## 2. Node.js는 무엇이고 무엇이 아닌가

Node.js 공식 문서는 Node.js를 asynchronous event-driven JavaScript runtime으로 설명합니다. JavaScript source를 실행하고, file system, network, process, crypto 같은 core API를 제공하며, application은 OS process로 실행됩니다.

이 정의에서 세 가지를 분리해야 합니다.

| 대상 | Node.js와의 관계 | 이번 연재에서의 의미 |
| --- | --- | --- |
| JavaScript | 언어 | `async`, Promise, module syntax를 작성하는 언어 규칙 |
| browser | 다른 host environment | DOM, `window`, rendering API는 Node.js runtime의 기본 API가 아님 |
| Express, NestJS | Node.js 위에서 동작할 수 있는 framework | route, middleware, dependency injection을 제공하지만 runtime 자체는 아님 |
| Node.js | JavaScript runtime | process, core modules, network I/O, module loader의 실행 환경 |
| container와 Kubernetes | deployment 및 orchestration 환경 | Node.js process를 배포하고 종료시키는 외부 실행 경계 |

따라서 "Node.js server"라는 말은 framework 이름이나 container 하나를 가리키지 않습니다. application code가 Node.js runtime 안에서 실행되고, 그 process가 OS의 network 기능을 통해 port를 listen하며, 필요하면 container와 Kubernetes가 그 process의 lifecycle을 관리하는 전체를 뜻합니다.

---

## 3. Node.js 서버의 최소 실행 경계

![Node.js 서버의 최소 실행 경계](/assets/img/nodejs/nodejs-server-runtime-overview.webp)
_Node.js application은 OS process 안에서 core API를 호출합니다. network listener와 준비된 I/O callback은 runtime의 scheduling 경계를 거쳐 application code에 전달됩니다. 그림은 책임 경계를 보여 주며 TCP parser, Event Loop phase, Worker Pool 구현은 다음 글에서 별도로 다룹니다._

application code는 route, domain rule, serialization처럼 제품 고유의 책임을 가집니다. Node.js process는 JavaScript와 `node:http` 같은 core API를 실행하는 경계입니다. OS는 socket, file descriptor, network readiness 같은 자원을 제공합니다. 이 경계를 나누면 application bug, port bind failure, network 문제, deployment lifecycle 문제를 같은 종류의 오류로 섞지 않을 수 있습니다.

`node:http`는 framework 없이도 HTTP server를 만들 수 있는 core API입니다. framework를 도입해도 application code는 결국 runtime과 process boundary 위에서 실행됩니다. 다음 요청 경로 글은 여기서 listener가 받은 TCP byte stream이 HTTP request와 handler 호출로 이어지는 과정을 다룹니다.

---

## 4. 비동기 I/O와 event-driven 처리의 의미

Node.js의 강점은 I/O를 기다리는 동안 JavaScript thread가 무조건 멈춰 있는 모델만 사용하는 것이 아니라, 완료된 I/O event와 callback을 처리하는 event-driven runtime이라는 점에 있습니다. network response, database response, file read 같은 작업은 완료까지 시간이 걸릴 수 있습니다. application이 기다리는 동안 준비된 다른 작업을 처리할 기회가 생깁니다.

이 설명은 "연결마다 JavaScript thread 하나" 또는 "Node.js는 자동으로 모든 요청을 병렬 CPU 실행한다"는 뜻이 아닙니다. 기본 application JavaScript는 main thread에서 실행됩니다. Worker Threads 같은 별도 실행 단위를 만들 수 있지만, 이는 명시적인 설계 선택입니다. event-driven I/O와 CPU parallelism은 다른 문제로 봐야 합니다.

`await`는 현재 async function의 다음 실행을 Promise 결과까지 보류합니다. process 전체를 멈춘다는 뜻은 아닙니다. 하지만 `await` 뒤에 수행하는 동기 CPU loop도 자동으로 다른 thread로 옮겨지지 않습니다. 이 차이가 later latency와 event loop delay를 해석할 때 중요합니다.

---

## 5. 어떤 workload에 잘 맞는가

Node.js는 HTTP API, upstream service 호출, cache 또는 database I/O, message broker I/O처럼 기다리는 시간이 중요한 server workload에 자주 사용됩니다. JavaScript 하나로 browser와 server의 domain model 또는 tooling을 공유할 수 있다는 점도 팀의 선택 기준이 될 수 있습니다. 그러나 이런 특성은 모든 workload에서 같은 성능이나 같은 운영 난이도를 보장하지 않습니다.

| 작업 형태 | 먼저 확인할 질문 | 이 글의 결론 |
| --- | --- | --- |
| network 또는 database I/O 대기 | response가 기다리는 동안 main thread가 긴 동기 작업을 수행하는가? | Event Loop와 request cancellation 경계를 확인 |
| 짧은 JSON validation과 serialization | payload 크기와 CPU 시간이 제한되어 있는가? | request path의 일부로 둘 수 있으나 측정 필요 |
| image, video, large compression, 긴 계산 | main JavaScript thread를 오래 점유하는가? | Worker Threads, queue, 별도 service 같은 분리 설계를 검토 |
| file system 또는 일부 crypto, DNS API | OS async I/O인지 libuv Worker Pool 경로인지? | Worker Pool 글에서 API별 경계와 contention을 확인 |

CPU-heavy 작업에 `setTimeout()`이나 Promise를 감싸는 것만으로 main thread 점유가 사라지지는 않습니다. 반대로 CPU usage 하나만 보고 Worker Pool 또는 JavaScript CPU loop를 단정할 수도 없습니다. 요청 지연, event loop delay, queue length, throttling, workload 형태를 함께 관찰해야 합니다.

---

## 6. 가장 작은 Node.js HTTP server를 관찰합니다

이 글의 lab은 dependency 없이 Node.js process가 core HTTP API로 request-response를 제공한다는 사실만 확인합니다. keep-alive, graceful shutdown, async error, ESM startup은 후속 lab의 고유 범위로 남깁니다.

```js
const http = require('node:http');

function createHealthServer() {
  return http.createServer((request, response) => {
    if (request.method !== 'GET' || request.url !== '/healthz') {
      response.writeHead(404).end();
      return;
    }

    response.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
    response.end(JSON.stringify({ runtime: 'node', node: process.version, pid: process.pid }));
  });
}

module.exports = { createHealthServer };
```

실습은 `/tmp/nodejs-overview-lab`에서 Node.js `v26.5.0`으로 실행했습니다.

```text
$ node --version
v26.5.0

$ npm test
✔ Node process serves /healthz through the core HTTP API
ℹ tests 1
ℹ pass 1
ℹ fail 0
```

test는 localhost ephemeral port에서 server를 열고 `fetch()`로 `/healthz`를 요청합니다. status `200`, `runtime: "node"`, 실행 중인 Node version, 양의 PID를 assertion합니다. 이것은 benchmark나 production readiness 증명이 아닙니다. 다만 Node.js가 browser 밖의 process로 실행되며 core API로 HTTP response를 만들 수 있다는 최소 증거입니다.

---

## 7. 이후 글에서 책임을 분리합니다

연재의 각 글은 같은 "Node.js server"를 다른 경계에서 봅니다. Overview에 세부 구현을 모두 넣으면 개념은 넓어지지만 재현 가능한 판단은 어려워집니다.

| 순서 | 글 | 핵심 질문 |
| --- | --- | --- |
| 0 | Node.js Overview | Node.js는 어떤 runtime이며 어떤 workload 경계를 먼저 구분해야 하는가? |
| 1 | [HTTP 서버의 요청 경로](/posts/nodejs-request-lifecycle/) | TCP connection, HTTP request, Node process, container 종료는 어디에서 나뉘는가? |
| 2 | [비동기 HTTP 처리](/posts/nodejs-async-http-handling/) | Promise failure, timeout, client disconnect를 response policy로 어떻게 끝내는가? |
| 3 | [ESM module boundary와 startup configuration](/posts/nodejs-esm-startup-config/) | module graph, configuration, port bind failure를 어떻게 분리하는가? |
| 4 | Event Loop와 microtask 경계 | callback을 어디에서 등록했는지가 실행 순서에 어떤 영향을 주는가? |
| 5 | libuv Worker Pool과 blocking I/O | 비동기 API 중 어떤 작업이 pool contention을 만들 수 있는가? |
| 6 | CPU blocking과 Worker Threads | 긴 계산을 main thread에서 분리할 기준은 무엇인가? |

Node.js를 "single-threaded라서 느리다" 또는 "non-blocking이라서 항상 빠르다"로 축약하면 이 경계를 잃습니다. runtime, workload, deployment 환경을 분리해 보는 것이 이후 진단의 출발점입니다.

---

## 8. 학습 점검과 다음 글

다음 질문에 답할 수 있으면 이 글의 출발점은 충분합니다.

- [ ] Node.js가 JavaScript 언어, browser, web framework와 다른 실행 환경임을 설명할 수 있는가?
- [ ] application code, Node.js process, OS network listener의 책임을 구분할 수 있는가?
- [ ] I/O 대기와 main JavaScript thread를 오래 점유하는 CPU 작업을 다른 문제로 설명할 수 있는가?
- [ ] HTTP request path, Promise error, ESM startup, Event Loop scheduling을 각각 다른 글에서 다뤄야 하는 이유를 말할 수 있는가?

다음 글에서는 listener가 받은 TCP connection과 byte stream이 HTTP request, parser, application handler로 이어지는 과정을 다룹니다. 그 흐름을 이해한 뒤에 request error boundary, startup boundary, callback scheduling으로 들어가면 운영 증상을 더 정확히 분리할 수 있습니다.

---

## 9. Reference

- [Node.js - About Node.js](https://nodejs.org/en/about)
- [Node.js Learn - Introduction to Node.js](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs)
- [Node.js Documentation - HTTP](https://nodejs.org/docs/latest-v26.x/api/http.html)
- [Node.js Documentation - Process](https://nodejs.org/docs/latest-v26.x/api/process.html)
- [Node.js Documentation - Test runner](https://nodejs.org/docs/latest-v26.x/api/test.html)
- [Node.js Learn - Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
