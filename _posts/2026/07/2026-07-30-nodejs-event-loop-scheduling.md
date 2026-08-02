---
title: Node.js 이벤트 루프에서 다음 콜백이 실행되는 순서
date: 2026-07-30 00:05:00 +0900
author: kkamji
categories: [Node.js, JavaScript]
tags: [nodejs, event-loop, microtask, process-nexttick, setimmediate, timers]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
  alt: Node.js 로고와 역사 타임라인
---

`setTimeout(fn, 0)`과 `setImmediate(fn)`을 같은 위치에서 등록했는데 실행 순서가 바뀌면, timer가 고장 난 것처럼 보일 수 있습니다. 하지만 두 API는 같은 queue에 들어가지 않고, callback을 등록한 위치도 같습니다. 순서를 판단할 때 먼저 봐야 할 것은 delay 값이 아니라 **어느 scheduling boundary에서 callback을 등록했는가**입니다.

Node.js는 기본적으로 하나의 JavaScript thread에서 callback을 실행하면서도 I/O를 kernel과 libuv에 맡깁니다. I/O 완료 이벤트가 poll queue에 들어오고, event loop가 적절한 시점에 JavaScript callback을 실행합니다. `process.nextTick()`, V8 microtask, `setImmediate()`, timer는 이 흐름의 서로 다른 지점에 연결됩니다.

![Node.js event loop scheduling boundary](/assets/img/nodejs/node-event-loop-scheduling-flow.webp)

---

## 1. callback body가 끝난 뒤 먼저 비우는 queue

JavaScript callback이 실행 중일 때 `process.nextTick()`, `queueMicrotask()`, `Promise.then()`을 등록하면 callback body가 끝난 직후에 바로 다음 event-loop phase로 넘어가지 않습니다.

CommonJS script와 일반 callback boundary에서는 Node.js가 우선 `process.nextTick()` queue를 비우고, 그다음 V8 microtask queue를 처리합니다. `queueMicrotask()`와 이미 resolve된 Promise의 `.then()`은 같은 microtask queue에 들어가므로 등록 순서가 FIFO 순서를 결정합니다.

ESM top-level은 예외입니다. ESM module 자체가 microtask queue의 일부로 처리되므로, top-level에서 등록한 `queueMicrotask()` callback이 `process.nextTick()`보다 먼저 실행될 수 있습니다. 따라서 next-tick과 microtask의 순서는 module format과 callback placement를 함께 적어야 합니다.

```js
process.nextTick(() => console.log('nextTick'));
queueMicrotask(() => console.log('queueMicrotask'));
Promise.resolve().then(() => console.log('promise.then'));
```

**CONFIRMED:** Node.js 문서는 현재 operation이 끝난 뒤 event loop가 계속되기 전에 `process.nextTick()` queue를 처리한다고 설명합니다. 재귀적으로 `process.nextTick()`을 채우면 poll phase가 I/O callback을 처리할 기회를 잃을 수 있습니다. CPU 작업을 작은 단위로 쪼갠 뒤에도 계속 `nextTick`만 등록하는 방식은 I/O latency를 악화시킬 수 있습니다.

`queueMicrotask()`도 무한 재귀하면 JavaScript thread를 점유합니다. 다만 Node 전용 next-tick queue에 의존해야 할 이유가 없다면, Promise 기반 API와 같은 microtask 경계를 사용하면 Node 밖의 JavaScript runtime과도 의미를 맞추기 쉽습니다.

---

## 2. `setImmediate()`와 `setTimeout(0)`은 같은 의미가 아닙니다

`setTimeout(fn, 0)`의 `0`은 즉시 실행 지시가 아닙니다. callback이 실행될 수 있는 최소 threshold를 의미하며, event loop의 현재 상태와 OS scheduling에 따라 실제 실행 시점은 달라집니다.

`setImmediate(fn)`은 check phase에서 실행할 callback을 등록합니다. 반면 timer callback은 timers phase에서 실행합니다. 따라서 top-level code에서 두 API를 같이 등록했을 때 어느 쪽이 먼저 실행될지는 portable contract가 아닙니다.

```js
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
```

**UNCONFIRMED as a general rule:** 한 번 실행해서 `timeout`이 먼저 나왔다고 모든 host와 모든 실행에서 `timeout`이 먼저라는 뜻은 아닙니다. 반대 결과도 같습니다. startup timing, I/O 존재 여부, event loop가 phase에 진입한 시점이 결과에 영향을 줍니다.

I/O callback 안에서는 판단 근거가 더 선명합니다. poll phase에서 실행된 callback이 `setImmediate()`를 등록하면 같은 iteration의 check phase에서 실행될 수 있습니다. `setTimeout(0)`은 이후 timers phase까지 기다립니다. 이 차이는 file read, socket I/O, database driver callback 뒤에 후속 작업을 연결할 때 중요합니다.

---

## 3. Node v26.5.0에서 확인한 두 경계

다음 실험은 WSL 환경의 Node `v26.5.0`에서 실행했습니다. top-level 실험은 순서가 달라질 수 있음을 기록하고, I/O callback 실험은 callback placement에 따른 순서를 assertion으로 검사했습니다.

```js
const fs = require('node:fs');

fs.readFile(__filename, () => {
  console.log('I/O callback:start');
  process.nextTick(() => console.log('nextTick'));
  queueMicrotask(() => console.log('queueMicrotask'));
  Promise.resolve().then(() => console.log('promise.then'));
  setTimeout(() => console.log('setTimeout(0)'), 0);
  setImmediate(() => console.log('setImmediate'));
  console.log('I/O callback:end');
});
```

50회 실행에서 top-level code는 두 결과를 모두 보였습니다.

```text
sync:start -> sync:end -> nextTick -> queueMicrotask -> promise.then -> setImmediate -> setTimeout(0)
sync:start -> sync:end -> nextTick -> queueMicrotask -> promise.then -> setTimeout(0) -> setImmediate
```

반대로 `fs.readFile()` callback 안에서 등록한 순서는 50회 모두 다음 assertion을 통과했습니다.

```text
I/O callback:start
I/O callback:end
nextTick
queueMicrotask
promise.then
setImmediate
setTimeout(0)
```

이 결과는 timer와 immediate의 보편적인 우선순위를 증명하지 않습니다. I/O callback이라는 등록 위치에서 event loop가 poll에서 check로 진행한다는 조건을 검증한 것입니다.

---

## 4. HTTP handler에서 생기는 지연을 분리하는 방법

HTTP handler가 I/O 결과를 받은 뒤 응답과 관계없는 작업을 시작해야 할 때, queue 선택은 request latency와 fairness에 영향을 줍니다.

- response를 보내기 전에 반드시 이어져야 하는 작은 상태 정리는 synchronous code나 제한된 microtask로 끝냅니다.
- poll callback 뒤에 후속 callback을 연결해야 하면 `setImmediate()`가 check phase 경계를 명시합니다.
- delay가 필요하면 `setTimeout()`에 실제 의도를 나타내는 값을 넣습니다. `0`을 yield 보장으로 사용하지 않습니다.
- CPU 집약 작업을 `nextTick`이나 microtask 재귀로 분할해도 JavaScript thread 점유 자체는 사라지지 않습니다. Worker Threads나 worker pool에 맡길 수 있는 workload인지 따로 판단해야 합니다.

event loop의 phase 이름을 암기하는 것보다 callback이 만들어진 지점, next-tick 및 microtask queue가 drain되는 지점, 그리고 I/O가 poll에 다시 도달할 기회를 함께 보는 편이 장애 분석에 더 도움이 됩니다.

---

## 5. Reference

- [Node.js Learn - The Node.js Event Loop](https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick)
- [Node.js Learn - Understanding setImmediate()](https://nodejs.org/en/learn/asynchronous-work/understanding-setimmediate)
- [Node.js API - process.nextTick()](https://nodejs.org/docs/latest/api/process.html#processnexttickcallback-args)
- [Node.js API - Timers](https://nodejs.org/docs/latest/api/timers.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
