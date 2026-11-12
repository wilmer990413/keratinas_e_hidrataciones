# Cambios: Cierre, Reportes, Histórico, Fechas y Jornadas

## Cierre y Reportes
- Se eliminó **Imprimir Reporte**.
- Se agregó **Exportar Excel** de la jornada actual.
- Se agregó filtro por **Todas / Servicios / Productos**.
- Se agregó edición de ventas desde la tabla de la jornada.
- Las ventas de servicio permiten corregir cliente, fecha/hora, valor de administradora, materia prima y auxiliares/porcentajes.
- Las ventas de producto permiten corregir cliente, fecha/hora, ganancia de administradora, inversión, ganancia del inversionista y fletes.
- El total se recalcula en backend para evitar inconsistencias.

## Histórico de Ventas
- Se agregó filtro por **Todas / Servicios / Productos**.
- El filtro se combina con el rango de fechas existente.
- La exportación a Excel respeta los filtros seleccionados.

## Fecha y hora Colombia
- Las nuevas ventas ya no dependen de `toISOString()` del navegador.
- El backend guarda la fecha/hora usando `America/Bogota`.
- Las fechas históricas que presentaban el desfase de un día por la mezcla UTC/hora local fueron normalizadas cuando se detectó exactamente ese desfase.

## Jornada
- La jornada ya no cambia automáticamente al cambiar el día del calendario.
- Se agregó una tabla `jornadas` persistente.
- Una jornada permanece abierta aunque el calendario cambie de fecha.
- Solo el botón **Reiniciar Jornada** cierra la jornada actual y crea una nueva.
- El Dashboard y Cierre y Reportes muestran únicamente la jornada actual.
- Histórico y Nómina siguen consultando el histórico completo por fecha.
