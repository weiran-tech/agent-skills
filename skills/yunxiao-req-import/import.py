import openpyxl
import time
import json
import sys

# 配置
ORG_ID = "62ac9a6364c8a06be2d5db5d"
SPACE_ID = "cbf6b94fbf645e67ec6626fac1"

# 负责人映射
ASSIGNEE_MAP = {
    "任广焱": "6836b16013953752274d9500",
    "王海洋": "665d6b2be250d584b90a9dbc",
}
DEFAULT_ASSIGNEE = "65699cacc319d2a0f949d3a7"

# 需求类型映射
TYPE_MAP = {
    "产品类需求": "9uy29901re573f561d69jn40",
    "技术类需求": "bca48ee2a0976d38f4802fae",
}
DEFAULT_TYPE = "9uy29901re573f561d69jn40"

# 自定义字段 ID
FEEDBACK_FIELD = "e3e6f16092d2b98b1a85026e39"


def generate_description(row):
    """生成固定格式的 HTML 描述"""
    desc = str(row.get("需求描述") or "")
    benefit = str(row.get("预期收益") or "")
    module = str(row.get("归属模块") or "")
    req_type = str(row.get("需求类型") or "")
    feedback = str(row.get("提交人") or "")

    html = f"<h3>为什么要做</h3>"
    html += f"<h4>业务背景</h4>"
    html += f"<p>{desc}</p>"

    if benefit and benefit != "None":
        html += f"<h4>业务价值 / 预期收益</h4>"
        html += f"<p>{benefit}</p>"

    html += f"<hr /><h3>业务规则</h3><ul>"
    if module and module != "None":
        html += f"<li><strong>业务场景 / 模块</strong>：{module}</li>"
    if req_type and req_type != "None":
        html += f"<li><strong>需求类型</strong>：{req_type}</li>"
    if feedback and feedback != "None":
        html += f"<li><strong>需求来源</strong>：{feedback}</li>"
    html += f"</ul>"

    html += f"<hr /><h3>需求描述</h3>"
    html += f"<p>{desc}</p>"

    html += f"<hr /><h3>验收标准</h3><ul>"
    html += f"<li>核心功能正常上线</li>"
    html += f"<li>达到预期业务目标</li>"
    html += f"<li>相关页面和流程正常运行</li>"
    html += f"</ul>"

    return html


def main():
    # 读取 Excel
    wb = openpyxl.load_workbook("docs/氪金兽.xlsx")
    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]

    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if any(row):
            rows.append(dict(zip(headers, row)))

    print(f"共读取 {len(rows)} 条需求，开始导入...")
    print(f"目标项目: 客诉工单处理中心 ({SPACE_ID})")
    print()

    success = 0
    failed = 0

    for i, row in enumerate(rows, 1):
        subject = str(row.get("需求描述") or "")[:200]
        assignee_name = str(row.get("跟进人") or "")
        feedback = str(row.get("提交人") or "")
        req_type = str(row.get("需求类型") or "")

        # 映射负责人
        assignee_id = ASSIGNEE_MAP.get(assignee_name, DEFAULT_ASSIGNEE)

        # 映射需求类型（根据需求类型字段判断，默认产品类）
        type_id = TYPE_MAP.get(req_type, DEFAULT_TYPE)

        # 生成描述
        description = generate_description(row)

        # 自定义字段
        custom_fields = {}
        if feedback and feedback != "None":
            custom_fields[FEEDBACK_FIELD] = feedback

        try:
            # 构造 MCP 命令（通过标准输出传递给外部执行）
            cmd = {
                "tool": "mcp__yunxiao__create_work_item",
                "params": {
                    "organizationId": ORG_ID,
                    "spaceId": SPACE_ID,
                    "subject": subject,
                    "workitemTypeId": type_id,
                    "assignedTo": assignee_id,
                    "customFieldValues": custom_fields,
                    "description": description,
                    "descriptionFormat": "RICHTEXT",
                },
            }
            print(f"__MCP_COMMAND__{json.dumps(cmd, ensure_ascii=False)}__MCP_COMMAND__")
            sys.stdout.flush()

            success += 1
            print(f"✅ [{i}/{len(rows)}] {subject[:30]}...")

        except Exception as e:
            failed += 1
            print(f"❌ [{i}/{len(rows)}] {subject[:30]}... 错误: {e}")

        # 限速
        time.sleep(0.5)

    print()
    print("✅ 批量导入完成")
    print("━━━━━━━━━━━━━━━━━━━━━")
    print(f"总计：{len(rows)} 条")
    print(f"成功：{success} 条")
    print(f"失败：{failed} 条")


if __name__ == "__main__":
    main()
