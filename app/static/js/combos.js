// Manejo del estado y CRUD de combos

function presentacionesComboProducto(prod) {
  return (prod?.presentaciones || []).filter(p => Number(p.activa ?? 1) === 1);
}

function obtenerPresentacionCombo(prod, presId) {
  return presentacionesComboProducto(prod).find(p => String(p.presentacionId) === String(presId)) || null;
}

function calcularTotalComboLive() {
  let totalBase = 0, totalAdmin = 0, totalInv = 0, totalFlete = 0;

  document.querySelectorAll('.combo-item-row').forEach(row => {
    const cant = Math.max(parseInt(row.querySelector('.combo-prod-cant')?.value, 10) || 0, 0);
    totalBase += (parseFloat(row.querySelector('.combo-prod-base')?.value) || 0) * cant;
    totalAdmin += (parseFloat(row.querySelector('.combo-prod-admin')?.value) || 0) * cant;
    totalInv += (parseFloat(row.querySelector('.combo-prod-inv')?.value) || 0) * cant;
    totalFlete += (parseFloat(row.querySelector('.combo-prod-flete')?.value) || 0) * cant;
  });

  const total = totalBase + totalAdmin + totalInv + totalFlete;
  const el = document.getElementById('comboPreviewTotal');
  if (el) el.textContent = `$${total.toLocaleString('es-CO')}`;
}

function actualizarPreciosPresentacionCombo(fila, forzarCatalogo = true) {
  const prodId = fila.querySelector('.combo-prod-select')?.value || '';
  const presId = fila.querySelector('.combo-prod-presentacion')?.value || '';
  const prod = (state.catalogoProductos || []).find(p => String(p.id) === String(prodId));
  const pres = obtenerPresentacionCombo(prod, presId);
  if (!pres) return;

  fila.dataset.factor = pres.factor;
  const labelUnidades = fila.querySelector('.combo-prod-unidades');
  const cantidad = Math.max(parseInt(fila.querySelector('.combo-prod-cant')?.value, 10) || 1, 1);
  if (labelUnidades) labelUnidades.textContent = `${cantidad * Number(pres.factor || 1)} ud`;

  if (forzarCatalogo) {
    fila.querySelector('.combo-prod-base').value = pres.basePrice ?? 0;
    fila.querySelector('.combo-prod-admin').value = pres.adminGain ?? 0;
    fila.querySelector('.combo-prod-inv').value = pres.invGain ?? 0;
    fila.querySelector('.combo-prod-flete').value = pres.flete ?? 0;
  }
  calcularTotalComboLive();
}

function opcionesPresentacionesCombo(prod, selectedId = '') {
  const pres = presentacionesComboProducto(prod);
  if (!pres.length) return '<option value="">-- Sin presentaciones --</option>';
  return '<option value="">-- Presentación --</option>' + pres.map(p =>
    `<option value="${escapeHtml(p.presentacionId)}" ${String(p.presentacionId) === String(selectedId) ? 'selected' : ''}>${escapeHtml(p.nombre)} (x${p.factor})</option>`
  ).join('');
}

function abrirModalCombo(comboId = null) {
  const form = document.getElementById('formComboCRUD');
  if (form) form.reset();

  const container = document.getElementById('comboItemsContainer');
  if (container) container.innerHTML = '';

  const combo = comboId ? (state.combos || []).find(c => c.id === comboId) : null;

  document.getElementById('modalComboTitulo').textContent = combo ? 'Editar Combo' : 'Nuevo Combo';
  document.getElementById('crudComboId').value = combo ? combo.id : '';
  document.getElementById('crudComboNombre').value = combo ? combo.nombre : '';

  if (combo && combo.items?.length) {
    combo.items.forEach(it => agregarFilaProductoCombo(
      it.productoId,
      it.presentacionId,
      it.cantidad,
      it.costoBase,
      it.adminGain,
      it.invGain,
      it.flete
    ));
  } else {
    agregarFilaProductoCombo();
  }

  calcularTotalComboLive();
  document.getElementById('modalCombo')?.classList.remove('hidden');
}

function cerrarModalCombo() {
  document.getElementById('modalCombo')?.classList.add('hidden');
}

function agregarFilaProductoCombo(selectedProdId = '', selectedPresentacionId = '', cantidad = 1, costoBase = null, adminGain = null, invGain = null, flete = null) {
  const container = document.getElementById('comboItemsContainer');
  if (!container) return;

  const prods = state.catalogoProductos || [];
  const fila = document.createElement('div');
  fila.className = "combo-item-row grid grid-cols-2 md:grid-cols-12 gap-2 items-center bg-gray-50 dark:bg-gray-800/40 p-2 rounded-xl border border-gray-100 dark:border-gray-700";

  const options = prods.map(p => `
    <option value="${escapeHtml(p.id)}" ${String(p.id) === String(selectedProdId) ? 'selected' : ''}>
      ${escapeHtml(p.nombre)} (Stock: ${p.stock} ud)
    </option>
  `).join('');

  const prodInicial = prods.find(p => String(p.id) === String(selectedProdId));
  const presIniciales = presentacionesComboProducto(prodInicial);
  const presInicial = selectedPresentacionId
    ? obtenerPresentacionCombo(prodInicial, selectedPresentacionId)
    : presIniciales[0];
  const presId = presInicial?.presentacionId || selectedPresentacionId || '';
  const preciosIniciales = presInicial || {};

  const base = costoBase !== null && costoBase !== undefined ? costoBase : (preciosIniciales.basePrice ?? 0);
  const admin = adminGain !== null && adminGain !== undefined ? adminGain : (preciosIniciales.adminGain ?? 0);
  const inv = invGain !== null && invGain !== undefined ? invGain : (preciosIniciales.invGain ?? 0);
  const fl = flete !== null && flete !== undefined ? flete : (preciosIniciales.flete ?? 0);
  const factor = Number(presInicial?.factor || 1);

  fila.dataset.factor = factor;
  fila.innerHTML = `
    <div class="col-span-2 md:col-span-3">
      <select class="combo-prod-select w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white">
        <option value="">-- Producto --</option>
        ${options}
      </select>
    </div>
    <div class="col-span-2 md:col-span-2">
      <select class="combo-prod-presentacion w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white">
        ${opcionesPresentacionesCombo(prodInicial, presId)}
      </select>
    </div>
    <div class="md:col-span-1">
      <input type="number" min="1" step="1" value="${cantidad}" class="combo-prod-cant w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Cant" oninput="actualizarUnidadesComboFila(this.closest('.combo-item-row')); calcularTotalComboLive()">
      <div class="text-[9px] text-gray-400 text-center mt-1"><span class="combo-prod-unidades">${Number(cantidad || 1) * factor} ud</span></div>
    </div>
    <div class="md:col-span-1">
      <input type="number" min="0" step="any" value="${base}" class="combo-prod-base w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Costo Base" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1">
      <input type="number" min="0" step="any" value="${admin}" class="combo-prod-admin w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="G. Admin" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1">
      <input type="number" min="0" step="any" value="${inv}" class="combo-prod-inv w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="G. Inv" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1">
      <input type="number" min="0" step="any" value="${fl}" class="combo-prod-flete w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Flete" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1 flex justify-center">
      <button type="button" onclick="this.closest('.combo-item-row').remove(); calcularTotalComboLive();" class="text-red-400 hover:text-red-600 p-1 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700"><i class="fa-solid fa-trash-can"></i></button>
    </div>
  `;
  container.appendChild(fila);

  const selectProducto = fila.querySelector('.combo-prod-select');
  const selectPresentacion = fila.querySelector('.combo-prod-presentacion');

  selectProducto.addEventListener('change', () => {
    const prod = prods.find(p => String(p.id) === String(selectProducto.value));
    selectPresentacion.innerHTML = opcionesPresentacionesCombo(prod);
    const primera = presentacionesComboProducto(prod)[0];
    if (primera) {
      selectPresentacion.value = primera.presentacionId;
      actualizarPreciosPresentacionCombo(fila, true);
    }
  });

  selectPresentacion.addEventListener('change', () => actualizarPreciosPresentacionCombo(fila, true));

  // Si se creó una fila vacía, deja los precios en cero hasta seleccionar producto.
  calcularTotalComboLive();
}

function actualizarUnidadesComboFila(fila) {
  const prodId = fila.querySelector('.combo-prod-select')?.value || '';
  const prod = (state.catalogoProductos || []).find(p => String(p.id) === String(prodId));
  const pres = obtenerPresentacionCombo(prod, fila.querySelector('.combo-prod-presentacion')?.value || '');
  const cantidad = Math.max(parseInt(fila.querySelector('.combo-prod-cant')?.value, 10) || 1, 1);
  const unidades = cantidad * Number(pres?.factor || 1);
  const el = fila.querySelector('.combo-prod-unidades');
  if (el) el.textContent = `${unidades} ud`;
}

async function guardarComboCRUD(event) {
  event.preventDefault();
  const id = document.getElementById('crudComboId').value.trim();
  const nombre = document.getElementById('crudComboNombre').value.trim();

  const items = [];
  document.querySelectorAll('.combo-item-row').forEach(row => {
    const prodId = row.querySelector('.combo-prod-select')?.value;
    const cant = parseInt(row.querySelector('.combo-prod-cant')?.value, 10);
    if (prodId && cant > 0) {
      items.push({
        productoId: prodId,
        presentacionId: row.querySelector('.combo-prod-presentacion')?.value || '',
        cantidad: cant,
        costoBase: parseFloat(row.querySelector('.combo-prod-base')?.value) || 0,
        adminGain: parseFloat(row.querySelector('.combo-prod-admin')?.value) || 0,
        invGain: parseFloat(row.querySelector('.combo-prod-inv')?.value) || 0,
        flete: parseFloat(row.querySelector('.combo-prod-flete')?.value) || 0
      });
    }
  });

  if (!nombre) {
    showAlert('El nombre del combo es obligatorio.', 'error');
    return;
  }
  if (items.length === 0) {
    showAlert('Debes seleccionar al menos un producto para el combo.', 'error');
    return;
  }

  const payload = { id: id || undefined, nombre, items };

  try {
    const res = await fetch('/api/combo', {
      method: id ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showAlert(data.error || 'Error al guardar el combo.', 'error');
      return;
    }

    cerrarModalCombo();
    showAlert(id ? 'Combo actualizado.' : 'Combo creado exitosamente.', 'success');
    cargarEstadoBackend();
  } catch (err) {
    showAlert('Error de comunicación con el servidor.', 'error');
  }
}

async function eliminarCombo(id) {
  if (!confirm('¿Deseas desactivar este combo? Ya no estará disponible para la venta.')) return;
  try {
    const res = await fetch(`/api/combo/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showAlert('Combo desactivado.', 'info');
      cargarEstadoBackend();
    } else {
      const data = await res.json().catch(() => ({}));
      showAlert(data.error || 'No fue posible desactivar el combo.', 'error');
    }
  } catch (err) {
    showAlert('Error al conectar con el servidor.', 'error');
  }
}

function renderTablaCombos() {
  const tbody = document.getElementById('tablaCombos');
  const empty = document.getElementById('emptyCombosMsg');
  if (!tbody) return;
  tbody.innerHTML = '';

  const combos = state.combos || [];
  if (combos.length === 0) {
    if (empty) empty.classList.remove('hidden');
    return;
  }
  if (empty) empty.classList.add('hidden');

  combos.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
    const prodsBadges = (c.items || []).map(i => `
      <span class="inline-flex items-center px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 text-[10px] font-medium mr-1 mb-1">
        ${i.cantidad}x ${escapeHtml(i.productoNombre)} · ${escapeHtml(i.presentacionNombre || "Presentación")}
      </span>
    `).join('');

    const sinStock = c.stockDisponible <= 0;
    tr.innerHTML = `
      <td class="p-4 font-bold text-gray-900 dark:text-white whitespace-nowrap">${escapeHtml(c.nombre)}</td>
      <td class="p-4 min-w-[200px]">${prodsBadges || '<span class="text-gray-400">Sin productos</span>'}</td>
      <td class="p-4 whitespace-nowrap">$${c.costoBase.toLocaleString('es-CO')}</td>
      <td class="p-4 text-brand-600 font-semibold whitespace-nowrap">$${c.adminGain.toLocaleString('es-CO')}</td>
      <td class="p-4 text-purple-600 font-semibold whitespace-nowrap">$${c.invGain.toLocaleString('es-CO')}</td>
      <td class="p-4 font-bold text-emerald-600 whitespace-nowrap">$${c.precioTotal.toLocaleString('es-CO')}</td>
      <td class="p-4 font-bold ${sinStock ? 'text-red-500' : 'text-gray-900 dark:text-white'} whitespace-nowrap">
        ${c.stockDisponible} combos
      </td>
      <td class="p-4 text-center space-x-2 whitespace-nowrap">
        <button onclick="abrirModalCombo('${c.id}')" class="text-blue-500 hover:text-blue-700 p-1" title="Editar"><i class="fa-solid fa-pen-to-square"></i></button>
        <button onclick="eliminarCombo('${c.id}')" class="text-red-400 hover:text-red-600 p-1" title="Desactivar"><i class="fa-solid fa-trash-can"></i></button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function cargarCombos() {
  renderTablaCombos();
}