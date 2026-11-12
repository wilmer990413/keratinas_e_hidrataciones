# Actualización: Auxiliares y Nómina

Se incorporaron tres cambios principales al sistema:

## 1. Módulo de Auxiliares

Permite:
- Crear auxiliares.
- Editar nombre, documento y teléfono.
- Desactivar auxiliares sin borrar su historial.
- Reactivar auxiliares.
- Usar únicamente auxiliares activos en el registro de servicios.

## 2. Registro de Servicios

El registro conserva las modalidades que ya existían:
- Hidratación: solo administradora o administradora + 1 auxiliar.
- Keratina: solo administradora, administradora + 1 auxiliar o administradora + N auxiliares.
- Servicios fijos: 100% para administradora y sin auxiliar.

Ahora, cuando participan auxiliares, la administradora selecciona exactamente quién participó y escribe manualmente el porcentaje de cada uno.

### Cálculo del porcentaje

El porcentaje se interpreta como participación sobre la **mano de obra total**, es decir:

`Mano de obra = Administradora + Auxiliares`

Si la administradora recibe `A` y los porcentajes de auxiliares suman `P`, entonces:

`Mano de obra = A / (1 - P)`

Cada auxiliar recibe:

`Pago auxiliar = Mano de obra × porcentaje auxiliar`

La suma de porcentajes debe ser menor al 100%.

Ejemplo:
- Administradora: $25.000
- Auxiliar: 50%
- Mano de obra: $50.000
- Pago auxiliar: $25.000

Para dos auxiliares:
- Administradora: $45.000
- Auxiliar 1: 20%
- Auxiliar 2: 20%
- Mano de obra: $75.000
- Pago auxiliar 1: $15.000
- Pago auxiliar 2: $15.000

La fórmula mantiene la lógica original del sistema:

`Total servicio = Materia prima + Administradora + Auxiliares`

## 3. Módulo de Nómina

Permite consultar por rango de fechas:
- Nómina de la administradora.
- Total a pagar por cada auxiliar.
- Cantidad de procedimientos por auxiliar.
- Detalle de cada procedimiento, porcentaje, base de mano de obra y pago.
- Exportación de la nómina a Excel.

La nómina de auxiliares se alimenta directamente de la relación guardada al registrar cada servicio, por lo que queda trazabilidad de qué auxiliar participó en cada procedimiento.

## Base de datos

Se agregaron las tablas:
- `auxiliares`
- `servicio_auxiliares`

La tabla `transacciones` existente se conserva para no perder los registros actuales. La inicialización del sistema crea automáticamente las nuevas tablas cuando se ejecuta una versión anterior de la base de datos.

## 4. Descuentos en la nómina

Al hacer clic en **Calcular Nómina** el sistema filtra por fechas y además calcula el **neto a pagar** aplicando los descuentos configurados en el panel "Descuentos a aplicar".

Cada descuento tiene:
- **Concepto** (ej.: seguridad social, anticipo).
- **Tipo**: valor fijo ($) o porcentaje (%).
- **Valor**.
- **Descontar a**: la administradora, cada auxiliar (se aplica a todos los auxiliares que tengan pagos en el periodo) o un auxiliar específico.

Reglas de cálculo:
- Los porcentajes se calculan sobre lo devengado (bruto) de cada persona.
- `Neto = Bruto − Descuentos`.
- El descuento acumulado nunca supera lo devengado: el neto no puede ser negativo (se muestra un aviso si se limitó).
- Si un descuento va dirigido a un auxiliar sin pagos en el periodo, no se aplica y se muestra un aviso.
- Los descuentos se recuerdan en el navegador (localStorage) para no tener que escribirlos de nuevo.

La exportación a Excel incluye las hojas `Totales`, `Administradora`, `Auxiliares`, `Descuentos` y `Detalle`, con bruto, descuentos y neto.

Los descuentos viajan al backend como parámetro `descuentos` (JSON) en `/api/nomina` y `/api/exportar-nomina-excel`.

## 5. Desprendible de nómina

En **Gestión de Nómina** se elige a quién liquidar (la administradora o un auxiliar) en el selector "Liquidar nómina a" y se hace clic en **Generar Desprendible**.

El desprendible (formato recibo) muestra:
- Encabezado con logo, empresa y fecha de generación.
- Datos de la persona: nombre, cargo, documento y periodo liquidado.
- **Ingresos / Devengado**: cada procedimiento con fecha, cliente y valor. Para auxiliares también el % de participación y la base de mano de obra.
- **Descuentos / Deducciones**: cada descuento registrado en el panel, con su concepto, tipo y valor descontado.
- Totales: total devengado, total descuentos y **neto a pagar**.
- Espacio para firmas (quien paga y recibí conforme).

Solo se aplican los descuentos dirigidos a la persona seleccionada (la administradora, "cada auxiliar" o ese auxiliar en particular). El botón **Imprimir / Guardar PDF** abre el diálogo de impresión del navegador; allí se puede elegir "Guardar como PDF".

Si la persona no tiene ingresos en el periodo, no se genera el desprendible y se muestra un aviso.

Endpoint: `GET /api/desprendible-nomina?inicio=&fin=&persona=admin|aux:<id>&descuentos=<json>`.

## 6. Cierre Diario: Ganancia Inversionista e Inversión

En **Cierre Diario y Reporte General** la columna "Inversionista/Costo" ahora son dos columnas:
- **Ganancia Inversionista**: la utilidad del inversionista.
- **Inversión**: lo que se invirtió (en servicios, la materia prima; en ventas de productos, costo base + flete).

La tabla `transacciones` guarda ahora `inversion_share` y `ganancia_inv_share` (`inv_share` se conserva como la suma de ambas). Al iniciar, los registros anteriores se desglosan automáticamente. Si alguno no se puede reconstruir (por ejemplo, un producto renombrado o eliminado), se muestra "—".

## 7. Presentación de productos

El campo **Tipo de Presentación / Regla** de cada producto ahora es: **Unidad (x1)**, **Media docena (x6)** o **Docena (x12)**. Los productos existentes quedaron como Unidad (sus totales no cambian); se editan desde Gestión de Productos.

En **Venta de Productos**:
- La presentación es un valor fijo en la tarjeta del producto (ya no es desplegable).
- La cantidad se cuenta en presentaciones: 2 × Docena = 24 unidades. El precio (PVP) del producto es por unidad, y el total, la ganancia de la administradora, la inversión y el flete se calculan sobre las unidades totales.
- El carrito y el detalle de la venta muestran la presentación (ej.: `2x Docena Óleo (24 ud)`).
- El resumen del carrito separa **Ganancia Inversionista** e **Inversión (costo base)**.

## 8. La nómina se calcula sobre el histórico completo

La nómina (resumen, desprendible y Excel) ya no depende de que la jornada esté activa. Toma todas las ventas del rango de fechas seleccionado, incluidos los días cerrados con **Reiniciar jornada**. Así se puede liquidar cualquier día o semana ya cerrado que aún no se haya pagado.

El Cierre Diario y el Dashboard siguen mostrando solo la jornada activa. El sistema no registra qué períodos ya se pagaron: al liquidar, hay que elegir bien el rango de fechas para no pagar dos veces el mismo día.

## 9. Stock de productos

Cada producto tiene un **Stock actual (unidades)**, que se edita en *Gestión de Productos* (campo y columna "Stock (ud)").

- El stock se maneja siempre en **unidades**. Al vender 2 docenas se descuentan 24 unidades; 1 media docena descuenta 6.
- Al **procesar una venta** el servidor descuenta las unidades del stock. Si un producto no alcanza, la venta completa se rechaza (no se descuenta nada ni se registra) y se muestra cuánto hay disponible.
- En *Venta de Productos* cada tarjeta muestra el stock; al agregar al carrito se muestra lo **disponible** (stock menos lo que ya está en el carrito). No se puede agregar más de lo que hay, y el botón "Agregar" se bloquea si no alcanza ni para una presentación completa (por ejemplo, una docena con 5 unidades).
- Si se **elimina una venta de productos** desde el Cierre Diario, sus unidades vuelven al stock. Las ventas hechas antes de esta función no tienen detalle de unidades, así que al eliminarlas el stock no cambia.
- **Reiniciar jornada** no modifica el stock.
- Los servicios (hidratación, keratina, etc.) no usan stock.

### Migración
Al iniciar, el sistema agrega la columna `stock` a la tabla `productos` y crea la tabla `venta_items` (detalle de unidades por venta). Los productos existentes quedan con **stock 0**: hay que ingresar el stock inicial de cada uno desde *Gestión de Productos* antes de poder venderlos. Los datos existentes no se modifican.
