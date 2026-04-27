#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
统计云效项目中 线上故障 类型工作项
统计三个指标：
1. 当前所有未解决线上故障数量
2. 当前月份创建的线上故障总数量
3. 当前月份关闭的线上故障总数量

固定配置：
- 已关闭 statusId: 100085
"""

import json
import sys
import datetime
from typing import Dict, List
from collections import defaultdict


def get_month_timestamp_range(year: int, month: int) -> tuple[int, int]:
    """获取指定月份的时间戳范围（毫秒）"""
    start = datetime.datetime(year, month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    if month == 12:
        next_month = datetime.datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    else:
        next_month = datetime.datetime(year, month + 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end = next_month - datetime.timedelta(milliseconds=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def load_workitems(json_file_path: str) -> List[Dict]:
    """加载工作项数据，支持多种格式"""
    with open(json_file_path, 'r') as f:
        content = f.read()

    data = json.loads(content)

    # 格式 1: 嵌套在 [{"text": "..."}] 中（旧 MCP 格式）
    if isinstance(data, list) and len(data) > 0 and 'text' in data[0]:
        actual_json_str = data[0]['text']
        result = json.loads(actual_json_str)
        return result.get('items', [])

    # 格式 2: 直接包含 items 字段
    if isinstance(data, dict) and 'items' in data:
        return data.get('items', [])

    # 格式 3: 直接是 items 列表
    if isinstance(data, list):
        return data

    return []


def get_priority_emoji(priority: str) -> str:
    """根据优先级获取 Emoji"""
    priority_map = {
        '紧急': '🔴',
        '高': '🟠',
        '中': '🟡',
        '低': '🟢',
        '最高': '🔴',
        '较高': '🟠',
        '普通': '🟡',
        '较低': '🟢',
    }
    for key, emoji in priority_map.items():
        if key in priority:
            return emoji
    return '⚪'


def get_severity_emoji(severity: str) -> str:
    """根据严重程度获取 Emoji"""
    severity_map = {
        '致命': '💥',
        '严重': '🔥',
        '一般': '⚠️',
        '轻微': '📝',
        '1-': '💥',
        '2-': '🔥',
        '3-': '⚠️',
        '4-': '📝',
    }
    for key, emoji in severity_map.items():
        if key in severity:
            return emoji
    return '⚪'


def get_status_emoji(status: str) -> str:
    """根据状态获取 Emoji"""
    status_map = {
        '待确认': '❓',
        '待处理': '📋',
        '处理中': '🔧',
        '进行中': '🔧',
        '已修复': '✅',
        '已解决': '✅',
        '挂起中': '⏸️',
        '暂停': '⏸️',
        '已关闭': '🔒',
        '开发中': '💻',
        '测试中': '🧪',
        '验证中': '🔍',
        '发布中': '🚀',
    }
    for key, emoji in status_map.items():
        if key in status:
            return emoji
    return '📍'


def get_custom_field_value(item: Dict, field_id: str) -> str:
    """获取自定义字段值"""
    custom_fields = item.get('customFieldValues', [])
    for field in custom_fields:
        if field.get('fieldId') == field_id:
            values = field.get('values', [])
            if values:
                return values[0].get('displayValue', '')
    return ''


def analyze_stats(json_file_path: str, year: int, month: int) -> Dict:
    """分析统计数据"""
    items = load_workitems(json_file_path)

    # 固定配置
    online_fault_type_id = 'bba77181ef64f834248a0175'  # 线上故障
    closed_status_ids = {'100085'}  # 已关闭

    start_ts, end_ts = get_month_timestamp_range(year, month)

    total_online_fault = 0
    unresolved_items = []
    current_month_created = 0
    current_month_closed = 0

    for item in items:
        workitem_type_id = item.get('workitemType', {}).get('id')
        if workitem_type_id != online_fault_type_id:
            continue

        total_online_fault += 1

        # Check if created in current month
        gmt_create = item.get('gmtCreate', 0)
        if start_ts <= gmt_create <= end_ts:
            current_month_created += 1

        status_id = str(item.get('status', {}).get('id', ''))
        update_status_at = item.get('updateStatusAt', 0)

        # Check if closed in current month
        if status_id in closed_status_ids and start_ts <= update_status_at <= end_ts:
            current_month_closed += 1

        # Check if unresolved
        if status_id not in closed_status_ids:
            unresolved_items.append(item)

    return {
        'total_online_fault': total_online_fault,
        'unresolved': len(unresolved_items),
        'unresolved_items': unresolved_items,
        'current_month_created': current_month_created,
        'current_month_closed': current_month_closed,
        'year': year,
        'month': month
    }


def print_result(stats: Dict, organization_id: str = ""):
    """打印结果 - 按负责人分组，带 Emoji"""
    print(f"""
# 线上故障统计结果

| 统计项 | 数量 |
|--------|------|
| **当前所有未解决线上故障** | **{stats['unresolved']}** |
| **{stats['year']}年{stats['month']}月创建的线上故障** | **{stats['current_month_created']}** |
| **{stats['year']}年{stats['month']}月关闭的线上故障** | **{stats['current_month_closed']}** |

**统计说明:**
- 项目中总共有 **{stats['total_online_fault']}** 个"线上故障"类型工作项
- **{stats['total_online_fault'] - stats['unresolved']}** 个已经关闭，**{stats['unresolved']}** 个仍处于未解决状态
""")

    unresolved_items = stats.get('unresolved_items', [])
    if not unresolved_items:
        print("✅ 当前没有未解决的线上故障！")
        return

    # 按负责人分组
    items_by_assignee = defaultdict(list)
    unassigned_items = []

    for item in unresolved_items:
        assigned_to = item.get('assignedTo') or {}
        assignee = assigned_to.get('name', '未分配')
        if assignee:
            items_by_assignee[assignee].append(item)
        else:
            unassigned_items.append(item)

    print("## 未解决故障清单（按负责人分组）\n")

    # 按故障数量排序负责人
    sorted_assignees = sorted(items_by_assignee.keys(), key=lambda x: len(items_by_assignee[x]), reverse=True)

    for assignee in sorted_assignees:
        items = items_by_assignee[assignee]
        print(f"### 👤 {assignee}（{len(items)} 个故障）\n")
        print("| 优先级 | 严重程度 | 状态 | 编号 | 标题 | 链接 |")
        print("|--------|----------|------|------|------|------|")

        for item in items:
            identifier = item.get("serialNumber", "")
            subject = item.get("subject", "")
            status = item.get("status") or {}
            status_name = status.get("name", "")

            priority = get_custom_field_value(item, 'priority')
            severity = get_custom_field_value(item, 'seriousLevel')

            priority_emoji = get_priority_emoji(priority)
            severity_emoji = get_severity_emoji(severity)
            status_emoji = get_status_emoji(status_name)

            if organization_id and identifier:
                link = f"https://devops.aliyun.com/organization/{organization_id}/work/workitems/{identifier}"
            else:
                link = identifier

            print(f"| {priority_emoji} {priority} | {severity_emoji} {severity} | {status_emoji} {status_name} | {identifier} | {subject} | [查看]({link}) |")
        print()

    # 未分配的故障
    if unassigned_items:
        print(f"### ❌ 未分配（{len(unassigned_items)} 个故障）\n")
        print("| 优先级 | 严重程度 | 状态 | 编号 | 标题 | 链接 |")
        print("|--------|----------|------|------|------|------|")
        for item in unassigned_items:
            identifier = item.get("serialNumber", "")
            subject = item.get("subject", "")
            status = item.get("status") or {}
            status_name = status.get("name", "")

            priority = get_custom_field_value(item, 'priority')
            severity = get_custom_field_value(item, 'seriousLevel')

            priority_emoji = get_priority_emoji(priority)
            severity_emoji = get_severity_emoji(severity)
            status_emoji = get_status_emoji(status_name)

            if organization_id and identifier:
                link = f"https://devops.aliyun.com/organization/{organization_id}/work/workitems/{identifier}"
            else:
                link = identifier

            print(f"| {priority_emoji} {priority} | {severity_emoji} {severity} | {status_emoji} {status_name} | {identifier} | {subject} | [查看]({link}) |")
        print()

    # 摘要统计
    print("## 状态统计摘要\n")
    status_counts = defaultdict(int)
    for item in unresolved_items:
        status = item.get("status") or {}
        status_name = status.get("name", "未知")
        status_counts[status_name] += 1

    print("| 状态 | 数量 |")
    print("|------|------|")
    for status_name, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        status_emoji = get_status_emoji(status_name)
        print(f"| {status_emoji} {status_name} | {count} |")
    print()

    print("## 优先级统计摘要\n")
    priority_counts = defaultdict(int)
    for item in unresolved_items:
        priority = get_custom_field_value(item, 'priority') or "未知"
        priority_counts[priority] += 1

    print("| 优先级 | 数量 |")
    print("|--------|------|")
    for priority, count in sorted(priority_counts.items(), key=lambda x: x[1], reverse=True):
        priority_emoji = get_priority_emoji(priority)
        print(f"| {priority_emoji} {priority} | {count} |")
    print()


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <json-file-path> <year> <month> [organization_id]")
        sys.exit(1)

    json_file = sys.argv[1]
    year = int(sys.argv[2])
    month = int(sys.argv[3])
    organization_id = sys.argv[4] if len(sys.argv) > 4 else ''

    stats = analyze_stats(json_file, year, month)
    print_result(stats, organization_id)


if __name__ == '__main__':
    main()
