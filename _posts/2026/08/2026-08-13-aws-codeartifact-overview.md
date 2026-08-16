---
title: "AWS CodeArtifact Overview - 프라이빗 패키지 저장소 구조와 보안"
date: 2026-08-13 14:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, codeartifact, package, registry, npm, pypi, maven, supply-chain, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

npm install로 lodash를 설치하는데 갑자기 404가 떨어진다. npmjs.com에서 패키지가 삭제됐거나 maintainer가 계정을 바꿨을 수 있다. 실제로 2016년 left-pad 사건처럼 단일 패키지 삭제가 수천 개 프로젝트의 빌드를 멈춘 사례가 있다. 팀이 internal하게 공유하는 사내 패키지는 공개 registry에 올릴 수 없고, public 패키지와 private 패키지를 같은 빌드에서 사용하려면 두 개의 registry를 오가야 한다.

AWS CodeArtifact는 이 문제를 풀기 위한 fully managed artifact repository service입니다. private 패키지를 저장하고, public registry를 proxy하고, npm, pip, Maven, NuGet, RubyGems, Cargo, Swift를 하나의 repository에서 처리합니다. 패키지 개수나 총 크기에 제한이 없으며, 자체 artifact 서버를 운영할 필요가 없습니다.

> **TL;DR**  
> - Domain이 KMS 암호화와 asset 중복 제거를 맡고 그 아래 repository가 패키지를 담는다. 하나의 repository는 polyglot이라 npm, PyPI, Maven을 함께 넣을 수 있다.  
> - External connection으로 public registry 10곳을 proxy하며, 이때 자동 생성되는 `-store` repository를 거친다. **public에서 fetch하는 요청도 request 과금에 포함된다.**  
> - Package origin controls가 dependency confusion을 막고, 원본 publish timestamp가 보존되므로 갓 올라온 버전을 거르는 quarantine window를 CI에 걸 수 있다.  
> - **서울(ap-northeast-2)은 지원 리전 13곳에 없고** cross-region 복제도 없다. CodeCommit과 달리 deprecation 발표는 없으며 Swift와 Cargo 지원이 최근 추가됐다.  
{: .prompt-info}

---

## 1. Domain과 Repository: 두 계층으로 구성된 저장 구조

CodeArtifact는 저장을 Domain이라는 상위 entity로 관리합니다. Domain은 KMS key로 모든 asset을 암호화하고, 동일한 asset은 domain 내에 한 번만 저장합니다(deduplication). 계정당 최대 10개 domain을 만들 수 있고, domain당 최대 1,000개 repository를 가질 수 있습니다.

Repository는 패키지를 publish하고 fetch하는 논리적 단위입니다. 하나의 repository는 polyglot입니다. npm 패키지와 Python 패키지, Maven artifact를 같은 repository에 넣을 수 있습니다. Repository는 반드시 하나의 domain에 속하며, 다른 domain으로 이동할 수 없습니다.

Domain administrator는 domain policy를 통해 다른 AWS 계정의 접근을 제어할 수 있습니다. `PutDomainPermissionsPolicy` API로 resource-based policy를 설정하고, AWS RAM(Resource Access Manager)을 통해 cross-account 공유를 구성합니다.

---

## 2. Upstream repository와 External connection으로 패키지 접근 범위를 확장합니다

Repository는 upstream repository를 연결해 패키지 접근 범위를 확장합니다. downstream repository의 endpoint에서 upstream에 있는 패키지 버전에 접근할 수 있으며, direct upstream은 repository당 최대 10개, 검색 대상 upstream은 최대 25개까지 설정할 수 있습니다.

External connection은 CodeArtifact repository와 public registry를 연결합니다. 다음 10개 public registry를 proxy할 수 있습니다.

| Public Registry | Store Repository |
| :--- | :--- |
| npmjs.com | npm-store |
| Maven Central | maven-central-store |
| PyPI | pypi-store |
| NuGet Gallery (nuget.org) | nuget-store |
| RubyGems.org | rubygems-store |
| crates.io | cargo-store |
| Clojars | clojars-store |
| CommonsWare Android | commonsware-store |
| Google Android | google-android-store |
| Gradle plugins | gradle-plugins-store |

External connection을 추가하면 중간에 `-store` repository가 자동으로 생성되고 upstream으로 연결됩니다. 패키지는 on-demand로 fetch되어 CodeArtifact에 저장됩니다. public registry에서 패키지를 fetch하는 요청도 request 과금에 포함됩니다.

---

## 3. 패키지 매니저 연동

CodeArtifact는 `aws codeartifact login` 명령으로 주요 패키지 매니저의 인증을 한 번에 설정할 수 있습니다.

```bash
aws codeartifact login \
  --tool npm \
  --domain my-domain \
  --repository my-repo \
  --domain-owner 123456789012
```

npm, pip, twine, dotnet, nuget, swift를 지원합니다. 각 매니저별 요구사항은 다음과 같습니다.

| 패키지 매니저 | 버전 요구사항 | 비고 |
| :--- | :--- | :--- |
| npm | Node.js v4.9.1+, npm v5.0.0+ | Yarn 호환 |
| pip/twine | Python 호환 | pip(설치), twine(publish) |
| Maven | Maven 3.6.3, Gradle 6.4.1 | Clojure, SBT, curl 호환 |
| NuGet | NuGet.exe 4.8+, dotnet CLI | Visual Studio 호환 |
| RubyGems | Ruby 3.3+ 권장 | Ruby 2.6 이하 미지원, Bundler 호환 |
| Cargo | Rust | crates.io proxy 지원 |
| Swift | Swift | 최근 추가 |

---

## 4. 인증: AWS credential에서 authorization token까지

CodeArtifact 인증은 AWS credential 기반으로 동작합니다. `GetAuthorizationToken` API를 호출하면 authorization token이 발급되고, 이 token을 패키지 매니저의 설정에 등록합니다.

Token의 기본 유효기간은 12시간이며, 15분부터 12시간까지 설정할 수 있습니다. Root user는 `GetAuthorizationToken`을 호출할 수 없으며, IAM 사용자나 역할을 사용해야 합니다. 필요한 IAM 권한은 `sts:GetServiceBearerToken`과 `codeartifact:GetAuthorizationToken`입니다.

CI/CD 환경에서는 token 갱신 전략이 중요합니다. `--duration-seconds 0`을 설정하면 assumed role의 남은 session 시간과 token 유효기간이 자동으로 일치합니다. Token 발급 요청은 계정당 초당 40회까지 가능하며(조정 가능), 단일 token으로 초당 1,200회 요청을 처리할 수 있습니다(조정 불가).

---

## 5. 보안: 암호화, 접근 제어, Dependency Confusion 방어

CodeArtifact의 보안은 여러 계층으로 구성됩니다.

**암호화**: 모든 asset과 metadata는 domain 단위로 AWS KMS key로 암호화됩니다. 전송 계층에서는 TLS 1.2를 요구하고 TLS 1.3을 권장하며, FIPS 140-3 validated endpoint를 지원합니다.

**Dependency Confusion 방어**: Package origin controls는 공격자가 public registry에 악성 패키지를 올려 private 패키지 이름을 가장하는 dependency substitution attack을 방어합니다. 첫 패키지 버전이 직접 publish되면 자동으로 `Publish:Allow, Upstream:Block`으로 설정되고, external connection에서 ingest되면 `Publish:Block, Upstream:Allow`로 설정됩니다. Package group을 사용하면 여러 패키지에 origin control을 일괄 적용할 수 있습니다.

**Version age gating**: CodeArtifact는 원본 upstream publish timestamp를 보존합니다. CI/CD 파이프라인에서 최근에 publish된 버전을 reject하는 quarantine window(3~7일 권장)를 설정해, 갓 publish된 악성 패키지가 빌드에 유입되는 것을 막을 수 있습니다. Yarn 4, Renovate, pnpm의 `minimumReleaseAge` 설정이 CodeArtifact와 수정 없이 호환됩니다.

**감사**: CloudTrail로 모든 API 호출과 사용자 활동을 추적할 수 있습니다. 패키지는 인증 없이 접근할 수 없으므로, 공개(publicly available) 상태로 만들 수 없습니다.

---

## 6. 과금 구조

CodeArtifact는 세 가지 차원으로 과금됩니다. Storage(GB/month), Requests(10,000건 단위), Data Transfer Out(리전 외부 전송)입니다. upfront fee나 commitment 없이 pay-as-you-go로 동작하며, Free Tier가 포함되어 있습니다.

같은 리전 내 AWS 서비스 간 데이터 전송은 무료이고, 인터넷에서 CodeArtifact로 들어오는 데이터 전송도 무료입니다. 공개 registry에서 패키지를 fetch하는 요청도 request count에 포함되므로, external connection을 많이 사용하면 request 비용이 증가합니다.

정확한 단가는 리전별로 다르며, AWS 프라이싱 캘큘레이터에서 확인해야 합니다.

---

## 7. 서울 리전 미지원과 대안

CodeArtifact는 13개 리전에서 사용할 수 있습니다. us-east-1, us-east-2, us-west-2, ap-south-1, ap-southeast-1, ap-southeast-2, ap-northeast-1, eu-central-1, eu-west-1, eu-west-2, eu-south-1, eu-west-3, eu-north-1입니다.

**서울(ap-northeast-2)은 지원 리전에 포함되어 있지 않습니다.** 한국 리전에서 서비스를 운영하는 조직은 ap-northeast-1(Tokyo)을 사용해야 합니다. 이 경우 cross-region data transfer 비용과 latency를 고려해야 합니다. CodeArtifact는 cross-region 복제를 지원하지 않으므로, 리전별로 별도 repository를 운영해야 합니다.

---

## 8. CodeArtifact는 폐지되는가

CodeCommit의 새 고객 가입 중단이 2024년에 발표되면서, CodeArtifact에 대한 deprecation 우려가 나왔습니다. CodeArtifact는 CodeCommit과 다른 서비스이며, deprecation 발표가 없습니다. 제품 페이지가 정상 운영 중이고, Swift와 Cargo 지원이 최근에 추가되었습니다.

다만 FAQ 페이지가 정리되었고 AWS 블로그에서의 CodeArtifact 관련 글이 2021년 이후 줄어든 점은 서비스 운영 전략의 변화를 시사합니다. 도입을 검토할 때는 이 점을 고려하되, 현재 서비스가 중단된 것은 아니라는 점이 확인되었습니다.

---

## 9. 경쟁사 비교

| 항목 | CodeArtifact | GitHub Packages | JFrog Artifactory | Sonatype Nexus |
| :--- | :--- | :--- | :--- | :--- |
| 관리 형태 | Fully managed (AWS) | Managed (GitHub) | Self-hosted / Cloud | Self-hosted / Cloud |
| 지원 포맷 | npm, PyPI, Maven, NuGet, RubyGems, Cargo, Swift, generic | npm, Maven, NuGet, RubyGems, Docker | 30+ 포맷 | npm, PyPI, Maven, NuGet, Docker, Helm |
| Public proxy | 10개 registry | npmjs (제한적) | 모든 public registry | 모든 public registry |
| 인증 | AWS IAM + token | GitHub PAT | Native / Access Token | Native / OIDC |
| AWS 통합 | KMS, IAM, RAM, EventBridge, CloudTrail | 없음 | S3 back-end | 없음 |
| Multi-region | 리전별 별도 (복제 미지원) | 글로벌 | 설정 가능 | 수동 |

CodeArtifact는 AWS 인프라에 이미 투자한 조직, IAM 기반 접근 제어가 필요한 경우, CI/CD 파이프라인이 AWS 내에 있는 경우에 적합합니다. Docker 이미지 저장, 30개 이상 포맷 지원, 복잡한 라우팅 규칙이 필요하면 JFrog Artifactory를 검토하는 것이 낫습니다.

---

## 10. Service Quotas 주요 항목

| Quota | 기본값 | 조정 가능 |
| :--- | :--- | :--- |
| Asset file size | 5 GB | Yes |
| Assets per package version | 350 | No |
| Direct upstreams per repository | 10 | No |
| Domains per AWS account | 10 | Yes |
| Repositories per domain | 1,000 | Yes |
| Read requests/s (single account) | 800 | Yes |
| Write requests/s (single account) | 100 | Yes |
| Requests/s (single auth token) | 1,200 | No |
| GetAuthorizationToken requests/s | 40 | Yes |

---

## 11. Reference

- [AWS CodeArtifact User Guide - Welcome](https://docs.aws.amazon.com/codeartifact/latest/ug/welcome.html)
- [AWS CodeArtifact Concepts](https://docs.aws.amazon.com/codeartifact/latest/ug/codeartifact-concepts.html)
- [AWS CodeArtifact Authentication and Tokens](https://docs.aws.amazon.com/codeartifact/latest/ug/tokens-authentication.html)
- [AWS CodeArtifact Domain Overview](https://docs.aws.amazon.com/codeartifact/latest/ug/domain-overview.html)
- [AWS CodeArtifact External Connections](https://docs.aws.amazon.com/codeartifact/latest/ug/external-connection.html)
- [AWS CodeArtifact Package Origin Controls](https://docs.aws.amazon.com/codeartifact/latest/ug/package-origin-controls.html)
- [AWS CodeArtifact Package Groups](https://docs.aws.amazon.com/codeartifact/latest/ug/package-groups.html)
- [AWS CodeArtifact Version Age Gating](https://docs.aws.amazon.com/codeartifact/latest/ug/package-version-age-gating.html)
- [AWS CodeArtifact Data Protection](https://docs.aws.amazon.com/codeartifact/latest/ug/data-protection.html)
- [AWS CodeArtifact Endpoints and Quotas](https://docs.aws.amazon.com/general/latest/gr/codeartifact.html)
- [AWS CodeArtifact Product Page](https://aws.amazon.com/codeartifact/)
- [AWS CodeArtifact Pricing](https://aws.amazon.com/codeartifact/pricing/)
- [AWS CodeArtifact Blog Posts](https://aws.amazon.com/blogs/devops/tag/codeartifact/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
