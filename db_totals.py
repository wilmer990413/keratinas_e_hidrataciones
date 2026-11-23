import sqlite3, json, os, sys
db_path = r'C:\Users\ASUS\Documents\GitHub\keratinas_e_hidrataciones\peluqueria_pos.db'
if not os.path.exists(db_path):
    print('Database not found')
    sys.exit(1)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
# Compute total ingresos (sum of total column where activa=1)
total_ing = conn.execute('SELECT SUM(total) FROM transacciones WHERE activa=1').fetchone()[0] or 0
admin_sum = conn.execute('SELECT SUM(admin_share) FROM transacciones WHERE activa=1').fetchone()[0] or 0
inv_sum = conn.execute('SELECT SUM(inv_share) FROM transacciones WHERE activa=1').fetchone()[0] or 0
# Also compute sum of flete_total for completeness
flete_sum = conn.execute('SELECT SUM(flete_total) FROM transacciones WHERE activa=1').fetchone()[0] or 0
print(json.dumps({
    'total_ingresos': total_ing,
    'admin_share_sum': admin_sum,
    'inv_share_sum': inv_sum,
    'flete_total_sum': flete_sum
}, indent=2, ensure_ascii=False))
