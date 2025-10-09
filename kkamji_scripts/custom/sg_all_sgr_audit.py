#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SG All-Rule Auditor
- sg_list의 모든 SG에 대해 모든 SGR을 나열
- SG 실제 사용 여부 식별 ENI 부착 및 서비스/리소스 참조
- ASG의 LC, LT 모두 고려. LT는 LaunchTemplate, MixedInstancesPolicy, Overrides까지 탐색
- VPCE는 vpc-id로 제한 후 SG 매칭
- CSV 한 줄당 하나의 SGR

Columns:
  sg_id, SG_Name, SG_Description, SGR_ID, SGR_Description, Direction, CIDR, Port_Range, Resources, Usage_Status
"""

import argparse
import csv
import sys
from typing import Dict, List, Tuple, Set, Iterable
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError


def session_for(profile: str, region: str):
    return boto3.session.Session(profile_name=profile, region_name=region)


def safe_client(sess, svc):
    return sess.client(
        svc, config=Config(retries={"max_attempts": 10, "mode": "standard"})
    )


def load_sg_ids(path: str) -> List[str]:
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                ids.append(s)
    return ids


def describe_sg(sess, sg_id: str) -> Dict:
    ec2 = safe_client(sess, "ec2")
    return ec2.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]


def list_sg_rules(sess, sg_id: str) -> List[Dict]:
    ec2 = safe_client(sess, "ec2")
    rules = []
    paginator = ec2.get_paginator("describe_security_group_rules")
    for page in paginator.paginate(Filters=[{"Name": "group-id", "Values": [sg_id]}]):
        rules.extend(page.get("SecurityGroupRules", []))
    return rules


def add_usage(usages: Set[Tuple[str, str]], rtype: str, rname: str):
    usages.add((rtype, rname))


# ENI 부착 스캔
def scan_eni_attachments(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    ec2 = safe_client(sess, "ec2")
    paginator = ec2.get_paginator("describe_network_interfaces")
    for page in paginator.paginate(Filters=[{"Name": "group-id", "Values": [sg_id]}]):
        for eni in page.get("NetworkInterfaces", []):
            att = eni.get("Attachment") or {}
            inst = att.get("InstanceId")
            if inst:
                add_usage(usages, "EC2", inst)
            else:
                desc = eni.get("Description") or ""
                if "ELB app/" in desc or "ELB net/" in desc or "ELB " in desc:
                    add_usage(usages, "ELB-ENI", eni["NetworkInterfaceId"])
                elif "RDS" in desc:
                    add_usage(usages, "RDS-ENI", eni["NetworkInterfaceId"])
                else:
                    add_usage(usages, "ENI", eni["NetworkInterfaceId"])


# LBs
def scan_elb(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        elbv2 = safe_client(sess, "elbv2")
        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                sgs = lb.get("SecurityGroups") or []
                if sg_id in sgs:
                    add_usage(
                        usages,
                        lb.get("Type", "ALB").upper(),
                        lb.get("LoadBalancerName"),
                    )
    except Exception as e:
        print(f"[warn] elbv2: {e}", file=sys.stderr)
    try:
        elb = safe_client(sess, "elb")
        paginator = elb.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for d in page.get("LoadBalancerDescriptions", []):
                sgs = d.get("SecurityGroups") or []
                if sg_id in sgs:
                    add_usage(usages, "CLB", d.get("LoadBalancerName"))
    except Exception as e:
        print(f"[warn] elb: {e}", file=sys.stderr)


# Lambda
def scan_lambda(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        lam = safe_client(sess, "lambda")
        paginator = lam.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                name = fn.get("FunctionName")
                try:
                    cfg = lam.get_function_configuration(FunctionName=name)
                    v = (cfg.get("VpcConfig") or {}).get("SecurityGroupIds") or []
                    if sg_id in v:
                        add_usage(usages, "Lambda", name)
                except Exception as e:
                    print(f"[warn] lambda describe {name}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] lambda list: {e}", file=sys.stderr)


# RDS
def scan_rds(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        rds = safe_client(sess, "rds")
        for page in rds.get_paginator("describe_db_instances").paginate():
            for db in page.get("DBInstances", []):
                v = [
                    g.get("VpcSecurityGroupId") for g in db.get("VpcSecurityGroups", [])
                ]
                if sg_id in v:
                    add_usage(usages, "RDS-Instance", db["DBInstanceIdentifier"])
        for page in rds.get_paginator("describe_db_clusters").paginate():
            for cl in page.get("DBClusters", []):
                v = [
                    g.get("VpcSecurityGroupId") for g in cl.get("VpcSecurityGroups", [])
                ]
                if sg_id in v:
                    add_usage(usages, "RDS-Cluster", cl["DBClusterIdentifier"])
        for page in rds.get_paginator("describe_db_proxies").paginate():
            for pr in page.get("DBProxies", []):
                if sg_id in (pr.get("VpcSecurityGroupIds") or []):
                    add_usage(usages, "RDS-Proxy", pr["DBProxyName"])
    except Exception as e:
        print(f"[warn] rds: {e}", file=sys.stderr)


# Redshift
def scan_redshift(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        rs = safe_client(sess, "redshift")
        resp = rs.describe_clusters()
        for cl in resp.get("Clusters", []):
            v = [g.get("VpcSecurityGroupId") for g in cl.get("VpcSecurityGroups", [])]
            if sg_id in v:
                add_usage(usages, "Redshift", cl["ClusterIdentifier"])
    except Exception as e:
        print(f"[warn] redshift: {e}", file=sys.stderr)
    try:
        rss = safe_client(sess, "redshift-serverless")
        resp = rss.list_workgroups()
        for wg in resp.get("workgroups", []):
            if sg_id in (wg.get("securityGroupIds") or []):
                add_usage(usages, "Redshift-Serverless", wg["workgroupName"])
    except Exception as e:
        print(f"[warn] redshift-serverless: {e}", file=sys.stderr)


# OpenSearch
def scan_opensearch(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        oss = safe_client(sess, "opensearch")
        resp = oss.list_domain_names()
        for dn in [d["DomainName"] for d in resp.get("DomainNames", [])]:
            try:
                d = oss.describe_domain(DomainName=dn)["DomainStatus"]
                v = (d.get("VPCOptions") or {}).get("SecurityGroupIds") or []
                if sg_id in v:
                    add_usage(usages, "OpenSearch", dn)
            except Exception as e:
                print(f"[warn] opensearch describe {dn}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] opensearch: {e}", file=sys.stderr)


# ElastiCache / MemoryDB
def scan_elasticache(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        ec = safe_client(sess, "elasticache")
        resp = ec.describe_cache_clusters(ShowCacheNodeInfo=True)
        for cc in resp.get("CacheClusters", []):
            v = [g.get("SecurityGroupId") for g in cc.get("SecurityGroups", [])]
            if sg_id in v:
                add_usage(usages, "ElastiCache", cc["CacheClusterId"])
    except Exception as e:
        print(f"[warn] elasticache: {e}", file=sys.stderr)
    try:
        mdb = safe_client(sess, "memorydb")
        resp = mdb.describe_clusters()
        for cl in resp.get("Clusters", []):
            if sg_id in (cl.get("SecurityGroups") or []):
                add_usage(usages, "MemoryDB", cl["Name"])
    except Exception as e:
        print(f"[warn] memorydb: {e}", file=sys.stderr)


# EFS / FSx
def scan_efs_fsx(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        efs = safe_client(sess, "efs")
        fs = efs.describe_file_systems().get("FileSystems", [])
        for f in fs:
            mt = efs.describe_mount_targets(FileSystemId=f["FileSystemId"]).get(
                "MountTargets", []
            )
            for m in mt:
                try:
                    sgs = efs.describe_mount_target_security_groups(
                        MountTargetId=m["MountTargetId"]
                    ).get("SecurityGroups", [])
                    if sg_id in sgs:
                        add_usage(usages, "EFS", f["FileSystemId"])
                        break
                except Exception as e:
                    print(
                        f"[warn] efs mt sg {m.get('MountTargetId')}: {e}",
                        file=sys.stderr,
                    )
    except Exception as e:
        print(f"[warn] efs: {e}", file=sys.stderr)
    try:
        fsx = safe_client(sess, "fsx")
        resp = fsx.describe_file_systems()
        for f in resp.get("FileSystems", []):
            if sg_id in (f.get("SecurityGroupIds") or []):
                add_usage(usages, f"FSx-{f.get('FileSystemType')}", f["FileSystemId"])
    except Exception as e:
        print(f"[warn] fsx: {e}", file=sys.stderr)


# VPCE Interface 엔드포인트 vpc-id로 제한 후 SG 매칭
def scan_vpce(sess, sg_id: str, vpc_id: str, usages: Set[Tuple[str, str]]):
    if not vpc_id:
        return
    try:
        ec2 = safe_client(sess, "ec2")
        paginator = ec2.get_paginator("describe_vpc_endpoints")
        for page in paginator.paginate(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ):
            for vpce in page.get("VpcEndpoints", []):
                if vpce.get("VpcEndpointType") != "Interface":
                    continue
                groups = []
                for g in vpce.get("Groups") or []:
                    gid = g.get("GroupId")
                    if gid:
                        groups.append(gid)
                if not groups:
                    groups = vpce.get("SecurityGroupIds") or []
                if sg_id in set(groups):
                    add_usage(usages, "VPCE-Interface", vpce["VpcEndpointId"])
    except Exception as e:
        print(f"[warn] vpce: {e}", file=sys.stderr)


# ECS
def scan_ecs(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        ecs = safe_client(sess, "ecs")
        clusters = ecs.list_clusters().get("clusterArns", [])
        for c in clusters:
            svcs = ecs.list_services(cluster=c).get("serviceArns", [])
            for i in range(0, len(svcs), 10):
                d = ecs.describe_services(cluster=c, services=svcs[i : i + 10])
                for s in d.get("services", []):
                    v = (
                        (
                            (s.get("networkConfiguration") or {}).get(
                                "awsvpcConfiguration"
                            )
                            or {}
                        ).get("securityGroups")
                    ) or []
                    if sg_id in v:
                        add_usage(usages, "ECS-Service", s["serviceName"])
    except Exception as e:
        print(f"[warn] ecs: {e}", file=sys.stderr)


# EKS
def scan_eks(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        eks = safe_client(sess, "eks")
        for name in eks.list_clusters().get("clusters", []):
            d = eks.describe_cluster(name=name)["cluster"]
            vcfg = d.get("resourcesVpcConfig") or {}
            sgs = set(vcfg.get("securityGroupIds") or [])
            csg = vcfg.get("clusterSecurityGroupId")
            if csg:
                sgs.add(csg)
            if sg_id in sgs:
                add_usage(usages, "EKS-Cluster", name)
    except Exception as e:
        print(f"[warn] eks: {e}", file=sys.stderr)


# 안전 문자열
def sanitize_str(x):
    return x if isinstance(x, str) and x.strip() else None


# LT 사양 이터레이터 ASG의 모든 LT 경로 포함
def iter_asg_lt_specs(g: Dict) -> Iterable[Tuple[str, Dict]]:
    # 1 LaunchTemplate 직결
    lt = g.get("LaunchTemplate")
    if lt:
        yield ("ASG.LaunchTemplate", lt)

    # 2 MixedInstancesPolicy 상위 LT
    mip = g.get("MixedInstancesPolicy") or {}
    lt_top = mip.get("LaunchTemplate")
    if lt_top:
        yield ("ASG.MIP.LaunchTemplate", lt_top)

    # 3 MixedInstancesPolicy Overrides별 LT
    for ov in mip.get("Overrides") or []:
        lts = ov.get("LaunchTemplateSpecification")
        if lts:
            yield ("ASG.MIP.Override", {"LaunchTemplateSpecification": lts})


# LT 사양으로부터 해당 버전의 SG 집합을 구함
def sgids_from_lt_spec(sess, spec: Dict) -> Tuple[Set[str], str]:
    ec2 = safe_client(sess, "ec2")
    base = spec.get("LaunchTemplateSpecification") or spec
    if not isinstance(base, dict):
        return set(), ""

    lt_id = sanitize_str(base.get("LaunchTemplateId"))
    lt_name = sanitize_str(base.get("LaunchTemplateName"))
    ver = base.get("Version") or "$Default"
    ver = str(ver)

    kwargs = {"Versions": [ver]}
    if lt_id:
        kwargs["LaunchTemplateId"] = lt_id
        label_base = lt_id
    elif lt_name:
        kwargs["LaunchTemplateName"] = lt_name
        label_base = lt_name
    else:
        # 둘 다 없으면 호출하지 않음
        return set(), ""

    try:
        resp = ec2.describe_launch_template_versions(**kwargs)
    except Exception as e:
        print(f"[warn] asg lt resolve: {e}", file=sys.stderr)
        return set(), ""

    sgs: Set[str] = set()
    for v in resp.get("LaunchTemplateVersions", []):
        data = v.get("LaunchTemplateData") or {}
        for g in data.get("SecurityGroupIds") or []:
            if g:
                sgs.add(g)
        for ni in data.get("NetworkInterfaces") or []:
            for g in ni.get("Groups") or []:
                if g:
                    sgs.add(g)
        vernum = v.get("VersionNumber")
    label = f"{label_base}:{ver}"
    return sgs, label


# ASG가 실제 사용하는 LC, LT 모두 고려
def scan_asg_lc_lt(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    ec2 = safe_client(sess, "ec2")
    asg = safe_client(sess, "autoscaling")

    def lc_uses_sg(lc_name: str) -> bool:
        try:
            resp = asg.describe_launch_configurations(
                LaunchConfigurationNames=[lc_name]
            )
            lcs = resp.get("LaunchConfigurations", [])
            if not lcs:
                return False
            sgs = set(lcs[0].get("SecurityGroups") or [])
            return sg_id in sgs
        except Exception as e:
            print(f"[warn] asg lc resolve: {e}", file=sys.stderr)
            return False

    try:
        groups = asg.describe_auto_scaling_groups().get("AutoScalingGroups", [])
        for g in groups:
            # LC 경로
            lcname = g.get("LaunchConfigurationName")
            if lcname and lc_uses_sg(lcname):
                add_usage(usages, "ASG", g["AutoScalingGroupName"])
                add_usage(usages, "LaunchConfig", lcname)

            # LT 경로들 반복
            for ctx, spec in iter_asg_lt_specs(g):
                sgs, label = sgids_from_lt_spec(sess, spec)
                if sgs and sg_id in sgs:
                    add_usage(usages, "ASG", g["AutoScalingGroupName"])
                    add_usage(usages, "LT", label or "unknown")
    except Exception as e:
        print(f"[warn] asg: {e}", file=sys.stderr)


def scan_msk_mq(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        msk = safe_client(sess, "kafka")
        clusters = msk.list_clusters_v2().get("ClusterInfoList", [])
        for info in clusters:
            base = info.get("ClusterInfo") or info
            v = (base.get("VpcConfig") or {}).get("SecurityGroups") or []
            if sg_id in v:
                add_usage(
                    usages, "MSK", base.get("ClusterName") or base.get("ClusterArn")
                )
    except Exception as e:
        print(f"[warn] msk: {e}", file=sys.stderr)
    try:
        mq = safe_client(sess, "mq")
        for b in mq.list_brokers().get("BrokerSummaries", []):
            d = mq.describe_broker(BrokerId=b["BrokerId"])
            if sg_id in (d.get("SecurityGroups") or []):
                add_usage(usages, "MQ", d["BrokerName"])
    except Exception as e:
        print(f"[warn] mq: {e}", file=sys.stderr)


def scan_usages(sess, sg_id: str, vpc_id: str) -> Set[Tuple[str, str]]:
    usages: Set[Tuple[str, str]] = set()
    scan_eni_attachments(sess, sg_id, usages)
    scan_elb(sess, sg_id, usages)
    scan_lambda(sess, sg_id, usages)
    scan_rds(sess, sg_id, usages)
    scan_redshift(sess, sg_id, usages)
    scan_opensearch(sess, sg_id, usages)
    scan_elasticache(sess, sg_id, usages)
    scan_efs_fsx(sess, sg_id, usages)
    scan_vpce(sess, sg_id, vpc_id, usages)
    scan_ecs(sess, sg_id, usages)
    scan_eks(sess, sg_id, usages)
    scan_asg_lc_lt(sess, sg_id, usages)
    scan_msk_mq(sess, sg_id, usages)
    return usages


def cidr_repr_from_rule(r: Dict) -> str:
    if r.get("CidrIpv4"):
        return r["CidrIpv4"]
    if r.get("CidrIpv6"):
        return r["CidrIpv6"]
    if r.get("ReferencedGroupInfo") and r["ReferencedGroupInfo"].get("GroupId"):
        return f"SG:{r['ReferencedGroupInfo']['GroupId']}"
    if r.get("PrefixListId"):
        return f"PL:{r['PrefixListId']}"
    return ""


def port_range_repr(r: Dict) -> str:
    proto = r.get("IpProtocol")
    if proto in (None, "-1"):
        return "all"
    proto_map = {"6": "tcp", "17": "udp"}
    kind = proto_map.get(str(proto), str(proto)).lower()
    if kind not in ("tcp", "udp"):
        return "n/a"
    fp = r.get("FromPort")
    tp = r.get("ToPort")
    if fp is None and tp is None:
        return "all"
    if fp is None:
        fp = tp
    if tp is None:
        tp = fp
    return f"{fp}-{tp}"


def main():
    ap = argparse.ArgumentParser(
        description="Audit ALL SGRs for SGs in sg_list and determine usage"
    )
    ap.add_argument("--region", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument(
        "--sg-list", required=True, help="Path to file with SG IDs, one per line"
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()

    sess = session_for(args.profile, args.region)
    sg_ids = load_sg_ids(args.sg_list)
    if not sg_ids:
        print("sg_list is empty", file=sys.stderr)
        sys.exit(2)

    rows: List[Dict] = []

    for sg_id in sg_ids:
        try:
            sg = describe_sg(sess, sg_id)
        except (ClientError, BotoCoreError) as e:
            print(f"[error] describe SG {sg_id}: {e}", file=sys.stderr)
            continue

        sg_name = sg.get("GroupName", "")
        sg_desc = sg.get("Description", "") or ""
        vpc_id = sg.get("VpcId")

        usages = scan_usages(sess, sg_id, vpc_id)
        resources_str = (
            "|".join(sorted([f"{t}:{n}" for t, n in usages])) if usages else ""
        )
        usage_status = "USED" if usages else "UNUSED"

        try:
            rules = list_sg_rules(sess, sg_id)
        except (ClientError, BotoCoreError) as e:
            print(f"[error] list rules {sg_id}: {e}", file=sys.stderr)
            continue

        for r in rules:
            rows.append(
                {
                    "sg_id": sg_id,
                    "SG_Name": sg_name,
                    "SG_Description": sg_desc,
                    "SGR_ID": r.get("SecurityGroupRuleId", ""),
                    "SGR_Description": r.get("Description", "") or "",
                    "Direction": "Outbound" if r.get("IsEgress") else "Inbound",
                    "CIDR": cidr_repr_from_rule(r),
                    "Port_Range": port_range_repr(r),
                    "Resources": resources_str,
                    "Usage_Status": usage_status,
                }
            )

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "sg_id",
            "SG_Name",
            "SG_Description",
            "SGR_ID",
            "SGR_Description",
            "Direction",
            "CIDR",
            "Port_Range",
            "Resources",
            "Usage_Status",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
