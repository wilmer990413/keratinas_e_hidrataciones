from flask import Flask
from app.database import init_db


def create_app():
  app = Flask(__name__)
  init_db()

  from app.routes.main_routes import main_bp
  from app.routes.api_productos import api_productos_bp
  from app.routes.api_ventas import api_ventas_bp
  from app.routes.api_auxiliares import api_auxiliares_bp
  from app.routes.api_nomina import api_nomina_bp
  from app.routes.api_combos import api_combos_bp

  app.register_blueprint(main_bp)
  app.register_blueprint(api_productos_bp)
  app.register_blueprint(api_ventas_bp)
  app.register_blueprint(api_auxiliares_bp)
  app.register_blueprint(api_nomina_bp)
  app.register_blueprint(api_combos_bp)

  return app