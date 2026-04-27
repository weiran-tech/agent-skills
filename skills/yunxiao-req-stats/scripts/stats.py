#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
统计云效项目中 技术类需求 类型工作项
输入：aliyun devops ListWorkitems 合并后的 workitems 列表（JSON 文件）
统计三个指标：
1. 当前所有未解决研发需求数量
2. 当前月份创建的研发需求总数量
3. 当前月份关闭的研发需求总数量
"""

import json
import sys
from typing import Dict, List

# 已关闭阶段标识（已完成/已取消），其余视为未解决
CLOSED_STAGES = {"4", "5"}

PRIORITY_MAP = {
    "1": "紧急",
    "2": "高",
    "3": "中",
    "4": "低",
}


def analyze_stats(json_file_path: str, year: int, month: int) -> Dict:
    month_str = f"{year}-{month:02d}"

    with open(json_file_path, "r") as f:
        items: List[Dict] = json.load(f)

    total = len(items)
    unresolved: List[Dict] = []
    created_this_month: List[Dict] = []
    closed_this_month: List[Dict] = []

    for item in items:
        stage = str(item.get("statusStageIdentifier", ""))
        created_at = (item.get("gmtCreate") or "")[:7]
        changed_at = (item.get("gmtStatusChanged") or "")[:7]

        if stage not in CLOSED_STAGES:
            unresolved.append(item)
        if created_at == month_str:
            created_this_month.append(item)
        if stage in CLOSED_STAGES and changed_at == month_str:
            closed_this_month.append(item)

    return {
        "total": total,
        "unresolved": unresolved,
        "created": created_this_month,
        "closed": closed_this_month,
        "year": year,
        "month": month,
    }


def print_result(stats: Dict, organization_id: str = ""):
    year, month = stats["year"], stats["month"]
    unresolved = stats["unresolved"]
    closed_count = stats["total"] - len(unresolved)

    print(f"""
| 统计项 | 数量 |
|--------|------|
| **当前所有未解决技术需求** | **{len(unresolved)}** |
| **{year}年{month}月创建的技术需求** | **{len(stats['created'])}** |
| **{year}年{month}月关闭的技术需求** | **{len(stats['closed'])}** |

**统计说明:**
- 项目中总共有 **{stats['total']}** 个"技术需求"类型工作项
- **{closed_count}** 个已经关闭，**{len(unresolved)}** 个仍处于未解决状态
""")

    if unresolved:
        print("**问题清单:**\n")
        print("| ID | 标题 | 负责人 | 优先级 | 链接 |")
        print("|-----|------|-----|------|------|")
        for item in unresolved:
            identifier = item.get("identifier", "")
            subject = item.get("subject", "")
            assigned = item.get("assignedTo") or []
            assignee = assigned[0].get("name", "") if assigned else ""
            priority = PRIORITY_MAP.get(str(item.get("priorityIdentifier", "")), "")
            if organization_id and identifier:
                link = f"https://devops.aliyun.com/organization/{organization_id}/work/workitems/{identifier}"
            elif identifier:
                link = identifier
            else:
                link = ""
            print(f"| {identifier} | {subject} | {assignee} | {priority} | {link} |")


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <json-file> <year> <month> [organization_id]")
        sys.exit(1)

    json_file = sys.argv[1]
    year = int(sys.argv[2])
    month = int(sys.argv[3])
    organization_id = sys.argv[4] if len(sys.argv) > 4 else ""

    stats = analyze_stats(json_file, year, month)
    print_result(stats, organization_id)


if __name__ == "__main__":
    main()
