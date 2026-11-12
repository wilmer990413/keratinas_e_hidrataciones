import math
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.database import get_db_connection, now_colombia

api_ventas_bp = Blueprint("api_ventas", __name__)


def _entero_positivo(valor):
  """Devuelve el entero (> 0) o None. Rechaza texto, booleanos, decimales, NaN e infinito."""
  if isinstance(valor, bool) or not isinstance(valor, (int, float)):
    return None
  if isinstance(valor, float) and (not math.isfinite(valor) or valor != int(valor)):
    return None
  valor = int(valor)
  return valor if 0 < valor <= 1_000_000_000 else None


def _descontar_stock(conn, items):
  """Valida presentaciones y descuenta unidades del stock único del producto.

  El cliente envía cantidad de presentaciones, pero el backend calcula las unidades reales
  usando el factor almacenado en SQLite.
  """
  if not items:
    return []
  if not isinstance(items, list):
    raise ValueError("El detalle de productos de la venta no es válido.")

  agrupados = {}
  for item in items:
    if not isinstance(item, dict):
      raise ValueError("Cada producto de la venta debe ser un objeto válido.")
    pid = str(item.get("productoId", "")).strip()
    pres_id = str(item.get("presentacionId", "")).strip()
    cantidad = _entero_positivo(item.get("cantidad"))
    if not pid or not pres_id or cantidad is None:
      raise ValueError("Cada producto debe tener producto, presentación y cantidad entera mayor que 0.")

    rel = conn.execute(
      """
      SELECT pr.id AS producto_id, pr.nombre AS producto_nombre, pr.stock,
             pp.presentacion_id, p.nombre AS presentacion_nombre, p.factor
      FROM productos pr
      JOIN producto_presentaciones pp ON pp.producto_id = pr.id AND pp.activa = 1
      JOIN presentaciones p ON p.id = pp.presentacion_id AND p.activa = 1
      WHERE pr.id = ? AND pp.presentacion_id = ?
      """, (pid, pres_id)
    ).fetchone()
    if not rel:
      raise ValueError("El producto o la presentación seleccionada ya no están disponibles. Actualice la página e intente de nuevo.")

    unidades = cantidad * int(rel["factor"])
    key = (pid, pres_id)
    agrupados[key] = {
      "productoId": pid,
      "productoNombre": rel["producto_nombre"],
      "presentacionId": pres_id,
      "presentacionNombre": rel["presentacion_nombre"],
      "factor": int(rel["factor"]),
      "cantidad": agrupados.get(key, {}).get("cantidad", 0) + cantidad,
      "unidades": agrupados.get(key, {}).get("unidades", 0) + unidades,
    }

  # Si el mismo producto aparece con presentaciones diferentes, el stock se comparte.
  por_producto = {}
  for item in agrupados.values():
    por_producto[item["productoId"]] = por_producto.get(item["productoId"], 0) + item["unidades"]

  for pid, unidades in por_producto.items():
    fila = conn.execute("SELECT nombre, stock FROM productos WHERE id = ?", (pid,)).fetchone()
    if not fila:
      raise ValueError("Uno de los productos de la venta ya no existe en el catálogo.")
    cur = conn.execute(
      "UPDATE productos SET stock = stock - ? WHERE id = ? AND stock >= ?",
      (unidades, pid, unidades)
    )
    if cur.rowcount != 1:
      raise ValueError(
        f"Stock insuficiente de «{fila['nombre']}»: disponible {fila['stock']} ud, solicitado {unidades} ud."
      )

  return list(agrupados.values())


def _calcular_auxiliares(conn, auxiliares_data, admin_share):
  if not auxiliares_data:
    return [], 0.0

  total_porcentaje = sum(float(x.get("porcentaje", 0)) for x in auxiliares_data)
  if total_porcentaje <= 0 or total_porcentaje >= 100:
    raise ValueError("La suma de los porcentajes de los auxiliares debe ser mayor que 0% y menor que 100%.")

  ids = [str(x.get("id", "")).strip() for x in auxiliares_data]
  if any(not x for x in ids) or len(ids) != len(set(ids)):
    raise ValueError("Cada auxiliar debe ser seleccionado una sola vez.")

  placeholders = ",".join("?" for _ in ids)
  rows = conn.execute(
      f"SELECT id, nombre FROM auxiliares WHERE id IN ({placeholders}) AND activo = 1",
      ids,
  ).fetchall()
  if len(rows) != len(ids):
    raise ValueError("Uno o más auxiliares no existen o están inactivos.")

  admin_share = float(admin_share)
  if admin_share <= 0:
    raise ValueError("La ganancia/valor de la administradora debe ser mayor que 0 cuando hay auxiliares.")

  # La fórmula actual del proyecto es: Total = Materia Prima + Administradora + Auxiliares.
  # Si el porcentaje representa la participación del auxiliar sobre la MANO DE OBRA
  # (Administradora + Auxiliares), se resuelve: Aux = % * ManoObra.
  # Por tanto: ManoObra = Admin / (1 - %Total).
  base_mano_obra = admin_share / (1 - total_porcentaje / 100)
  resultado = []
  total_aux = 0.0
  for item in auxiliares_data:
    pct = float(item.get("porcentaje", 0))
    if pct <= 0 or pct >= 100:
      raise ValueError("Cada porcentaje debe estar entre 0% y 100%.")
    pago = base_mano_obra * pct / 100
    resultado.append((item["id"], pct, base_mano_obra, pago))
    total_aux += pago
  return resultado, total_aux


def _jornada_actual_id(conn):
  row = conn.execute("SELECT id FROM jornadas WHERE activa = 1 ORDER BY rowid DESC LIMIT 1").fetchone()
  if row:
    return row["id"]
  ahora = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
  jid = "JOR-" + str(__import__("time").time_ns())
  conn.execute("INSERT INTO jornadas(id, iniciada_en, activa) VALUES(?,?,1)", (jid, ahora))
  return jid


def _normalizar_fecha_colombia(valor):
  """Normaliza una fecha/hora introducida por el usuario, tratándola como hora Colombia."""
  texto = str(valor or "").strip().replace("T", " ")
  if not texto:
    raise ValueError("La fecha y hora son obligatorias.")
  try:
    dt = datetime.strptime(texto[:16], "%Y-%m-%d %H:%M")
  except ValueError:
    try:
      dt = datetime.strptime(texto[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
      raise ValueError("La fecha y hora no tienen un formato válido.")
  return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")


@api_ventas_bp.route("/api/transaccion", methods=["POST"])
def api_transaccion():
  data = request.json or {}
  cliente = str(data.get("cliente", "")).strip()
  tipo_servicio = data.get("tipoServicio", "")
  if not cliente or not tipo_servicio:
    return jsonify({"error": "Cliente y tipo de servicio son obligatorios."}), 400

  conn = get_db_connection()
  cursor = conn.cursor()
  try:
    auxiliares_data = data.get("auxiliares", []) or []
    admin_share = float(data.get("adminShare", 0))
    materia_prima = float(data.get("materiaPrimaShare", 0))
    total = float(data.get("total", 0))

    mappings, aux_share = _calcular_auxiliares(conn, auxiliares_data, admin_share)

    # Ventas de productos: se descuentan las unidades del stock (falla si no alcanza).
    items_stock = _descontar_stock(conn, data.get("items"))
    items_combos = _descontar_stock_combos(conn, data.get("combos"))

    # Parte del inversionista: se guarda desglosada en inversión (costo) y ganancia.
    inv_share = float(data.get("invShare", materia_prima))
    inversion_raw, ganancia_raw = data.get("inversionShare"), data.get("gananciaInvShare")
    if inversion_raw is not None and ganancia_raw is not None:
      inversion, ganancia = float(inversion_raw), float(ganancia_raw)
      if inversion < 0 or ganancia < 0:
        raise ValueError("La inversión y la ganancia del inversionista no pueden ser negativas.")
      inv_share = round(inversion + ganancia, 2)
    elif not str(tipo_servicio).startswith("Prod:"):
      inversion, ganancia = materia_prima, round(inv_share - materia_prima, 2)
    else:
      inversion = ganancia = None

    if str(tipo_servicio).startswith("Prod:"):
      # Venta de productos o combos: el total es lo que paga el cliente (precio de venta):
      # ganancia de la administradora + parte del inversionista (costo base + flete + su ganancia).
      total = round(admin_share + inv_share, 2)
    else:
      # Servicios: el backend es la fuente de verdad del cálculo.
      # Para conservar la lógica de los servicios sin auxiliar, total = admin + materia + auxiliares.
      total_calculado = materia_prima + admin_share + aux_share
      if abs(total_calculado - total) > 0.01:
        total = total_calculado

    cursor.execute(
        """
        INSERT INTO transacciones (id, fecha_hora, fecha_dia, cliente, tipo_servicio, total,
          admin_share, aux_share, materia_prima_share, inv_share, flete_total,
          inversion_share, ganancia_inv_share, jornada_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["id"], now_colombia().strftime("%Y-%m-%d %H:%M:%S"), now_colombia().strftime("%Y-%m-%d"), cliente,
            tipo_servicio, total, admin_share, aux_share, materia_prima,
            inv_share, float(data.get("fleteTotal", 0)), inversion, ganancia, _jornada_actual_id(conn),
        ),
    )

    for aux_id, pct, base_mano_obra, pago in mappings:
      cursor.execute(
          """
          INSERT INTO servicio_auxiliares (transaccion_id, auxiliar_id, porcentaje, base_mano_obra, pago)
          VALUES (?, ?, ?, ?, ?)
          """,
          (data["id"], aux_id, pct, base_mano_obra, pago),
      )

    for item in items_stock:
      cursor.execute(
          """
          INSERT INTO venta_items
            (transaccion_id, producto_id, producto_nombre, unidades, presentacion_id, presentacion_nombre, factor_presentacion)
          VALUES (?, ?, ?, ?, ?, ?, ?)
          """,
          (data["id"], item["productoId"], item["productoNombre"], item["unidades"],
           item["presentacionId"], item["presentacionNombre"], item["factor"]),
      )

    # Insertar items de combos en venta_items (para que al eliminar la venta, el stock retorne intacto)
    for it in items_combos:
      cursor.execute(
          """
          INSERT INTO venta_items
            (transaccion_id, producto_id, producto_nombre, unidades, presentacion_id, presentacion_nombre, factor_presentacion)
          VALUES (?, ?, ?, ?, 'combo', ?, 1)
          """,
          (data["id"], it["productoId"], it["productoNombre"], it["unidades"], f"Combo: {it['comboNombre']}"),
      )

    conn.commit()
    return jsonify({
        "status": "success",
        "total": total,
        "auxShare": aux_share,
        "baseManoObra": mappings[0][2] if mappings else admin_share,
    })
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_ventas_bp.route("/api/transaccion/<id_tx>", methods=["GET"])
def api_obtener_transaccion(id_tx):
  conn = get_db_connection()
  try:
    tx = conn.execute("SELECT * FROM transacciones WHERE id = ?", (id_tx,)).fetchone()
    if not tx:
      return jsonify({"error": "Venta no encontrada."}), 404
    aux = conn.execute(
      """SELECT sa.auxiliar_id id, a.nombre, sa.porcentaje, sa.base_mano_obra, sa.pago
         FROM servicio_auxiliares sa JOIN auxiliares a ON a.id=sa.auxiliar_id
         WHERE sa.transaccion_id=? ORDER BY a.nombre COLLATE NOCASE""", (id_tx,)
    ).fetchall()
    items = conn.execute(
      """SELECT producto_id, producto_nombre, unidades, presentacion_id, presentacion_nombre, factor_presentacion
         FROM venta_items WHERE transaccion_id=? ORDER BY id""", (id_tx,)
    ).fetchall()
    return jsonify({
      "id": tx["id"], "fechaHora": tx["fecha_hora"], "cliente": tx["cliente"],
      "tipoServicio": tx["tipo_servicio"], "total": tx["total"],
      "adminShare": tx["admin_share"], "auxShare": tx["aux_share"],
      "materiaPrimaShare": tx["materia_prima_share"], "invShare": tx["inv_share"],
      "fleteTotal": tx["flete_total"], "inversionShare": tx["inversion_share"],
      "gananciaInvShare": tx["ganancia_inv_share"],
      "tipo": "producto" if str(tx["tipo_servicio"]).startswith("Prod:") else "servicio",
      "auxiliares": [dict(x) for x in aux],
      "items": [dict(x) for x in items],
    })
  finally:
    conn.close()


@api_ventas_bp.route("/api/transaccion/<id_tx>", methods=["PUT"])
def api_editar_transaccion(id_tx):
  data = request.json or {}
  conn = get_db_connection()
  try:
    tx = conn.execute("SELECT * FROM transacciones WHERE id = ?", (id_tx,)).fetchone()
    if not tx:
      return jsonify({"error": "Venta no encontrada."}), 404

    cliente = str(data.get("cliente", tx["cliente"])).strip()
    if not cliente:
      raise ValueError("El cliente/comprador es obligatorio.")
    fecha_hora, fecha_dia = _normalizar_fecha_colombia(data.get("fechaHora", tx["fecha_hora"]))
    es_producto = str(tx["tipo_servicio"]).startswith("Prod:")

    if es_producto:
      admin = float(data.get("adminShare", tx["admin_share"]))
      inversion = float(data.get("inversionShare", tx["inversion_share"] if tx["inversion_share"] is not None else 0))
      ganancia = float(data.get("gananciaInvShare", tx["ganancia_inv_share"] if tx["ganancia_inv_share"] is not None else max((tx["inv_share"] or 0) - inversion, 0)))
      flete = float(data.get("fleteTotal", tx["flete_total"] or 0))
      if min(admin, inversion, ganancia, flete) < 0:
        raise ValueError("Los valores de la venta no pueden ser negativos.")
      inv_share = round(inversion + ganancia, 2)
      total = round(admin + inv_share, 2)
      conn.execute(
        """UPDATE transacciones SET fecha_hora=?, fecha_dia=?, cliente=?, total=?, admin_share=?, aux_share=0,
           materia_prima_share=0, inv_share=?, flete_total=?, inversion_share=?, ganancia_inv_share=? WHERE id=?""",
        (fecha_hora, fecha_dia, cliente, total, admin, inv_share, flete, inversion, ganancia, id_tx),
      )
    else:
      admin = float(data.get("adminShare", tx["admin_share"]))
      materia = float(data.get("materiaPrimaShare", tx["materia_prima_share"]))
      auxiliares_data = data.get("auxiliares", None)
      if auxiliares_data is None:
        aux_rows = conn.execute("SELECT auxiliar_id id, porcentaje FROM servicio_auxiliares WHERE transaccion_id=? ORDER BY id", (id_tx,)).fetchall()
        auxiliares_data = [dict(x) for x in aux_rows]
      mappings, aux_share = _calcular_auxiliares(conn, auxiliares_data, admin) if auxiliares_data else ([], 0.0)
      total = round(materia + admin + aux_share, 2)
      conn.execute(
        """UPDATE transacciones SET fecha_hora=?, fecha_dia=?, cliente=?, total=?, admin_share=?, aux_share=?,
           materia_prima_share=?, inv_share=?, inversion_share=?, ganancia_inv_share=?, flete_total=0 WHERE id=?""",
        (fecha_hora, fecha_dia, cliente, total, admin, aux_share, materia, materia, materia, 0, id_tx),
      )
      conn.execute("DELETE FROM servicio_auxiliares WHERE transaccion_id=?", (id_tx,))
      for aux_id, pct, base_mano_obra, pago in mappings:
        conn.execute(
          """INSERT INTO servicio_auxiliares(transaccion_id, auxiliar_id, porcentaje, base_mano_obra, pago)
             VALUES(?,?,?,?,?)""", (id_tx, aux_id, pct, base_mano_obra, pago)
        )

    conn.commit()
    return jsonify({"status": "updated", "id": id_tx, "total": total, "fechaHora": fecha_hora})
  except (ValueError, TypeError) as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 500
  finally:
    conn.close()


@api_ventas_bp.route("/api/transaccion/<id_tx>", methods=["DELETE"])
def api_eliminar_transaccion(id_tx):
  conn = get_db_connection()
  try:
    # Si era una venta de productos, las unidades vuelven al stock. Las ventas anteriores a la
    # función de stock no tienen detalle (venta_items) y no modifican el inventario.
    filas = conn.execute(
        "SELECT producto_id, unidades FROM venta_items WHERE transaccion_id = ?", (id_tx,)).fetchall()
    for fila in filas:
      conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (fila["unidades"], fila["producto_id"]))
    conn.execute("DELETE FROM transacciones WHERE id = ?", (id_tx,))
    conn.commit()
    return jsonify({"status": "deleted"})
  except Exception:
    conn.rollback()
    raise
  finally:
    conn.close()


@api_ventas_bp.route("/api/reiniciar-jornada", methods=["POST"])
def api_reiniciar_jornada():
  conn = get_db_connection()
  try:
    actual = conn.execute("SELECT id FROM jornadas WHERE activa=1 ORDER BY rowid DESC LIMIT 1").fetchone()
    if actual:
      ahora = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
      conn.execute("UPDATE transacciones SET activa=0 WHERE jornada_id=?", (actual["id"],))
      conn.execute("UPDATE jornadas SET activa=0, cerrada_en=? WHERE id=?", (ahora, actual["id"]))
    nueva_id = "JOR-" + str(__import__("time").time_ns())
    ahora = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO jornadas(id, iniciada_en, activa) VALUES(?,?,1)", (nueva_id, ahora))
    conn.commit()
    return jsonify({"status": "reset", "jornadaId": nueva_id, "iniciadaEn": ahora})
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 500
  finally:
    conn.close()

def _descontar_stock_combos(conn, combos_data):
  """Valida y descuenta el stock de cada producto que compone los combos vendidos."""
  if not combos_data or not isinstance(combos_data, list):
    return []

  items_deducir = []
  for c_item in combos_data:
    combo_id = str(c_item.get("comboId", "")).strip()
    cantidad_combos = _entero_positivo(c_item.get("cantidad"))
    if not combo_id or cantidad_combos is None:
      raise ValueError("Cada combo debe incluir un identificador y una cantidad válida mayor a 0.")

    combo = conn.execute("SELECT id, nombre FROM combos WHERE id = ? AND activo = 1", (combo_id,)).fetchone()
    if not combo:
      raise ValueError(f"El combo solicitado ({combo_id}) ya no está disponible.")

    componentes = conn.execute(
        """
        SELECT ci.producto_id, ci.cantidad, p.nombre, p.stock
        FROM combo_items ci
        JOIN productos p ON p.id = ci.producto_id
        WHERE ci.combo_id = ?
        """,
        (combo_id,),
    ).fetchall()

    if not componentes:
      raise ValueError(f"El combo «{combo['nombre']}» no tiene productos asociados.")

    for comp in componentes:
      unidades_a_descontar = int(comp["cantidad"]) * cantidad_combos
      items_deducir.append({
          "productoId": comp["producto_id"],
          "productoNombre": comp["nombre"],
          "unidades": unidades_a_descontar,
          "comboNombre": combo["nombre"],
          "cantidadCombos": cantidad_combos,
      })

  # Agrupar por producto por si varios combos usan el mismo producto
  por_producto = {}
  for item in items_deducir:
    pid = item["productoId"]
    por_producto[pid] = por_producto.get(pid, 0) + item["unidades"]

  for pid, unidades in por_producto.items():
    fila = conn.execute("SELECT nombre, stock FROM productos WHERE id = ?", (pid,)).fetchone()
    if not fila:
      raise ValueError("Uno de los productos del combo no existe en el catálogo.")
    cur = conn.execute(
        "UPDATE productos SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (unidades, pid, unidades),
    )
    if cur.rowcount != 1:
      raise ValueError(
          f"Stock insuficiente de «{fila['nombre']}» para despachar el combo: disponible {fila['stock']} ud, solicitado {unidades} ud."
      )

  return items_deducir
