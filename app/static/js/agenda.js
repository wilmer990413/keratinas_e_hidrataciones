// Agenda de citas: calendario mensual (lunes a domingo) con estados definidos y coloreados por el usuario.
// Depende de main.js (escapeHtml, showAlert).

const AGENDA_MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const AGENDA_DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const AGENDA_PALETA = ['#92D050', '#FFFF00', '#FFA6A6', '#DFA9FF', '#FAE6D8', '#ECF9FF', '#FBCFE8', '#FDBA74', '#93C5FD', '#D1D5DB'];
const AGENDA_COLOR_SIN_ESTADO = '#E5E7EB';

const agenda = { anio: 0, mes: 0, citas: [], estados: [], personas: [], citaAbierta: null, filtroPersona: '', filtroEstado: '' };

// --------------------------------------------------------------- utilidades
function agPad(n) { return String(n).padStart(2, '0'); }
function agFechaStr(y, m, d) { return `${y}-${agPad(m + 1)}-${agPad(d)}`; }   // m = 0..11 (sin zonas horarias)
function agHoy() { const h = new Date(); return agFechaStr(h.getFullYear(), h.getMonth(), h.getDate()); }

function agHora12(hhmm) {
  if (!hhmm) return '';
  const [h, m] = hhmm.split(':').map(Number);
  return `${h % 12 === 0 ? 12 : h % 12}:${agPad(m)} ${h < 12 ? 'a. m.' : 'p. m.'}`;
}

function agColorTexto(hex) {   // texto oscuro o claro según el brillo del fondo
  const n = parseInt(String(hex).slice(1), 16);
  const lum = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return lum > 0.6 ? '#111827' : '#FFFFFF';
}

function agEstado(id) { return agenda.estados.find(e => e.id === id) || null; }

function agFechaLarga(fecha) {
  const [y, m, d] = fecha.split('-').map(Number);
  const dia = AGENDA_DIAS[(new Date(y, m - 1, d).getDay() + 6) % 7];
  return `${dia.charAt(0).toUpperCase() + dia.slice(1)} ${d} de ${AGENDA_MESES[m - 1].toLowerCase()} de ${y}`;
}

async function agFetch(url, opciones) {
  const res = await fetch(url, opciones);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'No se pudo completar la operación.');
  return data;
}
const agJson = (metodo, cuerpo) => ({ method: metodo, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) });

// --------------------------------------------------------------- calendario
async function cargarAgenda() {
  if (!agenda.anio) { const h = new Date(); agenda.anio = h.getFullYear(); agenda.mes = h.getMonth(); }
  document.getElementById('agendaDiasSemana').innerHTML =
    AGENDA_DIAS.map(d => `<div class="px-2">${d}</div>`).join('');

  // La cuadrícula empieza en el lunes de la primera semana y termina en el domingo de la última.
  const primero = new Date(agenda.anio, agenda.mes, 1);
  const inicio = new Date(agenda.anio, agenda.mes, 1 - ((primero.getDay() + 6) % 7));
  const ultimo = new Date(agenda.anio, agenda.mes + 1, 0);
  const fin = new Date(ultimo.getFullYear(), ultimo.getMonth(), ultimo.getDate() + (6 - ((ultimo.getDay() + 6) % 7)));
  const ini = agFechaStr(inicio.getFullYear(), inicio.getMonth(), inicio.getDate());
  const fi = agFechaStr(fin.getFullYear(), fin.getMonth(), fin.getDate());

  const errorEl = document.getElementById('agendaError');
  try {
    const data = await agFetch(`/api/agenda?inicio=${ini}&fin=${fi}`);
    agenda.citas = data.citas; agenda.estados = data.estados; agenda.personas = data.personas || [];
    errorEl.classList.add('hidden');
  } catch (e) {
    errorEl.textContent = e.message; errorEl.classList.remove('hidden');
  }
  document.getElementById('agendaTitulo').textContent = `${AGENDA_MESES[agenda.mes]} ${agenda.anio}`;
  agenda.rango = [inicio, fin];
  renderFiltrosAgenda();
  renderLeyendaAgenda();
  renderGridAgenda(inicio, fin);
}

// --------------------------------------------------------------- filtros (persona y estado)
function nombresResponsables(cita) {
  return (cita.responsables || []).map(r => r.nombre).join(', ');
}

function citasFiltradas() {
  return agenda.citas.filter(c => {
    const p = agenda.filtroPersona, e = agenda.filtroEstado;
    if (p === 'SIN' ? (c.responsables || []).length > 0 : (p && !(c.responsables || []).some(r => r.id === p))) return false;
    if (e === 'SIN' ? c.estadoId : (e && c.estadoId !== e)) return false;
    return true;
  });
}

function renderFiltrosAgenda() {
  // Personas: administradora, auxiliares activas y las inactivas que aparezcan asignadas en estas citas.
  const personas = [...agenda.personas];
  agenda.citas.forEach(c => (c.responsables || []).forEach(r => {
    if (!personas.some(p => p.id === r.id)) personas.push({ id: r.id, nombre: `${r.nombre} (inactiva)` });
  }));
  const selP = document.getElementById('agFiltroPersona');
  const valoresP = ['', 'SIN', ...personas.map(p => p.id)];
  if (!valoresP.includes(agenda.filtroPersona)) agenda.filtroPersona = '';
  selP.innerHTML = '<option value="">Todas las personas</option><option value="SIN">Sin asignar</option>' +
    personas.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.nombre)}</option>`).join('');
  selP.value = agenda.filtroPersona;

  const selE = document.getElementById('agFiltroEstado');
  const valoresE = ['', 'SIN', ...agenda.estados.map(e => e.id)];
  if (!valoresE.includes(agenda.filtroEstado)) agenda.filtroEstado = '';
  selE.innerHTML = '<option value="">Todos los estados</option><option value="SIN">Sin estado</option>' +
    agenda.estados.map(e => `<option value="${escapeHtml(e.id)}">${escapeHtml(e.nombre)}</option>`).join('');
  selE.value = agenda.filtroEstado;
  actualizarResumenFiltros(personas);
}

function actualizarResumenFiltros(personas) {
  const filtradas = citasFiltradas().length;
  const activo = agenda.filtroPersona || agenda.filtroEstado;
  document.getElementById('agFiltroResumen').textContent =
    activo ? `Mostrando ${filtradas} de ${agenda.citas.length} cita(s)` : `${agenda.citas.length} cita(s) en pantalla`;
  const partes = [];
  if (agenda.filtroPersona) {
    const p = agenda.filtroPersona === 'SIN' ? { nombre: 'Sin asignar' } : (personas || agenda.personas).find(x => x.id === agenda.filtroPersona);
    partes.push(`Persona: ${p ? p.nombre : ''}`);
  }
  if (agenda.filtroEstado) {
    const e = agenda.filtroEstado === 'SIN' ? { nombre: 'Sin estado' } : agEstado(agenda.filtroEstado);
    partes.push(`Estado: ${e ? e.nombre : ''}`);
  }
  document.getElementById('agFiltroImpresion').textContent = partes.length ? `Filtros aplicados — ${partes.join(' · ')}` : '';
}

function aplicarFiltrosAgenda() {
  agenda.filtroPersona = document.getElementById('agFiltroPersona').value;
  agenda.filtroEstado = document.getElementById('agFiltroEstado').value;
  cerrarPopoverCita();
  renderFiltrosAgenda();
  renderGridAgenda(...agenda.rango);
}

function limpiarFiltrosAgenda() {
  document.getElementById('agFiltroPersona').value = '';
  document.getElementById('agFiltroEstado').value = '';
  aplicarFiltrosAgenda();
}

// --------------------------------------------------------------- imprimir / PDF del calendario visible
// Se imprime solo la tarjeta del calendario (el CSS de impresión oculta el resto de la pantalla).
function imprimirAgenda() {
  window.print();
}

let agEraOscuro = false;
window.addEventListener('beforeprint', () => {
  const tab = document.getElementById('tab-agenda');
  if (!tab || tab.classList.contains('hidden') || document.body.classList.contains('imprimiendo')) return;
  const html = document.documentElement;
  if (html.classList.contains('imprimiendo-agenda')) return;   // algunos navegadores disparan beforeprint más de una vez
  cerrarPopoverCita();
  agEraOscuro = html.classList.contains('dark');
  html.classList.remove('dark');   // el papel siempre sale en claro
  html.classList.add('imprimiendo-agenda');
});
window.addEventListener('afterprint', () => {
  const html = document.documentElement;
  if (!html.classList.contains('imprimiendo-agenda')) return;
  html.classList.remove('imprimiendo-agenda');
  if (agEraOscuro) html.classList.add('dark');
  agEraOscuro = false;
});

function renderLeyendaAgenda() {
  const el = document.getElementById('agendaLeyenda');
  el.innerHTML = agenda.estados.length
    ? agenda.estados.map(e => `<span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 text-gray-600 dark:text-gray-300">
        <span class="w-3 h-3 rounded-full border border-black/10" style="background:${escapeHtml(e.color)}"></span>${escapeHtml(e.nombre)}</span>`).join('')
    : '<span class="text-gray-400">Aún no hay estados. Créelos en «Estados y colores».</span>';
}

function renderGridAgenda(inicio, fin) {
  const grid = document.getElementById('agendaGrid');
  const hoy = agHoy();
  const porDia = {};
  citasFiltradas().forEach(c => (porDia[c.fecha] = porDia[c.fecha] || []).push(c));

  let html = '';
  for (let d = new Date(inicio); d <= fin; d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
    const f = agFechaStr(d.getFullYear(), d.getMonth(), d.getDate());
    const delMes = d.getMonth() === agenda.mes;
    const citas = (porDia[f] || []).map(c => {
      const est = agEstado(c.estadoId);
      const fondo = est ? est.color : AGENDA_COLOR_SIN_ESTADO;
      const hora = c.hora ? `<span class="font-bold">${agHora12(c.hora)}</span> ` : '';
      const servicio = c.servicio ? ` <span class="opacity-75">· ${escapeHtml(c.servicio)}</span>` : '';
      const quienes = nombresResponsables(c);
      const personas = quienes ? `<span class="block text-[10px] opacity-90"><i class="fa-solid fa-user"></i> ${escapeHtml(quienes)}</span>` : '';
      return `<button type="button" data-cita="${escapeHtml(c.id)}" title="${escapeHtml(c.cliente)}${est ? ' — ' + escapeHtml(est.nombre) : ''}${quienes ? ' — Con: ' + escapeHtml(quienes) : ''}"
        class="agenda-cita block w-full text-left text-[11px] leading-snug rounded-md px-1.5 py-1 hover:brightness-95 hover:ring-2 hover:ring-brand-500 transition"
        style="background:${escapeHtml(fondo)};color:${agColorTexto(fondo)}">${hora}${escapeHtml(c.cliente)}${servicio}${personas}</button>`;
    }).join('');
    html += `<div data-dia="${f}" title="Clic en un espacio vacío para añadir una cita"
      class="agenda-dia min-h-[104px] p-1.5 border-b border-r border-gray-100 dark:border-gray-800 cursor-pointer ${delMes ? '' : 'bg-gray-50/70 dark:bg-gray-900/40'} hover:bg-brand-50/40 dark:hover:bg-gray-800/60 transition">
      <div class="mb-1 ${f === hoy ? 'inline-flex items-center justify-center w-6 h-6 rounded-full bg-brand-600 text-white font-bold' : delMes ? 'text-gray-700 dark:text-gray-200' : 'text-gray-300 dark:text-gray-600'} text-sm">${d.getDate()}</div>
      <div class="space-y-1">${citas}</div></div>`;
  }
  grid.innerHTML = html;
}

document.addEventListener('click', e => {
  const chip = e.target.closest?.('.agenda-cita');
  if (chip) { e.stopPropagation(); abrirPopoverCita(chip); return; }
  const pop = document.getElementById('agendaPopover');
  if (pop && !pop.classList.contains('hidden')) {
    // Con la ventana de una cita abierta, un clic fuera solo la cierra (no abre «nueva cita»).
    if (!pop.contains(e.target)) cerrarPopoverCita();
    return;
  }
  const dia = e.target.closest?.('.agenda-dia');
  if (dia) abrirModalCita(null, dia.dataset.dia);
});

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (!document.getElementById('modalEstados')?.classList.contains('hidden')) cerrarModalEstados();
  else if (!document.getElementById('modalCita')?.classList.contains('hidden')) cerrarModalCita();
  else cerrarPopoverCita();
});

function agendaCambiarMes(delta) {
  const f = new Date(agenda.anio, agenda.mes + delta, 1);
  agenda.anio = f.getFullYear(); agenda.mes = f.getMonth();
  cerrarPopoverCita();
  cargarAgenda();
}

function agendaIrAHoy() {
  const h = new Date(); agenda.anio = h.getFullYear(); agenda.mes = h.getMonth();
  cerrarPopoverCita();
  cargarAgenda();
}

// --------------------------------------------------------------- ventana emergente (editar / eliminar)
function abrirPopoverCita(chip) {
  const cita = agenda.citas.find(c => c.id === chip.dataset.cita);
  if (!cita) return;
  agenda.citaAbierta = cita;
  const est = agEstado(cita.estadoId);
  const pop = document.getElementById('agendaPopover');
  pop.innerHTML = `
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="font-bold text-gray-900 dark:text-white break-words">${escapeHtml(cita.cliente)}</p>
        <p class="text-[11px] text-gray-500 dark:text-gray-400">${agFechaLarga(cita.fecha)}${cita.hora ? ' · ' + agHora12(cita.hora) : ''}</p>
      </div>
      <button type="button" onclick="cerrarPopoverCita()" class="text-gray-400 hover:text-gray-600 dark:hover:text-white" aria-label="Cerrar"><i class="fa-solid fa-xmark"></i></button>
    </div>
    <div class="flex flex-wrap items-center gap-2 text-[11px]">
      <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full font-semibold" style="background:${escapeHtml(est ? est.color : AGENDA_COLOR_SIN_ESTADO)};color:${agColorTexto(est ? est.color : AGENDA_COLOR_SIN_ESTADO)}">${escapeHtml(est ? est.nombre : 'Sin estado')}</span>
      ${cita.servicio ? `<span class="text-gray-600 dark:text-gray-300"><i class="fa-solid fa-spa text-brand-500"></i> ${escapeHtml(cita.servicio)}</span>` : ''}
    </div>
    <p class="text-xs text-gray-700 dark:text-gray-200"><i class="fa-solid fa-user text-brand-500"></i> ${nombresResponsables(cita) ? 'Con: <span class="font-semibold">' + escapeHtml(nombresResponsables(cita)) + '</span>' : '<span class="text-gray-400">Sin persona asignada</span>'}</p>
    ${cita.notas ? `<p class="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 rounded-lg p-2 whitespace-pre-wrap break-words">${escapeHtml(cita.notas)}</p>` : ''}
    <div class="flex gap-2 pt-1">
      <button type="button" onclick="editarCitaAbierta()" class="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-xl transition"><i class="fa-solid fa-pen-to-square"></i> Editar</button>
      <button type="button" onclick="eliminarCitaAbierta()" class="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-950/40 hover:bg-red-100 dark:hover:bg-red-950 text-red-600 text-xs font-semibold rounded-xl transition"><i class="fa-solid fa-trash-can"></i> Eliminar</button>
    </div>`;
  pop.classList.remove('hidden');
  const r = chip.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  pop.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - w - 8))}px`;
  const abajo = r.bottom + 6;
  pop.style.top = `${abajo + h > window.innerHeight - 8 ? Math.max(8, r.top - h - 6) : abajo}px`;
}

function cerrarPopoverCita() {
  document.getElementById('agendaPopover')?.classList.add('hidden');
  agenda.citaAbierta = null;
}

function editarCitaAbierta() {
  const cita = agenda.citaAbierta;
  cerrarPopoverCita();
  if (cita) abrirModalCita(cita);
}

async function eliminarCitaAbierta() {
  const cita = agenda.citaAbierta;
  if (!cita) return;
  if (!confirm(`¿Eliminar la cita de «${cita.cliente}» del ${cita.fecha}${cita.hora ? ' a las ' + agHora12(cita.hora) : ''}?`)) return;
  cerrarPopoverCita();
  try {
    await agFetch(`/api/agenda/citas/${encodeURIComponent(cita.id)}`, { method: 'DELETE' });
    showAlert('Cita eliminada.', 'info');
  } catch (e) { showAlert(e.message, 'error'); }
  cargarAgenda();
}

// --------------------------------------------------------------- modal de cita (añadir / editar)
function llenarSelectEstados(seleccionado) {
  const sel = document.getElementById('citaEstado');
  sel.innerHTML = '<option value="">Sin estado</option>' +
    agenda.estados.map(e => `<option value="${escapeHtml(e.id)}" ${e.id === seleccionado ? 'selected' : ''}>${escapeHtml(e.nombre)}</option>`).join('');
  actualizarPuntoEstado();
}

function llenarResponsables(asignadas, cita) {
  const lista = [...agenda.personas];
  (cita?.responsables || []).forEach(r => { if (!lista.some(p => p.id === r.id)) lista.push({ id: r.id, nombre: `${r.nombre} (inactiva)` }); });
  document.getElementById('citaResponsables').innerHTML = lista.map(p => `
    <label class="flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200 cursor-pointer">
      <input type="checkbox" class="cita-resp accent-pink-600 w-4 h-4" value="${escapeHtml(p.id)}" ${asignadas.includes(p.id) ? 'checked' : ''}>
      <span class="break-words">${escapeHtml(p.nombre)}</span>
    </label>`).join('') || '<span class="text-xs text-gray-400 col-span-2">No hay personas disponibles.</span>';
}

function actualizarPuntoEstado() {
  const est = agEstado(document.getElementById('citaEstado').value);
  document.getElementById('citaEstadoPunto').style.background = est ? est.color : AGENDA_COLOR_SIN_ESTADO;
}

// abrirModalCita()                -> cita nueva (hoy)
// abrirModalCita(null, 'YYYY-MM-DD') -> cita nueva en ese día
// abrirModalCita(cita)            -> edición
function abrirModalCita(cita = null, fecha = null) {
  cerrarPopoverCita();
  document.getElementById('formCita').reset();
  document.getElementById('citaId').value = cita ? cita.id : '';
  document.getElementById('citaTitulo').textContent = cita ? 'Editar cita' : 'Nueva cita';
  document.getElementById('citaFecha').value = cita ? cita.fecha : (fecha || agHoy());
  document.getElementById('citaHora').value = cita?.hora || '';
  document.getElementById('citaCliente').value = cita?.cliente || '';
  document.getElementById('citaServicio').value = cita?.servicio || '';
  document.getElementById('citaNotas').value = cita?.notas || '';
  llenarSelectEstados(cita?.estadoId || '');
  llenarResponsables((cita?.responsables || []).map(r => r.id), cita);
  document.getElementById('citaError').classList.add('hidden');
  document.getElementById('modalCita').classList.remove('hidden');
  document.getElementById('citaCliente').focus();
}

function cerrarModalCita() {
  document.getElementById('modalCita')?.classList.add('hidden');
}

async function guardarCita(e) {
  e.preventDefault();
  const id = document.getElementById('citaId').value;
  const errorEl = document.getElementById('citaError');
  const boton = document.getElementById('citaGuardar');
  const cuerpo = {
    fecha: document.getElementById('citaFecha').value,
    hora: document.getElementById('citaHora').value,
    cliente: document.getElementById('citaCliente').value.trim(),
    servicio: document.getElementById('citaServicio').value.trim(),
    estadoId: document.getElementById('citaEstado').value || null,
    notas: document.getElementById('citaNotas').value.trim(),
    responsables: [...document.querySelectorAll('#citaResponsables .cita-resp:checked')].map(c => c.value),
  };
  errorEl.classList.add('hidden');
  boton.disabled = true;
  try {
    await agFetch(id ? `/api/agenda/citas/${encodeURIComponent(id)}` : '/api/agenda/citas', agJson(id ? 'PUT' : 'POST', cuerpo));
    cerrarModalCita();
    showAlert(id ? 'Cita actualizada.' : 'Cita agregada.', 'success');
    // Si la cita quedó en otro mes, el calendario se mueve a ese mes para que se vea.
    const [y, m] = cuerpo.fecha.split('-').map(Number);
    agenda.anio = y; agenda.mes = m - 1;
    await cargarAgenda();
  } catch (err) {
    errorEl.textContent = err.message; errorEl.classList.remove('hidden');
  } finally { boton.disabled = false; }
}

// --------------------------------------------------------------- estados y colores
function abrirModalEstados() {
  cerrarPopoverCita();
  resetFormEstado();
  renderListaEstados();
  document.getElementById('modalEstados').classList.remove('hidden');
}

function cerrarModalEstados() {
  document.getElementById('modalEstados')?.classList.add('hidden');
  cargarAgenda();   // refresca leyenda y colores de las citas
}

function renderListaEstados() {
  const ul = document.getElementById('estadosLista');
  ul.innerHTML = agenda.estados.length ? agenda.estados.map(e => `
    <li class="flex items-center gap-3 rounded-xl border border-gray-100 dark:border-gray-700 px-3 py-2">
      <span class="w-6 h-6 rounded-full border border-black/10 shrink-0" style="background:${escapeHtml(e.color)}"></span>
      <span class="flex-1 text-sm font-medium text-gray-800 dark:text-gray-100 break-words">${escapeHtml(e.nombre)}</span>
      <span class="text-[10px] text-gray-400">${e.citas} cita(s)</span>
      <button type="button" onclick="editarEstado('${escapeHtml(e.id)}')" class="text-brand-500 hover:text-brand-700 p-1" title="Editar"><i class="fa-solid fa-pen-to-square"></i></button>
      <button type="button" onclick="eliminarEstado('${escapeHtml(e.id)}')" class="text-red-400 hover:text-red-600 p-1" title="Eliminar"><i class="fa-solid fa-trash-can"></i></button>
    </li>`).join('') : '<li class="text-xs text-gray-400">Aún no hay estados. Cree el primero abajo.</li>';
}

function resetFormEstado() {
  document.getElementById('formEstado').reset();
  document.getElementById('estadoId').value = '';
  document.getElementById('estadoColor').value = '#92D050';
  document.getElementById('estadoFormTitulo').textContent = 'Nuevo estado';
  document.getElementById('estadoGuardar').textContent = 'Agregar estado';
  document.getElementById('estadoCancelar').classList.add('hidden');
  document.getElementById('estadoError').classList.add('hidden');
  renderPaletaEstado();
}

function renderPaletaEstado() {
  const actual = document.getElementById('estadoColor').value.toUpperCase();
  document.getElementById('estadoPaleta').innerHTML = AGENDA_PALETA.map(c => `
    <button type="button" onclick="elegirColorEstado('${c}')" aria-label="Color ${c}"
      class="w-7 h-7 rounded-full border-2 ${c === actual ? 'border-gray-900 dark:border-white' : 'border-black/10'}" style="background:${c}"></button>`).join('');
}

function elegirColorEstado(c) {
  document.getElementById('estadoColor').value = c;
  renderPaletaEstado();
}
document.addEventListener('input', e => { if (e.target?.id === 'estadoColor') renderPaletaEstado(); });

function editarEstado(id) {
  const est = agEstado(id);
  if (!est) return;
  document.getElementById('estadoId').value = est.id;
  document.getElementById('estadoNombre').value = est.nombre;
  document.getElementById('estadoColor').value = est.color;
  document.getElementById('estadoFormTitulo').textContent = 'Editar estado';
  document.getElementById('estadoGuardar').textContent = 'Guardar cambios';
  document.getElementById('estadoCancelar').classList.remove('hidden');
  document.getElementById('estadoError').classList.add('hidden');
  renderPaletaEstado();
  document.getElementById('estadoNombre').focus();
}

async function recargarEstados() {
  agenda.estados = await agFetch('/api/agenda/estados');
  renderListaEstados();
}

async function guardarEstado(e) {
  e.preventDefault();
  const id = document.getElementById('estadoId').value;
  const errorEl = document.getElementById('estadoError');
  errorEl.classList.add('hidden');
  const cuerpo = { nombre: document.getElementById('estadoNombre').value.trim(), color: document.getElementById('estadoColor').value };
  try {
    await agFetch(id ? `/api/agenda/estados/${encodeURIComponent(id)}` : '/api/agenda/estados', agJson(id ? 'PUT' : 'POST', cuerpo));
    await recargarEstados();
    resetFormEstado();
  } catch (err) { errorEl.textContent = err.message; errorEl.classList.remove('hidden'); }
}

async function eliminarEstado(id) {
  const est = agEstado(id);
  if (!est || !confirm(`¿Eliminar el estado «${est.nombre}»?`)) return;
  const errorEl = document.getElementById('estadoError');
  errorEl.classList.add('hidden');
  try {
    await agFetch(`/api/agenda/estados/${encodeURIComponent(id)}`, { method: 'DELETE' });
    await recargarEstados();
    if (document.getElementById('estadoId').value === id) resetFormEstado();
  } catch (err) { errorEl.textContent = err.message; errorEl.classList.remove('hidden'); }
}
