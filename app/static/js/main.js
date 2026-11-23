let state = { serviciosDia: [], ventasProductos: [], carrito: [], catalogoProductos: [], presentaciones: [], auxiliares: [], inversionistas: [], jornada: null };
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

// Nombres cortos de los inversionistas conocidos para columnas dinámicas
const INV_CORTOS = {
  'Leidy Carolina Vanegas Cañon': 'Carolina',
  'Wilmer Rodolfo Castro Ladino': 'Wilmer',
  'Ester Judith Figueredo': 'Ester',
};

function _etiquetaInv(nombre) {
  if (!nombre) return '';
  if (INV_CORTOS[nombre]) return INV_CORTOS[nombre];
  const norm = nombre.toLowerCase();
  if (norm.includes('carolina')) return 'Carolina';
  if (norm.includes('wilmer')) return 'Wilmer';
  if (norm.includes('ester')) return 'Ester';
  return nombre.split(' ')[0] || nombre;
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
  state.inversionistas = data.inversionistas || [];
  state.jornada = data.jornada || null;

  // CORRECCIÓN: Se reconocen como ventas de productos las que empiezan por "Prod:"
  const transacciones = data.transacciones || [];
  state.ventasProductos = transacciones.filter(t => t.tipoServicio && t.tipoServicio.startsWith('Prod:'));
  state.serviciosDia = transacciones.filter(t => !t.tipoServicio || !t.tipoServicio.startsWith('Prod:'));

  renderProductos();
  renderTablaGestionProductos();
  renderTablaPresentaciones();
  if (typeof renderTablaCombos === 'function') renderTablaCombos();
  if (typeof renderTablaInversionistas === 'function') renderTablaInversionistas();
  updateDashboard();
  renderTablaTransacciones();
  if (typeof poblarFiltroInversionistas === 'function') poblarFiltroInversionistas();
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
  let valorVenta = 0, valorInicial = 0, ganancia = 0, flete = 0, gananciaTotal = 0;
  let erikaAdmin = 0, auxTotal = 0, servVentas = 0, prodVentas = 0;

  // Mapa de inversionistas: inicializar con todos los activos registrados a 0
  // para que incluso si no tienen ventas se muestren en el panel
  const invMap = {};
  const activeInvs = (state.inversionistas || []).filter(i => Number(i.activo) === 1);
  activeInvs.forEach(inv => {
    invMap[inv.nombre] = 0;
  });

  // 1. Servicios de peluquería
  state.serviciosDia.forEach(s => {
    const total = Number(s.total || 0);
    const adm = Number(s.adminShare || 0);
    const aux = Number(s.auxShare || 0);
    const matPrima = Number(s.materiaPrimaShare || 0);

    valorVenta += total;
    valorInicial += matPrima;
    const gan = adm + aux;
    ganancia += gan;
    gananciaTotal += gan;
    erikaAdmin += adm;
    auxTotal += aux;
    servVentas += total;
  });

  // 2. Ventas de productos y combos
  state.ventasProductos.forEach(p => {
    const total = Number(p.total || 0);
    const flt = Number(p.fleteTotal || 0);
    const invShare = Number(p.inversionShare || 0);
    // Valor inicial = costo base sin flete
    const vInicial = Math.max(invShare - flt, 0);
    const gan = total - vInicial;
    const ganTot = gan - flt;
    const adm = Number(p.adminShare || 0);

    valorVenta += total;
    valorInicial += vInicial;
    ganancia += gan;
    flete += flt;
    gananciaTotal += ganTot;
    erikaAdmin += adm;
    prodVentas += total;

    // Reparto a inversionistas
    if (p.inversionistas && p.inversionistas.length > 0) {
      p.inversionistas.forEach(inv => {
        if (inv.nombre) {
          invMap[inv.nombre] = (invMap[inv.nombre] || 0) + Number(inv.ganancia || 0);
        }
      });
    } else if (p.gananciaInvShare) {
      const primerInv = activeInvs[0]?.nombre || 'Inversionista';
      invMap[primerInv] = (invMap[primerInv] || 0) + Number(p.gananciaInvShare || 0);
    }
  });

  // Actualizar tarjetas principales
  if (document.getElementById('dashValorVenta')) {
    document.getElementById('dashValorVenta').textContent = `$${valorVenta.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashValorInicial')) {
    document.getElementById('dashValorInicial').textContent = `$${valorInicial.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashGananciaBruta')) {
    document.getElementById('dashGananciaBruta').textContent = `$${ganancia.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashFleteTotal')) {
    document.getElementById('dashFleteTotal').textContent = `$${flete.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashGananciaTotal')) {
    document.getElementById('dashGananciaTotal').textContent = `$${gananciaTotal.toLocaleString('es-CO')}`;
  }

  // Desglose operativo
  if (document.getElementById('dashServiciosVentas')) {
    document.getElementById('dashServiciosVentas').textContent = `$${servVentas.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashProductosVentas')) {
    document.getElementById('dashProductosVentas').textContent = `$${prodVentas.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashAuxTotal')) {
    document.getElementById('dashAuxTotal').textContent = `$${auxTotal.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashFletesTotal')) {
    document.getElementById('dashFletesTotal').textContent = `$${flete.toLocaleString('es-CO')}`;
  }
  if (document.getElementById('dashTotalTx')) {
    document.getElementById('dashTotalTx').textContent = state.serviciosDia.length + state.ventasProductos.length;
  }

  // Lista ordenada de inversionistas
  const listaInvsNombres = Object.keys(invMap).sort((a, b) => _etiquetaInv(a).localeCompare(_etiquetaInv(b)));

  // Renderizar tarjetas dinámicas de Inversionistas y Erika
  const invContainer = document.getElementById('dashInversionistasCards');
  if (invContainer) {
    invContainer.innerHTML = '';
    listaInvsNombres.forEach(nom => {
      const gan = invMap[nom] || 0;
      const card = document.createElement('div');
      card.className = "bg-white dark:bg-cardbg p-4 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm";
      card.innerHTML = `
        <div class="flex justify-between items-start">
          <div>
            <p class="text-[11px] font-bold text-purple-700 dark:text-purple-300 uppercase tracking-wider">${escapeHtml(_etiquetaInv(nom).toUpperCase())}</p>
            <h3 class="text-2xl font-black mt-1 text-purple-700 dark:text-purple-300">$${gan.toLocaleString('es-CO')}</h3>
          </div>
          <div class="p-2.5 bg-purple-50 dark:bg-purple-950/50 text-purple-600 rounded-xl"><i class="fa-solid fa-user-tie text-base"></i></div>
        </div>
        <p class="text-[10px] text-gray-400 mt-2">Inversionista registrado</p>
      `;
      invContainer.appendChild(card);
    });

    const erikaCard = document.createElement('div');
    erikaCard.className = "bg-white dark:bg-cardbg p-4 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm";
    erikaCard.innerHTML = `
      <div class="flex justify-between items-start">
        <div>
          <p class="text-[11px] font-bold text-brand-600 dark:text-brand-400 uppercase tracking-wider">ERIKA</p>
          <h3 class="text-2xl font-black mt-1 text-brand-600 dark:text-brand-400">$${erikaAdmin.toLocaleString('es-CO')}</h3>
        </div>
        <div class="p-2.5 bg-brand-50 dark:bg-brand-950/50 text-brand-600 rounded-xl"><i class="fa-solid fa-user-shield text-base"></i></div>
      </div>
      <p class="text-[10px] text-gray-400 mt-2">Ganancia Administradora</p>
    `;
    invContainer.appendChild(erikaCard);
  }

  // Renderizar tabla horizontal consolidada
  const tblHeaders = document.getElementById('dashTablaHeaders');
  const tblRow = document.getElementById('dashTablaRow');
  if (tblHeaders && tblRow) {
    let thHtml = `
      <th class="p-3.5 whitespace-nowrap bg-gray-50 dark:bg-gray-800/80">VALOR VENTA</th>
      <th class="p-3.5 whitespace-nowrap bg-gray-50 dark:bg-gray-800/80">VALOR INICIAL</th>
      <th class="p-3.5 whitespace-nowrap bg-gray-50 dark:bg-gray-800/80">GANANCIA</th>
      <th class="p-3.5 whitespace-nowrap bg-gray-50 dark:bg-gray-800/80">FLETE</th>
      <th class="p-3.5 whitespace-nowrap bg-gray-50 dark:bg-gray-800/80">GANANCIA TOTAL</th>
    `;
    listaInvsNombres.forEach(nom => {
      thHtml += `<th class="p-3.5 whitespace-nowrap bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 font-black">${escapeHtml(_etiquetaInv(nom).toUpperCase())}</th>`;
    });
    thHtml += `<th class="p-3.5 whitespace-nowrap bg-pink-50 dark:bg-pink-950/40 text-brand-600 dark:text-brand-400 font-black">ERIKA</th>`;
    tblHeaders.innerHTML = thHtml;

    let tdHtml = `
      <td class="p-3.5 text-gray-900 dark:text-white">$${valorVenta.toLocaleString('es-CO')}</td>
      <td class="p-3.5 text-amber-600 dark:text-amber-400">$${valorInicial.toLocaleString('es-CO')}</td>
      <td class="p-3.5 text-green-600 dark:text-green-400">$${ganancia.toLocaleString('es-CO')}</td>
      <td class="p-3.5 text-rose-500">$${flete.toLocaleString('es-CO')}</td>
      <td class="p-3.5 text-emerald-600 dark:text-emerald-400 text-sm">$${gananciaTotal.toLocaleString('es-CO')}</td>
    `;
    listaInvsNombres.forEach(nom => {
      const gan = invMap[nom] || 0;
      tdHtml += `<td class="p-3.5 text-purple-700 dark:text-purple-300">$${gan.toLocaleString('es-CO')}</td>`;
    });
    tdHtml += `<td class="p-3.5 text-brand-600 dark:text-brand-400">$${erikaAdmin.toLocaleString('es-CO')}</td>`;
    tblRow.innerHTML = tdHtml;
  }

  // Gráfica de distribución financiera
  if (financialChartInstance) {
    const labels = ['Erika (Admin)'];
    const data = [erikaAdmin];
    const colors = ['#ec4899'];
    const palette = ['#a855f7', '#8b5cf6', '#6366f1', '#3b82f6', '#14b8a6', '#f59e0b'];
    let cIdx = 0;
    listaInvsNombres.forEach(nom => {
      const gan = invMap[nom] || 0;
      if (gan > 0) {
        labels.push(_etiquetaInv(nom));
        data.push(gan);
        colors.push(palette[cIdx % palette.length]);
        cIdx++;
      }
    });
    if (auxTotal > 0) {
      labels.push('Auxiliares');
      data.push(auxTotal);
      colors.push('#3b82f6');
    }
    financialChartInstance.data.labels = labels;
    financialChartInstance.data.datasets[0].data = data;
    financialChartInstance.data.datasets[0].backgroundColor = colors;
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
  if (!confirm("¿Estás seguro de que deseas eliminar este registro de venta? Las unidades volverán al stock.")) return;
  try {
    const res = await fetch(`/api/transaccion/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (res.ok) {
      showAlert("Registro de venta eliminado correctamente.", "info");
      await cargarEstadoBackend();
      if (!document.getElementById('tab-historico')?.classList.contains('hidden')) {
        cargarHistorico(paginaActual);
      }
    } else {
      const err = await res.json().catch(() => ({}));
      showAlert(err.error || "No fue posible eliminar la venta.", "error");
    }
  } catch (e) {
    console.error(e);
    showAlert("Error al intentar eliminar el registro.", "error");
  }
}

async function reiniciarDia() {
  if (confirm("¿Reiniciar jornada?")) {
    const res = await fetch('/api/reiniciar-jornada', { method: 'POST' });
    if (res.ok) { showAlert("Jornada reiniciada.", "info"); cargarEstadoBackend(); }
  }
}

let paginaActual = 1;
let totalPaginas = 1;

// Registra los inversionistas encontrados en la página actual para encabezados
let _historicoCols = []; // lista de nombres completos de inversionistas detectados

function poblarFiltroInversionistas() {
  const sel = document.getElementById('filtroInversionistaHistorico');
  if (!sel) return;
  const invs = (state.inversionistas || []).filter(i => Number(i.activo) === 1);
  // Mantener opción "Todos" y reconstruir el resto
  sel.innerHTML = '<option value="">Todos</option>';
  invs.sort((a, b) => a.nombre.localeCompare(b.nombre)).forEach(inv => {
    const opt = document.createElement('option');
    opt.value = inv.id;
    opt.textContent = _etiquetaInv(inv.nombre);
    sel.appendChild(opt);
  });
}

async function cargarHistorico(page = 1) {
  paginaActual = page;
  const inicio = document.getElementById('filtroFechaInicio')?.value;
  const fin = document.getElementById('filtroFechaFin')?.value;
  const tipo = document.getElementById('filtroTipoHistorico')?.value || 'todos';
  const busqueda = document.getElementById('filtroBusquedaHistorico')?.value.trim() || '';
  const invId = document.getElementById('filtroInversionistaHistorico')?.value || '';

  let url = `/api/historico-ventas?page=${page}&tipo=${encodeURIComponent(tipo)}`;
  if (busqueda) url += `&q=${encodeURIComponent(busqueda)}`;
  if (inicio) url += `&inicio=${encodeURIComponent(inicio)}`;
  if (fin) url += `&fin=${encodeURIComponent(fin)}`;
  if (invId) url += `&inv_id=${encodeURIComponent(invId)}`;

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

    // Detectar todos los inversionistas presentes en esta página
    const invSet = new Set();
    result.data.forEach(tx => {
      (tx.inversionistas || []).forEach(inv => { if (inv.nombre) invSet.add(inv.nombre); });
    });
    _historicoCols = Array.from(invSet).sort();

    // Actualizar encabezados dinámicos de inversionistas
    const thInv1 = document.getElementById('thInv1');
    const thInv2 = document.getElementById('thInv2');
    if (thInv1) { thInv1.textContent = _historicoCols[0] ? _etiquetaInv(_historicoCols[0]) : ''; thInv1.style.display = _historicoCols[0] ? '' : 'none'; }
    if (thInv2) { thInv2.textContent = _historicoCols[1] ? _etiquetaInv(_historicoCols[1]) : ''; thInv2.style.display = _historicoCols[1] ? '' : 'none'; }

    result.data.forEach(tx => {
      const esProducto = tx.tipo === 'producto';

      // Calcular columnas derivadas
      const valorVenta   = Number(tx.total || 0);
      const flete        = Number(tx.fleteTotal || 0);
      const inversionShare = Number(tx.inversionShare || 0); // costo base puro + flete almacenado como inversion_share
      // Valor Inicial = costo base sin flete = inversion_share - flete_total
      const valorInicial = esProducto ? Math.max(inversionShare - flete, 0) : Number(tx.materiaPrimaShare || 0);
      // Ganancia bruta = Valor Venta - Valor Inicial
      const ganancia     = esProducto ? valorVenta - valorInicial : Number(tx.adminShare || 0) + Number(tx.auxShare || 0);
      // Ganancia Total = Ganancia - Flete
      const gananciaTotal = esProducto ? ganancia - flete : ganancia;
      const adminShare   = Number(tx.adminShare || 0);
      const auxShare     = Number(tx.auxShare || 0);

      // Mapa de ganancia por inversionista
      const invMap = {};
      (tx.inversionistas || []).forEach(inv => {
        invMap[inv.nombre] = Number(inv.ganancia || 0);
      });

      // Celdas dinámicas para cada inversionista
      const tdInv1 = _historicoCols[0] != null
        ? `<td class="p-4 font-semibold text-purple-700 dark:text-purple-300" style="display:${thInv1 && thInv1.style.display !== 'none' ? '' : 'none'}">` +
          (esProducto ? `$${(invMap[_historicoCols[0]] || 0).toLocaleString('es-CO')}` : '—') + `</td>`
        : `<td style="display:none"></td>`;
      const tdInv2 = _historicoCols[1] != null
        ? `<td class="p-4 font-semibold text-purple-700 dark:text-purple-300" style="display:${thInv2 && thInv2.style.display !== 'none' ? '' : 'none'}">` +
          (esProducto ? `$${(invMap[_historicoCols[1]] || 0).toLocaleString('es-CO')}` : '—') + `</td>`
        : `<td style="display:none"></td>`;

      const tr = document.createElement('tr');
      tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
      tr.innerHTML = `
        <td class="p-4 font-mono font-medium text-gray-500 whitespace-nowrap">${escapeHtml(tx.fechaHora)}<br><span class="text-[9px] text-gray-400">${escapeHtml(tx.id)}</span></td>
        <td class="p-4 font-medium text-gray-900 dark:text-white">${escapeHtml(tx.cliente)}</td>
        <td class="p-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${esProducto ? 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300' : 'bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300'}">${esProducto ? 'Producto' : 'Servicio'}</span>
          <div class="mt-1 text-xs">${escapeHtml(tx.tipoServicio)}</div>
          ${tx.auxiliares?.length ? `<div class="mt-1 text-[10px] text-blue-600 dark:text-blue-400">Aux: ${tx.auxiliares.map(a => `${escapeHtml(a.nombre)} (${Number(a.porcentaje).toFixed(2)}%)`).join(', ')}</div>` : ''}
        </td>
        <td class="p-4 font-bold text-gray-900 dark:text-white whitespace-nowrap">$${valorVenta.toLocaleString('es-CO')}</td>
        <td class="p-4 text-orange-600 font-semibold whitespace-nowrap">${esProducto ? `$${valorInicial.toLocaleString('es-CO')}` : '—'}</td>
        <td class="p-4 text-green-600 font-semibold whitespace-nowrap">${esProducto ? `$${ganancia.toLocaleString('es-CO')}` : '—'}</td>
        <td class="p-4 text-red-500 font-semibold whitespace-nowrap">${esProducto ? `$${flete.toLocaleString('es-CO')}` : '—'}</td>
        <td class="p-4 text-emerald-700 font-bold whitespace-nowrap">${esProducto ? `$${gananciaTotal.toLocaleString('es-CO')}` : '—'}</td>
        ${tdInv1}
        ${tdInv2}
        <td class="p-4 text-brand-600 font-semibold whitespace-nowrap">$${adminShare.toLocaleString('es-CO')}</td>
        <td class="p-4 text-blue-600 font-semibold whitespace-nowrap">${auxShare > 0 ? `$${auxShare.toLocaleString('es-CO')}` : '—'}</td>
        <td class="p-4 text-center whitespace-nowrap">
          <button onclick="editarTransaccion('${escapeHtml(tx.id)}')" class="text-brand-600 hover:text-brand-800 dark:text-brand-400 p-1.5 rounded-lg hover:bg-brand-50 dark:hover:bg-brand-950/40 transition" title="Editar venta"><i class="fa-solid fa-pen"></i></button>
          <button onclick="eliminarTransaccion('${escapeHtml(tx.id)}')" class="text-red-400 hover:text-red-600 dark:text-red-400 p-1.5 ml-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40 transition" title="Eliminar registro"><i class="fa-solid fa-trash-can"></i></button>
        </td>`;
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
  const busqueda = document.getElementById('filtroBusquedaHistorico');
  if (busqueda) busqueda.value = '';
  const invSel = document.getElementById('filtroInversionistaHistorico');
  if (invSel) invSel.value = '';
  cargarHistorico(1);
}

function exportarExcel() {
  const inicio = document.getElementById('filtroFechaInicio').value;
  const fin = document.getElementById('filtroFechaFin').value;
  const tipo = document.getElementById('filtroTipoHistorico')?.value || 'todos';
  const busqueda = document.getElementById('filtroBusquedaHistorico')?.value.trim() || '';
  const invId = document.getElementById('filtroInversionistaHistorico')?.value || '';
  let url = `/api/exportar-ventas-excel?tipo=${encodeURIComponent(tipo)}`;
  if (busqueda) url += `&q=${encodeURIComponent(busqueda)}`;
  if (inicio) url += `&inicio=${encodeURIComponent(inicio)}`;
  if (fin) url += `&fin=${encodeURIComponent(fin)}`;
  if (invId) url += `&inv_id=${encodeURIComponent(invId)}`;
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

function productoCatalogoPorId(id) {
  return (state.catalogoProductos || state.productos || []).find(p => String(p.id) === String(id));
}

function presentacionCatalogoPorId(prod, id) {
  return (prod?.presentaciones || []).find(p => String(p.presentacionId) === String(id));
}

function opcionesProductoEdicion(selected = '') {
  const lista = (state.catalogoProductos || state.productos || []).slice().sort((a, b) => String(a.nombre).localeCompare(String(b.nombre), 'es'));
  return `<option value="">Seleccione producto...</option>` + lista.map(p =>
    `<option value="${escapeHtml(p.id)}" ${String(p.id) === String(selected) ? 'selected' : ''}>${escapeHtml(p.nombre)}</option>`
  ).join('');
}

function opcionesPresentacionEdicion(prod, selected = '', combo = false, comboNombre = '') {
  if (combo) return `<option value="combo" selected>${escapeHtml(comboNombre || 'Combo')}</option>`;
  const pres = (prod?.presentaciones || []).filter(p => Number(p.activa ?? 1) === 1);
  return pres.map(p => `<option value="${escapeHtml(p.presentacionId)}" ${String(p.presentacionId) === String(selected) ? 'selected' : ''}>${escapeHtml(p.nombre)} (x${p.factor})</option>`).join('');
}

function precioCatalogoPresentacion(prod, presId) {
  const p = presentacionCatalogoPorId(prod, presId);
  if (!p) return 0;
  return Number(p.basePrice || 0) + Number(p.adminGain || 0) + Number(p.invGain || 0) + Number(p.flete || 0);
}

function componentesCatalogoPresentacion(prod, presId) {
  const p = presentacionCatalogoPorId(prod, presId);
  return {
    base: Number(p?.basePrice || 0),
    admin: Number(p?.adminGain || 0),
    inv: Number(p?.invGain || 0),
    flete: Number(p?.flete || 0)
  };
}

function componentesFilaPrecio(row) {
  return {
    base: Math.max(Number(row.dataset.precioBase || 0), 0),
    admin: Math.max(Number(row.dataset.precioAdmin || 0), 0),
    inv: Math.max(Number(row.dataset.precioInv || 0), 0),
    flete: Math.max(Number(row.dataset.precioFlete || 0), 0)
  };
}

function precioFinalFila(row) {
  const c = componentesFilaPrecio(row);
  return c.base + c.admin + c.inv + c.flete;
}

function mostrarPrecioFila(row) {
  const precioEl = row.querySelector('.edit-prod-precio-display');
  if (precioEl) precioEl.textContent = `$${precioFinalFila(row).toLocaleString('es-CO')}`;
}

function actualizarFilaProductoEdicion(row, usarPrecioCatalogo = false) {
  const prodId = row.querySelector('.edit-prod-id')?.value || '';
  const presId = row.querySelector('.edit-pres-id')?.value || '';
  const prod = productoCatalogoPorId(prodId);
  const pres = presentacionCatalogoPorId(prod, presId);
  const cantidadEl = row.querySelector('.edit-prod-cantidad');
  if (pres) row.dataset.factor = pres.factor;
  const factor = Number(row.dataset.factor || pres?.factor || 1) || 1;

  if (usarPrecioCatalogo && pres) {
    const c = componentesCatalogoPresentacion(prod, presId);
    row.dataset.precioBase = c.base;
    row.dataset.precioAdmin = c.admin;
    row.dataset.precioInv = c.inv;
    row.dataset.precioFlete = c.flete;
  }

  const cantidad = Math.max(parseInt(cantidadEl?.value || '1', 10) || 1, 1);
  const unidades = cantidad * factor;
  const precioUnitario = precioFinalFila(row);
  const subtotal = precioUnitario * unidades;
  const totalEl = row.querySelector('.edit-prod-total');
  const unidadesEl = row.querySelector('.edit-prod-unidades');
  if (totalEl) totalEl.textContent = `$${subtotal.toLocaleString('es-CO')}`;
  if (unidadesEl) unidadesEl.textContent = `${unidades} ud`;
  mostrarPrecioFila(row);
  actualizarResumenEdicion();
}

function cambiarProductoEdicion(select) {
  const row = select.closest('.edit-producto-row');
  const prod = productoCatalogoPorId(select.value);
  const presSelect = row.querySelector('.edit-pres-id');
  presSelect.innerHTML = opcionesPresentacionEdicion(prod);
  const primera = prod?.presentaciones?.find(p => Number(p.activa ?? 1) === 1);
  if (primera) {
    presSelect.value = primera.presentacionId;
    row.dataset.factor = primera.factor;
  }
  actualizarFilaProductoEdicion(row, true);
}

function cambiarPresentacionEdicion(select) {
  const row = select.closest('.edit-producto-row');
  const prod = productoCatalogoPorId(row.querySelector('.edit-prod-id')?.value);
  const pres = presentacionCatalogoPorId(prod, select.value);
  if (pres) row.dataset.factor = pres.factor;
  actualizarFilaProductoEdicion(row, true);
}

function abrirModalEditarPrecioLinea(row) {
  if (!row) return;
  window.filaPrecioEditando = row;
  const c = componentesFilaPrecio(row);
  const prod = productoCatalogoPorId(row.querySelector('.edit-prod-id')?.value);
  const pres = row.querySelector('.edit-pres-id option:checked')?.textContent || '';
  const nombre = prod?.nombre || row.querySelector('.edit-prod-id option:checked')?.textContent || 'Producto';
  document.getElementById('editPrecioLineaNombre').textContent = `${nombre}${pres ? ` · ${pres}` : ''}`;
  document.getElementById('editPrecioBase').value = c.base;
  document.getElementById('editPrecioAdmin').value = c.admin;
  document.getElementById('editPrecioInv').value = c.inv;
  document.getElementById('editPrecioFlete').value = c.flete;
  actualizarPrecioFinalPopup();
  document.getElementById('modalEditarPrecioLinea').classList.remove('hidden');
}

function actualizarPrecioFinalPopup() {
  const base = Math.max(Number(document.getElementById('editPrecioBase')?.value || 0), 0);
  const admin = Math.max(Number(document.getElementById('editPrecioAdmin')?.value || 0), 0);
  const inv = Math.max(Number(document.getElementById('editPrecioInv')?.value || 0), 0);
  const flete = Math.max(Number(document.getElementById('editPrecioFlete')?.value || 0), 0);
  const final = base + admin + inv + flete;
  const el = document.getElementById('editPrecioFinalPopup');
  if (el) el.textContent = `$${final.toLocaleString('es-CO')}`;
  return final;
}

function cerrarModalEditarPrecioLinea() {
  document.getElementById('modalEditarPrecioLinea')?.classList.add('hidden');
  window.filaPrecioEditando = null;
}

function guardarPrecioPopup() {
  const row = window.filaPrecioEditando;
  if (!row) {
    cerrarModalEditarPrecioLinea();
    return;
  }
  const base = Math.max(Number(document.getElementById('editPrecioBase')?.value || 0), 0);
  const admin = Math.max(Number(document.getElementById('editPrecioAdmin')?.value || 0), 0);
  const inv = Math.max(Number(document.getElementById('editPrecioInv')?.value || 0), 0);
  const flete = Math.max(Number(document.getElementById('editPrecioFlete')?.value || 0), 0);
  row.dataset.precioBase = base;
  row.dataset.precioAdmin = admin;
  row.dataset.precioInv = inv;
  row.dataset.precioFlete = flete;
  actualizarFilaProductoEdicion(row, false);
  cerrarModalEditarPrecioLinea();
}

function inicializarComponentesFila(row, item = null, prod = null, presId = '') {
  if (item) {
    const factor = Number(item.factor_presentacion || 1) || 1;
    const unidades = Math.max(Number(item.unidades || 1), 1);
    let base = Number(item.costo_inversion || 0) / unidades;
    let inv = Number(item.ganancia_inversionista || 0) / unidades;
    let admin = Number(item.ganancia_admin || 0);
    let flete = Number(item.flete || 0);
    const pu = Number(item.precio_unitario || 0);
    if (unidades > 1) {
      if (Math.abs((base + inv + (admin / unidades) + (flete / unidades)) - pu) < 1) {
        admin = admin / unidades;
        flete = flete / unidades;
      } else if (admin >= pu) {
        admin = admin / unidades;
        flete = flete / unidades;
      }
    }
    if ((base + admin + inv + flete) <= 0 && pu > 0) {
      admin = Math.max(pu - base - inv - flete, 0);
    }
    row.dataset.precioBase = base;
    row.dataset.precioAdmin = admin;
    row.dataset.precioInv = inv;
    row.dataset.precioFlete = flete;
    return;
  }
  const c = componentesCatalogoPresentacion(prod, presId);
  row.dataset.precioBase = c.base;
  row.dataset.precioAdmin = c.admin;
  row.dataset.precioInv = c.inv;
  row.dataset.precioFlete = c.flete;
}

function agregarProductoEdicion(item = null) {
  const box = document.getElementById('editListaProductos');
  if (!box) return;
  const esCombo = item?.presentacion_id === 'combo';
  const prod = productoCatalogoPorId(item?.producto_id);
  const row = document.createElement('div');
  row.className = 'edit-producto-row rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/40 p-3 space-y-2';
  row.dataset.itemId = item?.id || '';
  row.dataset.factor = Number(item?.factor_presentacion || (esCombo ? 1 : 1));
  row.dataset.combo = esCombo ? '1' : '0';

  const cantidadInicial = item ? Math.max(Number(item.unidades || 1) / Number(item.factor_presentacion || 1), 1) : 1;
  row.innerHTML = `
    <div class="flex items-center justify-between gap-2">
      <div class="text-[10px] font-bold text-gray-500 uppercase tracking-wide">Producto ${esCombo ? '· Combo' : ''}</div>
      <button type="button" onclick="this.closest('.edit-producto-row').remove(); actualizarResumenEdicion()" class="text-red-500 hover:text-red-700 p-1" title="Eliminar producto"><i class="fa-solid fa-trash-can"></i></button>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
      <div class="md:col-span-4">
        <label class="block text-[10px] text-gray-500 mb-1">Producto</label>
        <select class="edit-prod-id w-full px-2.5 py-2 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white" ${esCombo ? 'disabled' : ''} onchange="cambiarProductoEdicion(this)">${esCombo ? `<option value="${escapeHtml(item.producto_id)}" selected>${escapeHtml(item.producto_nombre)}</option>` : opcionesProductoEdicion(item?.producto_id || '')}</select>
      </div>
      <div class="md:col-span-3">
        <label class="block text-[10px] text-gray-500 mb-1">Presentación</label>
        <select class="edit-pres-id w-full px-2.5 py-2 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white" ${esCombo ? 'disabled' : ''} onchange="cambiarPresentacionEdicion(this)">${opcionesPresentacionEdicion(prod, item?.presentacion_id || '', esCombo, item?.presentacion_nombre || '')}</select>
      </div>
      <div class="md:col-span-2">
        <label class="block text-[10px] text-gray-500 mb-1">Cantidad</label>
        <input type="number" min="1" step="1" value="${cantidadInicial}" class="edit-prod-cantidad w-full px-2.5 py-2 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white" oninput="actualizarFilaProductoEdicion(this.closest('.edit-producto-row'))">
      </div>
      <div class="md:col-span-3">
        <label class="block text-[10px] text-gray-500 mb-1">Precio</label>
        <button type="button" onclick="abrirModalEditarPrecioLinea(this.closest('.edit-producto-row'))" class="w-full px-2.5 py-2 text-xs bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/30 dark:hover:bg-brand-950/50 border border-brand-200 dark:border-brand-800 text-brand-700 dark:text-brand-300 rounded-lg font-semibold flex items-center justify-between gap-2">
          <span><i class="fa-solid fa-pen-to-square mr-1"></i> Editar precio</span>
          <strong class="edit-prod-precio-display">$0</strong>
        </button>
      </div>
    </div>
    <div class="flex items-center justify-between text-[10px] text-gray-500 pt-1">
      <span class="edit-prod-unidades">${Number(item?.unidades || 1)} ud</span>
      <strong class="edit-prod-total text-gray-900 dark:text-white">$0</strong>
    </div>`;
  box.appendChild(row);
  inicializarComponentesFila(row, item, prod, item?.presentacion_id || '');
  actualizarFilaProductoEdicion(row, !item);
}

function renderProductosEdicion(items = []) {
  const box = document.getElementById('editListaProductos');
  if (!box) return;
  box.innerHTML = '';
  (items || []).forEach(item => agregarProductoEdicion(item));
  if (!items.length) agregarProductoEdicion();
  actualizarResumenEdicion();
}

function actualizarResumenEdicion() {
  const rows = [...document.querySelectorAll('#editListaProductos .edit-producto-row')];
  let total = 0;
  let admin = 0;
  let inversion = 0;
  let ganInv = 0;
  rows.forEach(row => {
    const cantidad = Math.max(parseInt(row.querySelector('.edit-prod-cantidad')?.value || '1', 10) || 1, 1);
    const factor = Number(row.dataset.factor || 1) || 1;
    const unidades = cantidad * factor;
    const c = componentesFilaPrecio(row);
    total += (c.base + c.admin + c.inv + c.flete) * unidades;
    admin += c.admin * unidades;
    inversion += (c.base + c.flete) * unidades;
    ganInv += c.inv * unidades;
  });
  const fmt = v => `$${Number(v || 0).toLocaleString('es-CO')}`;
  const totalEl = document.getElementById('editResumenTotal');
  const adminEl = document.getElementById('editResumenAdmin');
  const invEl = document.getElementById('editResumenInversion');
  const ganEl = document.getElementById('editResumenGanInv');
  if (totalEl) totalEl.textContent = fmt(total);
  if (adminEl) adminEl.textContent = fmt(admin);
  if (invEl) invEl.textContent = fmt(inversion);
  if (ganEl) ganEl.textContent = fmt(ganInv);
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
      renderProductosEdicion(tx.items || []);
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
    const rows = [...document.querySelectorAll('#editListaProductos .edit-producto-row')];
    if (!rows.length) { showAlert('La venta debe conservar al menos un producto.', 'error'); return; }
    payload.items = rows.map(row => {
      const factor = Number(row.dataset.factor || 1) || 1;
      const c = componentesFilaPrecio(row);
      const precioUnitario = c.base + c.admin + c.inv + c.flete;
      return {
        id: row.dataset.itemId ? Number(row.dataset.itemId) : null,
        productoId: row.querySelector('.edit-prod-id')?.value || '',
        presentacionId: row.querySelector('.edit-pres-id')?.value || '',
        cantidad: Math.max(parseInt(row.querySelector('.edit-prod-cantidad')?.value || '1', 10) || 1, 1),
        precioUnitario: precioUnitario,
        precioBase: c.base,
        gananciaAdmin: c.admin,
        gananciaInv: c.inv,
        flete: c.flete,
        precioFinal: precioUnitario
      };
    });
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
