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

新架构：每个项目在仓库根目录下有独立目录 `projects/<项目名>/config.yaml`，
脚本会在以下位置按顺序查找：
  1. `--project-root` 入参指定的目录
  2. 当前工作目录（含 `projects/<项目名>/` 的最近一级）
  3. 脚本真实路径向上解析到仓库根（兼容未带参运行）
"""

import os
import sys
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


def _resolve_project_config_path(project_root: Path, project_name: str) -> Path:
    """解析项目配置文件路径。

    carry 仓的标准布局是 `<root>/projects/<项目名>/config.yaml`，
    本函数集中这一映射，便于后续仓库重构时单点调整。
    """
    return project_root / 'projects' / project_name / 'config.yaml'


def _find_project_root(start: Path) -> Path:
    """从 start 向上找最近的含 `projects/` 子目录的目录。

    这样无论从哪里运行脚本都能解析到正确的仓库根。在 duoli-weiran
    仓内跑(没有 projects/)会回退到 cwd。
    """
    cur = start.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / 'projects').is_dir():
            return parent
    return cur


def load_project_config(project_root: Path, project_name: str) -> Optional[Dict[str, Any]]:
    """加载项目独立配置文件"""
    config_path = _resolve_project_config_path(project_root, project_name)
    if not config_path.exists():
        return None
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_available_projects(project_root: Path) -> List[str]:
    """列出所有可用的项目配置(扫描 projects/<项目名>/config.yaml)"""
    projects_dir = project_root / 'projects'
    if not projects_dir.exists():
        return []
    result = []
    for entry in sorted(projects_dir.iterdir()):
        if entry.is_dir() and (entry / 'config.yaml').exists():
            result.append(entry.name)
    return result


def get_sls_threshold(project_config: Dict[str, Any]) -> int:
    """获取 SLS threshold，从第一个 sls 条目读取，无则返回默认值 50"""
    sls_config = project_config.get('sls', [])
    if sls_config and len(sls_config) > 0 and 'sls_threshold' in (sls_config[0] or {}):
        return sls_config[0].get('sls_threshold', 50)
    return 50


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


def _get_local_tz():
    """获取本地时区，优先读取 TZ 环境变量，无则默认 Asia/Shanghai (UTC+8)"""
    tz_name = os.environ.get('TZ', '')
    if not tz_name:
        # macOS/Linux: 尝试从 /etc/timezone 或 /etc/localtime 推断
        import subprocess
        try:
            result = subprocess.run(['systemsetup', '-gettimezone'], capture_output=True, text=True, timeout=5)
            out = result.stdout.strip()
            if 'Time Zone:' in out:
                tz_name = out.split('Time Zone:')[-1].strip()
        except Exception:
            pass
    if not tz_name:
        tz_name = 'Asia/Shanghai'
    # Python 3.9+: zoneinfo 可用；兼容旧版本用 fallback
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        # fallback: 固定偏移 UTC+8
        return timezone(timedelta(hours=8))


def generate_timestamp() -> str:
    """生成时间戳 mm-dd-hh-mm（使用时区感知的本地时间）"""
    return datetime.now(_get_local_tz()).strftime('%m-%d-%H-%M')


def build_report_content(project_name: str,
                         report_date: str,
                         results: Dict[str, Any]) -> Dict[str, str]:
    """构建各类型报告内容，返回 {filename: content} 字典"""
    reports: Dict[str, str] = {}
    date_str = report_date

    # 线上故障
    if 'bugs' in results or 'bugs' not in results:
        filename = "线上故障.md"
        lines = [f"# {project_name} - {date_str} — 线上故障\n"]
        if 'bugs' in results:
            lines.append(results['bugs'])
        else:
            lines.append("（本次未采集）")
        reports[filename] = "\n".join(lines)

    # 需求统计
    if 'req' in results or 'req' not in results:
        filename = "需求统计.md"
        lines = [f"# {project_name} - {date_str} — 需求统计\n"]
        if 'req' in results:
            lines.append(results['req'])
        else:
            lines.append("（本次未采集）")
        reports[filename] = "\n".join(lines)

    # Sentry
    if 'sentry' in results or 'sentry' not in results:
        filename = "Sentry异常.md"
        lines = [f"# {project_name} - {date_str} — Sentry\n"]
        if 'sentry' in results:
            sentry_results = results['sentry']
            if sentry_results:
                for group_name, content in sentry_results.items():
                    lines.append(f"### {group_name}\n")
                    lines.append(content)
                    lines.append("\n")
            else:
                lines.append("（本次未采集）")
        else:
            lines.append("（本次未采集）")
        reports[filename] = "\n".join(lines)

    # 接口高频统计
    if 'sls' in results or 'sls' not in results:
        filename = "高频接口.md"
        lines = [f"# {project_name} - {date_str} — 接口高频统计\n"]
        if 'sls' in results:
            sls_results = results['sls']
            if sls_results:
                for name, content in sls_results.items():
                    lines.append(f"### {name}\n")
                    lines.append(content)
                    lines.append("\n")
            else:
                lines.append("（本次未采集）")
        else:
            lines.append("（本次未采集）")
        reports[filename] = "\n".join(lines)

    return reports


def ensure_output_dir(project_root: Path, project_name: str, ts: Optional[str] = None) -> Path:
    """创建输出目录并返回目录路径。

    结构: `<root>/projects/<项目名>/QA/<MM-DD-HH-MM>/`，与 carry 仓既定
    `projects/<项目名>/QA/<日期>/` 落点保持一致(只把时间戳单独作为子目录)。
    """
    if ts is None:
        ts = generate_timestamp()
    output_dir = project_root / 'projects' / project_name / 'QA' / ts
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_report_file(output_dir: Path, filename: str, content: str) -> str:
    """写入单个报告文件到输出目录，返回文件路径"""
    filepath = output_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return str(filepath)


def main():
    """主函数：生成项目报告或列出可用项目"""
    import argparse

    parser = argparse.ArgumentParser(description="项目日报生成器")
    parser.add_argument('--project', type=str, help='项目名称')
    parser.add_argument('--types', type=str, help='内容类型，逗号分隔 (bugs,req,sentry,sls)')
    parser.add_argument(
        '--project-root',
        type=str,
        default=None,
        help='仓库根目录,内含 projects/<项目名>/config.yaml。默认从 CWD 向上查找包含 projects/ 的最近一级。',
    )
    args = parser.parse_args()

    # 默认从 cwd 向上找含 projects/ 的目录 — 这样在 carry 仓任何子目录跑都能解析对。
    if args.project_root:
        project_root = Path(args.project_root).resolve()
    else:
        project_root = _find_project_root(Path.cwd())

    if args.project:
        # 生成指定项目的报告
        config = load_project_config(project_root, args.project)
        if not config:
            missing = _resolve_project_config_path(project_root, args.project)
            print(f"⚠️ 配置文件不存在: {missing}")
            return

        ts = generate_timestamp()
        report_date = datetime.now(_get_local_tz()).strftime('%Y-%m-%d')
        output_dir = ensure_output_dir(project_root, args.project, ts)

        results = {}
        if config.get('online_fault'):
            results['bugs'] = config['online_fault'].get('content', '')
        if config.get('technical_req'):
            results['req'] = config['technical_req'].get('content', '')
        if config.get('sentry'):
            results['sentry'] = config['sentry']
        if config.get('api_frequency'):
            results['sls'] = config['api_frequency']

        reports = build_report_content(args.project, report_date, results)

        for filename, content in reports.items():
            filepath = write_report_file(output_dir, filename, content)
            print(f"  ✓ {filename}")

        print(f"\n报告路径: projects/{args.project}/QA/{ts}/")
    else:
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
