"""Agenda de citas: calendario mensual con estados definidos (y coloreados) por el usuario."""
import re
import time
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.database import get_db_connection

api_citas_bp = Blueprint("api_citas", __name__)

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ADMIN_ID = "ADMIN"
ADMIN_NOMBRE = "Administradora"


def _fecha(valor, campo="La fecha"):
  try:
    return datetime.strptime(str(valor or "").strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
  except ValueError:
    raise ValueError(f"{campo} no es válida.")


def _hora(valor):
  """Hora opcional en formato 24 h HH:MM. Vacío = cita sin hora (por ejemplo, un día de descanso)."""
  texto = str(valor or "").strip()
  if not texto:
    return None
  try:
    return datetime.strptime(texto, "%H:%M").strftime("%H:%M")
  except ValueError:
    raise ValueError("La hora no es válida.")


def _texto(valor, campo, maximo, obligatorio=False):
  texto = str(valor or "").strip()
  if obligatorio and not texto:
    raise ValueError(f"{campo} es obligatorio.")
  if len(texto) > maximo:
    raise ValueError(f"{campo} no puede superar {maximo} caracteres.")
  return texto


def _estado_existe(conn, estado_id):
  if estado_id in (None, ""):
    return None
  fila = conn.execute("SELECT id FROM citas_estados WHERE id = ?", (str(estado_id),)).fetchone()
  if not fila:
    raise ValueError("El estado seleccionado ya no existe.")
  return fila["id"]


def _responsables_de(conn, ids_citas):
  """{cita_id: [{id, nombre}, ...]} con la administradora primero y luego las auxiliares por nombre."""
  if not ids_citas:
    return {}
  resultado = {i: [] for i in ids_citas}
  for i in range(0, len(ids_citas), 500):
    lote = ids_citas[i:i + 500]
    filas = conn.execute(
        f"""
        SELECT cr.cita_id, cr.responsable_id, a.nombre, a.activo
        FROM cita_responsables cr LEFT JOIN auxiliares a ON a.id = cr.responsable_id
        WHERE cr.cita_id IN ({",".join("?" for _ in lote)})
        ORDER BY (cr.responsable_id = ?) DESC, a.nombre COLLATE NOCASE
        """, lote + [ADMIN_ID]).fetchall()
    for f in filas:
      if f["responsable_id"] == ADMIN_ID:
        resultado[f["cita_id"]].append({"id": ADMIN_ID, "nombre": ADMIN_NOMBRE, "activo": True})
      elif f["nombre"] is not None:
        resultado[f["cita_id"]].append({"id": f["responsable_id"], "nombre": f["nombre"], "activo": bool(f["activo"])})
  return resultado


def _personas(conn):
  """Personas que se pueden asignar a una cita: la administradora y las auxiliares activas."""
  personas = [{"id": ADMIN_ID, "nombre": ADMIN_NOMBRE, "tipo": "administradora"}]
  for r in conn.execute("SELECT id, nombre FROM auxiliares WHERE activo = 1 ORDER BY nombre COLLATE NOCASE").fetchall():
    personas.append({"id": r["id"], "nombre": r["nombre"], "tipo": "auxiliar"})
  return personas


def _cita_a_dict(r, responsables):
  return {
      "id": r["id"], "fecha": r["fecha"], "hora": r["hora"], "cliente": r["cliente"],
      "servicio": r["servicio"] or "", "estadoId": r["estado_id"], "notas": r["notas"] or "",
      "responsables": responsables,
  }


def _validar_responsables(conn, valor, cita_id=None):
  """Lista de ids (sin repetir). Una auxiliar inactiva solo se acepta si ya estaba asignada a esta cita."""
  if valor in (None, ""):
    return []
  if not isinstance(valor, list) or len(valor) > 30 or any(not isinstance(x, str) for x in valor):
    raise ValueError("La lista de personas asignadas no es válida.")
  ids = list(dict.fromkeys(x.strip() for x in valor if x.strip()))
  if not ids:
    return []
  ya = set()
  if cita_id:
    ya = {r["responsable_id"] for r in conn.execute(
        "SELECT responsable_id FROM cita_responsables WHERE cita_id = ?", (cita_id,)).fetchall()}
  for rid in ids:
    if rid == ADMIN_ID:
      continue
    fila = conn.execute("SELECT activo FROM auxiliares WHERE id = ?", (rid,)).fetchone()
    if not fila or (not fila["activo"] and rid not in ya):
      raise ValueError("Una de las personas asignadas ya no está disponible.")
  return ids


def _guardar_responsables(conn, cita_id, ids):
  conn.execute("DELETE FROM cita_responsables WHERE cita_id = ?", (cita_id,))
  conn.executemany("INSERT INTO cita_responsables (cita_id, responsable_id) VALUES (?, ?)", [(cita_id, i) for i in ids])


def _estados(conn):
  return [
      {"id": r["id"], "nombre": r["nombre"], "color": r["color"], "citas": r["citas"]}
      for r in conn.execute(
          """
          SELECT e.id, e.nombre, e.color, e.orden, COUNT(c.id) AS citas
          FROM citas_estados e LEFT JOIN citas c ON c.estado_id = e.id
          GROUP BY e.id ORDER BY e.orden, e.nombre COLLATE NOCASE
          """).fetchall()
  ]


@api_citas_bp.route("/api/agenda", methods=["GET"])
def api_agenda():
  """Citas de un rango de fechas (inicio y fin incluidos) y la lista de estados."""
  conn = get_db_connection()
  try:
    inicio = _fecha(request.args.get("inicio"), "La fecha de inicio")
    fin = _fecha(request.args.get("fin"), "La fecha final")
    filas = conn.execute(
        "SELECT * FROM citas WHERE fecha BETWEEN ? AND ? ORDER BY fecha, COALESCE(hora, ''), rowid",
        (inicio, fin)).fetchall()
    resp = _responsables_de(conn, [r["id"] for r in filas])
    return jsonify({"citas": [_cita_a_dict(r, resp.get(r["id"], [])) for r in filas],
                    "estados": _estados(conn), "personas": _personas(conn)})
  except ValueError as exc:
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


def _leer_cita(conn, data, cita_id=None):
  if not isinstance(data, dict):
    raise ValueError("Datos de la cita no válidos.")
  return (
      _fecha(data.get("fecha")),
      _hora(data.get("hora")),
      _texto(data.get("cliente"), "El cliente o título", 120, obligatorio=True),
      _texto(data.get("servicio"), "El servicio", 80),
      _estado_existe(conn, data.get("estadoId")),
      _texto(data.get("notas"), "Las notas", 500),
      _validar_responsables(conn, data.get("responsables"), cita_id),
  )


@api_citas_bp.route("/api/agenda/citas", methods=["POST"])
def api_crear_cita():
  conn = get_db_connection()
  try:
    fecha, hora, cliente, servicio, estado_id, notas, responsables = _leer_cita(conn, request.get_json(silent=True))
    cita_id = f"CIT-{time.time_ns()}"
    conn.execute(
        "INSERT INTO citas (id, fecha, hora, cliente, servicio, estado_id, notas, creada_en) VALUES (?,?,?,?,?,?,?,?)",
        (cita_id, fecha, hora, cliente, servicio, estado_id, notas, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    _guardar_responsables(conn, cita_id, responsables)
    conn.commit()
    return jsonify({"status": "created", "id": cita_id}), 201
  except ValueError as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_citas_bp.route("/api/agenda/citas/<cita_id>", methods=["PUT"])
def api_editar_cita(cita_id):
  conn = get_db_connection()
  try:
    if not conn.execute("SELECT 1 FROM citas WHERE id = ?", (cita_id,)).fetchone():
      return jsonify({"error": "La cita ya no existe."}), 404
    fecha, hora, cliente, servicio, estado_id, notas, responsables = _leer_cita(conn, request.get_json(silent=True), cita_id)
    conn.execute(
        "UPDATE citas SET fecha=?, hora=?, cliente=?, servicio=?, estado_id=?, notas=? WHERE id=?",
        (fecha, hora, cliente, servicio, estado_id, notas, cita_id))
    _guardar_responsables(conn, cita_id, responsables)
    conn.commit()
    return jsonify({"status": "updated"})
  except ValueError as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_citas_bp.route("/api/agenda/citas/<cita_id>", methods=["DELETE"])
def api_eliminar_cita(cita_id):
  conn = get_db_connection()
  try:
    cur = conn.execute("DELETE FROM citas WHERE id = ?", (cita_id,))
    conn.commit()
    if cur.rowcount == 0:
      return jsonify({"error": "La cita ya no existe."}), 404
    return jsonify({"status": "deleted"})
  finally:
    conn.close()


# ----------------------------------------------------------------------------- estados
def _leer_estado(data):
  if not isinstance(data, dict):
    raise ValueError("Datos del estado no válidos.")
  nombre = _texto(data.get("nombre"), "El nombre del estado", 40, obligatorio=True)
  color = str(data.get("color") or "").strip()
  if not _COLOR_RE.match(color):
    raise ValueError("Elija un color válido.")
  return nombre, color.upper()


@api_citas_bp.route("/api/agenda/estados", methods=["GET"])
def api_listar_estados():
  conn = get_db_connection()
  try:
    return jsonify(_estados(conn))
  finally:
    conn.close()


@api_citas_bp.route("/api/agenda/estados", methods=["POST"])
def api_crear_estado():
  conn = get_db_connection()
  try:
    nombre, color = _leer_estado(request.get_json(silent=True))
    if conn.execute("SELECT 1 FROM citas_estados WHERE nombre = ? COLLATE NOCASE", (nombre,)).fetchone():
      raise ValueError("Ya existe un estado con ese nombre.")
    orden = conn.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM citas_estados").fetchone()[0]
    estado_id = f"EST-{time.time_ns()}"
    conn.execute("INSERT INTO citas_estados (id, nombre, color, orden) VALUES (?,?,?,?)",
                 (estado_id, nombre, color, orden))
    conn.commit()
    return jsonify({"status": "created", "id": estado_id}), 201
  except ValueError as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_citas_bp.route("/api/agenda/estados/<estado_id>", methods=["PUT"])
def api_editar_estado(estado_id):
  conn = get_db_connection()
  try:
    if not conn.execute("SELECT 1 FROM citas_estados WHERE id = ?", (estado_id,)).fetchone():
      return jsonify({"error": "El estado ya no existe."}), 404
    nombre, color = _leer_estado(request.get_json(silent=True))
    if conn.execute("SELECT 1 FROM citas_estados WHERE nombre = ? COLLATE NOCASE AND id <> ?", (nombre, estado_id)).fetchone():
      raise ValueError("Ya existe un estado con ese nombre.")
    conn.execute("UPDATE citas_estados SET nombre = ?, color = ? WHERE id = ?", (nombre, color, estado_id))
    conn.commit()
    return jsonify({"status": "updated"})
  except ValueError as exc:
    conn.rollback()
    return jsonify({"error": str(exc)}), 400
  finally:
    conn.close()


@api_citas_bp.route("/api/agenda/estados/<estado_id>", methods=["DELETE"])
def api_eliminar_estado(estado_id):
  conn = get_db_connection()
  try:
    fila = conn.execute(
        "SELECT (SELECT COUNT(*) FROM citas WHERE estado_id = ?) AS en_uso FROM citas_estados WHERE id = ?",
        (estado_id, estado_id)).fetchone()
    if not fila:
      return jsonify({"error": "El estado ya no existe."}), 404
    if fila["en_uso"]:
      return jsonify({"error": f"No se puede eliminar: {fila['en_uso']} cita(s) usan este estado. "
                               "Cámbieles el estado primero."}), 409
    conn.execute("DELETE FROM citas_estados WHERE id = ?", (estado_id,))
    conn.commit()
    return jsonify({"status": "deleted"})
  finally:
    conn.close()
