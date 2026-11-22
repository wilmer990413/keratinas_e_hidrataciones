import os
import time
import logging
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from app.database import DB_NAME, now_colombia

logger = logging.getLogger("peluqueria_pos.backup")

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / os.getenv("BACKUP_DIR", "backups")
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "30"))
BACKUP_INTERVAL_HOURS = float(os.getenv("BACKUP_INTERVAL_HOURS", "12"))

_scheduler_thread = None
_scheduler_lock = threading.Lock()


def asegurar_directorio_backups():
    """Garantiza que la carpeta de copias de seguridad exista."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def limpiar_backups_antiguos(max_copias=None):
    """Mantiene solo las últimas N copias de seguridad para no saturar el almacenamiento."""
    if max_copias is None:
        max_copias = MAX_BACKUPS

    if not BACKUP_DIR.exists():
        return

    archivos = sorted(
        BACKUP_DIR.glob("peluqueria_pos_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if len(archivos) > max_copias:
        for viejo in archivos[max_copias:]:
            try:
                viejo.unlink(missing_ok=True)
                logger.info(f"Copia de seguridad antigua eliminada por rotación: {viejo.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar backup antiguo {viejo.name}: {e}")


def crear_backup(motivo="auto"):
    """
    Crea una copia de seguridad en caliente (online backup) de la base de datos SQLite.
    Es completamente seguro incluso si hay operaciones de lectura o escritura activas.
    """
    if not DB_NAME.exists():
        logger.warning(f"No se pudo crear backup: no existe la base de datos en {DB_NAME}")
        return None

    asegurar_directorio_backups()
    
    # Sanitizar motivo para nombre de archivo
    motivo_limpio = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in motivo)
    timestamp = now_colombia().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"peluqueria_pos_{timestamp}_{motivo_limpio}.db"
    destino_path = BACKUP_DIR / nombre_archivo

    try:
        origen = sqlite3.connect(str(DB_NAME), timeout=15.0)
        destino = sqlite3.connect(str(destino_path))
        with destino:
            origen.backup(destino, pages=250, sleep=0.01)
        origen.close()
        destino.close()

        tamano_kb = round(destino_path.stat().st_size / 1024, 2)
        print(f"[BACKUP] Copia de seguridad creada exitosamente: {nombre_archivo} ({tamano_kb} KB)")
        
        # Rotar copias antiguas
        limpiar_backups_antiguos()
        return destino_path

    except Exception as exc:
        print(f"[ERROR BACKUP] Error al crear la copia de seguridad ({motivo}): {exc}")
        return None


def listar_backups():
    """Retorna una lista de metadatos de las copias de seguridad disponibles."""
    if not BACKUP_DIR.exists():
        return []

    archivos = sorted(
        BACKUP_DIR.glob("peluqueria_pos_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    resultado = []
    for arch in archivos:
        stat = arch.stat()
        resultado.append({
            "nombre": arch.name,
            "tamano_kb": round(stat.st_size / 1024, 2),
            "tamano_mb": round(stat.st_size / (1024 * 1024), 2),
            "fecha_creacion": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "ruta": str(arch)
        })
    return resultado


def _bucle_backup_programado(intervalo_segundos):
    """Hilo daemon que genera copias automáticas periódicas."""
    while True:
        try:
            time.sleep(intervalo_segundos)
            crear_backup(motivo="programado")
        except Exception as e:
            logger.error(f"Error en el programador de backups: {e}")


def iniciar_backup_programado(intervalo_horas=None):
    """Inicia el temporizador de copias de seguridad en segundo plano."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return

        if intervalo_horas is None:
            intervalo_horas = BACKUP_INTERVAL_HOURS

        intervalo_segundos = max(300, int(intervalo_horas * 3600))
        _scheduler_thread = threading.Thread(
            target=_bucle_backup_programado,
            args=(intervalo_segundos,),
            daemon=True,
            name="BackupSchedulerThread"
        )
        _scheduler_thread.start()
        print(f"[BACKUP] Programador de copias automáticas activo (cada {intervalo_horas} horas).")


if __name__ == "__main__":
    import sys
    motivo = sys.argv[1] if len(sys.argv) > 1 else "manual_cli"
    archivo = crear_backup(motivo=motivo)
    if archivo:
        print(f"Copia completada: {archivo}")
    else:
        sys.exit(1)
