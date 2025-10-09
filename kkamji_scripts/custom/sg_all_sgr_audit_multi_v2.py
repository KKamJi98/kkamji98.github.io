#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SG All-Rule Auditor (Concurrent + Prefetch + Robust + Flexible sg_list)
- sg_list의 각 줄이 'sg-xxxx' 또는 JSON({"id":"sg-xxxx", ...} 혹은 더 복잡한 구조)이어도 SG ID를 추출
- 멀티스레드 병렬 처리, 진행 로그
- ASG/LC/LT는 사전 프리페치 캐시 사용(스로틀 회피)
- VPCE는 vpc-id로 제한 후 SG 매칭
- credential loop 시 기본 자격증명 체인으로 폴백
- 존재하지 않는 SG는 CSV에 NOT_FOUND 표기
- 최종 중복(SG+SGR_ID+Direction) 제거

CSV Columns:
  sg_id, SG_Name, SG_Description, SGR_ID, SGR_Description, Direction, CIDR, Port_Range, Resources, Usage_Status
"""

import argparse
import csv
import sys
import time
import random
import threading
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Set, Iterable, Any
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

# ===================== logging =====================
_print_lock = threading.Lock()


def log(msg: str):
    with _print_lock:
        print(msg, flush=True)


# ===================== retry/backoff =====================
THROTTLE_CODES = {
    "Throttling",
    "ThrottlingException",
    "RequestLimitExceeded",
    "TooManyRequestsException",
    "ProvisionedThroughputExceededException",
    "RequestThrottled",
    "RequestThrottledException",
}


def call_with_backoff(fn, max_attempts=8, base=0.4, cap=10.0):
    attempt = 0
    while True:
        try:
            return fn()
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            if code in THROTTLE_CODES:
                sleep = min(cap, base * (2**attempt)) * random.random()
                time.sleep(sleep)
                attempt += 1
                if attempt >= max_attempts:
                    raise
            else:
                raise


# ===================== session/client =====================
def session_for(profile: str, region: str):
    try:
        return boto3.session.Session(profile_name=profile, region_name=region)
    except Exception as e:
        msg = str(e)
        if "Infinite loop in credential configuration detected" in msg:
            log(f"[warn] credentials: {msg}")
            log(
                "[warn] credentials: falling back to default credential chain (ignoring --profile)"
            )
            return boto3.session.Session(region_name=region)
        raise


def safe_client(sess, svc):
    return sess.client(
        svc, config=Config(retries={"max_attempts": 15, "mode": "adaptive"})
    )


# ===================== sg_list flexible loader =====================
SG_ID_RE = re.compile(r"\bsg-[0-9a-fA-F]{8,}\b")


def _extract_sg_ids_from_obj(obj: Any, out: Set[str]):
    if isinstance(obj, str):
        for m in SG_ID_RE.findall(obj):
            out.add(m)
    elif isinstance(obj, dict):
        # dict에서 id 키를 특별히 우선 확인
        v = obj.get("id")
        if isinstance(v, str) and SG_ID_RE.fullmatch(v):
            out.add(v)
        # 모든 값 재귀 탐색
        for val in obj.values():
            _extract_sg_ids_from_obj(val, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_sg_ids_from_obj(item, out)
    # 기타 타입은 무시


def load_sg_ids(path: str) -> List[str]:
    ids: List[str] = []
    seen: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            found: Set[str] = set()
            # 1) JSON 시도
            try:
                obj = json.loads(s)
                _extract_sg_ids_from_obj(obj, found)
            except Exception:
                # 2) 일반 텍스트에서 정규식 매칭
                for m in SG_ID_RE.findall(s):
                    found.add(m)
            # 3) 수집 및 중복 제거
            for sg in sorted(found):
                if sg not in seen:
                    ids.append(sg)
                    seen.add(sg)
    return ids


# ===================== SG describe/rules =====================
def describe_sg(sess, sg_id: str) -> Dict:
    ec2 = safe_client(sess, "ec2")
    return call_with_backoff(lambda: ec2.describe_security_groups(GroupIds=[sg_id]))[
        "SecurityGroups"
    ][0]


def list_sg_rules(sess, sg_id: str) -> List[Dict]:
    ec2 = safe_client(sess, "ec2")
    rules: List[Dict] = []
    seen: Set[str] = set()
    paginator = ec2.get_paginator("describe_security_group_rules")
    for page in paginator.paginate(Filters=[{"Name": "group-id", "Values": [sg_id]}]):
        for r in page.get("SecurityGroupRules", []):
            rid = r.get("SecurityGroupRuleId")
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            rules.append(r)
    return rules


# ===================== usage recording =====================
def add_usage(usages: Set[Tuple[str, str]], rtype: str, rname: str):
    usages.add((rtype, rname))


# ===================== scanners (per SG) =====================
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
        log(f"[warn] elbv2: {e}")
    try:
        elb = safe_client(sess, "elb")
        paginator = elb.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for d in page.get("LoadBalancerDescriptions", []):
                sgs = d.get("SecurityGroups") or []
                if sg_id in sgs:
                    add_usage(usages, "CLB", d.get("LoadBalancerName"))
    except Exception as e:
        log(f"[warn] elb: {e}")


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
                    log(f"[warn] lambda describe {name}: {e}")
    except Exception as e:
        log(f"[warn] lambda list: {e}")


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
        log(f"[warn] rds: {e}")


def scan_redshift(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        rs = safe_client(sess, "redshift")
        resp = rs.describe_clusters()
        for cl in resp.get("Clusters", []):
            v = [g.get("VpcSecurityGroupId") for g in cl.get("VpcSecurityGroups", [])]
            if sg_id in v:
                add_usage(usages, "Redshift", cl["ClusterIdentifier"])
    except Exception as e:
        log(f"[warn] redshift: {e}")
    try:
        rss = safe_client(sess, "redshift-serverless")
        resp = rss.list_workgroups()
        for wg in resp.get("workgroups", []):
            if sg_id in (wg.get("securityGroupIds") or []):
                add_usage(usages, "Redshift-Serverless", wg["workgroupName"])
    except Exception as e:
        log(f"[warn] redshift-serverless: {e}")


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
                log(f"[warn] opensearch describe {dn}: {e}")
    except Exception as e:
        log(f"[warn] opensearch: {e}")


def scan_elasticache(sess, sg_id: str, usages: Set[Tuple[str, str]]):
    try:
        ec = safe_client(sess, "elasticache")
        resp = ec.describe_cache_clusters(ShowCacheNodeInfo=True)
        for cc in resp.get("CacheClusters", []):
            v = [g.get("SecurityGroupId") for g in cc.get("SecurityGroups", [])]
            if sg_id in v:
                add_usage(usages, "ElastiCache", cc["CacheClusterId"])
    except Exception as e:
        log(f"[warn] elasticache: {e}")
    try:
        mdb = safe_client(sess, "memorydb")
        resp = mdb.describe_clusters()
        for cl in resp.get("Clusters", []):
            if sg_id in (cl.get("SecurityGroups") or []):
                add_usage(usages, "MemoryDB", cl["Name"])
    except Exception as e:
        log(f"[warn] memorydb: {e}")


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
                    log(f"[warn] efs mt sg {m.get('MountTargetId')}: {e}")
    except Exception as e:
        log(f"[warn] efs: {e}")
    try:
        fsx = safe_client(sess, "fsx")
        resp = fsx.describe_file_systems()
        for f in resp.get("FileSystems", []):
            if sg_id in (f.get("SecurityGroupIds") or []):
                add_usage(usages, f"FSx-{f.get('FileSystemType')}", f["FileSystemId"])
    except Exception as e:
        log(f"[warn] fsx: {e}")


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
        log(f"[warn] vpce: {e}")


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
        log(f"[warn] ecs: {e}")


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
        log(f"[warn] eks: {e}")


# ===================== ASG/LC/LT prefetch and cached scan =====================
def iter_asg_lt_specs(g: Dict) -> Iterable[Dict]:
    if g.get("LaunchTemplate"):
        yield g["LaunchTemplate"]
    mip = g.get("MixedInstancesPolicy") or {}
    if mip.get("LaunchTemplate"):
        yield mip["LaunchTemplate"]
    for ov in mip.get("Overrides") or []:
        lts = ov.get("LaunchTemplateSpecification")
        if lts:
            yield {"LaunchTemplateSpecification": lts}


def normalize_lt_key(spec: Dict) -> Tuple[str, str, str]:
    base = spec.get("LaunchTemplateSpecification") or spec
    return (
        base.get("LaunchTemplateId") or "",
        base.get("LaunchTemplateName") or "",
        str(base.get("Version") or "$Default"),
    )


def prefetch_asg_inventory(
    sess,
) -> Tuple[List[Dict], Dict[str, Set[str]], Dict[Tuple[str, str, str], Set[str]]]:
    asg_cli = safe_client(sess, "autoscaling")
    ec2 = safe_client(sess, "ec2")

    groups: List[Dict] = []
    paginator = asg_cli.get_paginator("describe_auto_scaling_groups")
    for page in paginator.paginate():
        groups.extend(page.get("AutoScalingGroups", []))

    lc_names = sorted(
        {
            g["LaunchConfigurationName"]
            for g in groups
            if g.get("LaunchConfigurationName")
        }
    )
    lc_cache: Dict[str, Set[str]] = {}
    BATCH = 50
    for i in range(0, len(lc_names), BATCH):
        chunk = lc_names[i : i + BATCH]
        resp = call_with_backoff(
            lambda: asg_cli.describe_launch_configurations(
                LaunchConfigurationNames=chunk
            )
        )
        for lc in resp.get("LaunchConfigurations", []):
            sgs = set(lc.get("SecurityGroups") or [])
            lc_cache[lc["LaunchConfigurationName"]] = sgs

    lt_specs: Dict[Tuple[str, str, str], Dict] = {}
    for g in groups:
        for spec in iter_asg_lt_specs(g):
            lt_specs[normalize_lt_key(spec)] = spec

    lt_cache: Dict[Tuple[str, str, str], Set[str]] = {}
    for key, spec in lt_specs.items():
        ltid, ltname, ver = key
        kwargs = {"Versions": [ver]}
        if ltid:
            kwargs["LaunchTemplateId"] = ltid
        elif ltname:
            kwargs["LaunchTemplateName"] = ltname
        else:
            continue
        resp = call_with_backoff(
            lambda: ec2.describe_launch_template_versions(**kwargs)
        )
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
        lt_cache[key] = sgs

    return groups, lc_cache, lt_cache


def scan_asg_lc_lt_from_cache(
    sg_id: str,
    asg_groups: List[Dict],
    lc_cache: Dict[str, Set[str]],
    lt_cache: Dict[Tuple[str, str, str], Set[str]],
    usages: Set[Tuple[str, str]],
):
    for g in asg_groups:
        asg_name = g.get("AutoScalingGroupName")

        lcname = g.get("LaunchConfigurationName")
        if lcname and sg_id in (lc_cache.get(lcname) or set()):
            add_usage(usages, "ASG", asg_name)
            add_usage(usages, "LaunchConfig", lcname)

        def mark_if_match(spec):
            base = spec.get("LaunchTemplateSpecification") or spec
            key = (
                base.get("LaunchTemplateId") or "",
                base.get("LaunchTemplateName") or "",
                str(base.get("Version") or "$Default"),
            )
            sgs = lt_cache.get(key) or set()
            if sg_id in sgs:
                label = (
                    (
                        base.get("LaunchTemplateName")
                        or base.get("LaunchTemplateId")
                        or ""
                    )
                    + ":"
                    + key[2]
                )
                add_usage(usages, "ASG", asg_name)
                add_usage(usages, "LT", label)

        if g.get("LaunchTemplate"):
            mark_if_match(g["LaunchTemplate"])

        mip = g.get("MixedInstancesPolicy") or {}
        if mip.get("LaunchTemplate"):
            mark_if_match(mip["LaunchTemplate"])
        for ov in mip.get("Overrides") or []:
            lts = ov.get("LaunchTemplateSpecification")
            if lts:
                mark_if_match({"LaunchTemplateSpecification": lts})


# ===================== helpers =====================
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


def dedup_rows(rows: List[Dict]) -> List[Dict]:
    out, seen = [], set()
    for r in rows:
        key = (r.get("sg_id", ""), r.get("SGR_ID", ""), r.get("Direction", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ===================== per-SG worker =====================
def process_sg(
    sess,
    sg_id: str,
    idx: int,
    total: int,
    asg_groups: List[Dict],
    lc_cache: Dict[str, Set[str]],
    lt_cache: Dict[Tuple[str, str, str], Set[str]],
) -> List[Dict]:
    rows: List[Dict] = []
    log(f"[start] {idx}/{total} scanning {sg_id}")
    try:
        try:
            sg = describe_sg(sess, sg_id)
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            if "InvalidGroup" in code or "InvalidGroupId" in code:
                rows.append(
                    {
                        "sg_id": sg_id,
                        "SG_Name": "",
                        "SG_Description": "NOT_FOUND",
                        "SGR_ID": "",
                        "SGR_Description": "",
                        "Direction": "",
                        "CIDR": "",
                        "Port_Range": "",
                        "Resources": "",
                        "Usage_Status": "NOT_FOUND",
                    }
                )
                log(f"[done ] {idx}/{total} {sg_id} NOT_FOUND")
                return rows
            raise

        sg_name = sg.get("GroupName", "")
        sg_desc = sg.get("Description", "") or ""
        vpc_id = sg.get("VpcId")

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
        scan_asg_lc_lt_from_cache(sg_id, asg_groups, lc_cache, lt_cache, usages)

        resources_str = (
            "|".join(sorted([f"{t}:{n}" for t, n in usages])) if usages else ""
        )
        usage_status = "USED" if usages else "UNUSED"

        try:
            rules = list_sg_rules(sess, sg_id)
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            if "InvalidGroup" in code or "InvalidGroupId" in code:
                rows.append(
                    {
                        "sg_id": sg_id,
                        "SG_Name": sg_name,
                        "SG_Description": "NOT_FOUND_WHEN_LIST_RULES",
                        "SGR_ID": "",
                        "SGR_Description": "",
                        "Direction": "",
                        "CIDR": "",
                        "Port_Range": "",
                        "Resources": resources_str,
                        "Usage_Status": "NOT_FOUND",
                    }
                )
                log(f"[done ] {idx}/{total} {sg_id} NOT_FOUND_WHEN_LIST_RULES")
                return rows
            raise

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
        log(f"[done ] {idx}/{total} {sg_id} rules={len(rows)} status={usage_status}")
    except Exception as e:
        log(f"[error] {idx}/{total} {sg_id}: {e}")
    return rows


# ===================== main =====================
def main():
    ap = argparse.ArgumentParser(
        description="Audit ALL SGRs for SGs in sg_list and determine usage (concurrent, prefetch, robust, flexible loader)"
    )
    ap.add_argument("--region", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument(
        "--sg-list",
        required=True,
        help="Path to file with SG IDs or JSON lines that contain SG IDs",
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument(
        "--max-workers", type=int, default=8, help="Number of concurrent workers"
    )
    args = ap.parse_args()

    try:
        sess = session_for(args.profile, args.region)
    except Exception as e:
        log(f"[fatal] failed to create session: {e}")
        sys.exit(2)

    sg_ids = load_sg_ids(args.sg_list)
    if not sg_ids:
        log("sg_list yielded no SG IDs")
        sys.exit(2)

    log("[info ] prefetching ASG/LC/LT inventory...")
    try:
        asg_groups, lc_cache, lt_cache = prefetch_asg_inventory(sess)
        log(
            f"[info ] prefetch done: ASGs={len(asg_groups)}, LCs={len(lc_cache)}, LTs={len(lt_cache)}"
        )
    except Exception as e:
        log(f"[warn ] prefetch failed, ASG/LC/LT usage will be incomplete: {e}")
        asg_groups, lc_cache, lt_cache = [], {}, {}

    total = len(sg_ids)
    log(f"[info ] total SGs: {total}, max_workers: {args.max_workers}")

    all_rows: List[Dict] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {
            ex.submit(
                process_sg, sess, sg_id, i + 1, total, asg_groups, lc_cache, lt_cache
            ): sg_id
            for i, sg_id in enumerate(sg_ids)
        }
        for fut in as_completed(futures):
            rows = fut.result()
            if rows:
                all_rows.extend(rows)

    # 최종 중복 제거
    all_rows = dedup_rows(all_rows)

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
        w.writerows(all_rows)

    log(f"[info ] wrote {len(all_rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
