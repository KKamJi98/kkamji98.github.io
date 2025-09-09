#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SG All-Rule Auditor
- For every SG in sg_list, enumerate ALL Security Group Rules (SGR)
- For each SG, determine whether it is actually used (ENI-attachment or service references)
- Output one CSV with one row per SGR (inbound & outbound)

Columns:
  SG_Name, SG_Description, SGR_ID, SGR_Description, Direction, CIDR, Resources, Usage_Status

Notes:
  - CIDR field will contain (in priority) CidrIpv4 or CidrIpv6. If neither is present,
    and the rule references another SG or a PrefixList, CIDR will show "SG:<sg-id>" or "PL:<pl-id>".
  - Usage_Status is USED if any attachment/reference was found for the SG; otherwise UNUSED.

Usage:
  python sg_all_sgr_audit.py --region ap-northeast-2 --profile prod --sg-list ./sg_list --out ./all_sg_rules.csv

Requirements:
  pip install boto3
"""

import argparse
import csv
import sys
from typing import Dict, List, Tuple, Set
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

def session_for(profile: str, region: str):
    return boto3.session.Session(profile_name=profile, region_name=region)

def safe_client(sess, svc):
    return sess.client(svc, config=Config(retries={"max_attempts": 10, "mode": "standard"}))

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
    for page in paginator.paginate(Filters=[{"Name":"group-id","Values":[sg_id]}]):
        rules.extend(page.get("SecurityGroupRules", []))
    return rules

def add_usage(usages: Set[Tuple[str,str]], rtype: str, rname: str):
    usages.add((rtype, rname))

# ---------- Usage scanners ----------
def scan_eni_attachments(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    ec2 = safe_client(sess, "ec2")
    paginator = ec2.get_paginator("describe_network_interfaces")
    for page in paginator.paginate(Filters=[{"Name":"group-id","Values":[sg_id]}]):
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

def scan_elb(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    # ALB/NLB
    try:
        elbv2 = safe_client(sess, "elbv2")
        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                sgs = lb.get("SecurityGroups") or []
                if sg_id in sgs:
                    add_usage(usages, lb.get("Type","ALB").upper(), lb.get("LoadBalancerName"))
    except Exception as e:
        print(f"[warn] elbv2: {e}", file=sys.stderr)
    # Classic ELB
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

def scan_lambda(sess, sg_id: str, usages: Set[Tuple[str,str]]):
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

def scan_rds(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    try:
        rds = safe_client(sess, "rds")
        for page in rds.get_paginator("describe_db_instances").paginate():
            for db in page.get("DBInstances", []):
                v = [g.get("VpcSecurityGroupId") for g in db.get("VpcSecurityGroups", [])]
                if sg_id in v:
                    add_usage(usages, "RDS-Instance", db["DBInstanceIdentifier"])
        for page in rds.get_paginator("describe_db_clusters").paginate():
            for cl in page.get("DBClusters", []):
                v = [g.get("VpcSecurityGroupId") for g in cl.get("VpcSecurityGroups", [])]
                if sg_id in v:
                    add_usage(usages, "RDS-Cluster", cl["DBClusterIdentifier"])
        for page in rds.get_paginator("describe_db_proxies").paginate():
            for pr in page.get("DBProxies", []):
                if sg_id in (pr.get("VpcSecurityGroupIds") or []):
                    add_usage(usages, "RDS-Proxy", pr["DBProxyName"])
    except Exception as e:
        print(f"[warn] rds: {e}", file=sys.stderr)

def scan_redshift(sess, sg_id: str, usages: Set[Tuple[str,str]]):
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

def scan_opensearch(sess, sg_id: str, usages: Set[Tuple[str,str]]):
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

def scan_elasticache(sess, sg_id: str, usages: Set[Tuple[str,str]]):
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

def scan_efs_fsx(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    try:
        efs = safe_client(sess, "efs")
        fs = efs.describe_file_systems().get("FileSystems", [])
        for f in fs:
            mt = efs.describe_mount_targets(FileSystemId=f["FileSystemId"]).get("MountTargets", [])
            for m in mt:
                try:
                    sgs = efs.describe_mount_target_security_groups(MountTargetId=m["MountTargetId"]).get("SecurityGroups", [])
                    if sg_id in sgs:
                        add_usage(usages, "EFS", f["FileSystemId"])
                        break
                except Exception as e:
                    print(f"[warn] efs mt sg {m.get('MountTargetId')}: {e}", file=sys.stderr)
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

def scan_vpce(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    try:
        ec2 = safe_client(sess, "ec2")
        paginator = ec2.get_paginator("describe_vpc_endpoints")
        for page in paginator.paginate(Filters=[{"Name":"group-id","Values":[sg_id]}]):
            for vpce in page.get("VpcEndpoints", []):
                add_usage(usages, "VPCE-Interface", vpce["VpcEndpointId"])
    except Exception as e:
        print(f"[warn] vpce: {e}", file=sys.stderr)

def scan_ecs(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    try:
        ecs = safe_client(sess, "ecs")
        clusters = ecs.list_clusters().get("clusterArns", [])
        for c in clusters:
            svcs = ecs.list_services(cluster=c).get("serviceArns", [])
            for i in range(0, len(svcs), 10):
                d = ecs.describe_services(cluster=c, services=svcs[i:i+10])
                for s in d.get("services", []):
                    v = (((s.get("networkConfiguration") or {}).get("awsvpcConfiguration") or {}).get("securityGroups")) or []
                    if sg_id in v:
                        add_usage(usages, "ECS-Service", s["serviceName"])
    except Exception as e:
        print(f"[warn] ecs: {e}", file=sys.stderr)

def scan_eks(sess, sg_id: str, usages: Set[Tuple[str,str]]):
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

def scan_asg_lt(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    ec2 = safe_client(sess, "ec2")
    asg = safe_client(sess, "autoscaling")
    # Launch Templates
    try:
        for page in ec2.get_paginator("describe_launch_templates").paginate():
            for lt in page.get("LaunchTemplates", []):
                ltid = lt["LaunchTemplateId"]
                try:
                    vers = ec2.describe_launch_template_versions(LaunchTemplateId=ltid).get("LaunchTemplateVersions", [])
                    for v in vers:
                        data = v.get("LaunchTemplateData") or {}
                        sgids = set(data.get("SecurityGroupIds") or [])
                        for ni in data.get("NetworkInterfaces", []) or []:
                            for g in ni.get("Groups", []) or []:
                                sgids.add(g)
                        if sg_id in sgids:
                            add_usage(usages, "LT", f"{ltid}:{v.get('VersionNumber')}")
                            break
                except Exception as e:
                    print(f"[warn] lt vers {ltid}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] lt list: {e}", file=sys.stderr)
    # Launch Configurations
    try:
        for l in asg.describe_launch_configurations().get("LaunchConfigurations", []):
            if sg_id in (l.get("SecurityGroups") or []):
                add_usage(usages, "LaunchConfig", l["LaunchConfigurationName"])
    except Exception as e:
        print(f"[warn] lc: {e}", file=sys.stderr)
    # ASGs
    try:
        groups = asg.describe_auto_scaling_groups().get("AutoScalingGroups", [])
        def check_lt_spec(spec):
            try:
                if not spec:
                    return False
                if "LaunchTemplateName" in spec:
                    resp = ec2.describe_launch_templates(LaunchTemplateNames=[spec["LaunchTemplateName"]])
                    ltid = resp["LaunchTemplates"][0]["LaunchTemplateId"]
                else:
                    ltid = spec.get("LaunchTemplateId")
                ver = spec.get("Version") or "$Default"
                vers = ec2.describe_launch_template_versions(LaunchTemplateId=ltid, Versions=[ver])
                for v in vers.get("LaunchTemplateVersions", []):
                    data = v.get("LaunchTemplateData") or {}
                    sgids = set(data.get("SecurityGroupIds") or [])
                    for ni in data.get("NetworkInterfaces", []) or []:
                        for gg in ni.get("Groups", []) or []:
                            sgids.add(gg)
                    return sg_id in sgids
            except Exception as e:
                print(f"[warn] asg lt resolve: {e}", file=sys.stderr)
            return False
        for g in groups:
            used = False
            mip, lt, lcname = g.get("MixedInstancesPolicy"), g.get("LaunchTemplate"), g.get("LaunchConfigurationName")
            if mip and mip.get("LaunchTemplate"):
                used = check_lt_spec(mip["LaunchTemplate"])
            if not used and lt:
                used = check_lt_spec(lt)
            if not used and lcname:
                try:
                    l = asg.describe_launch_configurations(LaunchConfigurationNames=[lcname])["LaunchConfigurations"][0]
                    if sg_id in (l.get("SecurityGroups") or []):
                        used = True
                except Exception as e:
                    print(f"[warn] asg lc resolve: {e}", file=sys.stderr)
            if used:
                add_usage(usages, "ASG", g["AutoScalingGroupName"])
    except Exception as e:
        print(f"[warn] asg: {e}", file=sys.stderr)

def scan_msk_mq(sess, sg_id: str, usages: Set[Tuple[str,str]]):
    try:
        msk = safe_client(sess, "kafka")
        clusters = msk.list_clusters_v2().get("ClusterInfoList", [])
        for info in clusters:
            base = info.get("ClusterInfo") or info
            v = ((base.get("VpcConfig") or {}).get("SecurityGroups") or [])
            if sg_id in v:
                add_usage(usages, "MSK", base.get("ClusterName") or base.get("ClusterArn"))
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

def scan_usages(sess, sg_id: str) -> Set[Tuple[str,str]]:
    usages: Set[Tuple[str,str]] = set()
    scan_eni_attachments(sess, sg_id, usages)
    scan_elb(sess, sg_id, usages)
    scan_lambda(sess, sg_id, usages)
    scan_rds(sess, sg_id, usages)
    scan_redshift(sess, sg_id, usages)
    scan_opensearch(sess, sg_id, usages)
    scan_elasticache(sess, sg_id, usages)
    scan_efs_fsx(sess, sg_id, usages)
    scan_vpce(sess, sg_id, usages)
    scan_ecs(sess, sg_id, usages)
    scan_eks(sess, sg_id, usages)
    scan_asg_lt(sess, sg_id, usages)
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

def main():
    ap = argparse.ArgumentParser(description="Audit ALL SGRs for SGs in sg_list and determine usage")
    ap.add_argument("--region", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--sg-list", required=True, help="Path to file with SG IDs, one per line")
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

        usages = scan_usages(sess, sg_id)
        resources_str = "|".join(sorted([f"{t}:{n}" for t, n in usages])) if usages else ""
        usage_status = "USED" if usages else "UNUSED"

        try:
            rules = list_sg_rules(sess, sg_id)
        except (ClientError, BotoCoreError) as e:
            print(f"[error] list rules {sg_id}: {e}", file=sys.stderr)
            continue

        for r in rules:
            row = {
                "SG_Name": sg_name,
                "SG_Description": sg_desc,
                "SGR_ID": r.get("SecurityGroupRuleId", ""),
                "SGR_Description": r.get("Description", "") or "",
                "Direction": "Outbound" if r.get("IsEgress") else "Inbound",
                "CIDR": cidr_repr_from_rule(r),
                "Resources": resources_str,
                "Usage_Status": usage_status,
            }
            rows.append(row)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["SG_Name","SG_Description","SGR_ID","SGR_Description","Direction","CIDR","Resources","Usage_Status"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.out}")

if __name__ == "__main__":
    main()
