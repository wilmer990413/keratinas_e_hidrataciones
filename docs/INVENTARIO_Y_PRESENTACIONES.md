# 📦 Inventario, Presentaciones y Combos

[← Volver al README Principal](../README.md) | [📋 Módulo de Nómina](MODULO_NOMINA.md) | [📊 Jornadas e Histórico](JORNADAS_Y_REPORTES.md)

---

## 1. Modelo de Stock Unificado

Para evitar inconsistencias de inventario, el sistema gestiona **un único stock expresado en unidades individuales** para cada producto.

Un producto físico nunca duplica sus registros según el formato en que se venda:
* Una ampolleta, tratamiento o shampoo tiene un contador único de unidades en existencia (`productos.stock`).
* Las ventas descuentan directamente este contador según el **factor multiplicador** de la presentación elegida.

---

## 2. Presentaciones y Factores de Consumo

Cada producto cuenta con diferentes presentaciones comerciales asociadas:

| Presentación | Factor de Consumo | Descripción |
| :--- | :---: | :--- |
| **Unidad** | `1` | Venta al por menor individual. Consume 1 unidad del stock. |
| **Media docena** | `6` | Paquete de 6 unidades. Consume 6 unidades del stock. |
| **Docena** | `12` | Paquete de 12 unidades. Consume 12 unidades del stock. |
| **Personalizada** | `N` | Cajas o kits especiales (ej: Caja x24 con factor 24). |

### 🛠️ Creación de Presentaciones Personalizadas
Desde **Gestión de Productos > Catálogo de Presentaciones**, se pueden crear nuevos formatos indicando el nombre y el factor de unidades. 
* Al crear una presentación, queda disponible inmediatamente para todo el catálogo de productos.
* Se inicializa con los precios base de la unidad y luego puede ajustarse individualmente por producto.

### 📐 Ejemplo de Deducción de Stock
Si un producto tiene **20 unidades** en stock:
1. Una venta de **1 Unidad** consume $1 \times 1 = 1$ unidad $\rightarrow$ Quedan **19 unidades**.
2. Una venta de **2 Medias docenas** consume $2 \times 6 = 12$ unidades $\rightarrow$ Quedan **7 unidades**.
3. Un cliente intenta comprar **1 Docena** (requiere 12 unidades) $\rightarrow$ El sistema **bloquea la venta** automáticamente porque solo quedan 7 disponibles.

---

## 3. Finanzas por Presentación de Producto

Para cada presentación de cada producto, se configuran de forma independiente:
* **Costo Base**: Valor de costo unitario del producto para el inversionista.
* **Ganancia Administradora**: Margen de utilidad para la administradora del salón.
* **Ganancia Inversionista**: Margen de utilidad para el inversionista que financia el inventario.
* **Flete**: Costo logístico o de transporte asignado.

El precio final al público (PVP) se calcula automáticamente como la suma de estos 4 componentes:

$$\text{PVP} = \text{Costo Base} + \text{Ganancia Admin} + \text{Ganancia Inversionista} + \text{Flete}$$

---

## 4. Módulo de Combos (Paquetes Promocionales)

El sistema permite empaquetar varios productos en ofertas especiales (*Combos*):
* **Composición Dinámica**: Un combo puede incluir cualquier cantidad de productos del catálogo (ej: *1 Tratamiento Alisador + 1 Shampoo Antiresiduos + 2 Ampolletas Rojas*).
* **Cálculo de Disponibilidad de Combos**: El stock disponible para vender de un combo se calcula automáticamente en tiempo real mediante la disponibilidad del producto más escaso:
  
  $$\text{Stock Combo} = \min_{i} \left( \left\lfloor \frac{\text{Stock Actual}_i}{\text{Cantidad Requerida}_i} \right\rfloor \right)$$

* **Deducción y Devolución Atómica**:
  * Al vender un combo, se descuentan las unidades individuales de todos los productos que lo conforman.
  * Si una venta que incluía combos es eliminada o anulada desde el reporte diario, **el stock de todos los productos individuales regresa intacto al inventario**.

---

## 5. Módulo de Inversionistas y Financiación de Productos

El sistema cuenta con un **Módulo de Inversionistas** para registrar a los socios que aportan capital en el negocio:

* **Porcentaje de Ganancia Acordado**: Cada inversionista tiene un porcentaje de utilidad registrado (ej: 20%, 25%, 30%).
* **Relación Opcional en Productos**: Al crear o editar un producto en **Gestión de Productos**, se puede asociar al inversionista responsable o dejarlo como *Sin inversionista (Propio)*.
* **Cálculo Automático de Retorno**: Al seleccionar un inversionista, el sistema sugiere automáticamente la Ganancia del Inversionista en cada presentación según su porcentaje:
  
  $$\text{Ganancia Inversionista} = \text{Costo Base} \times \left(\frac{\% \text{ Ganancia}}{100}\right)$$

* **Trazabilidad en Ventas e Histórico**: Cada venta de producto guarda el costo de inversión asociado al inversionista correspondiente y lo refleja en la tabla de **Histórico General de Ventas** y en las exportaciones a Excel.
* **Control de Existencias Financiadas**: En el módulo de Inversionistas es posible consultar en tiempo real el catálogo de productos que financió cada inversionista junto con el valor total de su inversión en el stock actual disponible.
