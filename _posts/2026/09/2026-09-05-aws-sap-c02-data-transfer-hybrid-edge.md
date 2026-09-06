---
title: "AWS SAP-C02 박살내기 - 데이터 전송과 하이브리드 엣지: Snow Family, DataSync, Storage Gateway, Outposts"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, snowball, datasync, transfer-family, storage-gateway, outposts, local-zones, wavelength]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-05 10:00:00 +0900
---

온프레미스 NAS에 쌓인 600 TB를 S3로 옮기는 계획서를 받았다고 해보겠습니다. 인터넷 회선은 1 Gbps이고, 업무 시간 트래픽 때문에 마이그레이션에 실제로 할당할 수 있는 몫은 40%입니다. 기한은 8주입니다. 계획서에는 "1 Gbps면 하루 약 10 TB이므로 60일이면 끝난다"라고 적혀 있고, 여유가 없으니 Snowball Edge를 몇 대 주문해 병행하자는 대안도 함께 있습니다.

두 문장이 모두 성립하지 않습니다. AWS가 제시하는 전송 시간 공식에 40% 사용률을 넣으면 이론 최소값만 138일이 나옵니다. 그리고 Snow Family 디바이스는 신규 고객이 주문할 수 없습니다. 계획서의 두 축이 동시에 무너지면 남는 질문은 하나입니다. 회선을 늘릴 것인가, 물리 전송으로 갈 것인가, 아니면 애초에 전부 옮기지 않고 하이브리드로 남길 것인가입니다.

SAP-C02 Domain 4는 이 지점을 묻습니다. 서비스 이름을 아는 것으로는 선지가 좁혀지지 않고, 전송량과 허용 기간과 회선 대역폭이라는 세 숫자를 넣어 계산한 결과가 답을 가릅니다. 여기에 DataSync가 에이전트를 요구하는 조합, Storage Gateway 네 종류가 각각 제공하는 인터페이스, Outposts rack과 server가 지원하는 서비스 차이 같은 제약이 얹힙니다.

> **TL;DR**  
> - 전송 시간은 `(DATA_SIZE * 8) / (CIRCUIT * NETWORK_UTILIZATION * 3600 * AVAILABLE_HOURS)`로 계산하고 결과는 이론 최소값이다. cutover가 전체의 최대 30%를 먹을 수 있다.  
> - Snow Family 디바이스는 신규 고객이 주문할 수 없다. 온라인은 DataSync, 물리 전송은 Data Transfer Terminal 또는 파트너 솔루션이다.  
> - Data Transfer Terminal은 현재 Enterprise Support 고객에게만 제공된다.  
> - DataSync 태스크당 처리량 상한은 에이전트를 쓰면 10 Gbps, 쓰지 않으면 5 Gbps이고 둘 다 조정 불가다.  
> - Enhanced mode는 FSx for Windows File Server, ONTAP, OpenZFS를 지원하지 않는다. task mode는 만든 뒤에 바꿀 수 없다.  
> - DataSync VPC service endpoint는 default tenancy VPC만 지원하고 shared VPC를 지원하지 않는다.  
> - Transfer Acceleration은 버킷 이름에 마침표가 있으면 쓸 수 없고 15개 리전에서만 지원된다.  
> - internet-facing VPC hosted endpoint에서는 SFTP와 FTPS만 쓸 수 있다. FTP는 VPC 내부 접근에서만 된다.  
> - 16 TiB를 넘는 cached volume의 스냅샷은 EBS 볼륨으로 복원할 수 없다.  
> - `RefreshCache`는 인벤토리만 갱신하고 파일 데이터를 캐시에 채우지 않는다.  
> - Outposts server는 EBS, S3 on Outposts, EKS 노드, RDS를 지원하지 않고 신규 판매가 중단됐다.  
> - S3 on Outposts는 스토리지 클래스가 `OUTPOSTS` 하나이고 SSE-KMS와 lifecycle transition을 지원하지 않는다.  
> - carrier gateway는 통신사 네트워크에서 오는 inbound와 인터넷으로 나가는 outbound를 제공하지만 일반 인터넷에서 Wavelength Zone으로 직접 들어오는 연결은 설정할 수 없다. 일부 Wavelength Zone 파트너의 fixed wireless access는 별도 조건으로 제공된다.  
{: .prompt-info}

---

## 1. 전송 시간은 회선 속도가 아니라 네 개의 입력값으로 정해진다

AWS는 대규모 마이그레이션 타임라인을 다음 공식으로 계산하라고 문서에 명시합니다.

```text
(DATA_SIZE * 8 bits per byte) / (CIRCUIT * NETWORK_UTILIZATION * 3600 seconds per hour * AVAILABLE_HOURS) = Number of days
```

`DATA_SIZE`는 bytes, `CIRCUIT`은 bits per second, `AVAILABLE_HOURS`는 하루에 전송에 쓸 수 있는 시간입니다. 회선 속도 하나만 있는 것이 아니라 네 개의 입력값이 있고, 그중 세 개는 회선 사양이 아니라 운영 조건입니다.

![전송량과 회선과 하루 가용 시간을 입력으로 이론 최소 전송 일수를 계산하고 그 값이 허용 기간을 넘는지에 따라 온라인 전송과 회선 증설과 물리 전송으로 갈리는 판단 경로](/assets/img/sap-c02/data-transfer-online-vs-physical.webp)

그림은 왼쪽 열의 세 입력값이 계산 상자로 모이고, 그 결과가 허용 기간과 비교되어 두 갈래로 나뉘는 구조를 보여줍니다. 계산 상자에서 따로 뻗은 점선 하나는 cutover 보정 항목입니다. 오른쪽 끝에는 온라인 전송, 기간 한정 hosted connection, 물리 전송이라는 세 가지 도착점이 놓여 있습니다.

공식 문서가 드는 예시로 감을 잡을 수 있습니다. 100 TB를 1 Gbps 인터넷 회선으로 옮기면서 네트워크 사용률 80%, 하루 24시간 가용을 가정하면 다음과 같습니다.

```text
(100,000,000,000,000 * 8) / (1,000,000,000 * 0.80 * 3600 * 24) = 11.57 days
```

문서는 이 값을 **theoretical minimum transfer time**이라고 부르고, 네트워크 변동과 스토리지 성능 변동과 wave 사이 다운타임으로 보정하라고 명시합니다. 시험 문항에서 이 값을 그대로 계획에 넣은 선지는 대개 오답 쪽입니다.

도입부의 600 TB 사례를 같은 공식에 넣어보겠습니다. 사용률 40%, 하루 24시간이면 다음과 같습니다.

```text
(600,000,000,000,000 * 8) / (1,000,000,000 * 0.40 * 3600 * 24) = 138.9 days
```

8주는 56일입니다. 이론 최소값이 기한의 두 배를 넘으므로 현재 회선으로는 성립하지 않고, 보정까지 넣으면 격차가 더 벌어집니다.

두 가지를 더 기억해야 합니다. 첫째, **cutover 활동이 전체 마이그레이션 시간의 최대 30%를 차지하는 경우가 드물지 않다**고 문서가 명시합니다. 전송 시간만 계산하고 기한을 맞췄다고 보고하면 실제로는 넘깁니다. 둘째, POC에서 측정한 처리량이 가용 대역폭보다 낮으면(문서 예시는 10 Gbps 회선에서 300 MiB/s) **데이터셋을 여러 task로 파티셔닝해 대역폭을 채우라**고 권고합니다. 회선이 남는데 태스크가 하나뿐이면 그 태스크의 처리량 상한이 병목입니다.

---

## 2. 회선을 늘리는 경로는 기간 한정 hosted connection이다

계산 결과가 기한을 넘으면 회선을 늘리는 선택지가 있습니다. AWS는 Snowball Edge 대안을 안내하면서 **네트워크 대역폭 한계를 넘어야 하면 데이터 전송 프로젝트 기간 동안만 Direct Connect Delivery Partner에게서 hosted connection을 조달해 DataSync와 함께 쓰라**고 지목합니다. 상시 회선 계약이 아니라 프로젝트 기간에 한정한 조달이라는 점이 판단의 핵심입니다.

hosted connection의 포트 속도 선택지는 50 Mbps, 100 Mbps, 200 Mbps, 300 Mbps, 400 Mbps, 500 Mbps, 1 Gbps, 2 Gbps, 5 Gbps, 10 Gbps, 25 Gbps입니다. 여기에 조달 경로 제약이 세 개 붙습니다.

| 제약 | 내용 |
| :--- | :--- |
| 요청 주체 | Direct Connect 콘솔에서 직접 요청할 수 없다. Partner가 생성하고 사용자가 accept한다 |
| 속도 변경 | 포트 속도 변경도 Partner만 할 수 있다 |
| 1 Gbps 이상 | 특정 요건을 충족한 Direct Connect Partner만 만들 수 있다 |
| 25 Gbps | 100 Gbps 포트가 있는 Direct Connect location에서만 제공된다 |

hosted connection에는 **traffic policing**이 적용됩니다. 설정된 최대 속도에 도달하면 초과 트래픽을 drop하므로, bursty한 트래픽은 non-bursty 트래픽보다 실효 처리량이 낮아질 수 있습니다. 앞 절 공식에서 `NETWORK_UTILIZATION`을 100%로 잡으면 안 되는 이유가 여기에도 있습니다.

Direct Connect 자체의 구성과 VIF 종류는 [하이브리드 네트워크 편](/posts/aws-sap-c02-hybrid-networking/)이 다룹니다. 여기서는 회선을 전송 시간 계산의 `CIRCUIT` 입력값과 조달 리드타임이 붙는 항목으로만 봅니다.

---

## 3. Snow Family가 빠진 자리에 남은 선택지

물리 전송 선택지를 고를 때 가장 먼저 확인할 것은 현재 제공 상태입니다. 강의 자료와 오래된 정리 글이 전제하는 Snow Family 라인업은 지금 대부분 없습니다.

| 시점 | 변경 |
| :--- | :--- |
| 2024-11-12 | Snowcone 단종. Snowball Edge Storage Optimized 80 TB, Compute Optimized with 52 vCPUs, Compute Optimized with GPU 단종 |
| 2025-11-12 | 위 단종 모델의 기존 고객 지원 종료 |
| 2025-11-07 | 남은 Snowball Edge 디바이스가 기존 고객에게만 제공. 신규 고객 주문 불가 |

결과적으로 **신규 고객은 어떤 Snow Family 디바이스도 주문할 수 없습니다.** 기존 사용 고객은 계속 쓸 수 있습니다. 문항 지문에 "최근 AWS 계정을 개설했다"나 "이 회사의 첫 AWS 프로젝트다" 같은 문장이 있으면 Snow 선지는 그 문장 하나로 탈락합니다.

현재 문서에 남아 있는 Snowball Edge 구성은 두 가지입니다.

| 구성 | 저장 | CPU | 메모리 | 동작 온도 |
| :--- | :--- | :--- | :--- | :--- |
| Storage Optimized 210 TB | 210 TB usable NVMe | AMD Rome 64 cores 2 GHz, 104 vCPU | 416 GB 사용 가능 | 0-30 C |
| Compute Optimized | 28 TB dedicated NVMe SSD | AMD EPYC Gen2, 104 vCPU | 512 GB 탑재, 최대 416 GB 사용 가능 | 0-45 C |

디바이스 네트워크 인터페이스는 2x 10 Gbit RJ45(한 개만 사용 가능), 1x 25 Gbit SFP28, 1x 100 Gbit QSFP28이며 **한 번에 하나의 인터페이스만 사용할 수 있습니다.** 여러 포트를 묶어 대역폭을 늘리는 구성은 성립하지 않습니다. RJ45의 1G 동작은 대규모 전송에 권장되지 않고, 10G 동작은 Cat6A UTP 기준 최대 55 m입니다. 물리 사양으로는 무게 22.54 kg(49.7 lb), 평균 소비전력 304 W, 전원 정격 1200 W입니다.

AWS가 제시한 대체 경로는 세 갈래입니다.

| 용도 | 대체 |
| :--- | :--- |
| 온라인 전송 | AWS DataSync |
| 물리 전송 | AWS Data Transfer Terminal 또는 AWS Partner 솔루션 |
| 엣지 컴퓨팅 | AWS Outposts |

**AWS Data Transfer Terminal**은 디바이스가 고객에게 배송되는 방식이 아닙니다. 사용자가 자기 저장 장치를 들고 AWS 시설로 가서 업로드하는 물리 시설입니다. 콘솔에서 예약을 만들고, 예약한 시간에 도착해 자기 장비로 업로드하며, 예약이 끝나면 시설이 재보안됩니다. 두 가지 제약이 문항 재료가 됩니다. **현재 Enterprise Support 고객에게만 제공되고**, 시설 위치는 콘솔에서 예약을 만든 뒤에야 공개됩니다.

Snowmobile은 현재 `docs.aws.amazon.com`에 사용자 가이드가 없고 Snowball FAQ 본문에도 등장하지 않습니다. 널리 인용되는 100 PB라는 수치는 2016년 발표 블로그가 출처이므로 현행 사실로 다루지 않습니다.

---

## 4. DataSync 에이전트가 필요한 조합 네 가지

DataSync에서 가장 자주 틀리는 지점은 에이전트 필요 여부입니다. "온프레미스가 끼면 필요하다"나 "대상이 EFS면 필요하다" 같은 요약은 둘 다 틀립니다. 문서는 필요한 조합을 네 가지로 열거합니다.

![에이전트가 필요한 조합 네 가지와 필요 없는 조합 세 가지가 각각 에이전트 경유와 서비스 직접 전송으로 나뉘고 태스크당 10 Gbps 와 5 Gbps 상한으로 이어지는 구조](/assets/img/sap-c02/datasync-agent-requirement.webp)

그림은 조합 목록을 두 묶음으로 나누고 각 묶음이 도달하는 처리량 상한을 함께 보여줍니다. 두 묶음의 상한 값이 서로 다르다는 점이 이 그림의 요지입니다.

**에이전트가 필요한 조합**

| 조합 | 비고 |
| :--- | :--- |
| AWS 스토리지와 온프레미스 스토리지 사이 | NFS, SMB, HDFS, 자체관리 객체 스토리지 |
| EFS 또는 FSx와 타 클라우드 스토리지 사이 | 대상이 파일 시스템인 경우 |
| 계정 간 전송에서 소스와 대상이 모두 S3가 아닌 경우 | 한쪽이라도 S3면 해당하지 않는다 |
| 상용 리전과 GovCloud(US) 사이에서 양쪽 모두 EFS 또는 FSx인 경우 | 한쪽이 S3면 해당하지 않는다 |

**에이전트가 필요 없는 조합**

| 조합 | 비고 |
| :--- | :--- |
| 같은 계정의 AWS 스토리지 서비스 사이 | S3, EFS, FSx 조합 전부 |
| 계정 간이라도 한쪽이 S3인 경우 | S3가 한쪽에 있으면 직접 전송한다 |
| S3와 타 클라우드 객체 스토리지 사이 | Azure Blob을 포함한다 |
| 상용 리전과 GovCloud(US) 사이에서 한쪽이 S3인 경우 | 위와 같은 규칙이다 |

여기에 별도로 걸리는 조합이 하나 있습니다. **S3 on Outposts와 리전 S3 사이 전송은 에이전트가 필요하고 Basic mode만 지원합니다.**

에이전트 필요 여부가 처리량 상한까지 바꿉니다. **태스크당 최대 처리량은 에이전트를 쓰는 전송이 10 Gbps, 쓰지 않는 전송이 5 Gbps이고 둘 다 조정 불가입니다.** "에이전트를 없앴으니 더 빨라진다"는 방향이 아니라는 점이 중요합니다.

에이전트를 배포한다면 요건은 다음과 같습니다.

| 항목 | Basic mode | Enhanced mode |
| :--- | :--- | :--- |
| vCPU | 4 | 8 |
| 디스크 | 80 GB | 80 GB |
| RAM | 32 GB(2천만 개 이하), 64 GB(2천만 개 초과) | 32 GB, 파일 수 쿼터 없음 |
| 권장 EC2 인스턴스 | m5.2xlarge(2천만 개 이하), m5.4xlarge(2천만 개 초과) | m6a.2xlarge |

EC2 에이전트 인스턴스는 최소 2xlarge입니다. 지원 하이퍼바이저는 VMware ESXi 7.0과 8.0, KVM, Microsoft Hyper-V 2012 R2와 2016과 2019, 그리고 Amazon EC2입니다. **EC2 인스턴스 위에서 KVM을 돌려 그 안에 에이전트를 배포하는 구성은 지원되지 않습니다.**

---

## 5. task mode는 위치가 정하고 만든 뒤에는 바꿀 수 없다

Enhanced mode를 고르면 객체 수 제한이 사실상 사라지므로 대규모 전송에서 먼저 떠올리게 됩니다. 그런데 mode를 고를 수 있는지는 전송 위치가 결정합니다.

Enhanced mode가 지원하는 위치는 S3, EFS, FSx for Lustre, NFS, SMB, HDFS, Azure Blob, object storage입니다. 여기 없는 것이 답을 가릅니다. **FSx for Windows File Server, FSx for NetApp ONTAP, FSx for OpenZFS는 Enhanced mode를 지원하지 않아 Basic mode를 써야 합니다.** S3 on Outposts도 Basic mode 전용입니다.

| 항목 | Basic mode | Enhanced mode |
| :--- | :--- | :--- |
| 처리 방식 | 나열, 준비, 전송, 검증을 순차로 한다 | 네 단계를 병렬로 한다 |
| 로그 | 비구조화 | 구조화된 JSON |
| 검증 기본값 | 전체 데이터 검증 | 전송한 데이터만 검증 |
| task execution당 객체 수 | 온프레미스와 AWS 사이 5천만 개, AWS 스토리지 사이 2천5백만 개(둘 다 조정 가능) | 사실상 무제한 |
| 추가 권한 | 없음 | DataSync IAM role에 `iam:CreateServiceLinkedRole` 필요 |

**task mode는 task를 만든 뒤에 변경할 수 없습니다.** 이미 만든 Basic mode task를 Enhanced mode로 전환해 처리량이나 객체 수 한계를 푸는 선지는 성립하지 않고, 새 task를 만들어야 합니다.

객체 수 쿼터를 셀 때 함정이 하나 있습니다. S3 객체를 prefix와 함께 전송하면 **prefix가 디렉터리로 계산돼 쿼터에 포함**됩니다. 문서 예시로 `s3://bucket/foo/bar.txt`는 디렉터리 2개(`./`, `./foo/`)와 객체 1개로 셉니다. prefix가 깊은 데이터셋은 실제 객체 수보다 큰 값이 쿼터에 걸립니다.

DataSync의 나머지 쿼터도 함께 정리하면 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 계정과 리전당 task | 100개(조정 가능) |
| 태스크당 큐잉 가능한 실행 | 50개 |
| Enhanced mode 동시 실행 | 120개 |
| task execution 이력 보존 | 30일 |
| Enhanced mode manifest 파일 | 최대 20 GB |
| task filter 문자 수 | 102,400자 |
| 파일 경로 전체 길이 | 4,096 bytes |
| 경로 구성요소 | 255 bytes |
| Windows 도메인 이름 | 253자 |
| 서버 hostname | 255자 |
| S3 객체 이름 | 1,024 UTF-8 문자 |

---

## 6. 리전 경계와 다중 에이전트가 하지 않는 일

리전 간 전송에서 두 위치 중 하나는 DataSync를 실행하는 리전에 있어야 합니다. 그리고 **NFS, SMB, HDFS, object storage 위치는 리전 간 전송이 아예 불가능하고, 두 위치 모두 에이전트를 활성화한 리전에 있어야 합니다.** 온프레미스 NFS를 다른 리전의 S3로 한 번에 옮기는 구성은 이 제약에 걸립니다.

에이전트 다중 부착도 오해가 잦습니다. 위치 하나에 Basic mode 에이전트 최대 4개, Enhanced mode 에이전트 최대 4개를 붙일 수 있습니다. 여기서 중요한 것은 목적입니다. **다중 에이전트는 고가용성 구성이 아닙니다.** 붙어 있는 에이전트가 전부 online이어야 task를 시작할 수 있고, 하나라도 offline이면 실행되지 않습니다. 에이전트를 늘리는 것은 처리량을 위한 선택이고, 늘릴수록 장애 지점이 늘어납니다.

---

## 7. 서비스 엔드포인트 네 종류와 PrivateLink 경로의 계정 제약

DataSync 에이전트를 활성화할 때 서비스 엔드포인트 타입을 고릅니다. public, FIPS, VPC(PrivateLink), FIPS VPC 네 종류입니다. **에이전트 하나는 엔드포인트 타입 하나만 사용할 수 있습니다.** 타입을 섞으려면 타입마다 에이전트를 따로 만들어야 하고, "평소에는 VPC 엔드포인트를 쓰다가 장애 시 public으로 넘어가게 한다" 같은 폴백 구성은 만들 수 없습니다.

규제 요건 때문에 인터넷을 경유하지 않아야 하는 문항에서는 VPC service endpoint를 고르게 되는데, 여기에 제약 세 개가 붙습니다.

| 제약 | 내용 |
| :--- | :--- |
| tenancy | VPC가 default tenancy여야 한다 |
| shared VPC | 지원되지 않는다 |
| 계정 | 엔드포인트, VPC, 에이전트가 모두 같은 AWS 계정에 있어야 한다 |

네트워크 팀이 "공용 shared VPC에 엔드포인트를 하나 두고 여러 계정이 함께 쓰자"고 제안하는 형태가 문항 지문에 자주 등장하는데, DataSync에서는 성립하지 않습니다.

한 가지 설정 권고도 기억할 값입니다. VPC service endpoint를 만들 때 AWS는 **Private DNS Name을 끄는 것을 권장합니다.** 켜두면 같은 VPC 안의 다른 에이전트가 public service endpoint에 도달하지 못하는 부작용이 생깁니다.

---

## 8. 태스크 처리량 상한과 사용자 대역폭 제한은 다른 축이다

DataSync에서 대역폭 관련 값이 두 개 나오는데 성격이 다릅니다.

| 축 | 값 | 통제 주체 | 조정 |
| :--- | :--- | :--- | :--- |
| 태스크당 처리량 상한 | 에이전트 10 Gbps, 무에이전트 5 Gbps | 서비스 | 불가 |
| 사용자 대역폭 제한 | 사용자가 지정 | 사용자 | 실행 중에도 가능 |

사용자 대역폭 제한의 콘솔 단위는 MiB/s이고 API 파라미터는 `BytesPerSecond`입니다. 기본값은 `Use available`이라서 지정하지 않으면 가용 대역폭을 전부 사용합니다. 파라미터를 받는 오퍼레이션은 `CreateTask`, `UpdateTask`, `StartTaskExecution`, 그리고 실행 중 변경용 `UpdateTaskExecution`입니다.

**실행 중이거나 큐에 있는 task execution의 대역폭 제한을 바꾸면 60초 안에 반영됩니다.** "업무 시간에 WAN을 잠식하지 않게 하라"는 요구가 나오면 task를 멈추고 새로 만드는 것이 아니라 `UpdateTaskExecution`으로 제한을 거는 것이 답입니다. 반대로 이 제한으로 상한을 올릴 수는 없습니다. 제한은 낮추는 방향으로만 작동합니다.

---

## 9. Transfer Acceleration이 켜지지 않는 버킷과 켜도 소용없는 경로

S3 Transfer Acceleration은 엣지 로케이션을 경유해 장거리 구간의 전송 효율을 올리는 버킷 기능입니다. 세 가지 전제를 만족해야 켜집니다.

| 전제 | 내용 |
| :--- | :--- |
| 버킷 이름 | **마침표(`.`)가 있으면 사용할 수 없다.** DNS 호환이어야 한다 |
| 요청 스타일 | virtual-hosted style 요청만 지원한다 |
| 리전 | 모든 리전에서 지원되지 않는다 |

버킷 이름 제약이 특히 자주 나옵니다. `media.example.com` 같은 이름을 그대로 두고 Transfer Acceleration을 켜는 선지는 이 한 줄로 탈락하고, 실제로 필요한 조치는 마침표가 없는 새 버킷을 만드는 것입니다.

문서가 나열한 지원 리전은 15개입니다. ap-northeast-1, ap-northeast-2, ap-south-1, ap-southeast-1, ap-southeast-2, ca-central-1, eu-central-1, eu-west-1, eu-west-2, eu-west-3, sa-east-1, us-east-1, us-east-2, us-west-1, us-west-2입니다.

나머지 동작 값은 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 엔드포인트 | `bucket-name.s3-accelerate.amazonaws.com` |
| IPv6 엔드포인트 | `bucket-name.s3-accelerate.dualstack.amazonaws.com` |
| 상태 값 | `Enabled`, `Suspended` |
| 권한 | `s3:PutAccelerateConfiguration`, `s3:GetAccelerateConfiguration` |
| 활성화 후 반영 | 전송 속도 개선까지 최대 20분 |

일반 엔드포인트도 계속 쓸 수 있으므로, 켜두고 가속이 유리한 클라이언트만 accelerate 엔드포인트로 보내는 구성이 가능합니다. 적용 대상은 대륙 간 GB에서 TB 규모 정기 전송과 전 세계에서 중앙 버킷으로 업로드하는 경우입니다. Speed Comparison tool로 가속과 비가속 업로드 속도를 비교할 수 있고, 이 도구는 멀티파트 업로드를 사용합니다.

켜도 소용없는 경로가 둘 있습니다. 첫째, **온프레미스 회선의 물리 대역폭 상한은 늘어나지 않습니다.** 도입부 600 TB 사례에 Transfer Acceleration을 붙여도 `CIRCUIT` 값이 그대로이므로 계산 결과가 바뀌지 않습니다. 둘째, **S3 on Outposts는 Transfer Acceleration을 지원하지 않습니다.** S3 on Outposts에서 리전 S3로 올리는 지원 경로는 agent를 사용하는 DataSync입니다.

---

## 10. 멀티파트 업로드 임계와 part 경계

AWS는 객체가 **100 MB 이상이면 멀티파트 업로드를 사용하라**고 권고합니다. 실패한 part만 재시도할 수 있어 장거리 업로드의 실패 복구가 달라집니다.

| 항목 | 값 |
| :--- | :--- |
| 최대 객체 크기 | 48.8 TiB |
| 업로드당 최대 part 수 | 10,000개 |
| part 번호 | 1에서 10,000 |
| part 크기 | 5 MiB에서 5 GiB. 마지막 part는 최소 크기 제한이 없다 |
| list parts 응답 | 최대 1,000개 |
| list multipart uploads 응답 | 최대 1,000개 |

운영 측면에서 두 가지가 걸립니다. **멀티파트 업로드에는 만료가 없습니다.** 명시적으로 complete 또는 stop 하기 전까지 업로드된 part의 스토리지 요금이 계속 발생하므로, lifecycle의 `AbortIncompleteMultipartUpload` 액션으로 정리하는 것이 권장 구성입니다.

읽기 쪽에도 대칭이 있습니다. 멀티파트로 PUT한 객체는 **같은 part 크기로, 최소한 part 경계에 정렬해서 GET**하는 것이 성능상 유리합니다. `GET ?partNumber=N`으로 개별 part를 직접 지정할 수도 있습니다.

---

## 11. Transfer Family는 받는 서버와 나가는 connector 두 방향이다

Transfer Family는 파트너가 표준 프로토콜 클라이언트로 접속해 오는 **서버**와, AWS가 외부 파트너 서버에 능동적으로 접속하는 **connector** 두 방향을 제공합니다. 문항에서 방향이 뒤집힌 선지가 나오므로 구분해 두어야 합니다.

지원 프로토콜은 SFTP(version 3), FTPS, FTP, AS2, 그리고 브라우저 기반 전송입니다. **대상 스토리지는 S3와 EFS 두 가지뿐이고 FSx는 대상이 아닙니다.** "파트너 파일을 FSx for Windows File Server에 직접 받는다"는 구성은 성립하지 않습니다.

주요 쿼터는 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 계정당 서버 | 50개(조정 가능) |
| 계정당 VPC_ENDPOINT 서버 | 10개(조정 불가) |
| 서버당 service managed 사용자 | 10,000명(조정 가능) |
| 서버당 동시 세션 | 10,000개(조정 불가) |
| 개별 파일 크기 | 최대 5 TB(S3 객체 상한) |
| idle connection timeout | 1,800초 |

AS2와 SFTP connector 쪽 쿼터도 분리되어 있습니다.

| 항목 | 값 |
| :--- | :--- |
| AS2 connector와 agreement | 각각 계정당 100개 |
| AS2 certificate | 1,000개, profile당 10개 |
| 동시 AS2 메시지 | connector와 server당 400개 |
| 초당 AS2 메시지 | 서버당 100건 |
| AS2 메시지 크기 | inbound와 outbound 각각 최대 1,000 MB |
| SFTP connector | 계정당 100개 |
| `StartFileTransfer` | 초당 100 파일, 요청당 파일 10개 |
| `StartDirectoryListing` | 초당 3건 |
| 연결당 동시 multiplexed SFTP 세션 | 10개 |

워크플로우(MFTW)는 계정당 workflow 10개(조정 가능), workflow당 동시 신규 실행 100개, 신규 실행 refill rate 초당 1건입니다. logical directory mapping은 사용자당 최대 2,000 entry이고 JSON 문서 크기는 2,100,000 bytes입니다.

identity provider가 AWS Directory Service인 경우 **디렉터리당 사용자당 초당 2건**의 인증 제한이 걸립니다. AD group 매핑은 서버당 100개(조정 가능)입니다. 대량 자동화 클라이언트가 짧은 간격으로 재접속하는 시나리오에서 이 제한이 병목이 됩니다.

---

## 12. 엔드포인트 타입이 쓸 수 있는 프로토콜을 정한다

Transfer Family 서버의 엔드포인트 타입은 PUBLIC, VPC(Internal 또는 Internet Facing), 그리고 폐지된 VPC_ENDPOINT입니다. **VPC_ENDPOINT는 2021-05-19부터 신규 생성이 불가능합니다.**

![PUBLIC 과 VPC Internet Facing 과 VPC Internal 엔드포인트가 각각 허용하는 프로토콜과 소스 IP 제한 가능 여부, 그리고 대상 스토리지가 S3 와 EFS 로 고정되는 구조](/assets/img/sap-c02/transfer-family-endpoint-types.webp)

그림은 엔드포인트 타입 네 개를 한 묶음으로 두고, 각각이 쓸 수 있는 프로토콜과 통제 수단을 짝지어 보여줍니다. 어느 경로를 타든 도착점은 S3와 EFS 두 가지뿐이라는 점도 함께 담았습니다.

타입별 차이는 다음과 같습니다.

| 타입 | 프로토콜 | 소스 IP 제한 | 고정 IP |
| :--- | :--- | :--- | :--- |
| PUBLIC | FTP를 열 수 없다 | security group을 붙일 수 없다 | Elastic IP를 지정할 수 없다 |
| VPC Internet Facing | **SFTP와 FTPS만** | security group으로 제한한다 | 서브넷마다 Elastic IP를 지정한다 |
| VPC Internal | FTP를 포함해 받는다 | security group으로 제한한다 | 서브넷마다 Elastic IP를 지정한다 |
| VPC_ENDPOINT | 신규 생성 불가 | - | - |

파트너 방화벽 등록 때문에 고정 IP가 필요하고 파트너 IP만 허용해야 한다는 요구가 나오면 VPC 타입입니다. 여기에 평문 FTP만 지원하는 파트너가 섞여 있으면 그 파트너는 인터넷 경로로 받을 수 없고, Direct Connect나 VPN을 통한 내부 접근 경로로 분리해야 합니다.

VPC 엔드포인트는 최대 3개 AZ와 서브넷을 고를 수 있습니다. Internet Facing에서는 서브넷마다 Elastic IP를 지정해야 하고, **이미 사용 중인 EIP는 붙일 수 없으며**, 서버가 online인 동안에는 서브넷만 바꿀 수 있어 EIP를 바꾸려면 서버를 정지해야 합니다. 내부 전용 VPC 서버는 custom hostname을 지원하지 않습니다.

포트는 프로토콜마다 다릅니다.

| 프로토콜 | 포트 |
| :--- | :--- |
| SFTP | 22, 2222, 22000 중 선택. 기본 22 |
| FTP와 FTPS 컨트롤 채널 | 21 |
| FTP와 FTPS 데이터 채널 | 8192에서 8200 |

방화벽과 security group 규칙을 설계할 때 데이터 채널 범위를 빼먹으면 접속은 되는데 전송이 멈추는 형태로 나타납니다.

---

## 13. security policy 기본값이 생성 경로에 따라 갈린다

Transfer Family 서버의 security policy 기본값은 **어떻게 만들었는지에 따라 다릅니다.** 콘솔, API, CLI로 만들면 `TransferSecurityPolicy-2024-01`이 붙지만, **CloudFormation으로 만들고 기본값을 그대로 받으면 `TransferSecurityPolicy-2018-11`이 붙습니다.** IaC로 서버를 만들면서 "기본값이니 최신"이라고 가정하면 6년 전 정책으로 운영하게 됩니다.

security policy가 실제로 통제하는 항목도 프로토콜마다 다릅니다.

| 프로토콜 | 사용하는 항목 |
| :--- | :--- |
| SFTP | SshCiphers, SshKexs, SshMacs |
| FTPS | TlsCiphers |
| AS2 | ContentEncryptionCiphers, HashAlgorithms |
| FTP | 암호화를 쓰지 않으므로 어떤 항목도 사용하지 않는다 |

FTP 서버에 강한 security policy를 붙여 규정 준수를 주장하는 구성은 성립하지 않습니다. FTP는 평문이고 정책이 관여할 대상이 없습니다.

---

## 14. Storage Gateway 4종은 온프레미스가 요구하는 인터페이스로 갈린다

Storage Gateway는 온프레미스에 남는 워크로드가 AWS 스토리지를 로컬 인터페이스로 쓰게 하는 계층입니다. 현재 네 종류이고, 무엇을 고를지는 온프레미스 애플리케이션이 요구하는 인터페이스가 정합니다.

![NFS 와 SMB 파일 접근, Windows 원본이 필요한 SMB, iSCSI 블록 장치, iSCSI 가상 테이프라는 네 가지 인터페이스 요구가 각각 게이트웨이 종류와 AWS 백엔드 저장 형태로 이어지는 구조](/assets/img/sap-c02/storage-gateway-four-types.webp)

그림은 인터페이스 요구, 게이트웨이 종류, 백엔드 저장 형태를 세 열로 늘어놓고 각 행이 하나의 짝으로 고정되어 있음을 보여줍니다. 게이트웨이를 고른다는 것은 백엔드에 데이터가 어떤 형태로 남을지까지 고르는 일입니다.

| 게이트웨이 | 온프레미스 인터페이스 | 백엔드 | 현재 상태 |
| :--- | :--- | :--- | :--- |
| S3 File Gateway | NFS, SMB | S3 객체로 1:1 저장 | 정상 제공 |
| Amazon FSx File Gateway | SMB | FSx for Windows File Server | **신규 고객에게 제공되지 않는다** |
| Volume Gateway | iSCSI 블록 | S3와 EBS 스냅샷 | 정상 제공 |
| Tape Gateway | iSCSI VTL | S3 Glacier Flexible Retrieval 또는 Deep Archive | 정상 제공 |

배포 형태는 VMware ESXi, KVM, Hyper-V VM과 하드웨어 어플라이언스, 그리고 EC2 인스턴스입니다.

**FSx File Gateway는 신규 고객에게 제공되지 않습니다.** 기존 고객은 계속 쓸 수 있고, AWS는 FSx for Windows File Server 직접 접근으로의 전환을 안내합니다. 온프레미스에서 FSx를 캐싱하겠다는 신규 설계 선지는 이 사실로 탈락합니다.

File Gateway와 Volume Gateway의 갈림은 데이터가 백엔드에 어떤 형태로 남는지입니다. File Gateway는 파일이 **S3 객체로 1:1 저장**되어 S3에서 직접 읽을 수 있으므로 후속 분석 파이프라인에 그대로 연결됩니다. Volume Gateway는 iSCSI 블록 장치이고 백업 결과가 EBS 스냅샷이라 S3 객체로 직접 소비할 수 없습니다. 애플리케이션이 블록 장치를 요구하면 Volume, 객체로 후속 처리할 것이면 File입니다.

Tape Gateway는 다른 축입니다. 기존 백업 소프트웨어와 테이프 카탈로그를 그대로 유지하면서 물리 테이프 장비와 오프사이트 보관 계약만 제거하려는 요구에 대응합니다.

| 항목 | 값 |
| :--- | :--- |
| 가상 테이프 크기 | 최소 100 GiB, 최대 15 TiB |
| 게이트웨이에 할당 가능한 테이프 | 1,500개 |
| 할당 테이프 합계 | 1 PiB |
| 아카이브의 테이프 개수와 총 용량 | **제한이 없다** |
| 로컬 cache | 최소 150 GiB, 최대 64 TiB |
| 로컬 upload buffer | 최소 150 GiB, 최대 2 TiB |

7년 보관 같은 장기 규정에 대응할 수 있는 이유가 마지막 줄입니다. 게이트웨이에 붙여 두는 테이프는 제한이 있지만 아카이브로 넘긴 테이프에는 개수와 용량 제한이 없습니다.

S3 File Gateway의 쿼터도 정리해 두겠습니다.

| 항목 | 값 |
| :--- | :--- |
| 게이트웨이당 file share | 50개 |
| 개별 파일 크기 | 최대 5 TiB |
| 경로 길이 | 최대 1,024 bytes |
| 파일 이름 | 최대 255 bytes |
| cache | 최소 150 GiB, 최대 64 TiB |
| `GatewayCapacity` | Small 5M, Medium 10M, Large 20M 파일의 메타데이터 캐시 |

**file share 하나는 S3 버킷 하나에만 연결됩니다.** 여러 file share를 같은 버킷에 붙이려면 share마다 겹치지 않는 고유 prefix를 설정해야 read/write 충돌이 나지 않습니다. 백엔드가 S3이므로 폴더 크기나 총 파일 수 자체에는 상한이 없고, 상한이 걸리는 것은 게이트웨이가 동시에 캐시할 수 있는 메타데이터 파일 수입니다.

5 TiB 상한을 넘는 파일을 쓰면 동작이 조용히 어긋납니다. 조각내어 쓰면 **첫 5 TiB만 업로드**되고, 한 번에 쓰면 Windows 클라이언트에서는 파일이 생성되지 않으며 Linux 클라이언트에서는 크기 0인 파일이 생깁니다.

---

## 15. cached volume과 stored volume, 그리고 16 TiB 스냅샷 경계

Volume Gateway는 두 모드가 있고 데이터가 어디에 사는지가 다릅니다.

| 모드 | 데이터 위치 | 볼륨 최대 | 게이트웨이당 볼륨 | 게이트웨이 합계 |
| :--- | :--- | :--- | :--- | :--- |
| cached | S3에 두고 자주 쓰는 부분집합만 로컬 캐시 | 32 TiB | 32개 | 1,024 TiB |
| stored | 전체 데이터셋이 로컬, 스냅샷만 S3로 비동기 백업 | 16 TiB | 32개 | 512 TiB |

선택 기준은 명확합니다. 저지연 접근이 전체 데이터셋에 필요하면 stored, 온프레미스 스토리지 용량 절감이 목적이면 cached입니다. 온프레미스 어레이 증설을 피하려는 요구에 stored를 고르면 요구와 정반대가 됩니다.

여기에 시험에서 실제로 답을 가르는 경계가 하나 있습니다. **16 TiB를 넘는 cached volume에서 만든 스냅샷은 Storage Gateway 볼륨으로는 복원되지만 EBS 볼륨으로는 복원할 수 없습니다.** cached volume의 최대 크기가 32 TiB라는 사실만 보고 28 TiB 볼륨 하나를 만들면, 나중에 그 스냅샷으로 EC2에 EBS 볼륨을 붙여 검증하려는 계획이 무너집니다. 스냅샷을 EBS로 복원할 계획이 있으면 볼륨을 16 TiB 이하로 나눠야 합니다.

---

## 16. RefreshCache는 캐시를 데우지 않는다

S3 File Gateway를 쓰면서 게이트웨이 밖에서 버킷을 직접 갱신하는 구성이면 캐시 인벤토리를 맞추는 문제가 생깁니다. 여기서 `RefreshCache` API의 동작을 정확히 알아야 합니다.

**`RefreshCache`는 캐시 스토리지에 파일 데이터를 가져오지 않습니다.** 문서 원문은 `This operation does not import files into the S3 File Gateway cache storage. It only updates the cached inventory`입니다. 갱신되는 것은 파일 목록이지 파일 내용이 아니므로, 미리 호출해 두어도 첫 읽기는 여전히 S3에서 당겨옵니다. "캐시를 데워 첫 읽기 지연을 없앤다"는 선지는 이 한 줄로 탈락합니다.

갱신 경로는 TTL 기반 자동 refresh와 API 기반 refresh 두 가지이고 성격이 다릅니다.

| 항목 | TTL 기반 자동 refresh | API 기반 refresh |
| :--- | :--- | :--- |
| 범위 | 디렉터리 단위 비재귀 | recursive 지정 가능 |
| 트리거 | TTL 만료 후 그 디렉터리에 실제 NFS 또는 SMB 접근이 발생할 때 | 호출할 때 |
| 접근 블록 | **refresh가 끝날 때까지 그 디렉터리 접근을 블록한다** | 다른 작업과 동시에 돌고 일반적으로 블록하지 않는다 |
| 비용 | 접근이 없으면 S3 API 요금도 발생하지 않는다 | recursive가 더 비싸다 |

TTL 기반 refresh가 접근을 블록하기 때문에 AWS는 **실용 범위에서 가장 긴 TTL**을 권장합니다. "항상 최신 상태를 유지하려고 TTL을 5분으로 줄인다"는 조치는 권장 방향의 반대이고 접근 지연을 만듭니다.

API 기반 refresh에도 함정이 둘 있습니다. 첫째, **`RefreshCache`는 직렬입니다.** 하나가 끝나야 다음이 시작되므로 객체 생성과 삭제가 많은 버킷에서 성능이 나빠집니다. AWS는 S3 이벤트로 매 업로드마다 트리거하는 대신 CloudWatch 스케줄 규칙을 권장하고, 기본 권장 주기는 고정 30분이며 대형 버킷은 1시간에서 2시간입니다. 둘째, **요청은 작업을 시작시킬 뿐 완료를 뜻하지 않습니다.** 완료 확인은 CloudWatch 이벤트로 구독하는 `refresh-complete` 알림으로 하고, 수백만 객체 규모 버킷에서는 갱신에 수 시간이 걸릴 수 있습니다.

게이트웨이는 **현재 캐시가 stale인지 스스로 판정하지 못합니다.** 신선도와 무관하게 현재 내용을 NFS와 SMB 작업에 그대로 사용합니다.

---

## 17. 게이트웨이 배포 요건과 복구되지 않는 VM

게이트웨이를 실제로 배포할 때 걸리는 요건입니다.

| 항목 | 값 |
| :--- | :--- |
| 온프레미스 VM 최소 요건 | vCPU 4, **예약 RAM 16 GiB**, 디스크 80 GiB |
| EC2 배포 최소 인스턴스 | xlarge(compute optimized 계열은 2xlarge) |
| Graviton(ARM) 인스턴스 | 지원되지 않는다 |
| 게이트웨이 다운로드와 활성화와 업데이트 | 최소 100 Mbps 대역폭 |
| 하드웨어 어플라이언스 | 2025-05-12 신규 제공 중단. 기존 고객은 2028년 5월까지 지원. Dell PowerEdge R640, 뒷면 물리 포트 iDRAC와 em1-em4 5개, IPv4만 |

EC2 File Gateway에는 조건부 요건이 하나 더 있습니다. **S3 버킷에 500만 개가 넘는 객체가 있고 gp2 루트 볼륨을 쓰면 기동 성능을 위해 루트 EBS 볼륨이 최소 350 GiB 필요합니다.** 신규 EC2 File Gateway는 기본이 gp3이므로 이 요건이 없습니다. 오래 전에 만든 게이트웨이를 그대로 쓰다가 버킷 객체 수가 늘어난 환경에서 기동이 느려지는 형태로 드러납니다.

EC2 게이트웨이가 ephemeral storage를 캐시로 쓰는 경우에는 정지 절차가 다릅니다. 업로드가 끝나기 전에 인스턴스를 정지하면 캐시에 남은 데이터가 유실될 수 있으므로, 정지 전에 `CachePercentDirty` CloudWatch 지표가 0인지 확인해야 합니다.

가장 중요한 운영 제약은 복구 쪽입니다. **게이트웨이 VM은 스냅샷이나 클론에서 복구할 수 없습니다.** VM이 고장나면 새 게이트웨이를 활성화하고 데이터를 복구해야 합니다. dynamic memory와 virtual memory ballooning도 지원하지 않습니다. "게이트웨이 VM 스냅샷을 떠 두고 장애 시 복원한다"는 백업 계획은 성립하지 않습니다.

네트워크를 프라이빗으로 유지하려면 게이트웨이에 private VPC endpoint를 구성합니다. 이 경우 public internet 접근이 필요 없어지고, 추가로 열어야 하는 포트는 1026(control plane), 1027(anon control plane), 1028(proxy), 1031(data plane), 2222(support channel)입니다.

---

## 18. Outposts rack과 server가 지원하는 서비스가 다르다

데이터가 시설 밖으로 나가면 안 되거나 온프레미스 시스템과의 지연이 밀리초 단위여야 하면 Outposts가 후보가 됩니다. 여기서 rack과 server의 차이가 답을 가릅니다.

![Outposts rack 이 local gateway 로, server 가 local network interface 로 온프레미스에 연결되고 둘 다 service link 로 홈 리전에 묶이는 구조](/assets/img/sap-c02/outposts-rack-vs-server.webp)

그림은 고객 시설 안에 rack과 server를 나란히 두고 각각의 온프레미스 연결 경로와 지원 서비스 범위를 함께 보여줍니다. 두 폼팩터 모두 홈 리전으로 향하는 service link를 갖는다는 점도 담았습니다.

| 항목 | Outposts rack | Outposts server |
| :--- | :--- | :--- |
| 로컬 지원 서비스 | EC2, EBS, EBS 스냅샷, S3 on Outposts, EKS 노드, ECS, RDS, EMR, ElastiCache, ALB, Route 53 Resolver, IoT Greengrass | EC2, ECS, App Mesh Envoy, VPC subnet, IoT Greengrass |
| 블록 스토리지 | EBS | **instance store만. EBS를 지원하지 않는다** |
| 온프레미스 연결 | local gateway(LGW), IPv4 전용 | local network interface(LNI) |
| 판매 상태 | 제공 중 | **1U와 2U 모두 판매 중단** |

Outposts server의 인스턴스는 instance store 볼륨만 제공하므로, EBS 스냅샷 1개짜리 EBS-backed AMI를 골라야 하고 인스턴스 스토리지 용량으로 애플리케이션 요구를 맞춰야 합니다. server에 EBS gp3 볼륨을 붙여 데이터베이스를 올리거나 EKS 노드를 배치하는 구성은 성립하지 않습니다.

Outposts rack의 인스턴스는 반대로 루트 볼륨을 작게 두는 것이 권장 구성입니다. AWS는 루트 볼륨을 30 GiB 이하로 제한하고 데이터 볼륨을 따로 두라고 권장하며, 루트 볼륨의 NVMe timeout을 늘리는 것도 권장합니다.

rack은 industry-standard 42U입니다. 물리 구성에서 기억할 값은 다음과 같습니다.

| 항목 | 1세대 | 2세대 |
| :--- | :--- | :--- |
| 최소 footprint | compute rack 1개 | **compute rack 1개 + network rack 1개, 총 2 rack** |
| 인스턴스 | M5, C5, R5, G4dn | M7i, M8i, C7i, C8i, R7i, R8i와 bare-metal 가속 네트워킹 인스턴스 bmn-sf2e, bmn-cx2, bmn-cx3a |
| 전력 구성 | 5 kVA, 10 kVA, 15 kVA | 10 kVA, 15 kVA, 30 kVA |
| ACE rack | compute rack 4개 이상이면 필수 | 컴퓨트와 네트워킹을 독립 확장한다 |

ACE(Aggregation, Core, Edge) rack은 compute rack이 4개 이상이면 필수이고, 4개 미만이어도 이후 확장 계획이 있으면 미리 설치하라고 권고합니다.

세대별 로컬 서비스 목록에서 주의할 점이 하나 있습니다. 2세대 비교표의 로컬 지원 서비스 목록에는 1세대에 있던 EBS 스냅샷, Route 53 Resolver, ElastiCache, Elastic Disaster Recovery가 나열되지 않습니다. 이것이 실제 미지원인지 표의 생략인지는 문서만으로 판정되지 않으므로, 2세대에 이 네 가지를 전제하는 설계는 별도 확인이 필요합니다.

---

## 19. service link가 끊겼을 때 남는 기능과 사라지는 기능

Outpost는 홈 리전과 **service link**로 묶입니다. service link는 Outpost와 리전 사이의 암호화된 VPN 연결 집합이고 VLAN으로 트래픽을 분리합니다. rack의 service link는 AWS가 생성하고 server의 service link는 사용자가 생성합니다.

여기에 IPv6 제약이 붙습니다. **service link는 Outpost와 리전 사이 IPv6를 지원하지 않고, Outposts는 internet gateway를 통한 IPv6도 사용할 수 없습니다.** local gateway도 IPv4 전용입니다. Outpost 인스턴스와 리전 사이 통신을 IPv6로 구성하는 선지는 여기서 탈락합니다.

연결 단절 시 동작은 문서 사이에 서술이 갈립니다. Snowball Edge 대안 안내 문서는 두 폼팩터가 DDIL(Denied, Disrupted, Intermittent, Limited) 환경에서 최대 7일 동안 AWS 연결 없이 동작할 수 있다고 씁니다. 반면 S3 on Outposts 문서는 `The Outposts rack is not designed for disconnected operations or environments with limited to no connectivity`라고 쓰고, Outposts 동작 문서도 상시 일관된 연결을 전제로 설계됐다고 씁니다. **설계 전제는 상시 연결이고, AWS가 DDIL 환경의 최대 7일 동작을 별도로 언급한다**는 정도로 병기해 두는 것이 안전합니다.

단절이 실제로 무엇을 깨뜨리는지는 구성에 따라 갈립니다. **Route 53 hosted zone과 레코드는 리전에 남지만, Outposts rack에 Route 53 Resolver를 배치해 로컬 캐시를 사용할 수 있습니다. Resolver on Outposts를 구성하면 service link가 끊겨도 로컬 리소스 조회와 캐시에 있는 public DNS 조회가 계속됩니다.** 다만 control plane 변경, health check와 DNS failover는 동작하지 않고, 리전 VPC 리소스는 이름을 해석해도 연결이 복구될 때까지 접근할 수 없습니다. Resolver on Outposts를 쓰지 않는 구성에서는 기존처럼 리전 Resolver 연결에 의존하므로, 온프레미스 DNS가 필요하면 DHCP option set으로 별도 DNS를 지정합니다.

반대로 service link를 타지 않는 경로도 있습니다. **같은 Outpost에 있는 VPC 사이 peering 트래픽은 Outpost 안에 머물고 리전을 왕복하지 않습니다.**

연결 관련해서 성립하지 않는 구성이 하나 더 있습니다. **Outpost를 같은 VPC 안의 다른 Outpost나 Local Zone에 연결할 수 없습니다.** 두 Outpost를 직접 이어 저지연 통신을 만드는 설계는 이 제약에 걸립니다.

비용 축에서도 한 줄 기억할 것이 있습니다. Outposts 요금에는 리전에서 Outpost로 오는 데이터 전송과, AWS가 가용성과 보안 유지를 위해 수행하는 데이터 전송이 청구됩니다.

---

## 20. S3 on Outposts는 리전 S3의 부분집합이 아니다

S3 on Outposts는 이름이 S3이지만 리전 S3에서 기능을 몇 개 뺀 형태가 아니라, 별도의 제약 집합을 가진 스토리지입니다. 객체 데이터는 항상 Outpost에 남고 리전에 존재하지 않으므로 데이터 레지던시 요건을 만족하는 근거가 됩니다.

| 항목 | 값 |
| :--- | :--- |
| 스토리지 클래스 | `OUTPOSTS` 하나. 다른 클래스 지정 시 `InvalidStorageClass` 에러 |
| 기본 암호화 | SSE-S3. SSE-C 선택 가능. **SSE-KMS 미지원** |
| 버킷 크기 | 최대 50 TB |
| 객체 크기 | 최대 5 TB |
| 계정당 Outposts 버킷 | 100개 |
| 버킷당 access point | 10개 |
| access point policy | 20 KB |
| 접근 경로 | **access point와 endpoint를 통해서만 접근한다** |

**SSE-KMS를 지원하지 않는다**는 점이 규제 시나리오에서 자주 나옵니다. "내부 표준이 고객 관리 KMS 키를 요구한다"는 지문이 있으면 S3 on Outposts를 쓰는 순간 그 표준에 예외가 필요하고, 그 예외를 인정하는 선지가 정답이 됩니다.

지원되지 않는 기능 목록도 길고, 그 자체가 오답 선지의 재료입니다.

- Transfer Acceleration, S3 Batch Operations, S3 Inventory
- lifecycle transition(객체 삭제와 미완료 멀티파트 정리는 지원)
- Object Lock legal hold와 retention, SSE-KMS, S3 Replication Time Control
- Event Notifications, Lambda events, S3 Select
- Requester Pays, server access logging, CORS, ACL, website access, MFA delete, 조건부 요청

lifecycle 항목이 특히 헷갈립니다. **lifecycle transition은 지원되지 않고 객체 삭제와 미완료 멀티파트 정리만 됩니다.** 스토리지 클래스가 하나뿐이므로 전환할 대상 자체가 없습니다.

네트워크 제약도 설계 단계에서 걸립니다.

| 항목 | 값 |
| :--- | :--- |
| VPC당 endpoint | 1개 |
| Outpost당 endpoint | 100개 |
| VPC CIDR | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 서브스페이스만 |
| CIDR 중복 | 겹치지 않는 VPC들에서만 endpoint를 만들 수 있다 |
| endpoint 생성 | IP 주소 4개가 필요하다 |

운영 방식에도 차이가 있습니다. **콘솔은 리전에 호스팅되므로 콘솔로 Outpost 객체를 업로드하거나 관리할 수 없습니다.** REST API, CLI, SDK만 가능하고 지원되는 CLI 명령은 `cp`, `mv`, `sync`, `ls`, `presign`, `rm`입니다. 용량이 부족하면 API가 insufficient capacity exception(ICE)을 반환합니다. 버킷 소유자 계정이 모든 객체의 소유자이고 버킷 작업도 버킷 소유자 계정만 할 수 있습니다.

Outpost와 리전 사이 데이터 이동은 DataSync와의 통합으로 자동화합니다. 앞서 본 대로 이 경로는 에이전트가 필요하고 Basic mode만 지원합니다.

---

## 21. Local Zone과 Wavelength Zone은 시설 소유자와 진입 게이트웨이로 갈린다

엣지 배치 선택지 세 가지는 시설을 누가 운영하는지와 트래픽이 어느 게이트웨이로 들어오는지로 구분됩니다.

![인터넷 사용자와 통신사 단말과 시설 내부 시스템이 각각 리전 AZ 와 Local Zone 과 Wavelength Zone 과 Outposts 로 진입하고 네 배치 모두 부모 리전 control plane 에 묶이는 구조](/assets/img/sap-c02/edge-placement-boundaries.webp)

그림은 세 종류의 사용자와 네 종류의 배치 위치를 시설 소유자별로 묶어 보여줍니다. 각 배치가 부모 리전 control plane과 연결되는 관계도 함께 담았습니다.

| 배치 | 시설 소유 | 진입 경로 |
| :--- | :--- | :--- |
| 리전 가용 영역 | AWS | internet gateway |
| Local Zone | AWS | **자체 인터넷 연결과 Direct Connect** |
| Wavelength Zone | 통신사 | **carrier gateway 전용** |
| Outposts | 고객 | local gateway 또는 local network interface |

**Local Zone**은 리전의 확장입니다. 코드는 리전 코드 뒤에 물리 위치 식별자가 붙는 형태이고 예시는 `us-west-2-lax-1`입니다. 사용하려면 먼저 활성화하고 Local Zone에 서브넷을 만들어야 합니다. 활성화 자체에는 추가 요금이 없지만 **Local Zone의 AWS 리소스 가격은 부모 리전과 다릅니다.**

Local Zone에서 시험이 노리는 함정이 둘 있습니다. 첫째, **일부 zone은 opt in만으로 쓸 수 없고 Support 요청이 선행돼야 합니다.** 문서 표에 별표가 붙은 항목이고 Atlanta, Chicago, Dallas, Houston, Miami, New York City, Phoenix, Portland, Auckland, Taipei가 여기 해당합니다. 둘째, **zone마다 제공되는 서비스가 다릅니다.** "Local Zone이니까 부모 리전에서 쓰던 관리형 서비스를 그대로 배치할 수 있다"는 추론은 성립하지 않습니다. 예를 들어 ElastiCache 사용자 가이드는 지원 Local Zone을 `us-west-2-lax-1a`와 `us-west-2-lax-1b` 두 곳으로 못박고 지원 노드 타입도 M5, R5, T3로 한정하며 global datastore와 online migration을 미지원으로 적습니다. Local Zones 사용자 가이드와 EC2 Regions and Zones 페이지는 어느 쪽도 zone별 서비스 목록을 제공하지 않으므로, EC2와 EBS를 넘어서는 서비스는 그 서비스 문서에서 zone 지원 여부를 따로 확인해야 합니다.

network border group이라는 개념도 함께 나옵니다. AWS가 IP를 광고하는 AZ, Local Zone, Wavelength Zone의 고유 집합이고 Local Zone 인스턴스는 여기서 IP를 할당받습니다. 현재 Amazon 제공 IPv6 VPC 주소를 지원하는 Local Zone은 **9개**입니다: `us-east-1-atl-2a`, `us-east-1-chi-2a`, `us-east-1-dfw-2a`, `us-east-1-iah-2a`, `us-east-1-mia-2a`, `us-east-1-nyc-2a`, `us-west-2-lax-1a`, `us-west-2-lax-1b`, `us-west-2-phx-2a`. 목록은 변경될 수 있으므로 배포 전 공식 목록을 확인해야 합니다.

**Wavelength Zone**은 통신사 데이터센터 안에 배치된 격리 zone입니다. 리전에 묶이고 리전 control plane이 관리하며, 코드 예시는 `us-east-1-wl1-bos-wlz-1`입니다. 사용하려면 opt in 후 서브넷을 만듭니다. **모든 리전에 Wavelength Zone이 있지는 않습니다.**

carrier gateway의 동작이 배치 판단을 가릅니다.

| 방향 | 동작 |
| :--- | :--- |
| inbound | 특정 위치의 carrier network에서 오는 트래픽을 허용한다 |
| outbound | carrier network와 인터넷으로 나가는 트래픽을 허용한다 |
| 인터넷에서 inbound | **일반적인 직접 연결 설정을 제공하지 않는다. 일부 Wavelength Zone 파트너의 fixed wireless access는 별도 조건** |
| IP 버전 | IPv4만 지원한다 |

**일반 인터넷에서 Wavelength Zone으로 직접 들어오는 inbound 연결을 설정할 수 없다**는 점이 결정적입니다. 일부 Wavelength Zone 파트너의 fixed wireless access는 별도 조건으로 제공되지만, 5G 단말과 일반 유선 인터넷 사용자를 함께 받아야 하는 요구를 Wavelength Zone 단독 배치로 해결할 수 있다는 근거는 되지 않습니다.

Carrier IP는 Wavelength Zone 서브넷의 network interface에 붙는 주소이고, carrier gateway가 인스턴스 사설 IP를 Carrier IP로 NAT합니다. 리전의 internet gateway와 유사한 역할이며 network border group에서 할당합니다.

MTU 값도 문항 재료입니다.

| 구간 | MTU |
| :--- | :--- |
| 같은 Wavelength Zone 인스턴스 사이 | 9001 bytes |
| carrier gateway와 Wavelength Zone 사이 | 1500 bytes |
| Wavelength Zone 인스턴스와 리전 인스턴스, public IP 사용 | 1500 bytes |
| Wavelength Zone 인스턴스와 리전 인스턴스, private IP 사용 | **1300 bytes** |

jumbo frame 9001은 같은 Wavelength Zone 안에서만 성립합니다. 리전과의 private IP 통신에 9001을 전제하면 어긋납니다.

라우팅 기본값도 확인해 두어야 합니다. Wavelength 서브넷은 기본적으로 main route table을 상속하고 local route로 VPC 내 다른 서브넷과 통신합니다. AWS는 carrier gateway를 기본 경로로 두는 custom route table 구성을 권장합니다.

커버리지 자체가 선지를 지우는 경우도 있습니다. 문서 기준으로 Wavelength Zone이 있는 부모 리전은 us-east-1, us-west-2, ap-northeast-1, ca-central-1, eu-west-2, eu-west-3 여섯 곳입니다. 통신사는 미국 Verizon, 일본 KDDI, 캐나다 Bell, 영국 British Telecom, 모로코 Orange, 세네갈 Sonatel입니다. 미국 zone은 전부 Verizon 단일 통신사이므로 **같은 도시에서 통신사를 바꿔가며 이중화하는 구성은 Wavelength 안에서 성립하지 않습니다.** ap-northeast-2에 Wavelength Zone을 붙이는 선지도 이 목록으로 탈락합니다. zone 개수와 리전 목록은 문서 스냅샷이므로 시험 대비로는 "부모 리전이 한정된다"는 사실 쪽을 기억하는 편이 안전합니다.

---

## 22. 암기해야 하는 하드 리밋과 동작 제약

**전송 시간과 회선**

| 항목 | 값 |
| :--- | :--- |
| 전송 시간 공식 | `(DATA_SIZE * 8) / (CIRCUIT * NETWORK_UTILIZATION * 3600 * AVAILABLE_HOURS)` |
| 공식 문서 예시 | 100 TB, 1 Gbps, 사용률 80%, 24시간 가용 = 11.57일 |
| 계산 결과의 성격 | theoretical minimum. 실제 조건으로 보정한다 |
| cutover 비중 | 전체 마이그레이션 시간의 최대 30% |
| hosted connection 속도 | 50, 100, 200, 300, 400, 500 Mbps와 1, 2, 5, 10, 25 Gbps |
| hosted connection 생성 | Partner만 생성하고 사용자가 accept한다. 속도 변경도 Partner만 |
| 1 Gbps 이상 | 요건을 충족한 Partner만 |
| 25 Gbps | 100 Gbps 포트가 있는 location에서만 |
| traffic policing | 최대 속도 도달 시 초과 트래픽 drop |

**Snow Family와 물리 전송**

| 항목 | 값 |
| :--- | :--- |
| 신규 고객 주문 | 어떤 Snow Family 디바이스도 불가 |
| 신규 고객 차단 시점 | 2025-11-07 |
| 구형 3종과 Snowcone 단종 | 2024-11-12, 지원 종료 2025-11-12 |
| 남은 구성 | Storage Optimized 210 TB, Compute Optimized(28 TB NVMe SSD) |
| CPU | 두 구성 모두 AMD Rome 64 cores 2 GHz, 104 vCPU |
| 메모리 | 최대 416 GB customer usable |
| 네트워크 인터페이스 | 2x 10 Gbit RJ45, 1x 25 Gbit SFP28, 1x 100 Gbit QSFP28. **한 번에 하나만** |
| 10G RJ45 케이블 | Cat6A UTP 최대 55 m |
| 무게와 전력 | 22.54 kg, 평균 304 W, 정격 1200 W |
| 동작 온도 | Storage Optimized 0-30 C, Compute Optimized 0-45 C |
| Data Transfer Terminal 대상 | **Enterprise Support 고객만** |
| Data Transfer Terminal 위치 공개 | 콘솔에서 예약을 만든 뒤 |

**DataSync**

| 항목 | 값 |
| :--- | :--- |
| 태스크당 처리량 상한 | 에이전트 10 Gbps, 무에이전트 5 Gbps. 조정 불가 |
| 계정과 리전당 task | 100개(조정 가능) |
| 태스크당 큐잉 실행 | 50개 |
| Enhanced mode 동시 실행 | 120개 |
| task execution 이력 | 30일 |
| Enhanced mode manifest | 최대 20 GB |
| Basic mode 객체 수 | 온프레미스와 AWS 사이 5천만, AWS 스토리지 사이 2천5백만(조정 가능) |
| Enhanced mode 객체 수 | 사실상 무제한 |
| Basic mode 에이전트 | vCPU 4, 디스크 80 GB, RAM 32 GB 또는 64 GB |
| Enhanced mode 에이전트 | vCPU 8, 디스크 80 GB, RAM 32 GB |
| EC2 에이전트 최소 | 2xlarge. 권장 m5.2xlarge, m5.4xlarge, m6a.2xlarge |
| 하이퍼바이저 | VMware ESXi 7.0/8.0, KVM, Hyper-V 2012 R2/2016/2019, EC2 |
| 위치당 에이전트 | Basic 4개, Enhanced 4개. 전부 online이어야 실행된다 |
| 엔드포인트 타입 | public, FIPS, VPC(PrivateLink), FIPS VPC. **에이전트당 하나만** |
| VPC 엔드포인트 요건 | default tenancy, shared VPC 미지원, 같은 계정 |
| 대역폭 제한 단위 | 콘솔 MiB/s, API `BytesPerSecond`, 기본값 `Use available` |
| 대역폭 제한 반영 | 실행 중 변경 시 60초 안에 |
| task filter | 102,400자 |
| 파일 경로 | 4,096 bytes, 구성요소 255 bytes |
| S3 객체 이름 | 1,024 UTF-8 문자 |

**S3 Transfer Acceleration과 멀티파트**

| 항목 | 값 |
| :--- | :--- |
| 버킷 이름 | 마침표 불가, DNS 호환, virtual-hosted style만 |
| 지원 리전 | 15개 |
| 활성화 후 반영 | 최대 20분 |
| 상태 값 | `Enabled`, `Suspended` |
| 멀티파트 권장 임계 | 객체 100 MB 이상 |
| 최대 객체 크기 | 48.8 TiB |
| 업로드당 part | 10,000개, 번호 1에서 10,000 |
| part 크기 | 5 MiB에서 5 GiB, 마지막 part는 예외 |
| list 응답 | 각각 최대 1,000개 |
| 미완료 업로드 | 만료 없음. `AbortIncompleteMultipartUpload`로 정리 |

**Transfer Family**

| 항목 | 값 |
| :--- | :--- |
| 프로토콜 | SFTP(version 3), FTPS, FTP, AS2, 브라우저 기반 |
| 대상 스토리지 | S3와 EFS뿐 |
| SFTP 포트 | 22, 2222, 22000. 기본 22 |
| FTP와 FTPS | 컨트롤 21, 데이터 8192-8200 |
| internet-facing VPC 엔드포인트 | **SFTP와 FTPS만** |
| VPC_ENDPOINT | 2021-05-19부터 신규 생성 불가, 계정당 10개(조정 불가) |
| VPC 엔드포인트 AZ | 최대 3개 |
| 계정당 서버 | 50개(조정 가능) |
| 서버당 service managed 사용자 | 10,000명 |
| 서버당 동시 세션 | 10,000개(조정 불가) |
| 개별 파일 | 최대 5 TB |
| idle timeout | 1,800초 |
| AS2 connector와 agreement | 각각 100개 |
| AS2 메시지 | 동시 400개, 초당 100건, 최대 1,000 MB |
| SFTP connector | 100개, `StartFileTransfer` 초당 100 파일 요청당 10개 |
| `StartDirectoryListing` | 초당 3건 |
| workflow | 계정당 10개, 동시 신규 실행 100개, refill 초당 1건 |
| logical directory mapping | 사용자당 2,000 entry, JSON 2,100,000 bytes |
| Directory Service 인증 | 디렉터리당 사용자당 초당 2건 |
| AD group 매핑 | 서버당 100개 |
| 기본 security policy | 콘솔/API/CLI `TransferSecurityPolicy-2024-01`, **CloudFormation `TransferSecurityPolicy-2018-11`** |

**Storage Gateway**

| 항목 | 값 |
| :--- | :--- |
| 종류 | S3 File Gateway, FSx File Gateway(신규 고객 미제공), Volume Gateway, Tape Gateway |
| cached volume | 최대 32 TiB, 게이트웨이당 32개, 합계 1,024 TiB |
| stored volume | 최대 16 TiB, 게이트웨이당 32개, 합계 512 TiB |
| 16 TiB 초과 cached 스냅샷 | **EBS 볼륨으로 복원 불가** |
| 가상 테이프 | 100 GiB에서 15 TiB, 할당 1,500개, 합계 1 PiB |
| 아카이브 테이프 | 개수와 용량 제한 없음 |
| Tape Gateway 로컬 디스크 | cache 150 GiB-64 TiB, upload buffer 150 GiB-2 TiB |
| S3 File Gateway file share | 게이트웨이당 50개, share 하나가 버킷 하나 |
| S3 File Gateway 파일 | 최대 5 TiB, 경로 1,024 bytes, 이름 255 bytes |
| `GatewayCapacity` | Small 5M, Medium 10M, Large 20M |
| VM 최소 요건 | vCPU 4, 예약 RAM 16 GiB, 디스크 80 GiB |
| EC2 최소 인스턴스 | xlarge(compute optimized는 2xlarge), Graviton 미지원 |
| 활성화 대역폭 | 최소 100 Mbps |
| gp2 루트 볼륨 조건 | 버킷 객체 500만 개 초과 시 최소 350 GiB |
| VPC endpoint 추가 포트 | 1026, 1027, 1028, 1031, 2222 |
| 하드웨어 어플라이언스 | 2025-05-12 신규 제공 중단. 기존 고객은 2028년 5월까지 지원. Dell PowerEdge R640, IPv4만, NIC마다 고유 서브넷 |
| VM 복구 | 스냅샷과 클론에서 복구 불가 |
| `RefreshCache` | 인벤토리만 갱신, 직렬 실행, 권장 주기 30분(대형 버킷 1-2시간) |

**Outposts와 엣지**

| 항목 | 값 |
| :--- | :--- |
| rack 규격 | 42U |
| 1세대 최소 | compute rack 1개 |
| 2세대 최소 | compute rack 1개 + network rack 1개 |
| ACE rack | compute rack 4개 이상이면 필수 |
| 전력 | 1세대 5/10/15 kVA, 2세대 10/15/30 kVA |
| server 판매 | 1U와 2U 모두 중단 |
| server 스토리지 | instance store만, EBS 미지원 |
| rack 루트 볼륨 권장 | 30 GiB 이하 |
| 온프레미스 연결 | rack은 LGW(IPv4만), server는 LNI |
| service link | 암호화 VPN 집합, IPv6 미지원 |
| Outpost 사이 연결 | 같은 VPC 안 다른 Outpost나 Local Zone에 연결 불가 |
| S3 on Outposts 버킷 | 최대 50 TB, 계정당 100개 |
| S3 on Outposts 객체 | 최대 5 TB |
| S3 on Outposts access point | 버킷당 10개, policy 20 KB |
| S3 on Outposts 암호화 | SSE-S3 기본, SSE-C 선택, **SSE-KMS 불가** |
| S3 on Outposts endpoint | VPC당 1개, Outpost당 100개, IP 4개 필요 |
| S3 on Outposts VPC CIDR | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 서브스페이스 |
| Local Zone 요금 | 활성화 무료, 리소스 가격은 부모 리전과 다름 |
| Local Zone IPv6 | 현재 9개 zone: us-east-1-atl-2a, us-east-1-chi-2a, us-east-1-dfw-2a, us-east-1-iah-2a, us-east-1-mia-2a, us-east-1-nyc-2a, us-west-2-lax-1a, us-west-2-lax-1b, us-west-2-phx-2a |
| Wavelength 부모 리전 | us-east-1, us-west-2, ap-northeast-1, ca-central-1, eu-west-2, eu-west-3 |
| carrier gateway | IPv4만, 일반 인터넷에서 직접 inbound 연결 설정 불가. 일부 파트너의 fixed wireless access는 별도 조건 |
| Wavelength MTU | zone 내부 9001, carrier 구간 1500, 리전과 public IP 1500, **private IP 1300** |

---

## 23. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| DataSync 에이전트 필요 대 불필요 | 온프레미스, 자체관리 객체 스토리지, 타 클라우드에서 EFS나 FSx로 가는 전송에는 필요하다. 같은 계정의 AWS 스토리지 사이나 한쪽이 S3인 계정 간 전송에는 필요 없다. 처리량 상한도 10 Gbps와 5 Gbps로 갈린다 |
| DataSync Enhanced mode 대 Basic mode | Enhanced는 객체 수 무제한, 병렬 처리, JSON 로그, 전송분만 검증이다. Basic은 객체 수 쿼터, 순차 처리, 전체 검증이다. FSx for Windows/ONTAP/OpenZFS와 S3 on Outposts는 Basic만 가능하고 mode는 생성 후 변경 불가다 |
| DataSync 대 S3 Transfer Acceleration | DataSync는 NFS/SMB/HDFS/객체 스토리지와 S3/EFS/FSx 사이를 메타데이터와 권한을 보존하며 옮기고 스케줄과 검증을 제공한다. Transfer Acceleration은 버킷 기능이라 대상이 S3뿐이고 버킷 이름에 마침표가 없어야 하며 15개 리전에서만 지원된다 |
| DataSync 대 Transfer Family | DataSync는 AWS가 주도하는 push와 pull 동기화다. Transfer Family는 외부 파트너가 표준 프로토콜 클라이언트로 접속해 오는 서버를 제공하고 대상이 S3와 EFS뿐이다. 반복 배치 마이그레이션은 DataSync, 파트너의 기존 SFTP 클라이언트를 그대로 받는 상시 수신은 Transfer Family다 |
| Transfer Family server 대 connector | server는 외부 클라이언트를 받는 수신 엔드포인트다. SFTP와 AS2 connector는 AWS가 외부 파트너 서버에 능동적으로 접속하는 발신 경로다. 쿼터도 분리돼 있다 |
| Transfer Family PUBLIC 대 VPC 엔드포인트 | VPC 타입만 security group으로 소스 IP를 제한하고 Elastic IP를 직접 붙일 수 있다. internet-facing VPC 엔드포인트는 SFTP와 FTPS만 지원하고 FTP는 Internal 접근에서만 된다 |
| 콘솔 생성 대 CloudFormation 생성 security policy | 기본값이 다르다. 콘솔/API/CLI는 `TransferSecurityPolicy-2024-01`, CloudFormation은 `TransferSecurityPolicy-2018-11`이다 |
| S3 File Gateway 대 Volume Gateway | File Gateway는 NFS와 SMB로 접근하고 파일이 S3 객체로 1:1 저장돼 S3에서 직접 읽을 수 있다. Volume Gateway는 iSCSI 블록 장치이고 백업 결과가 EBS 스냅샷이라 S3 객체로 직접 소비할 수 없다 |
| Volume Gateway cached 대 stored | cached는 최대 32 TiB에 합계 1,024 TiB이고 데이터는 S3에 있다. stored는 최대 16 TiB에 합계 512 TiB이고 전체 데이터가 로컬에 있다. 16 TiB 초과 cached 볼륨 스냅샷은 EBS로 복원할 수 없다 |
| Tape Gateway 대 Volume Gateway 스냅샷 | Tape Gateway는 기존 백업 소프트웨어의 VTL 인터페이스를 그대로 쓰고 Glacier로 아카이빙하며 아카이브에는 개수와 용량 제한이 없다. Volume Gateway 스냅샷은 EBS 스냅샷이라 백업 소프트웨어 카탈로그와 무관하다 |
| File Gateway TTL refresh 대 API refresh | TTL은 비재귀이고 만료 뒤 실제 접근이 있을 때만 돌며 그동안 해당 디렉터리 접근을 블록한다. API는 recursive 지정이 가능하고 일반적으로 블록하지 않지만 recursive가 더 비싸다. 둘 다 인벤토리만 갱신한다 |
| Outposts rack 대 server | rack은 42U에 EBS, S3 on Outposts, EKS 노드, RDS, EMR, ElastiCache, ALB를 로컬로 돌리고 local gateway로 붙는다. server는 EC2와 ECS만 돌고 instance store만 쓰며 local network interface로 붙는다. server는 신규 판매 중단이다 |
| Outposts 1세대 대 2세대 rack | 1세대는 compute rack 1개로 시작하고 4 rack 이상이면 ACE rack이 필요하며 M5/C5/R5/G4dn이다. 2세대는 최소 2 rack이고 M7i/M8i/C7i/C8i/R7i/R8i와 bare-metal 가속 인스턴스이며 컴퓨트와 네트워킹을 독립 확장한다 |
| Outposts 대 Local Zones 대 Wavelength | Outposts는 고객 소유 시설에 AWS 하드웨어를 둔다. Local Zone은 AWS가 운영하는 리전 확장 위치로 자체 인터넷과 Direct Connect를 갖는다. Wavelength Zone은 통신사 데이터센터 안에 있고 carrier gateway로 붙는다. 일반 인터넷에서 직접 inbound 연결은 설정할 수 없으며 일부 파트너의 fixed wireless access는 별도 조건이다 |
| S3 on Outposts 대 리전 S3 | Outposts는 버킷 50 TB, 계정당 100개, access point 필수, 스토리지 클래스 `OUTPOSTS` 고정, SSE-KMS 불가, lifecycle transition 불가, Transfer Acceleration 불가, Event Notifications 불가, 콘솔 업로드 불가다 |
| Data Transfer Terminal 대 Snow Family | 둘 다 물리 전송이지만 Snow는 디바이스가 고객에게 배송되고 DTT는 고객이 자기 저장장치를 들고 AWS 시설로 간다. DTT는 Enterprise Support 고객 전용이고 Snow는 신규 고객 주문 자체가 불가하다 |
| 태스크 처리량 상한 대 사용자 대역폭 제한 | 상한은 서비스가 걸고 조정 불가다. 대역폭 제한은 사용자가 걸고 실행 중에도 바꿀 수 있으며 60초 안에 반영된다. "업무 시간에 WAN을 잠식하지 않게 하라"는 요구의 답은 후자다 |
| Local Zone 대 Wavelength Zone 커버리지 | Local Zone은 여러 대륙에 있고 일부는 Support 요청이 필요하다. Wavelength Zone은 부모 리전 여섯 곳뿐이고 통신사에 묶인다. "가장 가까운 엣지" 문항에서 커버리지 자체가 선지를 지운다 |

---

## 24. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| 신규 고객이 100 TB를 Snowball Edge로 오프라인 반입한다 | Snow Family 디바이스는 신규 고객이 주문할 수 없다. 온라인은 DataSync, 오프라인은 Data Transfer Terminal 또는 파트너다 |
| Snowball Edge 80 TB Storage Optimized 여러 대로 병렬 반입한다 | 80 TB Storage Optimized는 2024-11-12 단종 3종 중 하나다. 현재 문서에 남은 Storage Optimized 구성은 210 TB뿐이다 |
| 엣지 수집 지점에 Snowcone을 배치해 주기적으로 반송한다 | Snowcone은 2024-11-12 단종이고 기존 고객 지원도 2025-11-12에 끝났다 |
| 페타바이트 규모라 Snowmobile 100 PB로 한 번에 옮긴다 | Snowmobile은 현재 사용자 가이드가 없고 FAQ 본문에도 등장하지 않는다. 100 PB는 2016년 발표 수치이므로 현행 근거가 아니다 |
| Business Support 고객이 Data Transfer Terminal 예약을 잡는다 | 현재 DTT는 Enterprise Support 고객에게만 제공된다 |
| Snowball Edge의 10 GbE RJ45와 100 GbE QSFP28을 묶어 대역폭을 늘린다 | 한 번에 하나의 네트워크 인터페이스만 사용할 수 있다 |
| 1 Gbps 회선으로 100 TB를 11.6일이면 옮길 수 있다고 계획에 그대로 넣는다 | 그 값은 사용률 80%와 24시간 가용을 가정한 theoretical minimum이다. 문서가 실제 조건 보정을 요구하고 cutover가 최대 30%를 먹을 수 있다고 명시한다 |
| Direct Connect hosted connection을 콘솔에서 25 Gbps로 바로 주문한다 | hosted connection은 콘솔에서 요청할 수 없고 Partner가 만들어야 한다. 1 Gbps 이상은 자격을 갖춘 Partner만, 25 Gbps는 100 Gbps 포트가 있는 location에서만 가능하다 |
| 타 클라우드에서 S3로 전송하니 DataSync 에이전트를 배포한다 | Azure Blob을 포함한 타 클라우드 객체 스토리지와 S3 사이는 에이전트가 필요 없다. 필요한 조합은 문서가 열거한 네 가지다 |
| 대상이 EFS나 FSx면 무조건 에이전트가 필요하다 | 소스가 S3이거나 같은 계정의 AWS 스토리지 서비스 사이면 대상이 EFS나 FSx여도 필요 없다 |
| 파일이 수억 개이니 Enhanced mode로 FSx for Windows File Server에 옮긴다 | Enhanced mode가 지원하는 FSx는 Lustre뿐이다. Windows File Server, ONTAP, OpenZFS는 Basic mode 전용이다 |
| 이미 만든 Basic mode task를 Enhanced mode로 전환해 처리량을 올린다 | task mode는 생성 후 변경할 수 없다. 새 task를 만들어야 한다 |
| 에이전트를 4개 붙여 DataSync 전송의 고가용성을 확보한다 | 다중 에이전트는 성능용이지 HA용이 아니다. 붙은 에이전트 중 하나라도 offline이면 task를 시작할 수 없다 |
| 에이전트 없이 S3에서 S3로 옮기는 태스크를 10 Gbps로 계획한다 | 에이전트를 쓰지 않는 전송의 태스크당 상한은 5 Gbps다 |
| DataSync 대역폭 제한을 걸어 태스크 처리량을 10 Gbps 위로 올린다 | 사용자 대역폭 제한은 상한을 낮추는 방향으로만 작동한다 |
| 업무 시간 WAN 잠식을 막으려고 실행 중인 task를 멈추고 제한을 건 새 task를 만든다 | `UpdateTaskExecution`으로 실행 중이나 큐에 있는 execution의 제한을 바꿀 수 있고 60초 안에 반영된다 |
| 온프레미스 NFS를 다른 리전의 S3로 DataSync 한 번에 직접 옮긴다 | NFS, SMB, HDFS, object storage 위치는 리전 간 전송이 불가능하고 두 위치 모두 에이전트를 활성화한 리전에 있어야 한다 |
| DataSync를 shared VPC의 PrivateLink 엔드포인트로 태운다 | DataSync VPC service endpoint는 shared VPC를 지원하지 않고 default tenancy VPC여야 하며 엔드포인트와 VPC와 에이전트가 같은 계정이어야 한다 |
| 에이전트 하나에 VPC 엔드포인트와 public 엔드포인트를 함께 등록해 폴백을 만든다 | 에이전트 하나는 엔드포인트 타입 하나만 쓸 수 있다 |
| EC2 인스턴스 위에 KVM을 올려 DataSync 에이전트를 배포한다 | 지원 하이퍼바이저에 EC2 위 KVM 구성은 없다 |
| 버킷 `logs.example.com`에 Transfer Acceleration을 켜 해외 업로드를 가속한다 | 버킷 이름에 마침표가 있으면 Transfer Acceleration을 쓸 수 없다 |
| Transfer Acceleration을 켜면 모든 리전에서 즉시 가속된다 | 지원 리전이 15개로 한정되고 활성화 후 속도 개선까지 최대 20분이 걸린다 |
| Transfer Acceleration으로 온프레미스 회선 한계를 넘긴다 | 엣지 로케이션 경유는 장거리 구간 효율을 올릴 뿐 회선의 물리 대역폭을 늘리지 못한다 |
| S3 on Outposts에 Transfer Acceleration을 붙여 리전으로 빠르게 올린다 | S3 on Outposts는 Transfer Acceleration을 지원하지 않는다. 리전 이동 경로는 DataSync다 |
| S3 on Outposts에 lifecycle 규칙을 걸어 90일 뒤 Glacier로 보낸다 | 스토리지 클래스가 `OUTPOSTS` 하나뿐이고 lifecycle transition이 지원되지 않는다 |
| 규제 요건상 S3 on Outposts 객체를 고객 관리 KMS 키로 암호화한다 | S3 on Outposts는 SSE-KMS를 지원하지 않는다. 기본 SSE-S3와 선택적 SSE-C만 된다 |
| 콘솔로 S3 on Outposts 버킷에 객체를 올린다 | 콘솔은 리전에 호스팅되므로 Outpost 객체를 업로드하거나 관리할 수 없다. REST API, CLI, SDK만 가능하다 |
| internet-facing Transfer Family VPC endpoint에 FTP를 열어 레거시 파트너를 받는다 | internet-facing VPC hosted endpoint는 SFTP와 FTPS만 지원한다 |
| Transfer Family로 파트너 파일을 FSx for Windows File Server에 직접 받는다 | 대상 스토리지는 S3와 EFS뿐이다 |
| CloudFormation으로 Transfer Family 서버를 만들면 최신 security policy가 붙는다 | CloudFormation 기본값은 `TransferSecurityPolicy-2018-11`이다 |
| FTP 서버에 강한 security policy를 붙여 전송 구간 암호화를 만족시킨다 | FTP는 암호화를 쓰지 않아 security policy의 어떤 항목도 사용하지 않는다 |
| PUBLIC 엔드포인트에 security group을 붙여 파트너 IP만 허용한다 | PUBLIC 엔드포인트에는 security group을 연결할 수 없고 Elastic IP로 주소를 고정할 수도 없다 |
| cached volume을 24 TiB로 만들고 스냅샷을 EBS 볼륨으로 복원해 EC2로 리프트한다 | 16 TiB를 넘는 cached volume 스냅샷은 Storage Gateway 볼륨으로만 복원된다 |
| S3 File Gateway로 8 TiB 아카이브 파일 하나를 올린다 | 개별 파일 상한은 5 TiB다. 조각내어 쓰면 첫 5 TiB만 올라간다 |
| FSx File Gateway를 새로 배포해 온프레미스에서 FSx for Windows File Server를 캐싱한다 | FSx File Gateway는 신규 고객에게 제공되지 않는다 |
| 게이트웨이 VM 스냅샷을 떠 두고 장애 시 복원한다 | Storage Gateway는 스냅샷이나 클론에서 게이트웨이를 복구하는 것을 지원하지 않는다 |
| `RefreshCache`를 호출해 캐시를 데워 첫 읽기 지연을 없앤다 | 인벤토리만 갱신하고 파일 데이터를 캐시 스토리지에 가져오지 않는다 |
| S3 `ObjectCreated` 이벤트로 매 업로드마다 `RefreshCache`를 호출한다 | `RefreshCache`는 직렬이라 객체가 많으면 성능이 무너진다. AWS는 CloudWatch 고정 주기 30분을 권장한다 |
| `RefreshCache` API가 200을 반환했으니 파일 목록이 최신이다 | 요청은 작업을 시작시킬 뿐이다. 완료 확인은 `refresh-complete` 알림으로 한다 |
| TTL 기반 자동 refresh를 5분으로 짧게 잡아 항상 최신 상태를 유지한다 | TTL 만료 디렉터리에 접근하는 NFS와 SMB 작업이 refresh가 끝날 때까지 블록된다. AWS 권장은 반대로 가장 긴 TTL이다 |
| Outposts server에 EBS gp3 볼륨을 붙여 데이터베이스를 올린다 | server는 EBS를 지원하지 않고 instance store만 제공하며 RDS도 rack에서만 돈다 |
| Outposts server에 EKS 노드를 배치해 온프레미스 쿠버네티스를 돌린다 | EKS 노드는 rack에서만 지원된다. server는 EC2와 ECS까지다 |
| 두 Outpost를 같은 VPC 안에서 직접 연결해 저지연 통신을 만든다 | 같은 VPC 안의 다른 Outpost나 Local Zone에 Outpost를 연결할 수 없다 |
| service link가 끊겨도 Outpost 인스턴스가 Route 53 private hosted zone을 계속 해석한다 | Resolver on Outposts를 구성한 rack은 local cache로 일부 질의를 계속 처리할 수 있지만 health check, DNS failover와 control plane 변경은 중단된다. Resolver on Outposts가 없는 구성은 region Resolver 연결이 필요하고 대안은 DHCP option set이다 |
| Outposts 인스턴스와 리전 사이 통신을 IPv6로 구성한다 | service link는 IPv6를 지원하지 않고 local gateway도 IPv4 전용이다 |
| Wavelength Zone 인스턴스에 인터넷에서 직접 들어오는 API 엔드포인트를 노출한다 | carrier gateway는 일반 인터넷에서 직접 inbound 연결을 제공하지 않는다. 일부 파트너의 fixed wireless access는 별도 조건이라 일반 유선 인터넷 사용자 수용 근거가 되지 않는다 |
| Wavelength Zone과 리전 인스턴스 사이 private IP 통신에 jumbo frame 9001을 쓴다 | 그 구간 MTU는 1300 bytes다. 9001은 같은 Wavelength Zone 안에서만 성립한다 |
| 서울 사용자를 위해 ap-northeast-2에 Wavelength Zone을 붙인다 | Wavelength Zone이 있는 부모 리전은 여섯 곳뿐이고 ap-northeast-2는 포함되지 않는다 |
| 통신사를 바꿔가며 같은 도시의 Wavelength Zone을 이중화한다 | 미국 zone은 전부 Verizon 단일 통신사이고 다른 리전도 도시당 통신사가 하나다 |
| Local Zone에 리소스를 두면 부모 리전과 같은 요금이 적용된다 | 활성화는 무료지만 리소스 가격은 부모 리전과 다르다 |
| 부모 리전에서 opt in 하면 표에 있는 어느 Local Zone이든 바로 서브넷을 만들 수 있다 | 별표가 붙은 zone은 Support 요청이 선행돼야 한다 |
| Local Zone이 열려 있으니 부모 리전에서 쓰던 관리형 서비스를 그대로 그 zone에 배치한다 | zone마다 제공 서비스가 다르다. ElastiCache는 `us-west-2-lax-1a`와 `-1b` 두 zone에서만 지원된다 |

---

## 25. 예상 문제 10문항

**Q1.** 미디어 회사가 온프레미스 NAS의 600 TB를 S3로 옮깁니다. 인터넷 회선은 1 Gbps이고 업무 시간 다른 트래픽 때문에 마이그레이션에는 40%만 할당할 수 있습니다. 프로젝트 기한은 8주이고, 회사는 최근에 AWS 계정을 개설한 신규 고객입니다. MOST appropriate 접근은 무엇입니까?

- A. 온프레미스에 S3 File Gateway를 배포하고 캐시가 채워지는 대로 업로드한다
- B. S3 Transfer Acceleration을 켜고 멀티파트 업로드로 병렬 전송한다
- C. Direct Connect Delivery Partner에게서 전송 기간에만 hosted connection을 조달하고 AWS DataSync로 전송한다
- D. Snowball Edge Storage Optimized 디바이스 3대를 주문해 오프라인으로 반입한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

AWS 전송 시간 공식은 `(DATA_SIZE * 8) / (CIRCUIT * NETWORK_UTILIZATION * 3600 * AVAILABLE_HOURS)`입니다. 600 TB를 1 Gbps의 40%로 계산하면 이론 최소값만 138일이 넘어 8주 기한을 만족하지 못합니다. AWS는 Snowball Edge 대안 안내에서 네트워크 대역폭 한계를 넘어야 하면 데이터 전송 프로젝트 기간 동안만 Direct Connect Delivery Partner에게서 hosted connection을 조달해 DataSync와 함께 쓰라고 지목합니다.

- A가 틀린 이유: File Gateway는 온프레미스에서 파일 접근을 유지하면서 S3를 백엔드로 쓰는 캐시 계층이고, 실제 업로드는 같은 회선을 그대로 사용한다.
- B가 틀린 이유: Transfer Acceleration은 엣지 로케이션을 경유해 장거리 구간 효율을 올리는 기능이고 온프레미스 회선의 물리 대역폭 상한을 늘리지 못한다.
- D가 틀린 이유: Snowball Edge는 신규 고객에게 더 이상 제공되지 않으며 이 변경으로 어떤 Snow Family 디바이스도 신규 고객이 주문할 수 없다.

</details>

**Q2.** Azure Blob Storage에 있는 객체 8천만 개(90 TB)를 S3 Standard로 옮깁니다. 팀은 온프레미스나 Azure에 VM을 띄울 권한이 없습니다. 전송이 끝나면 같은 AWS 계정의 EFS 파일 시스템으로 일부 데이터셋을 다시 복사해야 합니다. LEAST operational overhead 구성은 무엇입니까?

- A. Azure에 DataSync 에이전트 VM을 배포하고 Basic mode task로 전송한다
- B. Azure Blob에서 S3로는 Enhanced mode task로 에이전트 없이 전송하고, S3에서 EFS로도 같은 계정 안이므로 에이전트 없이 전송한다
- C. EC2에 DataSync 에이전트를 배포하고 두 전송 모두 이 에이전트를 경유시킨다
- D. AzCopy 스크립트로 S3에 복사한 뒤 DataSync로 EFS에 복사한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

DataSync는 S3와 타 클라우드 객체 스토리지 사이, 그리고 같은 계정의 AWS 스토리지 서비스 사이 전송에 에이전트를 요구하지 않습니다. Basic mode는 온프레미스와 타 클라우드에서 AWS로 가는 전송에 task execution당 객체 5천만 개 쿼터가 걸리는데 대상이 8천만 개이므로 Enhanced mode가 필요하고, Enhanced mode는 객체 수가 사실상 무제한입니다.

- A가 틀린 이유: Basic mode의 실행당 객체 쿼터 5천만 개를 8천만 개가 초과하고, 에이전트 VM 운영 부담이 그대로 남으며 Azure에 VM을 띄울 권한도 없다.
- C가 틀린 이유: 두 경로 모두 에이전트가 필요 없는 조합이라 최소 2xlarge 이상의 EC2 에이전트를 상시 운영하는 만큼 운영 부담과 비용이 늘어난다.
- D가 틀린 이유: AzCopy는 실행 호스트와 스크립트를 직접 운영해야 하고 DataSync가 제공하는 스케줄, 재시도, 무결성 검증을 대체하지 못한다.

</details>

**Q3.** 온프레미스 NFS 공유에 파일 3억 개가 있고 이것을 Amazon FSx for Windows File Server로 옮깁니다. 팀은 객체 수 제한이 없는 Enhanced mode를 쓰려고 계획을 세웠고 이미 Basic mode task 하나를 만들어 둔 상태입니다. MOST appropriate 계획은 무엇입니까?

- A. Basic mode task를 쓰고 include filter로 데이터셋을 나눠 여러 task execution으로 전송한다
- B. 같은 위치에 에이전트 4개를 붙여 고가용성과 무제한 객체 처리를 확보한다
- C. Enhanced mode task를 새로 만들어 한 번에 전송한다
- D. 기존 task를 Enhanced mode로 전환하고 한 번에 전송한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Enhanced mode가 지원하는 위치는 S3, EFS, FSx for Lustre, NFS, SMB, HDFS, Azure Blob, object storage입니다. FSx for Windows File Server, FSx for NetApp ONTAP, FSx for OpenZFS는 Enhanced mode를 지원하지 않아 Basic mode를 써야 하고, Basic mode는 task execution당 객체 5천만 개 쿼터가 걸리므로 필터로 분할해 실행합니다.

- B가 틀린 이유: 위치 하나에 에이전트를 여러 개 붙이는 것은 성능 목적이고 고가용성 구성이 아니다. 붙은 에이전트 중 하나라도 offline이면 task를 시작할 수 없고, 에이전트 수는 객체 쿼터를 바꾸지 않는다.
- C가 틀린 이유: 대상이 FSx for Windows File Server이므로 Enhanced mode task 자체를 만들 수 없다.
- D가 틀린 이유: task mode는 task를 만든 뒤에 변경할 수 없다.

</details>

**Q4.** 규제 요건상 온프레미스 파일 서버에서 S3로 가는 DataSync 데이터 트래픽과 제어 트래픽이 모두 인터넷을 경유하면 안 됩니다. 회사는 Direct Connect private VIF를 보유하고 있고, 네트워크 팀은 여러 애플리케이션 계정이 공유하는 shared VPC에 엔드포인트를 두자고 제안했습니다. 요건을 충족하는 조치 두 가지는 무엇입니까? (2개 선택)

- A. 인터페이스 엔드포인트에서 Private DNS Name을 켜서 같은 VPC의 모든 에이전트가 엔드포인트를 쓰게 한다
- B. shared VPC에 DataSync 인터페이스 엔드포인트를 만들고 참여 계정의 에이전트들이 함께 사용하게 한다
- C. 에이전트를 VPC service endpoint(PrivateLink) 타입으로 활성화한다
- D. 데이터 경로를 S3 Transfer Acceleration 엔드포인트로 바꾼다
- E. 에이전트 하나에 public 엔드포인트와 VPC 엔드포인트를 함께 등록해 장애 시 public으로 넘어가게 한다
- F. DataSync 인터페이스 엔드포인트, VPC, 에이전트를 모두 같은 AWS 계정의 default tenancy VPC에 배치한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C, F**

DataSync 에이전트는 활성화 시점에 public, FIPS, VPC(PrivateLink), FIPS VPC 중 하나의 서비스 엔드포인트 타입을 선택하며, VPC 타입을 고르면 제어와 데이터 트래픽이 VPC 안에 머뭅니다. VPC service endpoint를 쓰는 VPC는 default tenancy여야 하고 shared VPC는 지원되지 않으며, 엔드포인트와 VPC와 에이전트가 같은 AWS 계정에 있어야 합니다.

- A가 틀린 이유: AWS는 Private DNS Name을 끄는 것을 권장한다. 켜면 같은 VPC 안의 다른 에이전트가 public service endpoint에 도달하지 못하는 부작용이 생기고, 이 설정은 요건 충족의 조건도 아니다.
- B가 틀린 이유: DataSync VPC service endpoint는 shared VPC를 지원하지 않는다.
- D가 틀린 이유: Transfer Acceleration은 엣지 로케이션을 경유하는 public 경로이므로 인터넷 미경유 요건에 정면으로 어긋난다.
- E가 틀린 이유: 에이전트 하나는 엔드포인트 타입 하나만 사용할 수 있다. 타입을 섞으려면 타입마다 에이전트를 따로 만들어야 하고, public 폴백 자체가 요건 위반이다.

</details>

**Q5.** 글로벌 지사 12곳이 각 지역에서 개당 20 GB에서 80 GB인 영상 파일을 us-east-1의 버킷 `media.example.com`에 업로드합니다. 지사별 업로드 시간 편차가 크고 일부 지사에서는 업로드 실패가 반복됩니다. 변경은 SDK 설정과 버킷 구성 수준까지만 허용됩니다. MOST appropriate 개선은 무엇입니까?

- A. 기존 버킷에 Transfer Acceleration을 활성화하고 accelerate 엔드포인트로 업로드한다
- B. 지사마다 가까운 리전에 버킷을 만들고 Cross-Region Replication으로 us-east-1에 모은다
- C. 지사마다 S3 File Gateway를 배포해 업로드를 로컬 캐시로 받는다
- D. 마침표가 없는 이름의 버킷을 새로 만들어 Transfer Acceleration을 활성화하고, SDK에서 accelerate 엔드포인트와 멀티파트 업로드를 사용한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

Transfer Acceleration은 버킷 이름이 DNS 호환이어야 하고 마침표를 포함하면 사용할 수 없으며 virtual-hosted style 요청만 지원합니다. `media.example.com`은 마침표를 포함하므로 새 버킷이 필요합니다. AWS는 객체가 100 MB 이상이면 멀티파트 업로드를 권장하고, 멀티파트는 업로드당 part 10,000개와 part 크기 5 MiB에서 5 GiB를 지원해 실패한 part만 재시도할 수 있습니다.

- A가 틀린 이유: 버킷 이름에 마침표가 있으면 Transfer Acceleration을 활성화할 수 없다.
- B가 틀린 이유: 리전 12곳의 버킷과 복제 규칙을 운영해야 하고 스토리지가 이중으로 과금되며 복제 지연이 생긴다. 원본 버킷 이름 제약도 해결되지 않는다.
- C가 틀린 이유: File Gateway는 온프레미스 어플라이언스와 캐시 디스크를 지사마다 운영해야 하고, 실제 S3 업로드는 같은 인터넷 경로를 그대로 사용한다.

</details>

**Q6.** 파트너 40곳이 기존 SFTP 클라이언트로 파일을 전송합니다. 회사는 이 파일을 S3에 받아야 하고, 파트너 IP에서만 접속을 허용해야 하며, 파트너 방화벽 등록을 위해 고정 IP가 필요합니다. 파트너 중 3곳은 평문 FTP만 지원하고 이들은 Direct Connect로 연결되어 있습니다. MOST appropriate 구성은 무엇입니까?

- A. VPC_ENDPOINT 타입 서버를 만들고 앞에 Network Load Balancer를 둔다
- B. internet-facing VPC 엔드포인트 하나에 SFTP, FTPS, FTP를 모두 노출한다
- C. VPC hosted internet-facing 엔드포인트로 SFTP와 FTPS를 노출하고, FTP 파트너는 VPC 내부 접근 경로로 받으며, security group으로 소스 IP를 제한하고 서브넷마다 Elastic IP를 지정한다
- D. PUBLIC 엔드포인트를 만들고 security group으로 파트너 IP를 제한한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Transfer Family의 VPC 엔드포인트 타입은 security group으로 소스 IP를 제한하고 서브넷마다 Elastic IP를 직접 붙일 수 있습니다. internet-facing VPC hosted endpoint에서는 SFTP와 FTPS만 사용할 수 있고 FTP는 VPC 내부 접근에서만 가능하므로, 평문 FTP 파트너는 Direct Connect를 통한 내부 경로로 받아야 합니다.

- A가 틀린 이유: VPC_ENDPOINT 타입은 2021년 5월 19일부터 신규 생성이 불가능하다.
- B가 틀린 이유: internet-facing VPC hosted endpoint는 FTP를 지원하지 않는다.
- D가 틀린 이유: PUBLIC 엔드포인트에는 security group을 연결할 수 없고 Elastic IP로 주소를 고정할 수도 없다.

</details>

**Q7.** 온프레미스 영상 편집 애플리케이션이 iSCSI 블록 볼륨에 직접 씁니다. 애플리케이션은 당분간 온프레미스에 남지만 스토리지 어레이 증설은 피해야 합니다. 최근 접근되는 데이터는 전체의 5% 수준이고, 데이터는 현재 20 TiB에서 28 TiB까지 늘어납니다. 운영팀은 스냅샷을 EBS 볼륨으로 복원해 EC2에서 검증할 계획입니다. MOST appropriate 구성은 무엇입니까?

- A. stored volume을 만들어 전체 데이터셋을 로컬에 유지한다
- B. 각 16 TiB 이하인 cached volume 여러 개로 나눠 만든다
- C. S3 File Gateway로 NFS 공유를 제공하고 애플리케이션 경로를 바꾼다
- D. 28 TiB 이상을 담는 cached volume 하나를 만든다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

cached volume은 데이터를 S3에 두고 자주 쓰는 부분집합만 로컬 캐시에 남겨 온프레미스 용량을 절감합니다. cached volume의 최대 크기는 32 TiB이지만 16 TiB를 넘는 cached volume에서 만든 스냅샷은 Storage Gateway 볼륨으로만 복원되고 EBS 볼륨으로는 복원할 수 없습니다. 게이트웨이당 볼륨 32개, cached 합계 1,024 TiB까지 쓸 수 있으므로 16 TiB 이하로 분할하면 두 요건을 모두 만족합니다.

- A가 틀린 이유: stored volume은 전체 데이터셋을 로컬에 유지하므로 어레이 증설 회피 목적에 어긋나고 볼륨 최대 크기도 16 TiB다.
- C가 틀린 이유: File Gateway는 NFS와 SMB 파일 인터페이스를 제공하고 iSCSI 블록 장치를 제공하지 않는다.
- D가 틀린 이유: 16 TiB를 넘는 cached volume의 스냅샷은 EBS 볼륨으로 복원할 수 없어 EC2 검증 계획이 성립하지 않는다.

</details>

**Q8.** 기업이 상용 백업 소프트웨어로 물리 테이프 라이브러리에 주간 백업을 남기고 7년 보관 규정을 지킵니다. 백업 소프트웨어와 카탈로그를 그대로 유지하면서 테이프 장비와 오프사이트 보관 계약을 없애려 합니다. 복원 요청은 연 2회에서 3회이고 12시간 이내 복원이면 충분합니다. MOST cost-effective 구성은 무엇입니까?

- A. Tape Gateway를 배포하고 아카이브를 S3 Glacier Deep Archive로 보낸다
- B. AWS Backup으로 온프레미스 서버를 직접 백업한다
- C. Volume Gateway stored volume에 백업을 쓰고 스냅샷을 남긴다
- D. S3 File Gateway 공유에 백업 파일을 쓰고 lifecycle로 Glacier Deep Archive로 전환한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Tape Gateway는 가상 테이프 라이브러리 인터페이스를 제공하므로 기존 백업 소프트웨어와 카탈로그를 바꾸지 않고 그대로 쓸 수 있고, 백업 데이터를 S3 Glacier Flexible Retrieval 또는 S3 Glacier Deep Archive에 보관합니다. 게이트웨이에 할당하는 가상 테이프는 1,500개와 합계 1 PiB로 제한되지만 아카이브에 보관하는 테이프의 개수와 총 용량에는 제한이 없어 7년 보관에 적합합니다.

- B가 틀린 이유: AWS Backup은 기존 백업 소프트웨어와 카탈로그를 유지한다는 요건을 충족하지 못하고 물리 테이프 라이브러리를 대체하는 VTL 인터페이스를 제공하지 않는다.
- C가 틀린 이유: stored volume은 전체 데이터셋을 로컬에 유지해 장비 제거 목적에 어긋나고, EBS 스냅샷은 백업 소프트웨어의 테이프 카탈로그와 연결되지 않는다.
- D가 틀린 이유: 파일 공유로 바꾸면 백업 소프트웨어의 테이프 워크플로와 보관 정책을 다시 설계해야 하고, File Gateway의 개별 파일 상한 5 TiB가 대형 백업 이미지에 걸릴 수 있다.

</details>

**Q9.** 제조 공장의 제어 시스템이 밀리초 단위 응답을 요구하고, 규제상 공정 데이터가 공장 밖으로 나가면 안 됩니다. 워크로드는 컨테이너로 돌고 로컬 객체 스토리지에 데이터를 쓰며, 함께 옮길 관계형 데이터베이스는 RDS로 운영하려 합니다. 내부 표준은 객체를 고객 관리 KMS 키로 암호화하라고 정합니다. MOST appropriate 설계와 그에 따른 조정은 무엇입니까?

- A. Wavelength Zone에 배치하고 carrier gateway로 공장 네트워크와 연결한다
- B. Outposts server를 배치해 ECS와 RDS를 운영하고 EBS 볼륨에 데이터를 저장한다
- C. Local Zone에 워크로드를 배치하고 리전 S3 버킷을 SSE-KMS로 암호화한다
- D. Outposts rack을 배치해 ECS와 RDS와 S3 on Outposts를 로컬로 운영하고, S3 on Outposts가 SSE-KMS를 지원하지 않으므로 객체 암호화는 SSE-S3 또는 SSE-C로 예외 처리한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

Outposts rack은 EC2, EBS, S3 on Outposts, EKS 노드, ECS, RDS, EMR 등을 고객 시설에서 로컬로 운영하고 S3 on Outposts의 객체는 Outpost에 남아 리전에 존재하지 않으므로 데이터 레지던시 요건을 만족합니다. 다만 S3 on Outposts의 스토리지 클래스는 `OUTPOSTS` 하나이고 기본 암호화는 SSE-S3, 선택적으로 SSE-C만 지원하며 SSE-KMS는 지원하지 않으므로 내부 표준에 예외가 필요합니다.

- A가 틀린 이유: Wavelength Zone은 통신사 데이터센터 안에 있고 carrier gateway는 통신사 네트워크 트래픽만 다루며 공장 시설 내 데이터 레지던시를 제공하지 않는다.
- B가 틀린 이유: Outposts server는 EBS와 S3 on Outposts와 RDS를 지원하지 않고 instance store만 제공하며, 1U와 2U server는 신규 판매가 중단됐다.
- C가 틀린 이유: Local Zone은 AWS가 운영하는 리전 확장 위치이고 공장 안이 아니므로 공정 데이터가 시설 밖으로 나간다.

</details>

**Q10.** 게임 회사가 특정 대도시 사용자에게 저지연 세션 서버를 제공하려 합니다. 사용자 다수는 5G 모바일 네트워크를 쓰지만, 유선 인터넷 사용자와 회사 Direct Connect를 통해 접속하는 스튜디오도 함께 받아야 합니다. 세션 서버는 EC2 인스턴스와 EBS 볼륨으로 구성되고, 회사는 시설을 직접 확보하거나 관리하지 않기로 했습니다. MOST appropriate 배치는 무엇입니까?

- A. 회사가 확보한 도심 코로케이션 공간에 Outposts rack을 설치하고 local gateway로 사용자 트래픽을 받는다
- B. Wavelength Zone에만 배치하고 carrier gateway로 모든 사용자 트래픽을 받는다
- C. 해당 도시의 Local Zone에 서브넷을 만들어 EC2와 EBS를 배치한다
- D. 부모 리전에 배치하고 AWS Global Accelerator를 앞에 둔다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Local Zone은 사용자와 지리적으로 가까운 리전의 확장이고 AWS가 운영하는 위치입니다. 문서는 Local Zone이 자체 인터넷 연결을 갖고 Direct Connect를 지원한다고 명시하므로, 5G 사용자와 유선 인터넷 사용자와 Direct Connect 스튜디오를 한 배치로 받을 수 있습니다. 활성화 자체에는 추가 요금이 없지만 Local Zone의 리소스 가격이 부모 리전과 다르다는 점을 비용 계산에 넣어야 합니다. 다만 Local Zone별로 제공되는 서비스가 다르므로 EC2와 EBS를 넘어서는 서비스는 대상 zone의 지원 여부를 따로 확인해야 합니다.

- A가 틀린 이유: Outposts는 고객이 확보하고 관리하는 시설에 AWS 하드웨어를 설치하는 형태라 시설을 직접 관리하지 않겠다는 요건과 어긋난다. local gateway도 온프레미스 네트워크 연결용이지 인터넷 사용자 수용 경로가 아니다.
- B가 틀린 이유: carrier gateway는 통신사 네트워크에서 오는 inbound 트래픽과 인터넷으로 나가는 outbound를 다루지만 일반 인터넷에서 Wavelength Zone으로 직접 inbound 연결을 제공하지 않는다. 일부 파트너의 fixed wireless access는 별도 조건이라 일반 유선 인터넷 사용자를 받을 수 있다는 근거가 되지 않는다.
- D가 틀린 이유: Global Accelerator는 AWS 글로벌 네트워크 진입점을 앞당기지만 컴퓨트가 여전히 부모 리전에 있어 물리 거리에서 오는 지연을 제거하지 못한다.

</details>

---

## 26. Reference

- [AWS Snowball - AWS Snowball Edge availability change](https://docs.aws.amazon.com/snowball/latest/developer-guide/snowball-edge-availability-change.html)
- [AWS Snowball - Differences between Snowball Edge device options](https://docs.aws.amazon.com/snowball/latest/developer-guide/device-differences.html)
- [AWS Snowball - AWS Snowball FAQs](https://aws.amazon.com/snowball/faqs/)
- [AWS Storage Blog - AWS Snow device updates](https://aws.amazon.com/blogs/storage/aws-snow-device-updates/)
- [AWS Data Transfer Terminal - What is AWS Data Transfer Terminal?](https://docs.aws.amazon.com/datatransferterminal/latest/userguide/what-is-dtt.html)
- [AWS DataSync - AWS DataSync quotas](https://docs.aws.amazon.com/datasync/latest/userguide/datasync-limits.html)
- [AWS DataSync - Planning your large-scale migration timeline](https://docs.aws.amazon.com/datasync/latest/userguide/datasync-large-migration-timelines.html)
- [AWS DataSync - AWS DataSync agent requirements](https://docs.aws.amazon.com/datasync/latest/userguide/agent-requirements.html)
- [AWS DataSync - Do I need an AWS DataSync agent?](https://docs.aws.amazon.com/datasync/latest/userguide/do-i-need-datasync-agent.html)
- [AWS DataSync - Choosing a task mode](https://docs.aws.amazon.com/datasync/latest/userguide/choosing-task-mode.html)
- [AWS DataSync - Where can I transfer my data with AWS DataSync?](https://docs.aws.amazon.com/datasync/latest/userguide/working-with-locations.html)
- [AWS DataSync - Choosing a service endpoint](https://docs.aws.amazon.com/datasync/latest/userguide/choose-service-endpoint.html)
- [AWS DataSync - Configuring bandwidth throttling](https://docs.aws.amazon.com/datasync/latest/userguide/configure-bandwidth.html)
- [Amazon S3 - Configuring fast, secure file transfers using Transfer Acceleration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html)
- [Amazon S3 - Best practices design patterns: optimizing Amazon S3 performance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance-guidelines.html)
- [Amazon S3 - Uploading and copying objects using multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [Amazon S3 - Amazon S3 multipart upload limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)
- [AWS Transfer Family - What is AWS Transfer Family?](https://docs.aws.amazon.com/transfer/latest/userguide/what-is-aws-transfer-family.html)
- [AWS Transfer Family - Create a server in a virtual private cloud](https://docs.aws.amazon.com/transfer/latest/userguide/create-server-in-vpc.html)
- [AWS Transfer Family - Security policies for AWS Transfer Family servers](https://docs.aws.amazon.com/transfer/latest/userguide/security-policies.html)
- [AWS General Reference - AWS Transfer Family endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/transfer-service.html)
- [AWS Storage Gateway - What is AWS Storage Gateway?](https://docs.aws.amazon.com/storagegateway/latest/vgw/WhatIsStorageGateway.html)
- [AWS Storage Gateway - Using the Storage Gateway Hardware Appliance](https://docs.aws.amazon.com/storagegateway/latest/vgw/hardware-appliance.html)
- [AWS Storage Gateway - Volume Gateway quotas](https://docs.aws.amazon.com/storagegateway/latest/vgw/resource-gateway-limits.html)
- [AWS Storage Gateway - What is Tape Gateway?](https://docs.aws.amazon.com/storagegateway/latest/tgw/WhatIsStorageGateway.html)
- [AWS Storage Gateway - Tape Gateway quotas](https://docs.aws.amazon.com/storagegateway/latest/tgw/resource-gateway-limits.html)
- [Amazon S3 File Gateway - S3 File Gateway quotas](https://docs.aws.amazon.com/filegateway/latest/files3/fgw-quotas.html)
- [Amazon S3 File Gateway - Setting up Amazon S3 File Gateway](https://docs.aws.amazon.com/filegateway/latest/files3/Requirements.html)
- [Amazon S3 File Gateway - Refreshing the Amazon S3 bucket object cache](https://docs.aws.amazon.com/filegateway/latest/files3/refresh-cache.html)
- [Amazon FSx File Gateway - Setting up Amazon FSx File Gateway](https://docs.aws.amazon.com/filegateway/latest/filefsxw/Requirements.html)
- [AWS Outposts - What is AWS Outposts?](https://docs.aws.amazon.com/outposts/latest/userguide/what-is-outposts.html)
- [AWS Outposts - How AWS Outposts works](https://docs.aws.amazon.com/outposts/latest/userguide/how-outposts-works.html)
- [AWS Outposts - What is AWS Outposts servers?](https://docs.aws.amazon.com/outposts/latest/server-userguide/what-is-outposts.html)
- [AWS Outposts - AWS Outposts racks network requirements](https://docs.aws.amazon.com/outposts/latest/network-userguide/what-is-outposts.html)
- [Amazon Route 53 - What is Amazon Route 53 on Outposts?](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/outpost-resolver.html)
- [Amazon S3 - Using Amazon S3 on Outposts](https://docs.aws.amazon.com/AmazonS3/latest/userguide/S3onOutposts.html)
- [Amazon S3 - S3 on Outposts restrictions and limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/S3OnOutpostsRestrictionsLimitations.html)
- [Amazon EC2 - Regions, Availability Zones, Local Zones, and Wavelength Zones](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html)
- [AWS Local Zones - What is AWS Local Zones?](https://docs.aws.amazon.com/local-zones/latest/ug/what-is-aws-local-zones.html)
- [AWS Local Zones - Available Local Zones](https://docs.aws.amazon.com/local-zones/latest/ug/available-local-zones.html)
- [AWS Local Zones - How AWS Local Zones work](https://docs.aws.amazon.com/local-zones/latest/ug/how-local-zones-work.html)
- [AWS Wavelength - How AWS Wavelength works](https://docs.aws.amazon.com/wavelength/latest/developerguide/how-wavelengths-work.html)
- [AWS Wavelength - Available Wavelength Zones](https://docs.aws.amazon.com/wavelength/latest/developerguide/available-wavelength-zones.html)
- [Amazon ElastiCache - Using Local Zones with ElastiCache](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Local_zones.html)
- [AWS Direct Connect - Hosted connections](https://docs.aws.amazon.com/directconnect/latest/UserGuide/hosted_connection.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
