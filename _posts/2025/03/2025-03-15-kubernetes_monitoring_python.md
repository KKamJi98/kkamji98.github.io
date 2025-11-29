---
title: Kubernetes Monitoring Tool 개발 (KMP)
date: 2025-03-15 16:55:36 +0900
author: kkamji
categories: [Monitoring & Observability, Metric]
tags: [kubernetes, monitoring, python, cli, devops, sre, eks, aws]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Kubernetes를 운영하면서 자주 반복적으로 사용하는 명령어들이 있습니다. 그때마다 매번 머릿속의 kubectl 명령어를 직접 입력하거나, 미리 정리해둔 명령어를 복사해서 사용하는 경우가 많았습니다.  
  
그러던 중 문득 "자주 쓰는 명령어를 나만의 alias로 등록하거나 간단한 CLI 툴로 만들어보면 어떨까?" 라는 생각이 들었고, 이를 계기로 평소 자주 사용하는 Kubernetes 모니터링 기능들을 모아 하나의 도구로 만들게 되었습니다.  

GitHub: <https://github.com/KKamJi98/monitoring-kubernetes>  

---

## 1. 실행 화면

```shell
===== Kubernetes Monitoring Tool =====
1) Event Monitoring (Normal, !=Normal)
2) Error Pod Catch (가장 최근에 재시작된 컨테이너 N개 확인)
3) Error Log Catch (가장 최근에 재시작된 컨테이너 N개 확인 후 이전 컨테이너의 로그 확인)
4) Pod Monitoring (생성된 순서) [옵션: Pod IP 및 Node Name 표시]
5) Pod Monitoring (Running이 아닌 Pod) [옵션: Pod IP 및 Node Name 표시]
6) Pod Monitoring (전체/정상/비정상 Pod 개수 출력)
7) Node Monitoring (생성된 순서) [AZ, NodeGroup 표시 및 필터링 가능]
8) Node Monitoring (Unhealthy Node 확인) [AZ, NodeGroup 표시 및 필터링 가능]
9) Node Monitoring (CPU/Memory 사용량 높은 순 정렬) [NodeGroup 필터링 가능]
Q) Quit
Select an option:
```

---

## 2. 주요 기능

1. Event Monitoring  
   - 특정 혹은 전체 네임스페이스에서 발생하는 모든 이벤트를 실시간으로 확인할 수 있습니다.  
   - 옵션을 통해 이벤트 타입이 `Normal`이 아닌 리소스만 필터링할 수 있습니다.

2. Error Pod Catch  
   - 문제가 생겨 재시작된 컨테이너를 최근 순으로 빠르게 확인할 수 있습니다.  

3. Error Log Catch  
   - 재시작된 컨테이너의 이전 로그를 지정한 줄 수 만큼 확인할 수 있습니다.  

4. Pod Monitoring  
   - 상태가 비정상인 Pod, 전체 Pod 개수를 간편하게 확인할 수 있습니다.  
   - 특정 혹은 전체 네임스페이스에서 생성된 시간을 기반으로 정렬된 Pod 리스트를 확인할 수 있습니다.

5. Node Monitoring  
   - Unhealthy 노드, 리소스 사용량이 높은 노드를 쉽게 파악할 수 있습니다.
   - 옵션을 통해 특정 노드 그룹만 따로 조회할 수 있습니다.

자세한 사용법과 옵션 설명은 [GitHub 저장소](https://github.com/KKamJi98/monitoring-kubernetes)의 README에서 확인할 수 있습니다.

---

## 3. 설치 및 실행

사전 요구 사항

- Python 3.10 이상
- `kubectl`과 유효한 `KUBECONFIG`
- Kubernetes Metrics Server(옵션 9 사용 시)

```bash
git clone https://github.com/KKamJi98/monitoring-kubernetes.git
cd monitoring-kubernetes

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py
```

실행 후 메뉴에서 원하는 번호를 입력하고 프롬프트에 따라 네임스페이스, 출력 개수 등의 조건을 선택하면 됩니다.

---

## 4. 마무리

이 툴을 만들면서 가장 크게 느낀 점은 "작은 귀찮음" 하나가 개발의 좋은 출발점이 될 수 있다는 것입니다. 평소 Kubernetes 운영에서 반복되는 명령어 입력이나, 작은 모니터링 업무가 귀찮다는 이유 하나로 시작한 간단한 툴이었지만, 직접 만들고 나니 생각보다 큰 성취감을 느꼈습니다.  
처음부터 대단한 프로그램을 만들어야겠다고 생각하면 부담스럽고 시작조차 하지 못했을 거라 생각합니다. 비록 단순히 귀찮음을 해결하려고 만든 기능이 단순하고 누구나 만들 수 있을 정도의 간단한 프로그램이지만, 앞으로도 꾸준히 이렇게 한 발짝 한 발짝 나아가다 보면 언젠가 여럿이 편리하게 사용할 수 있는 더 좋은 툴을 만들 수 있지 않을까 기대합니다.  

여러분도 Kubernetes 운영뿐만 아니라 평소 업무에서 반복되는 작은 불편함이 있다면, 간단한 스크립트나 나만의 CLI 툴을 만들어 보시길 추천합니다. 제 프로그램을 그대로 사용하셔도 좋고, 제 코드를 여러분만의 스타일로 변경하여 본인에게 최적화된 툴을 만들어 보시는 것도 좋겠습니다.
작은 시작이 모여서 더 큰 성장으로 이어지길 바라며, 제 코드를 통해 조금이나마 영감을 얻어 가셨으면 좋겠습니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
