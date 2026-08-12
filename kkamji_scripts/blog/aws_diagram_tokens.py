"""Design tokens for the AWS official architecture diagram style.

The AWS Architecture Icons deck fixes the category colours, the group container
treatment and the icon geometry. Everything here mirrors that deck so a diagram
built by ``build_aws_diagram.py`` reads like an AWS reference architecture.

Cells whose style contains ``mxgraph.aws4`` or ``resIcon=`` are exempt from the
house normaliser and linter (``drawio_tokens.UNTOUCHABLE_STYLE_MARKERS``), so
AWS colours live only on those cells. Every plain box, label and edge below
stays on the house tokens instead.
"""

# --------------------------------------------------------------------------
# Category colours (AWS Architecture Icons)
# --------------------------------------------------------------------------
CATEGORY = {
    "compute": "#ED7100",
    "containers": "#ED7100",
    "storage": "#7AA116",
    "database": "#C925D1",
    "networking": "#8C4FFF",
    "analytics": "#8C4FFF",
    "security": "#DD344C",
    "management": "#E7157B",
    "integration": "#E7157B",
    "ml": "#01A88D",
    "devtools": "#C7131F",
    "business": "#C925D1",
    "media": "#D6242D",
    "general": "#232F3E",
}

# --------------------------------------------------------------------------
# Service icons: name -> (resIcon, category)
# --------------------------------------------------------------------------
SERVICES = {
    # Compute / containers
    "ec2": ("mxgraph.aws4.ec2", "compute"),
    "ec2_instance": ("mxgraph.aws4.ec2", "compute"),
    "ecs": ("mxgraph.aws4.ecs", "containers"),
    "eks": ("mxgraph.aws4.eks", "containers"),
    "ecr": ("mxgraph.aws4.ecr", "containers"),
    "fargate": ("mxgraph.aws4.fargate", "containers"),
    "lambda": ("mxgraph.aws4.lambda_function", "compute"),
    "batch": ("mxgraph.aws4.batch", "compute"),
    "app_runner": ("mxgraph.aws4.app_runner", "compute"),
    "elastic_beanstalk": ("mxgraph.aws4.elastic_beanstalk", "compute"),
    "auto_scaling": ("mxgraph.aws4.auto_scaling2", "compute"),
    # Storage
    "s3": ("mxgraph.aws4.s3", "storage"),
    "ebs": ("mxgraph.aws4.elastic_block_store", "storage"),
    "efs": ("mxgraph.aws4.elastic_file_system", "storage"),
    "fsx": ("mxgraph.aws4.fsx", "storage"),
    "backup": ("mxgraph.aws4.backup", "storage"),
    # Database
    "rds": ("mxgraph.aws4.rds", "database"),
    "aurora": ("mxgraph.aws4.aurora", "database"),
    "dynamodb": ("mxgraph.aws4.dynamodb", "database"),
    "elasticache": ("mxgraph.aws4.elasticache", "database"),
    "redshift": ("mxgraph.aws4.redshift", "database"),
    "documentdb": ("mxgraph.aws4.documentdb_with_mongodb_compatibility", "database"),
    "timestream": ("mxgraph.aws4.timestream", "database"),
    # Networking & content delivery
    "vpc": ("mxgraph.aws4.vpc", "networking"),
    "cloudfront": ("mxgraph.aws4.cloudfront", "networking"),
    "route53": ("mxgraph.aws4.route_53", "networking"),
    "route53_hosted_zone": ("mxgraph.aws4.hosted_zone", "networking"),
    "api_gateway": ("mxgraph.aws4.api_gateway", "networking"),
    "alb": ("mxgraph.aws4.application_load_balancer", "networking"),
    "nlb": ("mxgraph.aws4.network_load_balancer", "networking"),
    "elb": ("mxgraph.aws4.elastic_load_balancing", "networking"),
    "nat_gateway": ("mxgraph.aws4.nat_gateway", "networking"),
    "internet_gateway": ("mxgraph.aws4.internet_gateway", "networking"),
    "transit_gateway": ("mxgraph.aws4.transit_gateway", "networking"),
    "direct_connect": ("mxgraph.aws4.direct_connect", "networking"),
    "vpc_endpoint": ("mxgraph.aws4.endpoints", "networking"),
    "eni": ("mxgraph.aws4.elastic_network_interface", "networking"),
    "vpc_lattice": ("mxgraph.aws4.vpc_lattice", "networking"),
    "privatelink": ("mxgraph.aws4.privatelink", "networking"),
    "global_accelerator": ("mxgraph.aws4.global_accelerator", "networking"),
    "vpn_gateway": ("mxgraph.aws4.vpn_gateway", "networking"),
    "router": ("mxgraph.aws4.router", "networking"),
    # Security, identity & compliance
    "iam": ("mxgraph.aws4.identity_and_access_management", "security"),
    "iam_role": ("mxgraph.aws4.role", "security"),
    "sts": ("mxgraph.aws4.sts", "security"),
    "waf": ("mxgraph.aws4.waf", "security"),
    "shield": ("mxgraph.aws4.shield", "security"),
    "kms": ("mxgraph.aws4.key_management_service", "security"),
    "secrets_manager": ("mxgraph.aws4.secrets_manager", "security"),
    "cognito": ("mxgraph.aws4.cognito", "security"),
    "acm": ("mxgraph.aws4.certificate_manager_3", "security"),
    "guardduty": ("mxgraph.aws4.guardduty", "security"),
    "ram": ("mxgraph.aws4.resource_access_manager", "security"),
    # Management & governance
    "cloudwatch": ("mxgraph.aws4.cloudwatch_2", "management"),
    "cloudformation": ("mxgraph.aws4.cloudformation", "management"),
    "cloudtrail": ("mxgraph.aws4.cloudtrail", "management"),
    "systems_manager": ("mxgraph.aws4.systems_manager", "management"),
    "organizations": ("mxgraph.aws4.organizations", "management"),
    "config": ("mxgraph.aws4.config", "management"),
    # Application integration
    "sns": ("mxgraph.aws4.sns", "integration"),
    "sqs": ("mxgraph.aws4.sqs", "integration"),
    "eventbridge": ("mxgraph.aws4.eventbridge", "integration"),
    "step_functions": ("mxgraph.aws4.step_functions", "integration"),
    "mq": ("mxgraph.aws4.mq", "integration"),
    # Analytics
    "athena": ("mxgraph.aws4.athena", "analytics"),
    "glue": ("mxgraph.aws4.glue", "analytics"),
    "kinesis": ("mxgraph.aws4.kinesis", "analytics"),
    "kinesis_firehose": ("mxgraph.aws4.kinesis_data_firehose", "analytics"),
    "emr": ("mxgraph.aws4.emr", "analytics"),
    "lake_formation": ("mxgraph.aws4.lake_formation", "analytics"),
    "quicksight": ("mxgraph.aws4.quicksight", "analytics"),
    "opensearch": ("mxgraph.aws4.elasticsearch_service", "analytics"),
    "msk": ("mxgraph.aws4.managed_streaming_for_kafka", "analytics"),
    # Machine learning
    "bedrock": ("mxgraph.aws4.bedrock", "ml"),
    "sagemaker": ("mxgraph.aws4.sagemaker", "ml"),
    # Developer tools
    "codebuild": ("mxgraph.aws4.codebuild", "devtools"),
    "codepipeline": ("mxgraph.aws4.codepipeline", "devtools"),
    "codedeploy": ("mxgraph.aws4.codedeploy", "devtools"),
    "codecommit": ("mxgraph.aws4.codecommit", "devtools"),
    # General / non-service marks from the same deck
    "user": ("mxgraph.aws4.user", "general"),
    "users": ("mxgraph.aws4.users", "general"),
    "client": ("mxgraph.aws4.client", "general"),
    "internet": ("mxgraph.aws4.internet_alt1", "general"),
    "generic_database": ("mxgraph.aws4.generic_database", "general"),
    "server": ("mxgraph.aws4.traditional_server", "general"),
    "mobile": ("mxgraph.aws4.mobile_client", "general"),
    "disk": ("mxgraph.aws4.disk", "general"),
    "forums": ("mxgraph.aws4.forums", "general"),
    "documents": ("mxgraph.aws4.documents", "general"),
    "gear": ("mxgraph.aws4.gear", "general"),
    "source_code": ("mxgraph.aws4.source_code", "general"),
    "email": ("mxgraph.aws4.email", "general"),
    "firewall_manager": ("mxgraph.aws4.firewall_manager", "security"),
    "question": ("mxgraph.aws4.question", "general"),
}

# --------------------------------------------------------------------------
# Kubernetes icons, referenced as ``k8s:<name>`` in a spec.
#
# The upstream Kubernetes icon set is a single blue hexagon per resource, drawn
# by ``mxgraph.kubernetes.icon`` with a ``prIcon`` selector. Same 48px slot and
# same caption treatment as an AWS resource icon, so the two mix without the
# grid noticing.
# --------------------------------------------------------------------------
KUBERNETES_BLUE = "#326CE5"
KUBERNETES = {
    "pod": "pod", "deploy": "deploy", "deployment": "deploy",
    "svc": "svc", "service": "svc", "ing": "ing", "ingress": "ing",
    "ns": "ns", "namespace": "ns", "node": "node", "etcd": "etcd",
    "job": "job", "cronjob": "cronjob", "ds": "ds", "daemonset": "ds",
    "sts": "sts", "statefulset": "sts", "rs": "rs", "replicaset": "rs",
    "hpa": "hpa", "quota": "quota", "limits": "limits",
    "secret": "secret", "cm": "cm", "configmap": "cm",
    "sa": "sa", "serviceaccount": "sa", "sc": "sc", "storageclass": "sc",
    "pv": "pv", "pvc": "pvc", "vol": "vol", "volume": "vol",
    "netpol": "netpol", "networkpolicy": "netpol", "psp": "psp",
    "role": "role", "rb": "rb", "rolebinding": "rb",
    "crd": "crd", "crb": "crb", "ep": "ep", "endpoint": "ep",
    "master": "master", "control_plane": "control_plane",
    "kubelet": "kubelet", "kproxy": "k_proxy", "api": "api", "sched": "sched",
    "c_m": "c_m", "controller_manager": "c_m", "c_c_m": "c_c_m",
    "group": "group", "user": "user",
}

# --------------------------------------------------------------------------
# Google Cloud icons, referenced as ``gcp:<name>`` in a spec.
#
# The gcp2 stencils are single-colour silhouettes, so the colour comes from the
# Google Cloud product palette rather than from the shape.
# --------------------------------------------------------------------------
GCP_BLUE = "#4285F4"
GCP_GREEN = "#34A853"
GCP_YELLOW = "#FBBC04"
GCP_RED = "#EA4335"
GCP = {
    "compute_engine": ("compute_engine", GCP_BLUE),
    "container_engine": ("container_engine", GCP_BLUE),
    "gke": ("container_engine", GCP_BLUE),
    "container_registry": ("container_registry", GCP_BLUE),
    "cloud_storage": ("cloud_storage", GCP_YELLOW),
    "bigquery": ("bigquery", GCP_BLUE),
    "cloud_iam": ("cloud_iam", GCP_RED),
    "iam": ("cloud_iam", GCP_RED),
    "key": ("key", GCP_RED),
    "kms": ("key_management_service", GCP_RED),
    "iap": ("identity_aware_proxy", GCP_RED),
    "cloud_apis": ("cloud_apis", GCP_GREEN),
    "api": ("cloud_apis", GCP_GREEN),
    "network": ("cloud_network", GCP_GREEN),
    "google_network": ("google_network", GCP_GREEN),
    "folders": ("folders", GCP_YELLOW),
    "service": ("service", GCP_BLUE),
    "users": ("users", GCP_BLUE),
    "cloud_shell": ("cloud_computer", GCP_BLUE),
    "external_data": ("external_data_resource", GCP_YELLOW),
}

# --------------------------------------------------------------------------
# Group containers: kind -> (grIcon, stroke, fill, dashed)
# --------------------------------------------------------------------------
GROUPS = {
    "aws_cloud": ("mxgraph.aws4.group_aws_cloud_alt", "#232F3E", "none", 0),
    "region": ("mxgraph.aws4.group_region", "#00A4A6", "none", 1),
    "account": ("mxgraph.aws4.group_account", "#E7157B", "none", 0),
    "vpc": ("mxgraph.aws4.group_vpc2", "#8C4FFF", "none", 0),
    "az": ("mxgraph.aws4.group_availability_zone", "#00A4A6", "none", 1),
    "public_subnet": ("mxgraph.aws4.group_security_group", "#7AA116", "#F2F7E9", 0),
    "private_subnet": ("mxgraph.aws4.group_security_group", "#00A4A6", "#E7F5F5", 0),
    "security_group": ("mxgraph.aws4.group_security_group", "#DD344C", "none", 1),
    "auto_scaling": ("mxgraph.aws4.group_auto_scaling_group", "#ED7100", "none", 1),
    "corporate": ("mxgraph.aws4.group_corporate_data_center", "#7D8998", "none", 0),
    "server_contents": ("mxgraph.aws4.group_server_contents", "#232F3E", "none", 0),
    "spot_fleet": ("mxgraph.aws4.group_spot_fleet", "#ED7100", "none", 0),
    "ec2_instance_contents": (
        "mxgraph.aws4.group_ec2_instance_contents",
        "#ED7100",
        "none",
        0,
    ),
    "iot": ("mxgraph.aws4.group_iot_greengrass", "#01A88D", "none", 1),
}

# Plain containers with no AWS icon. These stay on the house group tokens so the
# corpus linter can still check them.
PLAIN_GROUP_STROKE = "#5F6368"
PLAIN_GROUP_FILL = "none"

# --------------------------------------------------------------------------
# House tokens reused verbatim (see drawio_tokens.py in the skill)
# --------------------------------------------------------------------------
INK = "#202124"
INK_MUTED = "#5F6368"
INK_INVERSE = "#FFFFFF"
EDGE_STROKE = "#232F3E"
STEP_FILL = "#1A73E8"

ROLES = {
    "process": ("#E8F0FE", "#1A73E8"),
    "store": ("#E6F4EA", "#34A853"),
    "queue": ("#FEF7E0", "#F9AB00"),
    "danger": ("#FCE8E6", "#EA4335"),
    "compute": ("#F3E8FD", "#A142F4"),
    "external": ("#E8EAED", "#9AA0A6"),
    "surface": ("#FFFFFF", "#5F6368"),
    "group": ("#F8F9FA", "#9AA0A6"),
}

# Type scale. Only these four sizes may appear in a published diagram.
FONT_TITLE = 20
FONT_LEAD = 16
FONT_BODY = 13
FONT_DETAIL = 11

# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
ICON = 48  # AWS resource icon edge length
ICON_LABEL_H = 34  # two label lines under a 48px icon at fontSize 11
BOX_W = 176
BOX_H = 54
STEP = 26  # numbered step badge
STEP_OVERLAP = 6  # how far the badge sits over the element's corner
GROUP_PAD = 22  # left/right/bottom padding inside a container
GROUP_HEADER = 42  # top padding: clears the 24px corner icon and its label
COL_GAP = 56
ROW_GAP = 52
MARGIN = 34  # canvas margin inside the outer frame
TITLE_H = 30
SUBTITLE_H = 22
