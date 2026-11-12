from app import create_app

app = create_app()

if __name__ == "__main__":
  print("=" * 60)
  print("🚀 Servidor modular de Peluquería POS activo.")
  print("🌐 Abre tu navegador en: http://127.0.0.1:5000")
  print("=" * 60)
  app.run(debug=True, port=5000)