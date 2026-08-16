---
title: Goroutine이란?
date: 2024-01-15 15:54:32 +0900
author: kkamji
categories: [Programming Language, Go]
tags: [go, go routine, goroutine, concurrency, parallelism]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

![Goroutine scheduling model](/assets/img/go/goroutine-scheduling-model.webp)

동시성과 병렬성은 자주 같은 말처럼 쓰이지만 서로 다른 개념입니다. 코어가 하나뿐인 기계에서도 동시성은 성립하고, 병렬성은 코어가 여럿이어야 성립합니다. Go는 goroutine과 채널로 동시성을 언어 차원에서 다루고, 실제로 몇 개의 코어에 펼칠지는 런타임이 결정합니다. 둘의 차이와 `runtime.GOMAXPROCS()`, `sync.WaitGroup`이 각각 어느 쪽에 관여하는지 정리합니다.

---

## 1. 동시성과 병렬성

> Goroutine은 동시성과 병렬성을 매우 간결하고 효과적으로 다룰 수 있는 기능을 제공합니다.  

### 1.1. 동시성(Concurrency)

- **싱글 코어에서 멀티 쓰레드 동작**
- 여러 작업을 시간을 나누어 사용함으로써 동시에 실행되는 것처럼 보이는 기술입니다.
- 실제로는 한 순간에 하나의 작업만 처리하지만, 작업들 사이를 빠르게 전환하면서 동시에 진행되는 것처럼 보이게 합니다.
- 단일 코어 환경에서 효율적인 자원 사용과 빠른 응답 시간을 목표로 사용됩니다.

### 1.2. 병렬성(Parallelism)

- **멀티 코어에서 멀티 쓰레드 동작**
- 여러 작업을 실제로 동시에 실행하는 기술입니다.
- 멀티코어 프로세서를 사용하며, 각 코어에서 별도의 작업을 동시에 수행합니다.
- 멀티코어 환경에서 성능을 극대화하기 위해 사용됩니다.

---

## 2. 몇 개의 코어에 펼칠지 정하는 GOMAXPROCS

> `runtime.GOMAXPROCS()` 함수는 프로그램이 동시에 실행할 수 있는 최대 CPU 코어 수를 설정합니다.  
Go 1.5 버전부터 `runtime.GOMAXPROCS()`의 기본값은 시스템에서 사용 가능한 물리적 CPU 코어 수로 설정되어 있습니다.  

---

## 3. goroutine 실행 예시

`go` 키워드를 붙이면 호출이 새 goroutine에서 시작되고 호출한 쪽은 기다리지 않고 다음 줄로 넘어갑니다. 아래 예시는 같은 함수를 동기로 한 번, 비동기로 세 번 호출해 출력 순서가 어떻게 달라지는지 보여줍니다.

```go
package main

import (
	"fmt"
	"time"
)

func printHelloWorld(strIn string) {
	for i := 0; i < 10; i++ {
		fmt.Println(strIn, "hello world", i)
	}
}

func main() {
	// 기존 -> 동기적
	printHelloWorld("Sync")

	// Goroutine -> 비동기적
	go printHelloWorld("Async1")
	go printHelloWorld("Async2")
	go printHelloWorld("Async3")

	time.Sleep(time.Second * 3)
}
```

### 3.1. 익명 함수와 WaitGroup

```go
package main

import (
	"fmt"
	"sync"
)

func main() {
	// WaitGroup 생성. 2개의 Goroutine이 끝날 때까지 기다리기
	var wait sync.WaitGroup
	wait.Add(2)

	go func() {
		defer wait.Done()
		fmt.Println("Hello")
	}()

	go func(msg string) {
		defer wait.Done()
		fmt.Println(msg)
	}("Hi")

	wait.Wait() // Go 루틴이 모두 끝날 때까지 대기
}
```

---

## 4. Reference

- [Go Docs - Effective Go: Concurrency](https://go.dev/doc/effective_go#concurrency)
- [Go Blog - Concurrency is not parallelism](https://go.dev/blog/waza-talk)
- [Go Docs - runtime.GOMAXPROCS](https://pkg.go.dev/runtime#GOMAXPROCS)
- [Go Docs - sync.WaitGroup](https://pkg.go.dev/sync#WaitGroup)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
