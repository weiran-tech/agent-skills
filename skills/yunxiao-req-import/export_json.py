import openpyxl
import json

wb = openpyxl.load_workbook('docs/氪金兽.xlsx')
sheet = wb.active
headers = [cell.value for cell in sheet[1]]

rows = []
for row in sheet.iter_rows(min_row=2, values_only=True):
    if any(row):
        r = dict(zip(headers, row))
        rows.append({
            'subject': str(r.get('需求描述') or '')[:200],
            'assignee_name': str(r.get('跟进人') or ''),
            'feedback': str(r.get('提交人') or ''),
            'req_type': str(r.get('需求类型') or ''),
            'benefit': str(r.get('预期收益') or ''),
            'module': str(r.get('归属模块') or ''),
            'desc': str(r.get('需求描述') or ''),
        })

print(json.dumps(rows, ensure_ascii=False))
