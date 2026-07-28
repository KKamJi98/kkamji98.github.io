---
title: "Node.js HTTP 서버의 요청 경로: HTTP, TCP, 프로세스, 컨테이너의 경계"
date: 2026-07-27 09:00:00 +0900
author: kkamji
categories: [Node.js, System]
tags: [nodejs, http, tcp, keep-alive, process, signal, container, kubernetes]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

Node.js 서버의 성능, Event Loop, Worker Threads, Kubernetes CPU limit을 이해하려면 먼저 요청 하나가 어디에서 시작하고 어느 책임 경계를 지나 애플리케이션 코드에 도착하는지 알아야 합니다. 이 글은 `GET /healthz` 같은 HTTP 요청을 기준으로 TCP 연결, HTTP 메시지, Node.js 프로세스, 컨테이너 종료 신호까지의 기본 흐름을 정리합니다.

> **TL;DR**<br>  
> - TCP 연결은 바이트 스트림을 제공하고, HTTP는 그 위에서 요청과 응답의 의미를 정의합니다.<br>  
> - Node.js의 `http.createServer()` handler는 HTTP 요청이 해석된 뒤 호출됩니다. 하나의 TCP 연결이 곧 하나의 HTTP 요청이라는 뜻은 아닙니다.<br>  
> - keep-alive는 연결 재사용을 가능하게 하지만, 항상 재사용을 보장하지는 않습니다. 클라이언트, 프록시, 서버 timeout과 종료 상태가 함께 결정합니다.<br>  
> - 컨테이너는 별도 VM이 아니라 프로세스 실행 경계입니다. 종료 시 애플리케이션이 `SIGTERM`을 처리하고 새 연결을 멈추며 진행 중 요청을 정리해야 합니다.  
{: .prompt-info}

---

## 1. 이 글의 범위와 도착 역량

이 글의 독자는 [TCP와 UDP](/posts/tcp-and-udp/)에서 다룬 TCP 바이트 스트림 특성과 Kubernetes Pod의 기본 개념을 알고, 이제 Node.js 서버를 처음부터 운영 관점으로 이해하려는 DevOps 엔지니어입니다. 읽은 뒤에는 HTTP 요청이 Node.js handler에 도착하는 흐름을 설명하고, keep-alive 재사용 여부를 관찰하며, `SIGTERM`을 받는 서버의 최소 종료 처리를 구현할 수 있어야 합니다.

다루지 않는 범위도 명확히 둡니다. TLS handshake, DNS, HTTP/2와 HTTP/3, reverse proxy 세부 설정, Event Loop 내부 단계, libuv Worker Pool, Worker Threads는 이후 글에서 다룹니다. 이 글에서 컨테이너와 Kubernetes는 요청 처리의 실행 경계와 종료 신호를 설명하는 데만 사용합니다.

TCP는 연결된 양 끝점 사이에 순서가 있는 바이트 스트림을 제공하지만 HTTP 요청 경계나 애플리케이션 처리 성공을 보장하지는 않습니다. HTTP는 method, target, header, status, body의 의미를 정의하지만 요청 처리의 병렬성이나 DB 작업 성공을 보장하지는 않습니다.

Node.js process는 포트를 listen하고 HTTP 요청을 handler로 전달합니다. Container runtime 또는 kubelet은 process에 종료를 요청하고 grace period를 적용하지만, 애플리케이션별 drain과 데이터 정합성은 보장하지 않습니다.

---

## 2. 요청은 TCP 연결과 같은 단위가 아닙니다

클라이언트는 서버의 IP 주소와 포트로 TCP 연결을 만들고, 그 연결의 바이트 흐름에 HTTP 요청을 기록합니다. TCP는 응용 메시지 경계를 보존하지 않으므로, 한 번의 socket read가 HTTP 요청 하나와 정확히 일치한다고 가정하면 안 됩니다. HTTP parser는 들어온 바이트를 읽어 request line, header, body 규칙에 따라 HTTP 메시지로 해석합니다.

HTTP/1.1 keep-alive가 유효하고 양 끝점이 연결을 유지하기로 하면 하나의 TCP 연결로 여러 HTTP 요청과 응답을 처리할 수 있습니다. 반대로 클라이언트 agent 설정, server timeout, reverse proxy 정책, max request 수, network 오류, 배포 중 drain 상태가 있으면 새 연결이 만들어질 수 있습니다. 따라서 "요청 두 번을 보냈는데 connection event가 하나였다"는 것은 연결 재사용의 관측 결과이지 Node.js가 요청을 하나만 처리했다는 뜻이 아닙니다.

![Node.js HTTP 요청 처리와 종료 제어 흐름](/assets/img/nodejs/node-http-request-lifecycle-flow.webp)
_Node.js process 안에서 accepted TCP socket의 byte stream을 HTTP parser가 해석하고, request event가 application handler를 호출합니다. 실선은 데이터 흐름, 점선은 container runtime 또는 kubelet의 종료 제어 흐름입니다._

그림의 왼쪽에서 오른쪽은 요청 처리의 논리 흐름입니다. HTTP parser, request event, application handler는 모두 Node.js process와 container boundary 안에 있습니다. 점선은 데이터 요청이 아니라 process termination 제어 흐름입니다. 실제 배포에서는 client와 Node.js 사이에 load balancer, Gateway, reverse proxy가 추가될 수 있지만, 각 홉에서도 TCP 연결과 HTTP 메시지의 구분은 유지됩니다.

---

## 3. Node.js `http` 서버가 하는 일

`http.createServer()`는 서버 객체를 만들고 request listener를 등록합니다. 서버가 `listen()`한 뒤 일반 HTTP 요청을 받으면 listener는 `IncomingMessage`와 `ServerResponse`를 받아 status, header, body를 작성합니다. connection event는 TCP socket이 수락될 때 관찰할 수 있고, 일반 request handler는 해석된 HTTP 요청마다 호출됩니다. 다만 `Expect: 100-continue`, `CONNECT`, protocol upgrade는 각각 `checkContinue`, `connect`, `upgrade` event로 별도 처리 경로를 가질 수 있으므로, 이 글의 실험은 일반 HTTP/1.1 request event만 대상으로 합니다.

다음 예제는 요청과 연결을 각각 로그로 남기고, `SIGTERM` 때 새 연결 수락을 중단하는 최소 서버입니다. 실제 서비스에서는 readiness 전환, 외부 연결 drain, timeout, 강제 종료 정책을 서비스 특성에 맞게 추가해야 합니다.

```js
import http from 'node:http';

const server = http.createServer((request, response) => {
  console.log(`request method=${request.method} url=${request.url} socket=${request.socket.remotePort}`);
  response.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify({ ok: true, pid: process.pid }));
});

server.on('connection', (socket) => {
  console.log(`connection remotePort=${socket.remotePort}`);
});

server.listen(4310, '127.0.0.1', () => {
  console.log(`listening pid=${process.pid}`);
});

process.on('SIGTERM', () => {
  console.log('received SIGTERM: stop accepting new connections');
  server.close((error) => {
    console.log(`server.close callback error=${error ?? 'none'}`);
    process.exitCode = error ? 1 : 0;
  });

  setTimeout(() => {
    console.error('forced shutdown after 5000ms');
    process.exit(1);
  }, 5000).unref();
});
```

`server.close()`의 현재 Node.js 문서는 새 연결 수락을 중단하고, 요청을 보내거나 응답을 기다리지 않는 idle connection을 닫는다고 설명합니다. 장기 연결, streaming response, WebSocket upgrade처럼 일반 HTTP 요청보다 오래가는 연결은 별도 종료 설계가 필요합니다. "`server.close()`를 호출했으므로 모든 작업이 즉시 안전하게 끝난다"고 일반화하면 안 됩니다.

또한 non-Windows Node.js에서 `SIGTERM` listener를 등록하면 기본 종료 동작이 제거됩니다. handler에서 로그만 남기면 process가 계속 실행될 수 있으므로, 위 예제처럼 close를 시작하고 event loop가 비워지도록 하거나 제한 시간 뒤 명시적으로 종료해야 합니다.

---

## 4. 같은 연결의 두 요청과 `SIGTERM`을 직접 관찰하기

아래 client는 keep-alive agent로 순차 요청 두 개를 보냅니다. `reusedSocket`은 Node.js client가 해당 요청에 기존 socket을 재사용했는지 보여 줍니다.

```js
import http from 'node:http';

const agent = new http.Agent({ keepAlive: true, maxSockets: 1 });

function requestOnce(path) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host: '127.0.0.1', port: 4310, path, agent }, (response) => {
      response.resume();
      response.on('end', () => {
        console.log(`client status=${response.statusCode} reusedSocket=${request.reusedSocket}`);
        resolve();
      });
    });
    request.on('error', reject);
  });
}

await requestOnce('/first');
await requestOnce('/second');
agent.destroy();
```

Node.js `v26.5.0` 환경에서 위 server와 client를 실행한 뒤 server process에 `SIGTERM`을 보낸 실제 결과는 다음과 같습니다.

```text
client status=200 reusedSocket=false
client status=200 reusedSocket=true

listening pid=44938
connection remotePort=34744
request method=GET url=/first socket=34744
request method=GET url=/second socket=34744
received SIGTERM: stop accepting new connections
server.close callback error=none
```

두 번째 client 요청의 `reusedSocket=true`와 server의 connection log 한 줄, 같은 remote port는 이 실험에서 하나의 TCP 연결이 두 HTTP 요청에 재사용됐다는 증거입니다. 이는 특정 Node.js version, localhost network, 순차 요청, 명시적인 keep-alive agent 조건의 결과입니다. browser, proxy, HTTP version, concurrent request 수가 달라지면 관측 결과도 달라질 수 있습니다.

같은 환경에서 `/slow` 요청을 처리하는 동안 `SIGTERM`을 보내는 별도 drain 실험도 실행했습니다. 이 실험은 새 연결을 성공적으로 처리했다는 보장이 아니라, `server.close()` 호출 뒤 listen socket이 닫혀 새 TCP 연결이 거절되고 기존 handler가 종료 전까지 완료되는 한 가지 조건을 확인합니다.

```text
listening
request_start path=/slow
sigterm
request_end path=/slow status=200
close_callback
```

실험에서 SIGTERM 뒤 새 연결은 `ECONNREFUSED`였고, 이미 시작한 `/slow` 요청은 `200`으로 끝났습니다. 장기 streaming response, WebSocket, downstream database transaction은 이 재현 범위에 없으므로 같은 종료 결과를 보장한다고 해석하면 안 됩니다.

---

## 5. 컨테이너 종료는 프로세스 종료 요청입니다

컨테이너는 애플리케이션이 실행되는 별도 VM이 아니라, namespace와 cgroup 같은 Linux 기능으로 격리된 프로세스 실행 환경입니다. 따라서 컨테이너 종료의 핵심 질문은 "Node.js main process가 어떤 signal을 받고, 새 요청과 진행 중 요청을 어떻게 정리하는가"입니다.

Docker의 `docker stop`은 기본적으로 컨테이너 안의 main process에 `SIGTERM`을 보내고 grace period 뒤 `SIGKILL`을 보냅니다. `STOPSIGNAL` 또는 CLI option으로 첫 signal은 바꿀 수 있습니다. `SIGKILL`은 process handler가 가로챌 수 없으므로, drain에 필요한 작업은 grace period 안에 끝나야 합니다.

Kubernetes에서도 Pod deletion이 시작되면 kubelet은 container runtime에 각 container의 main process 종료를 요청합니다. 현재 Kubernetes 문서는 일반적인 graceful termination에서 TERM signal과 grace period를 사용한다고 설명하며, image의 `STOPSIGNAL`을 존중하는 runtime도 있을 수 있음을 명시합니다. 따라서 운영 이미지를 inspect하거나 실제 종료 실험을 하기 전에는 signal 이름을 고정 가정하지 않습니다. container runtime 요청은 비동기이고 처리 순서가 보장되지 않으므로, 여러 container가 있는 Pod에서 sidecar와 application의 종료 순서를 임의로 가정하면 안 됩니다.

서비스 종료를 설계할 때의 최소 순서는 다음과 같습니다.

1. readiness가 새 트래픽을 받지 않도록 전환되는지 확인합니다.
2. `SIGTERM` handler에서 새 연결 수락을 중단합니다.
3. 진행 중 요청, background job, downstream connection을 제한 시간 안에 정리합니다.
4. grace period를 넘길 경우 강제 종료가 일어날 수 있음을 metric과 log로 남깁니다.

Kubernetes Service와 EndpointSlice가 terminating Pod를 어떤 시점에 제외하는지, preStop hook을 언제 쓰는지, HTTP keep-alive 또는 long-lived connection을 어떻게 drain하는지는 다음 운영 심화 단계에서 cluster version과 traffic path를 기준으로 별도 검증해야 합니다.

---

## 6. 장애가 나면 어느 경계를 먼저 확인할까요

HTTP 5xx나 connection reset이 보이면 바로 "Node.js가 느리다"고 결론 내리지 않습니다. 요청의 어느 경계에서 끊겼는지부터 좁힙니다.

| 관측 질문 | 확인 예시 | 다음 가설 |
| --- | --- | --- |
| process가 listen 중인가 | `ss -ltnp`, application startup log | port bind 실패, process 종료, 잘못된 listen address |
| TCP 연결은 되는가 | `curl -v`, load balancer health check | network policy, Service endpoint, proxy route |
| HTTP handler까지 왔는가 | request log, trace ID, access log | request parsing, route, middleware, upstream timeout |
| 종료 중이었는가 | `SIGTERM` log, Pod event, termination timestamp | rollout drain, grace period 부족, forced kill |
| 같은 connection이 재사용됐는가 | socket/connection log, client `reusedSocket` | keep-alive timeout, proxy connection policy |

이 표는 진단 순서의 출발점입니다. 운영 환경에서는 request timestamp, Pod name, container restart count, error rate, p95/p99 latency, connection 수를 같은 시간 창에서 비교해야 인과관계를 판단할 수 있습니다. 다음 글에서는 handler 안의 비동기 작업을 이해하기 위한 Promise와 module boundary를 다룹니다.

---

## 7. 학습 점검

- [ ] TCP 바이트 스트림과 HTTP 요청 경계가 다른 이유를 설명할 수 있는가?
- [ ] Node.js의 connection event와 request handler가 각각 언제 관찰되는지 구분할 수 있는가?
- [ ] keep-alive 재사용 여부를 `reusedSocket`과 server log로 확인할 수 있는가?
- [ ] `SIGTERM`, grace period, `SIGKILL`의 역할 차이를 설명할 수 있는가?
- [ ] 장애 시 process, TCP, HTTP handler, termination 중 어느 경계를 먼저 확인할지 정할 수 있는가?

---

## 8. Reference

- [Node.js Documentation - HTTP](https://nodejs.org/api/http.html)
- [Node.js Documentation - Net](https://nodejs.org/api/net.html)
- [Node.js Documentation - Process Signal Events](https://nodejs.org/api/process.html#signal-events)
- [Docker Documentation - docker container stop](https://docs.docker.com/reference/cli/docker/container/stop/)
- [Kubernetes Documentation - Pod Termination Flow](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination-flow)
- [RFC 9110 - HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- [RFC 9293 - Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
