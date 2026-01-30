---
title: Secret 안전하게 관리하기 - etcd 암호화
date: 2024-09-01 22:51:41 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, secrets, secret, etcd]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Kubernetes Secret은 Kubernetes Cluster 내에서 민감한 정보를 안전하게 저장하고 관리하기 위한 리소스 유형입니다. 하지만 Secret은 기본적으로 API 서버의 etcd에 암호화되지 않은 상태로 Base64 인코딩만으로 보호되기 때문에 클러스터 내부에서 쉽게 디코딩될 수 있다는 문제가 있습니다.

Kubernetes Secret을 안전하게 사용하기 위해서 대표적으로 다음과 같은 방법이 있습니다.

1. 저장된 Secret에 대한 암호화 활성화
2. RBAC을 사용한 Secret에 대한 접근 제어
3. 외부 비밀 관리 솔루션과 통합 (Secrets Manager, Vault)

해당 포스트에서는 저장된 Secret에 대한 암호화 활성화 방법을 다루도록 하겠습니다.

---

## 1. 문제 확인

> Secret에 대한 내용을 확인해 보겠습니다.
{: .prompt-info}

### 1.1. Secret 내용 Base64 인코딩

```bash
❯ echo -n test_secrets | base64
dGVzdF9zZWNyZXRz
```

### 1.2. Secret Manifest 파일 (test-secret.yaml)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: test-secret
type: Opaque
data:
  test_secret: dGVzdF9zZWNyZXRz
```

### 1.3. Secret 생성 및 암호 확인

```bash
❯ kubectl apply -f test-secret.yaml
secret/test-secret created
❯ ETCDCTL_API=3 etcdctl \
   --cacert=/etc/kubernetes/pki/etcd/ca.crt   \
   --cert=/etc/kubernetes/pki/etcd/server.crt \
   --key=/etc/kubernetes/pki/etcd/server.key  \
   get /registry/secrets/default/test-secret | hexdump -C
...
...
000000c0  6e 12 a7 01 7b 22 61 70  69 56 65 72 73 69 6f 6e  |n...{"apiVersion|
000000d0  22 3a 22 76 31 22 2c 22  64 61 74 61 22 3a 7b 22  |":"v1","data":{"|
000000e0  74 65 73 74 5f 73 65 63  72 65 74 22 3a 22 64 47  |test_secret":"dG|
000000f0  56 7a 64 46 39 7a 5a 57  4e 79 5a 58 52 7a 22 7d  |VzdF9zZWNyZXRz"}|
00000100  2c 22 6b 69 6e 64 22 3a  22 53 65 63 72 65 74 22  |,"kind":"Secret"|
...
...
❯ echo dGVzdF9zZWNyZXRz | base64 -d
test_secrets
```

---

## 2. Secret에 대한 암호화 활성화하기

> 앞선 예시에서 Base64 방식으로 인코딩된 Secret을 확인할 수 있었고, 디코딩을 통해 Secret의 값을 평문으로도 확인할 수 있었습니다. 이러한 보안 문제를 방지하기 위해 Secret에 대한 암호화 기능을 활성화해 보도록 하겠습니다.
{: .prompt-info}

### 2.1. 새로운 암호화 키 생성 후 Base64 인코딩

```bash
❯ head -c 32 /dev/urandom | base64
IK2pXvujA7VdAyPI3w6mFulvy6ruouE1KkGHKQUZ/fs=
```

### 2.2. 암호화 설정 파일 작성(encryption-configuration.yaml)

> 아래의 파일을 Master Node의 `/etc/kubernetes/enc/encryption-configuration.yaml` 경로에 저장합니다.
{: .prompt-info}

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: IK2pXvujA7VdAyPI3w6mFulvy6ruouE1KkGHKQUZ/fs=
      - identity: {}
```

### 2.3. 암호화 설정 적용

> 암호화 설정 파일을 kube-apiserver에 적용합니다. kube-apiserver 설정 파일이 수정되면 kubelet이 변경 사항을 감지하고 kube-apiserver를 재시작합니다.
{: .prompt-info}

kube-apiserver 설정 파일은 보통 `/etc/kubernetes/manifests/kube-apiserver.yaml` 경로에 위치합니다.

```yaml
...
spec:
  containers:
  - command:
    - kube-apiserver
    ...
    - --encryption-provider-config=/etc/kubernetes/enc/encryption-configuration.yaml  # 추가
    volumeMounts:
    ...
    - name: enc                           # 추가
      mountPath: /etc/kubernetes/enc      # 추가
      readOnly: true                      # 추가
    ...
  volumes:
  ...
  - name: enc                             # 추가
    hostPath:                             # 추가
      path: /etc/kubernetes/enc           # 추가
      type: DirectoryOrCreate             # 추가
...
```

### 2.4. 암호화 설정 적용 확인

> 5분 전에 재시작된 것을 확인할 수 있습니다. 더 자세하게 설정이 적용되었는지 확인하시려면 kubectl describe pods -n kube-system {kube-apiserver-pod-name} 해당 명령어를 통해 확인 가능합니다.
{: .prompt-info}

```bash
❯ kubectl get pods -n kube-system | grep kube-apiserver
kube-apiserver-master                      1/1     Running   0                5m2s
```

---

## 3. Secret이 제대로 암호화되는지 확인

> Secret에 대한 암호화를 설정해도 기존에 저장된 Secret은 암호화되지 않습니다. 새로운 Secret을 생성 후 기존 Secret과 비교해본 뒤, 기존에 저장된 Secret도 암호화되도록 하겠습니다.
{: .prompt-info}

### 3.1. Secret 값 Base64 인코딩

```bash
❯ echo -n test-secrets2 | base64
dGVzdC1zZWNyZXRzMg==
```

### 3.2. Secret Manifest 파일 (test-secret2.yaml)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: test-secret2
type: Opaque
data:
  test_secret2: dGVzdC1zZWNyZXRzMg==
```

### 3.3. 새로운 Secret 생성 및 암호 확인

```bash
❯ kubectl apply -f test-secret2.yaml
secret/test-secret2 created
❯ ETCDCTL_API=3 etcdctl \
   --cacert=/etc/kubernetes/pki/etcd/ca.crt   \
   --cert=/etc/kubernetes/pki/etcd/server.crt \
   --key=/etc/kubernetes/pki/etcd/server.key  \
   get /registry/secrets/default/test-secret2 | hexdump -C
00000000  2f 72 65 67 69 73 74 72  79 2f 73 65 63 72 65 74  |/registry/secret|
00000010  73 2f 64 65 66 61 75 6c  74 2f 74 65 73 74 2d 73  |s/default/test-s|
00000020  65 63 72 65 74 32 0a 6b  38 73 3a 65 6e 63 3a 61  |ecret2.k8s:enc:a|
00000030  65 73 63 62 63 3a 76 31  3a 6b 65 79 31 3a 83 98  |escbc:v1:key1:..|
00000040  0b 64 91 5e 91 89 43 e6  d6 98 65 85 2b 54 a1 2e  |.d.^..C...e.+T..|
00000050  7d f9 d7 09 a8 4d 5e da  eb 25 bd 12 fc 58 b1 d4  |}....M^..%...X..|
...
000000c0  b5 0f 6d 55 e4 73 df b9  3d f0 71 6a 70 6f 11 4e  |..mU.s..=.qjpo.N|
000000d0  77 46 09 da c4 75 e5 db  0a 7a 1d 73 99 68 4c e2  |wF...u...z.s.hL.|
000000e0  f0 ff 4f cd 24 1c 5f a3  3f 9c 3b a9 ba d0 63 56  |..O.$._.?.;...cV|
000000f0  cd 15 4c 5d fc ca 47 63  6d c7 4a 5b 2a 17 3b 28  |..L]..Gcm.J[*.;(|
00000100  79 bf 14 93 8b 3a ce 57  61 37 f4 f0 dd 12 f7 6d  |y....:.Wa7.....m|
00000110  cb bb 45 49 ed 21 51 80  81 20 24 ae a4 fb 13 a9  |..EI.!Q.. $.....|
...
```

### 3.4. 기존 Secret 확인

```bash
❯ ETCDCTL_API=3 etcdctl \
   --cacert=/etc/kubernetes/pki/etcd/ca.crt   \
   --cert=/etc/kubernetes/pki/etcd/server.crt \
   --key=/etc/kubernetes/pki/etcd/server.key  \
   get /registry/secrets/default/test-secret | hexdump -C
...
...
000000c0  6e 12 a7 01 7b 22 61 70  69 56 65 72 73 69 6f 6e  |n...{"apiVersion|
000000d0  22 3a 22 76 31 22 2c 22  64 61 74 61 22 3a 7b 22  |":"v1","data":{"|
000000e0  74 65 73 74 5f 73 65 63  72 65 74 22 3a 22 64 47  |test_secret":"dG|
000000f0  56 7a 64 46 39 7a 5a 57  4e 79 5a 58 52 7a 22 7d  |VzdF9zZWNyZXRz"}|
00000100  2c 22 6b 69 6e 64 22 3a  22 53 65 63 72 65 74 22  |,"kind":"Secret"|
...
...
```

### 3.5. 기존 Secret 암호화 후 다시 확인

```bash
❯ kubectl get secrets --all-namespaces -o json | kubectl replace -f -
...
secret/test-secret replaced
secret/test-secret2 replaced
...

❯ ETCDCTL_API=3 etcdctl \
   --cacert=/etc/kubernetes/pki/etcd/ca.crt   \
   --cert=/etc/kubernetes/pki/etcd/server.crt \
   --key=/etc/kubernetes/pki/etcd/server.key  \
   get /registry/secrets/default/test-secret | hexdump -C
00000000  2f 72 65 67 69 73 74 72  79 2f 73 65 63 72 65 74  |/registry/secret|
00000010  73 2f 64 65 66 61 75 6c  74 2f 74 65 73 74 2d 73  |s/default/test-s|
00000020  65 63 72 65 74 0a 6b 38  73 3a 65 6e 63 3a 61 65  |ecret.k8s:enc:ae|
00000030  73 63 62 63 3a 76 31 3a  6b 65 79 31 3a fb 3c ec  |scbc:v1:key1:.<.|
00000040  5c c3 a6 e3 e8 d5 9b d0  e7 d2 01 96 32 0e 42 f2  |\...........2.B.|
00000050  f2 7b 66 c3 72 65 cc d6  9d 53 b2 07 e2 a7 d5 dc  |.{f.re...S......|
...
00000190  5b 39 7c a3 87 02 b1 ca  aa ef ad 28 c7 6b 91 f5  |[9|........(.k..|
000001a0  13 35 13 81 0d b5 62 44  af 09 68 29 a4 7b 76 e6  |.5....bD..h).{v.|
000001b0  6f 7d 0f 02 a7 f5 17 55  29 67 09 6e 4a 71 05 73  |o}.....U)g.nJq.s|
000001c0  96 68 8c 0a 0f 53 b5 c2  8b 74 da 1e 6f b4 a0 60  |.h...S...t..o..`|
000001d0  53 2f 0e 05 82 91 0d 2d  2c 89 1a 6f 54 c8 f3 a0  |S/.....-,..oT...|
000001e0  2d 10 19 08 2d 1d ab 13  48 bd f3 ce 2f 4f cf 76  |-...-...H.../O.v|
...
...
```

> 기존의 Secret도 모두 암호화된 것을 확인할 수 있습니다.
{: .prompt-tip}

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
