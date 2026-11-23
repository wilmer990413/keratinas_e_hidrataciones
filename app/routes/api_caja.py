from datetime import datetime
import json
import io
from flask import Blueprint, jsonify, request, send_file
from app.database import get_db_connection, now_colombia

api_caja_bp = Blueprint("api_caja", __name__)


def _obtener_resumen_caja(conn, fecha_dia):
    """Calcula el balance completo del día en tiempo real:

    - Ventas de productos y servicios cobrados.
    - Egresos del día clasificados por bolsillo (FLETE, REINVERSION, GENERAL).
    - Estado exacto del Bolsillo de Flete.
    - Estado exacto del Bolsillo de Reinversión (Costo Base).
    - Ganancia neta de la Administradora (Erika).
    - Ganancias y capital de retorno desglosados DINÁMICAMENTE por cada Inversionista.
    - Saldo total esperado en caja/cuentas.
    """
    # 1. Ventas y transacciones del día
    txs = conn.execute(
        """
        SELECT id, total, admin_share, aux_share, inv_share, flete_total,
               inversion_share, ganancia_inv_share, tipo_servicio
        FROM transacciones
        WHERE fecha_dia = ? AND activa = 1
        """,
        (fecha_dia,),
    ).fetchall()

    total_ingresos = round(sum(float(t["total"] or 0) for t in txs), 2)
    ganancia_admin_servicios_prod = round(sum(float(t["admin_share"] or 0) for t in txs), 2)
    flete_cobrado_ventas = round(sum(float(t["flete_total"] or 0) for t in txs), 2)

    # 2. Desglose detallado por ítem de venta para productos del día
    items = conn.execute(
        """
        SELECT vi.producto_id, vi.producto_nombre, vi.unidades,
               vi.costo_inversion, vi.ganancia_inversionista, vi.flete, vi.inversionista_id,
               COALESCE(inv.nombre, vi.inversionista_nombre, 'Sin Inversionista') AS inv_nombre
        FROM venta_items vi
        JOIN transacciones t ON t.id = vi.transaccion_id
        LEFT JOIN inversionistas inv ON inv.id = vi.inversionista_id
        WHERE t.fecha_dia = ? AND t.activa = 1
        """,
        (fecha_dia,),
    ).fetchall()

    total_reinversion_cobrado = round(sum(float(it["costo_inversion"] or 0) for it in items), 2)

    # Agrupar dinámicamente por Inversionista
    inv_map = {}
    # Obtener todos los inversionistas registrados activos para que aparezcan en la tabla aunque tengan $0
    todos_inv = conn.execute("SELECT id, nombre FROM inversionistas WHERE activo = 1 ORDER BY nombre").fetchall()
    for row in todos_inv:
        inv_map[row["id"]] = {
            "id": row["id"],
            "nombre": row["nombre"],
            "unidadesVendidas": 0,
            "gananciaNeta": 0.0,
            "capitalRetorno": 0.0,
            "totalLiquidar": 0.0,
            "productos": {},
        }

    for it in items:
        inv_id = it["inversionista_id"]
        inv_nom = it["inv_nombre"]
        if not inv_id:
            inv_id = "SIN_ASIGNAR"
        if inv_id not in inv_map:
            inv_map[inv_id] = {
                "id": inv_id,
                "nombre": inv_nom,
                "unidadesVendidas": 0,
                "gananciaNeta": 0.0,
                "capitalRetorno": 0.0,
                "totalLiquidar": 0.0,
                "productos": {},
            }
        unidades = int(it["unidades"] or it["cantidad"] or 0)
        gan = round(float(it["ganancia_inversionista"] or 0), 2)
        cap = round(float(it["costo_inversion"] or 0), 2)

        inv_map[inv_id]["unidadesVendidas"] += unidades
        inv_map[inv_id]["gananciaNeta"] = round(inv_map[inv_id]["gananciaNeta"] + gan, 2)
        inv_map[inv_id]["capitalRetorno"] = round(inv_map[inv_id]["capitalRetorno"] + cap, 2)
        inv_map[inv_id]["totalLiquidar"] = round(inv_map[inv_id]["gananciaNeta"] + inv_map[inv_id]["capitalRetorno"], 2)

        p_nom = it["producto_nombre"]
        if p_nom not in inv_map[inv_id]["productos"]:
            inv_map[inv_id]["productos"][p_nom] = {"unidades": 0, "ganancia": 0.0, "capital": 0.0}
        inv_map[inv_id]["productos"][p_nom]["unidades"] += unidades
        inv_map[inv_id]["productos"][p_nom]["ganancia"] = round(inv_map[inv_id]["productos"][p_nom]["ganancia"] + gan, 2)
        inv_map[inv_id]["productos"][p_nom]["capital"] = round(inv_map[inv_id]["productos"][p_nom]["capital"] + cap, 2)

    inversionistas_resumen = list(inv_map.values())
    total_ganancias_inversionistas = round(sum(i["gananciaNeta"] for i in inversionistas_resumen), 2)

    # 3. Egresos del día
    egresos_rows = conn.execute(
        """
        SELECT id, fecha, fecha_dia, bolsillo, categoria, descripcion, monto,
               inversionista_id, inversionista_nombre, creado_en
        FROM caja_egresos
        WHERE fecha_dia = ? AND activo = 1
        ORDER BY creado_en DESC
        """,
        (fecha_dia,),
    ).fetchall()

    egresos_lista = [
        {
            "id": r["id"],
            "fecha": r["fecha"],
            "fechaDia": r["fecha_dia"],
            "bolsillo": r["bolsillo"],
            "categoria": r["categoria"],
            "descripcion": r["descripcion"],
            "monto": float(r["monto"] or 0),
            "inversionistaId": r["inversionista_id"],
            "inversionistaNombre": r["inversionista_nombre"] or "",
            "creadoEn": r["creado_en"],
        }
        for r in egresos_rows
    ]

    total_egresos = round(sum(e["monto"] for e in egresos_lista), 2)
    egresos_flete = round(sum(e["monto"] for e in egresos_lista if e["bolsillo"] == "FLETE"), 2)
    egresos_reinversion = round(sum(e["monto"] for e in egresos_lista if e["bolsillo"] == "REINVERSION"), 2)
    egresos_otros = round(sum(e["monto"] for e in egresos_lista if e["bolsillo"] == "GENERAL"), 2)

    # 4. Balances de bolsillos
    saldo_flete = round(flete_cobrado_ventas - egresos_flete, 2)
    saldo_reinversion = round(total_reinversion_cobrado - egresos_reinversion, 2)
    saldo_teorico_caja = round(total_ingresos - total_egresos, 2)

    # 5. Cierre registrado si ya existe
    cierre_row = conn.execute(
        "SELECT * FROM caja_cierres WHERE fecha_dia = ?", (fecha_dia,)
    ).fetchone()

    cierre_data = None
    if cierre_row:
        cierre_data = {
            "id": cierre_row["id"],
            "fechaCierre": cierre_row["fecha_cierre"],
            "saldoRealBanco": float(cierre_row["saldo_real_banco"] or 0),
            "diferencia": float(cierre_row["diferencia"] or 0),
            "observaciones": cierre_row["observaciones"] or "",
            "cerradoPor": cierre_row["cerrado_por"] or "Administrador",
        }

    return {
        "fecha": fecha_dia,
        "totales": {
            "ingresos": total_ingresos,
            "egresos": total_egresos,
            "saldoTeorico": saldo_teorico_caja,
        },
        "bolsilloFlete": {
            "cobrado": flete_cobrado_ventas,
            "gastado": egresos_flete,
            "saldo": saldo_flete,
        },
        "bolsilloReinversion": {
            "cobrado": total_reinversion_cobrado,
            "gastado": egresos_reinversion,
            "saldo": saldo_reinversion,
        },
        "ganancias": {
            "administradora": ganancia_admin_servicios_prod,
            "totalInversionistas": total_ganancias_inversionistas,
        },
        "inversionistas": inversionistas_resumen,
        "egresos": egresos_lista,
        "cierre": cierre_data,
    }


@api_caja_bp.route("/api/caja/resumen", methods=["GET"])
def obtener_resumen_caja():
    fecha_dia = request.args.get("fecha") or now_colombia().strftime("%Y-%m-%d")
    conn = get_db_connection()
    try:
        data = _obtener_resumen_caja(conn, fecha_dia)
        return jsonify(data)
    except Exception as e:
        # Log the error for debugging
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": "Error interno al obtener resumen", "details": str(e)}), 500
    finally:
        conn.close()


@api_caja_bp.route("/api/caja/egreso", methods=["POST"])
def registrar_egreso():
    data = request.get_json() or {}
    monto = float(data.get("monto") or 0)
    if monto <= 0:
        return jsonify({"error": "El monto del egreso debe ser mayor a 0."}), 400

    bolsillo = str(data.get("bolsillo", "FLETE")).strip().upper()
    if bolsillo not in {"FLETE", "REINVERSION", "GENERAL"}:
        bolsillo = "GENERAL"

    categoria = str(data.get("categoria", "OTRO")).strip()
    descripcion = str(data.get("descripcion", "")).strip()
    if not descripcion:
        return jsonify({"error": "Debe ingresar una descripción del egreso."}), 400

    fecha_dia = str(data.get("fecha") or now_colombia().strftime("%Y-%m-%d"))
    ahora_str = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
    inv_id = data.get("inversionistaId") or None
    inv_nombre = data.get("inversionistaNombre") or None

    conn = get_db_connection()
    try:
        if inv_id and not inv_nombre:
            inv = conn.execute("SELECT nombre FROM inversionistas WHERE id = ?", (inv_id,)).fetchone()
            if inv:
                inv_nombre = inv["nombre"]

        egreso_id = f"EGR-{int(datetime.now().timestamp() * 1000)}"
        conn.execute(
            """
            INSERT INTO caja_egresos
              (id, fecha, fecha_dia, bolsillo, categoria, descripcion, monto,
               inversionista_id, inversionista_nombre, creado_en, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                egreso_id,
                ahora_str,
                fecha_dia,
                bolsillo,
                categoria,
                descripcion,
                monto,
                inv_id,
                inv_nombre,
                ahora_str,
            ),
        )
        conn.commit()
        return jsonify({"ok": True, "id": egreso_id, "mensaje": "Egreso registrado correctamente."})
    finally:
        conn.close()


@api_caja_bp.route("/api/caja/egreso/<egreso_id>", methods=["DELETE"])
def anular_egreso(egreso_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE caja_egresos SET activo = 0 WHERE id = ?", (egreso_id,))
        conn.commit()
        return jsonify({"ok": True, "mensaje": "Egreso anulado correctamente."})
    finally:
        conn.close()


@api_caja_bp.route("/api/caja/cierre", methods=["POST"])
def guardar_cierre_caja():
    data = request.get_json() or {}
    fecha_dia = str(data.get("fecha") or now_colombia().strftime("%Y-%m-%d"))
    saldo_real = float(data.get("saldoRealBanco") or 0)
    observaciones = str(data.get("observaciones", "")).strip()

    conn = get_db_connection()
    try:
        resumen = _obtener_resumen_caja(conn, fecha_dia)
        saldo_teorico = resumen["totales"]["saldoTeorico"]
        diferencia = round(saldo_real - saldo_teorico, 2)
        ahora_str = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
        cierre_id = f"CIE-{int(datetime.now().timestamp() * 1000)}"

        inv_json = json.dumps(resumen["inversionistas"], ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO caja_cierres
              (id, fecha_dia, fecha_cierre, total_ingresos, total_egresos,
               saldo_teorico, saldo_real_banco, diferencia, total_flete_cobrado,
               egresos_flete, saldo_flete, total_reinversion_cobrado,
               egresos_reinversion, saldo_reinversion, ganancia_admin,
               ganancias_inversionistas_json, observaciones, cerrado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Administradora')
            ON CONFLICT(fecha_dia) DO UPDATE SET
              fecha_cierre = excluded.fecha_cierre,
              total_ingresos = excluded.total_ingresos,
              total_egresos = excluded.total_egresos,
              saldo_teorico = excluded.saldo_teorico,
              saldo_real_banco = excluded.saldo_real_banco,
              diferencia = excluded.diferencia,
              total_flete_cobrado = excluded.total_flete_cobrado,
              egresos_flete = excluded.egresos_flete,
              saldo_flete = excluded.saldo_flete,
              total_reinversion_cobrado = excluded.total_reinversion_cobrado,
              egresos_reinversion = excluded.egresos_reinversion,
              saldo_reinversion = excluded.saldo_reinversion,
              ganancia_admin = excluded.ganancia_admin,
              ganancias_inversionistas_json = excluded.ganancias_inversionistas_json,
              observaciones = excluded.observaciones
            """,
            (
                cierre_id,
                fecha_dia,
                ahora_str,
                resumen["totales"]["ingresos"],
                resumen["totales"]["egresos"],
                saldo_teorico,
                saldo_real,
                diferencia,
                resumen["bolsilloFlete"]["cobrado"],
                resumen["bolsilloFlete"]["gastado"],
                resumen["bolsilloFlete"]["saldo"],
                resumen["bolsilloReinversion"]["cobrado"],
                resumen["bolsilloReinversion"]["gastado"],
                resumen["bolsilloReinversion"]["saldo"],
                resumen["ganancias"]["administradora"],
                inv_json,
                observaciones,
            ),
        )
        conn.commit()
        return jsonify({"ok": True, "diferencia": diferencia, "mensaje": "Cierre de caja guardado con éxito."})
    finally:
        conn.close()


@api_caja_bp.route("/api/caja/exportar-excel", methods=["GET"])
def exportar_excel_cuadre():
    fecha_dia = request.args.get("fecha") or now_colombia().strftime("%Y-%m-%d")
    conn = get_db_connection()
    try:
        resumen = _obtener_resumen_caja(conn, fecha_dia)
    finally:
        conn.close()

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        return jsonify({"error": "Librería openpyxl no instalada."}), 500

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Cuadre {fecha_dia}"

    # Encabezado
    ws.merge_cells("A1:E1")
    ws["A1"] = f"CUADRE DIARIO DE CAJA Y BOLSILLOS - {fecha_dia}"
    ws["A1"].font = Font(size=14, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill(start_color="831843", end_color="831843", fill_type="solid")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    # Resumen Financiero
    ws["A3"] = "CONCEPTO"
    ws["B3"] = "MONTO"
    for col in ["A3", "B3"]:
        ws[col].font = Font(bold=True)
        ws[col].fill = PatternFill(start_color="FCE7F3", end_color="FCE7F3", fill_type="solid")

    filas_resumen = [
        ("Ventas Totales Recaudadas", resumen["totales"]["ingresos"]),
        ("Egresos / Gastos Totales", resumen["totales"]["egresos"]),
        ("SALDO TEÓRICO EN CAJA / BANCO", resumen["totales"]["saldoTeorico"]),
        ("---", "---"),
        ("Bolsillo Flete (Ingreso ventas)", resumen["bolsilloFlete"]["cobrado"]),
        ("Bolsillo Flete (Gastado)", resumen["bolsilloFlete"]["gastado"]),
        ("SALDO RESTANTE FLETE", resumen["bolsilloFlete"]["saldo"]),
        ("---", "---"),
        ("Bolsillo Reinversión (Costo Base vendido)", resumen["bolsilloReinversion"]["cobrado"]),
        ("Bolsillo Reinversión (Gastado en compras)", resumen["bolsilloReinversion"]["gastado"]),
        ("DISPONIBLE PARA REINVERTIR EN STOCK", resumen["bolsilloReinversion"]["saldo"]),
        ("---", "---"),
        ("Ganancia Administradora (Erika)", resumen["ganancias"]["administradora"]),
    ]

    r_idx = 4
    for conc, val in filas_resumen:
        ws[f"A{r_idx}"] = conc
        ws[f"B{r_idx}"] = val
        if isinstance(val, (int, float)):
            ws[f"B{r_idx}"].number_format = "$#,##0"
        r_idx += 1

    # Tabla Inversionistas Dinámica
    r_idx += 2
    ws[f"A{r_idx}"] = "INVERSIONISTA"
    ws[f"B{r_idx}"] = "UNIDADES"
    ws[f"C{r_idx}"] = "GANANCIA NETA"
    ws[f"D{r_idx}"] = "CAPITAL A DEVOLVER"
    ws[f"E{r_idx}"] = "TOTAL A LIQUIDAR"

    for c in ["A", "B", "C", "D", "E"]:
        ws[f"{c}{r_idx}"].font = Font(bold=True)
        ws[f"{c}{r_idx}"].fill = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")

    r_idx += 1
    for inv in resumen["inversionistas"]:
        ws[f"A{r_idx}"] = inv["nombre"]
        ws[f"B{r_idx}"] = inv["unidadesVendidas"]
        ws[f"C{r_idx}"] = inv["gananciaNeta"]
        ws[f"D{r_idx}"] = inv["capitalRetorno"]
        ws[f"E{r_idx}"] = inv["totalLiquidar"]
        for c in ["C", "D", "E"]:
            ws[f"{c}{r_idx}"].number_format = "$#,##0"
        r_idx += 1

    # Tabla Egresos del Día
    r_idx += 2
    ws[f"A{r_idx}"] = "HORA / FECHA"
    ws[f"B{r_idx}"] = "BOLSILLO"
    ws[f"C{r_idx}"] = "CATEGORÍA"
    ws[f"D{r_idx}"] = "DESCRIPCIÓN"
    ws[f"E{r_idx}"] = "MONTO GASTADO"

    for c in ["A", "B", "C", "D", "E"]:
        ws[f"{c}{r_idx}"].font = Font(bold=True)
        ws[f"{c}{r_idx}"].fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    r_idx += 1
    for eg in resumen["egresos"]:
        ws[f"A{r_idx}"] = eg["fecha"]
        ws[f"B{r_idx}"] = eg["bolsillo"]
        ws[f"C{r_idx}"] = eg["categoria"]
        ws[f"D{r_idx}"] = eg["descripcion"]
        ws[f"E{r_idx}"] = eg["monto"]
        ws[f"E{r_idx}"].number_format = "$#,##0"
        r_idx += 1

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 35
    ws.column_dimensions["E"].width = 22

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"cuadre_caja_{fecha_dia}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
