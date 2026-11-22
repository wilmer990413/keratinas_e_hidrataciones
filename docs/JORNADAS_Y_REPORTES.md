# 📊 Jornadas de Trabajo e Histórico de Ventas

[← Volver al README Principal](../README.md) | [📋 Módulo de Nómina](MODULO_NOMINA.md) | [📦 Inventario y Presentaciones](INVENTARIO_Y_PRESENTACIONES.md)

---

## 1. Concepto de Jornadas (Turnos de Caja)

A diferencia de sistemas que dependen de la medianoche del reloj para reiniciar métricas, este sistema implementa el concepto de **Jornada de Trabajo Persistente**:
* Una jornada permanece abierta independientemente del cambio de día del calendario.
* Si el salón atiende clientas hasta altas horas de la noche o extiende un turno al día siguiente, todas las ventas continúan agrupadas dentro de la misma jornada activa.
* **El Dashboard muestra exclusivamente los datos de la jornada activa actual**.

---

## 2. Reinicio de Jornada

Para finalizar el turno y hacer corte de caja:
1. La administradora ingresa al **Dashboard General**.
2. Revisa el balance total de ingresos, ganancias y participaciones del día.
3. Presiona el botón **Reiniciar Jornada**:
   * La jornada activa se marca como cerrada con la fecha y hora exacta (`cerrada_en`).
   * Las transacciones de la jornada se conservan en el historial general (`activa = 0`).
   * Se inicia automáticamente una nueva jornada lista para recibir ventas.
   * **Se dispara una copia de seguridad en caliente automática** (`peluqueria_pos_YYYYMMDD_HHMMSS_cierre_jornada.db`).

---

## 3. Desglose de Cuentas Financieras

Cada venta (de servicio o producto) desglosa el dinero en cuentas contables diferenciadas:

```
                            [ Total Facturado al Cliente ]
                                          │
         ┌───────────────────┬────────────┴───────┬──────────────────────┐
         ▼                   ▼                    ▼                      ▼
┌──────────────────┐ ┌───────────────┐ ┌──────────────────────┐ ┌────────────────┐
│ Ganancia Admin   │ │ Auxiliares    │ │ Costo / Inversión    │ │ Ganancia Inv.  │
│ (Mano de obra    │ │ (Porcentajes  │ │ (Materia prima serv. │ │ (Utilidad del  │
│  administradora) │ │  comisiones)  │ │  o costo prod+flete) │ │  inversionista)│
└──────────────────┘ └───────────────┘ └──────────────────────┘ └────────────────┘
```

1. **Ganancia Administradora**: Ingreso neto que percibe la administradora por su trabajo y dirección.
2. **Pago Auxiliares**: Dinero liquidado a las colaboradoras que participaron en la mano de obra.
3. **Inversión**:
   * En servicios: valor del insumo o materia prima consumida.
   * En productos: costo base del producto para el inversionista más el flete logístico.
4. **Ganancia Inversionista**: Margen de utilidad para quien financió el producto o inventario.
5. **Fletes**: Costos de transporte cuando aplique.

---

## 4. Edición y Eliminación de Ventas desde el Histórico

Desde la tabla de **Histórico de Ventas** es posible gestionar y corregir cualquier transacción histórica mediante los botones de acción:
* **Editar Venta (Icono lápiz)**:
  * **Ventas de Servicios**: Permite corregir cliente, fecha/hora, valor de la administradora, materia prima y porcentajes o auxiliares participantes. El backend recalcula la mano de obra y el total de forma segura.
  * **Ventas de Productos**: Permite modificar cliente, fecha/hora, ganancia de la administradora, costo de inversión, utilidad del inversionista y fletes.
* **Eliminar Venta (Icono papelera)**:
  * Pide confirmación al usuario antes de proceder.
  * Si la venta incluía productos o combos, **las unidades vendidas regresan de forma automática al stock del inventario**.

---

## 5. Histórico de Ventas y Exportaciones a Excel

* **Filtros Avanzados**: Permite consultar transacciones históricas combinando **Rango de Fechas (Inicio / Fin)** con el filtro de **Tipo (Todas / Servicios / Productos)**.
* **Desglose de Costo por Inversionista**: En la columna *Inversionista / Costo*, el histórico detalla exactamente el nombre de cada inversionista participante en la venta y el costo de inversión asociado (o indica si fue venta propia / sin inversionista), tanto en la tabla web como en los reportes exportados a Excel.
* **Paginación Dinámica**: Carga eficiente en bloques de 10 registros para garantizar alta velocidad.
* **Exportación Inteligente**: Genera hojas de cálculo (`.xlsx`) con filtros automáticos aplicados en la cabecera, congelamiento de paneles (`freeze_panes = 'A2'`) y autoajuste del ancho de columnas para visualización clara.
