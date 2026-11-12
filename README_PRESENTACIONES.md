# Cambio de inventario y presentaciones

Se implementó un modelo en el que cada producto tiene **un único stock expresado en unidades individuales** y puede venderse mediante múltiples presentaciones.

## Presentaciones iniciales

- Unidad: factor 1
- Media docena: factor 6
- Docena: factor 12

Las tres quedan disponibles para todos los productos.

## Presentaciones adicionales

Desde **Gestión de Productos > Catálogo de Presentaciones** se puede crear una presentación adicional indicando:

- Nombre
- Factor de unidades que consume

Por ejemplo: `Caja x24` con factor `24`.

Al crearla, queda disponible automáticamente para todos los productos. El precio/costo de esa presentación se inicializa con los valores de la presentación Unidad y después puede editarse por producto.

## Stock

El stock no se duplica por presentación.

Ejemplo con 20 unidades:

- 1 Unidad consume 1 → quedan 19.
- 2 Media docenas consumen 12 → quedan 8.
- 1 Docena requiere 12 → no se permite si solo quedan 8.

La validación definitiva se realiza en el backend usando el factor almacenado en SQLite.

## Migración

La base de datos existente se migró automáticamente. Los productos que anteriormente estaban duplicados como `Producto`, `Producto X6` y `Producto x12` se consolidan en un solo producto con tres presentaciones.

Para el inventario existente, se conservó el mayor stock encontrado entre las variantes para evitar perder existencias durante la migración. En el caso del Tratamiento Alisador, el stock migrado es de 10 unidades porque era el valor registrado en la variante x12.

Los precios/costos históricos de las variantes se conservaron en la configuración de cada presentación.

Las ventas históricas mantienen el detalle textual de la venta y el detalle de presentación en `venta_items`.
