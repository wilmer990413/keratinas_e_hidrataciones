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
        """SELECT vi.producto_id, vi.producto_nombre, vi.unidades, vi.presentacion_id,
                  vi.presentacion_nombre, vi.factor_presentacion,
                  vi.inversionista_id,
                  COALESCE(vi.inversionista_nombre, inv.nombre) AS inversionista_nombre,
                  COALESCE(vi.costo_inversion, 0) AS costo_inversion,
                  COALESCE(vi.ganancia_inversionista, 0) AS ganancia_inversionista
           FROM venta_items vi
           LEFT JOIN productos p ON p.id = vi.producto_id
           LEFT JOIN inversionistas inv ON inv.id = COALESCE(vi.inversionista_id, p.inversionista_id)
           WHERE vi.transaccion_id=? ORDER BY vi.id""",
        (r["id"],),
    ).fetchall()

    es_producto = str(r["tipo_servicio"]).startswith("Prod:")
    inversionistas_map = {}
    for it in item_rows:
      inv_nombre = it["inversionista_nombre"]
      costo = float(it["costo_inversion"] or 0)
      gan = float(it["ganancia_inversionista"] or 0)
      if inv_nombre:
        if inv_nombre not in inversionistas_map:
          inversionistas_map[inv_nombre] = {"nombre": inv_nombre, "costoInversion": 0.0, "ganancia": 0.0}
        inversionistas_map[inv_nombre]["costoInversion"] = round(inversionistas_map[inv_nombre]["costoInversion"] + costo, 2)
        inversionistas_map[inv_nombre]["ganancia"] = round(inversionistas_map[inv_nombre]["ganancia"] + gan, 2)
      elif costo > 0:
        if "Sin inversionista" not in inversionistas_map:
          inversionistas_map["Sin inversionista"] = {"nombre": "Sin inversionista", "costoInversion": 0.0, "ganancia": 0.0}
        inversionistas_map["Sin inversionista"]["costoInversion"] = round(inversionistas_map["Sin inversionista"]["costoInversion"] + costo, 2)

    if es_producto:
      if not inversionistas_map and ((r["inversion_share"] or 0) > 0 or r["inversionista_id"]):
        inv_nom = None
        if r["inversionista_id"]:
          inv_row = conn.execute("SELECT nombre FROM inversionistas WHERE id = ?", (r["inversionista_id"],)).fetchone()
          if inv_row:
            inv_nom = inv_row["nombre"]
        if not inv_nom:
          row_inv = conn.execute(
              """SELECT inv.nombre
                 FROM venta_items vi
                 JOIN productos p ON p.id = vi.producto_id
                 JOIN inversionistas inv ON inv.id = p.inversionista_id
                 WHERE vi.transaccion_id = ? LIMIT 1""",
              (r["id"],)
          ).fetchone()
          inv_nom = row_inv["nombre"] if row_inv else "Sin inversionista"
        inversionistas_map[inv_nom] = {
            "nombre": inv_nom,
            "costoInversion": max(0.0, float(r["inversion_share"] or 0) - float(r["flete_total"] or 0)),
            "ganancia": float(r["ganancia_inv_share"] or 0)
        }
      elif len(inversionistas_map) == 1 and r["ganancia_inv_share"] is not None:
        single_inv = list(inversionistas_map.keys())[0]
        inversionistas_map[single_inv]["ganancia"] = float(r["ganancia_inv_share"] or 0)
        inversionistas_map[single_inv]["costoInversion"] = max(0.0, float(r["inversion_share"] or 0) - float(r["flete_total"] or 0))

    inversionistas_lista = list(inversionistas_map.values())

    transacciones.append({
        "id": r["id"],
        "fechaHora": r["fecha_hora"],
        "cliente": r["cliente"],
        "tipoServicio": r["tipo_servicio"],
        "tipo": "producto" if es_producto else "servicio",
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
        "inversionistas": inversionistas_lista,
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
  busqueda = (request.args.get('q') or '').strip()
  inv_id = (request.args.get('inv_id') or '').strip()
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
    if busqueda:
      patron = f"%{busqueda}%"
      where.append("(cliente LIKE ? OR tipo_servicio LIKE ? OR EXISTS (SELECT 1 FROM venta_items vi WHERE vi.transaccion_id = transacciones.id AND vi.producto_nombre LIKE ?))")
      params.extend([patron, patron, patron])
    if inv_id:
      where.append("EXISTS (SELECT 1 FROM venta_items vi WHERE vi.transaccion_id = transacciones.id AND vi.inversionista_id = ?)")
      params.append(inv_id)
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
  busqueda = (request.args.get('q') or '').strip()
  inv_id = (request.args.get('inv_id') or '').strip()
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
    if busqueda:
      patron = f"%{busqueda}%"
      where.append("(t.cliente LIKE ? OR t.tipo_servicio LIKE ? OR EXISTS (SELECT 1 FROM venta_items vi WHERE vi.transaccion_id = t.id AND vi.producto_nombre LIKE ?))")
      params.extend([patron, patron, patron])
    if inv_id:
      where.append("EXISTS (SELECT 1 FROM venta_items vi WHERE vi.transaccion_id = t.id AND vi.inversionista_id = ?)")
      params.append(inv_id)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"SELECT * FROM transacciones t{where_sql} ORDER BY t.rowid DESC", params).fetchall()
    transacciones = _mapear_transacciones(conn, rows)

    filas = []
    for tx in transacciones:
      inv_txt = ", ".join(f"{inv['nombre']} (${inv['costoInversion']:,.0f})" for inv in tx["inversionistas"]) if tx["inversionistas"] else ("—" if tx["tipo"] == "servicio" else "Sin inversionista")
      filas.append({
          "Fecha": tx["fechaHora"],
          "Tipo": "Producto" if tx["tipo"] == "producto" else "Servicio",
          "Cliente": tx["cliente"],
          "Detalle": tx["tipoServicio"],
          "Total": round(tx["total"], 2),
          "Ganancia Admin": round(tx["adminShare"], 2),
          "Pago Auxiliares": round(tx["auxShare"], 2),
          "Inversionista / Costo": inv_txt,
          "Ganancia Inversionista": round(tx["gananciaInvShare"] or 0, 2),
          "Costo Inversión Total": round(tx["inversionShare"] or 0, 2),
          "Fletes": round(tx["fleteTotal"] or 0, 2),
      })
    df = pd.DataFrame(filas)
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


@main_bp.route('/api/sistema/backups', methods=['GET'])
def api_listar_backups():
  from app.backup import listar_backups
  return jsonify(listar_backups())


@main_bp.route('/api/sistema/backup', methods=['POST'])
def api_crear_backup_manual():
  from app.backup import crear_backup
  data = request.get_json(silent=True) or {}
  motivo = str(data.get("motivo", "manual_admin")).strip()
  archivo = crear_backup(motivo=motivo)
  if archivo:
    return jsonify({"status": "success", "archivo": archivo.name})
  return jsonify({"error": "No se pudo generar la copia de seguridad."}), 500

