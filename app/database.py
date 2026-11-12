from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import re
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
DB_NAME = BASE_DIR / "peluqueria_pos.db"
COLOMBIA_TZ = ZoneInfo("America/Bogota")


def now_colombia():
  """Fecha y hora oficial de Colombia (America/Bogota)."""
  return datetime.now(COLOMBIA_TZ)


def get_db_connection():
  conn = sqlite3.connect(str(DB_NAME))
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  return conn


def _desglosar_inversion_historica(cursor):
  """Separa inv_share en inversión y ganancia del inversionista en registros anteriores."""
  filas = cursor.execute(
      "SELECT id, tipo_servicio, materia_prima_share, inv_share, flete_total "
      "FROM transacciones WHERE inversion_share IS NULL"
  ).fetchall()
  if not filas:
    return

  catalogo = {
      r["nombre"].strip().lower(): (r["base_price"], r["inv_gain"])
      for r in cursor.execute("SELECT nombre, base_price, inv_gain FROM productos")
  }
  patron = re.compile(r"(\d+)x\s+(.+?)(?=,\s*\d+x\s|$)", re.DOTALL)

  for f in filas:
    inversion = ganancia = None
    tipo = f["tipo_servicio"] or ""
    inv_share = f["inv_share"] or 0.0
    if not tipo.startswith("Prod:"):
      inversion = f["materia_prima_share"] or 0.0
      ganancia = round(inv_share - inversion, 2)
      if ganancia < -0.01:
        inversion, ganancia = inv_share, 0.0
    else:
      items = patron.findall(tipo[len("Prod:"):].strip())
      base_total = ganancia_total = 0.0
      completo = bool(items)
      for cantidad, nombre in items:
        datos = catalogo.get(nombre.strip().lower())
        if not datos:
          completo = False
          break
        base_total += datos[0] * int(cantidad)
        ganancia_total += datos[1] * int(cantidad)
      if completo:
        inversion = round(base_total + (f["flete_total"] or 0.0), 2)
        ganancia = round(ganancia_total, 2)
        if abs(inversion + ganancia - inv_share) > 0.01:
          inversion = ganancia = None
    if inversion is not None:
      cursor.execute(
          "UPDATE transacciones SET inversion_share = ?, ganancia_inv_share = ? WHERE id = ?",
          (round(inversion, 2), round(ganancia, 2), f["id"]),
      )


def _corregir_totales_ventas_productos(cursor):
  """Corrige el total de las ventas de productos guardadas con un valor menor al precio de venta.

  El total de una venta de productos es lo que pagó el cliente: ganancia de la administradora +
  parte del inversionista (costo base + flete + su ganancia). Una versión anterior guardaba solo la
  ganancia de la administradora. Se corrigen únicamente las ventas de productos cuyo total no
  coincide con esa suma. Antes de modificar se guarda una copia de la base de datos; si no se
  puede guardar la copia, no se modifica nada.
  """
  filas = cursor.execute(
      """
      SELECT id FROM transacciones
      WHERE tipo_servicio LIKE 'Prod:%'
        AND ABS(total - (COALESCE(admin_share, 0) + COALESCE(inv_share, 0))) > 0.01
      """
  ).fetchall()
  if not filas:
    return

  copia = DB_NAME.with_name(f"peluqueria_pos.antes_de_corregir_totales_{datetime.now():%Y%m%d_%H%M%S}.db")
  try:
    origen = sqlite3.connect(str(DB_NAME))
    destino = sqlite3.connect(str(copia))
    with destino:
      origen.backup(destino)
    origen.close()
    destino.close()
  except Exception as exc:
    print(f"[AVISO] No se corrigieron los totales de {len(filas)} venta(s) de productos: "
          f"no se pudo guardar la copia de seguridad ({exc}).")
    return

  cursor.execute(
      """
      UPDATE transacciones
      SET total = ROUND(COALESCE(admin_share, 0) + COALESCE(inv_share, 0), 2)
      WHERE tipo_servicio LIKE 'Prod:%'
        AND ABS(total - (COALESCE(admin_share, 0) + COALESCE(inv_share, 0))) > 0.01
      """
  )
  print(f"[OK] Se corrigió el total de {len(filas)} venta(s) de productos. Copia de seguridad: {copia.name}")


def _corregir_fechas_historicas(cursor):
  """Corrige el desfase de fecha producido por versiones que mezclaban toISOString()
  (UTC) con la hora local. Solo ajusta registros donde fecha_hora tiene exactamente
  un día de diferencia respecto de fecha_dia y conserva la hora/minutos registrados."""
  filas = cursor.execute(
      "SELECT id, fecha_hora, fecha_dia FROM transacciones WHERE fecha_hora IS NOT NULL AND fecha_dia IS NOT NULL"
  ).fetchall()
  corregidas = 0
  for row in filas:
    fecha_hora = str(row["fecha_hora"] or "")
    fecha_dia = str(row["fecha_dia"] or "")
    if len(fecha_hora) < 16 or len(fecha_dia) != 10:
      continue
    try:
      d_hora = datetime.strptime(fecha_hora[:10], "%Y-%m-%d").date()
      d_dia = datetime.strptime(fecha_dia, "%Y-%m-%d").date()
    except ValueError:
      continue
    if (d_hora - d_dia).days == 1:
      nueva = f"{fecha_dia}{fecha_hora[10:19] if len(fecha_hora) >= 19 else fecha_hora[10:16]}"
      cursor.execute("UPDATE transacciones SET fecha_hora=? WHERE id=?", (nueva, row["id"]))
      corregidas += 1
  if corregidas:
    print(f"[OK] Se corrigieron {corregidas} fecha(s) de venta para conservar la fecha local de Colombia.")


def _columna_existe(cursor, tabla, columna):
  return any(r["name"] == columna for r in cursor.execute(f"PRAGMA table_info({tabla})").fetchall())


def _normalizar_nombre_presentacion(nombre):
  return re.sub(r"\s+x(?:6|12)\s*$", "", (nombre or "").strip(), flags=re.IGNORECASE).strip()


def _migrar_presentaciones(cursor):
  """Migra el antiguo modelo producto=x1/x6/x12 al modelo producto + presentaciones."""
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS presentaciones (
      id TEXT PRIMARY KEY,
      nombre TEXT NOT NULL UNIQUE,
      factor INTEGER NOT NULL CHECK (factor > 0),
      activa INTEGER NOT NULL DEFAULT 1,
      orden INTEGER NOT NULL DEFAULT 0
    )
  """)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS producto_presentaciones (
      id TEXT PRIMARY KEY,
      producto_id TEXT NOT NULL,
      presentacion_id TEXT NOT NULL,
      base_price REAL NOT NULL DEFAULT 0,
      admin_gain REAL NOT NULL DEFAULT 0,
      inv_gain REAL NOT NULL DEFAULT 0,
      flete REAL NOT NULL DEFAULT 0,
      activa INTEGER NOT NULL DEFAULT 1,
      UNIQUE(producto_id, presentacion_id),
      FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE,
      FOREIGN KEY(presentacion_id) REFERENCES presentaciones(id)
    )
  """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_producto_presentaciones_producto ON producto_presentaciones(producto_id)")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_producto_presentaciones_pres ON producto_presentaciones(presentacion_id)")

  defaults = [
    ("unidad", "Unidad", 1, 1, 0),
    ("media_docena", "Media docena", 6, 1, 1),
    ("docena", "Docena", 12, 1, 2),
  ]
  cursor.executemany(
      "INSERT OR IGNORE INTO presentaciones (id, nombre, factor, activa, orden) VALUES (?, ?, ?, ?, ?)",
      defaults,
  )

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS producto_id_aliases (
      old_producto_id TEXT PRIMARY KEY,
      producto_id TEXT NOT NULL
    )
  """)

  if not _columna_existe(cursor, "productos", "presentacion"):
    return

  if cursor.execute("SELECT COUNT(*) FROM producto_presentaciones").fetchone()[0] > 0:
    return

  filas = cursor.execute("""
    SELECT id, nombre, base_price, admin_gain, inv_gain, flete,
           es_ampolleta, presentacion, COALESCE(stock, 0) AS stock
    FROM productos
  """).fetchall()
  if not filas:
    return

  grupos = {}
  for row in filas:
    pres = row["presentacion"] or "unidad"
    if pres not in {"unidad", "media_docena", "docena"}:
      pres = "unidad"
    base_nombre = _normalizar_nombre_presentacion(row["nombre"])
    key = base_nombre.casefold()
    grupos.setdefault(key, []).append((row, pres))

  for key, entries in grupos.items():
    unidad_entries = [e for e in entries if e[1] == "unidad"]
    canonical = unidad_entries[0][0] if unidad_entries else entries[0][0]
    base_nombre = _normalizar_nombre_presentacion(canonical["nombre"])
    stock_real = max(int(e[0]["stock"] or 0) for e in entries)

    cursor.execute(
      "UPDATE productos SET nombre=?, stock=?, presentacion='unidad' WHERE id=?",
      (base_nombre, stock_real, canonical["id"]),
    )

    for row, pres in entries:
      cursor.execute(
        "INSERT OR IGNORE INTO producto_id_aliases(old_producto_id, producto_id) VALUES (?, ?)",
        (row["id"], canonical["id"]),
      )
      pres_id = pres
      cursor.execute(
        """
        INSERT OR IGNORE INTO producto_presentaciones
          (id, producto_id, presentacion_id, base_price, admin_gain, inv_gain, flete, activa)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
          f"pp-{canonical['id']}-{pres_id}", canonical["id"], pres_id,
          row["base_price"], row["admin_gain"], row["inv_gain"], row["flete"],
        ),
      )

    if not unidad_entries:
      row = canonical
      cursor.execute(
        """
        INSERT OR IGNORE INTO producto_presentaciones
          (id, producto_id, presentacion_id, base_price, admin_gain, inv_gain, flete, activa)
        VALUES (?, ?, 'unidad', ?, ?, ?, ?, 1)
        """,
        (f"pp-{canonical['id']}-unidad", canonical["id"], row["base_price"], row["admin_gain"], row["inv_gain"], row["flete"]),
      )

  ids_canonicos = {r["producto_id"] for r in cursor.execute("SELECT DISTINCT producto_id FROM producto_presentaciones")}
  if ids_canonicos:
    placeholders = ",".join("?" for _ in ids_canonicos)
    cursor.execute(
      f"DELETE FROM productos WHERE id NOT IN ({placeholders})",
      tuple(ids_canonicos),
    )


def _asegurar_presentaciones_para_productos(cursor):
  """Toda presentación activa global queda disponible para todos los productos."""
  productos = cursor.execute("SELECT id, base_price, admin_gain, inv_gain, flete FROM productos").fetchall()
  presentaciones = cursor.execute("SELECT id FROM presentaciones WHERE activa=1").fetchall()
  for p in productos:
    for pres in presentaciones:
      existe = cursor.execute(
        "SELECT 1 FROM producto_presentaciones WHERE producto_id=? AND presentacion_id=?",
        (p["id"], pres["id"]),
      ).fetchone()
      if not existe:
        cursor.execute(
          """
          INSERT INTO producto_presentaciones
            (id, producto_id, presentacion_id, base_price, admin_gain, inv_gain, flete, activa)
          VALUES (?, ?, ?, ?, ?, ?, ?, 1)
          """,
          (f"pp-{p['id']}-{pres['id']}", p["id"], pres["id"], p["base_price"], p["admin_gain"], p["inv_gain"], p["flete"]),
        )


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS jornadas (
            id TEXT PRIMARY KEY,
            iniciada_en TEXT NOT NULL,
            cerrada_en TEXT,
            activa INTEGER NOT NULL DEFAULT 1
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id TEXT PRIMARY KEY,
            fecha_hora TEXT NOT NULL,
            fecha_dia TEXT NOT NULL,
            cliente TEXT NOT NULL,
            tipo_servicio TEXT NOT NULL,
            total REAL NOT NULL,
            admin_share REAL NOT NULL,
            aux_share REAL NOT NULL,
            materia_prima_share REAL NOT NULL,
            inv_share REAL NOT NULL,
            flete_total REAL DEFAULT 0,
            activa INTEGER DEFAULT 1,
            inversion_share REAL,
            ganancia_inv_share REAL,
            jornada_id TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            base_price REAL NOT NULL DEFAULT 0,
            admin_gain REAL NOT NULL DEFAULT 0,
            inv_gain REAL NOT NULL DEFAULT 0,
            flete REAL NOT NULL DEFAULT 0,
            es_ampolleta INTEGER NOT NULL DEFAULT 0,
            presentacion TEXT NOT NULL DEFAULT 'unidad',
            stock INTEGER NOT NULL DEFAULT 0
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS auxiliares (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            documento TEXT,
            telefono TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_ingreso TEXT
        )
    """)

  cursor.execute("""
      CREATE TABLE IF NOT EXISTS combos (
          id TEXT PRIMARY KEY,
          nombre TEXT NOT NULL,
          costo_base REAL NOT NULL DEFAULT 0,
          admin_gain REAL NOT NULL DEFAULT 0,
          inv_gain REAL NOT NULL DEFAULT 0,
          flete REAL NOT NULL DEFAULT 0,
          activo INTEGER NOT NULL DEFAULT 1
      )
  """)

  cursor.execute("""
      CREATE TABLE IF NOT EXISTS combo_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          combo_id TEXT NOT NULL,
          producto_id TEXT NOT NULL,
          cantidad INTEGER NOT NULL CHECK (cantidad > 0),
          costo_base REAL NOT NULL DEFAULT 0,
          admin_gain REAL NOT NULL DEFAULT 0,
          inv_gain REAL NOT NULL DEFAULT 0,
          flete REAL NOT NULL DEFAULT 0,
          FOREIGN KEY (combo_id) REFERENCES combos(id) ON DELETE CASCADE,
          FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
      )
  """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_combo_items_combo ON combo_items(combo_id)")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_combo_items_prod ON combo_items(producto_id)")  

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicio_auxiliares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaccion_id TEXT NOT NULL,
            auxiliar_id TEXT NOT NULL,
            porcentaje REAL NOT NULL,
            base_mano_obra REAL NOT NULL,
            pago REAL NOT NULL,
            FOREIGN KEY (transaccion_id) REFERENCES transacciones(id) ON DELETE CASCADE,
            FOREIGN KEY (auxiliar_id) REFERENCES auxiliares(id)
        )
    """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_servicio_aux_tx ON servicio_auxiliares(transaccion_id)")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_servicio_aux_aux ON servicio_auxiliares(auxiliar_id)")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha_dia)")

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS venta_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaccion_id TEXT NOT NULL,
            producto_id TEXT NOT NULL,
            producto_nombre TEXT NOT NULL,
            unidades INTEGER NOT NULL,
            presentacion_id TEXT,
            presentacion_nombre TEXT,
            factor_presentacion INTEGER,
            FOREIGN KEY (transaccion_id) REFERENCES transacciones(id) ON DELETE CASCADE
        )
    """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_venta_items_tx ON venta_items(transaccion_id)")

  for columna in ("activa",):
    try:
      cursor.execute(f"ALTER TABLE transacciones ADD COLUMN {columna} INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
      pass

  for columna, definicion in (("presentacion", "TEXT NOT NULL DEFAULT 'unidad'"), ("stock", "INTEGER NOT NULL DEFAULT 0")):
    try:
      cursor.execute(f"ALTER TABLE productos ADD COLUMN {columna} {definicion}")
    except sqlite3.OperationalError:
      pass

  for columna in ("inversion_share", "ganancia_inv_share"):
    try:
      cursor.execute(f"ALTER TABLE transacciones ADD COLUMN {columna} REAL")
    except sqlite3.OperationalError:
      pass

  try:
    cursor.execute("ALTER TABLE transacciones ADD COLUMN jornada_id TEXT")
  except sqlite3.OperationalError:
    pass

  cursor.execute("CREATE INDEX IF NOT EXISTS idx_transacciones_jornada ON transacciones(jornada_id, activa)")

  for columna, definicion in (
      ("presentacion_id", "TEXT"),
      ("presentacion_nombre", "TEXT"),
      ("factor_presentacion", "INTEGER"),
  ):
    try:
      cursor.execute(f"ALTER TABLE venta_items ADD COLUMN {columna} {definicion}")
    except sqlite3.OperationalError:
      pass

  # --- NUEVAS COLUMNAS PARA COMBOS ---
  try:
    cursor.execute("ALTER TABLE combos ADD COLUMN flete REAL NOT NULL DEFAULT 0")
  except sqlite3.OperationalError:
    pass

  for col in ("costo_base", "admin_gain", "inv_gain", "flete"):
    try:
      cursor.execute(f"ALTER TABLE combo_items ADD COLUMN {col} REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
      pass
  # ----------------------------------

  if cursor.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
    productos_iniciales = [
        ("p1", "Tratamiento Alisador", 40000, 15000, 10000, 3000, 0),
        ("p2", "Shampoo Antiresiduos", 25000, 8000, 5000, 2000, 0),
        ("p3", "Shampoo Hidratante", 22000, 7000, 4000, 2000, 0),
        ("p4", "Tratamiento Acondicionador", 24000, 8000, 5000, 2000, 0),
        ("p5", "Termo Protector", 30000, 10000, 6000, 2500, 0),
        ("p6", "Óleo", 18000, 6000, 4000, 1500, 0),
        ("p7", "Oil Total Repair", 35000, 12000, 8000, 2500, 0),
        ("p8", "Ampolletas Amarillas", 8000, 3000, 2000, 1000, 1),
        ("p9", "Ampolletas Rojas", 8000, 3000, 2000, 1000, 1),
        ("p10", "Shampoo Anticaída", 28000, 9000, 6000, 2000, 0),
        ("p11", "Acondicionador Anticaída", 28000, 9000, 6000, 2000, 0),
    ]
    cursor.executemany(
        "INSERT INTO productos (id, nombre, base_price, admin_gain, inv_gain, flete, es_ampolleta, presentacion, stock) VALUES (?, ?, ?, ?, ?, ?, ?, 'unidad', 0)",
        productos_iniciales,
    )

  jornada = cursor.execute("SELECT id FROM jornadas WHERE activa = 1 ORDER BY rowid DESC LIMIT 1").fetchone()
  if not jornada:
    jornada_id = "JOR-" + str(__import__("time").time_ns())
    ahora = now_colombia().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO jornadas(id, iniciada_en, activa) VALUES(?,?,1)", (jornada_id, ahora))
    jornada = {"id": jornada_id}
  jornada_id = jornada["id"]

  hoy = now_colombia().strftime("%Y-%m-%d")
  cursor.execute("UPDATE transacciones SET jornada_id=? WHERE jornada_id IS NULL AND activa=1 AND fecha_dia=?", (jornada_id, hoy))
  cursor.execute("UPDATE transacciones SET activa=0 WHERE jornada_id IS NULL AND fecha_dia<>?", (hoy,))

  _corregir_fechas_historicas(cursor)
  _desglosar_inversion_historica(cursor)
  _corregir_totales_ventas_productos(cursor)
  _migrar_presentaciones(cursor)
  _asegurar_presentaciones_para_productos(cursor)

  try:
    cursor.execute("UPDATE venta_items SET producto_id = (SELECT producto_id FROM producto_id_aliases a WHERE a.old_producto_id = venta_items.producto_id) WHERE producto_id IN (SELECT old_producto_id FROM producto_id_aliases)")
  except sqlite3.OperationalError:
    pass

  conn.commit()
  conn.close()