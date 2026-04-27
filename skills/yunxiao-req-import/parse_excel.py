import openpyxl
import json

# 读取 Excel
wb = openpyxl.load_workbook('docs/氪金兽.xlsx')
sheet = wb.active

# 获取表头
headers = [cell.value for cell in sheet[1]]
print('表头:', headers)
print()

# 读取数据
rows = []
for row in sheet.iter_rows(min_row=2, values_only=True):
    if any(row):
        rows.append(dict(zip(headers, row)))

print(f'共读取 {len(rows)} 条需求')
print()
for i, r in enumerate(rows, 1):
    print(f'=== 需求 {i} ===')
    for k, v in r.items():
        print(f'  {k}: {v}')
    print()
