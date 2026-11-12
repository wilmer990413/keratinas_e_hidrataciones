import io
import json
import math
from datetime import datetime
import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from app.database import get_db_connection, now_colombia

api_nomina_bp = Blueprint("api_nomina", __name__)

DESTINO_ADMIN = "admin"
DESTINO_TODOS_AUX = "auxiliares"
PREFIJO_AUX = "aux:"


def _rangos(request):
  hoy = now_colombia().strftime("%Y-%m-%d")
  inicio = request.args.get("inicio") or hoy[:8] + "01"
  fin = request.args.get("fin") or hoy
  return inicio, fin


def _leer_descuentos(request):
  """Lee y valida el parámetro `descuentos` (lista JSON). Lanza ValueError si es inválido.

  Cada descuento: {concepto, tipo: 'porcentaje'|'monto', valor, destino}
  destino: 'admin' | 'auxiliares' (se aplica a cada auxiliar) | 'aux:<id_auxiliar>'
  """
  raw = request.args.get("descuentos")
  if not raw:
    return []
  try:
    data = json.loads(raw)
  except ValueError:
    raise ValueError("El formato de los descuentos no es válido.")
  if not isinstance(data, list):
    raise ValueError("El formato de los descuentos no es válido.")

  limpios = []
  for i, d in enumerate(data, start=1):
    if not isinstance(d, dict):
      raise ValueError("El formato de los descuentos no es válido.")
    concepto = str(d.get("concepto") or "").strip() or f"Descuento {i}"
    tipo = d.get("tipo")
    if tipo not in ("porcentaje", "monto"):
      raise ValueError(f"El descuento '{concepto}' tiene un tipo inválido.")
    try:
      valor = float(d.get("valor"))
    except (TypeError, ValueError):
      raise ValueError(f"El descuento '{concepto}' no tiene un valor numérico.")
    if not math.isfinite(valor) or valor < 0:
      raise ValueError(f"El valor del descuento '{concepto}' debe ser un número mayor o igual a 0.")
    if tipo == "porcentaje" and valor > 100:
      raise ValueError(f"El descuento '{concepto}' no puede superar el 100%.")
    destino = str(d.get("destino") or "").strip()
    if destino not in (DESTINO_ADMIN, DESTINO_TODOS_AUX) and not (
        destino.startswith(PREFIJO_AUX) and len(destino) > len(PREFIJO_AUX)):
      raise ValueError(f"El descuento '{concepto}' no tiene un destinatario válido.")
    limpios.append({"concepto": concepto, "tipo": tipo, "valor": valor, "destino": destino})
  return limpios


def _descuentos_de(clave, es_admin, descuentos):
  """Descuentos que le corresponden a una persona (la administradora o un auxiliar)."""
  if es_admin:
    return [d for d in descuentos if d["destino"] == DESTINO_ADMIN]
  return [d for d in descuentos
          if d["destino"] == DESTINO_TODOS_AUX or d["destino"] == PREFIJO_AUX + clave]


def _liquidar(bruto, destinatario, lista):
  """Aplica los descuentos sobre el bruto. Los porcentajes se calculan sobre el bruto
  y el descuento acumulado nunca supera lo que la persona devengó (el neto no es negativo)."""
  restante = round(bruto, 2)
  aplicados = []
  total_desc = 0.0
  for d in lista:
    pedido = bruto * d["valor"] / 100 if d["tipo"] == "porcentaje" else d["valor"]
    pedido = round(pedido, 2)
    monto = round(min(pedido, restante), 2)
    restante = round(restante - monto, 2)
    total_desc = round(total_desc + monto, 2)
    aplicados.append({
        "concepto": d["concepto"],
        "destinatario": destinatario,
        "tipo": d["tipo"],
        "valor": d["valor"],
        "monto": monto,
        "excedido": monto < pedido,
    })
  return {"descuentos": total_desc, "neto": round(bruto - total_desc, 2), "detalle": aplicados}


def _calcular_nomina(inicio, fin, descuentos):
  # La nómina se calcula sobre TODO el histórico de ventas del rango de fechas, incluidos los
  # días ya cerrados con "Reiniciar jornada" (activa = 0), que pueden estar pendientes de pago.
  conn = get_db_connection()

  admin_row = conn.execute(
      """
      SELECT COALESCE(SUM(admin_share), 0) total, COUNT(*) cantidad
      FROM transacciones
      WHERE fecha_dia BETWEEN ? AND ?
        AND tipo_servicio NOT LIKE 'Prod:%'
      """,
      (inicio, fin),
  ).fetchone()

  aux_rows = conn.execute(
      """
      SELECT a.id, a.nombre, COUNT(sa.id) cantidad_servicios,
             COALESCE(SUM(sa.pago), 0) total,
             COALESCE(SUM(sa.porcentaje), 0) porcentaje_acumulado
      FROM servicio_auxiliares sa
      JOIN auxiliares a ON a.id = sa.auxiliar_id
      JOIN transacciones t ON t.id = sa.transaccion_id
      WHERE t.fecha_dia BETWEEN ? AND ?
      GROUP BY a.id, a.nombre
      ORDER BY a.nombre COLLATE NOCASE
      """,
      (inicio, fin),
  ).fetchall()

  detalle = conn.execute(
      """
      SELECT t.fecha_dia fecha, t.fecha_hora fecha_hora, t.cliente,
             t.tipo_servicio servicio, a.nombre auxiliar,
             sa.porcentaje, sa.base_mano_obra, sa.pago
      FROM servicio_auxiliares sa
      JOIN auxiliares a ON a.id = sa.auxiliar_id
      JOIN transacciones t ON t.id = sa.transaccion_id
      WHERE t.fecha_dia BETWEEN ? AND ?
      ORDER BY t.fecha_dia DESC, t.rowid DESC, a.nombre COLLATE NOCASE
      """,
      (inicio, fin),
  ).fetchall()

  nombres_aux = {r["id"]: r["nombre"] for r in conn.execute("SELECT id, nombre FROM auxiliares").fetchall()}
  conn.close()

  descuentos_aplicados = []

  # Administradora
  admin_bruto = round(admin_row["total"], 2)
  liq_admin = _liquidar(admin_bruto, "Administradora", _descuentos_de("", True, descuentos))
  descuentos_aplicados.extend(liq_admin["detalle"])

  # Auxiliares
  auxiliares = []
  ids_con_pago = set()
  for r in aux_rows:
    ids_con_pago.add(r["id"])
    bruto = round(r["total"], 2)
    liq = _liquidar(bruto, r["nombre"], _descuentos_de(r["id"], False, descuentos))
    descuentos_aplicados.extend(liq["detalle"])
    auxiliares.append({
        "id": r["id"],
        "nombre": r["nombre"],
        "cantidadServicios": r["cantidad_servicios"],
        "total": bruto,
        "descuentos": liq["descuentos"],
        "neto": liq["neto"],
    })

  # Avisos: descuentos dirigidos a un auxiliar que no tiene pagos en el periodo.
  avisos = []
  for d in descuentos:
    if d["destino"].startswith(PREFIJO_AUX):
      aux_id = d["destino"][len(PREFIJO_AUX):]
      if aux_id not in ids_con_pago:
        nombre = nombres_aux.get(aux_id, "un auxiliar")
        avisos.append(f"El descuento '{d['concepto']}' no se aplicó: {nombre} no tiene pagos en el periodo.")
  for d in descuentos_aplicados:
    if d["excedido"]:
      avisos.append(
          f"El descuento '{d['concepto']}' de {d['destinatario']} se limitó al total devengado (el neto no puede ser negativo).")

  detalle_json = [
      {
          "fecha": r["fecha"],
          "fechaHora": r["fecha_hora"],
          "cliente": r["cliente"],
          "servicio": r["servicio"],
          "auxiliar": r["auxiliar"],
          "porcentaje": r["porcentaje"],
          "baseManoObra": r["base_mano_obra"],
          "pago": r["pago"],
      }
      for r in detalle
  ]

  total_aux = round(sum(x["total"] for x in auxiliares), 2)
  total_aux_desc = round(sum(x["descuentos"] for x in auxiliares), 2)
  total_aux_neto = round(sum(x["neto"] for x in auxiliares), 2)
  total_bruto = round(admin_bruto + total_aux, 2)
  total_descuentos = round(liq_admin["descuentos"] + total_aux_desc, 2)
  total_neto = round(liq_admin["neto"] + total_aux_neto, 2)

  return {
      "inicio": inicio,
      "fin": fin,
      "administradora": {
          "cantidadServicios": admin_row["cantidad"],
          "total": admin_bruto,
          "descuentos": liq_admin["descuentos"],
          "neto": liq_admin["neto"],
      },
      "auxiliares": auxiliares,
      "totalAuxiliares": total_aux,
      "totalAuxiliaresDescuentos": total_aux_desc,
      "totalAuxiliaresNeto": total_aux_neto,
      "totalNomina": total_bruto,
      "totalBruto": total_bruto,
      "totalDescuentos": total_descuentos,
      "totalNeto": total_neto,
      "descuentosAplicados": descuentos_aplicados,
      "avisos": avisos,
      "detalle": detalle_json,
  }


@api_nomina_bp.route("/api/nomina", methods=["GET"])
def consultar_nomina():
  inicio, fin = _rangos(request)
  try:
    descuentos = _leer_descuentos(request)
  except ValueError as e:
    return jsonify({"error": str(e)}), 400
  return jsonify(_calcular_nomina(inicio, fin, descuentos))


@api_nomina_bp.route("/api/exportar-nomina-excel", methods=["GET"])
def exportar_nomina_excel():
  inicio, fin = _rangos(request)
  try:
    descuentos = _leer_descuentos(request)
  except ValueError as e:
    return jsonify({"error": str(e)}), 400
  nomina = _calcular_nomina(inicio, fin, descuentos)

  admin = pd.DataFrame([{
      "Concepto": "Nómina Administradora",
      "Servicios": nomina["administradora"]["cantidadServicios"],
      "Bruto": nomina["administradora"]["total"],
      "Descuentos": nomina["administradora"]["descuentos"],
      "Neto_Pagar": nomina["administradora"]["neto"],
  }])
  resumen = pd.DataFrame(
      [{
          "Auxiliar": a["nombre"],
          "Servicios": a["cantidadServicios"],
          "Bruto": a["total"],
          "Descuentos": a["descuentos"],
          "Neto_Pagar": a["neto"],
      } for a in nomina["auxiliares"]],
      columns=["Auxiliar", "Servicios", "Bruto", "Descuentos", "Neto_Pagar"],
  )
  descuentos_df = pd.DataFrame(
      [{
          "Concepto": d["concepto"],
          "Destinatario": d["destinatario"],
          "Tipo": "Porcentaje" if d["tipo"] == "porcentaje" else "Monto fijo",
          "Valor": d["valor"],
          "Monto_Descontado": d["monto"],
      } for d in nomina["descuentosAplicados"]],
      columns=["Concepto", "Destinatario", "Tipo", "Valor", "Monto_Descontado"],
  )
  detalle = pd.DataFrame(
      [{
          "Fecha": d["fecha"],
          "Hora": d["fechaHora"],
          "Cliente": d["cliente"],
          "Procedimiento": d["servicio"],
          "Auxiliar": d["auxiliar"],
          "Porcentaje": d["porcentaje"],
          "Base_Mano_Obra": d["baseManoObra"],
          "Pago": d["pago"],
      } for d in reversed(nomina["detalle"])],
      columns=["Fecha", "Hora", "Cliente", "Procedimiento", "Auxiliar", "Porcentaje", "Base_Mano_Obra", "Pago"],
  )
  totales = pd.DataFrame([{
      "Bruto": nomina["totalBruto"],
      "Descuentos": nomina["totalDescuentos"],
      "Neto_Pagar": nomina["totalNeto"],
  }])

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    totales.to_excel(writer, index=False, sheet_name="Totales")
    admin.to_excel(writer, index=False, sheet_name="Administradora")
    resumen.to_excel(writer, index=False, sheet_name="Auxiliares")
    descuentos_df.to_excel(writer, index=False, sheet_name="Descuentos")
    detalle.to_excel(writer, index=False, sheet_name="Detalle")
  output.seek(0)
  filename = f"nomina_{inicio}_{fin}.xlsx"
  return send_file(
      output,
      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      as_attachment=True,
      download_name=filename,
  )


@api_nomina_bp.route("/api/desprendible-nomina", methods=["GET"])
def desprendible_nomina():
  """Datos del desprendible de nómina de una persona (administradora o un auxiliar).

  persona: 'admin' | 'aux:<id_auxiliar>'. Solo se aplican los descuentos dirigidos a esa persona.
  """
  inicio, fin = _rangos(request)
  persona = (request.args.get("persona") or "").strip()
  if not persona:
    return jsonify({"error": "Seleccione a quién desea liquidar la nómina."}), 400
  try:
    descuentos = _leer_descuentos(request)
  except ValueError as e:
    return jsonify({"error": str(e)}), 400

  conn = get_db_connection()
  if persona == DESTINO_ADMIN:
    filas = conn.execute(
        """
        SELECT fecha_dia fecha, fecha_hora, cliente, tipo_servicio servicio, admin_share valor
        FROM transacciones
        WHERE fecha_dia BETWEEN ? AND ?
            AND tipo_servicio NOT LIKE 'Prod:%'
        ORDER BY fecha_dia, rowid
        """,
        (inicio, fin),
    ).fetchall()
    empleado = {"nombre": "Administradora", "documento": "", "telefono": "", "cargo": "Administradora"}
    ingresos = [
        {
            "fecha": r["fecha"],
            "fechaHora": r["fecha_hora"],
            "cliente": r["cliente"],
            "servicio": r["servicio"],
            "porcentaje": None,
            "baseManoObra": None,
            "valor": round(r["valor"], 2),
        }
        for r in filas
    ]
    total_devengado = round(sum(r["valor"] for r in filas), 2)
    aplicables = _descuentos_de("", True, descuentos)
    destinatario = "Administradora"
  elif persona.startswith(PREFIJO_AUX) and len(persona) > len(PREFIJO_AUX):
    aux_id = persona[len(PREFIJO_AUX):]
    aux = conn.execute("SELECT * FROM auxiliares WHERE id = ?", (aux_id,)).fetchone()
    if not aux:
      conn.close()
      return jsonify({"error": "No se encontró el auxiliar seleccionado."}), 404
    filas = conn.execute(
        """
        SELECT t.fecha_dia fecha, t.fecha_hora fecha_hora, t.cliente,
               t.tipo_servicio servicio, sa.porcentaje, sa.base_mano_obra, sa.pago valor
        FROM servicio_auxiliares sa
        JOIN transacciones t ON t.id = sa.transaccion_id
        WHERE sa.auxiliar_id = ? AND t.fecha_dia BETWEEN ? AND ?
        ORDER BY t.fecha_dia, t.rowid
        """,
        (aux_id, inicio, fin),
    ).fetchall()
    empleado = {
        "nombre": aux["nombre"],
        "documento": aux["documento"] or "",
        "telefono": aux["telefono"] or "",
        "cargo": "Auxiliar",
    }
    ingresos = [
        {
            "fecha": r["fecha"],
            "fechaHora": r["fecha_hora"],
            "cliente": r["cliente"],
            "servicio": r["servicio"],
            "porcentaje": r["porcentaje"],
            "baseManoObra": round(r["base_mano_obra"], 2),
            "valor": round(r["valor"], 2),
        }
        for r in filas
    ]
    total_devengado = round(sum(r["valor"] for r in filas), 2)
    aplicables = _descuentos_de(aux_id, False, descuentos)
    destinatario = aux["nombre"]
  else:
    conn.close()
    return jsonify({"error": "La persona seleccionada no es válida."}), 400
  conn.close()

  liq = _liquidar(total_devengado, destinatario, aplicables)
  avisos = [
      f"El descuento '{d['concepto']}' se limitó al total devengado (el neto no puede ser negativo)."
      for d in liq["detalle"] if d["excedido"]
  ]
  return jsonify({
      "empresa": "Keratinas e Hidrataciones by Erika",
      "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
      "inicio": inicio,
      "fin": fin,
      "empleado": empleado,
      "cantidadServicios": len(ingresos),
      "ingresos": ingresos,
      "totalDevengado": total_devengado,
      "descuentos": liq["detalle"],
      "totalDescuentos": liq["descuentos"],
      "neto": liq["neto"],
      "avisos": avisos,
  })
