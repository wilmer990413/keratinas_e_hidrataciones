# 📋 Módulo de Auxiliares y Nómina

[← Volver al README Principal](../README.md) | [📦 Inventario y Presentaciones](INVENTARIO_Y_PRESENTACIONES.md) | [📊 Jornadas e Histórico](JORNADAS_Y_REPORTES.md)

---

## 1. Visión General del Módulo

El módulo de **Auxiliares y Nómina** permite administrar el equipo de colaboradoras del salón, calcular con exactitud la participación en los servicios realizados, aplicar deducciones/descuentos personalizados y emitir desprendibles de pago imprimibles y libros de Excel para la liquidación.

A diferencia del flujo de caja diario, **la nómina se calcula sobre el histórico completo por rango de fechas**, lo que permite liquidar semanas o quincenas completas incluso si las jornadas diarias ya fueron cerradas.

---

## 2. Gestión de Auxiliares

Desde la vista **Auxiliares** se gestiona el directorio del personal:
* **Creación y edición**: Nombre, documento de identidad, número de teléfono y estado.
* **Borrado lógico (Desactivación)**: Al desactivar un auxiliar no se borra su historial financiero ni los servicios donde participó; simplemente deja de aparecer como opción al registrar nuevas ventas.
* **Reactivación**: Permite volver a habilitar a cualquier auxiliar cuando regrese al turno de trabajo.

---

## 3. Fórmulas de Repartición de Mano de Obra

En el salón, los servicios se realizan bajo diferentes modalidades:
1. **Solo Administradora**: 100% de la mano de obra para la administradora.
2. **Servicios Fijos**: Tarifa plana para la administradora sin intervención de auxiliares.
3. **Servicios con Auxiliares (Keratinas e Hidrataciones)**: Uno o varios auxiliares participan con un porcentaje asignado sobre la mano de obra total.

### 📐 Definición Matemática

La mano de obra total es la suma de lo que gana la administradora más todos los auxiliares:

$$\text{Mano de Obra Total} = \text{Ganancia Administradora} + \sum \text{Pagos Auxiliares}$$

Si la administradora recibe un valor pactado $A$ y los porcentajes manuales asignados a los auxiliares suman $P$ (donde $P = \sum p_i < 1.0$), la base de mano de obra total se calcula de forma exacta:

$$\text{Mano de Obra} = \frac{A}{1 - P}$$

Y la liquidación de cada auxiliar participante $i$ es:

$$\text{Pago Auxiliar}_i = \text{Mano de Obra} \times p_i$$

El precio total facturado al cliente es:

$$\text{Total Facturado} = \text{Materia Prima} + \text{Ganancia Administradora} + \sum \text{Pagos Auxiliares}$$

---

### 💡 Ejemplos Numéricos

#### Ejemplo 1: Hidratación con 1 Auxiliar (50%)
* Ganancia Administradora ($A$): **\$25.000**
* Materia Prima: **\$15.000**
* Porcentaje Auxiliar ($P$): **50% (0.5)**
* Mano de obra: $\frac{25000}{1 - 0.5} = \$50.000$
* Pago Auxiliar: $\$50.000 \times 0.5 = \mathbf{\$25.000}$
* **Total Servicio al Cliente**: $\$15.000 + \$25.000 + \$25.000 = \mathbf{\$65.000}$

#### Ejemplo 2: Keratina con 2 Auxiliares (20% y 20%)
* Ganancia Administradora ($A$): **\$45.000**
* Materia Prima: **\$35.000**
* Auxiliar 1: **20%** | Auxiliar 2: **20%** ($P = 40\% = 0.4$)
* Mano de obra: $\frac{45000}{1 - 0.4} = \$75.000$
* Pago Auxiliar 1: $\$75.000 \times 0.20 = \mathbf{\$15.000}$
* Pago Auxiliar 2: $\$75.000 \times 0.20 = \mathbf{\$15.000}$
* **Total Servicio al Cliente**: $\$35.000 + \$45.000 + \$15.000 + \$15.000 = \mathbf{\$110.000}$

---

## 4. Descuentos y Deducciones

El panel de **Descuentos a Aplicar** permite configurar deducciones periódicas:
* **Concepto**: Motivo del descuento (ej: *Seguridad Social*, *Préstamo*, *Anticipo*, *Insumos personales*).
* **Tipo**:
  * **Valor Fijo (\$)**: Monto exacto en pesos.
  * **Porcentaje (%)**: Porcentaje calculado sobre el valor bruto devengado de la persona.
* **Destinatario (`aplicarA` / `destino`)**:
  * *La Administradora*: Aplica solo a la administradora.
  * *Cada Auxiliar*: Aplica individualmente a todas las auxiliares con ingresos en el rango.
  * *Auxiliar Específico*: Aplica únicamente a la persona seleccionada.

### 🛡️ Reglas de Seguridad Financiera
1. **Piso de Neto No Negativo**: Las deducciones nunca pueden superar el valor bruto devengado. $\text{Neto} = \max(0, \text{Bruto} - \text{Descuentos})$.
2. **Auxiliares sin Ingresos**: Si se configura un descuento para un auxiliar que no tuvo servicios en el periodo, el sistema omite el cobro y alerta a la administradora.
3. **Persistencia Local**: Los descuentos configurados se guardan en el navegador (`localStorage`) para agilizar liquidaciones recurrentes.

---

## 5. Desprendibles de Pago Imprimibles

En la vista de Nómina se selecciona el destinatario y se genera el recibo de liquidación con:
* Membrete corporativo del salón y fecha de expedición.
* Datos del colaborador (nombre, documento, periodo liquidado).
* **Ingresos detallados**: Cada procedimiento con fecha, nombre del cliente, porcentaje de mano de obra y pago.
* **Deducciones desglosadas**: Concepto, porcentaje o valor fijo, y monto debitado.
* **Totales en negrilla**: Total Devengado, Total Deducciones y **Neto a Pagar**.
* Espacio de firmas para el pagador y el colaborador (*Recibí conforme*).
* Optimizado para imprimir directamente o **Guardar como PDF** en tamaño carta o media carta.

---

## 6. Exportación de Nómina a Excel

El botón **Exportar Nómina Excel** genera un archivo `.xlsx` estructurado en pestañas especializadas:
1. `Totales`: Resumen macro del periodo (total devengado, descuentos consolidados y neto global pagado).
2. `Administradora`: Liquidación detallada de la administradora.
3. `Auxiliares`: Tabla consolidada con servicios realizados, bruto, descuentos y neto por auxiliar.
4. `Descuentos`: Detalle de todas las deducciones procesadas con su concepto y destinatario.
5. `Detalle`: Registro individual de cada servicio registrado en el rango de fechas.
