from datetime import datetime
from flask import Blueprint, jsonify, request
from app.database import get_db_connection, now_colombia

api_auxiliares_bp = Blueprint("api_auxiliares", __name__)


def _row_to_json(row):
  return {
      "id": row["id"],
      "nombre": row["nombre"],
      "documento": row["documento"] or "",
      "telefono": row["telefono"] or "",
      "activo": bool(row["activo"]),
      "fechaIngreso": row["fecha_ingreso"] or "",
  }


@api_auxiliares_bp.route("/api/auxiliares", methods=["GET"])
def listar_auxiliares():
  solo_activos = request.args.get("activos", "0") == "1"
  conn = get_db_connection()
  query = "SELECT * FROM auxiliares"
  if solo_activos:
    query += " WHERE activo = 1"
  query += " ORDER BY activo DESC, nombre COLLATE NOCASE"
  rows = conn.execute(query).fetchall()
  conn.close()
  return jsonify([_row_to_json(r) for r in rows])


@api_auxiliares_bp.route("/api/auxiliar", methods=["POST", "PUT"])
def guardar_auxiliar():
  data = request.get_json() or {}
  nombre = str(data.get("nombre", "")).strip()
  documento = str(data.get("documento", "")).strip()
  telefono = str(data.get("telefono", "")).strip()
  activo = 1 if data.get("activo", True) else 0
  auxiliar_id = str(data.get("id", "")).strip() or f"AUX-{int(datetime.now().timestamp() * 1000)}"

  if not nombre:
    return jsonify({"error": "El nombre del auxiliar es obligatorio."}), 400

  conn = get_db_connection()
  try:
    if request.method == "PUT":
      exists = conn.execute("SELECT 1 FROM auxiliares WHERE id = ?", (auxiliar_id,)).fetchone()
      if not exists:
        return jsonify({"error": "El auxiliar no existe."}), 404
      conn.execute(
          "UPDATE auxiliares SET nombre = ?, documento = ?, telefono = ?, activo = ? WHERE id = ?",
          (nombre, documento, telefono, activo, auxiliar_id),
      )
    else:
      conn.execute(
          "INSERT INTO auxiliares (id, nombre, documento, telefono, activo, fecha_ingreso) VALUES (?, ?, ?, ?, ?, ?)",
          (auxiliar_id, nombre, documento, telefono, activo, now_colombia().strftime("%Y-%m-%d")),
      )
    conn.commit()
    row = conn.execute("SELECT * FROM auxiliares WHERE id = ?", (auxiliar_id,)).fetchone()
    return jsonify(_row_to_json(row))
  except Exception as exc:
    conn.rollback()
    return jsonify({"error": f"No fue posible guardar el auxiliar: {exc}"}), 400
  finally:
    conn.close()


@api_auxiliares_bp.route("/api/auxiliar/<auxiliar_id>", methods=["DELETE"])
def eliminar_auxiliar(auxiliar_id):
  conn = get_db_connection()
  try:
    row = conn.execute("SELECT 1 FROM auxiliares WHERE id = ?", (auxiliar_id,)).fetchone()
    if not row:
      return jsonify({"error": "El auxiliar no existe."}), 404
    # Borrado lógico para conservar la trazabilidad de la nómina histórica.
    conn.execute("UPDATE auxiliares SET activo = 0 WHERE id = ?", (auxiliar_id,))
    conn.commit()
    return jsonify({"status": "deleted"})
  finally:
    conn.close()
