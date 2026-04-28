---
# the default layout is 'page'
icon: fas fa-info-circle
order: 4
---

<style>
  /* ===== Tokens ===== */
  :root {
    --cv-border: var(--main-border-color, #d8dee4);
    --cv-border-strong: var(--text-muted-color, #6a737d);
    --cv-muted: var(--text-muted-color, #6a737d);
    --cv-card-bg: transparent;
    --cv-icon-warm: #c47e6e;
    --cv-icon-amber: #c89b3c;
    --cv-icon-khaki: #b48a5a;
    --cv-radius-sm: 4px;
    --cv-radius-md: 6px;
    --cv-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --cv-transition: 140ms ease;
  }

  /* ===== Section header ===== */
  h2.cv-h2 {
    margin-top: 2.4rem !important;
    margin-bottom: 1rem !important;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--cv-border);
    line-height: 1.25;
  }

  h2.cv-h2 i {
    color: var(--cv-icon-warm);
    font-size: 0.85em;
    margin-right: 0.35rem;
  }

  /* ===== Hero ===== */
  .cv-hero {
    display: grid;
    grid-template-columns: minmax(150px, 210px) 1fr;
    gap: 1.5rem;
    align-items: center;
    margin-bottom: 2.2rem;
  }

  .cv-hero img {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: var(--cv-radius-md);
    border: 1px solid var(--cv-border);
  }

  .cv-hero h1 {
    margin: 0;
    font-size: 2rem;
    line-height: 1.15;
  }

  .cv-role {
    margin: 0.3rem 0 0.85rem;
    color: var(--cv-muted);
    font-size: 1rem;
  }

  .cv-bio {
    margin: 0.5rem 0 0;
    font-size: 0.95rem;
  }

  .cv-contact {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.85rem;
    align-items: center;
  }

  .cv-contact a {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    border: 1px solid var(--cv-border);
    border-radius: var(--cv-radius-sm);
    padding: 0.28rem 0.6rem;
    font-size: 0.86rem;
    line-height: 1.35;
    color: inherit;
    text-decoration: none;
    transition: var(--cv-transition);
  }

  .cv-contact a:hover {
    border-color: var(--cv-border-strong);
  }

  /* ===== Summary cards ===== */
  .cv-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
    margin: 1rem 0 1.8rem;
  }

  .cv-summary-card {
    border: 1px solid var(--cv-border);
    border-radius: var(--cv-radius-md);
    padding: 0.9rem 1rem;
  }

  .cv-summary-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
    margin-bottom: 0.3rem;
  }

  .cv-summary-title i {
    color: var(--cv-icon-warm);
    font-size: 0.9em;
  }

  .cv-summary-grid > .cv-summary-card:nth-child(1) .cv-summary-title i { color: var(--cv-icon-amber); }
  .cv-summary-grid > .cv-summary-card:nth-child(3) .cv-summary-title i { color: var(--cv-icon-khaki); }

  .cv-muted {
    color: var(--cv-muted);
    font-size: 0.9rem;
  }

  /* ===== Skill cloud ===== */
  .cv-skill-cloud {
    display: grid;
    gap: 0.85rem;
    margin: 0.6rem 0 1.6rem;
  }

  .cv-skill-group {
    display: grid;
    grid-template-columns: minmax(180px, 220px) 1fr;
    gap: 0.8rem;
    align-items: start;
  }

  .cv-skill-label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
    padding-top: 0.25rem;
  }

  .cv-skill-label i {
    color: var(--cv-muted);
    font-size: 0.9em;
  }

  .cv-chip-cloud {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .cv-chip {
    border: 1px solid var(--cv-border);
    border-radius: 4px;
    padding: 0.14rem 0.5rem;
    font-size: 0.8rem;
    line-height: 1.4;
    color: var(--cv-muted);
    background: transparent;
  }

  /* ===== Timeline ===== */
  .cv-timeline {
    list-style: none;
    margin: 0.6rem 0 1.4rem;
    padding: 0 0 0 1.2rem;
    border-left: 2px solid var(--cv-border);
  }

  .cv-timeline-item {
    position: relative;
    padding: 0 0 1.4rem 0.9rem;
  }

  .cv-timeline-item:last-child {
    padding-bottom: 0.2rem;
  }

  .cv-timeline-item::before {
    content: '';
    position: absolute;
    left: -1.55rem;
    top: 0.55rem;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--cv-border);
  }

  .cv-timeline-item.is-current::before {
    background: var(--cv-muted);
  }

  .cv-timeline-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.45rem;
  }

  .cv-timeline-title {
    font-size: 1.08rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.3;
  }

  .cv-timeline-title small {
    color: var(--cv-muted);
    font-weight: 500;
    font-size: 0.92rem;
    margin-left: 0.35rem;
  }

  .cv-period {
    font-family: var(--cv-mono);
    font-size: 0.78rem;
    color: var(--cv-muted);
    white-space: nowrap;
  }

  .cv-timeline-body ul {
    margin: 0.25rem 0 0;
    padding-left: 1.15rem;
  }

  .cv-timeline-body li {
    margin: 0.15rem 0;
  }

  /* ===== Card grid ===== */
  .cv-card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 0.95rem;
    margin: 0.4rem 0 1.6rem;
  }

  .cv-card {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--cv-border);
    border-radius: var(--cv-radius-md);
    padding: 1rem 1.05rem;
    background: var(--cv-card-bg);
  }

  .cv-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.3rem;
  }

  .cv-card-title {
    font-weight: 700;
    font-size: 1.05rem;
    margin: 0;
    line-height: 1.3;
  }

  .cv-card-links {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
  }

  .cv-card-links a {
    color: var(--cv-muted);
    text-decoration: none;
    transition: var(--cv-transition);
  }

  .cv-card-links a:hover {
    color: inherit;
  }

  .cv-card-meta {
    color: var(--cv-muted);
    font-size: 0.85rem;
    margin-bottom: 0.55rem;
    font-family: var(--cv-mono);
  }

  .cv-card-desc {
    margin: 0 0 0.55rem;
    font-size: 0.95rem;
  }

  .cv-card ul:not(.cv-card-tech) {
    margin: 0 0 0.7rem;
    padding-left: 1.15rem;
    font-size: 0.92rem;
  }

  .cv-card ul:not(.cv-card-tech) li {
    margin: 0.15rem 0;
  }

  .cv-card-tech {
    list-style: none;
    margin: auto 0 0;
    padding: 0.6rem 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
    border-top: 1px dashed var(--cv-border);
  }

  .cv-card-tech .cv-chip {
    font-size: 0.74rem;
    padding: 0.1rem 0.5rem;
  }

  /* ===== Mini card (Personal Projects) ===== */
  .cv-mini-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.7rem;
    margin: 0.5rem 0 1.4rem;
  }

  .cv-mini-card {
    display: block;
    border: 1px solid var(--cv-border);
    border-radius: var(--cv-radius-md);
    padding: 0.7rem 0.9rem;
    text-decoration: none;
    color: inherit;
    transition: var(--cv-transition);
  }

  .cv-mini-card:hover {
    border-color: var(--cv-border-strong);
  }

  .cv-mini-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
  }

  .cv-mini-title i {
    color: var(--cv-muted);
    font-size: 0.85em;
  }

  .cv-mini-desc {
    color: var(--cv-muted);
    font-size: 0.85rem;
    line-height: 1.45;
    margin: 0;
  }

  /* ===== Certifications (row list) ===== */
  .cv-cert-grid {
    list-style: none;
    margin: 0.5rem 0 1.4rem;
    padding: 0;
  }

  .cv-cert {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.5rem 0.2rem;
    border-bottom: 1px solid var(--cv-border);
  }

  .cv-cert:last-child {
    border-bottom: none;
  }

  .cv-cert-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--cv-muted);
  }

  .cv-cert-dot.aws { background: #ff9900; }
  .cv-cert-dot.hashicorp { background: #7b42bc; }
  .cv-cert-dot.kubernetes { background: #326ce5; }
  .cv-cert-dot.kr { background: #34a853; }

  .cv-cert-body {
    flex: 1;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.6rem;
    min-width: 0;
  }

  .cv-cert-name {
    font-weight: 500;
    font-size: 0.95rem;
    line-height: 1.3;
  }

  .cv-cert-meta {
    color: var(--cv-muted);
    font-size: 0.78rem;
    font-family: var(--cv-mono);
    white-space: nowrap;
  }

  /* ===== OSS contributions ===== */
  .cv-oss-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 0.7rem;
    margin: 0.5rem 0 1.4rem;
  }

  .cv-oss {
    display: block;
    border: 1px solid var(--cv-border);
    border-radius: var(--cv-radius-md);
    padding: 0.85rem 1rem;
    text-decoration: none;
    color: inherit;
    transition: var(--cv-transition);
  }

  .cv-oss:hover {
    border-color: var(--cv-border-strong);
  }

  .cv-oss-head {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-weight: 600;
    margin-bottom: 0.3rem;
  }

  .cv-oss-head i { color: var(--cv-muted); }

  .cv-oss-pr {
    color: var(--cv-muted);
    font-family: var(--cv-mono);
    font-size: 0.78rem;
    margin-left: auto;
  }

  .cv-oss-desc {
    color: var(--cv-muted);
    font-size: 0.9rem;
    line-height: 1.5;
    margin: 0;
  }

  /* ===== Awards ===== */
  .cv-awards {
    list-style: none;
    margin: 0.5rem 0 1.4rem;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .cv-award {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0.2rem;
    border-bottom: 1px solid var(--cv-border);
  }

  .cv-award:last-child {
    border-bottom: none;
  }

  .cv-award-icon {
    color: #c89b3c;
    flex-shrink: 0;
    width: 1.1rem;
    text-align: center;
    font-size: 0.95em;
  }

  .cv-award.silver .cv-award-icon {
    color: #9aa5b1;
  }

  .cv-award-text {
    flex: 1;
    font-size: 0.95rem;
  }

  .cv-award-date {
    font-family: var(--cv-mono);
    font-size: 0.8rem;
    color: var(--cv-muted);
    white-space: nowrap;
  }

  /* ===== Activities (row list) ===== */
  .cv-activities {
    list-style: none;
    margin: 0.5rem 0 1.4rem;
    padding: 0;
  }

  .cv-activity {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.5rem 0.2rem;
    border-bottom: 1px solid var(--cv-border);
    font-size: 0.92rem;
  }

  .cv-activity:last-child {
    border-bottom: none;
  }

  .cv-activity::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--cv-muted);
    flex-shrink: 0;
  }

  .cv-activity.speaker::before { background: var(--cv-icon-amber); }
  .cv-activity.staff::before { background: var(--cv-icon-khaki); }

  .cv-activity-text {
    flex: 1;
    line-height: 1.45;
  }

  .cv-activity-role {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--cv-muted);
    border: 1px solid var(--cv-border);
    padding: 0.02rem 0.4rem;
    border-radius: 4px;
    margin-right: 0.4rem;
    vertical-align: middle;
  }

  .cv-activity-date {
    font-family: var(--cv-mono);
    font-size: 0.78rem;
    color: var(--cv-muted);
    white-space: nowrap;
  }

  /* ===== Responsive ===== */
  @media (max-width: 860px) {
    .cv-skill-group {
      grid-template-columns: 1fr;
      gap: 0.35rem;
    }
  }

  @media (max-width: 720px) {
    .cv-hero {
      grid-template-columns: 1fr;
    }

    .cv-hero img {
      max-width: 280px;
    }

    .cv-timeline-head {
      flex-direction: column;
      align-items: flex-start;
    }
  }

  /* ===== Print ===== */
  @media print {
    .cv-card:hover,
    .cv-cert:hover,
    .cv-award:hover,
    .cv-summary-card:hover,
    .cv-mini-card:hover,
    .cv-oss:hover,
    .cv-contact a:hover {
      transform: none;
      box-shadow: none;
    }

    .cv-hero img { box-shadow: none; }
    h2.cv-h2 { break-after: avoid; }

    .cv-card,
    .cv-cert,
    .cv-summary-card,
    .cv-oss,
    .cv-mini-card,
    .cv-timeline-item {
      break-inside: avoid;
    }

    a {
      text-decoration: none;
      color: inherit;
    }
  }
</style>

<section class="cv-hero">
  <img src="/assets/img/kkam-img/kcd_2025.jpg" alt="Taeji Kim profile photo">
  <div>
    <h1>Taeji Kim</h1>
    <p class="cv-role">SRE / DevSecOps Engineer</p>
    <p class="cv-bio">
      AWS, Kubernetes, IaC, CI/CD, Observability, Security 영역을 함께 다루며
      운영 가능한 플랫폼과 반복 가능한 인프라를 만드는 데 집중합니다.
      장애 대응과 RCA, 자동화, 비용 최적화, 인증/인가 체계 개선 경험을 기반으로
      서비스 신뢰성과 운영 효율을 높이는 일을 지향합니다.
    </p>
    <div class="cv-contact">
      <a href="mailto:xowl5460@naver.com"><i class="fas fa-envelope fa-fw"></i> xowl5460@naver.com</a>
      <a href="https://kkamji.net"><i class="fas fa-blog fa-fw"></i> Blog</a>
      <a href="https://github.com/KKamJi98"><i class="fab fa-github fa-fw"></i> GitHub</a>
      <a href="https://linkedin.com/in/taejikim"><i class="fab fa-linkedin fa-fw"></i> LinkedIn</a>
    </div>
  </div>
</section>

## <i class="fas fa-user fa-fw"></i> Profile
{: #profile .cv-h2}

Cloud Native 환경에서 운영, 배포, 보안, 관측 가능성을 연결해 서비스 신뢰성을 개선하는 엔지니어입니다. 현재는 번개장터에서 서비스 운영 및 고도화를 담당하며, EKS Upgrade, Terraform 모듈화, AWS 인프라 프로비저닝, Grafana / Datadog Dashboard, Packer 기반 Golden Image 자동화, 사내 장애대응 AI Agent, 백신 PoC, AWS 인증 방식 전환 등 운영 플랫폼의 안정성과 보안성을 개선하고 있습니다.

<div class="cv-summary-grid">
  <div class="cv-summary-card">
    <div class="cv-summary-title"><i class="fas fa-layer-group fa-fw"></i> Platform Operations</div>
    <span class="cv-muted">AWS Infra, EKS Upgrade, Terraform IaC, Packer, Golden Image</span>
  </div>
  <div class="cv-summary-card">
    <div class="cv-summary-title"><i class="fas fa-heart-pulse fa-fw"></i> Reliability</div>
    <span class="cv-muted">Incident Response, RCA Guide, Grafana, Datadog, AI Agent</span>
  </div>
  <div class="cv-summary-card">
    <div class="cv-summary-title"><i class="fas fa-shield-halved fa-fw"></i> Security &amp; Automation</div>
    <span class="cv-muted">Access Key Removal, Security Group, ClamAV, RBAC, CI/CD</span>
  </div>
</div>

## <i class="fas fa-toolbox fa-fw"></i> Skill Set
{: #skill-set .cv-h2}

<div class="cv-skill-cloud">
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-cloud fa-fw"></i> Cloud / Infra</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">AWS</li>
      <li class="cv-chip">EC2</li>
      <li class="cv-chip">EKS</li>
      <li class="cv-chip">ECS</li>
      <li class="cv-chip">ECR</li>
      <li class="cv-chip">RDS</li>
      <li class="cv-chip">VPC</li>
      <li class="cv-chip">Route 53</li>
      <li class="cv-chip">CloudFront</li>
      <li class="cv-chip">CloudWatch</li>
      <li class="cv-chip">Lambda</li>
      <li class="cv-chip">API Gateway</li>
      <li class="cv-chip">WAF</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-dharmachakra fa-fw"></i> Kubernetes / Platform</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Kubernetes</li>
      <li class="cv-chip">EKS</li>
      <li class="cv-chip">Helm</li>
      <li class="cv-chip">Karpenter</li>
      <li class="cv-chip">HPA</li>
      <li class="cv-chip">IRSA</li>
      <li class="cv-chip">Cilium</li>
      <li class="cv-chip">Hubble</li>
      <li class="cv-chip">Gateway API</li>
      <li class="cv-chip">Envoy</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-code-branch fa-fw"></i> IaC / CI&#47;CD</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Terraform</li>
      <li class="cv-chip">HCP Terraform</li>
      <li class="cv-chip">Packer</li>
      <li class="cv-chip">Jenkins</li>
      <li class="cv-chip">GitHub Actions</li>
      <li class="cv-chip">Argo CD</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-chart-line fa-fw"></i> Observability / Data</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Prometheus</li>
      <li class="cv-chip">Grafana</li>
      <li class="cv-chip">Datadog</li>
      <li class="cv-chip">Thanos</li>
      <li class="cv-chip">ELK</li>
      <li class="cv-chip">CloudWatch Logs</li>
      <li class="cv-chip">InfluxDB</li>
      <li class="cv-chip">Apache Superset</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-shield-halved fa-fw"></i> Security / Identity</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Keycloak</li>
      <li class="cv-chip">SSO</li>
      <li class="cv-chip">RBAC</li>
      <li class="cv-chip">AWS IAM</li>
      <li class="cv-chip">Secrets Manager</li>
      <li class="cv-chip">Parameter Store</li>
      <li class="cv-chip">External Secrets</li>
      <li class="cv-chip">ClamAV</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-code fa-fw"></i> Programming / App</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Python</li>
      <li class="cv-chip">Go</li>
      <li class="cv-chip">Java</li>
      <li class="cv-chip">Spring Boot</li>
      <li class="cv-chip">Streamlit</li>
      <li class="cv-chip">React</li>
    </ul>
  </div>
  <div class="cv-skill-group">
    <div class="cv-skill-label"><i class="fas fa-server fa-fw"></i> OS / Runtime</div>
    <ul class="cv-chip-cloud">
      <li class="cv-chip">Ubuntu</li>
      <li class="cv-chip">Amazon Linux</li>
      <li class="cv-chip">CentOS</li>
      <li class="cv-chip">Docker</li>
    </ul>
  </div>
</div>

## <i class="fas fa-briefcase fa-fw"></i> Careers
{: #careers .cv-h2}

<ol class="cv-timeline">
  <li class="cv-timeline-item is-current">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">Bunjang <small>/ DevSecOps Engineer</small></h3>
      <span class="cv-period">2025.11 ~ 현재</span>
    </div>
    <div class="cv-timeline-body">
      <ul>
        <li>번개장터 서비스 운영 및 고도화</li>
        <li>EKS Upgrade 진행: Kubernetes 1.32 이상</li>
        <li>Terraform 모듈화 및 AWS 인프라 프로비저닝</li>
        <li>Grafana, Datadog Dashboards 구성</li>
        <li>ClamAV 서버 백신 PoC 및 도입</li>
        <li>Packer 도입 및 Golden Image 생성 자동화</li>
        <li>사내 장애대응 AI Agent 개발 및 도입</li>
        <li>Security Group Outbound Rule 최적화</li>
        <li>AWS 인증 방식 전환: Access Key 제거</li>
      </ul>
    </div>
  </li>
  <li class="cv-timeline-item">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">Warepoint <small>/ Technical Architect</small></h3>
      <span class="cv-period">2024.12 ~ 2025.10</span>
    </div>
    <div class="cv-timeline-body">
      <ul>
        <li>Samsung Galaxy Chatting Plus (RCS) 서비스 운영</li>
        <li>AWS Infra 구축 및 운영, Terraform 기반 IaC 적용</li>
        <li>EKS Cluster 운영 및 업그레이드</li>
        <li>서비스 장애 대응 및 근본 원인 분석(RCA) 가이드 작성</li>
        <li>GitHub Actions Matrix Strategy 도입으로 Multi-Architecture Container Image Build 시간 50% 이상 단축</li>
        <li>Apache Superset 구축, PoC, 운영</li>
        <li>Keycloak SSO + RBAC 적용: Grafana, Argo CD, Apache Superset</li>
        <li>InfluxDB(TSDB) 마이그레이션: Amazon Linux 2 → Ubuntu, EoS 대응</li>
        <li>Open-source Software 버전 업그레이드: Grafana, Prometheus, Thanos, External Secrets</li>
      </ul>
    </div>
  </li>
</ol>

## <i class="fab fa-github fa-fw"></i> Open-source Contributions
{: #open-source-contributions .cv-h2}

<div class="cv-oss-grid">
  <a class="cv-oss" href="https://github.com/aws-observability/helm-charts/pull/190" target="_blank" rel="noopener">
    <div class="cv-oss-head">
      <i class="fab fa-github"></i>
      <span>aws-observability/helm-charts</span>
      <span class="cv-oss-pr">PR #190</span>
    </div>
    <p class="cv-oss-desc">불필요한 리소스 생성을 제어할 수 있도록 <code>dcgmExporter.enabled</code>, <code>neuronMonitor.enabled</code> Flag 추가</p>
  </a>
  <a class="cv-oss" href="https://github.com/strands-agents/sdk-python/pull/1906" target="_blank" rel="noopener">
    <div class="cv-oss-head">
      <i class="fab fa-github"></i>
      <span>strands-agents/sdk-python</span>
      <span class="cv-oss-pr">PR #1906</span>
    </div>
    <p class="cv-oss-desc">README 내 깨진 Documentation Link 19개 수정. v1.35.0 Release New Contributors 항목 등재</p>
  </a>
</div>

## <i class="fas fa-diagram-project fa-fw"></i> Projects
{: #projects .cv-h2}

<div class="cv-card-grid">
  <article class="cv-card">
    <header class="cv-card-head">
      <h3 class="cv-card-title">Home Sweet Home</h3>
      <span class="cv-card-links">
        <span class="cv-period">2025.04</span>
      </span>
    </header>
    <p class="cv-card-meta">Infra · Frontend · Backend</p>
    <p class="cv-card-desc">청년 주택청약 알리미 Web App · Students @ AI - Seoul Hackathon Winner</p>
    <ul>
      <li>Streamlit 기반 사용자 Frontend UI 개발</li>
      <li>Bedrock Knowledge Base 기반 특정 청약 정보의 대화형 조회 구현</li>
      <li>로그 모니터링 기반 트러블슈팅</li>
    </ul>
    <ul class="cv-card-tech">
      <li class="cv-chip">Streamlit</li>
      <li class="cv-chip">AWS Bedrock</li>
      <li class="cv-chip">Knowledge Base</li>
    </ul>
  </article>

  <article class="cv-card">
    <header class="cv-card-head">
      <h3 class="cv-card-title">Remember Me</h3>
      <span class="cv-card-links">
        <a href="https://github.com/vocaAppServerless" target="_blank" rel="noopener" aria-label="GitHub"><i class="fab fa-github fa-lg"></i></a>
        <span class="cv-period">2024.11 ~ 2024.12</span>
      </span>
    </header>
    <p class="cv-card-meta">Infra · DevOps Lead</p>
    <p class="cv-card-desc">서버리스(AWS Lambda) 기반 영단어 암기 Web App</p>
    <ul>
      <li>Terraform(HCP Terraform) 기반 Cloud Infra IaC</li>
      <li>Lambda CI/CD Pipeline 구축</li>
      <li>CloudWatch Logs Subscription Filters + ELK Stack 기반 Lambda Logs 중앙화</li>
      <li>AWS Budgets, WAF Rule Event Slack Alarm 연동</li>
      <li>Secrets Manager, Parameter Store 기반 시크릿 및 환경변수 관리</li>
    </ul>
    <ul class="cv-card-tech">
      <li class="cv-chip">AWS Lambda</li>
      <li class="cv-chip">Terraform</li>
      <li class="cv-chip">ELK Stack</li>
      <li class="cv-chip">WAF</li>
      <li class="cv-chip">Secrets Manager</li>
    </ul>
  </article>

  <article class="cv-card">
    <header class="cv-card-head">
      <h3 class="cv-card-title">Weasel</h3>
      <span class="cv-card-links">
        <a href="https://github.com/Team-S5T1" target="_blank" rel="noopener" aria-label="GitHub"><i class="fab fa-github fa-lg"></i></a>
        <span class="cv-period">2024.07 ~ 2024.08</span>
      </span>
    </header>
    <p class="cv-card-meta">Project Lead · Infra Lead</p>
    <p class="cv-card-desc">EKS / Bedrock 기반 문제 풀이 Web App</p>
    <ul>
      <li>Team Lead 및 Cloud Infra 설계, 구축, 운영</li>
      <li>Terraform(HCP Terraform) 기반 Cloud Infra IaC</li>
      <li>Jenkins / Argo CD 기반 Spring Boot Application CI/CD Pipeline 구축</li>
      <li>EKS Autoscaling: Karpenter, HPA 적용</li>
      <li>IRSA 기반 Pod 단위 IAM 권한 제어</li>
      <li>Spot Instance, NAT Instance, VPC CNI maxPods 튜닝을 통한 비용 최적화</li>
      <li>Prometheus, Grafana 기반 EKS 모니터링 구성</li>
    </ul>
    <ul class="cv-card-tech">
      <li class="cv-chip">Spring Boot</li>
      <li class="cv-chip">React</li>
      <li class="cv-chip">EKS</li>
      <li class="cv-chip">RDS(MySQL)</li>
      <li class="cv-chip">Terraform</li>
      <li class="cv-chip">Jenkins</li>
      <li class="cv-chip">Argo CD</li>
      <li class="cv-chip">Karpenter</li>
      <li class="cv-chip">Prometheus</li>
      <li class="cv-chip">Grafana</li>
      <li class="cv-chip">Bedrock (Claude 3.5)</li>
    </ul>
  </article>

  <article class="cv-card">
    <header class="cv-card-head">
      <h3 class="cv-card-title">Amazon Photo Query</h3>
      <span class="cv-card-links">
        <a href="https://github.com/KKamJi98/Photo-Query" target="_blank" rel="noopener" aria-label="Backend"><i class="fab fa-github fa-lg"></i></a>
        <a href="https://github.com/KKamJi98/aws-app-eks-manifests" target="_blank" rel="noopener" aria-label="EKS Manifests"><i class="fas fa-cubes fa-lg"></i></a>
        <span class="cv-period">2024.01 ~ 2024.03</span>
      </span>
    </header>
    <p class="cv-card-meta">Cloud Architecture · Infra · Backend</p>
    <p class="cv-card-desc">AI 기반 사진 앨범 서비스 (MSA · 3-Tier Architecture)</p>
    <ul>
      <li>AWS 클라우드 상에서 MSA, 3-Tier Architecture 기반 구축 및 배포</li>
      <li>Cloud Architecture 설계, AWS 인프라 구축 및 운영</li>
      <li>CI/CD Pipeline 구축, ERD 구축 및 운영</li>
      <li>EKS 모니터링 및 비용 추적</li>
      <li>이미지 CRUD, 북마크, 태그 기능 개발 및 배포</li>
      <li>S3, DynamoDB Public Access 차단 이후 Access Deny 문제를 IRSA 적용으로 해결</li>
      <li>이미지 리사이징 Lambda 분리, Global Accelerator 도입, Goroutine 병렬 처리로 이미지 업로드 API 응답 시간을 5분 이상에서 1분 미만으로 단축</li>
    </ul>
    <ul class="cv-card-tech">
      <li class="cv-chip">Go</li>
      <li class="cv-chip">EKS</li>
      <li class="cv-chip">ECR</li>
      <li class="cv-chip">RDS(MySQL)</li>
      <li class="cv-chip">DynamoDB</li>
      <li class="cv-chip">DocumentDB</li>
      <li class="cv-chip">Karpenter</li>
      <li class="cv-chip">Jenkins</li>
      <li class="cv-chip">Argo CD</li>
      <li class="cv-chip">Prometheus</li>
      <li class="cv-chip">Grafana</li>
      <li class="cv-chip">Terraform</li>
      <li class="cv-chip">SNS / SQS</li>
    </ul>
  </article>
</div>

## <i class="fas fa-screwdriver-wrench fa-fw"></i> Personal Projects
{: #personal-projects .cv-h2}

수동/반복 작업의 편의성을 높이기 위해 CLI Tool과 Web App을 직접 개발하고 운영하고 있습니다.

<div class="cv-mini-grid">
  <a class="cv-mini-card" href="https://github.com/KKamJi98/ssh-connector" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> ssh-connector</div>
    <p class="cv-mini-desc">SSH Config 파일의 설정을 기반으로 동작하는 서버 접근 관리 Tool</p>
  </a>
  <a class="cv-mini-card" href="https://github.com/KKamJi98/aws-pick" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> aws-pick</div>
    <p class="cv-mini-desc">AWS CLI 사용에 적용되는 Default Profile 전환 Tool</p>
  </a>
  <a class="cv-mini-card" href="https://github.com/KKamJi98/kubernetes-monitoring-python" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> kubernetes-monitoring-python</div>
    <p class="cv-mini-desc">Kubernetes Cluster Monitoring CLI Tool</p>
  </a>
  <a class="cv-mini-card" href="https://github.com/KKamJi98/listup-aws-resources" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> listup-aws-resources</div>
    <p class="cv-mini-desc">AWS 리소스를 수집 및 정리해 Excel / JSON으로 내보내는 Tool</p>
  </a>
  <a class="cv-mini-card" href="https://github.com/KKamJi98/log-filter" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> log-filter</div>
    <p class="cv-mini-desc">정규식 패턴으로 기존 로그를 제외하고 신규 패턴 로그만 추출하는 Tool</p>
  </a>
  <a class="cv-mini-card" href="https://github.com/KKamJi98/image-converter" target="_blank" rel="noopener">
    <div class="cv-mini-title"><i class="fab fa-github"></i> image-converter</div>
    <p class="cv-mini-desc">이미지 확장자 변환, 리사이즈, 압축을 제공하는 Web App</p>
  </a>
</div>

## <i class="fas fa-certificate fa-fw"></i> Certifications
{: #certifications .cv-h2}

<div class="cv-cert-grid">
  <div class="cv-cert">
    <span class="cv-cert-dot hashicorp" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">Terraform Associate (003)</span>
      <span class="cv-cert-meta">HashiCorp · 2025.07</span>
    </div>
  </div>
  <div class="cv-cert">
    <span class="cv-cert-dot aws" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">AWS DevOps Engineer - Professional</span>
      <span class="cv-cert-meta">AWS · 2024.12</span>
    </div>
  </div>
  <div class="cv-cert">
    <span class="cv-cert-dot kubernetes" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">CKA: Certified Kubernetes Administrator</span>
      <span class="cv-cert-meta">CNCF · 2024.07</span>
    </div>
  </div>
  <div class="cv-cert">
    <span class="cv-cert-dot aws" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">AWS Solutions Architect - Associate</span>
      <span class="cv-cert-meta">AWS · 2024.02</span>
    </div>
  </div>
  <div class="cv-cert">
    <span class="cv-cert-dot kr" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">정보처리기사</span>
      <span class="cv-cert-meta">한국산업인력공단 · 2023.09</span>
    </div>
  </div>
  <div class="cv-cert">
    <span class="cv-cert-dot aws" aria-hidden="true"></span>
    <div class="cv-cert-body">
      <span class="cv-cert-name">AWS Cloud Practitioner</span>
      <span class="cv-cert-meta">AWS · 2023.05</span>
    </div>
  </div>
</div>

## <i class="fas fa-graduation-cap fa-fw"></i> Education
{: #education .cv-h2}

<ol class="cv-timeline">
  <li class="cv-timeline-item">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">중원대학교 <small>/ 컴퓨터공학과 학사</small></h3>
      <span class="cv-period">2018.02 ~ 2023.08</span>
    </div>
    <div class="cv-timeline-body">
      <ul>
        <li>Sorting Algorithm 성능 측정 및 비교분석, 지도교수: 백승훈</li>
        <li>J-Smart, 교수역량진단시스템 사업 참여, 학생대표</li>
        <li>데이터베이스 강의 보조 활동</li>
        <li>GPA: 4.40 / 4.5, 수석 졸업</li>
      </ul>
    </div>
  </li>
</ol>

## <i class="fas fa-book-open fa-fw"></i> Training &amp; Study
{: #training-study .cv-h2}

<ol class="cv-timeline">
  <li class="cv-timeline-item">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">Cilium 공식 문서 핸즈온 스터디 1기 <small>/ CloudNet@</small></h3>
      <span class="cv-period">2025.07 ~ 2025.08</span>
    </div>
    <div class="cv-timeline-body">
      <p class="cv-muted">Cloud Native 네트워킹 심화 스터디</p>
      <ul>
        <li>eBPF, Cilium 기반 Kubernetes DataPath 이해 및 L3 / L4 / L7 Network Policy 설계</li>
        <li>Routing Mode: Encapsulation(VXLAN / GENEVE) vs Native Routing 구조 및 Trade-off 비교</li>
        <li>Cluster Mesh: Multi-Cluster Service Discovery, 통신, Identity 이해</li>
        <li>Service Mesh 연계: Ingress / Gateway API + Envoy 기반 TLS, L7 Traffic 처리</li>
        <li>Hubble 활용: Flow, Service Map, DNS / HTTP 가시성 기반 Policy Miss 및 차단 Traffic Troubleshooting</li>
      </ul>
    </div>
  </li>
  <li class="cv-timeline-item">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">AWS Cloud School 1기 <small>/ 한국전파진흥협회</small></h3>
      <span class="cv-period">2023.08 ~ 2024.03</span>
    </div>
    <div class="cv-timeline-body">
      <p class="cv-muted">Cloud &amp; DevOps 교육과정</p>
      <ul>
        <li>Network, Linux, Docker, Kubernetes, Jenkins, Argo CD, AWS 학습</li>
        <li>교육과정 내 공지 게시판 개발</li>
        <li>AI &amp; Cloud 기반 앨범 서비스 Photo Query 팀 프로젝트 참여: Kubernetes 운영, Go Backend 개발</li>
      </ul>
    </div>
  </li>
  <li class="cv-timeline-item">
    <div class="cv-timeline-head">
      <h3 class="cv-timeline-title">Rising Camp Plus 백엔드과정 1기 <small>/ 소프트스퀘어드</small></h3>
      <span class="cv-period">2023.07 ~ 2023.09</span>
    </div>
    <div class="cv-timeline-body">
      <p class="cv-muted">Java Backend 교육과정</p>
      <ul>
        <li>Java, Spring Boot, JPA, MySQL, Git 학습</li>
        <li>Spring Boot 기반 채용사이트 개발 팀 프로젝트 참여</li>
      </ul>
    </div>
  </li>
</ol>

## <i class="fas fa-trophy fa-fw"></i> Awards
{: #awards .cv-h2}

<ul class="cv-awards">
  <li class="cv-award">
    <i class="fas fa-trophy cv-award-icon" aria-hidden="true"></i>
    <span class="cv-award-text">Fastfive x AWS Frugality Fest GameDay - <strong>Winner</strong></span>
    <span class="cv-award-date">2025.04</span>
  </li>
  <li class="cv-award">
    <i class="fas fa-trophy cv-award-icon" aria-hidden="true"></i>
    <span class="cv-award-text">Students @ AI - Seoul Hackathon - <strong>Winner</strong></span>
    <span class="cv-award-date">2025.04</span>
  </li>
  <li class="cv-award silver">
    <i class="fas fa-medal cv-award-icon" aria-hidden="true"></i>
    <span class="cv-award-text">AWS PS GameDay (GenAI) - 5th Place</span>
    <span class="cv-award-date">2024.08</span>
  </li>
  <li class="cv-award silver">
    <i class="fas fa-medal cv-award-icon" aria-hidden="true"></i>
    <span class="cv-award-text">AWS x RAPA DevOps Jam - <strong>Runner-up</strong>, 2nd Place</span>
    <span class="cv-award-date">2023.12</span>
  </li>
</ul>

## <i class="fas fa-people-group fa-fw"></i> Activities
{: #activities .cv-h2}

<ul class="cv-activities">
  <li class="cv-activity speaker">
    <span class="cv-activity-text"><span class="cv-activity-role">Speaker</span>Cloud Native Korea Community Day 2025 - ArgoCD와 함께하는 Multi-Cluster 운영</span>
    <span class="cv-activity-date">2025.09</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">Dive 2025 Global Data Hackathon, 부산항만공사</span>
    <span class="cv-activity-date">2025.08</span>
  </li>
  <li class="cv-activity staff">
    <span class="cv-activity-text"><span class="cv-activity-role">Mentor / Staff</span>AWS Cloud School 8기 - Amazon Working Backwards</span>
    <span class="cv-activity-date">2025.06</span>
  </li>
  <li class="cv-activity staff">
    <span class="cv-activity-text"><span class="cv-activity-role">Staff</span>2025 경기창고 개회식</span>
    <span class="cv-activity-date">2025.05</span>
  </li>
  <li class="cv-activity staff">
    <span class="cv-activity-text"><span class="cv-activity-role">Staff</span>2024 충남대학교 커스텀 GPT 프롬프톤</span>
    <span class="cv-activity-date">2024.08</span>
  </li>
  <li class="cv-activity staff">
    <span class="cv-activity-text"><span class="cv-activity-role">Mentor / Staff</span>서울디지텍고등학교 - Amazon Working Backwards</span>
    <span class="cv-activity-date">2024.08</span>
  </li>
  <li class="cv-activity staff">
    <span class="cv-activity-text"><span class="cv-activity-role">Mentor / Staff</span>부산일과학고 AWS Cloud 실습 및 활용</span>
    <span class="cv-activity-date">2024.07</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS PS GameDay (GenAI) 참가</span>
    <span class="cv-activity-date">2024.07</span>
  </li>
  <li class="cv-activity speaker">
    <span class="cv-activity-text"><span class="cv-activity-role">Speaker</span>제2회 AWS 강의실 온라인 세미나 - MicroK8s Cluster 구축하기</span>
    <span class="cv-activity-date">2024.06</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Summit Seoul 2024 참여</span>
    <span class="cv-activity-date">2024.05</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Student Community Day 2024 참여</span>
    <span class="cv-activity-date">2024.04</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">Wanted Backend Challenge - AWS를 활용한 시스템 아키텍처 참여</span>
    <span class="cv-activity-date">2024.03</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">Advanced Architecting on AWS 수료</span>
    <span class="cv-activity-date">2023.12</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">DevOps Engineering on AWS 수료</span>
    <span class="cv-activity-date">2023.12</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">Developing on AWS 수료</span>
    <span class="cv-activity-date">2023.12</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Well-Architected Best Practices 수료</span>
    <span class="cv-activity-date">2023.11</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Community Day 2023 참여</span>
    <span class="cv-activity-date">2023.10</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Security Essentials 수료</span>
    <span class="cv-activity-date">2023.10</span>
  </li>
  <li class="cv-activity">
    <span class="cv-activity-text">AWS Cloud Practitioner Essentials 수료</span>
    <span class="cv-activity-date">2023.10</span>
  </li>
</ul>
