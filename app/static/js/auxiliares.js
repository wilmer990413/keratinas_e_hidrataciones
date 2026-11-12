let catalogoAuxiliares = [];

async function cargarAuxiliares() {
  const res = await fetch('/api/auxiliares');
  catalogoAuxiliares = await res.json();
  renderTablaAuxiliares();
  if (typeof cargarAuxiliaresParaServicios === 'function') await cargarAuxiliaresParaServicios();
  if (document.getElementById('srvTipo')) actualizarAsignacionAuxiliares();
}

function renderTablaAuxiliares() {
  const tbody = document.getElementById('tablaAuxiliares');
  const empty = document.getElementById('emptyAuxiliares');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (!catalogoAuxiliares.length) { empty?.classList.remove('hidden'); return; }
  empty?.classList.add('hidden');
  catalogoAuxiliares.forEach(a => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="p-4 font-semibold text-gray-900 dark:text-white">${escapeHtml(a.nombre)}</td><td class="p-4">${escapeHtml(a.documento || '-')}</td><td class="p-4">${escapeHtml(a.telefono || '-')}</td><td class="p-4"><span class="px-2 py-1 rounded-full text-[10px] font-bold ${a.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}">${a.activo ? 'ACTIVO' : 'INACTIVO'}</span></td><td class="p-4">${a.fechaIngreso || '-'}</td><td class="p-4 text-center"><button onclick='editarAuxiliar(${JSON.stringify(a)})' class="text-brand-600 hover:text-brand-800 p-1" title="Editar"><i class="fa-solid fa-pen"></i></button>${a.activo ? `<button onclick="eliminarAuxiliar('${a.id}')" class="text-red-500 hover:text-red-700 p-1 ml-2" title="Desactivar"><i class="fa-solid fa-user-slash"></i></button>` : `<button onclick='reactivarAuxiliar(${JSON.stringify(a)})' class="text-emerald-600 hover:text-emerald-800 p-1 ml-2" title="Reactivar"><i class="fa-solid fa-user-check"></i></button>`}</td>`;
    tbody.appendChild(tr);
  });
}

function abrirModalAuxiliar() {
  document.getElementById('formAuxiliar')?.reset();
  document.getElementById('auxId').value = '';
  document.getElementById('modalAuxTitulo').textContent = 'Nuevo Auxiliar';
  document.getElementById('modalAuxiliar').classList.remove('hidden');
}
function cerrarModalAuxiliar() { document.getElementById('modalAuxiliar')?.classList.add('hidden'); }
function editarAuxiliar(a) { document.getElementById('auxId').value=a.id; document.getElementById('auxNombre').value=a.nombre; document.getElementById('auxDocumento').value=a.documento||''; document.getElementById('auxTelefono').value=a.telefono||''; document.getElementById('modalAuxTitulo').textContent='Editar Auxiliar'; document.getElementById('modalAuxiliar').classList.remove('hidden'); }
async function guardarAuxiliar(e) {
  e.preventDefault();
  const id=document.getElementById('auxId').value;
  const payload={id, nombre:document.getElementById('auxNombre').value.trim(), documento:document.getElementById('auxDocumento').value.trim(), telefono:document.getElementById('auxTelefono').value.trim(), activo:true};
  const res=await fetch('/api/auxiliar',{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const result=await res.json().catch(()=>({}));
  if(!res.ok){showAlert(result.error||'No fue posible guardar el auxiliar.','error');return;}
  cerrarModalAuxiliar(); showAlert('Auxiliar guardado correctamente.','success'); await cargarAuxiliares();
}
async function eliminarAuxiliar(id) {
  if(!confirm('¿Desactivar este auxiliar? Sus registros históricos de nómina se conservarán.')) return;
  const res=await fetch(`/api/auxiliar/${id}`,{method:'DELETE'}); const result=await res.json().catch(()=>({}));
  if(!res.ok){showAlert(result.error||'No fue posible desactivar el auxiliar.','error');return;}
  showAlert('Auxiliar desactivado.','info'); await cargarAuxiliares();
}
async function reactivarAuxiliar(a) {
  const res=await fetch('/api/auxiliar',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...a,activo:true})});
  if(res.ok){showAlert('Auxiliar reactivado.','success'); await cargarAuxiliares();}
}

document.addEventListener('DOMContentLoaded',()=>{ if(document.getElementById('tablaAuxiliares')) cargarAuxiliares(); });
