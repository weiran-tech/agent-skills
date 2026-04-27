#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests",
# ]
# ///
"""
云效未排期需求导出脚本
"""

import json
import os
import sys
from datetime import datetime, timezone

ORGANIZATION_ID = "62ac9a6364c8a06be2d5db5d"

# 未完成状态ID列表
INCOMPLETE_STATUS_IDS = {
    "28", "100005", "30", "34", "32", "625489",
    "154395", "165115", "100010", "156603",
    "307012", "142838", "100011", "100012"
}

# 已完成状态关键词
COMPLETED_STATUS_KEYWORDS = ["已完成", "已关闭", "已验收", "已发布", "已上线"]


def search_projects(organization_id: str, project_name: str) -> list:
    """搜索项目"""
    # 这里需要调用 MCP 工具
    pass


def search_workitems(organization_id: str, space_id: str, page: int = 1, per_page: int = 200) -> dict:
    """查询工作项"""
    pass


def is_no_sprint(item: dict) -> bool:
    """检查是否没有迭代"""
    sprint = item.get("sprint")
    if sprint is None or sprint == "":
        return True
    if isinstance(sprint, dict) and (not sprint.get("id") or sprint.get("id") == ""):
        return True
    if isinstance(sprint, str) and sprint == "":
        return True
    return False


def is_incomplete_status(item: dict) -> bool:
    """检查是否为未完成状态"""
    status_id = str(item.get("status", ""))
    status_name = item.get("statusName", "") or item.get("status_name", "") or ""

    # 检查状态名称是否包含已完成关键词
    for keyword in COMPLETED_STATUS_KEYWORDS:
        if keyword in status_name:
            return False

    # 检查状态ID是否在未完成列表中
    if status_id in INCOMPLETE_STATUS_IDS:
        return True

    # 如果状态ID不在列表中但状态名称也不包含已完成关键词，也视为未完成
    return True


def is_product_requirement(item: dict) -> bool:
    """检查是否为产品类需求"""
    workitem_type = item.get("workitemType", {})
    type_name = workitem_type.get("name", "") if isinstance(workitem_type, dict) else str(workitem_type)
    return "产品" in type_name


def has_tag(item: dict, tag_name: str) -> bool:
    """检查是否包含指定标签"""
    tags = item.get("tags", []) or []
    for tag in tags:
        if isinstance(tag, dict):
            if tag_name in tag.get("name", "") or tag_name in tag.get("value", ""):
                return True
        elif isinstance(tag, str):
            if tag_name in tag:
                return True
    return False


def main():
    # 参数解析
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    project_name = None
    req_type = "product"
    tag_filter = None
    output_file = "report/temp/unplanned_reqs.json"

    for arg in args:
        if arg.startswith("project="):
            project_name = arg.split("=", 1)[1]
        elif arg.startswith("type="):
            req_type = arg.split("=", 1)[1]
        elif arg.startswith("tag="):
            tag_filter = arg.split("=", 1)[1]
        elif arg.startswith("output="):
            output_file = arg.split("=", 1)[1]

    if not project_name:
        print("错误: 请提供项目名称")
        print("用法: uv run stats.py project=客诉 type=product tag=氪金兽")
        sys.exit(1)

    print(f"开始导出未排期需求...")
    print(f"项目名称: {project_name}")
    print(f"需求类型: {req_type}")
    if tag_filter:
        print(f"标签筛选: {tag_filter}")

    # 注意: 实际执行时需要通过 MCP 工具调用
    # 这里输出需要执行的操作
    print(f"\n需要执行以下步骤:")
    print(f"1. 查询项目列表，获取 '{project_name}' 项目的 spaceId")
    print(f"2. 使用 spaceId 查询所有需求工作项（分页处理）")
    print(f"3. 本地筛选：没有迭代 + 产品类需求 + 未完成状态 + 标签筛选")
    print(f"4. 输出结果到 {output_file}")

    # 输出 JSON 格式的配置供 MCP 调用使用
    config = {
        "organizationId": ORGANIZATION_ID,
        "project_name": project_name,
        "req_type": req_type,
        "tag_filter": tag_filter,
        "output_file": output_file
    }
    print(f"\n配置: {json.dumps(config, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
