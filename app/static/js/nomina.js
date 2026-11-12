// ---------------------------------------------------------------------------
// Nómina: filtro por fechas + descuentos configurables
// ---------------------------------------------------------------------------
const DESCUENTOS_STORAGE_KEY = 'nominaDescuentos';
let descuentosNomina = [];          // [{uid, concepto, tipo, valor, destino}]
let auxiliaresNomina = [];          // [{id, nombre, activo}]
let uidDescuento = 0;

const fmtMoneda = n => `$${Number(n || 0).toLocaleString('es-CO')}`;

function inicializarFechasNomina() {
  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  const iso = d => d.toISOString().slice(0, 10);
  const a = document.getElementById('nominaInicio'), b = document.getElementById('nominaFin');
  if (a && !a.value) a.value = iso(inicio);
  if (b && !b.value) b.value = iso(hoy);
}

// ----------------------------- Descuentos ----------------------------------
function guardarDescuentosLocal() {
  try {
    localStorage.setItem(DESCUENTOS_STORAGE_KEY, JSON.stringify(
      descuentosNomina.map(({ concepto, tipo, valor, destino }) => ({ concepto, tipo, valor, destino }))
    ));
  } catch (e) { /* el almacenamiento puede no estar disponible */ }
}

function cargarDescuentosLocal() {
  try {
    const guardado = JSON.parse(localStorage.getItem(DESCUENTOS_STORAGE_KEY) || '[]');
    if (Array.isArray(guardado)) {
      descuentosNomina = guardado.map(d => ({
        uid: ++uidDescuento,
        concepto: String(d.concepto || ''),
        tipo: d.tipo === 'porcentaje' ? 'porcentaje' : 'monto',
        valor: d.valor === undefined || d.valor === null ? '' : String(d.valor),
        destino: String(d.destino || 'admin'),
      }));
    }
  } catch (e) { descuentosNomina = []; }
}

function opcionesDestino(seleccionado) {
  const opciones = [
    ['admin', 'Administradora'],
    ['auxiliares', 'Cada auxiliar (todos)'],
    ...auxiliaresNomina.map(a => [`aux:${a.id}`, a.activo ? a.nombre : `${a.nombre} (inactivo)`]),
  ];
  // Si el destino guardado ya no existe en la lista, se conserva visible para no perderlo en silencio.
  if (!opciones.some(([v]) => v === seleccionado)) opciones.push([seleccionado, 'Auxiliar no disponible']);
  return opciones.map(([v, t]) =>
    `<option value="${escapeHtml(v)}" ${v === seleccionado ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('');
}

function renderDescuentos() {
  const cont = document.getElementById('listaDescuentos');
  const vacio = document.getElementById('emptyDescuentos');
  if (!cont) return;
  cont.innerHTML = '';
  vacio.classList.toggle('hidden', descuentosNomina.length > 0);
  const claseInput = 'w-full px-3 py-2 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl dark:text-white';

  descuentosNomina.forEach(d => {
    const fila = document.createElement('div');
    fila.className = 'grid grid-cols-2 md:grid-cols-12 gap-2 items-end';
    fila.innerHTML = `
      <div class="col-span-2 md:col-span-3"><label class="block text-[11px] font-semibold text-gray-600 dark:text-gray-400 mb-1">Concepto</label>
        <input type="text" data-campo="concepto" value="${escapeHtml(d.concepto)}" placeholder="Ej: Seguridad social, anticipo" class="${claseInput}"></div>
      <div class="md:col-span-2"><label class="block text-[11px] font-semibold text-gray-600 dark:text-gray-400 mb-1">Tipo</label>
        <select data-campo="tipo" class="${claseInput}">
          <option value="monto" ${d.tipo === 'monto' ? 'selected' : ''}>Valor fijo ($)</option>
          <option value="porcentaje" ${d.tipo === 'porcentaje' ? 'selected' : ''}>Porcentaje (%)</option>
        </select></div>
      <div class="md:col-span-2"><label class="block text-[11px] font-semibold text-gray-600 dark:text-gray-400 mb-1">Valor</label>
        <input type="number" min="0" step="any" data-campo="valor" value="${escapeHtml(d.valor)}" placeholder="0" class="${claseInput}"></div>
      <div class="col-span-2 md:col-span-4"><label class="block text-[11px] font-semibold text-gray-600 dark:text-gray-400 mb-1">Descontar a</label>
        <select data-campo="destino" class="${claseInput}">${opcionesDestino(d.destino)}</select></div>
      <div class="col-span-2 md:col-span-1 flex md:justify-end">
        <button type="button" data-accion="quitar" title="Quitar descuento" class="px-3 py-2 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-xl transition"><i class="fa-solid fa-trash"></i></button></div>`;

    fila.querySelectorAll('[data-campo]').forEach(el => {
      const evento = el.tagName === 'SELECT' ? 'change' : 'input';
      el.addEventListener(evento, () => { d[el.dataset.campo] = el.value; guardarDescuentosLocal(); });
    });
    fila.querySelector('[data-accion="quitar"]').addEventListener('click', () => quitarDescuento(d.uid));
    cont.appendChild(fila);
  });
}

function agregarDescuento() {
  descuentosNomina.push({ uid: ++uidDescuento, concepto: '', tipo: 'monto', valor: '', destino: 'admin' });
  guardarDescuentosLocal();
  renderDescuentos();
}

function quitarDescuento(uid) {
  descuentosNomina = descuentosNomina.filter(d => d.uid !== uid);
  guardarDescuentosLocal();
  renderDescuentos();
}

function limpiarDescuentos() {
  descuentosNomina = [];
  guardarDescuentosLocal();
  renderDescuentos();
}

// Devuelve la lista lista para enviar, o null si hay un error de captura (ya notificado).
function descuentosParaEnviar() {
  const lista = [];
  for (const d of descuentosNomina) {
    const concepto = d.concepto.trim();
    const valorTxt = String(d.valor).trim();
    if (!concepto && !valorTxt) continue;               // fila vacía: se ignora
    const nombre = concepto || 'sin concepto';
    const valor = Number(valorTxt);
    if (!valorTxt || !Number.isFinite(valor) || valor < 0) {
      showAlert(`Revise el valor del descuento "${nombre}".`, 'error'); return null;
    }
    if (d.tipo === 'porcentaje' && valor > 100) {
      showAlert(`El descuento "${nombre}" no puede superar el 100%.`, 'error'); return null;
    }
    lista.push({ concepto, tipo: d.tipo, valor, destino: d.destino });
  }
  return lista;
}

async function cargarAuxiliaresDescuentos() {
  try {
    const res = await fetch('/api/auxiliares');
    if (res.ok) auxiliaresNomina = await res.json();
  } catch (e) { /* si falla, quedan las opciones generales */ }
  poblarSelectorPersona();
  renderDescuentos();
}

function poblarSelectorPersona() {
  const sel = document.getElementById('nominaPersona');
  if (!sel) return;
  const actual = sel.value || 'admin';
  const opciones = [['admin', 'Administradora'],
    ...auxiliaresNomina.map(a => [`aux:${a.id}`, a.activo ? `Auxiliar · ${a.nombre}` : `Auxiliar · ${a.nombre} (inactivo)`])];
  sel.innerHTML = opciones.map(([v, t]) => `<option value="${escapeHtml(v)}">${escapeHtml(t)}</option>`).join('');
  sel.value = opciones.some(([v]) => v === actual) ? actual : 'admin';
}

function parametrosNomina(inicio, fin, descuentos) {
  const p = new URLSearchParams({ inicio, fin });
  if (descuentos.length) p.set('descuentos', JSON.stringify(descuentos));
  return p.toString();
}

// ------------------------------ Cálculo ------------------------------------
async function cargarNomina() {
  inicializarFechasNomina();
  const inicio = document.getElementById('nominaInicio').value, fin = document.getElementById('nominaFin').value;
  if (!inicio || !fin || inicio > fin) { showAlert('Verifique el rango de fechas de la nómina.', 'error'); return; }

  await cargarAuxiliaresDescuentos();
  const descuentos = descuentosParaEnviar();
  if (descuentos === null) return;

  const res = await fetch(`/api/nomina?${parametrosNomina(inicio, fin, descuentos)}`);
  const data = await res.json();
  if (!res.ok) { showAlert(data.error || 'No fue posible calcular la nómina.', 'error'); return; }

  const set = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
  set('nominaAdminTotal', fmtMoneda(data.administradora.neto));
  set('nominaAdminServicios', `${data.administradora.cantidadServicios} servicios · Bruto ${fmtMoneda(data.administradora.total)} − Desc. ${fmtMoneda(data.administradora.descuentos)}`);
  set('nominaAuxTotal', fmtMoneda(data.totalAuxiliaresNeto));
  set('nominaAuxDetalle', `Bruto ${fmtMoneda(data.totalAuxiliares)} − Desc. ${fmtMoneda(data.totalAuxiliaresDescuentos)}`);
  set('nominaTotal', fmtMoneda(data.totalNeto));
  set('nominaTotalDetalle', `Bruto ${fmtMoneda(data.totalBruto)} − Descuentos ${fmtMoneda(data.totalDescuentos)}`);

  const tbody = document.getElementById('tablaNominaAuxiliares'), empty = document.getElementById('emptyNominaAux');
  tbody.innerHTML = '';
  if (!data.auxiliares.length) empty.classList.remove('hidden');
  else {
    empty.classList.add('hidden');
    data.auxiliares.forEach(a => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td class="p-4 font-semibold">${escapeHtml(a.nombre)}</td><td class="p-4">${a.cantidadServicios}</td>
        <td class="p-4">${fmtMoneda(a.total)}</td>
        <td class="p-4 ${a.descuentos > 0 ? 'text-red-600' : 'text-gray-400'}">${a.descuentos > 0 ? '−' : ''}${fmtMoneda(a.descuentos)}</td>
        <td class="p-4 font-bold text-blue-600">${fmtMoneda(a.neto)}</td>`;
      tbody.appendChild(tr);
    });
  }

  const tdesc = document.getElementById('tablaDescuentosAplicados'), emptyDesc = document.getElementById('emptyDescuentosAplicados');
  tdesc.innerHTML = '';
  if (!data.descuentosAplicados.length) emptyDesc.classList.remove('hidden');
  else {
    emptyDesc.classList.add('hidden');
    data.descuentosAplicados.forEach(d => {
      const tr = document.createElement('tr');
      const valorTxt = d.tipo === 'porcentaje' ? `${Number(d.valor)}%` : fmtMoneda(d.valor);
      tr.innerHTML = `<td class="p-4 font-semibold">${escapeHtml(d.concepto)}</td><td class="p-4">${escapeHtml(d.destinatario)}</td>
        <td class="p-4">${valorTxt}</td><td class="p-4 font-bold text-red-600">−${fmtMoneda(d.monto)}</td>`;
      tdesc.appendChild(tr);
    });
  }

  const detail = document.getElementById('tablaDetalleNomina'), emptyD = document.getElementById('emptyDetalleNomina');
  detail.innerHTML = '';
  if (!data.detalle.length) emptyD.classList.remove('hidden');
  else {
    emptyD.classList.add('hidden');
    data.detalle.forEach(d => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td class="p-4">${d.fechaHora}</td><td class="p-4">${escapeHtml(d.cliente)}</td><td class="p-4">${escapeHtml(d.servicio)}</td><td class="p-4 font-semibold">${escapeHtml(d.auxiliar)}</td><td class="p-4">${Number(d.porcentaje).toFixed(2)}%</td><td class="p-4">${fmtMoneda(d.baseManoObra)}</td><td class="p-4 font-bold text-blue-600">${fmtMoneda(d.pago)}</td>`;
      detail.appendChild(tr);
    });
  }

  if (data.avisos && data.avisos.length) showAlert(data.avisos.join(' '), 'info');
}

function exportarNomina() {
  const inicio = document.getElementById('nominaInicio').value, fin = document.getElementById('nominaFin').value;
  if (!inicio || !fin) { showAlert('Seleccione el rango de fechas antes de exportar.', 'error'); return; }
  const descuentos = descuentosParaEnviar();
  if (descuentos === null) return;
  window.location.href = `/api/exportar-nomina-excel?${parametrosNomina(inicio, fin, descuentos)}`;
}

// ------------------------- Desprendible de nómina ---------------------------
async function generarDesprendible() {
  inicializarFechasNomina();
  const inicio = document.getElementById('nominaInicio').value, fin = document.getElementById('nominaFin').value;
  if (!inicio || !fin || inicio > fin) { showAlert('Verifique el rango de fechas de la nómina.', 'error'); return; }
  const persona = document.getElementById('nominaPersona').value;
  if (!persona) { showAlert('Seleccione a quién desea liquidar la nómina.', 'error'); return; }
  const descuentos = descuentosParaEnviar();
  if (descuentos === null) return;

  const params = new URLSearchParams(parametrosNomina(inicio, fin, descuentos));
  params.set('persona', persona);
  let res, data;
  try {
    res = await fetch(`/api/desprendible-nomina?${params.toString()}`);
    data = await res.json();
  } catch (e) { showAlert('No fue posible generar el desprendible.', 'error'); return; }
  if (!res.ok) { showAlert(data.error || 'No fue posible generar el desprendible.', 'error'); return; }
  if (!data.ingresos.length) {
    showAlert(`${data.empleado.nombre} no tiene ingresos en el periodo seleccionado.`, 'info'); return;
  }
  mostrarDesprendible(data);
  if (data.avisos && data.avisos.length) showAlert(data.avisos.join(' '), 'info');
}

function htmlDesprendible(d) {
  const esAux = d.empleado.cargo === 'Auxiliar';
  const th = 'px-3 py-2 text-left text-[11px] font-bold uppercase text-gray-600 bg-gray-100 border-b border-gray-300';
  const td = 'px-3 py-2 border-b border-gray-200';
  const filasIngresos = d.ingresos.map(i => `<tr>
      <td class="${td}">${escapeHtml(i.fechaHora || i.fecha)}</td>
      <td class="${td}">${escapeHtml(i.cliente)}</td>
      <td class="${td}">${escapeHtml(i.servicio)}</td>
      ${esAux ? `<td class="${td} text-right">${Number(i.porcentaje).toFixed(2)}%</td><td class="${td} text-right">${fmtMoneda(i.baseManoObra)}</td>` : ''}
      <td class="${td} text-right font-semibold">${fmtMoneda(i.valor)}</td></tr>`).join('');
  const colsIngresos = esAux ? 6 : 4;
  const filasDesc = d.descuentos.length
    ? d.descuentos.map(x => `<tr>
        <td class="${td}">${escapeHtml(x.concepto)}</td>
        <td class="${td}">${x.tipo === 'porcentaje' ? `${Number(x.valor)}% del devengado` : 'Valor fijo'}</td>
        <td class="${td} text-right font-semibold text-red-700">−${fmtMoneda(x.monto)}</td></tr>`).join('')
    : `<tr><td class="${td} text-gray-500 italic" colspan="3">Sin descuentos en este periodo.</td></tr>`;
  const dato = (t, v) => `<div><p class="text-[10px] uppercase font-semibold text-gray-500">${t}</p><p class="text-sm font-semibold">${escapeHtml(v || '—')}</p></div>`;

  return `
    <div class="flex items-center justify-between gap-4 pb-4 border-b-2 border-gray-800">
      <div class="flex items-center gap-3">
        <img src="/static/img/logo_erika.png" alt="Logo" class="w-14 h-14 rounded-full object-cover border border-gray-300">
        <div><p class="text-base font-bold leading-tight">${escapeHtml(d.empresa)}</p><p class="text-[11px] text-gray-500">Comprobante de pago de nómina</p></div>
      </div>
      <div class="text-right"><p class="text-lg font-extrabold tracking-wide">DESPRENDIBLE DE NÓMINA</p><p class="text-[11px] text-gray-500">Generado: ${escapeHtml(d.generado)}</p></div>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 py-4 border-b border-gray-300">
      ${dato('Nombre', d.empleado.nombre)}
      ${dato('Cargo', d.empleado.cargo)}
      ${dato('Documento', d.empleado.documento)}
      ${dato('Periodo liquidado', `${d.inicio} a ${d.fin}`)}
    </div>

    <h4 class="mt-5 mb-2 text-xs font-bold uppercase tracking-wide text-gray-700">Ingresos / Devengado <span class="font-normal text-gray-500">(${d.cantidadServicios} ${d.cantidadServicios === 1 ? 'procedimiento' : 'procedimientos'})</span></h4>
    <div class="overflow-x-auto"><table class="w-full text-xs border border-gray-300">
      <thead><tr><th class="${th}">Fecha</th><th class="${th}">Cliente</th><th class="${th}">Procedimiento</th>${esAux ? `<th class="${th} text-right">% Participación</th><th class="${th} text-right">Base mano de obra</th>` : ''}<th class="${th} text-right">Valor</th></tr></thead>
      <tbody>${filasIngresos}</tbody>
      <tfoot><tr class="bg-gray-50"><td class="px-3 py-2 font-bold text-right" colspan="${colsIngresos - 1 + 0}">TOTAL DEVENGADO</td><td class="px-3 py-2 font-bold text-right">${fmtMoneda(d.totalDevengado)}</td></tr></tfoot>
    </table></div>

    <h4 class="mt-5 mb-2 text-xs font-bold uppercase tracking-wide text-gray-700">Descuentos / Deducciones</h4>
    <div class="overflow-x-auto"><table class="w-full text-xs border border-gray-300">
      <thead><tr><th class="${th}">Concepto</th><th class="${th}">Tipo</th><th class="${th} text-right">Valor descontado</th></tr></thead>
      <tbody>${filasDesc}</tbody>
      <tfoot><tr class="bg-gray-50"><td class="px-3 py-2 font-bold text-right" colspan="2">TOTAL DESCUENTOS</td><td class="px-3 py-2 font-bold text-right text-red-700">−${fmtMoneda(d.totalDescuentos)}</td></tr></tfoot>
    </table></div>

    <div class="mt-5 border-2 border-gray-800 rounded-lg overflow-hidden">
      <div class="grid grid-cols-3 text-center text-xs">
        <div class="p-3 border-r border-gray-300"><p class="text-[10px] uppercase font-semibold text-gray-500">Total devengado</p><p class="text-base font-bold">${fmtMoneda(d.totalDevengado)}</p></div>
        <div class="p-3 border-r border-gray-300"><p class="text-[10px] uppercase font-semibold text-gray-500">Total descuentos</p><p class="text-base font-bold text-red-700">−${fmtMoneda(d.totalDescuentos)}</p></div>
        <div class="p-3 bg-gray-900 text-white"><p class="text-[10px] uppercase font-semibold text-gray-300">Neto a pagar</p><p class="text-xl font-extrabold">${fmtMoneda(d.neto)}</p></div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-10 mt-14 text-center text-[11px] text-gray-600">
      <div><div class="border-t border-gray-700 pt-1">Firma de quien paga</div></div>
      <div><div class="border-t border-gray-700 pt-1">Recibí conforme · ${escapeHtml(d.empleado.nombre)}${d.empleado.documento ? ' · C.C. ' + escapeHtml(d.empleado.documento) : ''}</div></div>
    </div>`;
}

function mostrarDesprendible(d) {
  cerrarDesprendible();
  const modal = document.createElement('div');
  modal.id = 'modalDesprendible';
  modal.className = 'fixed inset-0 z-[100] bg-black/60 overflow-y-auto p-4';
  modal.dataset.titulo = `Desprendible_${d.empleado.nombre.replace(/\s+/g, '_')}_${d.inicio}_${d.fin}`;
  modal.innerHTML = `
    <div class="no-imprimir max-w-3xl mx-auto mb-3 flex justify-end gap-2">
      <button type="button" id="btnImprimirDesprendible" class="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow"><i class="fa-solid fa-print"></i> Imprimir / Guardar PDF</button>
      <button type="button" id="btnCerrarDesprendible" class="inline-flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-100 text-gray-800 text-xs font-semibold rounded-xl shadow"><i class="fa-solid fa-xmark"></i> Cerrar</button>
    </div>
    <div id="desprendibleImprimible" class="max-w-3xl mx-auto bg-white text-gray-900 rounded-xl shadow-2xl p-6 sm:p-8">${htmlDesprendible(d)}</div>`;
  document.body.appendChild(modal);
  modal.querySelector('#btnImprimirDesprendible').addEventListener('click', imprimirDesprendible);
  modal.querySelector('#btnCerrarDesprendible').addEventListener('click', cerrarDesprendible);
  modal.addEventListener('click', e => { if (e.target === modal) cerrarDesprendible(); });
  document.addEventListener('keydown', cerrarConEscape);
}

function cerrarConEscape(e) { if (e.key === 'Escape') cerrarDesprendible(); }

function cerrarDesprendible() {
  document.removeEventListener('keydown', cerrarConEscape);
  document.body.classList.remove('imprimiendo');
  const m = document.getElementById('modalDesprendible');
  if (m) m.remove();
}

function imprimirDesprendible() {
  const modal = document.getElementById('modalDesprendible');
  if (!modal) return;
  const tituloOriginal = document.title;
  document.title = modal.dataset.titulo || tituloOriginal;   // nombre sugerido al guardar como PDF
  document.body.classList.add('imprimiendo');
  window.addEventListener('afterprint', () => {
    document.body.classList.remove('imprimiendo');
    document.title = tituloOriginal;
  }, { once: true });
  window.print();
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('nominaInicio')) {
    inicializarFechasNomina();
    cargarDescuentosLocal();
    renderDescuentos();
    cargarNomina();
  }
});
