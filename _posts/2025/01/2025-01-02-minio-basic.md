---
title: Minio 개념 및 실습 (1) - Object Storage
date: 2025-01-02 01:12:09 +0900
author: kkamji
categories: [DevOps, Storage]
tags: [minio, object-storage, s3, pv, pvc, kubernetes, storage]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/storage/minio/minio.webp
---

최근 SSD를 사용하게 되면서 기본 HDD의 용량을 어떻게 사용할 수 있을까? 라는 고민을 하던 중 **Minio**를 접하게 되었습니다.

**Minio**는 단순히 오브젝트 스토리지(Object Storage)로 운영하는 방법뿐만 아니라, **Kubernetes의 PV(퍼시스턴트 볼륨, PersistentVolume)**로도 활용 가능합니다.

포스트를 2개로 나눠 이번 포스트에서는 **Minio**가 무엇인지 알아보고, 설치 과정과 함께 **Object Storage**로 사용하는 방법에 대해 알아 보고 다음 포스트에서는 **Kubernetes PV**로 사용할 수 있는 방법에 대해 다루도록 하겠습니다.

---

## 1. Minio란?

> Minio는 고성능·고가용성을 갖춘 오브젝트 스토리지(Object Storage) 솔루션입니다.  
{: .prompt-tip}

- AWS S3와 호환되는 API 인터페이스를 제공하기 때문에, AWS SDK, s3cmd 등과 함께 사용할 수 있습니다.
- 경량화된 설계와 간단한 설정으로 개발/테스트 환경부터 프로덕션까지 폭넓게 쓰이고 있습니다.
- 단일 노드 형태로도 구성이 가능하고, 클러스터링(Distributed Minio) 방식으로 노드 여러 대를 묶어 내결함성(HA)을 높일 수도 있습니다.

Kubernetes 환경에서는 Minio를 다음과 같이 활용할 수 있습니다.

- 일반 Object Storage로 사용
- 애플리케이션이 S3 호환 API를 통해 Minio 버킷(Bucket)에 파일을 업로드/다운로드
- Kubernetes PV(퍼시스턴트 볼륨)로 사용
- Minio 파일 시스템을 PVC로 매핑하여, Pod가 마치 로컬 스토리지처럼 사용 (CSI Driver 필요)

---

## 2. Minio 설치 및 실행(Windows)

> `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` 환경변수를 사용한 root계정의 USERNAME과, PASSWORD를 지정할 수 있습니다.  
{: .prompt-tip}

```powershell
## Minio 설치 파일 다운로드
curl -O https://dl.min.io/server/minio/release/windows-amd64/minio.exe


## Minio 실행

### root 사용자 이름, 비밀번호 지정
PS E:\> $env:MINIO_ROOT_USER="새로운사용자"
PS E:\> $env:MINIO_ROOT_PASSWORD="새로운비밀번호"

PS E:\> .\minio.exe server E:\minio --console-address :9001
INFO: Formatting 1st pool, 1 set(s), 1 drives per set.
INFO: WARNING: Host local has more than 0 drives of set. A host failure will result in data becoming unavailable.
MinIO Object Storage Server
Copyright: 2015-2025 MinIO, Inc.
License: GNU AGPLv3 - https://www.gnu.org/licenses/agpl-3.0.html
Version: RELEASE.2024-12-18T13-15-44Z (go1.23.4 windows/amd64)

API: http://192.168.0.2:9000  http://10.0.0.1:9000  http://172.26.112.1:9000  http://172.28.0.1:9000  http://127.0.0.1:9000
   RootUser: minioadmin
   RootPass: minioadmin

WebUI: http://192.168.0.2:9001 http://10.0.0.1:9001 http://172.26.112.1:9001 http://172.28.0.1:9001 http://127.0.0.1:9001
   RootUser: minioadmin
   RootPass: minioadmin

CLI: https://min.io/docs/minio/linux/reference/minio-mc.html#quickstart
   $ mc alias set 'myminio' 'http://192.168.0.2:9000' 'minioadmin' 'minioadmin'

Docs: https://docs.min.io
WARN: Detected default credentials 'minioadmin:minioadmin', we recommend that you change these values with 'MINIO_ROOT_USER' and 'MINIO_ROOT_PASSWORD' environment variables
```

---

## 3. 접속 확인

> 위 콘솔 출력과 같이 localhost의 9001번 포트로 접속이 가능합니다. 초기 username:password => minioadmin:minioadmin  
> `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` 환경변수를 사용한 root계정의 USERNAME과, PASSWORD를 지정할 수 있습니다.  
{: .prompt-tip}

![minio login](/assets/img/storage/minio/minio-login.webp)

---

## 4. Minio Client 설치 및 Minio 연결 (Linux)

> 필요한 Minio CLI 명령어는 <https://min.io/docs/minio/linux/reference/minio-mc.html#command-quick-reference> 사이트에서 확인이 가능합니다.  
{: .prompt-tip}

```shell
curl https://dl.min.io/client/mc/release/linux-amd64/mc \
  --create-dirs \
  -o $HOME/minio-binaries/mc

chmod +x $HOME/minio-binaries/mc
export PATH=$PATH:$HOME/minio-binaries/

mc alias set {alias_name} http://192.168.0.2:9000 {username} {password}

❯ mc admin info {alias_name}
●  192.168.0.2:9000
   Uptime: 6 minutes
   Version: 2024-12-18T13:15:44Z
   Network: 1/1 OK
   Drives: 1/1 OK
   Pool: 1

┌──────┬───────────────────────┬─────────────────────┬──────────────┐
│ Pool │ Drives Usage          │ Erasure stripe size │ Erasure sets │
│ 1st  │ 0.0% (total: 932 GiB) │ 1                   │ 1            │
└──────┴───────────────────────┴─────────────────────┴──────────────┘

1 drive online, 0 drives offline, EC:0
```

---

## 5. 파일 업로드 테스트

> 간단하게 .txt 파일 생성 후 Minio에 업로드 후 해당 파일을 다운로드해 테스트하도록 하겠습니다.  
{: .prompt-tip}

```shell
## Bucket 생성
❯ mc mb kkamji-minio/test
Bucket created successfully `kkamji-minio/test`.

## 테스트 파일 생성 및 업로드
❯ echo "kkamji minio bucket file upload test" > file_upload_test_minio.txt
❯ mc cp file_upload_test_minio.txt kkamji-minio/test
...kamji/file_upload_test_minio.txt: 37 B / 37 B ┃▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓┃ 969 B/s 0s

## 기존 파일 삭제 후 확인
❯ rm file_upload_test_minio.txt
❯ cat file_upload_test_minio.txt
cat: file_upload_test_minio.txt: No such file or directory ## 파일이 잘 삭제됨

## 파일 다운로드 후 확인
❯ mc cp kkamji-minio/test/file_upload_test_minio.txt .
.../test/file_upload_test_minio.txt: 37 B / 37 B ┃▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓┃ 4.61 KiB/s 0s

❯ cat file_upload_test_minio.txt 
kkamji minio bucket file upload test
```

![minio-test-file](/assets/img/storage/minio/minio-test-file.webp)

---

## 6. 마무리

이로써 AWS S3와 비슷한 Object Storage 공간으로 남은 HDD를 사용할 수 있게 되었습니다. nssm과 let's encrypt를 사용해 자동 시작과 TLS 인증도 적용이 가능합니다!

---

## 7. Reference

- Minio 공식 문서 - <https://min.io/docs/minio/windows/index.html>
- Minio GitHub - <https://github.com/minio/minio>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
