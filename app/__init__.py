import os
from flask import Flask
from app.database import init_db
from app.backup import crear_backup, iniciar_backup_programado


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "erika-pos-default-secret-key-2026")

    # 1. Inicializar base de datos y esquema
    init_db()

    # 2. Generar copia de seguridad preventiva al arranque e iniciar backups programados
    try:
        crear_backup(motivo="inicio_servidor")
        iniciar_backup_programado()
    except Exception as exc:
        print(f"[AVISO] No se pudo inicializar el servicio de copias de seguridad: {exc}")

    # 3. Registrar Blueprints
    from app.routes.main_routes import main_bp
    from app.routes.api_productos import api_productos_bp
    from app.routes.api_ventas import api_ventas_bp
    from app.routes.api_auxiliares import api_auxiliares_bp
    from app.routes.api_nomina import api_nomina_bp
    from app.routes.api_combos import api_combos_bp
    from app.routes.api_inversionistas import api_inversionistas_bp
    from app.routes.api_citas import api_citas_bp
    from app.routes.api_caja import api_caja_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_productos_bp)
    app.register_blueprint(api_ventas_bp)
    app.register_blueprint(api_auxiliares_bp)
    app.register_blueprint(api_nomina_bp)
    app.register_blueprint(api_combos_bp)
    app.register_blueprint(api_inversionistas_bp)
    app.register_blueprint(api_citas_bp)
    app.register_blueprint(api_caja_bp)

    return app
