let resumenCajaActual = null;

function formatoMonedaCaja(val) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0
  }).format(val || 0);
}

function hoyColombiaISO() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function cargarResumenCaja() {
  const inputFecha = document.getElementById('cajaFechaFiltro');
  if (!inputFecha.value) {
    inputFecha.value = hoyColombiaISO();
  }
  const fecha = inputFecha.value;

  try {
    const res = await fetch(`/api/caja/resumen?fecha=${fecha}`);
    if (!res.ok) throw new Error('Error al cargar balance de caja');
    const data = await res.json();
    resumenCajaActual = data;
    renderizarResumenCaja(data);
  } catch (err) {
    console.error(err);
    if (typeof mostrarNotificacion === 'function') {
      mostrarNotificacion('Error al consultar balance de caja', 'error');
    }
  }
}

function renderizarResumenCaja(data) {
  // Bolsillo Flete
  document.getElementById('kpiSaldoFlete').textContent = formatoMonedaCaja(data.bolsilloFlete.saldo);
  document.getElementById('kpiFleteCobrado').textContent = formatoMonedaCaja(data.bolsilloFlete.cobrado);
  document.getElementById('kpiFleteGastado').textContent = formatoMonedaCaja(data.bolsilloFlete.gastado);

  // Bolsillo Reinversión
  document.getElementById('kpiSaldoReinversion').textContent = formatoMonedaCaja(data.bolsilloReinversion.saldo);
  document.getElementById('kpiReinversionCobrado').textContent = formatoMonedaCaja(data.bolsilloReinversion.cobrado);
  document.getElementById('kpiReinversionGastado').textContent = formatoMonedaCaja(data.bolsilloReinversion.gastado);

  // Ganancia Admin
  document.getElementById('kpiGananciaAdmin').textContent = formatoMonedaCaja(data.ganancias.administradora);

  // Totales Teóricos
  document.getElementById('kpiSaldoTeorico').textContent = formatoMonedaCaja(data.totales.saldoTeorico);
  document.getElementById('kpiIngresosTotales').textContent = formatoMonedaCaja(data.totales.ingresos);
  document.getElementById('kpiEgresosTotales').textContent = formatoMonedaCaja(data.totales.egresos);
  document.getElementById('cuadreSaldoEsperado').textContent = formatoMonedaCaja(data.totales.saldoTeorico);

  // Ganancias Inversionistas
  document.getElementById('totalGananciasInv').textContent = formatoMonedaCaja(data.ganancias.totalInversionistas);

  // Tabla Inversionistas Dinámica
  const tbodyInv = document.getElementById('tablaRepartoInversionistas');
  const emptyInv = document.getElementById('emptyRepartoInv');
  tbodyInv.innerHTML = '';

  const listaInv = data.inversionistas || [];
  if (listaInv.length === 0) {
    emptyInv.classList.remove('hidden');
  } else {
    emptyInv.classList.add('hidden');
    listaInv.forEach(inv => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50/50 dark:hover:bg-gray-800/40 transition';

      let itemsHtml = '';
      if (inv.productos && Object.keys(inv.productos).length > 0) {
        itemsHtml = Object.entries(inv.productos)
          .map(([pNom, pInfo]) => `<span class="inline-block bg-gray-100 dark:bg-gray-800 text-[10px] px-1.5 py-0.5 rounded mr-1 mb-1">${pNom} (${pInfo.unidades} un.)</span>`)
          .join('');
      } else {
        itemsHtml = '<span class="text-gray-400 text-[10px]">Sin ventas registradas hoy</span>';
      }

      tr.innerHTML = `
        <td class="p-3.5">
          <div class="font-bold text-gray-900 dark:text-white">${inv.nombre}</div>
          <div class="mt-1">${itemsHtml}</div>
        </td>
        <td class="p-3.5 text-center font-bold text-gray-700 dark:text-gray-300">${inv.unidadesVendidas}</td>
        <td class="p-3.5 text-right font-bold text-emerald-600 dark:text-emerald-400">${formatoMonedaCaja(inv.gananciaNeta)}</td>
        <td class="p-3.5 text-right font-semibold text-amber-600 dark:text-amber-400">${formatoMonedaCaja(inv.capitalRetorno)}</td>
        <td class="p-3.5 text-right font-black text-purple-600 dark:text-purple-400">${formatoMonedaCaja(inv.totalLiquidar)}</td>
        <td class="p-3.5 text-center">
          <span class="text-[10px] px-2 py-0.5 rounded-full ${inv.totalLiquidar > 0 ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300' : 'bg-gray-100 text-gray-500'} font-semibold">
            ${inv.totalLiquidar > 0 ? 'Por liquidar' : 'Al día'}
          </span>
        </td>
      `;
      tbodyInv.appendChild(tr);
    });
  }

  // Tabla Egresos
  const tbodyEg = document.getElementById('tablaEgresosDia');
  const emptyEg = document.getElementById('emptyEgresos');
  tbodyEg.innerHTML = '';

  const listaEg = data.egresos || [];
  if (listaEg.length === 0) {
    emptyEg.classList.remove('hidden');
  } else {
    emptyEg.classList.add('hidden');
    listaEg.forEach(eg => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50/50 dark:hover:bg-gray-800/40 transition';

      let badgeColor = 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
      if (eg.bolsillo === 'FLETE') badgeColor = 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300';
      if (eg.bolsillo === 'REINVERSION') badgeColor = 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300';

      const horaCorta = eg.fecha.split(' ')[1] || eg.fecha;

      tr.innerHTML = `
        <td class="p-3.5 text-gray-500 whitespace-nowrap">${horaCorta}</td>
        <td class="p-3.5">
          <span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${badgeColor}">${eg.bolsillo}</span>
        </td>
        <td class="p-3.5">
          <span class="font-medium text-gray-800 dark:text-gray-200">${eg.descripcion}</span>
          ${eg.inversionistaNombre ? `<span class="block text-[10px] text-gray-400">Para: ${eg.inversionistaNombre}</span>` : ''}
        </td>
        <td class="p-3.5 text-right font-bold text-red-600 dark:text-red-400 whitespace-nowrap">-${formatoMonedaCaja(eg.monto)}</td>
        <td class="p-3.5 text-center">
          <button onclick="anularEgreso('${eg.id}')" class="text-red-400 hover:text-red-600 dark:hover:text-red-300 p-1 rounded transition" title="Eliminar egreso">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </td>
      `;
      tbodyEg.appendChild(tr);
    });
  }

  // Si ya existía un cierre guardado para la fecha, cargar sus datos
  if (data.cierre) {
    document.getElementById('cuadreSaldoReal').value = data.cierre.saldoRealBanco;
    document.getElementById('cierreObservaciones').value = data.cierre.observaciones || '';
    calcularDiferenciaCaja();
  } else {
    document.getElementById('cuadreSaldoReal').value = '';
    document.getElementById('cierreObservaciones').value = '';
    document.getElementById('alertaDiferencia').classList.add('hidden');
  }

  // Poblar select de inversionistas en egresos si no está poblado
  poblarSelectInversionistasEgreso(listaInv);
}

function poblarSelectInversionistasEgreso(listaInv) {
  const sel = document.getElementById('egresoInversionistaId');
  if (!sel) return;
  const valActual = sel.value;
  sel.innerHTML = '<option value="">-- General / No aplica --</option>';
  listaInv.forEach(inv => {
    if (inv.id && inv.id !== 'SIN_ASIGNAR') {
      const opt = document.createElement('option');
      opt.value = inv.id;
      opt.textContent = inv.nombre;
      sel.appendChild(opt);
    }
  });
  sel.value = valActual;
}

function actualizarCategoriasEgreso() {
  const bolsillo = document.getElementById('egresoBolsillo').value;
  const campoInv = document.getElementById('campoInversionistaEgreso');
  if (bolsillo === 'REINVERSION') {
    campoInv.classList.remove('hidden');
  } else {
    campoInv.classList.add('hidden');
  }
}

async function guardarEgreso(e) {
  e.preventDefault();
  const monto = parseFloat(document.getElementById('egresoMonto').value);
  const bolsillo = document.getElementById('egresoBolsillo').value;
  const descripcion = document.getElementById('egresoDescripcion').value.trim();
  const fecha = document.getElementById('cajaFechaFiltro').value || hoyColombiaISO();
  const invSelect = document.getElementById('egresoInversionistaId');
  const invId = invSelect ? invSelect.value : null;

  if (!monto || monto <= 0 || !descripcion) {
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion('Ingresa un monto y detalle válidos', 'error');
    return;
  }

  try {
    const res = await fetch('/api/caja/egreso', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        monto,
        bolsillo,
        descripcion,
        fecha,
        inversionistaId: invId
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al guardar egreso');

    if (typeof mostrarNotificacion === 'function') mostrarNotificacion('Egreso registrado correctamente', 'success');
    document.getElementById('formRegistrarEgreso').reset();
    actualizarCategoriasEgreso();
    cargarResumenCaja();
  } catch (err) {
    console.error(err);
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion(err.message, 'error');
  }
}

async function anularEgreso(id) {
  if (!confirm('¿Estás seguro de anular este egreso? El monto volverá al saldo del bolsillo correspondiente.')) return;
  try {
    const res = await fetch(`/api/caja/egreso/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al anular egreso');
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion('Egreso eliminado', 'info');
    cargarResumenCaja();
  } catch (err) {
    console.error(err);
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion(err.message, 'error');
  }
}

function calcularDiferenciaCaja() {
  if (!resumenCajaActual) return;
  const saldoTeorico = resumenCajaActual.totales.saldoTeorico;
  const inputReal = document.getElementById('cuadreSaldoReal');
  const alerta = document.getElementById('alertaDiferencia');
  const icono = document.getElementById('alertaDiferenciaIcono');
  const texto = document.getElementById('alertaDiferenciaTexto');

  if (inputReal.value === '') {
    alerta.classList.add('hidden');
    return;
  }

  const saldoReal = parseFloat(inputReal.value) || 0;
  const dif = Math.round(saldoReal - saldoTeorico);

  alerta.classList.remove('hidden', 'bg-emerald-50', 'text-emerald-700', 'bg-red-50', 'text-red-700', 'bg-blue-50', 'text-blue-700');

  if (Math.abs(dif) < 1) {
    alerta.classList.add('bg-emerald-50', 'text-emerald-700', 'dark:bg-emerald-950/40', 'dark:text-emerald-300');
    icono.className = 'fa-solid fa-circle-check text-base text-emerald-600';
    texto.innerHTML = `<strong>¡Caja Cuadrada Perfecta!</strong> El saldo de Bancolombia coincide exactamente con el sistema ($0 diferencia).`;
  } else if (dif < 0) {
    alerta.classList.add('bg-red-50', 'text-red-700', 'dark:bg-red-950/40', 'dark:text-red-300');
    icono.className = 'fa-solid fa-triangle-exclamation text-base text-red-600';
    texto.innerHTML = `<strong>Faltante de dinero: ${formatoMonedaCaja(Math.abs(dif))}</strong>. Hay menos plata en la cuenta de lo que reporta el sistema (posible gasto no registrado o pusiste de tu bolsillo).`;
  } else {
    alerta.classList.add('bg-blue-50', 'text-blue-700', 'dark:bg-blue-950/40', 'dark:text-blue-300');
    icono.className = 'fa-solid fa-circle-info text-base text-blue-600';
    texto.innerHTML = `<strong>Sobrante de dinero: ${formatoMonedaCaja(dif)}</strong>. Hay más dinero en la cuenta del que registra el sistema.`;
  }
}

async function guardarCierreCaja() {
  const inputReal = document.getElementById('cuadreSaldoReal');
  if (inputReal.value === '') {
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion('Por favor ingresa cuánto dinero tienes en Bancolombia / Efectivo', 'warning');
    inputReal.focus();
    return;
  }

  const fecha = document.getElementById('cajaFechaFiltro').value || hoyColombiaISO();
  const saldoRealBanco = parseFloat(inputReal.value) || 0;
  const observaciones = document.getElementById('cierreObservaciones').value.trim();

  try {
    const res = await fetch('/api/caja/cierre', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fecha, saldoRealBanco, observaciones })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al guardar cierre');

    if (typeof mostrarNotificacion === 'function') {
      mostrarNotificacion('¡Cierre de caja guardado exitosamente!', 'success');
    } else {
      alert('¡Cierre de caja guardado exitosamente!');
    }
    cargarResumenCaja();
  } catch (err) {
    console.error(err);
    if (typeof mostrarNotificacion === 'function') mostrarNotificacion(err.message, 'error');
  }
}

function exportarExcelCuadre() {
  const fecha = document.getElementById('cajaFechaFiltro').value || hoyColombiaISO();
  window.open(`/api/caja/exportar-excel?fecha=${fecha}`, '_blank');
}
