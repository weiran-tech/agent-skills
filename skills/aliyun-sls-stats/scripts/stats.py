#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
阿里云 SLS 日志统计脚本 - 支持多种日志格式

支持的日志格式：
- nginx: Nginx 标准格式 (request_uri, upstream_response_time)
- apisix: Apache APISIX 格式 (request_uri, upstream_response_time)
- custom: 自定义格式 (可配置字段映射)
"""

import json
import sys
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable


@dataclass
class LogFormat:
    """日志格式定义"""
    name: str
    description: str
    uri_field: str
    response_time_field: str
    additional_fields: Dict[str, str] = field(default_factory=dict)
    preprocess_hook: Optional[Callable[[Dict], Dict]] = None


# 预定义的日志格式
LOG_FORMATS = {
    "nginx": LogFormat(
        name="nginx",
        description="Nginx 标准日志格式",
        uri_field="request_uri",
        response_time_field="upstream_response_time",
    ),
    "apisix": LogFormat(
        name="apisix",
        description="Apache APISIX 日志格式",
        uri_field="request_uri",
        response_time_field="upstream_response_time",
    ),
    "mwcs": LogFormat(
        name="mwcs",
        description="Mogu 网关日志格式",
        uri_field="request_path",
        response_time_field="upstream_response_time",
    ),
    "k8s-ingress": LogFormat(
        name="k8s-ingress",
        description="Kubernetes Ingress Nginx 格式",
        uri_field="request_uri",
        response_time_field="request_length",
    ),
    "spring-boot": LogFormat(
        name="spring-boot",
        description="Spring Boot 应用日志",
        uri_field="uri",
        response_time_field="duration",
    ),
    "custom": LogFormat(
        name="custom",
        description="自定义日志格式（需通过 --field-uri 和 --field-time 指定字段名）",
        uri_field="request_uri",
        response_time_field="upstream_response_time",
    ),
}


def build_sls_query(log_format: LogFormat, days: int, threshold: int, host: Optional[str] = None) -> str:
    """构建 SLS 查询语句"""
    uri_field = log_format.uri_field
    time_field = log_format.response_time_field

    where_clause = f'host:"{host}"' if host else ""
    where_clause = f"{where_clause} |" if where_clause else ""

    return f"""{where_clause} SELECT
  request_uri,
  pv_per_day,
  ROUND(pv_inner * 100.0 / total_pv, 2) AS percentage,
  cumulative_percentage,
  avg_response_time,
  max_response_time
FROM (
  SELECT
    request_uri,
    pv_inner,
    pv_inner / {days} AS pv_per_day,
    total_pv,
    cumulative_pv,
    cumulative_percentage,
    LAG(cumulative_percentage) OVER (ORDER BY pv_inner DESC) AS prev_cumulative_percentage,
    avg_response_time,
    max_response_time
  FROM (
    SELECT
      {uri_field} AS request_uri,
      COUNT(*) AS pv_inner,
      SUM(COUNT(*)) OVER () AS total_pv,
      SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC ROWS UNBOUNDED PRECEDING) AS cumulative_pv,
      ROUND(SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC ROWS UNBOUNDED PRECEDING) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS cumulative_percentage,
      AVG(CAST({time_field} AS DOUBLE)) AS avg_response_time,
      MAX(CAST({time_field} AS DOUBLE)) AS max_response_time
    FROM log
    GROUP BY {uri_field}
  )
)
WHERE cumulative_percentage <= {threshold} OR
      (cumulative_percentage > {threshold} AND prev_cumulative_percentage <= {threshold})
ORDER BY pv_inner DESC
""".strip()


def execute_sls_query(project: str, logstore: str, region: str, from_ts: int, to_ts: int, query: str) -> Dict:
    """执行 SLS 查询"""
    cmd = [
        "aliyun", "sls", "GetLogs",
        "--project", project,
        "--logstore", logstore,
        "--region", region,
        "--from", str(from_ts),
        "--to", str(to_ts),
        "--line", "100",
        "--query", query,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parsed = json.loads(result.stdout)
        # 处理不同的返回格式：可能是字典或直接是列表
        if isinstance(parsed, list):
            return {"logs": parsed, "processedRows": len(parsed)}
        return parsed
    except subprocess.CalledProcessError as e:
        print(f"Error executing SLS query: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing SLS response: {e}", file=sys.stderr)
        print(f"Raw response: {result.stdout}", file=sys.stderr)
        sys.exit(1)


def format_number(num: float) -> str:
    """格式化数字"""
    if isinstance(num, str):
        num = float(num)
    return f"{num:,.0f}" if num.is_integer() else f"{num:,.2f}"


def print_markdown_result(result: Dict, days: int, threshold: int, format_name: str, title: str = "接口流量分布"):
    """输出 Markdown 格式结果"""
    from datetime import datetime

    logs = result.get("logs", [])
    total_processed = result.get("processedRows", 0)

    if not logs:
        print("未找到符合条件的日志数据。")
        return

    # 计算总 PV
    total_pv = sum(float(log.get("pv_per_day", 0)) * days for log in logs)

    print(f"## {title} - {datetime.now().strftime('%Y-%m-%d')}\n")
    print(f"> 统计范围：最近 {days} 天 | 数据来源：SLS ({format_name} 格式) | 分析方法：帕累托（前{threshold}%流量）\n")

    print("| 接口 | PV/天 | 占比 | 累计占比 | 平均响应时间 | 最大响应时间 |")
    print("|------|-------|------|----------|--------------|--------------|")

    for log in logs:
        uri = log.get("request_uri", "N/A")
        pv_per_day = format_number(float(log.get("pv_per_day", 0)))
        percentage = f"{log.get('percentage', 0)}%"
        cumulative_percentage = f"{log.get('cumulative_percentage', 0)}%"
        avg_time = f"{float(log.get('avg_response_time', 0)):.2f}"
        max_time = f"{float(log.get('max_response_time', 0)):.2f}"

        print(f"| {uri} | {pv_per_day} | {percentage} | {cumulative_percentage} | {avg_time} | {max_time} |")

    print("\n**汇总**")
    print(f"- 总 PV：{format_number(total_pv)}")
    print(f"- 上榜接口数：{len(logs)} 个")
    print(f"- 处理日志行数：{format_number(total_processed)}")
    print(f"- 前 {threshold}% 流量集中在以上接口")


def list_formats():
    """列出支持的日志格式"""
    print("支持的日志格式：\n")
    print("| 格式名称 | 描述 | URI 字段 | 响应时间字段 |")
    print("|----------|------|----------|--------------|")
    for fmt in LOG_FORMATS.values():
        print(f"| {fmt.name} | {fmt.description} | {fmt.uri_field} | {fmt.response_time_field} |")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阿里云 SLS 日志统计 - 支持多种日志格式")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # list-formats 命令
    subparsers.add_parser("list-formats", help="列出支持的日志格式")

    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="执行 SLS 日志统计分析")
    analyze_parser.add_argument("--project", required=True, help="SLS Project 名称")
    analyze_parser.add_argument("--logstore", required=True, help="SLS Logstore 名称")
    analyze_parser.add_argument("--region", default="cn-hangzhou", help="SLS 地域（默认: cn-hangzhou）")
    analyze_parser.add_argument("--host", help="Hostname 过滤")
    analyze_parser.add_argument("--format", default="nginx", choices=LOG_FORMATS.keys(), help="日志格式（默认: nginx）")
    analyze_parser.add_argument("--days", type=int, default=7, help="统计天数（默认: 7）")
    analyze_parser.add_argument("--threshold", type=int, default=50, help="帕累托分析阈值 %%（默认: 50）")
    analyze_parser.add_argument("--field-uri", help="自定义 URI 字段名（仅 custom 格式有效）")
    analyze_parser.add_argument("--field-time", help="自定义响应时间字段名（仅 custom 格式有效）")
    analyze_parser.add_argument("--title", default="接口流量分布", help="报告标题（默认: 接口流量分布）")
    analyze_parser.add_argument("--dry-run", action="store_true", help="仅打印查询语句，不执行")

    args = parser.parse_args()

    if args.command == "list-formats":
        list_formats()
        return

    if args.command == "analyze":
        # 获取日志格式配置
        log_format = LOG_FORMATS[args.format]

        # 处理自定义格式
        if args.format == "custom":
            if args.field_uri:
                log_format.uri_field = args.field_uri
            if args.field_time:
                log_format.response_time_field = args.field_time

        # 计算时间范围
        import time
        to_ts = int(time.time())
        from_ts = to_ts - (args.days * 24 * 60 * 60)

        # 构建查询
        query = build_sls_query(log_format, args.days, args.threshold, args.host)

        if args.dry_run:
            print("SLS 查询语句：")
            print("=" * 80)
            print(query)
            print("=" * 80)
            return

        # 检查 aliyun-cli 配置
        try:
            subprocess.run(["aliyun", "configure", "list"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("错误: aliyun-cli 未配置或未安装。", file=sys.stderr)
            print("请执行: aliyun configure", file=sys.stderr)
            sys.exit(1)

        # 执行查询
        result = execute_sls_query(
            project=args.project,
            logstore=args.logstore,
            region=args.region,
            from_ts=from_ts,
            to_ts=to_ts,
            query=query,
        )

        # 输出结果
        print_markdown_result(
            result=result,
            days=args.days,
            threshold=args.threshold,
            format_name=log_format.name,
            title=args.title,
        )


if __name__ == "__main__":
    main()
