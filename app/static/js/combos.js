// Manejo del estado y CRUD de combos

function calcularTotalComboLive() {
  let totalBase = 0, totalAdmin = 0, totalInv = 0, totalFlete = 0;
  
  document.querySelectorAll('.combo-item-row').forEach(row => {
    const cant = parseFloat(row.querySelector('.combo-prod-cant')?.value) || 0;
    const base = parseFloat(row.querySelector('.combo-prod-base')?.value) || 0;
    const admin = parseFloat(row.querySelector('.combo-prod-admin')?.value) || 0;
    const inv = parseFloat(row.querySelector('.combo-prod-inv')?.value) || 0;
    const flete = parseFloat(row.querySelector('.combo-prod-flete')?.value) || 0;

    totalBase += base * cant;
    totalAdmin += admin * cant;
    totalInv += inv * cant;
    totalFlete += flete * cant;
  });

  const total = totalBase + totalAdmin + totalInv + totalFlete;
  const el = document.getElementById('comboPreviewTotal');
  if (el) el.textContent = `$${total.toLocaleString('es-CO')}`;
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
    combo.items.forEach(it => agregarFilaProductoCombo(it.productoId, it.cantidad, it.costoBase, it.adminGain, it.invGain, it.flete));
  } else {
    agregarFilaProductoCombo();
  }

  calcularTotalComboLive();
  document.getElementById('modalCombo')?.classList.remove('hidden');
}

function cerrarModalCombo() {
  document.getElementById('modalCombo')?.classList.add('hidden');
}

function agregarFilaProductoCombo(selectedProdId = '', cantidad = 1, costoBase = 0, adminGain = 0, invGain = 0, flete = 0) {
  const container = document.getElementById('comboItemsContainer');
  if (!container) return;

  const prods = state.catalogoProductos || [];
  const fila = document.createElement('div');
  fila.className = "combo-item-row grid grid-cols-2 md:grid-cols-12 gap-2 items-center bg-gray-50 dark:bg-gray-800/40 p-2 rounded-xl border border-gray-100 dark:border-gray-700";

  const options = prods.map(p => `
    <option value="${p.id}" ${p.id === selectedProdId ? 'selected' : ''}>
      ${escapeHtml(p.nombre)} (Stock: ${p.stock} ud)
    </option>
  `).join('');

  fila.innerHTML = `
    <div class="col-span-2 md:col-span-3">
      <select class="combo-prod-select w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white">
        <option value="">-- Producto --</option>
        ${options}
      </select>
    </div>
    <div class="md:col-span-1">
      <input type="number" min="1" step="1" value="${cantidad}" class="combo-prod-cant w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Cant" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-2">
      <input type="number" min="0" step="any" value="${costoBase}" class="combo-prod-base w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Costo Base" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-2">
      <input type="number" min="0" step="any" value="${adminGain}" class="combo-prod-admin w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="G. Admin" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-2">
      <input type="number" min="0" step="any" value="${invGain}" class="combo-prod-inv w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="G. Inv" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1">
      <input type="number" min="0" step="any" value="${flete}" class="combo-prod-flete w-full px-2 py-2 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-center dark:text-white" placeholder="Flete" oninput="calcularTotalComboLive()">
    </div>
    <div class="md:col-span-1 flex justify-center">
      <button type="button" onclick="this.closest('.combo-item-row').remove(); calcularTotalComboLive();" class="text-red-400 hover:text-red-600 p-1 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700"><i class="fa-solid fa-trash-can"></i></button>
    </div>
  `;
  container.appendChild(fila);

  // Auto-completar precios si el usuario selecciona un producto nuevo
  const select = fila.querySelector('.combo-prod-select');
  select.addEventListener('change', (e) => {
    const prodId = e.target.value;
    if (!prodId) return;
    const prod = prods.find(p => p.id === prodId);
    if (prod) {
       const unidad = prod.presentaciones?.find(p => p.factor === 1) || prod.presentaciones?.[0];
       if (unidad) {
         fila.querySelector('.combo-prod-base').value = unidad.basePrice;
         fila.querySelector('.combo-prod-admin').value = unidad.adminGain;
         fila.querySelector('.combo-prod-inv').value = unidad.invGain;
         fila.querySelector('.combo-prod-flete').value = unidad.flete;
       }
    }
    calcularTotalComboLive();
  });
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
        ${i.cantidad}x ${escapeHtml(i.productoNombre)}
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