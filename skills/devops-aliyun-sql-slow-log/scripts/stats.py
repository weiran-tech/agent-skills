#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
阿里云 RDS 慢 SQL 统计脚本

调用 aliyun-cli-rds describe-slow-log-records API，按 SQLHash 分组聚合，
输出 Markdown 格式的慢 SQL TOP N 排行榜。
"""

import json
import os
import sys
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone


@dataclass
class SQLHashStats:
    """按 SQLHash 聚合的统计信息"""
    sql_hash: str
    max_time_ms: int = 0
    count: int = 0
    total_exec: int = 0
    total_parse_rows: int = 0
    total_return_rows: int = 0
    total_lock_ms: int = 0
    sample_sql: str = ""
    db_name: str = ""
    engine: str = ""
    host_addrs: Set[str] = field(default_factory=set)
    first_time: str = ""
    last_time: str = ""


def format_number(num) -> str:
    """格式化数字（千分位）"""
    if isinstance(num, str):
        num = float(num)
    return f"{num:,.0f}" if isinstance(num, (int, float)) and num.is_integer() else f"{num:,.2f}"


ENV_PROFILE = "ALIYUN_PROFILE"


def resolve_profile() -> str:
    """从环境变量 ALIYUN_PROFILE 读取 aliyun-cli profile。

    不猜测、不回退到默认 profile —— 未设置即终止。
    默认 profile 的权限范围通常与目标实例不一致，静默回退会取到错误的数据。
    """
    profile = os.environ.get(ENV_PROFILE, "").strip()
    if profile:
        return profile

    print(f"错误: 环境变量 {ENV_PROFILE} 未设置。", file=sys.stderr)
    print("", file=sys.stderr)
    print("本脚本不会猜测或回退到 aliyun-cli 默认 profile，请显式指定：", file=sys.stderr)
    print(f"    export {ENV_PROFILE}=<profile 名>", file=sys.stderr)
    print("", file=sys.stderr)
    print("当前机器可用的 profile：", file=sys.stderr)
    try:
        out = subprocess.run(["aliyun", "configure", "list"],
                             capture_output=True, text=True, check=True).stdout
        print(out, file=sys.stderr)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("    (无法执行 `aliyun configure list`，请确认 aliyun-cli 已安装)", file=sys.stderr)
    print("注意: `configure list` 中的 Valid 只表示凭证格式正确，不代表有目标资源的授权。",
          file=sys.stderr)
    sys.exit(2)


def classify_aliyun_error(stderr: str) -> str:
    """把 aliyun-cli 报错翻译成可执行的修复指引。"""
    s = stderr or ""
    if "AccessKeyId not found" in s:
        return ("AccessKey 已被删除或轮换，凭证本身已失效。\n"
                "    修复: aliyun configure --profile $" + ENV_PROFILE)
    if "denied by sts or ram" in s or "Forbidden" in s or "NoPermission" in s:
        return ("凭证有效，但 RAM 未授予所需权限。\n"
                "    修复: 为该 RAM 用户/角色补上 AliyunRDSReadOnlyAccess，"
                "或针对目标实例单独授予 rds:DescribeSlowLogRecords。")
    if "InvalidAccessKeySecret" in s or "SignatureDoesNotMatch" in s:
        return ("AccessKey Secret 不匹配。\n"
                "    修复: aliyun configure --profile $" + ENV_PROFILE)
    if "InvalidDBInstanceId" in s or "NotFound" in s:
        return "RDS 实例 ID 不存在或不在该地域，请核对 instance-id 与 region。"
    if "not found" in s and "plugin" in s.lower():
        return ("aliyun-cli-rds 插件未安装。\n"
                "    修复: aliyun plugin install --names aliyun-cli-rds && hash -r")
    return "请根据上方原始错误排查。"


def preflight_rds(instance_id: str, region: str, profile: str) -> None:
    """对目标实例打一次最小慢日志查询，确认「凭证 + 授权 + 插件」三者均就绪。

    `aliyun configure list` 只能确认凭证格式，无法确认授权，因此必须实打一次。
    校验不通过直接终止，不进入下一步。
    """
    now = int(time.time())
    dt_to = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    dt_from = datetime.fromtimestamp(now - 3600, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    cmd = [
        "aliyun", "rds", "describe-slow-log-records",
        "--region", region,
        "--db-instance-id", instance_id,
        "--start-time", dt_from,
        "--end-time", dt_to,
        "--page-size", "30",
        "--profile", profile,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print("错误: 未找到 aliyun-cli，请先安装。", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        print("=" * 72, file=sys.stderr)
        print(f"权限校验失败 — profile={profile} 无法读取 {region}/{instance_id} 的慢日志",
              file=sys.stderr)
        print("=" * 72, file=sys.stderr)
        print((e.stderr or "").strip(), file=sys.stderr)
        print("", file=sys.stderr)
        print("原因: " + classify_aliyun_error(e.stderr), file=sys.stderr)
        print("", file=sys.stderr)
        print("校验未通过，已终止（不会继续执行统计查询）。", file=sys.stderr)
        sys.exit(2)


def call_rds_api(
    instance_id: str,
    region: str,
    start_time: str,
    end_time: str,
    db_name: Optional[str] = None,
    page_size: int = 100,
    profile: str = "",
) -> Dict:
    """调用 RDS describe-slow-log-records API"""
    cmd = [
        "aliyun", "rds", "describe-slow-log-records",
        "--region", region,
        "--db-instance-id", instance_id,
        "--start-time", start_time,
        "--end-time", end_time,
        "--page-size", str(page_size),
    ]
    if db_name:
        cmd.extend(["--db-name", db_name])
    if profile:
        cmd.extend(["--profile", profile])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parsed = json.loads(result.stdout)
        return parsed
    except subprocess.CalledProcessError as e:
        print(f"Error calling RDS API: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing RDS response: {e}", file=sys.stderr)
        print(f"Raw response: {result.stdout}", file=sys.stderr)
        sys.exit(1)


def aggregate_records(records: List[Dict]) -> List[SQLHashStats]:
    """按 SQLHash 聚合慢 SQL 记录"""
    hash_stats: Dict[str, SQLHashStats] = {}

    for r in records:
        h = r["SQLHash"]
        if h not in hash_stats:
            hash_stats[h] = SQLHashStats(sql_hash=h)
        s = hash_stats[h]

        qt = r.get("QueryTimeMS", 0)
        if qt > s.max_time_ms:
            s.max_time_ms = qt

        exec_times = r.get("QueryTimes", 1) or 1
        s.total_exec += exec_times
        s.count += 1
        s.total_parse_rows += r.get("ParseRowCounts", 0)
        s.total_return_rows += r.get("ReturnRowCounts", 0)
        s.total_lock_ms += r.get("LockTimeMS", 0)

        if not s.sample_sql:
            s.sample_sql = r.get("SQLText", "")
        if s.db_name == "":
            s.db_name = r.get("DBName", "")
        if s.engine == "":
            s.engine = r.get("Engine", "")

        addr = r.get("HostAddress", "").strip().replace("@", "")
        s.host_addrs.add(addr)

        et = r.get("ExecutionStartTime", "")
        if not s.first_time or et < s.first_time:
            s.first_time = et
        if et > s.last_time:
            s.last_time = et

    return sorted(hash_stats.values(), key=lambda x: x.max_time_ms, reverse=True)


def build_report(
    stats_list: List[SQLHashStats],
    days: int,
    title: str,
    top_n: int = 20,
    instance_id: str = "",
    region: str = "",
    total_records: int = 0,
) -> str:
    """生成 Markdown 报告"""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d")

    meta_parts = [f"最近 {days} 天"]
    if instance_id:
        meta_parts.append(f"实例：{instance_id}")
    if region:
        meta_parts.append(region)

    lines.append(f"## {title} - {now}")
    lines.append("")
    lines.append("> 统计范围：" + " | ".join(meta_parts) + " | 原始记录：" + str(total_records) + " 条")
    lines.append("")

    # 展示前 total_unique 条中取 top_N
    unique_count = len(stats_list)
    display = stats_list[:top_n]

    # ---- TOP 排行表格 ----
    lines.append(f"### TOP {len(display)} 最慢 SQL 排行")
    lines.append("")
    lines.append("| 排名 | 最大耗时(ms) | 出现次数 | 累计执行 | 平均扫描行数 | SQLHash | 数据库 |")
    lines.append("|------|-------------|---------|---------|-------------|---------|--------|")

    for i, s in enumerate(display, 1):
        avg_parse = s.total_parse_rows // s.count if s.count else 0
        lines.append(
            f"| {i} | {format_number(s.max_time_ms)} | {s.count} "
            f"| {format_number(s.total_exec)} | {format_number(avg_parse)} "
            f"| {s.sql_hash[:8]} | {s.db_name} |"
        )

    lines.append("")

    # ---- 详细信息 ----
    lines.append("### 详细信息\n")
    for i, s in enumerate(display, 1):
        # 格式化时间范围
        first_str = _format_ts(s.first_time)
        last_str = _format_ts(s.last_time)
        hosts = ", ".join(sorted(s.host_addrs)[:3])

        sql_snippet = s.sample_sql[:300].replace("`", "") if s.sample_sql else "N/A"

        lines.append(f"[{i}] Hash: `{s.sql_hash}` | 最大耗时: **{format_number(s.max_time_ms)}ms** "
                     f"| 出现: {s.count} 次 | 累计执行: {format_number(s.total_exec)} 次")
        if s.total_lock_ms > 0:
            lines.append(f"   锁等待总计: {format_number(s.total_lock_ms)}ms | 扫描总行数: {format_number(s.total_parse_rows)}")
        lines.append(f"   时间范围: {first_str} ~ {last_str} | 来源主机: {hosts}")
        lines.append(f"   SQL: {sql_snippet}...")
        lines.append("")

    # ---- 汇总 ----
    lines.append("---")
    lines.append("**汇总**")
    lines.append(f"- 涉及不同 SQL 数：{unique_count} 个")
    lines.append(f"- 原始慢 SQL 记录：{total_records} 条")
    lines.append(f"- 最热 SQL（SQLHash: {stats_list[0].sql_hash if stats_list else 'N/A'}）：出现 {stats_list[0].count if stats_list else 0} 次，最大耗时 {format_number(stats_list[0].max_time_ms)}ms" if stats_list else "- 无数据")

    return "\n".join(lines)


def _format_ts(ts: str) -> str:
    """格式化 ISO 时间为可读字符串"""
    if not ts:
        return "N/A"
    try:
        return ts.replace("T", " ").replace("Z", "")[:19]
    except Exception:
        return ts


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阿里云 RDS 慢 SQL 统计")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    analyze_parser = subparsers.add_parser("analyze", help="分析 RDS 慢 SQL")
    analyze_parser.add_argument("--instance-id", required=True, help="RDS 实例 ID")
    analyze_parser.add_argument("--region", default="cn-hangzhou", help="地域 ID（默认: cn-hangzhou）")
    analyze_parser.add_argument("--db-name", help="数据库名过滤")
    analyze_parser.add_argument("--days", type=int, default=7, help="统计天数（默认: 7）")
    analyze_parser.add_argument("--max-time-threshold", type=int, default=0, help="仅显示最大耗时 >= 此值(ms) 的 SQL")
    analyze_parser.add_argument("--page-size", type=int, default=100, choices=range(30, 101), help="每页记录数（30~100，默认: 100）")
    analyze_parser.add_argument("--top-N", type=int, default=20, help="输出前 N 个不同 SQL（默认: 20）")
    analyze_parser.add_argument("--title", default="慢 SQL 统计报告", help="报告标题（默认: 慢 SQL 统计报告）")
    analyze_parser.add_argument("--dry-run", action="store_true", help="仅打印 API 调用信息，不执行")

    args = parser.parse_args()

    if args.command != "analyze":
        parser.print_help()
        return

    # 确保 rds 插件已加载
    try:
        subprocess.run(["hash", "-r"], capture_output=True, check=True)
    except Exception:
        pass

    # 计算时间范围（UTC 格式 yyyy-MM-ddTHH:mmZ）
    to_ts = int(time.time())
    from_ts = to_ts - (args.days * 24 * 60 * 60)
    dt_to = datetime.fromtimestamp(to_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    dt_from = datetime.fromtimestamp(from_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    if args.dry_run:
        print("API 调用预览：")
        print("=" * 80)
        print(f"Command: aliyun rds describe-slow-log-records --region {args.region} --db-instance-id {args.instance_id} --start-time {dt_from} --end-time {dt_to} --page-size {args.page_size}")
        if args.db_name:
            print(f"  --db-name {args.db_name}")
        print("=" * 80)
        return

    # 解析 profile（仅从 ALIYUN_PROFILE 取，缺失即终止）
    profile = resolve_profile()

    # 权限校验门禁：对目标实例实打一次最小查询，不通过则终止，不进入下一步
    preflight_rds(args.instance_id, args.region, profile)

    # 调用 API
    resp = call_rds_api(
        instance_id=args.instance_id,
        region=args.region,
        start_time=dt_from,
        end_time=dt_to,
        db_name=args.db_name,
        page_size=args.page_size,
        profile=profile,
    )

    records = resp.get("Items", {}).get("SQLSlowRecord", [])
    total_records = len(records)

    if not records:
        print("未找到符合条件的慢 SQL 记录。")
        return

    # 聚合
    all_stats = aggregate_records(records)

    # 应用最大耗时阈值过滤
    if args.max_time_threshold > 0:
        all_stats = [s for s in all_stats if s.max_time_ms >= args.max_time_threshold]

    # 生成报告
    report = build_report(
        stats_list=all_stats,
        days=args.days,
        title=args.title,
        top_n=args.top_N,
        instance_id=args.instance_id,
        region=args.region,
        total_records=total_records,
    )
    print(report)


if __name__ == "__main__":
    main()
