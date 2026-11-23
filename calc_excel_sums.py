import pandas as pd, os, json, sys
excel_path = r'C:\Users\ASUS\.gemini\antigravity\brain\401c3ac2-92d5-4b41-a355-d5387eed5413\.user_uploaded\media_1795399108222_83cbe678.xlsx'
if not os.path.exists(excel_path):
    print('Excel not found')
    sys.exit(1)
xls = pd.ExcelFile(excel_path)
# Load sheets
venta_delta = pd.read_excel(xls, sheet_name='VENTA DELTA')
venta_al = pd.read_excel(xls, sheet_name='VENTA AL MAYOR')
# Compute sums
sum_carolina = venta_delta['GANANCIA CAROLINA'].fillna(0).sum()
sum_wilmer_delta = venta_delta['GANANCIA WILMER'].fillna(0).sum()
sum_wilmer_al = 0
if 'GANANCIA WILMER' in venta_al.columns:
    sum_wilmer_al = venta_al['GANANCIA WILMER'].fillna(0).sum()
# Total ingresos (sum of all gains)
total_ingresos = sum_carolina + sum_wilmer_delta + sum_wilmer_al
# Output
result = {
    'sum_carolina': float(sum_carolina),
    'sum_wilmer_delta': float(sum_wilmer_delta),
    'sum_wilmer_al': float(sum_wilmer_al),
    'total_ingresos': float(total_ingresos)
}
print(json.dumps(result, indent=2, ensure_ascii=False))
