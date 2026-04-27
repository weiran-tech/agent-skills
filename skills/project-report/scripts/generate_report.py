#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///
"""
Project Daily Report Generator

生成单个项目的日报报告，支持配置读取和文件输出。

新架构：每个项目有独立的配置文件 config/{项目名}.yaml
"""

import os
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


def load_project_config(project_root: Path, project_name: str) -> Optional[Dict[str, Any]]:
    """加载项目独立配置文件"""
    config_path = project_root / 'config' / f'{project_name}.yaml'
    if not config_path.exists():
        return None
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_available_projects(project_root: Path) -> List[str]:
    """列出所有可用的项目配置"""
    config_dir = project_root / 'config'
    if not config_dir.exists():
        return []
    return [f.stem for f in config_dir.glob('*.yaml')]


def get_enabled_content_types(project_config: Dict[str, Any],
                        types_param: Optional[str] = None) -> Dict[str, bool]:
    """获取启用的内容类型

    bugs 和 req 始终启用；sentry/sls 只有配置非空时启用"""
    all_types = {'bugs': True, 'req': True}

    # sentry: 配置存在且非空时启用
    sentry_config = project_config.get('sentry', {})
    all_types['sentry'] = bool(sentry_config)

    # sls: 配置存在且非空列表时启用
    sls_config = project_config.get('sls', [])
    all_types['sls'] = bool(sls_config)

    if types_param:
        selected_types = [t.strip() for t in types_param.split(',')]
        return {k: v for k, v in all_types.items() if k in selected_types}

    return all_types


def generate_timestamp() -> str:
    """生成时间戳 yyyy-mm-dd-hh-mm"""
    return datetime.now().strftime('%Y-%m-%d-%H-%M')


def build_report_content(project_name: str,
                         report_date: str,
                         results: Dict[str, Any]) -> str:
    """构建报告内容"""
    lines = [f"# {project_name} - {report_date}\n"]

    # 线上故障
    lines.append("## 线上故障\n")
    if 'bugs' in results:
        lines.append(results['bugs'])
    else:
        lines.append("（本次未采集）")
    lines.append("\n")

    # 技术需求
    lines.append("## 技术需求\n")
    if 'req' in results:
        lines.append(results['req'])
    else:
        lines.append("（本次未采集）")
    lines.append("\n")

    # Sentry
    lines.append("## Sentry\n")
    if 'sentry' in results:
        sentry_results = results['sentry']
        for group_name, content in sentry_results.items():
            lines.append(f"### {group_name}\n")
            lines.append(content)
            lines.append("\n")
    else:
        lines.append("（本次未采集）")
    lines.append("\n")

    # 接口高频统计
    lines.append("## 接口高频统计\n")
    if 'sls' in results:
        sls_results = results['sls']
        for host, content in sls_results.items():
            lines.append(f"### {host}\n")
            lines.append(content)
            lines.append("\n")
    else:
        lines.append("（本次未采集）")

    return "\n".join(lines)


def write_report(project_root: Path,
                 project_name: str,
                 content: str) -> str:
    """写入报告文件，返回文件路径

    输出目录结构: report/temp/{project}/qa/{project}-{timestamp}.md
    """
    # 输出目录: report/temp/{project}/qa/
    output_dir = project_root / 'report' / 'temp' / project_name / 'qa'
    os.makedirs(output_dir, exist_ok=True)

    timestamp = generate_timestamp()
    filename = f"{project_name}-{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


def main():
    """主函数：列出可用项目"""
    # 代码库根目录
    project_root = Path(__file__).parents[5]

    # 打印可用的项目列表
    projects = list_available_projects(project_root)
    print("可用项目:")
    for proj in sorted(projects):
        config = load_project_config(project_root, proj)
        enabled = "✓" if config and config.get('enabled', False) else "✗"
        print(f"  {enabled} {proj}")

    if not projects:
        print("\n  (无可用项目配置)")


if __name__ == '__main__':
    main()
