---
title: Kubernetes Graceful Shutdown이란?
date: 2024-12-24 22:05:51 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, pod, shutdown, graceful, graceful-shutdown, pod-graceful-shutdown]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

**Graceful Shutdown**은 프로세스(애플리케이션)가 종료 요청을 받았을 때(예: `SIGTERM`), 바로 강제 종료되지 않고 일정 시간을 두어 정리 작업(예: DB Connection, Message Queue)을 수행한 뒤 종료되는 방식입니다. **Graceful Shutdown**이 이루어지지 않고 **Ungraceful Shutdown**이 이루어지게 되면 이미 종료된 pod로 트래픽이 흘러가 500번대 에러를 마주할 수도 있으며 DB 트랜젝션 중 데이터 불일치 발생, 로그 데이터 유실 등의 다양한 문제를 직면할 수 있습니다.

Kubernetes 환경에서는 Scale-In, Rolling Update, Node Failure 등의 이유로 pod가 언제든 종료될 수 있습니다. 따라서 앞선 문제를 피하기 위해 **Graceful Shutdown**을 통해 pod가 안전하게 종료되도록 처리하는 것이 중요합니다.

---

## 1. Kubernetes에서 Graceful Shutdown

![Graceful Shutdown](/assets/img/kubernetes/graceful-shutdown.webp)

> **Graceful Shutdown** 절차  
>
> 1. api-server에 pod 삭제 요청  
> 2. kubelet과 kube-proxy가 api-server를 통해 pod 상태 변경(삭제 요청)을 감지  
> 3. kube-proxy는 해당 pod로 더 이상 트래픽이 전달되지 않도록 iptables 혹은 ipvs 규칙에서 해당 pod의 IP를 제거  
> 4. kubelet은 pod에 정의된 `preStop` 절차에 따라 **Graceful Shutdown** 후, pod에 `SIGTERM` 전송  
> 5. `terminationGracePeriodSecond`가 정의되어있고, 해당 pod가 해당 시간안에 종료가 되지 않았을 시, `SIGKILL`을 통해 강제 종료  
{: .prompt-tip}

---

## 2. 실습

> FastAPI를 통해 간단한 실습을 해보도록 하겠습니다.  
{: .prompt-tip}

### 2.1. FastAPI 애플리케이션 배포

> 실습을 위해 아래의 간단한 FastAPI 애플리케이션을 만들어 사용했습니다.  
> SIGTERM을 통해 애플리케이션이 종료될 때 print와 sleep을 통해 확인할 수 있도록 하였습니다.  
> 상세한 정보는 GitHub에서 확인이 가능합니다. <https://github.com/KKamJi98/kubernetes-graceful-shutdown-fastapi>  
{: .prompt-tip}

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

# 애플리케이션 상태를 관리할 글로벌 플래그
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FastAPI application is starting up...")  # Startup logic
    yield
    print("FastAPI application is shutting down...")  # Shutdown logic
    await asyncio.sleep(5)  # Graceful Shutdown 작업 (ex: DB Connection 등)
    print("FastAPI application shutting down complete!")

# Lifespan을 사용하는 FastAPI 애플리케이션
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI"}
```

### 2.2. FastAPI 애플리케이션 Deployment 정의 파일

> deployment를 통해 pod를 생성하였고, `lifecycle.preStop`을 정의해 pod가 graceful하게 shutdown될 수 있도록 했습니다.  
> 또한 아래와 같이 `terminationGracePeriodSeconds` 옵션을 통해 60초 안에 pod가 graceful shutdown 되지 않을 시, 강제 종료하도록 설정할 수 있습니다.  
{: .prompt-tip}

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-graceful
  namespace: kkamji
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fastapi-graceful
  template:
    metadata:
      labels:
        app: fastapi-graceful
    spec:
      imagePullSecrets:
      - name: harbor-registry
      terminationGracePeriodSeconds: 60
      containers:
      - name: fastapi
        image: harbor.kkamji.net/kkamji/graceful-shutdown
        ports:
        - containerPort: 8000
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "echo 'Running preStop hook'; sleep 30"]
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 3
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 3
          periodSeconds: 5
```

### 2.3. pod 상태 및 로그 확인

```bash
❯ kubectl get po
NAME                                READY   STATUS    RESTARTS   AGE
fastapi-graceful-797fbdfcc9-sfkm2   1/1     Running   0          87s

❯ kubectl logs fastapi-graceful-797fbdfcc9-sfkm2                                                                   
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
FastAPI application is starting up...
INFO:     10.0.0.201:40562 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.201:40546 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.201:40572 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.201:40574 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.201:48024 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.201:48012 - "GET / HTTP/1.1" 200 OK
```

### 2.4. Graceful Shutdown 테스트

> `kubectl logs` 명령어의 `-f`, 옵션과 `kubectl get pods` 명령어의 `-w` 옵션을 통해 실시간으로 pod의 상태와 로그를 확인하며 정상 동작하는 pod에 `kubectl delete pod {pod_name}` 명령어로 삭제 요청을 한 뒤 상태 변화를 확인해보도록 하겠습니다.  
{: .prompt-tip}

#### 2.4.1. 로그 실시간 확인

```bash
❯ kubectl logs fastapi-graceful-797fbdfcc9-sfkm2 -f --tail=20
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
FastAPI application is starting up...
INFO:     10.0.0.202:32808 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:32810 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:42842 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:42840 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:42850 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:42862 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:57996 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:57998 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:58006 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:58008 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:59300 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:59298 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:59308 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:48250 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:48264 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51742 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51756 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:52932 - "GET / HTTP/1.1" 200 OK
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [1]
FastAPI application is shutting down...
FastAPI application shutting down complete!
```

#### 2.4.2. pod 실시간 확인

```bash
❯ kubectl get po -w
NAME                                READY   STATUS    RESTARTS   AGE
fastapi-graceful-797fbdfcc9-sfkm2   1/1     Running   0          3m13s
```

#### 2.4.3. pod 삭제 요청

```bash
❯ kubectl delete pod fastapi-graceful-797fbdfcc9-sfkm2
pod "kubectl logs fastapi-graceful-797fbdfcc9-sfkm2" deleted
```

### 2.5. 결과 확인

> 애플리케이션이 종료되며 Shutdown logic을 통해 모든 작업을 마무리하는 것을 log를 통해 확인할 수 있으며 pod가 바로 종료되지 않고, preStop 훅이 실행된 후, 30초 뒤 `SIGTERM` 신호를 받아 Pod가 Completed 상태로 종료되는 것을 확인할 수 있습니다.  
{: .prompt-tip}

```bash
❯ kubectl get po -w
NAME                                READY   STATUS    RESTARTS   AGE
fastapi-graceful-797fbdfcc9-sfkm2   1/1     Running   0          11s
fastapi-graceful-797fbdfcc9-sfkm2   1/1     Terminating   0          32s
fastapi-graceful-797fbdfcc9-sfkm2   1/1     Terminating         0          68s
fastapi-graceful-797fbdfcc9-sfkm2   0/1     Completed           0          68s
fastapi-graceful-797fbdfcc9-sfkm2   0/1     Completed           0          69s
fastapi-graceful-797fbdfcc9-sfkm2   0/1     Completed           0          69s
```

```bash
❯ kubectl logs fastapi-graceful-5dd7b8d775-kzdqx -f --tail=20
INFO:     10.0.0.202:57636 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:57638 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:55126 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:55130 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:55140 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:55142 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:56160 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:56162 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:56174 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:56172 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51396 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51398 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51404 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:51406 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:44870 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:44868 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:44874 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:44876 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:47514 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:47498 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:43434 - "GET / HTTP/1.1" 200 OK
INFO:     10.0.0.202:43436 - "GET / HTTP/1.1" 200 OK
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     FastAPI application shutting down complete!
INFO:     Finished server process [1]
FastAPI application is shutting down...
FastAPI application shutting down complete!
```

---

## 3. 결론

쿠버네티스 환경에서 Graceful Shutdown은 무중단 배포(Rolling Update)나 스케일 인·아웃 등의 과정에서 데이터 무결성을 지키고, 에러 없는 종료를 위해 필수적으로 고려해야 할 요소입니다.

- Pod 종료 시점에 `preStop` 훅과 `SIGTERM` 신호를 활용해, 애플리케이션이 DB 커넥션 정리, 로그 Flush, Queue ACK 등의 작업을 수행할 수 있게 됩니다.
- kube-proxy가 Pod IP를 Service 엔드포인트에서 제거하여 새 트래픽이 더 이상 해당 Pod로 가지 않도록 처리함으로써, 사용 중인 연결을 안전하게 정리할 시간을 확보합니다.
- `terminationGracePeriodSeconds`을 통해 “최대 대기 시간”을 정의하면, 정리 작업이 그 시간 안에 끝나지 못했을 때 강제 종료(`SIGKILL`) 가 발생하도록 설정할 수 있습니다.

이를 통해 Pod IP가 언제든 바뀌거나 Pod가 재시작되는 불안정한 상황에서도 안정적이고 예측 가능한 애플리케이션 종료를 구현할 수 있습니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
