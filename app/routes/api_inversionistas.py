from datetime import datetime
from flask import Blueprint, jsonify, request
from app.database import get_db_connection, now_colombia
from app.schemas import InversionistaGuardarSchema, parse_payload

api_inversionistas_bp = Blueprint("api_inversionistas", __name__)


def _inversionista_json(conn, row):
    prod_rows = conn.execute(
        """
        SELECT id, nombre, stock, base_price, admin_gain, inv_gain, flete
        FROM productos
        WHERE inversionista_id = ?
        ORDER BY nombre COLLATE NOCASE
        """,
        (row["id"],),
    ).fetchall()

    productos = [
        {
            "id": p["id"],
            "nombre": p["nombre"],
            "stock": p["stock"],
            "basePrice": p["base_price"],
            "adminGain": p["admin_gain"],
            "invGain": p["inv_gain"],
            "flete": p["flete"],
            "inversionTotalStock": round((p["stock"] or 0) * (p["base_price"] or 0), 2),
        }
        for p in prod_rows
    ]

    total_inversion_stock = round(sum(p["inversionTotalStock"] for p in productos), 2)

    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "documento": row["documento"] or "",
        "telefono": row["telefono"] or "",
        "porcentajeGanancia": float(row["porcentaje_ganancia"] or 0.0),
        "activo": bool(row["activo"]),
        "fechaRegistro": row["fecha_registro"] or "",
        "productos": productos,
        "totalProductos": len(productos),
        "totalInversionStock": total_inversion_stock,
    }


@api_inversionistas_bp.route("/api/inversionistas", methods=["GET"])
def listar_inversionistas():
    solo_activos = request.args.get("activos", "0") == "1"
    conn = get_db_connection()
    try:
        query = "SELECT * FROM inversionistas"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY activo DESC, nombre COLLATE NOCASE"
        rows = conn.execute(query).fetchall()
        return jsonify([_inversionista_json(conn, r) for r in rows])
    finally:
        conn.close()


@api_inversionistas_bp.route("/api/inversionista", methods=["POST", "PUT"])
def guardar_inversionista():
    data = request.get_json() or {}
    try:
        val = parse_payload(InversionistaGuardarSchema, data)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    nombre = val.nombre
    documento = val.documento or ""
    telefono = val.telefono or ""
    porcentaje = float(val.porcentajeGanancia or 0.0)
    activo = 1 if (val.activo if val.activo is not None else True) else 0
    inv_id = str(val.id or "").strip() or f"INV-{int(datetime.now().timestamp() * 1000)}"

    conn = get_db_connection()
    try:
        if request.method == "PUT" or val.id:
            exists = conn.execute("SELECT 1 FROM inversionistas WHERE id = ?", (inv_id,)).fetchone()
            if not exists:
                return jsonify({"error": "El inversionista no existe."}), 404
            conn.execute(
                """
                UPDATE inversionistas
                SET nombre = ?, documento = ?, telefono = ?, porcentaje_ganancia = ?, activo = ?
                WHERE id = ?
                """,
                (nombre, documento, telefono, porcentaje, activo, inv_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO inversionistas (id, nombre, documento, telefono, porcentaje_ganancia, activo, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (inv_id, nombre, documento, telefono, porcentaje, activo, now_colombia().strftime("%Y-%m-%d")),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM inversionistas WHERE id = ?", (inv_id,)).fetchone()
        return jsonify(_inversionista_json(conn, row))
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": f"No fue posible guardar el inversionista: {exc}"}), 400
    finally:
        conn.close()


@api_inversionistas_bp.route("/api/inversionista/<inv_id>", methods=["DELETE"])
def eliminar_inversionista(inv_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT 1 FROM inversionistas WHERE id = ?", (inv_id,)).fetchone()
        if not row:
            return jsonify({"error": "El inversionista no existe."}), 404
        # Borrado lógico para conservar la trazabilidad histórica de ventas y productos.
        conn.execute("UPDATE inversionistas SET activo = 0 WHERE id = ?", (inv_id,))
        conn.commit()
        return jsonify({"status": "deleted"})
    finally:
        conn.close()
