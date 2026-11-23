import pandas as pd, os, sys, json
excel_path = r'C:\Users\ASUS\.gemini\antigravity\brain\401c3ac2-92d5-4b41-a355-d5387eed5413\.user_uploaded\media_1795399108222_83cbe678.xlsx'
if not os.path.exists(excel_path):
    print('Excel not found')
    sys.exit(1)
xls = pd.ExcelFile(excel_path)
print('Sheets:', xls.sheet_names)
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    print('\n---', sheet, '---')
    print(df.head())
