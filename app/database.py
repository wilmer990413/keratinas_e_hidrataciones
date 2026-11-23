from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import re
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
DB_NAME = BASE_DIR / os.getenv("DATABASE_PATH", "peluqueria_pos.db")
COLOMBIA_TZ = ZoneInfo("America/Bogota")


def now_colombia():
  """Fecha y hora oficial de Colombia (America/Bogota)."""
  return datetime.now(COLOMBIA_TZ)


def get_db_connection():
  """Establece conexión a SQLite con modo WAL y timeout para prevenir bloqueos por concurrencia."""
  conn = sqlite3.connect(str(DB_NAME), timeout=20.0)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  conn.execute("PRAGMA journal_mode = WAL")
  conn.execute("PRAGMA busy_timeout = 5000")
  conn.execute("PRAGMA synchronous = NORMAL")
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


def _crear_tablas_agenda(cursor):
  """Agenda de citas. Los estados iniciales solo se crean la primera vez (el usuario puede
  cambiarlos o borrarlos; no se vuelven a crear)."""
  primera_vez = cursor.execute(
      "SELECT 1 FROM sqlite_master WHERE type='table' AND name='citas_estados'").fetchone() is None
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS citas_estados (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            color TEXT NOT NULL,
            orden INTEGER NOT NULL DEFAULT 0
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS citas (
            id TEXT PRIMARY KEY,
            fecha TEXT NOT NULL,
            hora TEXT,
            cliente TEXT NOT NULL,
            servicio TEXT,
            estado_id TEXT REFERENCES citas_estados(id) ON DELETE RESTRICT,
            notas TEXT,
            creada_en TEXT
        )
    """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas(fecha)")
  # Personas asignadas a una cita: 'ADMIN' (la administradora) o el id de una auxiliar.
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS cita_responsables (
            cita_id TEXT NOT NULL REFERENCES citas(id) ON DELETE CASCADE,
            responsable_id TEXT NOT NULL,
            PRIMARY KEY (cita_id, responsable_id)
        )
    """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_cita_resp_persona ON cita_responsables(responsable_id)")
  if primera_vez:
    cursor.executemany(
        "INSERT INTO citas_estados (id, nombre, color, orden) VALUES (?,?,?,?)",
        [("EST-PENDIENTE", "Pendiente", "#FFFF00", 1),
         ("EST-CONFIRMADA", "Confirmada", "#92D050", 2),
         ("EST-CANCELADA", "Cancelada", "#FFA6A6", 3)])


def _crear_tablas_caja(cursor):
  """Crea tablas para control de egresos, bolsillos de dinero y cierres de caja diarios."""
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS caja_egresos (
      id TEXT PRIMARY KEY,
      jornada_id TEXT,
      fecha TEXT NOT NULL,
      fecha_dia TEXT NOT NULL,
      bolsillo TEXT NOT NULL,
      categoria TEXT NOT NULL,
      descripcion TEXT NOT NULL,
      monto REAL NOT NULL DEFAULT 0,
      inversionista_id TEXT,
      inversionista_nombre TEXT,
      creado_en TEXT NOT NULL,
      activo INTEGER NOT NULL DEFAULT 1,
      FOREIGN KEY(inversionista_id) REFERENCES inversionistas(id)
    )
  """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_caja_egresos_dia ON caja_egresos(fecha_dia)")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_caja_egresos_bolsillo ON caja_egresos(bolsillo)")

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS caja_cierres (
      id TEXT PRIMARY KEY,
      jornada_id TEXT,
      fecha_dia TEXT NOT NULL UNIQUE,
      fecha_cierre TEXT NOT NULL,
      total_ingresos REAL NOT NULL DEFAULT 0,
      total_egresos REAL NOT NULL DEFAULT 0,
      saldo_teorico REAL NOT NULL DEFAULT 0,
      saldo_real_banco REAL NOT NULL DEFAULT 0,
      diferencia REAL NOT NULL DEFAULT 0,
      total_flete_cobrado REAL NOT NULL DEFAULT 0,
      egresos_flete REAL NOT NULL DEFAULT 0,
      saldo_flete REAL NOT NULL DEFAULT 0,
      total_reinversion_cobrado REAL NOT NULL DEFAULT 0,
      egresos_reinversion REAL NOT NULL DEFAULT 0,
      saldo_reinversion REAL NOT NULL DEFAULT 0,
      ganancia_admin REAL NOT NULL DEFAULT 0,
      ganancias_inversionistas_json TEXT,
      observaciones TEXT,
      cerrado_por TEXT DEFAULT 'Administrador'
    )
  """)
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_caja_cierres_dia ON caja_cierres(fecha_dia)")


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
      CREATE TABLE IF NOT EXISTS inversionistas (
          id TEXT PRIMARY KEY,
          nombre TEXT NOT NULL,
          documento TEXT,
          telefono TEXT,
          porcentaje_ganancia REAL NOT NULL DEFAULT 0,
          activo INTEGER NOT NULL DEFAULT 1,
          fecha_registro TEXT
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
          presentacion_id TEXT,
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
            inversionista_id TEXT,
            inversionista_nombre TEXT,
            costo_inversion REAL DEFAULT 0,
            ganancia_inversionista REAL DEFAULT 0,
            precio_unitario REAL DEFAULT 0,
            ganancia_admin REAL DEFAULT 0,
            flete REAL DEFAULT 0,
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
  try:
    cursor.execute("ALTER TABLE combo_items ADD COLUMN presentacion_id TEXT")
  except sqlite3.OperationalError:
    pass
  # Las filas antiguas de combos se asocian a la primera presentación activa del producto.
  try:
    cursor.execute("""
      UPDATE combo_items
      SET presentacion_id = (
        SELECT pp.presentacion_id
        FROM producto_presentaciones pp
        JOIN presentaciones pr ON pr.id = pp.presentacion_id
        WHERE pp.producto_id = combo_items.producto_id
          AND pp.activa = 1 AND pr.activa = 1
        ORDER BY pr.orden, pr.factor, pr.nombre COLLATE NOCASE
        LIMIT 1
      )
      WHERE presentacion_id IS NULL
    """)
  except sqlite3.OperationalError:
    pass
  # ----------------------------------

  # --- COLUMNAS PARA INVERSIONISTAS ---
  try:
    cursor.execute("ALTER TABLE productos ADD COLUMN inversionista_id TEXT")
  except sqlite3.OperationalError:
    pass

  try:
    cursor.execute("ALTER TABLE transacciones ADD COLUMN inversionista_id TEXT")
  except sqlite3.OperationalError:
    pass

  for columna, definicion in (
      ("inversionista_id", "TEXT"),
      ("inversionista_nombre", "TEXT"),
      ("costo_inversion", "REAL DEFAULT 0"),
      ("ganancia_inversionista", "REAL DEFAULT 0"),
      ("precio_unitario", "REAL DEFAULT 0"),
      ("ganancia_admin", "REAL DEFAULT 0"),
      ("flete", "REAL DEFAULT 0"),
  ):
    try:
      cursor.execute(f"ALTER TABLE venta_items ADD COLUMN {columna} {definicion}")
    except sqlite3.OperationalError:
      pass
  # -----------------------------------

  # Completa precios por línea para ventas históricas que fueron creadas antes
  # de guardar el desglose de precio de cada producto. Se reparte el componente
  # administradora + flete proporcionalmente a las unidades, conservando el total
  # de la transacción.
  ventas_antiguas = cursor.execute("""
      SELECT t.id, COALESCE(t.admin_share, 0) AS admin_share, COALESCE(t.flete_total, 0) AS flete_total
      FROM transacciones t
      WHERE t.tipo_servicio LIKE 'Prod:%'
        AND EXISTS (SELECT 1 FROM venta_items vi WHERE vi.transaccion_id = t.id)
  """).fetchall()
  for venta in ventas_antiguas:
    items = cursor.execute("""
        SELECT id, unidades, COALESCE(costo_inversion,0) AS costo_inversion,
               COALESCE(ganancia_inversionista,0) AS ganancia_inversionista
        FROM venta_items WHERE transaccion_id=? ORDER BY id
    """, (venta["id"],)).fetchall()
    pendientes = [x for x in items if float(x["precio_unitario"] if "precio_unitario" in x.keys() else 0) <= 0]
    if not pendientes:
      continue
    total_unidades = sum(max(int(x["unidades"] or 0), 0) for x in items)
    if total_unidades <= 0:
      continue
    reparto = float(venta["admin_share"] or 0) + float(venta["flete_total"] or 0)
    for item in pendientes:
      unidades = max(int(item["unidades"] or 0), 1)
      admin_linea = reparto * unidades / total_unidades
      base = float(item["costo_inversion"] or 0)
      gan_inv = float(item["ganancia_inversionista"] or 0)
      total_linea = base + gan_inv + admin_linea
      precio_unitario = total_linea / unidades
      cursor.execute(
          "UPDATE venta_items SET precio_unitario=?, ganancia_admin=?, flete=? WHERE id=?",
          (round(precio_unitario, 4), round(admin_linea, 2), 0, item["id"]),
      )

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
  _crear_tablas_agenda(cursor)
  _crear_tablas_caja(cursor)

  try:
    cursor.execute("UPDATE venta_items SET producto_id = (SELECT producto_id FROM producto_id_aliases a WHERE a.old_producto_id = venta_items.producto_id) WHERE producto_id IN (SELECT old_producto_id FROM producto_id_aliases)")
  except sqlite3.OperationalError:
    pass

  conn.commit()
  conn.close()