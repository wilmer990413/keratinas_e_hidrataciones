import math
from flask import Blueprint, jsonify, request
from app.database import get_db_connection

api_combos_bp = Blueprint("api_combos", __name__)


def _decimal_no_negativo(valor):
  try:
    value = float(valor)
    return value if math.isfinite(value) and value >= 0 else None
  except (TypeError, ValueError):
    return None


def _combo_json(conn, combo_id):
  row = conn.execute(
      "SELECT id, nombre, activo FROM combos WHERE id = ?",
      (combo_id,),
  ).fetchone()
  if not row:
    return None

  items_db = conn.execute(
      """
      SELECT ci.id, ci.producto_id, p.nombre AS producto_nombre, ci.presentacion_id,
             COALESCE(pr.nombre, 'Sin presentación') AS presentacion_nombre,
             COALESCE(pr.factor, 1) AS presentacion_factor,
             ci.cantidad, p.stock AS stock_actual,
             ci.costo_base, ci.admin_gain, ci.inv_gain, ci.flete
      FROM combo_items ci
      JOIN productos p ON p.id = ci.producto_id
      LEFT JOIN presentaciones pr ON pr.id = ci.presentacion_id
      WHERE ci.combo_id = ?
      ORDER BY p.nombre COLLATE NOCASE
      """,
      (combo_id,),
  ).fetchall()

  items = []
  max_combos = 999999
  total_costo_base = 0.0
  total_admin_gain = 0.0
  total_inv_gain = 0.0
  total_flete = 0.0

  for it in items_db:
    cant = int(it["cantidad"])
    factor = int(it["presentacion_factor"] or 1)
    stock = int(it["stock_actual"] or 0)
    unidades_por_combo_item = cant * max(factor, 1)
    posibles = stock // unidades_por_combo_item if unidades_por_combo_item > 0 else 0
    if posibles < max_combos:
      max_combos = posibles

    costo = float(it["costo_base"] or 0)
    admin = float(it["admin_gain"] or 0)
    inv = float(it["inv_gain"] or 0)
    flete = float(it["flete"] or 0)

    total_costo_base += costo * cant
    total_admin_gain += admin * cant
    total_inv_gain += inv * cant
    total_flete += flete * cant

    items.append({
        "id": it["id"],
        "productoId": it["producto_id"],
        "productoNombre": it["producto_nombre"],
        "presentacionId": it["presentacion_id"],
        "presentacionNombre": it["presentacion_nombre"],
        "presentacionFactor": factor,
        "cantidad": cant,
        "unidades": unidades_por_combo_item,
        "stockActual": stock,
        "costoBase": costo,
        "adminGain": admin,
        "invGain": inv,
        "flete": flete,
    })

  stock_disponible = max_combos if items else 0
  precio_total = round(total_costo_base + total_admin_gain + total_inv_gain + total_flete, 2)

  return {
      "id": row["id"],
      "nombre": row["nombre"],
      "costoBase": round(total_costo_base, 2),
      "adminGain": round(total_admin_gain, 2),
      "invGain": round(total_inv_gain, 2),
      "flete": round(total_flete, 2),
      "precioTotal": precio_total,
      "activo": bool(row["activo"]),
      "items": items,
      "stockDisponible": stock_disponible,
  }


def obtener_todos_combos(conn, solo_activos=False):
  q = "SELECT id FROM combos"
  if solo_activos:
    q += " WHERE activo = 1"
  q += " ORDER BY nombre COLLATE NOCASE"
  rows = conn.execute(q).fetchall()
  combos = []
  for r in rows:
    c = _combo_json(conn, r["id"])
    if c:
      combos.append(c)
  return combos


@api_combos_bp.route("/api/combos", methods=["GET"])
def api_listar_combos():
  solo_activos = request.args.get("activos", "0") == "1"
  conn = get_db_connection()
  try:
    combos = obtener_todos_combos(conn, solo_activos=solo_activos)
    return jsonify(combos)
  finally:
    conn.close()


@api_combos_bp.route("/api/combo", methods=["POST", "PUT"])
def api_guardar_combo():
  data = request.json or {}
  from app.schemas import ComboGuardarSchema, parse_payload
  try:
    val = parse_payload(ComboGuardarSchema, data)
  except ValueError as err:
    return jsonify({"error": str(err)}), 400

  nombre = val.nombre
  if not val.items:
    return jsonify({"error": "El combo debe incluir al menos un producto."}), 400

  conn = get_db_connection()
  try:
    combo_id = str(val.id or "").strip() or "combo-" + str(__import__("time").time_ns())
    existente = conn.execute("SELECT id FROM combos WHERE id = ?", (combo_id,)).fetchone()

    items_a_insertar = []
    total_costo = 0.0
    total_admin = 0.0
    total_inv = 0.0
    total_flete = 0.0

    for it in val.items:
      pid = str(it.productoId).strip()
      cant = int(it.cantidad)
      prod = conn.execute("SELECT id FROM productos WHERE id = ?", (pid,)).fetchone()
      if not prod:
        return jsonify({"error": f"El producto {pid} no existe en el catálogo."}), 400

      pres_id = str(it.presentacionId or "").strip()
      if not pres_id:
        pres = conn.execute("""
          SELECT pp.presentacion_id, pp.base_price, pp.admin_gain, pp.inv_gain, pp.flete
          FROM producto_presentaciones pp
          JOIN presentaciones pr ON pr.id = pp.presentacion_id
          WHERE pp.producto_id=? AND pp.activa=1 AND pr.activa=1
          ORDER BY pr.orden, pr.factor, pr.nombre COLLATE NOCASE LIMIT 1
        """, (pid,)).fetchone()
        if not pres:
          return jsonify({"error": f"El producto {pid} no tiene presentaciones disponibles."}), 400
        pres_id = pres["presentacion_id"]
      else:
        pres = conn.execute("""
          SELECT pp.presentacion_id, pp.base_price, pp.admin_gain, pp.inv_gain, pp.flete
          FROM producto_presentaciones pp
          JOIN presentaciones pr ON pr.id = pp.presentacion_id
          WHERE pp.producto_id=? AND pp.presentacion_id=? AND pp.activa=1 AND pr.activa=1
        """, (pid, pres_id)).fetchone()
        if not pres:
          return jsonify({"error": f"La presentación seleccionada no está disponible para el producto {pid}."}), 400

      base = float(it.costoBase if it.costoBase is not None else pres["base_price"] or 0)
      admin = float(it.adminGain if it.adminGain is not None else pres["admin_gain"] or 0)
      inv = float(it.invGain if it.invGain is not None else pres["inv_gain"] or 0)
      flete = float(it.flete if it.flete is not None else pres["flete"] or 0)
      if None in (base, admin, inv, flete):
        return jsonify({"error": "Los valores de precio deben ser números válidos."}), 400

      items_a_insertar.append((pid, pres_id, cant, base, admin, inv, flete))
      total_costo += base * cant
      total_admin += admin * cant
      total_inv += inv * cant
      total_flete += flete * cant

    if existente:
      conn.execute(
          "UPDATE combos SET nombre=?, costo_base=?, admin_gain=?, inv_gain=?, flete=?, activo=1 WHERE id=?",
          (nombre, total_costo, total_admin, total_inv, total_flete, combo_id),
      )
      conn.execute("DELETE FROM combo_items WHERE combo_id=?", (combo_id,))
    else:
      conn.execute(
          "INSERT INTO combos (id, nombre, costo_base, admin_gain, inv_gain, flete, activo) VALUES (?, ?, ?, ?, ?, ?, 1)",
          (combo_id, nombre, total_costo, total_admin, total_inv, total_flete),
      )

    for pid, pres_id, cant, base, admin, inv, flete in items_a_insertar:
      conn.execute(
          """
          INSERT INTO combo_items (combo_id, producto_id, presentacion_id, cantidad, costo_base, admin_gain, inv_gain, flete)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (combo_id, pid, pres_id, cant, base, admin, inv, flete),
      )

    conn.commit()
    combo = _combo_json(conn, combo_id)
    return jsonify({"status": "success", "combo": combo})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_combos_bp.route("/api/combo/<combo_id>", methods=["DELETE"])
def api_eliminar_combo(combo_id):
  conn = get_db_connection()
  try:
    conn.execute("UPDATE combos SET activo = 0 WHERE id = ?", (combo_id,))
    conn.commit()
    return jsonify({"status": "deleted"})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()