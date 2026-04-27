#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
统计云效项目中指定迭代的需求评审结果
输入：MCP 转换后的工作项列表（JSON 文件）
用法：python3 stats.py <json-file> <sprint_id> <sprint_name> <organization_id>
"""

import json
import sys
from typing import Dict, List
from collections import defaultdict

REVIEW_CONCLUSION_KEYS = [
    "reviewConclusion",
    "评审结论",
    "conclusion",
    "结论",
    "reviewResult",
    "评审结果",
]


def get_review_conclusion(item: Dict) -> str:
    custom_fields = item.get("customFieldValues") or {}
    for key in REVIEW_CONCLUSION_KEYS:
        if key in custom_fields:
            value = custom_fields[key]
            if isinstance(value, str):
                return value.strip()
            return str(value)
    return ""


def is_passed(conclusion: str) -> bool:
    if not conclusion:
        return False
    return "通过" in conclusion or "pass" in conclusion.lower() or "approved" in conclusion.lower()


def analyze_stats(json_file_path: str, sprint_id: str, sprint_name: str = "") -> Dict:
    with open(json_file_path, "r") as f:
        items: List[Dict] = json.load(f)

    passed_items: List[Dict] = []
    failed_items: List[Dict] = []
    by_assignee = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})

    for item in items:
        conclusion = get_review_conclusion(item)
        passed = is_passed(conclusion)

        assigned = item.get("assignedTo") or []
        assignee = assigned[0].get("name", "未分配") if assigned else "未分配"

        by_assignee[assignee]["total"] += 1
        if passed:
            passed_items.append(item)
            by_assignee[assignee]["passed"] += 1
        else:
            failed_items.append(item)
            by_assignee[assignee]["failed"] += 1

    total = len(items)
    pass_rate = (len(passed_items) / total * 100) if total > 0 else 0.0

    return {
        "sprint_id": sprint_id,
        "sprint_name": sprint_name or sprint_id,
        "total": total,
        "passed": passed_items,
        "failed": failed_items,
        "pass_rate": round(pass_rate, 1),
        "by_assignee": dict(by_assignee),
    }


def print_result(stats: Dict, organization_id: str = ""):
    total = stats["total"]
    passed = stats["passed"]
    failed = stats["failed"]
    pass_rate = stats["pass_rate"]
    sprint_name = stats.get("sprint_name", "")

    print(f"## {sprint_name} 迭代评审概况\n")
    print("| 统计项           | 数量     |")
    print("| ---------------- | -------- |")
    print(f"| **迭代总需求数** | **{total}** |")
    print(f"| **评审通过数**   | **{len(passed)}** |")
    print(f"| **评审未通过数** | **{len(failed)}** |")
    print(f"| **评审通过率**   | **{pass_rate}%** |")
    print()

    print("## 按负责人通过率统计\n")
    print("| 负责人 | 总需求数 | 通过数 | 未通过数 | 通过率 |")
    print("| ------ | -------- | ------ | -------- | ------ |")
    for assignee, data in sorted(stats["by_assignee"].items(), key=lambda x: -x[1]["total"]):
        rate = round(data["passed"] / data["total"] * 100, 1) if data["total"] > 0 else 0.0
        print(f"| {assignee} | {data['total']} | {data['passed']} | {data['failed']} | {rate}% |")
    print()

    if not failed:
        return

    def get_item_link(item: Dict) -> str:
        identifier = item.get("identifier", "")
        if organization_id and identifier:
            return f"https://devops.aliyun.com/organization/{organization_id}/work/workitems/{identifier}"
        return identifier or ""

    def get_assignee_name(item: Dict) -> str:
        assigned = item.get("assignedTo") or []
        return assigned[0].get("name", "未分配") if assigned else "未分配"

    print("## 评审未通过清单\n")
    # 按负责人分组输出
    by_assignee_failed: Dict[str, List[Dict]] = defaultdict(list)
    for item in failed:
        by_assignee_failed[get_assignee_name(item)].append(item)

    for assignee, items in sorted(by_assignee_failed.items()):
        print(f"**{assignee}提交的需求：**\n")
        print("| ID  | 标题 | 评审结论 | 链接 |")
        print("| --- | ---- | -------- | ---- |")
        for item in items:
            identifier = item.get("identifier", "")
            subject = item.get("subject", "")
            conclusion = get_review_conclusion(item) or "未评审"
            link = get_item_link(item)
            print(f"| {identifier} | {subject} | {conclusion} | {link} |")
        print()


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <json-file> <sprint_id> [sprint_name] [organization_id]")
        sys.exit(1)

    json_file = sys.argv[1]
    sprint_id = sys.argv[2]
    sprint_name = sys.argv[3] if len(sys.argv) > 3 else ""
    organization_id = sys.argv[4] if len(sys.argv) > 4 else ""

    stats = analyze_stats(json_file, sprint_id, sprint_name)
    print_result(stats, organization_id)


if __name__ == "__main__":
    main()
