#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
将 MCP 云效工具返回的 workitems 数据转换为 stats.py 兼容的格式
处理时间戳转换（毫秒 → ISO 8601 格式字符串）
"""

import json
import sys
from datetime import datetime, timezone
from typing import Dict, List


def timestamp_to_iso(ts: int) -> str:
    """将毫秒时间戳转换为 ISO 8601 格式字符串"""
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def convert_mcp_to_stats_format(mcp_items: List[Dict]) -> List[Dict]:
    """将 MCP 返回的 items 转换为 stats.py 兼容的格式"""
    converted = []
    for item in mcp_items:
        # 处理负责人
        assigned_to_list = []
        assigned_to = item.get("assignedTo")
        if assigned_to:
            assigned_to_list = [{"name": assigned_to.get("name", "")}]

        # 处理优先级
        priority_identifier = ""
        for cf in item.get("customFieldValues", []):
            if cf.get("fieldName") == "优先级" and cf.get("values"):
                priority_identifier = cf["values"][0].get("identifier", "")
                break

        converted.append({
            "identifier": item.get("id", ""),
            "subject": item.get("subject", ""),
            "statusStageIdentifier": str(item.get("statusStageId", "")),
            "statusIdentifier": str(item.get("status", {}).get("id", "")),
            "assignedTo": assigned_to_list,
            "priorityIdentifier": priority_identifier,
            "gmtCreate": timestamp_to_iso(item.get("gmtCreate", 0)),
            "gmtStatusChanged": timestamp_to_iso(item.get("gmtStatusChanged", 0)),
        })

    return converted


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 convert_mcp.py <input-json-file> [output-json-file]")
        print("Input format: MCP search_workitems 返回的 JSON 数据")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    with open(input_file, "r") as f:
        data = json.load(f)

    # 支持两种输入格式：直接是 items 列表，或包含 items 字段的对象
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items", [])
        if not items and "workitems" in data:
            items = data.get("workitems", [])
    else:
        items = []

    converted = convert_mcp_to_stats_format(items)

    if output_file:
        with open(output_file, "w") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)
        print(f"Converted {len(converted)} items to {output_file}")
    else:
        print(json.dumps(converted, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
