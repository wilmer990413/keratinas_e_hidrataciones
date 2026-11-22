let catalogoInversionistas = [];

async function cargarInversionistas() {
  try {
    const res = await fetch('/api/inversionistas');
    if (!res.ok) return;
    catalogoInversionistas = await res.json();
    if (typeof state !== 'undefined') {
      state.inversionistas = catalogoInversionistas;
    }
    renderTablaInversionistas();
    actualizarKPIsInversionistas();
  } catch (err) {
    console.error('Error al cargar inversionistas:', err);
  }
}

function actualizarKPIsInversionistas() {
  const kpiTotal = document.getElementById('kpiTotalInversionistas');
  const kpiProds = document.getElementById('kpiTotalProductosInv');
  const kpiDinero = document.getElementById('kpiTotalInversionDinero');

  if (!kpiTotal) return;

  const activos = catalogoInversionistas.filter(i => i.activo);
  kpiTotal.textContent = activos.length;

  let totalProds = 0;
  let totalDinero = 0;

  activos.forEach(inv => {
    totalProds += (inv.totalProductos || 0);
    totalDinero += (inv.totalInversionStock || 0);
  });

  if (kpiProds) kpiProds.textContent = totalProds;
  if (kpiDinero) kpiDinero.textContent = `$${Math.round(totalDinero).toLocaleString('es-CO')}`;
}

function renderTablaInversionistas() {
  const tbody = document.getElementById('tablaInversionistas');
  const empty = document.getElementById('emptyInversionistas');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!catalogoInversionistas.length) {
    empty?.classList.remove('hidden');
    actualizarKPIsInversionistas();
    return;
  }
  empty?.classList.add('hidden');

  catalogoInversionistas.forEach(inv => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";

    const productosBadges = (inv.productos && inv.productos.length > 0)
      ? inv.productos.map(p => `
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 mr-1 mb-1 border border-gray-200 dark:border-gray-700">
            <i class="fa-solid fa-box text-[9px] text-brand-500"></i> ${escapeHtml(p.nombre)}
            <span class="text-gray-400 font-normal">(${Number(p.stock || 0).toLocaleString('es-CO')} ud)</span>
          </span>
        `).join('')
      : '<span class="text-gray-400 text-[11px] italic">Sin productos asignados</span>';

    tr.innerHTML = `
      <td class="p-4">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 flex items-center justify-center font-bold text-xs shrink-0">
            <i class="fa-solid fa-user-tie"></i>
          </div>
          <div>
            <p class="font-bold text-gray-900 dark:text-white">${escapeHtml(inv.nombre)}</p>
            <p class="text-[10px] text-gray-400">Registrado: ${escapeHtml(inv.fechaRegistro || '—')}</p>
          </div>
        </div>
      </td>
      <td class="p-4">
        <div class="text-xs">
          ${inv.documento ? `<p><span class="text-gray-400">CC:</span> ${escapeHtml(inv.documento)}</p>` : ''}
          ${inv.telefono ? `<p><span class="text-gray-400">Tel:</span> ${escapeHtml(inv.telefono)}</p>` : ''}
          ${!inv.documento && !inv.telefono ? '<span class="text-gray-400">—</span>' : ''}
        </div>
      </td>
      <td class="p-4">
        <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
          ${Number(inv.porcentajeGanancia).toFixed(1)}%
        </span>
      </td>
      <td class="p-4 max-w-xs">
        <div class="flex flex-wrap items-center">
          ${productosBadges}
        </div>
      </td>
      <td class="p-4 font-bold text-emerald-600 dark:text-emerald-400">
        $${Number(inv.totalInversionStock || 0).toLocaleString('es-CO')}
      </td>
      <td class="p-4">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${inv.activo ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}">
          ${inv.activo ? 'ACTIVO' : 'INACTIVO'}
        </span>
      </td>
      <td class="p-4 text-center whitespace-nowrap space-x-1">
        <button onclick="verProductosInversionista('${escapeHtml(inv.id)}')" class="text-purple-600 hover:text-purple-800 dark:text-purple-400 p-1.5 rounded-lg hover:bg-purple-50 dark:hover:bg-purple-950/40 transition" title="Ver productos asociados">
          <i class="fa-solid fa-boxes-stacked"></i>
        </button>
        <button onclick='editarInversionista(${JSON.stringify(inv)})' class="text-brand-600 hover:text-brand-800 dark:text-brand-400 p-1.5 rounded-lg hover:bg-brand-50 dark:hover:bg-brand-950/40 transition" title="Editar inversionista">
          <i class="fa-solid fa-pen"></i>
        </button>
        ${inv.activo ? `
          <button onclick="eliminarInversionista('${escapeHtml(inv.id)}')" class="text-red-400 hover:text-red-600 dark:text-red-400 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40 transition" title="Desactivar inversionista">
            <i class="fa-solid fa-user-slash"></i>
          </button>
        ` : `
          <button onclick='reactivarInversionista(${JSON.stringify(inv)})' class="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 p-1.5 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition" title="Reactivar inversionista">
            <i class="fa-solid fa-user-check"></i>
          </button>
        `}
      </td>
    `;
    tbody.appendChild(tr);
  });

  actualizarKPIsInversionistas();
}

function abrirModalInversionista() {
  document.getElementById('formInversionista')?.reset();
  document.getElementById('invId').value = '';
  document.getElementById('invPorcentajeGanancia').value = '0';
  document.getElementById('modalInvTitulo').textContent = 'Nuevo Inversionista';
  document.getElementById('modalInversionista')?.classList.remove('hidden');
}

function cerrarModalInversionista() {
  document.getElementById('modalInversionista')?.classList.add('hidden');
}

function editarInversionista(inv) {
  document.getElementById('invId').value = inv.id;
  document.getElementById('invNombre').value = inv.nombre || '';
  document.getElementById('invDocumento').value = inv.documento || '';
  document.getElementById('invTelefono').value = inv.telefono || '';
  document.getElementById('invPorcentajeGanancia').value = inv.porcentajeGanancia ?? 0;
  document.getElementById('modalInvTitulo').textContent = 'Editar Inversionista';
  document.getElementById('modalInversionista')?.classList.remove('hidden');
}

async function guardarInversionista(e) {
  e.preventDefault();
  const id = document.getElementById('invId').value.trim();
  const nombre = document.getElementById('invNombre').value.trim();
  const documento = document.getElementById('invDocumento').value.trim();
  const telefono = document.getElementById('invTelefono').value.trim();
  const porcentajeGanancia = parseFloat(document.getElementById('invPorcentajeGanancia').value) || 0;

  if (!nombre) {
    showAlert('El nombre del inversionista es obligatorio.', 'error');
    return;
  }
  if (porcentajeGanancia < 0 || porcentajeGanancia > 100) {
    showAlert('El porcentaje de ganancia debe estar entre 0% y 100%.', 'error');
    return;
  }

  const payload = {
    id: id || undefined,
    nombre,
    documento,
    telefono,
    porcentajeGanancia,
    activo: true
  };

  try {
    const res = await fetch('/api/inversionista', {
      method: id ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) {
      showAlert(result.error || 'No fue posible guardar el inversionista.', 'error');
      return;
    }
    cerrarModalInversionista();
    showAlert(id ? 'Inversionista actualizado correctamente.' : 'Inversionista registrado exitosamente.', 'success');
    await cargarInversionistas();
    if (typeof cargarEstadoBackend === 'function') {
      await cargarEstadoBackend();
    }
  } catch (err) {
    console.error('Error al guardar inversionista:', err);
    showAlert('Ocurrió un error al guardar el inversionista.', 'error');
  }
}

async function eliminarInversionista(id) {
  if (!confirm('¿Desactivar este inversionista? Sus registros históricos de ventas y productos asociados se conservarán.')) return;
  try {
    const res = await fetch(`/api/inversionista/${id}`, { method: 'DELETE' });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) {
      showAlert(result.error || 'No fue posible desactivar el inversionista.', 'error');
      return;
    }
    showAlert('Inversionista desactivado.', 'info');
    await cargarInversionistas();
    if (typeof cargarEstadoBackend === 'function') {
      await cargarEstadoBackend();
    }
  } catch (err) {
    console.error('Error al desactivar inversionista:', err);
    showAlert('Error al procesar la solicitud.', 'error');
  }
}

async function reactivarInversionista(inv) {
  try {
    const res = await fetch('/api/inversionista', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...inv, activo: true })
    });
    if (res.ok) {
      showAlert('Inversionista reactivado exitosamente.', 'success');
      await cargarInversionistas();
      if (typeof cargarEstadoBackend === 'function') {
        await cargarEstadoBackend();
      }
    }
  } catch (err) {
    console.error('Error al reactivar inversionista:', err);
  }
}

function verProductosInversionista(invId) {
  const inv = catalogoInversionistas.find(i => i.id === invId);
  if (!inv) return;

  document.getElementById('modalProdInvTitulo').textContent = `Productos de ${inv.nombre}`;
  document.getElementById('modalProdInvSubtitulo').textContent = `${Number(inv.porcentajeGanancia).toFixed(1)}% de ganancia acordada`;

  const tbody = document.getElementById('tablaDetalleProductosInversionista');
  const empty = document.getElementById('emptyDetalleProductosInv');
  const totalDisplay = document.getElementById('modalProdInvTotal');

  if (!tbody) return;
  tbody.innerHTML = '';

  const prods = inv.productos || [];
  if (prods.length === 0) {
    empty?.classList.remove('hidden');
    if (totalDisplay) totalDisplay.textContent = 'Inversión total en stock: $0';
  } else {
    empty?.classList.add('hidden');
    let totalInv = 0;
    prods.forEach(p => {
      totalInv += (p.inversionTotalStock || 0);
      const tr = document.createElement('tr');
      tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
      tr.innerHTML = `
        <td class="p-3 font-semibold text-gray-900 dark:text-white">${escapeHtml(p.nombre)}</td>
        <td class="p-3 text-center font-bold">${Number(p.stock || 0).toLocaleString('es-CO')} ud</td>
        <td class="p-3 text-gray-600 dark:text-gray-300">$${Number(p.basePrice || 0).toLocaleString('es-CO')}</td>
        <td class="p-3 text-purple-600 font-semibold">$${Number(p.invGain || 0).toLocaleString('es-CO')}</td>
        <td class="p-3 font-bold text-emerald-600 dark:text-emerald-400">$${Number(p.inversionTotalStock || 0).toLocaleString('es-CO')}</td>
      `;
      tbody.appendChild(tr);
    });
    if (totalDisplay) {
      totalDisplay.textContent = `Inversión total en stock: $${Number(totalInv).toLocaleString('es-CO')}`;
    }
  }

  document.getElementById('modalProductosInversionista')?.classList.remove('hidden');
}

function cerrarModalProductosInversionista() {
  document.getElementById('modalProductosInversionista')?.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('tablaInversionistas')) {
    cargarInversionistas();
  }
});
