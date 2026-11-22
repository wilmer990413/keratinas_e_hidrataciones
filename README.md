# 💇‍♀️ Sistema POS & Gestión Administrativa - Keratinas & Hidrataciones by Erika

Sistema integral de **Punto de Venta (POS), Control de Inventario, Gestión de Personal y Liquidación Contable** diseñado a medida para salones de belleza y centros de estética capilar.

El sistema permite facturar servicios y productos, controlar el inventario en unidades individuales a través de múltiples presentaciones y combos, liquidar participaciones de colaboradoras con deducciones y generar desprendibles de pago y reportes en Excel.

---

## 📑 Tabla de Contenidos

1. [Características Principales](#-características-principales)
2. [Documentación Especializada](#-documentación-especializada)
3. [Tecnologías Utilizadas](#-tecnologías-utilizadas)
4. [Estructura del Proyecto](#-estructura-del-proyecto)
5. [Guía de Instalación y Ejecución Local](#-guía-de-instalación-y-ejecución-local)
6. [Configuración y Variables de Entorno](#-configuración-y-variables-de-entorno)
7. [Módulos del Sistema](#-módulos-del-sistema)
8. [Copias de Seguridad y Resiliencia](#-copias-de-seguridad-y-resiliencia)

---

## 🌟 Características Principales

* **Facturación de Servicios con Cálculo Automático de Mano de Obra**: Repartición matemática exacta entre administradora y auxiliares según porcentajes de participación.
* **Inventario con Stock Unificado**: Cada producto tiene un inventario único expresado en unidades individuales que se descuenta según el factor de cada presentación (Unidad, Media Docena, Docena, Cajas).
* **Gestión de Paquetes y Combos**: Creación de combos de productos con validación de disponibilidad en tiempo real y deducción atómica de existencias.
* **Liquidación de Nómina Completa**: Cálculo sobre el histórico de fechas con descuentos (fijos o porcentuales), exportación a Excel en 5 hojas y generación de **Desprendibles de Pago Imprimibles**.
* **Jornadas de Caja Persistentes**: Los turnos no se reinician con el reloj a medianoche; solo se cierran cuando la administradora lo decide.
* **100% Autónomo y Offline**: Todos los recursos (Tailwind CSS, FontAwesome 6, Chart.js) están empaquetados localmente, permitiendo operar sin conexión a internet.
* **Alta Concurrencia y Estabilidad**: SQLite configurado con modo **WAL (*Write-Ahead Logging*)** y tiempos de espera para evitar bloqueos (`database is locked`).
* **Copias de Seguridad Automáticas en Caliente**: Respaldos periódicos en segundo plano y disparadores al cerrar jornadas o iniciar la app.
* **Validación Centralizada con Pydantic**: Integridad total de datos en cada endpoint de la API.

---

## 📚 Documentación Especializada

Para consultar los detalles matemáticos, reglas de negocio y flujos específicos de cada módulo, revisa las guías dedicadas:

* 📋 [**Módulo de Auxiliares y Nómina**](docs/MODULO_NOMINA.md): Fórmulas de mano de obra, liquidación de colaboradoras, reglas de descuentos, desprendibles de pago imprimibles y exportación contable a Excel.
* 📦 [**Inventario, Presentaciones y Combos**](docs/INVENTARIO_Y_PRESENTACIONES.md): Modelo de stock en unidades individuales, factores de conversión, finanzas por presentación y deducción de stock en combos.
* 📊 [**Jornadas de Trabajo e Histórico de Ventas**](docs/JORNADAS_Y_REPORTES.md): Turnos de caja persistentes, desglose de cuentas financieras (Administradora, Inversión, Inversionista, Fletes), edición y eliminación de ventas con retorno a inventario, y respaldos automáticos.

---

## 🛠️ Tecnologías Utilizadas

| Componente | Tecnología | Descripción |
| :--- | :--- | :--- |
| **Backend** | Python 3.12+ (compatible con 3.14 y 3.15) | Lenguaje base del servidor. |
| **Framework Web** | Flask 3.x | Microframework modular con arquitectura de **Blueprints**. |
| **Base de Datos** | SQLite 3 (`peluqueria_pos.db`) | Base de datos relacional con claves foráneas y modo **WAL** activo. |
| **Validación de Datos** | Pydantic v2 | Validación tipada de payloads JSON en todos los endpoints. |
| **Procesamiento de Datos** | Pandas & OpenPyXL | Análisis numérico y exportación avanzada de hojas de cálculo Excel (`.xlsx`). |
| **Zona Horaria** | Python `zoneinfo` | Normalización con hora oficial de Colombia (`America/Bogota`). |
| **Frontend Estilos** | Tailwind CSS | Interfaz moderna con soporte completo para **Modo Oscuro (*Dark Mode*)**. |
| **Iconografía** | FontAwesome 6 | Iconos vectoriales servidos localmente. |
| **Gráficos** | Chart.js | Visualización gráfica de ingresos y tendencias en el Dashboard. |

---

## 📁 Estructura del Proyecto

```text
keratinas_e_hidrataciones/
│
├── run.py                          # Punto de entrada de la aplicación Flask
├── requirements.txt                # Dependencias del proyecto Python
├── peluqueria_pos.db               # Base de datos SQLite
├── .env.example                    # Plantilla de variables de entorno
├── .env                            # Configuración local (ignorado en Git)
├── .gitignore                      # Reglas de exclusión para Git
├── README.md                       # Documentación general del sistema
│
├── docs/                           # Documentación técnica detallada
│   ├── MODULO_NOMINA.md            # Guía completa de nómina, fórmulas y desprendibles
│   ├── INVENTARIO_Y_PRESENTACIONES.md # Guía de stock, presentaciones y combos
│   └── JORNADAS_Y_REPORTES.md      # Guía de jornadas, balance financiero y reportes
│
├── backups/                        # Directorio de copias de seguridad automáticas (.db)
│
└── app/                            # Paquete principal de la aplicación
    ├── __init__.py                 # Application Factory (create_app), inicio de backups
    ├── database.py                 # Conexión SQLite, esquemas DDL y migraciones
    ├── backup.py                   # Servicio de copias de seguridad en caliente y rotación
    ├── schemas.py                  # Modelos de validación con Pydantic v2
    │
    ├── routes/                     # Controladores y Endpoints (Blueprints de Flask)
    │   ├── main_routes.py          # Vistas principales, histórico y exportación de ventas
    │   ├── api_ventas.py           # Registro de servicios/productos y jornadas
    │   ├── api_productos.py        # CRUD de productos, stock y presentaciones
    │   ├── api_combos.py           # Armado y venta de combos
    │   ├── api_auxiliares.py       # Directorio de estilistas auxiliares
    │   ├── api_nomina.py           # Cálculo de liquidación, descuentos y desprendibles
    │   └── api_inversionistas.py   # Gestión de inversionistas, porcentajes y productos financiados
    │
    ├── templates/                  # Plantillas Jinja2
    │   ├── layout.html             # Shell maestro (sidebar fija, header, dark mode)
    │   ├── index.html              # Contenedor principal de módulos
    │   ├── dashboard.html          # Métricas de ventas y gráficos
    │   ├── servicios.html          # Facturación de keratinas e hidrataciones
    │   ├── productos.html          # Facturación y catálogo de productos
    │   ├── combos.html             # Gestión y venta de combos
    │   ├── auxiliares.html         # Directorio de colaboradoras
    │   ├── nomina.html             # Liquidación de nómina y recibos
    │   ├── inversionistas.html     # Directorio de inversionistas y productos financiados
    │   └── historico.html          # Histórico con filtros por fecha, tipo y acciones (editar/eliminar)
    │
    └── static/                     # Archivos estáticos cliente
        ├── css/style.css           # Estilos complementarios y reglas de impresión
        ├── img/logo_erika.png      # Logotipo del salón
        ├── js/                     # Lógica cliente modular (main.js, nomina.js, etc.)
        └── vendor/                 # Librerías cliente locales (100% offline)
            ├── tailwind/           # Tailwind CSS Play script
            ├── chartjs/            # Chart.js
            └── fontawesome/        # FontAwesome CSS y fuentes web (woff2/ttf)
```

---

## 🚀 Guía de Instalación y Ejecución Local

Sigue estos pasos para clonar y ejecutar el sistema en tu máquina:

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/keratinas_e_hidrataciones.git
cd keratinas_e_hidrataciones
```

### 2. Crear y Activar un Entorno Virtual

* **En Windows (PowerShell / CMD)**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```

* **En macOS / Linux**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar las Dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar el Archivo de Entorno (`.env`)
Copia la plantilla `.env.example` y crea tu archivo `.env`:

* **En Windows**:
  ```powershell
  copy .env.example .env
  ```
* **En macOS / Linux**:
  ```bash
  cp .env.example .env
  ```

*(Puedes abrir `.env` con cualquier editor de texto para ajustar el puerto o la clave secreta si lo requieres).*

### 5. Iniciar la Aplicación
```bash
python run.py
```

El servidor iniciará mostrando en consola:
```text
============================================================
🚀 Servidor modular de Peluquería POS activo.
🌐 Servidor escuchando en: http://127.0.0.1:5000
⚙️  Modo Debug: Activado
============================================================
[BACKUP] Copia de seguridad creada exitosamente: peluqueria_pos_..._inicio_servidor.db
[BACKUP] Programador de copias automáticas activo (cada 12.0 horas).
```

### 6. Abrir en el Navegador
Visita [**http://127.0.0.1:5000**](http://127.0.0.1:5000) para acceder a la aplicación.

---

## ⚙️ Configuración y Variables de Entorno

El archivo `.env` permite configurar las opciones operativas del sistema:

| Variable | Valor por Defecto | Descripción |
| :--- | :---: | :--- |
| `FLASK_ENV` | `development` | Entorno de ejecución (`development` o `production`). |
| `FLASK_DEBUG` | `True` | Activa o desactiva la recarga automática y trazas de depuración. |
| `PORT` | `5000` | Puerto TCP donde escuchará la aplicación. |
| `HOST` | `127.0.0.1` | Dirección IP de escucha (`127.0.0.1` local o `0.0.0.0` para red local). |
| `SECRET_KEY` | *(clave aleatoria)* | Clave para proteger sesiones y cookies. |
| `DATABASE_PATH` | `peluqueria_pos.db` | Nombre o ruta relativa del archivo SQLite. |
| `BACKUP_DIR` | `backups` | Carpeta donde se almacenarán las copias de seguridad. |
| `MAX_BACKUPS` | `30` | Límite máximo de copias conservadas antes de la rotación automática. |
| `BACKUP_INTERVAL_HOURS`| `12` | Frecuencia en horas para respaldos automáticos en segundo plano. |

---

## 🧭 Módulos del Sistema

1. **Dashboard General**: Panel central con indicadores de ventas del día, balance financiero, ingresos netos y gráficos de servicios más solicitados.
2. **Registro de Servicios**: Formulario de cobro para Keratinas, Hidrataciones y Servicios fijos. Permite asignar auxiliares participantes con sus respectivos porcentajes.
3. **Venta de Productos**: Carrito de compras con selección de presentaciones (Unidad, Media Docena, Docena), control de existencias en vivo y cálculo automático de márgenes para administradora e inversionista.
4. **Gestión de Productos**: Catálogo maestro para crear o editar productos, stock disponible, precio base, fletes, comisiones por presentación y vinculación opcional de inversionistas.
5. **Gestión de Combos**: Armado de paquetes promocionales integrando múltiples productos del catálogo.
6. **Auxiliares**: Directorio de colaboradoras con control de activación/desactivación sin pérdida de trazabilidad histórica.
7. **Nómina y Descuentos**: Cálculo de liquidaciones por rango de fechas, aplicación de descuentos personalizados, impresión de desprendibles y exportación contable a Excel.
8. **Inversionistas**: Directorio de inversionistas con porcentajes de ganancia acordados, cálculo de retornos e inventario financiado.
9. **Histórico de Ventas**: Búsqueda global de todas las transacciones históricas con filtros por fecha y tipo, detalle del costo de inversión por inversionista, edición de ventas, eliminación con reposición automática a inventario y exportación a Excel.

---

## 🛡️ Copias de Seguridad y Resiliencia

El sistema cuenta con un motor de respaldo en caliente ([app/backup.py](app/backup.py)) que utiliza la API atómica `sqlite3.backup()`:

* **Sin Interrupciones**: Las copias se generan mientras el salón sigue facturando, sin bloquear lecturas ni escrituras.
* **Rotación Automática**: Para evitar llenar el disco duro, el sistema conserva únicamente las últimas $N$ copias (configurado con `MAX_BACKUPS`).
* **Endpoints de Respaldo**:
  * `GET /api/sistema/backups`: Lista todas las copias de seguridad disponibles con su tamaño y fecha.
  * `POST /api/sistema/backup`: Genera una copia manual inmediata.
* **Ejecución desde Consola**: Puedes ejecutar un respaldo manual en cualquier momento con:
  ```bash
  python -m app.backup "respaldo_manual"
  ```
