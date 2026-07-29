---
title: "Node.js 서버는 무엇 위에서 동작하는가"
date: 2026-07-25 09:00:00 +0900
author: kkamji
categories: [Node.js, System]
tags: [nodejs, javascript-runtime, server, asynchronous-io, event-driven, libuv, http]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

Node.js 서버에서 응답이 느려졌을 때 Express middleware부터 의심하기 쉽습니다. 하지만 route 코드가 정상이어도 Node.js process가 CPU를 오래 점유하거나, port를 열지 못했거나, container가 종료 신호를 받는 중일 수 있습니다. 원인을 나누려면 Node.js가 JavaScript 언어도, browser도, web framework도 아니라는 점부터 분명히 해야 합니다.

Node.js는 OS process 안에서 JavaScript와 core API를 실행하는 runtime입니다. `node:http`로 HTTP server를 열고, file system, network, process, crypto API를 호출할 수 있습니다. Express나 NestJS는 이 runtime 위에서 route와 middleware를 구성하는 framework입니다. container와 Kubernetes는 Node.js process를 배포하고 lifecycle을 관리하는 바깥 환경입니다.

---

## 1. Node.js runtime, application, OS

| 대상 | 하는 일 |
| --- | --- |
| JavaScript | application logic을 표현하는 언어 |
| Node.js | JavaScript와 core API를 OS process에서 실행하는 runtime |
| Express, NestJS | routing, middleware, dependency injection 같은 application 구조 제공 |
| OS | socket, file descriptor, network readiness 같은 자원 제공 |
| Container, Kubernetes | Node.js process를 배포, 제한, 종료하는 실행 환경 |

"Node.js 서버"는 framework 이름 하나를 뜻하지 않습니다. application code가 Node.js runtime에서 실행되고, process가 OS socket을 listen하며, 배포 환경이 그 process의 lifecycle을 관리하는 상태를 함께 가리킵니다.

![Node.js 서버의 실행 경계](/assets/img/nodejs/nodejs-server-runtime-overview.webp)
_Node.js application은 OS process 안에서 core API를 호출합니다. network listener와 준비된 I/O callback은 runtime의 scheduling 경계를 거쳐 application code에 전달됩니다._

application code는 route, domain rule, serialization처럼 제품 고유의 책임을 가집니다. Node.js process는 JavaScript와 `node:http` 같은 core API를 실행합니다. OS는 socket과 file descriptor를 제공합니다. 이 셋을 나누면 application bug, port bind failure, network 문제, deployment lifecycle 문제를 같은 오류로 묶지 않게 됩니다.

---

## 2. I/O를 기다리는 일과 CPU를 쓰는 일

Node.js는 asynchronous event-driven runtime입니다. database query, upstream HTTP request, file read처럼 완료까지 기다려야 하는 I/O가 있을 때, application은 그 시간 내내 연결 하나를 위해 JavaScript thread를 붙잡아 두는 방식만 사용하지 않습니다. 완료된 I/O event가 준비되면 callback이나 Promise 후속 처리를 실행합니다.

그렇다고 Node.js가 CPU 작업을 자동으로 병렬 처리하는 것은 아닙니다. 기본 application JavaScript는 main thread에서 실행됩니다. `await`는 현재 async function의 다음 실행을 Promise 결과까지 미룰 뿐이고, 그 뒤의 긴 JSON 변환이나 암호화, image 처리, 계산을 다른 thread로 옮기지 않습니다.

Worker Threads를 만들 수는 있습니다. 다만 이는 CPU-heavy 작업을 main thread에서 떼어 내기 위한 명시적인 설계 선택입니다. event-driven I/O와 CPU parallelism은 다른 문제로 봐야 합니다.

---

## 3. workload를 볼 때 먼저 확인할 것

| 작업 형태 | 먼저 확인할 것 | 흔한 대응 |
| --- | --- | --- |
| network 또는 database I/O 대기 | 대기 중 main thread에서 긴 동기 작업을 하는가 | request cancellation, timeout, event loop 지연 확인 |
| 짧은 JSON validation과 serialization | payload 크기와 CPU 시간이 제한되어 있는가 | request path에 둘 수 있지만 지연 시간을 측정 |
| image, video, large compression, 긴 계산 | main JavaScript thread를 오래 점유하는가 | Worker Threads, queue, 별도 service 검토 |
| file system 또는 일부 crypto, DNS API | OS async I/O인지 libuv Worker Pool 경로인지 | API별 worker pool contention 확인 |

CPU-heavy 작업을 Promise나 `setTimeout()`으로 감싼다고 main thread 점유가 사라지지는 않습니다. 반대로 CPU usage 하나만으로 JavaScript CPU loop나 Worker Pool 병목을 단정할 수도 없습니다. 요청 지연, event loop delay, queue length, throttling, workload 형태를 함께 봐야 합니다.

---

## 4. framework 없이 HTTP server를 열어 보기

`node:http`만으로도 HTTP server를 만들 수 있습니다. 아래 코드는 `/healthz` 요청에 실행 중인 Node version과 PID를 돌려줍니다.

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

`/tmp/nodejs-overview-lab`에서 Node.js `v26.5.0`으로 실행했습니다.

```text
$ node --version
v26.5.0

$ npm test
✔ Node process serves /healthz through the core HTTP API
ℹ tests 1
ℹ pass 1
ℹ fail 0
```

test는 localhost ephemeral port에서 server를 열고 `fetch()`로 `/healthz`를 요청합니다. status `200`, `runtime: "node"`, 실행 중인 Node version, 양의 PID를 assertion합니다. 이 작은 확인만으로 production readiness를 판단할 수는 없지만, Node.js가 browser 밖의 process에서 core HTTP API를 제공한다는 실행 증거는 됩니다.

---

Node.js를 "single-threaded라서 느리다" 또는 "non-blocking이라서 항상 빠르다"로 줄이면 문제의 위치가 사라집니다. runtime, workload, deployment 환경을 나눠 보면, 요청 지연이 코드인지 I/O인지 CPU인지 process lifecycle인지부터 구분할 수 있습니다.

---

## 5. Reference

- [Node.js - About Node.js](https://nodejs.org/en/about)
- [Node.js Learn - Introduction to Node.js](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs)
- [Node.js Documentation - HTTP](https://nodejs.org/docs/latest-v26.x/api/http.html)
- [Node.js Documentation - Process](https://nodejs.org/docs/latest-v26.x/api/process.html)
- [Node.js Documentation - Test runner](https://nodejs.org/docs/latest-v26.x/api/test.html)
- [Node.js Learn - Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
