---
title: "Node.js 비동기 HTTP 처리 - Promise, async/await, 오류 경계"
date: 2026-07-27 20:30:00 +0900
author: kkamji
categories: [Node.js, System]
tags: [nodejs, http, async, promise, async-await, error-handling, abortcontroller, timeout]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

Node.js HTTP handler는 비동기 작업을 시작한 뒤에도 다른 요청을 처리할 수 있습니다. 하지만 `async` 함수가 반환한 Promise의 실패가 HTTP 응답으로 자동 변환되지는 않습니다. 이 글은 native `node:http`를 기준으로 Promise, timeout, client disconnect, upstream 오류를 요청 하나의 응답 정책으로 묶는 방법을 정리합니다.

> **TL;DR**<br>  
> - `async/await`는 Promise를 없애지 않습니다. `async` 함수의 예외는 rejection이 됩니다.<br>  
> - `http.createServer()`의 async listener가 reject되어도 Node.js가 자동으로 500 응답을 만들지 않습니다. 요청 단위 오류 경계가 필요합니다.<br>  
> - 요청 하나는 성공, 입력 오류, upstream 오류, timeout 중 하나의 terminal response만 끝까지 소유해야 합니다.<br>  
> - `fetch()`는 HTTP 404나 500만으로 reject하지 않습니다. `response.ok`를 확인해야 합니다.<br>  
> - client disconnect와 timeout은 `AbortSignal`로 downstream 작업에 전달하고, 이미 닫힌 response에는 다시 쓰지 않습니다.  
{: .prompt-info}

---

## 1. Promise 실패는 HTTP response가 아닙니다

[HTTP 요청 경로](/posts/nodejs-request-lifecycle/)를 지나 handler에 도착한 뒤에는 입력 검증, upstream 호출, response 직렬화처럼 완료 시간이 다른 작업이 이어집니다. 여기서 rejected Promise를 어떤 status와 body로 바꿀지는 runtime이 아니라 application의 책임입니다.

retry와 circuit breaker는 idempotency, 중복 요청, dependency 계약을 먼저 정해야 합니다. 이 글의 예제는 그 정책을 섞지 않고 요청 하나가 terminal response 하나만 소유하도록 만드는 데 집중합니다.

---

## 2. 비동기 HTTP handler에서 실제로 끊기는 경계

HTTP request가 handler에 전달된 뒤에는 입력 검증, upstream HTTP 호출, database 호출, response 직렬화처럼 완료 시간이 다른 작업이 이어집니다. 이 작업의 결과는 Promise로 전달됩니다. Promise가 fulfilled되면 정상 response를 쓸 수 있고, rejected되면 어떤 status와 body를 보낼지 application이 정해야 합니다.

`http.createServer(async (request, response) => { ... })`처럼 listener를 `async`로 선언해도 반환 Promise를 Node.js HTTP server가 response로 바꾸지 않습니다. EventEmitter listener는 기본적으로 동기 호출되며 Promise rejection을 HTTP error policy로 해석하지 않습니다. 따라서 "throw하면 자동으로 500"이라는 가정은 안전하지 않습니다.

![Node.js 비동기 HTTP 처리 흐름](/assets/img/nodejs/node-async-http-handling-flow.webp)
_실선은 정상 작업과 terminal response 흐름입니다. 점선은 timeout 또는 client disconnect가 downstream 작업을 취소하는 제어 흐름입니다. rejected Promise 자체는 HTTP response가 아니므로 error boundary가 안전한 response로 매핑합니다._

그림의 불변 조건은 간단합니다. request 하나에는 terminal response가 하나만 있어야 합니다. `response.end()`는 각 response에서 호출되어야 하며, error handling도 이 소유권을 깨면 안 됩니다.

---

## 3. Promise와 `await`의 최소 mental model

Promise는 아직 끝나지 않은 결과와 실패를 함께 표현합니다. 상태는 `pending`, `fulfilled`, `rejected` 중 하나로 끝납니다. `.then()`과 `.catch()`는 새 Promise를 반환하므로, chain에서 다음 단계에 값을 넘기려면 callback이 Promise 또는 값을 `return`해야 합니다.

`async` 함수는 항상 Promise를 반환합니다. 함수 안의 일반 `return` 값도 fulfilled Promise가 되고, 잡히지 않은 예외는 rejected Promise가 됩니다. `await`는 Promise가 끝날 때까지 현재 async 함수의 다음 실행을 보류합니다. 이것은 Node.js process 전체나 다른 HTTP request를 멈춘다는 뜻이 아닙니다. Event Loop의 세부 scheduling은 다음 단계에서 별도로 다룹니다.

독립적인 작업은 시작을 먼저 모은 뒤 `Promise.all()`로 함께 기다릴 수 있습니다. 다만 하나가 reject되면 결과 Promise가 빨리 reject될 뿐, 이미 시작한 나머지 작업을 자동으로 취소하지는 않습니다. 취소가 필요한 작업에는 공통 `AbortSignal`을 전달해야 합니다.

---

## 4. 안전한 handler 설계: module boundary와 response 소유권

작은 server도 책임을 나누면 오류 경계가 선명해집니다. transport 조립은 server, route와 orchestration은 `handleRequest()`, upstream protocol은 `fetchJson()`, JSON 직렬화는 `writeJson()`이 담당하게 둡니다. 각 함수가 무엇을 response에 쓰는지 한 곳에서만 결정하면 double response를 피하기 쉽습니다.

| 경계 | 책임 | 실패 처리 |
| --- | --- | --- |
| `server` | request listener를 등록하고 최상위 rejection을 받음 | 아직 response를 쓰지 않았다면 safe 500 |
| `handleRequest()` | route, validation, timeout, status mapping | 예상 가능한 오류를 HTTP policy로 변환 |
| `fetchJson()` | upstream fetch와 HTTP status 확인 | body를 비밀값 없이 domain error로 변환 |
| `writeJson()` | header, status, body를 한 번에 종료 | `writableEnded`이면 아무것도 하지 않음 |

`response.headersSent`는 header가 이미 전송되었는지, `response.writableEnded`는 `end()`가 호출되었는지 확인하는 데 사용합니다. body 일부를 이미 전송했다면 status를 500으로 교체할 수 없습니다. 이 글의 예제는 response 직렬화 이전에 오류를 모으는 구조를 사용합니다. streaming response는 별도의 연결 종료 정책이 필요합니다.

---

## 5. native `node:http`로 구현하는 비동기 HTTP 처리

다음 예제는 Node.js 20.3 이상에서 실행할 수 있습니다. `AbortSignal.timeout()`은 upstream response가 늦을 때 request lifetime을 제한하고, client socket이 먼저 닫히면 별도 controller가 downstream fetch를 취소합니다. Node.js v26 이상에서는 `request.signal`도 같은 목적의 signal로 사용할 수 있습니다.

```js
import http from 'node:http';

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function writeJson(response, status, body) {
  if (response.writableEnded) return;

  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(body));
}

async function fetchJson(url, signal) {
  const upstream = await fetch(url, { signal });

  if (!upstream.ok) {
    throw new HttpError(upstream.status === 404 ? 404 : 502, 'upstream request failed');
  }

  return upstream.json();
}

async function handleRequest(request, response) {
  const clientAbort = new AbortController();
  const abortWhenClientLeaves = () => {
    if (!response.writableEnded) clientAbort.abort();
  };

  response.once('close', abortWhenClientLeaves);

  try {
    if (request.method !== 'GET' || request.url !== '/profile') {
      throw new HttpError(400, 'unsupported request');
    }

    const signal = AbortSignal.any([
      clientAbort.signal,
      AbortSignal.timeout(1500),
    ]);
    const profile = await fetchJson('http://127.0.0.1:4321/profile', signal);
    writeJson(response, 200, { profile });
  } catch (error) {
    if (clientAbort.signal.aborted || response.writableEnded) return;

    if (error.name === 'TimeoutError') {
      writeJson(response, 504, { error: 'upstream timeout' });
      return;
    }

    if (error instanceof HttpError) {
      writeJson(response, error.status, { error: error.message });
      return;
    }

    console.error('unexpected request error', { name: error.name });
    writeJson(response, 500, { error: 'internal server error' });
  } finally {
    response.off('close', abortWhenClientLeaves);
  }
}

const server = http.createServer((request, response) => {
  void handleRequest(request, response).catch((error) => {
    console.error('request boundary failed', { name: error.name });
    writeJson(response, 500, { error: 'internal server error' });
  });
});

server.listen(4310, '127.0.0.1');
```

예제는 upstream response body, authorization header, cookie, stack trace를 client에 보내지 않습니다. log에는 오류 이름처럼 진단에 필요한 최소 field만 남기고, 민감한 raw payload는 제외합니다. 실제 서비스의 status mapping은 API contract에 맞춰 정해야 합니다. 예를 들어 upstream의 404를 호출자에게도 404로 보일지, 502로 감출지는 서비스 경계의 결정입니다.

---

## 6. timeout, 취소, client disconnect를 같은 request lifetime으로 다루기

`server.requestTimeout`은 HTTP request 전체를 수신하는 시간 제한입니다. database query나 upstream HTTP request에 적용되는 application timeout과는 다른 값입니다. handler가 시작한 downstream 작업에는 별도의 timeout signal을 전달해야 합니다.

client가 response를 기다리다 연결을 닫으면 이미 전달할 곳이 없는 결과를 계속 계산할 이유가 없습니다. 예제의 `response` close handler는 `AbortController.abort()`를 호출하고, 합쳐진 signal이 `fetch()`에 전달됩니다. abort를 서버 오류처럼 기록하거나 이미 닫힌 socket에 500 response를 쓰면 진단 신호가 흐려집니다. client abort는 작업을 중단한 뒤 return하는 경로로 분리합니다.

timeout은 upstream이 응답하지 않았다는 관측이며 service 전체 장애의 확정 증거는 아닙니다. request ID, route template, upstream target 이름, elapsed time, status, abort reason을 같은 시간 구간에서 비교한 뒤 원인을 좁혀야 합니다. retry는 이번 예제에 넣지 않습니다. 안전한 retry에는 idempotency, deadline budget, duplicate side effect를 먼저 검토해야 합니다.

---

## 7. 통합 테스트로 응답 경계를 검증하기

다음 실험은 저장소 밖의 `/tmp/node-async-http-lab`에서 Node.js `v22.23.1`로 실제 실행했습니다. mock upstream과 application server를 localhost의 임의 port에 띄우고 `node:test`로 response policy를 확인했습니다.

```text
node --test async-http.test.mjs

ok 1 - upstream success returns 200 JSON
ok 2 - upstream 404 is an explicit 404 response
ok 3 - timeout returns 504
ok 4 - rejected Promise becomes one safe 500 response
1..4
# pass 4
# fail 0
```

테스트는 성공 response, upstream 404, timeout, 예상하지 못한 rejection을 각각 분리합니다. 마지막 case는 async handler rejection이 자동 HTTP response가 아니라는 점을 검증합니다. listener의 최상위 `.catch()`가 rejection을 safe 500으로 바꾸고, response가 한 번만 종료되는지 확인합니다.

client abort는 integration test에서도 별도 case로 다루는 편이 좋습니다. client가 먼저 socket을 닫은 뒤에는 `response.end()`를 다시 호출하지 않고, downstream fetch가 abort signal을 받았는지 관측합니다. OS timing에 따라 socket error 문자열이 달라질 수 있으므로 특정 error text보다 abort signal과 response write 여부를 assertion으로 사용하는 편이 안정적입니다.

---

## 8. 운영 관측과 다음 글

요청 경계를 운영에서 관찰하려면 request ID, method, path template, status, elapsed time, abort reason, upstream target 이름을 남깁니다. raw authorization header, cookie, full request body, upstream response 전문은 log에 넣지 않습니다.

| 먼저 볼 관측 | 구분할 조건 | 다음 확인 |
| --- | --- | --- |
| client disconnect | abort signal과 response close | client, proxy, load balancer timeout |
| upstream timeout | timeout signal과 elapsed time | upstream latency, connection pool, deadline budget |
| upstream non-2xx | `response.ok=false`와 upstream status | API contract, dependency health |
| coding bug | 예상하지 못한 rejection과 500 | stack trace를 안전한 내부 log에서 확인 |

timeout, client abort, upstream 오류, coding bug는 서로 다른 관측 조건과 response policy를 가집니다. `AbortSignal`, elapsed time, `response.ok`, 내부 log를 함께 남기면 같은 500처럼 보이는 증상을 dependency, client, application 문제로 나눌 수 있습니다.

---

## 9. Reference

- [Node.js Documentation - HTTP](https://nodejs.org/api/http.html)
- [Node.js Documentation - Events](https://nodejs.org/api/events.html)
- [Node.js Documentation - Fetch and Web APIs](https://nodejs.org/api/globals.html#fetch)
- [Node.js Documentation - Errors](https://nodejs.org/api/errors.html)
- [Node.js Documentation - Test Runner](https://nodejs.org/api/test.html)
- [MDN - async function](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function)
- [MDN - await](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/await)
- [MDN - Promise.all](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all)
- [MDN - Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [RFC 9110 - HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
