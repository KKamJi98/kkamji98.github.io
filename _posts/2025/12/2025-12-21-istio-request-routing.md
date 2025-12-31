---
title: Istio Request Routing 실습 [Istio Study 2]
date: 2025-12-21 21:00:00 +0900
author: kkamji
categories: [Kubernetes, Istio]
tags: [kubernetes, istio, request-routing, virtualservice, destinationrule, traffic-management, canary, ab-test, envoy, kiali]
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

서비스 메시의 핵심 가치는 **트래픽 제어를 애플리케이션 밖에서 일관되게 수행**하는 데 있습니다. Istio의 **Request Routing** 기능을 활용하면 동일 서비스의 버전별 트래픽 분산, 사용자 그룹별 라우팅, 점진적 배포를 손쉽게 구현할 수 있습니다.

이번 글에서는 Bookinfo 데모 애플리케이션을 대상으로 DestinationRule과 VirtualService를 적용해 **헤더 기반 라우팅**을 구현하고, Envoy 로그와 Kiali로 동작을 검증합니다.

---

## 1. Request Routing이 필요한 이유

- **트래픽 분산**: 버전별 트래픽 비율 제어
- **A/B 테스트**: 사용자 그룹별 다른 버전 노출
- **카나리 배포**: 점진적 전환으로 배포 안정성 확보

---

## 2. 사전 준비

- Bookinfo 애플리케이션이 배포되어 있어야 합니다.
- `default` 네임스페이스에 Sidecar 자동 주입이 활성화되어 있어야 합니다.

### 실습 코드 받기

```shell
git clone https://github.com/KKamJi98/kkamji-lab.git 
cd kkamji-lab/study/istio-study/02-request-routing/
```

```shell
kubectl get pods -n default
kubectl get ns default --show-labels
```

---

## 3. DestinationRule & VirtualService 적용

```shell
kubectl apply -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/bookstore-app/destination-rule.yaml
kubectl apply -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/bookstore-app/virtual-service.yaml
```

위 명령은 `reviews` 서비스에 대한 **DestinationRule**(v1/v2 subset 정의)과 **VirtualService**(헤더 기반 라우팅 규칙)를 생성합니다.

**설정 요약**

- `end-user: admin` → **reviews:v2**로 라우팅
- 그 외 사용자 → **reviews:v1**로 라우팅

아래는 적용된 리소스의 핵심 구조 예시입니다.

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
  - reviews
  http:
  - match:
    - headers:
        end-user:
          exact: admin
    route:
    - destination:
        host: reviews
        subset: v2
  - route:
    - destination:
        host: reviews
        subset: v1
```

---

## 4. 라우팅 동작 검증

```shell
kubectl get nodes -o wide
open http://<EXTERNAL-IP>:30010/productpage
```

**검증 시나리오**

1. `Sign in` 클릭
2. Username에 `admin` 입력 (Password는 임의 입력)
3. 새로고침 시 별점(Star Ratings)이 보이면 `reviews:v2`가 호출된 상태입니다.

![Bookinfo 로그인 화면](/assets/img/kubernetes/istio-study/01_bookinfo_login.webp)

---

## 5. Envoy 액세스 로그로 요청 경로 확인

Envoy access log를 활성화하면 라우팅 결과를 정밀하게 확인할 수 있습니다.

```shell
cat <<EOF > istio-cni.yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  components:
    cni:
      namespace: istio-system
      enabled: true
    pilot:
      k8s:
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
  meshConfig:
    accessLogFile: /dev/stdout
    accessLogEncoding: JSON
    accessLogFormat: |
      {
        "req_method": "%REQ(:METHOD)%",
        "req_path": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%",
        "res_code": "%RESPONSE_CODE%",
        "upstream_info": "%UPSTREAM_CLUSTER_RAW%",
        "req_headers_end-user": "%REQ(end-user)%"
      }
EOF

istioctl install -f istio-cni.yaml -y

kubectl logs deployments/productpage-v1 -c istio-proxy
```

**로그 해석 포인트**

- `req_headers_end-user`: 헤더 기반 라우팅 여부 확인
- `upstream_info`: 실제 라우팅된 서비스 버전 확인
- `res_code`: 응답 코드 확인

![Pod Detail](/assets/img/kubernetes/istio-study/02_pod_detail.webp)

---

## 6. Kiali로 트래픽 시각화

```shell
istioctl dashboard kiali
```

![Traffic Visualization](/assets/img/kubernetes/istio-study/03_kiali_traffic.webp)

Kiali에서는 서비스 간 트래픽 흐름, 응답 시간, 버전별 분산 비율을 한눈에 확인할 수 있습니다.

### 6.1. 주요 메트릭 설명

| 메트릭 | 의미 |
| --- | --- |
| Response Time | 요청-응답 소요 시간 |
| Throughput | 단위 시간당 처리량 |
| Traffic Distribution | 버전별 트래픽 비율 |
| Traffic Rate | 초당 요청 수 |

### 6.2. Response Time 상세 지표

| 지표 | 의미 | 설명 |
| :--- | :--- | :--- |
| **Average** | 평균 | 시스템의 일반적인 처리 시간 |
| **Median** | 중앙값 | 사용자가 체감하는 보편적인 응답 시간 |
| **P95** | 95 백분위수 | 하위 95% 요청이 이 시간 이내에 완료됨 (성능 척도) |
| **P99** | 99 백분위수 | 하위 99% 요청이 이 시간 이내에 완료됨 (극단값 제외) |

> **P95 이해하기**: 100개의 요청 중 95번째로 느린 요청의 응답 시간이 `260ms`라면, P95는 `260ms`입니다. 즉, 95%의 사용자는 260ms 이내의 응답 속도를 경험합니다.

---

## 7. Gateway API로 동일한 라우팅 구성 (옵션)

Istio API 리소스를 제거하고 Gateway API(`HTTPRoute`)로 동일한 라우팅을 구현할 수 있습니다.

```shell
kubectl delete -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/istio-api/destination-rule.yaml
kubectl delete -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/istio-api/virtual-service.yaml

kubectl apply -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/gateway-api/http-route.yaml
kubectl apply -f https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/study/istio-study/02-request-routing/gateway-api/service.yaml

kubectl get httproutes reviews -o yaml
kubectl get service
```

![Gateway API Traffic](/assets/img/kubernetes/istio-study/04_gateway_api.webp)

위 delete는 기존 **DestinationRule/VirtualService** 리소스를 제거합니다.  
apply는 **HTTPRoute**와 `reviews-v1`, `reviews-v2` **Service**를 생성/갱신하여 동일 라우팅을 Gateway API로 구현합니다.

---

## 8. 리소스 정리

```shell
kubectl delete httproutes reviews
kubectl delete service reviews-v1 reviews-v2
kubectl delete gateways bookinfo-gateway
kubectl delete httproutes bookinfo
```

위 명령은 Gateway API 관련 **HTTPRoute/Service/Gateway** 리소스를 정리합니다.

---

## 9. Reference

- [KubeOPS - [아는 만큼 힘이 되는 트래픽 관리]](https://cafe.naver.com/kubeops/822)
- [Istio Docs - Envoy Access Logs](https://istio.io/v1.26/docs/tasks/observability/logs/access-log/#using-mesh-config)
- [k8s-1pro/kubernetes-anotherclass-sprint5](https://github.com/k8s-1pro/kubernetes-anotherclass-sprint5)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
