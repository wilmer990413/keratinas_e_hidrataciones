import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env antes de inicializar la app
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "True").strip().lower() in ("true", "1", "t", "yes")
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")

    print("=" * 60)
    print("🚀 Servidor modular de Peluquería POS activo.")
    print(f"🌐 Servidor escuchando en: http://{host}:{port}")
    print(f"⚙️  Modo Debug: {'Activado' if debug else 'Desactivado'}")
    print("=" * 60)
    app.run(host=host, port=port, debug=debug)
