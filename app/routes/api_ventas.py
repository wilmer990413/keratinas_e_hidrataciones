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
             pr.inversionista_id, inv.nombre AS inversionista_nombre,
             pp.presentacion_id, p.nombre AS presentacion_nombre, p.factor,
             pp.base_price, pp.admin_gain, pp.inv_gain, pp.flete
      FROM productos pr
      JOIN producto_presentaciones pp ON pp.producto_id = pr.id AND pp.activa = 1
      JOIN presentaciones p ON p.id = pp.presentacion_id AND p.activa = 1
      LEFT JOIN inversionistas inv ON inv.id = pr.inversionista_id
      WHERE pr.id = ? AND pp.presentacion_id = ?
      """, (pid, pres_id)
    ).fetchone()
    if not rel:
      raise ValueError("El producto o la presentación seleccionada ya no están disponibles. Actualice la página e intente de nuevo.")

    unidades = cantidad * int(rel["factor"])
    costo_base = round(float(rel["base_price"] or 0) * unidades, 2)
    ganancia_inv = round(float(rel["inv_gain"] or 0) * unidades, 2)
    key = (pid, pres_id)
    agrupados[key] = {
      "productoId": pid,
      "productoNombre": rel["producto_nombre"],
      "presentacionId": pres_id,
      "presentacionNombre": rel["presentacion_nombre"],
      "factor": int(rel["factor"]),
      "cantidad": agrupados.get(key, {}).get("cantidad", 0) + cantidad,
      "unidades": agrupados.get(key, {}).get("unidades", 0) + unidades,
      "inversionistaId": rel["inversionista_id"],
      "inversionistaNombre": rel["inversionista_nombre"],
      "costoInversion": round(agrupados.get(key, {}).get("costoInversion", 0) + costo_base, 2),
      "gananciaInversionista": round(agrupados.get(key, {}).get("gananciaInversionista", 0) + ganancia_inv, 2),
      "adminGain": round(agrupados.get(key, {}).get("adminGain", 0) + float(rel["admin_gain"] or 0) * unidades, 2),
      "flete": round(agrupados.get(key, {}).get("flete", 0) + float(rel["flete"] or 0) * unidades, 2),
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
  from app.schemas import TransaccionCrearSchema, parse_payload
  try:
    val = parse_payload(TransaccionCrearSchema, data)
  except ValueError as err:
    return jsonify({"error": str(err)}), 400

  cliente = val.cliente
  tipo_servicio = val.tipoServicio

  conn = get_db_connection()
  cursor = conn.cursor()
  try:
    auxiliares_data = [a.model_dump() for a in val.auxiliares]
    admin_share = float(val.adminShare)
    materia_prima = float(val.materiaPrimaShare)
    total = float(val.total)

    mappings, aux_share = _calcular_auxiliares(conn, auxiliares_data, admin_share)

    # Ventas de productos: se descuentan las unidades del stock (falla si no alcanza).
    items_stock = _descontar_stock(conn, [i.model_dump() for i in (val.items or [])])
    items_combos = _descontar_stock_combos(conn, [c.model_dump() for c in (val.combos or [])])

    # Parte del inversionista: se guarda desglosada en inversión (costo) y ganancia.
    inv_share = float(val.invShare if val.invShare is not None else materia_prima)
    inversion_raw, ganancia_raw = val.inversionShare, val.gananciaInvShare
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

    inv_ids = {it.get("inversionistaId") for it in items_stock + items_combos if it.get("inversionistaId")}
    transaccion_inv_id = list(inv_ids)[0] if len(inv_ids) == 1 else None

    cursor.execute(
        """
        INSERT INTO transacciones (id, fecha_hora, fecha_dia, cliente, tipo_servicio, total,
          admin_share, aux_share, materia_prima_share, inv_share, flete_total,
          inversion_share, ganancia_inv_share, jornada_id, inversionista_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            val.id, now_colombia().strftime("%Y-%m-%d %H:%M:%S"), now_colombia().strftime("%Y-%m-%d"), cliente,
            tipo_servicio, total, admin_share, aux_share, materia_prima,
            inv_share, float(val.fleteTotal), inversion, ganancia, _jornada_actual_id(conn), transaccion_inv_id,
        ),
    )

    for aux_id, pct, base_mano_obra, pago in mappings:
      cursor.execute(
          """
          INSERT INTO servicio_auxiliares (transaccion_id, auxiliar_id, porcentaje, base_mano_obra, pago)
          VALUES (?, ?, ?, ?, ?)
          """,
          (val.id, aux_id, pct, base_mano_obra, pago),
      )

    for item in items_stock:
      cursor.execute(
          """
          INSERT INTO venta_items
            (transaccion_id, producto_id, producto_nombre, unidades, presentacion_id,
             presentacion_nombre, factor_presentacion, inversionista_id, inversionista_nombre,
             costo_inversion, ganancia_inversionista, precio_unitario, ganancia_admin, flete)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (val.id, item["productoId"], item["productoNombre"], item["unidades"],
           item["presentacionId"], item["presentacionNombre"], item["factor"],
           item.get("inversionistaId"), item.get("inversionistaNombre"),
           item.get("costoInversion", 0), item.get("gananciaInversionista", 0),
           round((float(item.get("costoInversion", 0)) + float(item.get("gananciaInversionista", 0)) + float(item.get("adminGain", 0)) + float(item.get("flete", 0))) / max(int(item["unidades"]), 1), 4),
           float(item.get("adminGain", 0)),
           float(item.get("flete", 0))),
      )

    # Insertar items de combos en venta_items (para que al eliminar la venta, el stock retorne intacto)
    for it in items_combos:
      cursor.execute(
          """
          INSERT INTO venta_items
            (transaccion_id, producto_id, producto_nombre, unidades, presentacion_id,
             presentacion_nombre, factor_presentacion, inversionista_id, inversionista_nombre,
             costo_inversion, ganancia_inversionista, precio_unitario, ganancia_admin, flete)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (val.id, it["productoId"], it["productoNombre"], it["unidades"], it.get("presentacionId") or 'combo', f"{it.get('presentacionNombre') or 'Presentación'} · Combo: {it['comboNombre']}", it.get("factor") or 1,
           it.get("inversionistaId"), it.get("inversionistaNombre"),
           it.get("costoInversion", 0), it.get("gananciaInversionista", 0),
           round((float(it.get("costoInversion", 0)) + float(it.get("gananciaInversionista", 0))) / max(int(it["unidades"]), 1), 4),
           float(it.get("adminGain", 0)),
           float(it.get("flete", 0))),
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
      """SELECT id, producto_id, producto_nombre, unidades, presentacion_id, presentacion_nombre, factor_presentacion,
                COALESCE(precio_unitario, 0) AS precio_unitario,
                COALESCE(costo_inversion, 0) AS costo_inversion,
                COALESCE(ganancia_admin, 0) AS ganancia_admin,
                COALESCE(ganancia_inversionista, 0) AS ganancia_inversionista,
                COALESCE(flete, 0) AS flete
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
  from app.schemas import TransaccionEditarSchema, parse_payload
  try:
    val = parse_payload(TransaccionEditarSchema, data)
  except ValueError as err:
    return jsonify({"error": str(err)}), 400

  conn = get_db_connection()
  try:
    tx = conn.execute("SELECT * FROM transacciones WHERE id = ?", (id_tx,)).fetchone()
    if not tx:
      return jsonify({"error": "Venta no encontrada."}), 404

    cliente = str(val.cliente if val.cliente is not None else tx["cliente"]).strip()
    if not cliente:
      raise ValueError("El cliente/comprador es obligatorio.")
    fecha_hora, fecha_dia = _normalizar_fecha_colombia(val.fechaHora if val.fechaHora else tx["fecha_hora"])
    es_producto = str(tx["tipo_servicio"]).startswith("Prod:")

    if es_producto:
      # Si el editor recibe items, esos items son la fuente de verdad. Antes de
      # reconstruirlos se devuelve al stock todo lo que tenía la venta original.
      old_items = conn.execute(
          """SELECT id, producto_id, producto_nombre, unidades, presentacion_id,
                    presentacion_nombre, factor_presentacion, inversionista_id, inversionista_nombre,
                    COALESCE(costo_inversion,0) AS costo_inversion,
                    COALESCE(ganancia_inversionista,0) AS ganancia_inversionista,
                    COALESCE(precio_unitario,0) AS precio_unitario,
                    COALESCE(ganancia_admin,0) AS ganancia_admin,
                    COALESCE(flete,0) AS flete
             FROM venta_items WHERE transaccion_id=? ORDER BY id""", (id_tx,)
      ).fetchall()
      old_by_id = {int(x["id"]): x for x in old_items}

      if val.items is None:
        # Compatibilidad con clientes antiguos: solo modifica los totales de la venta.
        admin = float(val.adminShare if val.adminShare is not None else tx["admin_share"])
        inversion = float(val.inversionShare if val.inversionShare is not None else (tx["inversion_share"] or 0))
        ganancia = float(val.gananciaInvShare if val.gananciaInvShare is not None else (tx["ganancia_inv_share"] or 0))
        flete = float(val.fleteTotal if val.fleteTotal is not None else (tx["flete_total"] or 0))
        inv_share = round(inversion + ganancia, 2)
        total = round(admin + inv_share, 2)
        conn.execute(
          """UPDATE transacciones SET fecha_hora=?, fecha_dia=?, cliente=?, total=?, admin_share=?, aux_share=0,
             materia_prima_share=0, inv_share=?, flete_total=?, inversion_share=?, ganancia_inv_share=? WHERE id=?""",
          (fecha_hora, fecha_dia, cliente, total, admin, inv_share, flete, inversion, ganancia, id_tx),
        )
      else:
        if len(val.items) == 0:
          raise ValueError("La venta debe conservar al menos un producto.")

        # Devuelve el stock original; si algo falla, toda la operación hace rollback.
        for item in old_items:
          conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (int(item["unidades"] or 0), item["producto_id"]))

        nuevos = []
        total = 0.0
        total_base = 0.0
        total_gan_inv = 0.0
        total_flete = 0.0
        total_admin = 0.0
        nombres = []

        for raw in val.items:
          pid = str(raw.productoId).strip()
          pres_id = str(raw.presentacionId).strip()
          cantidad = int(raw.cantidad)
          if cantidad <= 0:
            raise ValueError("La cantidad de cada producto debe ser mayor que 0.")

          old = old_by_id.get(int(raw.id)) if raw.id is not None else None
          # Las líneas de combo históricas no tienen una presentación de catálogo.
          if pres_id == "combo":
            if not old or old["presentacion_id"] != "combo":
              raise ValueError("No se puede agregar manualmente una línea de combo desde este editor.")
            factor = 1
            pres_nombre = old["presentacion_nombre"] or "Combo"
            unidades_historicas = max(int(old["unidades"] or 0), 1)
            base_unit_default = float(old["costo_inversion"] or 0) / unidades_historicas
            inv_unit_default = float(old["ganancia_inversionista"] or 0) / unidades_historicas
            flete_unit_default = float(old["flete"] or 0) / unidades_historicas
            admin_unit_default = float(old["ganancia_admin"] or 0) / unidades_historicas
            inversionista_id = old["inversionista_id"]
            inversionista_nombre = old["inversionista_nombre"]
          else:
            if old and old["producto_id"] == pid and old["presentacion_id"] == pres_id:
              factor = int(old["factor_presentacion"] or 1)
              pres_nombre = old["presentacion_nombre"] or "Presentación"
              unidades_historicas = max(int(old["unidades"] or 0), 1)
              base_unit_default = float(old["costo_inversion"] or 0) / unidades_historicas
              inv_unit_default = float(old["ganancia_inversionista"] or 0) / unidades_historicas
              flete_unit_default = float(old["flete"] or 0) / unidades_historicas
              admin_unit_default = float(old["ganancia_admin"] or 0) / unidades_historicas
              inversionista_id = old["inversionista_id"]
              inversionista_nombre = old["inversionista_nombre"]
            else:
              rel = conn.execute(
                """SELECT pr.id producto_id, pr.nombre producto_nombre, pr.inversionista_id,
                          inv.nombre inversionista_nombre, pp.presentacion_id, p.nombre presentacion_nombre,
                          p.factor, pp.base_price, pp.admin_gain, pp.inv_gain, pp.flete
                   FROM productos pr
                   JOIN producto_presentaciones pp ON pp.producto_id=pr.id AND pp.activa=1
                   JOIN presentaciones p ON p.id=pp.presentacion_id AND p.activa=1
                   LEFT JOIN inversionistas inv ON inv.id=pr.inversionista_id
                   WHERE pr.id=? AND pp.presentacion_id=?""", (pid, pres_id)
              ).fetchone()
              if not rel:
                raise ValueError("El producto o la presentación seleccionada no están disponibles.")
              factor = int(rel["factor"])
              pres_nombre = rel["presentacion_nombre"]
              base_unit_default = float(rel["base_price"] or 0)
              admin_unit_default = float(rel["admin_gain"] or 0)
              inv_unit_default = float(rel["inv_gain"] or 0)
              flete_unit_default = float(rel["flete"] or 0)
              inversionista_id = rel["inversionista_id"]
              inversionista_nombre = rel["inversionista_nombre"]

          # El editor actual envía el desglose completo unitario por presentación.
          componentes_enviados = all(
            getattr(raw, nombre) is not None
            for nombre in ("precioBase", "gananciaAdmin", "gananciaInv", "flete")
          )
          if componentes_enviados:
            base_unit = float(raw.precioBase)
            admin_unit = float(raw.gananciaAdmin)
            inv_unit = float(raw.gananciaInv)
            flete_unit = float(raw.flete)
            precio_final_unit = base_unit + admin_unit + inv_unit + flete_unit
            if raw.precioFinal is not None and abs(float(raw.precioFinal) - precio_final_unit) > 0.01:
              raise ValueError("El precio final no coincide con la suma de costo base, ganancia admin, ganancia del inversionista y flete.")
          else:
            base_unit = base_unit_default
            admin_unit = admin_unit_default
            inv_unit = inv_unit_default
            flete_unit = flete_unit_default
            precio_final_unit = base_unit + admin_unit + inv_unit + flete_unit

          producto = conn.execute("SELECT nombre, stock FROM productos WHERE id=?", (pid,)).fetchone()
          if not producto:
            raise ValueError("Uno de los productos seleccionados ya no existe.")

          unidades = cantidad * factor
          precio_unit = base_unit + admin_unit + inv_unit + flete_unit
          if precio_unit < 0:
            raise ValueError("El precio no puede ser negativo.")

          costo_total = base_unit * unidades
          gan_inv_total = inv_unit * unidades
          flete_total = flete_unit * unidades
          admin_total = max(admin_unit * unidades, 0)
          linea_total = precio_unit * unidades

          nuevos.append({
            "productoId": pid, "productoNombre": producto["nombre"], "unidades": unidades,
            "presentacionId": pres_id, "presentacionNombre": pres_nombre, "factor": factor,
            "inversionistaId": inversionista_id, "inversionistaNombre": inversionista_nombre,
            "costoInversion": round(costo_total, 2),
            "gananciaInversionista": round(gan_inv_total, 2),
            "precioUnitario": round(precio_unit, 4),
            "gananciaAdmin": round(admin_total, 2),
            "flete": round(flete_total, 2),
          })
          total += linea_total
          total_base += costo_total
          total_gan_inv += gan_inv_total
          total_flete += flete_total
          total_admin += admin_total
          nombres.append(f"{cantidad}x {pres_nombre} {producto['nombre']}")

        # Valida el stock completo antes de escribir las líneas nuevas.
        por_producto = {}
        for item in nuevos:
          por_producto[item["productoId"]] = por_producto.get(item["productoId"], 0) + item["unidades"]
        for pid, unidades in por_producto.items():
          fila = conn.execute("SELECT nombre, stock FROM productos WHERE id=?", (pid,)).fetchone()
          if not fila or int(fila["stock"] or 0) < unidades:
            disponible = int(fila["stock"] or 0) if fila else 0
            raise ValueError(f"Stock insuficiente de «{fila['nombre'] if fila else pid}»: disponible {disponible} ud, solicitado {unidades} ud.")
          conn.execute("UPDATE productos SET stock=stock-? WHERE id=?", (unidades, pid))

        conn.execute("DELETE FROM venta_items WHERE transaccion_id=?", (id_tx,))
        for item in nuevos:
          conn.execute(
            """INSERT INTO venta_items
              (transaccion_id, producto_id, producto_nombre, unidades, presentacion_id,
               presentacion_nombre, factor_presentacion, inversionista_id, inversionista_nombre,
               costo_inversion, ganancia_inversionista, precio_unitario, ganancia_admin, flete)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (id_tx, item["productoId"], item["productoNombre"], item["unidades"],
             item["presentacionId"], item["presentacionNombre"], item["factor"],
             item["inversionistaId"], item["inversionistaNombre"], item["costoInversion"],
             item["gananciaInversionista"], item["precioUnitario"], item["gananciaAdmin"], item["flete"]),
          )

        inv_share = round(total_base + total_flete + total_gan_inv, 2)
        total = round(total, 2)
        total_admin = round(total_admin, 2)
        conn.execute(
          """UPDATE transacciones SET fecha_hora=?, fecha_dia=?, cliente=?, tipo_servicio=?, total=?,
             admin_share=?, aux_share=0, materia_prima_share=0, inv_share=?, flete_total=?,
             inversion_share=?, ganancia_inv_share=? WHERE id=?""",
          (fecha_hora, fecha_dia, cliente, "Prod: " + ", ".join(nombres), total,
           total_admin, inv_share, round(total_flete, 2), round(total_base + total_flete, 2),
           round(total_gan_inv, 2), id_tx),
        )

    else:
      admin = float(val.adminShare if val.adminShare is not None else tx["admin_share"])
      materia = float(val.materiaPrimaShare if val.materiaPrimaShare is not None else tx["materia_prima_share"])
      auxiliares_data = [a.model_dump() for a in val.auxiliares] if val.auxiliares is not None else None
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

    # Generar copia de seguridad automática al cerrar/reiniciar jornada
    try:
      from app.backup import crear_backup
      crear_backup(motivo="cierre_jornada")
    except Exception as exc_b:
      print(f"[AVISO] No se pudo crear copia de seguridad al reiniciar jornada: {exc_b}")

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

    combo = conn.execute("SELECT id, nombre, admin_gain, flete FROM combos WHERE id = ? AND activo = 1", (combo_id,)).fetchone()
    if not combo:
      raise ValueError(f"El combo solicitado ({combo_id}) ya no está disponible.")

    componentes = conn.execute(
        """
        SELECT ci.producto_id, ci.presentacion_id, ci.cantidad, ci.costo_base, ci.inv_gain,
               ci.admin_gain, ci.flete,
               COALESCE(pr.nombre, 'Presentación') AS presentacion_nombre,
               COALESCE(pr.factor, 1) AS presentacion_factor,
               p.nombre, p.stock, p.inversionista_id, inv.nombre AS inversionista_nombre
        FROM combo_items ci
        JOIN productos p ON p.id = ci.producto_id
        LEFT JOIN presentaciones pr ON pr.id = ci.presentacion_id
        LEFT JOIN inversionistas inv ON inv.id = p.inversionista_id
        WHERE ci.combo_id = ?
        """,
        (combo_id,),
    ).fetchall()

    if not componentes:
      raise ValueError(f"El combo «{combo['nombre']}» no tiene productos asociados.")

    unidades_por_combo = sum(int(c["cantidad"] or 0) * max(int(c["presentacion_factor"] or 1), 1) for c in componentes)
    for comp in componentes:
      factor = max(int(comp["presentacion_factor"] or 1), 1)
      unidades_a_descontar = int(comp["cantidad"]) * factor * cantidad_combos
      admin_item = float(comp["admin_gain"] or 0) * cantidad_combos if float(comp["admin_gain"] or 0) > 0 else round(float(combo["admin_gain"] or 0) * cantidad_combos * (int(comp["cantidad"]) * factor) / max(unidades_por_combo, 1), 2)
      flete_item = float(comp["flete"] or 0) * cantidad_combos if float(comp["flete"] or 0) > 0 else round(float(combo["flete"] or 0) * cantidad_combos * (int(comp["cantidad"]) * factor) / max(unidades_por_combo, 1), 2)
      items_deducir.append({
          "productoId": comp["producto_id"],
          "productoNombre": comp["nombre"],
          "unidades": unidades_a_descontar,
          "presentacionId": comp["presentacion_id"],
          "presentacionNombre": comp["presentacion_nombre"],
          "factor": factor,
          "comboNombre": combo["nombre"],
          "cantidadCombos": cantidad_combos,
          "inversionistaId": comp["inversionista_id"],
          "inversionistaNombre": comp["inversionista_nombre"],
          "costoInversion": round(float(comp["costo_base"] or 0) * cantidad_combos, 2),
          "gananciaInversionista": round(float(comp["inv_gain"] or 0) * cantidad_combos, 2),
          "adminGain": round(admin_item, 2),
          "flete": round(flete_item, 2),
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
