from datetime import datetime
import io
from flask import Blueprint, jsonify, render_template, request, send_file
import pandas as pd
from app.database import get_db_connection

main_bp = Blueprint('main', __name__)


def _filtro_tipo_sql(tipo, params):
  tipo = (tipo or 'todos').lower()
  if tipo == 'producto':
    return " AND tipo_servicio LIKE 'Prod:%'"
  if tipo == 'servicio':
    return " AND tipo_servicio NOT LIKE 'Prod:%'"
  return ""


def _mapear_transacciones(conn, rows):
  transacciones = []
  for r in rows:
    aux_rows = conn.execute(
        """SELECT a.id, a.nombre, sa.porcentaje, sa.base_mano_obra, sa.pago
           FROM servicio_auxiliares sa
           JOIN auxiliares a ON a.id = sa.auxiliar_id
           WHERE sa.transaccion_id = ?
           ORDER BY a.nombre COLLATE NOCASE""",
        (r["id"],),
    ).fetchall()
    item_rows = conn.execute(
        """SELECT producto_id, producto_nombre, unidades, presentacion_id,
                  presentacion_nombre, factor_presentacion
           FROM venta_items WHERE transaccion_id=? ORDER BY id""",
        (r["id"],),
    ).fetchall()
    transacciones.append({
        "id": r["id"],
        "fechaHora": r["fecha_hora"],
        "cliente": r["cliente"],
        "tipoServicio": r["tipo_servicio"],
        "tipo": "producto" if str(r["tipo_servicio"]).startswith("Prod:") else "servicio",
        "total": r["total"],
        "adminShare": r["admin_share"],
        "auxShare": r["aux_share"],
        "materiaPrimaShare": r["materia_prima_share"],
        "invShare": r["inv_share"],
        "inversionShare": r["inversion_share"],
        "gananciaInvShare": r["ganancia_inv_share"],
        "fleteTotal": r["flete_total"],
        "activa": r["activa"],
        "jornadaId": r["jornada_id"],
        "auxiliares": [dict(a) for a in aux_rows],
        "items": [dict(i) for i in item_rows],
    })
  return transacciones


@main_bp.route('/')
def index():
  return render_template('index.html')


@main_bp.route('/api/historico-ventas', methods=['GET'])
def obtener_historico_ventas():
  fecha_inicio = request.args.get('inicio')
  fecha_fin = request.args.get('fin')
  tipo = request.args.get('tipo', 'todos')
  try:
    page = max(1, int(request.args.get('page', 1)))
  except ValueError:
    page = 1
  per_page = 10

  conn = get_db_connection()
  try:
    where = []
    params = []
    if fecha_inicio:
      where.append("fecha_hora >= ?")
      params.append(fecha_inicio)
    if fecha_fin:
      where.append("fecha_hora <= ?")
      params.append(fecha_fin + " 23:59:59")
    tipo_sql = _filtro_tipo_sql(tipo, [])
    if tipo_sql:
      where.append(tipo_sql[5:] if tipo_sql.startswith(" AND ") else tipo_sql)
    if not where:
      where.append("1=1")

    base_where = " WHERE " + " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM transacciones{base_where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM transacciones{base_where} ORDER BY rowid DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    transacciones = _mapear_transacciones(conn, rows)
    return jsonify({
      'data': transacciones,
      'total': total,
      'page': page,
      'per_page': per_page,
      'total_pages': (total + per_page - 1) // per_page,
    })
  finally:
    conn.close()


@main_bp.route('/api/exportar-ventas-excel', methods=['GET'])
def exportar_ventas_excel():
  fecha_inicio = request.args.get('inicio')
  fecha_fin = request.args.get('fin')
  tipo = request.args.get('tipo', 'todos')
  jornada_actual = request.args.get('jornada') == 'actual'

  conn = get_db_connection()
  try:
    where = []
    params = []
    if jornada_actual:
      jornada = conn.execute("SELECT id FROM jornadas WHERE activa=1 ORDER BY rowid DESC LIMIT 1").fetchone()
      if jornada:
        where.append("t.jornada_id = ? AND t.activa = 1")
        params.append(jornada["id"])
      else:
        where.append("1=0")
    else:
      if fecha_inicio:
        where.append("t.fecha_hora >= ?")
        params.append(fecha_inicio)
      if fecha_fin:
        where.append("t.fecha_hora <= ?")
        params.append(fecha_fin + ' 23:59:59')
    tipo_sql = _filtro_tipo_sql(tipo, [])
    if tipo_sql:
      where.append(tipo_sql[5:])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    query = f"""
      SELECT t.fecha_hora AS Fecha,\n             CASE WHEN t.tipo_servicio LIKE 'Prod:%' THEN 'Producto' ELSE 'Servicio' END AS Tipo,\n             t.cliente AS Cliente,\n             t.tipo_servicio AS Detalle,\n             ROUND(t.total, 2) AS Total,\n             ROUND(t.admin_share, 2) AS 'Ganancia Admin',\n             ROUND(t.aux_share, 2) AS 'Pago Auxiliares',\n             ROUND(COALESCE(t.ganancia_inv_share, 0), 2) AS 'Ganancia Inversionista',\n             ROUND(COALESCE(t.inversion_share, 0), 2) AS Inversion,\n             ROUND(COALESCE(t.flete_total, 0), 2) AS Fletes\n      FROM transacciones t{where_sql}\n      ORDER BY t.rowid DESC\n    """
    df = pd.read_sql_query(query, conn, params=params)
  finally:
    conn.close()

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name='Ventas')
    ws = writer.book['Ventas']
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for column_cells in ws.columns:
      length = max(len(str(cell.value or '')) for cell in column_cells)
      ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 45)
  output.seek(0)

  prefijo = 'jornada' if jornada_actual else 'historico_ventas'
  filename = f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
  return send_file(
      output,
      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      as_attachment=True,
      download_name=filename,
  )
