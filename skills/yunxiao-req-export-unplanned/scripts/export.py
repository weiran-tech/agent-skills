#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests",
# ]
# ///
"""
云效未排期需求导出脚本
支持交互式参数询问、多标签筛选
"""

import json
import os
import sys
from datetime import datetime, timezone

ORGANIZATION_ID = "62ac9a6364c8a06be2d5db5d"

# 未完成状态ID
INCOMPLETE_STATUS_IDS = {
    "28", "100005", "30", "34", "32", "625489",
    "154395", "165115", "100010", "156603",
    "307012", "142838", "100011", "100012"
}

# 已完成状态关键词
COMPLETED_STATUS_KEYWORDS = ["已完成", "已关闭", "已验收", "已发布", "已上线"]


def load_mcp_result(filepath: str) -> dict:
    """加载 MCP 工具返回的结果文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list) and len(data) > 0:
        text_content = data[0].get('text', '')
        if text_content:
            return json.loads(text_content)
    return data


def extract_tag_names(labels: list) -> list:
    """从标签列表中提取标签名称"""
    label_names = []
    for label in labels or []:
        if isinstance(label, dict):
            name = label.get('name', '') or label.get('value', '')
            if name:
                label_names.append(name)
        elif isinstance(label, str) and label:
            label_names.append(label)
    return label_names


def has_any_tag(item_labels: list, filter_tags: list) -> bool:
    """检查是否包含任意一个筛选标签"""
    if not filter_tags:
        return True
    item_label_names = extract_tag_names(item_labels)
    for ft in filter_tags:
        if ft in item_label_names:
            return True
    return False


def has_sprint(item: dict) -> bool:
    """检查是否有迭代"""
    sprint = item.get('sprint')
    if sprint and isinstance(sprint, dict) and sprint.get('id'):
        return True
    if sprint and isinstance(sprint, str) and sprint:
        return True
    return False


def is_incomplete_status(item: dict) -> bool:
    """检查是否为未完成状态"""
    status_data = item.get('status', {})
    if isinstance(status_data, dict):
        status_id = str(status_data.get('id', ''))
        status_name = status_data.get('name', '') or status_data.get('displayName', '')
    else:
        status_id = str(status_data or '')
        status_name = ''

    # 检查状态名称是否包含已完成关键词
    for keyword in COMPLETED_STATUS_KEYWORDS:
        if keyword in status_name:
            return False

    # 检查状态ID是否在未完成列表中
    if status_id in INCOMPLETE_STATUS_IDS:
        return True

    # 如果状态ID不在列表中但状态名称也不包含已完成关键词，也视为未完成
    return True


def is_requirement_type(item: dict, req_type: str) -> bool:
    """检查是否为指定类型的需求"""
    workitem_type = item.get('workitemType', {})
    type_name = workitem_type.get('name', '') if isinstance(workitem_type, dict) else str(workitem_type)

    if req_type == 'product':
        return '产品' in type_name
    elif req_type == 'tech':
        return '技术' in type_name
    return True  # 其他类型不过滤


def get_workitem_field(item: dict, field: str, subfield: str = 'name'):
    """获取工作项字段值"""
    value = item.get(field)
    if isinstance(value, dict) and subfield in value:
        return value.get(subfield)
    return value

def get_status_name(item: dict) -> str:
    """获取状态名称"""
    status = item.get('status', {})
    if isinstance(status, dict):
        return status.get('name') or status.get('displayName') or ''
    return str(status or '')

def get_status_id(item: dict) -> str:
    """获取状态ID"""
    status = item.get('status', {})
    if isinstance(status, dict):
        return str(status.get('id', ''))
    return str(status or '')


def filter_workitems(items: list, req_type: str, filter_tags: list, filter_by_sprint: bool = True) -> list:
    """筛选工作项"""
    result = []
    for item in items:
        # 迭代筛选
        if filter_by_sprint and has_sprint(item):
            continue

        # 状态筛选（仅保留未完成）
        if not is_incomplete_status(item):
            continue

        # 需求类型筛选
        if not is_requirement_type(item, req_type):
            continue

        # 标签筛选（包含任意一个即可）
        if not has_any_tag(item.get('labels', []), filter_tags):
            continue

        result.append(item)

    return result


def format_result(items: list, project_id: str, project_name: str, req_type: str, filter_tags: list) -> dict:
    """格式化输出结果"""
    req_type_name = '产品类需求' if req_type == 'product' else '技术类需求'

    formatted_items = []
    for item in items:
        formatted_items.append({
            'id': item.get('id'),
            'subject': item.get('subject'),
            'status': get_status_name(item),
            'status_id': get_status_id(item),
            'priority': get_workitem_field(item, 'priority'),
            'assigned_to': get_workitem_field(item, 'assignedTo'),
            'creator': get_workitem_field(item, 'creator'),
            'created_at': item.get('gmtCreate'),
            'description': item.get('description', ''),
            'sprint': item.get('sprint'),
            'sprint_name': get_workitem_field(item, 'sprint'),
            'workitem_type': get_workitem_field(item, 'workitemType'),
            'category': item.get('category'),
            'version': get_workitem_field(item, 'version'),
            'parent_id': item.get('parentId'),
            'tags': extract_tag_names(item.get('labels', [])),
            'raw': item
        })

    return {
        'export_time': datetime.now(timezone.utc).isoformat(),
        'project_id': project_id,
        'project_name': project_name,
        'req_type': req_type,
        'req_type_name': req_type_name,
        'filter_tags': filter_tags,
        'filter_by_sprint': True,
        'total_items': len(formatted_items),
        'items': formatted_items
    }


def print_summary(result: dict, output_file: str):
    """打印导出摘要"""
    print(f"\n{'='*60}")
    print(f"导出完成！")
    print(f"{'='*60}")
    print(f"项目: {result['project_name']}")
    print(f"需求类型: {result['req_type_name']}")
    print(f"筛选标签: {result['filter_tags'] if result['filter_tags'] else '无'}")
    print(f"导出数量: {result['total_items']} 条")
    print(f"输出文件: {output_file}")

    # 按状态统计
    status_stats = {}
    for item in result['items']:
        s = item['status'] or '未知'
        status_stats[s] = status_stats.get(s, 0) + 1

    if status_stats:
        print(f"\n按状态统计:")
        for s, c in sorted(status_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {s}: {c}")

    # 打印前10条
    if result['items']:
        print(f"\n需求列表（前{min(10, len(result['items']))}条）:")
        for i, item in enumerate(result['items'][:10]):
            tags = ', '.join(item['tags']) if item['tags'] else '无'
            print(f"\n{i+1}. [{item['status']}] {item['subject']}")
            print(f"   标签: {tags} | 创建人: {item['creator']} | 指派人: {item['assigned_to']}")


def main():
    args = sys.argv[1:]

    # 解析参数
    params = {
        'project_id': None,
        'project_name': None,
        'req_type': 'product',
        'filter_tags': [],
        'output_file': 'report/temp/unplanned_requirements.json',
        'input_file': None,
        'filter_by_sprint': True
    }

    for arg in args:
        if arg.startswith('project_id='):
            params['project_id'] = arg.split('=', 1)[1]
        elif arg.startswith('project_name='):
            params['project_name'] = arg.split('=', 1)[1]
        elif arg.startswith('type='):
            params['req_type'] = arg.split('=', 1)[1]
        elif arg.startswith('tags='):
            tags_str = arg.split('=', 1)[1]
            params['filter_tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
        elif arg.startswith('output='):
            params['output_file'] = arg.split('=', 1)[1]
        elif arg.startswith('input='):
            params['input_file'] = arg.split('=', 1)[1]
        elif arg.startswith('sprint='):
            params['filter_by_sprint'] = arg.split('=', 1)[1].lower() == 'true'

    if not params['input_file']:
        print("错误: 请提供 MCP 结果文件路径")
        print("用法: uv run export.py input=/path/to/mcp_result.json project_id=xxx project_name=xxx")
        sys.exit(1)

    if not params['project_id']:
        print("错误: 请提供项目 ID")
        sys.exit(1)

    print(f"项目: {params['project_name'] or params['project_id']}")
    print(f"需求类型: {'产品类需求' if params['req_type'] == 'product' else '技术类需求'}")
    print(f"标签筛选: {params['filter_tags'] if params['filter_tags'] else '无'}")
    print(f"迭代筛选: {'仅导出无迭代需求' if params['filter_by_sprint'] else '包含有迭代需求'}")

    # 加载数据
    data = load_mcp_result(params['input_file'])
    items = data.get('items', data) if isinstance(data, dict) else data
    print(f"\n加载数据: {len(items)} 条工作项")

    # 筛选数据
    filtered = filter_workitems(
        items,
        req_type=params['req_type'],
        filter_tags=params['filter_tags'],
        filter_by_sprint=params['filter_by_sprint']
    )

    # 格式化结果
    result = format_result(
        filtered,
        project_id=params['project_id'],
        project_name=params['project_name'] or params['project_id'],
        req_type=params['req_type'],
        filter_tags=params['filter_tags']
    )

    # 保存文件
    with open(params['output_file'], 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print_summary(result, params['output_file'])


if __name__ == "__main__":
    main()
