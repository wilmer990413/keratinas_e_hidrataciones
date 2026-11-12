let state = { serviciosDia: [], ventasProductos: [], carrito: [], catalogoProductos: [], presentaciones: [], auxiliares: [], jornada: null };
let financialChartInstance = null;

// Única definición de escapeHtml para toda la aplicación (main.js se carga primero).
// No debe volver a declararse en otros archivos: dos funciones globales con el mismo nombre
// se sobrescriben entre sí, y una que se llame a sí misma por window.escapeHtml entra en bucle.
function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}

function fechaHoraColombia() {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).format(new Date()).replace(' ', ' ');
}

window.onload = function () {
  const dateDisplay = document.getElementById('currentDateDisplay');
  if (dateDisplay) {
    dateDisplay.textContent = new Date().toLocaleDateString('es-CO', {
      timeZone: 'America/Bogota',
      weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
    });
  }
  initChart();
  cargarEstadoBackend();
  actualizarFormularioServicio();
};

async function cargarEstadoBackend() {
  const res = await fetch('/api/estado');
  const data = await res.json();
  state.productos = data.productos || [];
  state.catalogoProductos = data.productos || [];
  state.combos = data.combos || [];
  state.presentaciones = data.presentaciones || [];
  state.auxiliares = data.auxiliares || [];
  state.jornada = data.jornada || null;

  // CORRECCIÓN: Se reconocen como ventas de productos las que empiezan por "Prod:"
  const transacciones = data.transacciones || [];
  state.ventasProductos = transacciones.filter(t => t.tipoServicio && t.tipoServicio.startsWith('Prod:'));
  state.serviciosDia = transacciones.filter(t => !t.tipoServicio || !t.tipoServicio.startsWith('Prod:'));

  renderProductos();
  renderTablaGestionProductos();
  renderTablaPresentaciones();
  if (typeof renderTablaCombos === 'function') renderTablaCombos();
  updateDashboard();
  renderTablaTransacciones();
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(el => {
    el.classList.remove('bg-brand-50', 'text-brand-600', 'dark:bg-brand-900/30', 'dark:text-brand-500');
    el.classList.add('text-gray-600', 'dark:text-gray-400');
  });

  const targetTab = document.getElementById(`tab-${tabId}`);
  const activeNav = document.getElementById(`nav-${tabId}`);
  if (targetTab) targetTab.classList.remove('hidden');
  if (activeNav) {
    activeNav.classList.add('bg-brand-50', 'text-brand-600', 'dark:bg-brand-900/30', 'dark:text-brand-500');
    activeNav.classList.remove('text-gray-600', 'dark:text-gray-400');
  }
}

function toggleDarkMode() {
  document.documentElement.classList.toggle('dark');
}

function showAlert(message, type = 'info') {
  const alert = document.getElementById('notificationAlert');
  const icon = document.getElementById('notifIcon');
  const text = document.getElementById('notifText');
  if (!alert || !text) return;

  alert.className = "mb-6 p-4 rounded-xl shadow-md border flex items-center justify-between transition-all ";
  if (type === 'error') {
    alert.classList.add('bg-red-50', 'border-red-200', 'text-red-800', 'dark:bg-red-950/50', 'dark:text-red-300', 'dark:border-red-900');
    if (icon) icon.className = "fa-solid fa-triangle-exclamation text-red-600";
  } else if (type === 'success') {
    alert.classList.add('bg-emerald-50', 'border-emerald-200', 'text-emerald-800', 'dark:bg-emerald-950/50', 'dark:text-emerald-300', 'dark:border-emerald-900');
    if (icon) icon.className = "fa-solid fa-circle-check text-emerald-600";
  } else {
    alert.classList.add('bg-blue-50', 'border-blue-200', 'text-blue-800', 'dark:bg-blue-950/50', 'dark:text-blue-300', 'dark:border-blue-900');
    if (icon) icon.className = "fa-solid fa-circle-info text-blue-600";
  }

  text.textContent = message;
  alert.classList.remove('hidden');
  setTimeout(() => alert.classList.add('hidden'), 6000);
}

function closeNotification() {
  const alert = document.getElementById('notificationAlert');
  if (alert) alert.classList.add('hidden');
}

function updateDashboard() {
  let total = 0, admin = 0, aux = 0, inv = 0, mat = 0, flete = 0, servVentas = 0, prodVentas = 0;
  let gananciaInv = 0, inversionBase = 0;

  // 1. Servicios de peluquería
  state.serviciosDia.forEach(s => {
    total += Number(s.total || 0);
    admin += Number(s.adminShare || 0);
    aux += Number(s.auxShare || 0);
    
    const matPrima = Number(s.materiaPrimaShare || 0);
    mat += matPrima;
    inv += Number(s.invShare || matPrima);
    inversionBase += matPrima;
    gananciaInv += Math.max(0, Number(s.invShare || 0) - matPrima);
    servVentas += Number(s.total || 0);
  });

  // 2. Ventas de productos y combos
  state.ventasProductos.forEach(p => {
    total += Number(p.total || 0);
    admin += Number(p.adminShare || 0);
    
    const invParte = Number(p.invShare || 0);
    inv += invParte;
    flete += Number(p.fleteTotal || 0);
    prodVentas += Number(p.total || 0);

    // Sumar ganancia del inversionista e inversión registradas
    if (p.gananciaInvShare !== null && p.gananciaInvShare !== undefined) {
      gananciaInv += Number(p.gananciaInvShare);
    } else {
      gananciaInv += Math.max(0, invParte - Number(p.inversionShare || 0));
    }

    if (p.inversionShare !== null && p.inversionShare !== undefined) {
      inversionBase += Number(p.inversionShare);
    } else {
      inversionBase += Math.max(0, invParte - Number(p.gananciaInvShare || 0));
    }
  });

  // Actualizar valores en pantalla
  if (document.getElementById('dashTotalIngresos')) {
    document.getElementById('dashTotalIngresos').textContent = `$${total.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashAdminTotal')) {
    document.getElementById('dashAdminTotal').textContent = `$${admin.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashAuxTotal')) {
    document.getElementById('dashAuxTotal').textContent = `$${aux.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashInvTotal')) {
    document.getElementById('dashInvTotal').textContent = `$${inv.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashServiciosVentas')) {
    document.getElementById('dashServiciosVentas').textContent = `$${servVentas.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashProductosVentas')) {
    document.getElementById('dashProductosVentas').textContent = `$${prodVentas.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashMateriaPrimaTotal')) {
    document.getElementById('dashMateriaPrimaTotal').textContent = `$${mat.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashFletesTotal')) {
    document.getElementById('dashFletesTotal').textContent = `$${flete.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashTotalTx')) {
    document.getElementById('dashTotalTx').textContent = state.serviciosDia.length + state.ventasProductos.length;
  }

  // Gráfica de distribución financiera
  if (financialChartInstance) {
    financialChartInstance.data.datasets[0].data = [admin, aux, inv];
    financialChartInstance.update();
  }
}

function initChart() {
  const canvas = document.getElementById('financialChart');
  if (!canvas) return;
  financialChartInstance = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Ganancia Administradora', 'Pago Auxiliares', 'Inversionista / Costos Insumos'],
      datasets: [{ data: [0, 0, 0], backgroundColor: ['#ec4899', '#3b82f6', '#a855f7'], borderWidth: 0 }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
  });
}

function renderTablaTransacciones() {
  const tbody = document.getElementById('tablaTransacciones');
  const emptyMsg = document.getElementById('emptyTableMsg');
  if (!tbody) return;
  tbody.innerHTML = '';

  const filtro = document.getElementById('filtroCierreTipo')?.value || 'todos';
  let todas = [...state.serviciosDia, ...state.ventasProductos];
  if (filtro === 'servicio') todas = todas.filter(tx => !tx.tipoServicio.startsWith('Prod:'));
  if (filtro === 'producto') todas = todas.filter(tx => tx.tipoServicio.startsWith('Prod:'));
  if (emptyMsg) emptyMsg.classList.toggle('hidden', todas.length > 0);

  todas.forEach(tx => {
    const esVentaProd = tx.tipoServicio.startsWith('Prod:');
    const tr = document.createElement('tr');
    tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
    tr.innerHTML = `
      <td class="p-4 font-mono font-medium text-gray-500">${escapeHtml(tx.fechaHora)}<br><span class="text-[9px] text-gray-400">${escapeHtml(tx.id)}</span></td>
      <td class="p-4 font-medium text-gray-900 dark:text-white">${escapeHtml(tx.cliente)}</td>
      <td class="p-4">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${esVentaProd ? 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300' : 'bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300'}">${escapeHtml(tx.tipoServicio)}</span>
        ${tx.auxiliares?.length ? `<div class="mt-1 text-[10px] text-blue-600">Aux: ${tx.auxiliares.map(a => `${escapeHtml(a.nombre)} (${Number(a.porcentaje).toFixed(2)}%)`).join(', ')}</div>` : ''}
      </td>
      <td class="p-4 font-bold text-gray-900 dark:text-white">$${Number(tx.total).toLocaleString('es-CO')}</td>
      <td class="p-4 text-brand-600 font-semibold">$${Number(tx.adminShare).toLocaleString('es-CO')}</td>
      <td class="p-4 text-blue-600 font-semibold">$${Number(tx.auxShare).toLocaleString('es-CO')}</td>
      ${celdasInversionista(tx)}
      <td class="p-4 text-center whitespace-nowrap">
        <button onclick="editarTransaccion('${escapeHtml(tx.id)}')" class="text-brand-600 hover:text-brand-800 p-1" title="Editar venta"><i class="fa-solid fa-pen"></i></button>
        <button onclick="eliminarTransaccion('${escapeHtml(tx.id)}')" class="text-red-400 hover:text-red-600 p-1 ml-1" title="Eliminar registro"><i class="fa-solid fa-trash-can"></i></button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function celdasInversionista(tx) {
  const money = n => `$${Number(n || 0).toLocaleString('es-CO')}`;
  if (tx.gananciaInvShare === null || tx.gananciaInvShare === undefined || tx.inversionShare === null || tx.inversionShare === undefined) {
    const titulo = `Registro anterior sin desglose (total combinado: ${money(tx.invShare)})`;
    return `<td class="p-4 text-gray-400" title="${titulo}">—</td><td class="p-4 text-gray-400" title="${titulo}">—</td>`;
  }
  return `<td class="p-4 text-purple-600 font-semibold">${money(tx.gananciaInvShare)}</td><td class="p-4 text-amber-600 font-semibold">${money(tx.inversionShare)}</td>`;
}

async function eliminarTransaccion(id) {
  const res = await fetch(`/api/transaccion/${id}`, { method: 'DELETE' });
  if (res.ok) { showAlert("Eliminado.", "info"); cargarEstadoBackend(); }
}

async function reiniciarDia() {
  if (confirm("¿Reiniciar jornada?")) {
    const res = await fetch('/api/reiniciar-jornada', { method: 'POST' });
    if (res.ok) { showAlert("Jornada reiniciada.", "info"); cargarEstadoBackend(); }
  }
}

let paginaActual = 1;
let totalPaginas = 1;

async function cargarHistorico(page = 1) {
  paginaActual = page;
  const inicio = document.getElementById('filtroFechaInicio')?.value;
  const fin = document.getElementById('filtroFechaFin')?.value;
  const tipo = document.getElementById('filtroTipoHistorico')?.value || 'todos';

  let url = `/api/historico-ventas?page=${page}&tipo=${encodeURIComponent(tipo)}`;
  if (inicio) url += `&inicio=${encodeURIComponent(inicio)}`;
  if (fin) url += `&fin=${encodeURIComponent(fin)}`;

  const res = await fetch(url, { cache: 'no-store' });
  const result = await res.json();
  const tbody = document.getElementById('tablaHistoricoVentas');
  const emptyMsg = document.getElementById('emptyHistoricoMsg');
  if (!tbody) return;

  tbody.innerHTML = '';
  totalPaginas = result.total_pages || 1;
  if (result.data.length === 0) {
    emptyMsg.classList.remove('hidden');
  } else {
    emptyMsg.classList.add('hidden');
    result.data.forEach(tx => {
      const esProducto = tx.tipo === 'producto';
      const tr = document.createElement('tr');
      tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
      tr.innerHTML = `
        <td class="p-4 font-mono font-medium text-gray-500">${escapeHtml(tx.fechaHora)}</td>
        <td class="p-4 font-medium text-gray-900 dark:text-white">${escapeHtml(tx.cliente)}</td>
        <td class="p-4"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${esProducto ? 'bg-purple-100 text-purple-700' : 'bg-brand-100 text-brand-700'}">${esProducto ? 'Producto' : 'Servicio'}</span><div class="mt-1">${escapeHtml(tx.tipoServicio)}</div></td>
        <td class="p-4 font-bold text-gray-900 dark:text-white">$${Number(tx.total).toLocaleString('es-CO')}</td>
        <td class="p-4 text-brand-600 font-semibold">$${Number(tx.adminShare).toLocaleString('es-CO')}</td>
        <td class="p-4 text-blue-600 font-semibold">$${Number(tx.auxShare).toLocaleString('es-CO')}</td>
        <td class="p-4 text-purple-600 font-semibold">$${Number(tx.invShare).toLocaleString('es-CO')}</td>`;
      tbody.appendChild(tr);
    });
  }
  document.getElementById('paginacionInfo').textContent = `Página ${paginaActual} de ${totalPaginas} (Total registros: ${result.total})`;
  document.getElementById('btnAnterior').disabled = paginaActual <= 1;
  document.getElementById('btnSiguiente').disabled = paginaActual >= totalPaginas;
}

function cambiarPagina(direccion) {
  const nuevaPagina = paginaActual + direccion;
  if (nuevaPagina >= 1 && nuevaPagina <= totalPaginas) {
    cargarHistorico(nuevaPagina);
  }
}

function limpiarFiltros() {
  document.getElementById('filtroFechaInicio').value = '';
  document.getElementById('filtroFechaFin').value = '';
  document.getElementById('filtroTipoHistorico').value = 'todos';
  cargarHistorico(1);
}

function exportarExcel() {
  const inicio = document.getElementById('filtroFechaInicio').value;
  const fin = document.getElementById('filtroFechaFin').value;
  const tipo = document.getElementById('filtroTipoHistorico')?.value || 'todos';
  let url = `/api/exportar-ventas-excel?tipo=${encodeURIComponent(tipo)}`;
  if (inicio) url += `&inicio=${encodeURIComponent(inicio)}`;
  if (fin) url += `&fin=${encodeURIComponent(fin)}`;
  window.location.href = url;
}

function exportarJornadaExcel() {
  const tipo = document.getElementById('filtroCierreTipo')?.value || 'todos';
  window.location.href = `/api/exportar-ventas-excel?jornada=actual&tipo=${encodeURIComponent(tipo)}`;
}

function cerrarModalEditarTransaccion() {
  document.getElementById('modalEditarTransaccion')?.classList.add('hidden');
}

function fechaParaInput(valor) {
  if (!valor) return '';
  return String(valor).replace(' ', 'T').slice(0, 16);
}

function opcionesAuxiliarEdicion(selected = '') {
  const lista = (state.auxiliares || []).filter(a => Number(a.activo) === 1);
  return `<option value="">Seleccione auxiliar...</option>` + lista.map(a => `<option value="${escapeHtml(a.id)}" ${a.id === selected ? 'selected' : ''}>${escapeHtml(a.nombre)}</option>`).join('');
}

function renderAuxiliaresEdicion(auxiliares = []) {
  const box = document.getElementById('editListaAuxiliares');
  if (!box) return;
  box.innerHTML = '';
  auxiliares.forEach(a => agregarAuxiliarEdicion(a.id, a.porcentaje));
}

function agregarAuxiliarEdicion(id = '', porcentaje = '') {
  const box = document.getElementById('editListaAuxiliares');
  if (!box) return;
  const row = document.createElement('div');
  row.className = 'edit-aux-row grid grid-cols-[1fr_120px_auto] gap-2 items-end';
  row.innerHTML = `<select class="edit-aux-id w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl dark:text-white">${opcionesAuxiliarEdicion(id)}</select><input type="number" min="0.01" max="99.99" step="0.01" value="${porcentaje}" class="edit-aux-pct w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl dark:text-white" placeholder="%"><button type="button" onclick="this.closest('.edit-aux-row').remove()" class="text-red-500 hover:text-red-700 p-2" title="Quitar"><i class="fa-solid fa-trash-can"></i></button>`;
  box.appendChild(row);
}

async function editarTransaccion(id) {
  try {
    const res = await fetch(`/api/transaccion/${encodeURIComponent(id)}`, { cache: 'no-store' });
    const tx = await res.json();
    if (!res.ok) { showAlert(tx.error || 'No fue posible cargar la venta.', 'error'); return; }
    document.getElementById('editTxId').value = tx.id;
    document.getElementById('editTxCliente').value = tx.cliente || '';
    document.getElementById('editTxFecha').value = fechaParaInput(tx.fechaHora);
    document.getElementById('editTxEsProducto').value = tx.tipo === 'producto' ? '1' : '0';
    document.getElementById('editTxTipo').textContent = `${tx.tipo === 'producto' ? 'Venta de producto' : 'Servicio'} · ${tx.tipoServicio}`;

    const productoBox = document.getElementById('editProductoCampos');
    const servicioBox = document.getElementById('editServicioCampos');
    if (tx.tipo === 'producto') {
      productoBox.classList.remove('hidden'); servicioBox.classList.add('hidden');
      document.getElementById('editTxAdmin').value = Number(tx.adminShare || 0);
      document.getElementById('editTxInversion').value = Number(tx.inversionShare ?? Math.max((tx.invShare || 0) - (tx.gananciaInvShare || 0), 0));
      document.getElementById('editTxGanInv').value = Number(tx.gananciaInvShare ?? 0);
      document.getElementById('editTxFlete').value = Number(tx.fleteTotal || 0);
      document.getElementById('editTxDetalleProducto').textContent = tx.items?.length ? tx.items.map(i => `${i.unidades} ud · ${i.presentacion_nombre || i.presentacionNombre || 'Presentación'} · ${i.producto_nombre || i.productoNombre}`).join(' | ') : tx.tipoServicio;
    } else {
      productoBox.classList.add('hidden'); servicioBox.classList.remove('hidden');
      document.getElementById('editSrvAdmin').value = Number(tx.adminShare || 0);
      document.getElementById('editSrvMateria').value = Number(tx.materiaPrimaShare || 0);
      renderAuxiliaresEdicion(tx.auxiliares || []);
    }
    document.getElementById('modalEditarTransaccion').classList.remove('hidden');
  } catch (e) {
    console.error(e); showAlert('No fue posible cargar la venta.', 'error');
  }
}

async function guardarEdicionTransaccion(event) {
  event.preventDefault();
  const id = document.getElementById('editTxId').value;
  const esProducto = document.getElementById('editTxEsProducto').value === '1';
  const payload = { cliente: document.getElementById('editTxCliente').value.trim(), fechaHora: document.getElementById('editTxFecha').value };
  if (!payload.cliente || !payload.fechaHora) { showAlert('Cliente y fecha/hora son obligatorios.', 'error'); return; }

  if (esProducto) {
    payload.adminShare = Number(document.getElementById('editTxAdmin').value) || 0;
    payload.inversionShare = Number(document.getElementById('editTxInversion').value) || 0;
    payload.gananciaInvShare = Number(document.getElementById('editTxGanInv').value) || 0;
    payload.fleteTotal = Number(document.getElementById('editTxFlete').value) || 0;
  } else {
    payload.adminShare = Number(document.getElementById('editSrvAdmin').value) || 0;
    payload.materiaPrimaShare = Number(document.getElementById('editSrvMateria').value) || 0;
    payload.auxiliares = [...document.querySelectorAll('#editListaAuxiliares .edit-aux-row')].map(row => ({ id: row.querySelector('.edit-aux-id')?.value || '', porcentaje: Number(row.querySelector('.edit-aux-pct')?.value) || 0 })).filter(x => x.id);
  }

  try {
    const res = await fetch(`/api/transaccion/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) { showAlert(result.error || 'No fue posible actualizar la venta.', 'error'); return; }
    cerrarModalEditarTransaccion();
    showAlert('Venta actualizada correctamente.', 'success');
    await cargarEstadoBackend();
    if (!document.getElementById('tab-historico')?.classList.contains('hidden')) cargarHistorico(paginaActual);
  } catch (e) {
    console.error(e); showAlert('No fue posible actualizar la venta.', 'error');
  }
}
