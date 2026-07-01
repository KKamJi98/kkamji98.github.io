---
title: gcloud CLI Command Cheat Sheet
date: 2026-06-12 17:21:06 +0900
author: kkamji
categories: [Cloud, GCP]
tags: [gcp, gcloud, cli, devops, cloud, gcloud-cli, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/gcp/gcp.webp
---

gcloud CLI를 사용하며 알게 된 CLI 명령어들을 공유합니다.

---

## 1. 기본 설정 및 초기화

```shell
gcloud init                                          # 대화형 초기 설정 (계정/프로젝트/리전)
gcloud version                                       # 설치된 gcloud 버전 확인
gcloud info                                          # SDK 경로/활성 계정/설정 종합 정보
gcloud components list                               # 설치된/사용 가능한 컴포넌트 목록
gcloud components update                             # gcloud SDK 업데이트
gcloud components install gke-gcloud-auth-plugin     # 특정 컴포넌트 설치
gcloud config set core/disable_usage_reporting true  # 사용량 리포팅 비활성화
```

---

## 2. 인증 및 계정 관리

```shell
gcloud auth login                                    # 브라우저 기반 사용자 인증
gcloud auth list                                     # 인증된 계정 목록/활성 계정 (AWS sts get-caller-identity 대응)
gcloud auth print-access-token                       # 현재 계정의 액세스 토큰 출력
gcloud config set account user@example.com           # 활성 계정 전환
gcloud auth revoke user@example.com                  # 계정 인증 해제

# Application Default Credentials (ADC) - SDK/클라이언트 라이브러리용 인증
gcloud auth application-default login                # ADC 로그인 (로컬 개발용)
gcloud auth application-default print-access-token   # ADC 액세스 토큰 출력
gcloud auth application-default revoke               # ADC 해제

# 서비스 계정 인증
gcloud auth activate-service-account --key-file=key.json  # 서비스 계정 키로 인증
gcloud auth print-identity-token                     # ID 토큰 출력 (OIDC)
```

---

## 3. 설정 및 프로젝트 관리

```shell
# 설정(config) 확인/변경
gcloud config list                                   # 현재 활성 설정 확인
gcloud config get-value project                      # 현재 프로젝트 ID 확인
gcloud config set project my-project-id              # 기본 프로젝트 지정
gcloud config set compute/region asia-northeast3     # 기본 리전 지정 (서울)
gcloud config set compute/zone asia-northeast3-a     # 기본 존 지정
gcloud config unset compute/region                   # 설정 값 제거

# 설정 프로파일(configurations) - AWS named profile 대응
gcloud config configurations list                    # 설정 프로파일 목록
gcloud config configurations create dev              # 새 프로파일 생성
gcloud config configurations activate dev            # 프로파일 전환
gcloud config configurations describe dev            # 프로파일 상세 확인
gcloud config configurations delete dev              # 프로파일 삭제
gcloud compute instances list --configuration=dev    # 특정 프로파일로 명령 실행

# 프로젝트 관리
gcloud projects list                                 # 접근 가능한 프로젝트 목록
gcloud projects describe my-project-id               # 프로젝트 상세 조회
gcloud projects create my-new-project                # 프로젝트 생성
```

---

## 4. 디버깅 및 문제 해결

```shell
gcloud info                                          # SDK 환경/설정 종합 진단
gcloud info --run-diagnostics                        # 네트워크/속성 진단 실행
gcloud config list                                   # 현재 설정 확인
gcloud auth list                                     # 활성 계정 확인
gcloud compute instances list --verbosity=debug      # 디버그 로그와 함께 실행
gcloud compute instances list --log-http             # HTTP 요청/응답 로그 출력
gcloud projects list --impersonate-service-account=SA_EMAIL  # 서비스 계정 가장하여 실행
```

---

## 5. Compute Engine 관련 명령어

```shell
# 인스턴스 관리
gcloud compute instances list                        # 모든 인스턴스 조회
gcloud compute instances describe my-vm --zone=asia-northeast3-a   # 특정 인스턴스 조회
gcloud compute instances create my-vm --zone=asia-northeast3-a --machine-type=e2-medium --image-family=debian-12 --image-project=debian-cloud
gcloud compute instances start my-vm --zone=asia-northeast3-a      # 인스턴스 시작
gcloud compute instances stop my-vm --zone=asia-northeast3-a       # 인스턴스 중지
gcloud compute instances reset my-vm --zone=asia-northeast3-a      # 인스턴스 재부팅
gcloud compute instances delete my-vm --zone=asia-northeast3-a     # 인스턴스 삭제
gcloud compute ssh my-vm --zone=asia-northeast3-a    # SSH 접속

# 이미지/머신 타입/디스크
gcloud compute images list                           # 사용 가능한 이미지 목록
gcloud compute machine-types list --zones=asia-northeast3-a  # 머신 타입 목록
gcloud compute disks list                            # 디스크 목록
```

---

## 6. Cloud Storage 관련 명령어

```shell
# 버킷 관리 (gcloud storage는 gsutil의 최신 대체 명령)
gcloud storage ls                                    # 모든 버킷 목록
gcloud storage buckets create gs://my-bucket --location=asia-northeast3  # 버킷 생성
gcloud storage buckets describe gs://my-bucket       # 버킷 정보 조회
gcloud storage rm --recursive gs://my-bucket         # 버킷과 모든 객체 삭제

# 파일 업로드/다운로드
gcloud storage cp file.txt gs://my-bucket/           # 파일 업로드
gcloud storage cp gs://my-bucket/file.txt ./         # 파일 다운로드
gcloud storage rsync ./local-folder gs://my-bucket/folder/  # 폴더 동기화
gcloud storage rsync gs://my-bucket/folder/ ./local-folder  # GCS에서 로컬로 동기화

# 객체 관리
gcloud storage ls gs://my-bucket                     # 버킷 내용 목록
gcloud storage ls --recursive gs://my-bucket         # 재귀적 목록
gcloud storage rm gs://my-bucket/file.txt            # 파일 삭제
```

---

## 7. IAM 및 서비스 계정 관련 명령어

```shell
# IAM 정책 (프로젝트 레벨)
gcloud projects get-iam-policy my-project-id         # 프로젝트 IAM 정책 조회
gcloud projects add-iam-policy-binding my-project-id --member="user:user@example.com" --role="roles/viewer"
gcloud projects remove-iam-policy-binding my-project-id --member="user:user@example.com" --role="roles/viewer"

# 역할(Role) 조회
gcloud iam roles list                                # 사전 정의 역할 목록
gcloud iam roles describe roles/viewer               # 역할 상세(권한 목록) 조회
gcloud iam roles list --project=my-project-id        # 커스텀 역할 목록

# 서비스 계정 관리
gcloud iam service-accounts list                     # 서비스 계정 목록
gcloud iam service-accounts create my-sa --display-name="My SA"  # 서비스 계정 생성
gcloud iam service-accounts describe my-sa@my-project-id.iam.gserviceaccount.com
gcloud iam service-accounts delete my-sa@my-project-id.iam.gserviceaccount.com

# 서비스 계정 키 관리
gcloud iam service-accounts keys list --iam-account=my-sa@my-project-id.iam.gserviceaccount.com
gcloud iam service-accounts keys create key.json --iam-account=my-sa@my-project-id.iam.gserviceaccount.com
```

---

## 8. VPC 네트워크 관련 명령어

```shell
# 네트워크 관리
gcloud compute networks list                         # VPC 네트워크 목록
gcloud compute networks create my-vpc --subnet-mode=custom  # 커스텀 모드 VPC 생성
gcloud compute networks delete my-vpc                # VPC 삭제

# 서브넷 관리
gcloud compute networks subnets list                 # 서브넷 목록
gcloud compute networks subnets create my-subnet --network=my-vpc --region=asia-northeast3 --range=10.0.1.0/24
gcloud compute networks subnets delete my-subnet --region=asia-northeast3

# 방화벽 규칙
gcloud compute firewall-rules list                   # 방화벽 규칙 목록
gcloud compute firewall-rules create allow-ssh --network=my-vpc --allow=tcp:22 --source-ranges=0.0.0.0/0
gcloud compute firewall-rules delete allow-ssh       # 방화벽 규칙 삭제

# 라우팅
gcloud compute routes list                           # 라우트 목록
```

---

## 9. GKE 관련 명령어

```shell
# 클러스터 관리
gcloud container clusters list                       # GKE 클러스터 목록
gcloud container clusters describe my-cluster --zone=asia-northeast3-a   # 클러스터 정보 조회
gcloud container clusters create my-cluster --zone=asia-northeast3-a --num-nodes=3
gcloud container clusters delete my-cluster --zone=asia-northeast3-a
gcloud container clusters upgrade my-cluster --zone=asia-northeast3-a     # 클러스터 버전 업그레이드

# kubeconfig 업데이트 (AWS update-kubeconfig 대응)
gcloud container clusters get-credentials my-cluster --zone=asia-northeast3-a  # kubeconfig에 자격 증명 등록

# 노드 풀 관리
gcloud container node-pools list --cluster=my-cluster --zone=asia-northeast3-a
gcloud container node-pools create my-pool --cluster=my-cluster --zone=asia-northeast3-a --num-nodes=2
gcloud container node-pools delete my-pool --cluster=my-cluster --zone=asia-northeast3-a
gcloud container clusters resize my-cluster --node-pool=my-pool --num-nodes=5 --zone=asia-northeast3-a

# 버전/Add-on 확인
gcloud container get-server-config --zone=asia-northeast3-a  # 사용 가능한 K8s/노드 버전 확인
```

---

## 10. Cloud Functions 관련 명령어

```shell
# 함수 관리
gcloud functions list                                # Cloud Functions 목록
gcloud functions describe my-function --region=asia-northeast3   # 함수 정보 조회
gcloud functions deploy my-function --gen2 --runtime=python311 --region=asia-northeast3 --trigger-http --entry-point=main --source=.
gcloud functions delete my-function --region=asia-northeast3     # 함수 삭제

# 함수 실행/로그
gcloud functions call my-function --region=asia-northeast3 --data='{"key":"value"}'  # 함수 호출
gcloud functions logs read my-function --region=asia-northeast3 --limit=50           # 함수 로그 조회
```

---

## 11. Cloud SQL 관련 명령어

```shell
# 인스턴스 관리
gcloud sql instances list                            # Cloud SQL 인스턴스 목록
gcloud sql instances describe my-db                  # 인스턴스 정보 조회
gcloud sql instances create my-db --database-version=MYSQL_8_0 --tier=db-f1-micro --region=asia-northeast3
gcloud sql instances delete my-db                    # 인스턴스 삭제
gcloud sql connect my-db --user=root                 # 인스턴스에 직접 접속

# 데이터베이스/백업 관리
gcloud sql databases list --instance=my-db           # 데이터베이스 목록
gcloud sql backups list --instance=my-db             # 백업 목록
gcloud sql backups create --instance=my-db           # 백업 생성
```

---

## 12. Cloud Logging 관련 명령어

```shell
# 로그 조회
gcloud logging logs list                             # 로그 이름 목록
gcloud logging read "resource.type=gce_instance" --limit=10     # 리소스 타입별 로그 조회
gcloud logging read "severity>=ERROR" --limit=20 --format=json  # ERROR 이상 로그 조회
gcloud logging read 'resource.type="k8s_container" AND resource.labels.cluster_name="my-cluster"' --limit=20

# 로그 싱크
gcloud logging sinks list                            # 로그 싱크 목록
```

---

## 13. 유용한 필터링 및 출력 옵션

```shell
# 출력 형식 변경
gcloud compute instances list --format=json          # JSON 출력
gcloud compute instances list --format=yaml          # YAML 출력
gcloud compute instances list --format="table(name, zone, status)"  # 테이블 형식 (컬럼 지정)
gcloud compute instances list --format="value(name)"  # 값만 출력 (스크립트용)

# 필터링 (--filter)
gcloud compute instances list --filter="status=RUNNING"          # 상태로 필터링
gcloud compute instances list --filter="zone:asia-northeast3-a"  # 존으로 필터링
gcloud compute instances list --filter="labels.env=prod"         # 라벨로 필터링

# 정렬/개수 제한
gcloud compute instances list --sort-by=~creationTimestamp       # 최신순 정렬 (~는 내림차순)
gcloud compute instances list --limit=5                          # 결과 개수 제한
```

---

## 14. References

- [Google Cloud Docs - gcloud CLI overview](https://cloud.google.com/sdk/gcloud)
- [Google Cloud Docs - gcloud CLI reference](https://cloud.google.com/sdk/gcloud/reference)
- [Google Cloud Docs - Authorize the gcloud CLI](https://cloud.google.com/sdk/docs/authorizing)
- [Google Cloud Docs - Managing gcloud CLI configurations](https://cloud.google.com/sdk/docs/configurations)
- [Google Cloud Docs - Filtering and formatting fundamentals](https://cloud.google.com/sdk/gcloud/reference/topic/filters)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
