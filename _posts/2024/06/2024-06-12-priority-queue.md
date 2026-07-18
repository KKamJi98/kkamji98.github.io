---
title: Priority queue 개념, 사용 방법
date: 2024-06-12 20:31:44 +0900
author: kkamji
categories: [CS, Data Structure]
tags: [priority-queue, python, heap, heapq]     # TAG names should always be lowercase
comments: true
# image:
# path: /assets/img/kkam-img/kkam.webp
---

## 1. TL;DR

- 우선순위 큐(priority queue)는 먼저 넣은 순서가 아니라 우선순위에 따라 다음 원소를 꺼내는 자료구조다.
- Python의 `heapq`는 기본적으로 최소 힙(min-heap)이다. 가장 작은 원소는 항상 `heap[0]`에 있다.
- 같은 우선순위에서 처리 순서를 보존하거나 작업 객체를 안전하게 넣으려면 `(priority, sequence, task)` 튜플을 사용한다.
- Python 3.14 이상은 최대 힙 API를 제공한다. 그보다 낮은 버전에서는 음수 우선순위 방식이 호환되는 선택지다.

---

## 2. 우선순위 큐와 힙

일반 큐는 먼저 들어온 원소를 먼저 꺼내는 FIFO(first in, first out) 구조다. 반면 **우선순위 큐**는 각 원소의 우선순위를 비교해 다음 원소를 정한다. Python의 `heapq`에서는 값이 작을수록 먼저 나온다.

**힙(heap)** 은 부모와 자식 사이의 순서 규칙을 만족하는 완전 이진 트리를 리스트에 표현한 자료구조다. 최소 힙의 불변 조건은 다음과 같다.

```text
heap[k] <= heap[2 * k + 1]
heap[k] <= heap[2 * k + 2]
```

인덱스가 존재하는 경우에만 비교한다. 이 조건은 부모가 자식보다 작거나 같다는 뜻이며, 전체 리스트가 정렬되어 있다는 뜻은 아니다. 따라서 가장 작은 원소는 `heap[0]`에서 즉시 확인할 수 있지만, 나머지 원소의 순서는 정렬된 결과가 아니다.

```text
        1
      /   \
     3     2
    / \
   7   8
```

`heappush()`와 `heappop()`은 힙 높이만큼 원소를 이동하므로 보통 O(log n) 시간에 동작한다. `heapify()`는 기존 리스트를 제자리에서 최소 힙으로 바꾸며 O(n) 시간에 동작한다.

---

## 3. `heapq`의 기본 API

| 함수 | 동작 | 빈 힙일 때 |
| --- | --- | --- |
| `heapq.heapify(x)` | 리스트 `x`를 제자리 최소 힙으로 변환 | 해당 없음 |
| `heapq.heappush(heap, item)` | 원소를 추가하고 힙 조건 유지 | 해당 없음 |
| `heapq.heappop(heap)` | 가장 작은 원소를 제거하고 반환 | `IndexError` |
| `heapq.heappushpop(heap, item)` | 추가 후 가장 작은 원소를 반환 | 빈 힙에서도 동작 |
| `heapq.heapreplace(heap, item)` | 가장 작은 원소를 반환하고 새 원소 추가 | `IndexError` |

`heappushpop()`과 `heapreplace()`는 비슷해 보이지만 반환 규칙이 다르다. `heappushpop()`은 새 원소와 기존 최솟값 중 작은 값을 반환하고 큰 값을 힙에 남긴다. `heapreplace()`는 기존 힙의 최솟값을 반드시 반환한 뒤 새 원소를 넣는다.

---

## 4. 안정적인 최소 우선순위 큐

작업 자체가 비교 가능하지 않거나, 같은 우선순위의 삽입 순서를 보존해야 한다면 `(priority, sequence, task)`를 넣는다. 튜플은 첫 번째 값부터 순서대로 비교하므로 `sequence`이 동점 처리 기준이 된다.

```python
import heapq
from itertools import count

queue = []
sequence = count()

def push(priority, task):
    heapq.heappush(queue, (priority, next(sequence), task))

def pop():
    priority, _, task = heapq.heappop(queue)
    return priority, task

push(2, {"name": "report"})
push(1, {"name": "deploy"})
push(2, {"name": "backup"})

while queue:
    priority, task = pop()
    print(priority, task["name"])

# 1 deploy
# 2 report
# 2 backup
```

단순히 `(priority, task)`만 넣으면 우선순위가 같은 경우 Python이 `task`끼리 비교하려 한다. `dict`처럼 비교할 수 없는 객체를 넣으면 `TypeError`가 발생할 수 있다.

---

## 5. 최대 우선순위가 먼저 필요한 경우

최대 힙(max-heap)은 부모가 자식보다 크거나 같은 힙이다. Python 3.14부터 `heapify_max()`, `heappush_max()`, `heappop_max()` 같은 최대 힙 API를 제공한다.

```python
import heapq

queue = []
heapq.heappush_max(queue, 2)
heapq.heappush_max(queue, 5)
heapq.heappush_max(queue, 3)

print(heapq.heappop_max(queue))  # 5
```

Python 3.13 이하를 지원해야 한다면 최소 힙에 음수 우선순위를 넣는 방식이 호환된다.

```python
import heapq

queue = []
heapq.heappush(queue, (-5, "urgent"))
heapq.heappush(queue, (-2, "normal"))

priority, task = heapq.heappop(queue)
print(-priority, task)  # 5 urgent
```

---

## 6. `heapq`와 `queue.PriorityQueue`의 선택

`heapq`는 리스트를 직접 다루는 저수준 API로, 단일 스레드 처리나 별도 동기화가 있는 코드에 적합하다. 여러 생산자와 소비자 스레드가 하나의 큐를 안전하게 공유해야 한다면 락을 제공하는 `queue.PriorityQueue`를 검토한다. 이 클래스도 가장 낮은 값부터 꺼낸다.

```python
from queue import PriorityQueue

queue = PriorityQueue()
queue.put((1, "deploy"))
queue.put((2, "report"))

print(queue.get())  # (1, 'deploy')
```

---

## 7. 자료 범위와 한계

이 글의 `heapq` API 설명은 Python 3.14 이상 공식 문서를 기준으로 한다. 특히 최대 힙 함수는 Python 3.14에 추가되었으므로, 실행 환경의 Python 버전을 먼저 확인해야 한다. 시간 복잡도는 힙 연산 자체의 특성이며, 작업 처리 시간이나 스레드 경합 시간까지 포함하지 않는다.

---

## 8. Reference

- [Python `heapq` documentation](https://docs.python.org/3/library/heapq.html)
- [Python `queue.PriorityQueue` documentation](https://docs.python.org/3/library/queue.html#queue.PriorityQueue)

<br><br>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
