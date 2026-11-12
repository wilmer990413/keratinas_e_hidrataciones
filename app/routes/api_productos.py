import math
import re
from datetime import datetime
from flask import Blueprint, jsonify, request, make_response
from app.database import get_db_connection
from app.routes.api_combos import obtener_todos_combos

api_productos_bp = Blueprint("api_productos", __name__)


def _entero_no_negativo(valor):
  if isinstance(valor, bool) or not isinstance(valor, (int, float)):
    return None
  if isinstance(valor, float) and (not math.isfinite(valor) or valor != int(valor)):
    return None
  valor = int(valor)
  return valor if 0 <= valor <= 1_000_000_000 else None


def _entero_positivo(valor):
  value = _entero_no_negativo(valor)
  return value if value and value > 0 else None


def _decimal_no_negativo(valor):
  try:
    value = float(valor)
    return value if math.isfinite(value) and value >= 0 else None
  except (TypeError, ValueError):
    return None


def _producto_json(conn, producto_id):
  row = conn.execute(
      "SELECT id, nombre, stock, es_ampolleta FROM productos WHERE id = ?", (producto_id,)
  ).fetchone()
  if not row:
    return None
  pres = conn.execute(
      """
      SELECT pp.id, pp.presentacion_id, p.nombre, p.factor,
             pp.base_price AS basePrice, pp.admin_gain AS adminGain,
             pp.inv_gain AS invGain, pp.flete, pp.activa
      FROM producto_presentaciones pp
      JOIN presentaciones p ON p.id = pp.presentacion_id
      WHERE pp.producto_id = ? AND pp.activa = 1 AND p.activa = 1
      ORDER BY p.orden, p.factor, p.nombre COLLATE NOCASE
      """,
      (producto_id,),
  ).fetchall()
  return {
      "id": row["id"],
      "nombre": row["nombre"],
      "stock": row["stock"],
      "esAmpolleta": row["es_ampolleta"],
      "presentaciones": [
          {
              "id": r["id"],
              "presentacionId": r["presentacion_id"],
              "nombre": r["nombre"],
              "factor": r["factor"],
              "basePrice": r["basePrice"],
              "adminGain": r["adminGain"],
              "invGain": r["invGain"],
              "flete": r["flete"],
          }
          for r in pres
      ],
  }


def _todos_productos(conn):
  ids = [r["id"] for r in conn.execute("SELECT id FROM productos ORDER BY nombre COLLATE NOCASE")]
  return [p for pid in ids if (p := _producto_json(conn, pid))]


def _asegurar_presentaciones_producto(conn, producto_id, presentaciones_data=None):
  globales = conn.execute("SELECT id FROM presentaciones WHERE activa = 1 ORDER BY orden, factor").fetchall()
  existentes = {
      r["presentacion_id"]: r
      for r in conn.execute(
          "SELECT * FROM producto_presentaciones WHERE producto_id = ?", (producto_id,)
      ).fetchall()
  }
  data_map = {str(x.get("presentacionId")): x for x in (presentaciones_data or []) if isinstance(x, dict)}

  # Toda presentación global activa queda disponible para cualquier producto.
  for gp in globales:
    pid = gp["id"]
    if pid in existentes:
      item = data_map.get(pid)
      if item:
        vals = [_decimal_no_negativo(item.get(k)) for k in ("basePrice", "adminGain", "invGain", "flete")]
        if all(v is not None for v in vals):
          conn.execute(
              "UPDATE producto_presentaciones SET base_price=?, admin_gain=?, inv_gain=?, flete=?, activa=1 WHERE producto_id=? AND presentacion_id=?",
              (*vals, producto_id, pid),
          )
      continue

    # Si no viene configuración explícita, se usa el precio de unidad del producto.
    base = conn.execute(
        "SELECT base_price, admin_gain, inv_gain, flete FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    item = data_map.get(pid) or {}
    vals = [_decimal_no_negativo(item.get(k)) for k in ("basePrice", "adminGain", "invGain", "flete")]
    if not all(v is not None for v in vals):
      vals = [base["base_price"], base["admin_gain"], base["inv_gain"], base["flete"]]
    conn.execute(
        """
        INSERT INTO producto_presentaciones
          (id, producto_id, presentacion_id, base_price, admin_gain, inv_gain, flete, activa)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (f"pp-{producto_id}-{pid}", producto_id, pid, *vals),
    )


def _normalizar_presentacion_data(data):
  rows = data if isinstance(data, list) else []
  result = []
  seen = set()
  for item in rows:
    if not isinstance(item, dict):
      continue
    pid = str(item.get("presentacionId", "")).strip()
    if not pid or pid in seen:
      continue
    seen.add(pid)
    result.append(item)
  return result


@api_productos_bp.route("/api/estado")
def api_estado():
  conn = get_db_connection()
  jornada = conn.execute("SELECT id, iniciada_en FROM jornadas WHERE activa=1 ORDER BY rowid DESC LIMIT 1").fetchone()
  if not jornada:
    # Solo crea la primera jornada si la base antigua aún no tenía una.
    from app.database import now_colombia
    jid = "JOR-" + str(__import__("time").time_ns())
    inicio = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO jornadas(id, iniciada_en, activa) VALUES(?,?,1)", (jid, inicio))
    jornada = conn.execute("SELECT id, iniciada_en FROM jornadas WHERE id=?", (jid,)).fetchone()

  productos = _todos_productos(conn)
  combos = obtener_todos_combos(conn, solo_activos=True)
  presentaciones = [
      dict(r) for r in conn.execute(
          "SELECT id, nombre, factor, activa, orden FROM presentaciones ORDER BY orden, factor, nombre COLLATE NOCASE"
      ).fetchall()
  ]

  rows = conn.execute(
      "SELECT * FROM transacciones WHERE jornada_id = ? AND activa = 1 ORDER BY rowid DESC", (jornada["id"],)
  ).fetchall()
  transacciones = []
  for r in rows:
    aux_rows = conn.execute(
        """
        SELECT a.id, a.nombre, sa.porcentaje, sa.pago
        FROM servicio_auxiliares sa
        JOIN auxiliares a ON a.id = sa.auxiliar_id
        WHERE sa.transaccion_id = ?
        ORDER BY a.nombre COLLATE NOCASE
        """, (r["id"],)
    ).fetchall()
    transacciones.append({
        "id": r["id"],
        "fechaHora": r["fecha_hora"],
        "cliente": r["cliente"],
        "tipoServicio": r["tipo_servicio"],
        "tipo": "producto" if str(r["tipo_servicio"]).startswith("Prod:") else "servicio",  # <-- AGREGAR ESTA LÍNEA
        "total": r["total"],
        "adminShare": r["admin_share"],
        "auxShare": r["aux_share"],
        "materiaPrimaShare": r["materia_prima_share"] or 0,
        "invShare": r["inv_share"] or 0,
        "inversionShare": r["inversion_share"],
        "gananciaInvShare": r["ganancia_inv_share"],
        "fleteTotal": r["flete_total"] or 0,
        "auxiliares": [dict(a) for a in aux_rows],
    })

  auxiliares = [dict(r) for r in conn.execute(
      "SELECT id, nombre, documento, telefono, activo, fecha_ingreso FROM auxiliares ORDER BY activo DESC, nombre COLLATE NOCASE"
  ).fetchall()]
  conn.close()

  response = make_response(jsonify({
      "productos": productos,
      "combos": combos,
      "presentaciones": presentaciones,
      "transacciones": transacciones,
      "jornada": {"id": jornada["id"], "iniciadaEn": jornada["iniciada_en"]},
      "auxiliares": auxiliares,
  }))
  response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
  return response


@api_productos_bp.route("/api/presentaciones", methods=["GET"])
def api_listar_presentaciones():
  conn = get_db_connection()
  rows = conn.execute(
      "SELECT id, nombre, factor, activa, orden FROM presentaciones ORDER BY orden, factor, nombre COLLATE NOCASE"
  ).fetchall()
  conn.close()
  return jsonify([dict(r) for r in rows])


@api_productos_bp.route("/api/presentacion", methods=["POST"])
def api_crear_presentacion():
  data = request.json or {}
  nombre = str(data.get("nombre", "")).strip()
  factor = _entero_positivo(data.get("factor"))
  if not nombre or factor is None:
    return jsonify({"error": "El nombre y el factor de la presentación son obligatorios."}), 400
  conn = get_db_connection()
  try:
    existe = conn.execute("SELECT 1 FROM presentaciones WHERE lower(nombre)=lower(?)", (nombre,)).fetchone()
    if existe:
      return jsonify({"error": "Ya existe una presentación con ese nombre."}), 409
    pid = "pres-" + str(__import__("time").time_ns())
    orden = conn.execute("SELECT COALESCE(MAX(orden), 2) + 1 FROM presentaciones").fetchone()[0]
    conn.execute(
        "INSERT INTO presentaciones(id,nombre,factor,activa,orden) VALUES(?,?,?,?,?)",
        (pid, nombre, factor, 1, orden),
    )
    # Queda disponible automáticamente para todos los productos usando el precio de unidad.
    productos = conn.execute("SELECT id, base_price, admin_gain, inv_gain, flete FROM productos").fetchall()
    for p in productos:
      conn.execute(
          "INSERT INTO producto_presentaciones(id,producto_id,presentacion_id,base_price,admin_gain,inv_gain,flete,activa) VALUES(?,?,?,?,?,?,?,1)",
          (f"pp-{p['id']}-{pid}", p["id"], pid, p["base_price"], p["admin_gain"], p["inv_gain"], p["flete"]),
      )
    conn.commit()
    row = conn.execute("SELECT id,nombre,factor,activa,orden FROM presentaciones WHERE id=?", (pid,)).fetchone()
    return jsonify({"status": "success", "presentacion": dict(row)})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_productos_bp.route("/api/presentacion/<presentacion_id>", methods=["PUT"])
def api_editar_presentacion(presentacion_id):
  data = request.json or {}
  nombre = str(data.get("nombre", "")).strip()
  factor = _entero_positivo(data.get("factor"))
  if not nombre or factor is None:
    return jsonify({"error": "El nombre y el factor deben ser válidos."}), 400
  conn = get_db_connection()
  try:
    row = conn.execute("SELECT * FROM presentaciones WHERE id=?", (presentacion_id,)).fetchone()
    if not row:
      return jsonify({"error": "Presentación no encontrada."}), 404
    dup = conn.execute("SELECT 1 FROM presentaciones WHERE lower(nombre)=lower(?) AND id<>?", (nombre, presentacion_id)).fetchone()
    if dup:
      return jsonify({"error": "Ya existe otra presentación con ese nombre."}), 409
    conn.execute("UPDATE presentaciones SET nombre=?, factor=? WHERE id=?", (nombre, factor, presentacion_id))
    conn.commit()
    return jsonify({"status": "success"})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_productos_bp.route("/api/presentacion/<presentacion_id>", methods=["DELETE"])
def api_desactivar_presentacion(presentacion_id):
  conn = get_db_connection()
  try:
    row = conn.execute("SELECT id FROM presentaciones WHERE id=?", (presentacion_id,)).fetchone()
    if not row:
      return jsonify({"error": "Presentación no encontrada."}), 404
    if presentacion_id in {"unidad", "media_docena", "docena"}:
      return jsonify({"error": "Las presentaciones estándar no se pueden eliminar; pueden mantenerse activas para todos los productos."}), 400
    conn.execute("UPDATE presentaciones SET activa=0 WHERE id=?", (presentacion_id,))
    conn.execute("UPDATE producto_presentaciones SET activa=0 WHERE presentacion_id=?", (presentacion_id,))
    conn.commit()
    return jsonify({"status": "deleted"})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_productos_bp.route("/api/producto", methods=["POST", "PUT"])
def api_guardar_producto():
  data = request.json or {}
  nombre = str(data.get("nombre", "")).strip()
  if not nombre:
    return jsonify({"error": "El nombre del producto es obligatorio."}), 400
  stock = _entero_no_negativo(data.get("stock", 0))
  if stock is None:
    return jsonify({"error": "El stock debe ser un número entero mayor o igual a 0."}), 400

  conn = get_db_connection()
  try:
    producto_id = str(data.get("id", "")).strip() or "p-" + str(__import__("time").time_ns())
    existente = conn.execute("SELECT * FROM productos WHERE id=?", (producto_id,)).fetchone()
    es_ampolleta = int(data.get("esAmpolleta", existente["es_ampolleta"] if existente else 0) or 0)

    pres_data = _normalizar_presentacion_data(data.get("presentaciones"))
    if existente:
      conn.execute(
          "UPDATE productos SET nombre=?, stock=?, es_ampolleta=? WHERE id=?",
          (nombre, stock, es_ampolleta, producto_id),
      )
    else:
      # Los valores legacy quedan como precio base de referencia para nuevas presentaciones.
      unit = next((x for x in pres_data if x.get("presentacionId") == "unidad"), None) or {}
      base = _decimal_no_negativo(unit.get("basePrice")) or 0
      admin = _decimal_no_negativo(unit.get("adminGain")) or 0
      inv = _decimal_no_negativo(unit.get("invGain")) or 0
      flete = _decimal_no_negativo(unit.get("flete")) or 0
      conn.execute(
          "INSERT INTO productos(id,nombre,base_price,admin_gain,inv_gain,flete,es_ampolleta,presentacion,stock) VALUES(?,?,?,?,?,?,?,?,?)",
          (producto_id, nombre, base, admin, inv, flete, es_ampolleta, "unidad", stock),
      )

    _asegurar_presentaciones_producto(conn, producto_id, pres_data)
    unidad = conn.execute(
        "SELECT base_price, admin_gain, inv_gain, flete FROM producto_presentaciones WHERE producto_id=? AND presentacion_id='unidad'",
        (producto_id,),
    ).fetchone()
    if unidad:
      conn.execute(
          "UPDATE productos SET base_price=?, admin_gain=?, inv_gain=?, flete=? WHERE id=?",
          (unidad["base_price"], unidad["admin_gain"], unidad["inv_gain"], unidad["flete"], producto_id),
      )
    conn.commit()
    producto = _producto_json(conn, producto_id)
    return jsonify({"status": "success", "producto": producto})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_productos_bp.route("/api/producto/<prod_id>", methods=["DELETE"])
def api_eliminar_producto(prod_id):
  conn = get_db_connection()
  try:
    conn.execute("DELETE FROM productos WHERE id = ?", (prod_id,))
    conn.commit()
    return jsonify({"status": "deleted"})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()
