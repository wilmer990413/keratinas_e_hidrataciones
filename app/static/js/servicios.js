let auxiliaresDisponibles = [];

window.addEventListener("load", async function() {
  await cargarAuxiliaresParaServicios();
  actualizarFormularioServicio();
});

async function cargarAuxiliaresParaServicios() {
  try {
    const res = await fetch('/api/auxiliares?activos=1');
    if (!res.ok) throw new Error('No fue posible cargar auxiliares');
    auxiliaresDisponibles = await res.json();
  } catch (error) {
    auxiliaresDisponibles = [];
    console.error(error);
  }
}

function actualizarFormularioServicio() {
  const srvTipo = document.getElementById('srvTipo');
  if (!srvTipo) return;
  const tipo = srvTipo.value;
  const boxFijos = document.getElementById('boxValoresFijos');
  const boxHid = document.getElementById('boxHidrataciones');
  const boxKer = document.getElementById('boxKeratinas');
  if (boxFijos) boxFijos.classList.add('hidden');
  if (boxHid) boxHid.classList.add('hidden');
  if (boxKer) boxKer.classList.add('hidden');

  if (['diagnostico', 'despunte', 'capacitacion_virtual', 'capacitacion_presencial'].includes(tipo)) {
    boxFijos?.classList.remove('hidden');
  } else if (tipo === 'hidratacion') {
    boxHid?.classList.remove('hidden');
  } else if (tipo === 'keratina') {
    boxKer?.classList.remove('hidden');
    actualizarKeratinaUI();
    return;
  }
  actualizarAsignacionAuxiliares();
  calcularServicioLive();
}

function actualizarKeratinaUI() {
  const modalidad = document.getElementById('kerModalidad')?.value;
  const boxNumAux = document.getElementById('boxKerNumAux');
  if (!modalidad) return;
  if (modalidad === 'admin') boxNumAux?.classList.add('hidden');
  else if (modalidad === 'admin_aux') boxNumAux?.classList.add('hidden');
  else boxNumAux?.classList.remove('hidden');
  actualizarAsignacionAuxiliares();
  calcularServicioLive();
}

function opcionesAuxiliares(selected = '') {
  const options = auxiliaresDisponibles.map(a => `<option value="${a.id}" ${a.id === selected ? 'selected' : ''}>${escapeHtml(a.nombre)}</option>`).join('');
  return `<option value="">Seleccione auxiliar...</option>${options}`;
}

function actualizarAsignacionAuxiliares() {
  const tipo = document.getElementById('srvTipo')?.value;
  const box = document.getElementById('boxAsignacionAuxiliares');
  const lista = document.getElementById('listaAsignacionAuxiliares');
  if (!box || !lista) return;

  let cantidad = 0;
  if (tipo === 'hidratacion') {
    cantidad = document.getElementById('hidModalidad')?.value === 'normal' ? 1 : 0;
  } else if (tipo === 'keratina') {
    const modalidad = document.getElementById('kerModalidad')?.value;
    if (modalidad === 'admin_aux') cantidad = 1;
    if (modalidad === 'admin_n_aux') cantidad = Math.max(1, Math.min(10, parseInt(document.getElementById('kerNumAux')?.value || '1')));
  }

  if (cantidad === 0) {
    box.classList.add('hidden');
    lista.innerHTML = '';
    actualizarPorcentajeTotal();
    return;
  }
  box.classList.remove('hidden');
  const anteriores = [...lista.querySelectorAll('.aux-row')].map(row => ({
    id: row.querySelector('.aux-id')?.value || '',
    porcentaje: row.querySelector('.aux-pct')?.value || ''
  }));

  lista.innerHTML = '';
  for (let i = 0; i < cantidad; i++) {
    const prev = anteriores[i] || {};
    const row = document.createElement('div');
    row.className = 'aux-row grid grid-cols-1 sm:grid-cols-[1fr_150px_auto] gap-2 items-end';
    row.innerHTML = `
      <div><label class="block text-[11px] text-gray-500 mb-1">Auxiliar ${i + 1}</label><select class="aux-id w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl dark:text-white">${opcionesAuxiliares(prev.id)}</select></div>
      <div><label class="block text-[11px] text-gray-500 mb-1">Porcentaje (%)</label><input type="number" class="aux-pct w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl dark:text-white" min="0.01" max="99.99" step="0.01" value="${prev.porcentaje || ''}" oninput="calcularServicioLive()"></div>
      <div class="text-[11px] text-gray-500 pb-2"><span class="aux-pago-preview">$0</span></div>`;
    lista.appendChild(row);
  }
  lista.querySelectorAll('.aux-id, .aux-pct').forEach(el => el.addEventListener('change', calcularServicioLive));
  actualizarPorcentajeTotal();
}

function obtenerAuxiliaresFormulario() {
  return [...document.querySelectorAll('#listaAsignacionAuxiliares .aux-row')].map(row => ({
    id: row.querySelector('.aux-id')?.value || '',
    porcentaje: parseFloat(row.querySelector('.aux-pct')?.value || '0') || 0
  })).filter(x => x.id);
}

function porcentajeTotalAuxiliares() {
  return obtenerAuxiliaresFormulario().reduce((sum, x) => sum + x.porcentaje, 0);
}

function actualizarPorcentajeTotal() {
  const el = document.getElementById('porcentajeAuxTotal');
  if (el) el.textContent = `${porcentajeTotalAuxiliares().toFixed(2)}%`;
}

function calcularPagoAuxiliares(adminShare) {
  const aux = obtenerAuxiliaresFormulario();
  const pctTotal = aux.reduce((sum, x) => sum + x.porcentaje, 0);
  if (!aux.length || pctTotal <= 0) return { total: 0, base: adminShare, pagos: [] };
  if (pctTotal >= 100) return { total: NaN, base: NaN, pagos: [] };
  const base = adminShare / (1 - pctTotal / 100);
  const pagos = aux.map(x => ({ ...x, pago: base * x.porcentaje / 100 }));
  return { total: pagos.reduce((sum, x) => sum + x.pago, 0), base, pagos };
}

function desgloseServicio() {
  const tipo = document.getElementById('srvTipo').value;
  let total = 0, formulaText = '', adminShare = 0, auxShare = 0, materiaPrimaShare = 0;

  if (['diagnostico', 'despunte', 'capacitacion_virtual', 'capacitacion_presencial'].includes(tipo)) {
    adminShare = parseFloat(document.getElementById('srvValorFijoAdmin').value) || 0;
    total = adminShare;
    formulaText = 'Valor Fijo para Administradora';
  } else if (tipo === 'hidratacion') {
    const modalidad = document.getElementById('hidModalidad').value;
    const insumoExtra = document.getElementById('hidInsumoExtra').value;
    const m1 = parseFloat(document.getElementById('hidMateria1').value) || 0;
    const m2 = parseFloat(document.getElementById('hidMateria2').value) || 0;
    const mExtra = parseFloat(document.getElementById('hidMateriaExtra').value) || 0;
    adminShare = parseFloat(document.getElementById('hidValorAdmin').value) || 0;
    materiaPrimaShare = m1 + m2 + (insumoExtra === 'si' ? mExtra : 0);
    const calc = modalidad === 'normal' ? calcularPagoAuxiliares(adminShare) : { total: 0, base: adminShare, pagos: [] };
    auxShare = calc.total || 0;
    total = materiaPrimaShare + adminShare + auxShare;
    formulaText = `Hidratación: ${modalidad === 'normal' ? 'Auxiliar + ' : ''}Admin + Mat 1 + Mat 2${insumoExtra === 'si' ? ' + Mat Extra' : ''}`;
  } else if (tipo === 'keratina') {
    const modalidad = document.getElementById('kerModalidad').value;
    materiaPrimaShare = parseFloat(document.getElementById('kerMateriaPrima').value) || 0;
    adminShare = parseFloat(document.getElementById('kerValorAdmin').value) || 0;
    const calc = modalidad === 'admin' ? { total: 0 } : calcularPagoAuxiliares(adminShare);
    auxShare = calc.total || 0;
    if (modalidad === 'admin') formulaText = 'Precio Total Admin = Materia Prima + Administradora';
    else if (modalidad === 'admin_aux') formulaText = 'Precio Total Admin + Aux = Materia Prima + Admin + Auxiliar';
    else formulaText = 'Precio Total Admin + N Aux = Materia Prima + Admin + Auxiliares';
    total = materiaPrimaShare + adminShare + auxShare;
  }
  return { total, formulaText, adminShare, auxShare, materiaPrimaShare };
}

// Muestra el campo "Materia Extra ($)" solo cuando se elige "Especial (+ Materia Extra)".
function actualizarMateriaExtra() {
  const select = document.getElementById('hidInsumoExtra');
  const box = document.getElementById('boxMateriaExtra');
  if (!select || !box) return;
  box.classList.toggle('hidden', select.value !== 'si');
}

function calcularServicioLive() {
  const srvTipo = document.getElementById('srvTipo');
  if (!srvTipo) return 0;
  actualizarMateriaExtra();
  const { total, formulaText, adminShare } = desgloseServicio();
  const formulaEl = document.getElementById('srvCalculadoFormula');
  const previewEl = document.getElementById('srvPrecioTotalPreview');
  if (formulaEl) formulaEl.textContent = formulaText;
  if (previewEl) previewEl.textContent = Number.isFinite(total) ? `$${total.toLocaleString('es-CO', {maximumFractionDigits: 0})}` : 'Porcentaje inválido';
  const calc = calcularPagoAuxiliares(adminShare);
  document.querySelectorAll('.aux-row').forEach((row, index) => {
    const pago = calc.pagos[index]?.pago || 0;
    const preview = row.querySelector('.aux-pago-preview');
    if (preview) preview.textContent = `$${pago.toLocaleString('es-CO', {maximumFractionDigits: 0})}`;
  });
  actualizarPorcentajeTotal();
  return total;
}

async function registrarServicio(e) {
  e.preventDefault();
  const cliente = document.getElementById('srvCliente').value.trim();
  const tipo = document.getElementById('srvTipo').value;
  const { total, adminShare, auxShare, materiaPrimaShare } = desgloseServicio();
  const auxiliares = obtenerAuxiliaresFormulario();
  const porcentajeTotal = auxiliares.reduce((sum, x) => sum + x.porcentaje, 0);

  if (auxiliares.length && porcentajeTotal >= 100) {
    showAlert('La suma de los porcentajes de los auxiliares debe ser menor al 100%.', 'error');
    return;
  }
  if (auxiliares.length && auxiliares.some(x => !x.id || x.porcentaje <= 0)) {
    showAlert('Seleccione el auxiliar y registre un porcentaje válido para cada participación.', 'error');
    return;
  }
  if (auxiliares.length > 1 && new Set(auxiliares.map(x => x.id)).size !== auxiliares.length) {
    showAlert('No puede asignar el mismo auxiliar dos veces en el mismo procedimiento.', 'error');
    return;
  }

  const fechaFormateada = fechaHoraColombia();
  const nombreServicioLimpio = tipo.toUpperCase().replaceAll('_', ' ');
  const nuevoServicio = {
    id: 'SRV-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
    fechaHora: fechaFormateada,
    cliente,
    tipoServicio: nombreServicioLimpio,
    total,
    adminShare,
    auxShare,
    materiaPrimaShare,
    invShare: materiaPrimaShare,
    fleteTotal: 0,
    auxiliares
  };

  const res = await fetch('/api/transaccion', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(nuevoServicio) });
  const result = await res.json().catch(() => ({}));
  if (!res.ok) { showAlert(result.error || 'Error al registrar el servicio.', 'error'); return; }

  showAlert(`Servicio guardado para "${cliente}". Total: $${Number(result.total ?? total).toLocaleString('es-CO')}`, 'success');
  document.getElementById('formServicio').reset();
  document.getElementById('kerNumAux').value = 2;
  await cargarAuxiliaresParaServicios();
  actualizarFormularioServicio();
  cargarEstadoBackend();
}

// escapeHtml() está definida en main.js.
