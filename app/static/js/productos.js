// =============================================================================
// MODULO DE PRODUCTOS, PRESENTACIONES Y COMBOS
// =============================================================================

// escapeHtml() está definida en main.js.

function presentacionesActivas() {
  return (state.presentaciones || []).filter(p => Number(p.activa) === 1);
}

function obtenerProducto(productId) {
  return (state.catalogoProductos || []).find(p => p.id === productId);
}

function obtenerCombo(comboId) {
  return (state.combos || []).find(c => c.id === comboId);
}

function obtenerPresentacionProducto(prod, presentationId) {
  return (prod?.presentaciones || []).find(p => p.presentacionId === presentationId)
      || (prod?.presentaciones || [])[0];
}

// Calcula cuántas unidades de un producto están reservadas en el carrito
// (sumando productos individuales Y productos incluidos dentro de combos en el carrito)
function unidadesEnCarrito(productId) {
  let total = 0;
  (state.carrito || []).forEach(item => {
    if (!item.isCombo && item.productId === productId) {
      total += item.unidadesTotales || 0;
    } else if (item.isCombo) {
      const combo = obtenerCombo(item.comboId);
      const componente = combo?.items?.find(it => it.productoId === productId);
      if (componente) {
        total += (Number(componente.cantidad) || 0) * (Number(item.cantidad) || 0);
      }
    }
  });
  return total;
}

// Calcula cuántos combos se pueden armar según el stock disponible de sus componentes
function stockComboDisponible(combo) {
  if (!combo || !combo.items || combo.items.length === 0) return 0;
  let maxPosibles = Infinity;
  for (const it of combo.items) {
    const prod = obtenerProducto(it.productoId);
    const stockTotal = Number(prod?.stock) || 0;
    const ocupadasCarrito = unidadesEnCarrito(it.productoId);
    const disponible = Math.max(stockTotal - ocupadasCarrito, 0);
    const cantRequerida = Number(it.cantidad) || 1;
    const posibles = Math.floor(disponible / cantRequerida);
    if (posibles < maxPosibles) maxPosibles = posibles;
  }
  return maxPosibles === Infinity ? 0 : maxPosibles;
}

function descripcionItemCarrito(item) {
  if (item.isCombo) {
    return `${item.cantidad} × Combo: ${item.comboName} (${item.detalle})`;
  }
  const detalle = item.cantidad === 1
    ? item.presentacionLabel
    : `${item.cantidad} × ${item.presentacionLabel}`;
  return `${detalle} ${item.productName} (${item.unidadesTotales} ud)`;
}

// =============================================================================
// CATÁLOGO DE VENTA (PRODUCTOS Y COMBOS)
// =============================================================================

let tipoCatalogoActual = 'todos'; // 'todos' | 'productos' | 'combos'

function filtrarTipoCatalogo(tipo) {
  tipoCatalogoActual = tipo;
  ['todos', 'productos', 'combos'].forEach(t => {
    const btn = document.getElementById(`filtroCat-${t}`);
    if (btn) {
      btn.className = (t === tipo)
        ? 'px-2.5 py-1 rounded-lg bg-white dark:bg-cardbg text-brand-600 shadow-sm'
        : 'px-2.5 py-1 rounded-lg text-gray-500 hover:text-gray-900 dark:hover:text-white';
    }
  });
  renderProductos();
}

function renderProductos() {
  const container = document.getElementById('productGrid');
  if (!container) return;
  container.innerHTML = '';

  const listaProductos = obtenerListaProductos();
  const listaCombos = obtenerListaCombos();

  let elementosRenderizados = 0;

  // 1. Renderizar Productos individuales
  if (tipoCatalogoActual === 'todos' || tipoCatalogoActual === 'productos') {
    listaProductos.forEach(prod => {
      elementosRenderizados++;
      const card = document.createElement('div');
      card.className = "catalog-card bg-gray-50 dark:bg-gray-800/60 p-3 rounded-xl border border-gray-100 dark:border-gray-700/60 shadow-sm flex flex-col justify-between space-y-2";
      card.dataset.productId = prod.id;
      card.dataset.type = "producto";

      card.innerHTML = `
        <div>
          <div class="flex justify-between items-start gap-2">
            <h4 class="font-bold text-xs text-gray-900 dark:text-white truncate" title="${escapeHtml(prod.nombre)}">${escapeHtml(prod.nombre)}</h4>
          </div>
          <p id="pvp-${prod.id}" class="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold mt-0.5"></p>
          <p id="stock-${prod.id}" class="text-[10px] font-semibold mt-0.5"></p>
        </div>
        <div class="space-y-1.5">
          <div class="grid grid-cols-2 gap-1.5">
            <div>
              <label class="block text-[9px] text-gray-400">Presentación</label>
              <select id="pres-${prod.id}" onchange="actualizarTarjetaProducto('${prod.id}')" class="w-full text-[11px] p-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg font-semibold text-gray-700 dark:text-gray-200">
                ${(prod.presentaciones || []).map(p => `<option value="${p.presentacionId}">${escapeHtml(p.nombre)} (x${p.factor})</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="block text-[9px] text-gray-400">Cant.</label>
              <input type="number" id="cant-${prod.id}" value="1" min="1" step="1" onchange="actualizarTarjetaProducto('${prod.id}')" oninput="actualizarTarjetaProducto('${prod.id}')" class="w-full text-[11px] p-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
            </div>
          </div>
          <button id="btn-add-${prod.id}" onclick="agregarAlCarrito('${prod.id}')" class="w-full py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-[11px] font-semibold transition flex items-center justify-center gap-1">
            <i class="fa-solid fa-cart-plus"></i> Agregar
          </button>
        </div>
      `;
      container.appendChild(card);
      const select = document.getElementById(`pres-${prod.id}`);
      if (select && prod.presentaciones?.length) select.value = prod.presentaciones[0].presentacionId;
    });
  }

  // 2. Renderizar Combos
  if (tipoCatalogoActual === 'todos' || tipoCatalogoActual === 'combos') {
    listaCombos.forEach(combo => {
      elementosRenderizados++;
      const card = document.createElement('div');
      card.className = "catalog-card bg-purple-50/60 dark:bg-purple-950/20 p-3 rounded-xl border border-purple-200 dark:border-purple-800/60 shadow-sm flex flex-col justify-between space-y-2";
      card.dataset.comboId = combo.id;
      card.dataset.type = "combo";

      const detalleItems = (combo.items || []).map(i => `${i.cantidad}x ${i.productoNombre}`).join(' + ');
      const disponible = typeof stockComboDisponible === 'function' ? stockComboDisponible(combo) : (combo.stockDisponible || 0);
      const sinStock = disponible <= 0;

      card.innerHTML = `
        <div>
          <div class="flex justify-between items-start gap-1">
            <span class="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-600 text-white uppercase">Combo 🎁</span>
          </div>
          <h4 class="font-bold text-xs text-gray-900 dark:text-white truncate mt-1" title="${escapeHtml(combo.nombre)}">${escapeHtml(combo.nombre)}</h4>
          <p class="text-[9px] text-gray-500 truncate" title="${escapeHtml(detalleItems)}">${escapeHtml(detalleItems)}</p>
          <p class="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold mt-0.5">PVP: $${combo.precioTotal.toLocaleString('es-CO')}</p>
          <p id="stock-combo-${combo.id}" class="text-[10px] font-semibold mt-0.5 ${sinStock ? 'text-red-500 dark:text-red-400' : 'text-purple-600 dark:text-purple-400'}">
            ${sinStock ? 'Sin stock componentes' : `Disponible: ${disponible} combos`}
          </p>
        </div>
        <div class="space-y-1.5">
          <div class="flex items-center gap-1.5">
            <span class="text-[9px] text-gray-400">Cant:</span>
            <input type="number" id="cant-combo-${combo.id}" value="1" min="1" max="${Math.max(disponible, 1)}" oninput="actualizarTarjetaCombo('${combo.id}')" onchange="actualizarTarjetaCombo('${combo.id}')" class="w-full text-[11px] p-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-center">
          </div>
          <button id="btn-add-combo-${combo.id}" onclick="agregarComboAlCarrito('${combo.id}')" ${sinStock ? 'disabled' : ''} class="w-full py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-[11px] font-semibold transition flex items-center justify-center gap-1">
            <i class="fa-solid fa-cart-plus"></i> Agregar Combo
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // Si no hay productos para mostrar en este filtro
  if (elementosRenderizados === 0) {
    container.innerHTML = `
      <div class="p-8 text-center text-xs text-gray-400 w-full col-span-full">
        No hay ${tipoCatalogoActual === 'combos' ? 'combos' : 'productos'} disponibles para mostrar.
      </div>
    `;
    return;
  }

  actualizarDisponibilidadCatalogo();
}

function actualizarDisponibilidadCatalogo() {
  obtenerListaProductos().forEach(prod => actualizarTarjetaProducto(prod.id));
  obtenerListaCombos().forEach(combo => {
    if (typeof actualizarTarjetaCombo === 'function') {
      actualizarTarjetaCombo(combo.id);
    }
  });
}

function actualizarTarjetaProducto(productId) {
  const prod = obtenerProducto(productId);
  if (!prod) return;
  const select = document.getElementById(`pres-${productId}`);
  const pres = obtenerPresentacionProducto(prod, select?.value);
  const cantidad = Math.max(parseInt(document.getElementById(`cant-${productId}`)?.value) || 1, 1);
  if (!pres) return;

  const pvp = Number(pres.basePrice) + Number(pres.adminGain) + Number(pres.invGain) + Number(pres.flete);
  const pvpEl = document.getElementById(`pvp-${productId}`);
  if (pvpEl) pvpEl.textContent = `PVP ${pres.nombre}: $${pvp.toLocaleString('es-CO')} c/u`;

  const stock = Number(prod.stock) || 0;
  const enCarrito = unidadesEnCarrito(productId);
  const disponible = stock - enCarrito;
  const requerido = cantidad * Number(pres.factor);
  const etiqueta = document.getElementById(`stock-${productId}`);
  const boton = document.getElementById(`btn-add-${productId}`);

  if (etiqueta) {
    if (stock <= 0) etiqueta.textContent = 'Sin stock';
    else if (enCarrito > 0) etiqueta.textContent = `Disponible: ${disponible} ud · Stock ${stock} ud`;
    else etiqueta.textContent = `Stock: ${stock} ud · Requiere ${requerido} ud`;
    etiqueta.className = 'text-[10px] font-semibold mt-0.5 ' +
      (disponible < requerido ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400');
  }

  if (boton) {
    const sinStock = disponible < requerido;
    boton.disabled = sinStock;
    boton.classList.toggle('opacity-50', sinStock);
    boton.classList.toggle('cursor-not-allowed', sinStock);
    boton.title = sinStock ? `Stock insuficiente: requiere ${requerido} unidades` : '';
  }
}

function actualizarTarjetaCombo(comboId) {
  const combo = obtenerCombo(comboId);
  if (!combo) return;
  const disponible = stockComboDisponible(combo);
  const cantidad = Math.max(parseInt(document.getElementById(`cant-combo-${comboId}`)?.value, 10) || 1, 1);

  const etiqueta = document.getElementById(`stock-combo-${comboId}`);
  const boton = document.getElementById(`btn-add-combo-${comboId}`);

  if (etiqueta) {
    if (disponible <= 0) {
      etiqueta.textContent = 'Sin stock componentes';
      etiqueta.className = 'text-[10px] font-semibold mt-0.5 text-red-500 dark:text-red-400';
    } else {
      etiqueta.textContent = `Disponible: ${disponible} combos · Requiere ${cantidad}`;
      etiqueta.className = 'text-[10px] font-semibold mt-0.5 ' +
        (cantidad > disponible ? 'text-red-500 dark:text-red-400' : 'text-purple-600 dark:text-purple-400');
    }
  }

  if (boton) {
    const sinStock = cantidad > disponible || disponible <= 0;
    boton.disabled = sinStock;
    boton.classList.toggle('opacity-50', sinStock);
    boton.classList.toggle('cursor-not-allowed', sinStock);
  }
}

function actualizarDisponibilidadCatalogo() {
  (state.catalogoProductos || []).forEach(prod => actualizarTarjetaProducto(prod.id));
  (state.combos || []).forEach(combo => actualizarTarjetaCombo(combo.id));
}

function agregarAlCarrito(productId) {
  const prod = obtenerProducto(productId);
  if (!prod) return;
  const select = document.getElementById(`pres-${productId}`);
  const pres = obtenerPresentacionProducto(prod, select?.value);
  const cantidad = Math.max(parseInt(document.getElementById(`cant-${productId}`)?.value) || 1, 1);
  if (!pres) {
    showAlert('Este producto no tiene presentaciones disponibles.', 'error');
    return;
  }

  const unidades = cantidad * Number(pres.factor);
  const disponible = (Number(prod.stock) || 0) - unidadesEnCarrito(productId);
  if (unidades > disponible) {
    showAlert(`Stock insuficiente de "${prod.nombre}": disponible ${Math.max(disponible, 0)} ud y se piden ${unidades} ud.`, 'error');
    return;
  }

  const pvpUnitario = Number(pres.basePrice) + Number(pres.adminGain) + Number(pres.invGain) + Number(pres.flete);
  state.carrito.push({
    isCombo: false,
    productId: prod.id,
    productName: prod.nombre,
    presentationId: pres.presentacionId,
    presentacionLabel: pres.nombre,
    unidadesPorPresentacion: Number(pres.factor),
    cantidad,
    unidadesTotales: unidades,
    pvpUnitario,
    total: pvpUnitario * unidades,
    adminGain: Number(pres.adminGain) * unidades,
    base: Number(pres.basePrice) * unidades,
    gananciaInv: Number(pres.invGain) * unidades,
    flete: Number(pres.flete) * unidades
  });
  renderCarrito();
}

// Reemplaza la función agregarComboAlCarrito por esta:

function agregarComboAlCarrito(comboId) {
  const combo = obtenerCombo(comboId);
  if (!combo) return;
  const cantidad = Math.max(parseInt(document.getElementById(`cant-combo-${comboId}`)?.value, 10) || 1, 1);
  const disponible = stockComboDisponible(combo);

  if (cantidad > disponible) {
    showAlert(`Stock insuficiente de productos para armar ${cantidad} combos de «${combo.nombre}».`, 'error');
    return;
  }

  state.carrito.push({
    isCombo: true,
    comboId: combo.id,
    comboName: combo.nombre,
    productName: `[COMBO] ${combo.nombre}`,
    detalle: (combo.items || []).map(i => `${i.cantidad}x ${i.productoNombre}`).join(' + '),
    cantidad,
    pvpUnitario: combo.precioTotal,
    total: combo.precioTotal * cantidad,
    adminGain: combo.adminGain * cantidad,
    base: combo.costoBase * cantidad,
    gananciaInv: combo.invGain * cantidad,
    flete: (combo.flete || 0) * cantidad // <-- Aquí se añade el flete del combo
  });
  renderCarrito();
}

function renderCarrito() {
  actualizarDisponibilidadCatalogo();
  const container = document.getElementById('cartItemsContainer');
  if (!container) return;
  container.innerHTML = '';
  const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = `$${v.toLocaleString('es-CO')}`; };

  if (!state.carrito || state.carrito.length === 0) {
    container.innerHTML = `<p class="text-xs text-gray-400 text-center py-8">No has añadido ningún producto al carrito.</p>`;
    setTxt('cartAdminTotal', 0); setTxt('cartInvTotal', 0); setTxt('cartInversionTotal', 0); setTxt('cartFleteTotal', 0); setTxt('cartGrandTotal', 0);
    return;
  }

  let grandTotal = 0, totalAdmin = 0, totalGanInv = 0, totalBase = 0, totalFlete = 0;
  state.carrito.forEach((item, index) => {
    grandTotal += item.total;
    totalAdmin += item.adminGain;
    totalGanInv += item.gananciaInv;
    totalBase += item.base;
    totalFlete += (item.flete || 0);

    const subtitulo = item.isCombo
      ? `${item.cantidad} × Combo (${escapeHtml(item.detalle)}) · $${item.pvpUnitario.toLocaleString('es-CO')} c/u`
      : `${item.cantidad} × ${escapeHtml(item.presentacionLabel)} (x${item.unidadesPorPresentacion}, ${item.unidadesTotales} ud) · $${item.pvpUnitario.toLocaleString('es-CO')} c/u`;

    const row = document.createElement('div');
    row.className = "bg-gray-50 dark:bg-gray-800/60 p-2.5 rounded-xl border border-gray-100 dark:border-gray-700/50 flex justify-between items-center text-xs gap-2";
    row.innerHTML = `
      <div class="min-w-0">
        <p class="font-bold text-gray-900 dark:text-white truncate flex items-center gap-1.5">
          ${item.isCombo ? '<span class="text-[9px] px-1 bg-purple-600 text-white rounded">COMBO</span>' : ''}
          ${escapeHtml(item.productName)}
        </p>
        <p class="text-[10px] text-gray-500">${subtitulo}</p>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span class="font-bold text-gray-900 dark:text-white">$${item.total.toLocaleString('es-CO')}</span>
        <button onclick="state.carrito.splice(${index},1);renderCarrito()" class="text-red-500 hover:text-red-700 p-1"><i class="fa-solid fa-trash-can"></i></button>
      </div>
    `;
    container.appendChild(row);
  });

  setTxt('cartAdminTotal', totalAdmin);
  setTxt('cartInvTotal', totalGanInv);
  setTxt('cartInversionTotal', totalBase);
  setTxt('cartFleteTotal', totalFlete);
  setTxt('cartGrandTotal', grandTotal);
}

let ventaProductosEnCurso = false;

async function finalizarVentaProductos() {
  if (ventaProductosEnCurso) return;
  if (!state.carrito || state.carrito.length === 0) { showAlert("Carrito vacío.", "error"); return; }
  const nombreComprador = document.getElementById('nombreCompradorProd').value.trim();
  if (!nombreComprador) {
    showAlert("Ingresa el nombre de la persona que compra.", "error");
    document.getElementById('nombreCompradorProd').focus();
    return;
  }

  let grandTotal = 0, totalAdmin = 0, totalBase = 0, totalGanInv = 0, totalFlete = 0;
  const listaNombresProductos = state.carrito.map(descripcionItemCarrito).join(', ');
  state.carrito.forEach(item => {
    grandTotal += item.total;
    totalAdmin += item.adminGain;
    totalBase += item.base;
    totalGanInv += item.gananciaInv;
    totalFlete += (item.flete || 0);
  });

  const fechaFormateada = fechaHoraColombia();

  // Separar items de productos regulares y combos
  const itemsRegulares = state.carrito
    .filter(i => !i.isCombo)
    .map(i => ({
      productoId: i.productId,
      presentacionId: i.presentationId,
      cantidad: i.cantidad
    }));

  const combosSeleccionados = state.carrito
    .filter(i => i.isCombo)
    .map(i => ({
      comboId: i.comboId,
      cantidad: i.cantidad
    }));

  const venta = {
    id: 'PROD-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
    fechaHora: fechaFormateada,
    cliente: nombreComprador,
    tipoServicio: `Prod: ${listaNombresProductos}`,
    total: grandTotal,
    adminShare: totalAdmin,
    auxShare: 0,
    materiaPrimaShare: 0,
    invShare: totalBase + totalFlete + totalGanInv,
    inversionShare: totalBase + totalFlete,
    gananciaInvShare: totalGanInv,
    fleteTotal: totalFlete,
    items: itemsRegulares,
    combos: combosSeleccionados
  };

  ventaProductosEnCurso = true;
  try {
    const res = await fetch('/api/transaccion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(venta)
    });
    const result = await res.json().catch(() => ({}));
    if (res.ok) {
      state.carrito = [];
      document.getElementById('nombreCompradorProd').value = '';
      showAlert("Venta registrada. El stock individual de cada producto se descontó.", "success");
      renderCarrito();
      if (typeof cargarEstadoBackend === 'function') {
        cargarEstadoBackend();
      }
    } else {
      showAlert(result.error || 'No fue posible registrar la venta.', 'error');
      if (typeof cargarEstadoBackend === 'function') {
        cargarEstadoBackend();
      }
    }
  } catch (err) {
    showAlert('No fue posible conectar con el servidor. La venta no se registró.', 'error');
  } finally {
    ventaProductosEnCurso = false;
  }
}

function filtrarProductos() {
  const q = document.getElementById('prodSearch').value.toLowerCase();
  Array.from(document.getElementById('productGrid').children).forEach(card => {
    card.style.display = card.textContent.toLowerCase().includes(q) ? 'flex' : 'none';
  });
}

// =============================================================================
// GESTIÓN CRUD DE PRODUCTOS (MODAL)
// =============================================================================

function abrirModalProducto(prodId = null) {
  const form = document.getElementById('formProductoCRUD');
  if (!form) return;
  form.reset();

  const prod = prodId ? obtenerProducto(prodId) : null;

  document.getElementById('modalProductoTitulo').textContent = prod ? 'Editar Producto' : 'Nuevo Producto';
  document.getElementById('crudProdId').value = prod ? prod.id : '';
  document.getElementById('crudNombre').value = prod ? prod.nombre : '';
  document.getElementById('crudStock').value = prod ? (prod.stock ?? 0) : '0';

  renderPreciosPresentacionesEnModal(prod);
  document.getElementById('modalProducto').classList.remove('hidden');
}

function editarProducto(id) {
  abrirModalProducto(id);
}

function renderPreciosPresentacionesEnModal(prod) {
  const container = document.getElementById('crudPresentacionesPrecios');
  if (!container) return;
  const pres = presentacionesActivas();
  container.innerHTML = pres.map(p => {
    const actual = prod?.presentaciones?.find(x => x.presentacionId === p.id);
    return `
      <div class="rounded-xl border border-gray-100 dark:border-gray-700 p-3 bg-gray-50/70 dark:bg-gray-800/40">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold text-gray-800 dark:text-gray-200">${escapeHtml(p.nombre)} (x${p.factor})</span>
          <span class="text-[10px] text-gray-400">${p.factor === 1 ? '1 unidad' : `consume ${p.factor} unidades`}</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
          ${campoPrecioPresentacion(p.id, 'basePrice', 'Costo base', actual?.basePrice ?? 0)}
          ${campoPrecioPresentacion(p.id, 'adminGain', 'Ganancia Admin', actual?.adminGain ?? 0)}
          ${campoPrecioPresentacion(p.id, 'invGain', 'Ganancia Inv.', actual?.invGain ?? 0)}
          ${campoPrecioPresentacion(p.id, 'flete', 'Flete', actual?.flete ?? 0)}
        </div>
      </div>`;
  }).join('');
}

function campoPrecioPresentacion(presId, campo, label, valor) {
  return `<div><label class="block text-[9px] text-gray-400 mb-1">${label}</label><input type="number" min="0" step="0.01" data-pres-id="${presId}" data-pres-field="${campo}" value="${Number(valor) || 0}" class="w-full px-2 py-1.5 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg dark:text-white"></div>`;
}

function cerrarModalProducto() {
  document.getElementById('modalProducto')?.classList.add('hidden');
}

async function guardarProductoCRUD(event) {
  event.preventDefault();

  const id = document.getElementById('crudProdId').value.trim();
  const nombre = document.getElementById('crudNombre').value.trim();
  const stock = parseInt(document.getElementById('crudStock').value, 10);

  if (!nombre) {
    showAlert('El nombre del producto es obligatorio.', 'error');
    return;
  }
  if (isNaN(stock) || stock < 0) {
    showAlert('El stock debe ser un número entero mayor o igual a 0.', 'error');
    return;
  }

  const presentacionesData = [];
  presentacionesActivas().forEach(p => {
    const getVal = campo => {
      const el = document.querySelector(`input[data-pres-id="${p.id}"][data-pres-field="${campo}"]`);
      return parseFloat(el?.value) || 0;
    };
    presentacionesData.push({
      presentacionId: p.id,
      basePrice: getVal('basePrice'),
      adminGain: getVal('adminGain'),
      invGain: getVal('invGain'),
      flete: getVal('flete')
    });
  });

  const payload = {
    id: id || undefined,
    nombre: nombre,
    stock: stock,
    presentaciones: presentacionesData
  };

  try {
    const res = await fetch('/api/producto', {
      method: id ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showAlert(data.error || 'Error al guardar el producto.', 'error');
      return;
    }

    cerrarModalProducto();
    showAlert(id ? 'Producto actualizado correctamente.' : 'Producto creado exitosamente.', 'success');
    if (typeof cargarEstadoBackend === 'function') {
      cargarEstadoBackend();
    }
  } catch (err) {
    console.error('Error al guardar producto:', err);
    showAlert('Ocurrió un error al guardar el producto.', 'error');
  }
}

async function eliminarProducto(id) {
  if (!confirm("¿Eliminar producto?")) return;
  const res = await fetch(`/api/producto/${id}`, { method: 'DELETE' });
  if (res.ok) {
    showAlert("Eliminado.", "info");
    if (typeof cargarEstadoBackend === 'function') cargarEstadoBackend();
  } else {
    const e = await res.json().catch(() => ({}));
    showAlert(e.error || 'No fue posible eliminar.', 'error');
  }
}

function renderTablaGestionProductos() {
  const tbody = document.getElementById('tablaGestionProductos');
  if (!tbody) return;
  tbody.innerHTML = '';
  (state.catalogoProductos || []).forEach(prod => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
    const badges = (prod.presentaciones || []).map(p => `<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300 mr-1 mb-1">${escapeHtml(p.nombre)} (x${p.factor})</span>`).join('');
    const unidad = (prod.presentaciones || []).find(p => Number(p.factor) === 1);
    const pvpUnidad = unidad ? Number(unidad.basePrice) + Number(unidad.adminGain) + Number(unidad.invGain) + Number(unidad.flete) : 0;
    tr.innerHTML = `
      <td class="p-4 font-bold text-gray-900 dark:text-white">${escapeHtml(prod.nombre)}</td>
      <td class="p-4 text-xs">${badges || '<span class="text-gray-400">Sin presentaciones</span>'}</td>
      <td class="p-4 font-bold ${Number(prod.stock) <= 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}">${Number(prod.stock).toLocaleString('es-CO')} ud</td>
      <td class="p-4 font-semibold text-emerald-600">$${pvpUnidad.toLocaleString('es-CO')}</td>
      <td class="p-4 text-gray-500">${(prod.presentaciones?.length || 0)} presentaciones</td>
      <td class="p-4 text-center space-x-2">
        <button onclick="abrirModalProducto('${prod.id}')" class="text-blue-500 hover:text-blue-700 p-1" title="Editar producto"><i class="fa-solid fa-pen-to-square"></i></button>
        <button onclick="eliminarProducto('${prod.id}')" class="text-red-400 hover:text-red-600 p-1" title="Eliminar"><i class="fa-solid fa-trash-can"></i></button>
      </td>`;
    tbody.appendChild(tr);
  });
}

// =============================================================================
// GESTIÓN CRUD DE PRESENTACIONES (MODAL)
// =============================================================================

function renderTablaPresentaciones() {
  const tbody = document.getElementById('tablaPresentaciones');
  if (!tbody) return;
  tbody.innerHTML = '';
  (state.presentaciones || []).forEach(p => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/40 transition";
    const estandar = ['unidad', 'media_docena', 'docena'].includes(p.id);
    tr.innerHTML = `
      <td class="p-3 font-semibold text-gray-900 dark:text-white">${escapeHtml(p.nombre)}</td>
      <td class="p-3">x${p.factor}</td>
      <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${p.activa ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300' : 'bg-gray-100 text-gray-500'}">${p.activa ? 'Activa' : 'Inactiva'}</span></td>
      <td class="p-3 text-center">
        <button onclick="editarPresentacion('${p.id}')" class="text-blue-500 hover:text-blue-700 p-1" title="Editar"><i class="fa-solid fa-pen-to-square"></i></button>
        ${!estandar && p.activa ? `<button onclick="eliminarPresentacion('${p.id}')" class="text-red-400 hover:text-red-600 p-1" title="Desactivar"><i class="fa-solid fa-trash-can"></i></button>` : ''}
      </td>`;
    tbody.appendChild(tr);
  });
}

function abrirModalPresentacion(id = null) {
  const p = (state.presentaciones || []).find(x => x.id === id);
  document.getElementById('crudPresId').value = p?.id || '';
  document.getElementById('crudPresNombre').value = p?.nombre || '';
  document.getElementById('crudPresFactor').value = p?.factor || 1;
  document.getElementById('modalPresentacion').classList.remove('hidden');
}

function editarPresentacion(id) { abrirModalPresentacion(id); }
function cerrarModalPresentacion() { document.getElementById('modalPresentacion')?.classList.add('hidden'); }

async function guardarPresentacionCRUD(e) {
  e.preventDefault();
  const id = document.getElementById('crudPresId').value;
  const payload = {
    nombre: document.getElementById('crudPresNombre').value.trim(),
    factor: Number(document.getElementById('crudPresFactor').value)
  };
  if (!payload.nombre || !Number.isInteger(payload.factor) || payload.factor <= 0) {
    showAlert('Indica un nombre y un factor entero mayor que 0.', 'error');
    return;
  }
  const res = await fetch(id ? `/api/presentacion/${id}` : '/api/presentacion', {
    method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  const result = await res.json().catch(() => ({}));
  if (res.ok) {
    showAlert(id ? 'Presentación actualizada.' : 'Presentación creada y habilitada para todos los productos.', 'success');
    cerrarModalPresentacion();
    if (typeof cargarEstadoBackend === 'function') cargarEstadoBackend();
  } else {
    showAlert(result.error || 'No fue posible guardar la presentación.', 'error');
  }
}

async function eliminarPresentacion(id) {
  if (!confirm('¿Desactivar esta presentación? Dejará de aparecer para las nuevas ventas.')) return;
  const res = await fetch(`/api/presentacion/${id}`, { method: 'DELETE' });
  const result = await res.json().catch(() => ({}));
  if (res.ok) {
    showAlert('Presentación desactivada.', 'info');
    if (typeof cargarEstadoBackend === 'function') cargarEstadoBackend();
  } else {
    showAlert(result.error || 'No fue posible desactivar.', 'error');
  }
}

// Función segura para obtener la lista de productos sin importar cómo la llame main.js
function obtenerListaProductos() {
  if (typeof state !== 'undefined') {
    if (Array.isArray(state.catalogoProductos) && state.catalogoProductos.length > 0) return state.catalogoProductos;
    if (Array.isArray(state.productos) && state.productos.length > 0) return state.productos;
  }
  if (typeof window.state !== 'undefined') {
    if (Array.isArray(window.state.catalogoProductos) && window.state.catalogoProductos.length > 0) return window.state.catalogoProductos;
    if (Array.isArray(window.state.productos) && window.state.productos.length > 0) return window.state.productos;
  }
  return [];
}

// Función segura para obtener los combos
function obtenerListaCombos() {
  if (typeof state !== 'undefined' && Array.isArray(state.combos)) return state.combos;
  if (typeof window.state !== 'undefined' && Array.isArray(window.state.combos)) return window.state.combos;
  return [];
}

function obtenerProducto(productId) {
  return obtenerListaProductos().find(p => p.id === productId);
}

function obtenerCombo(comboId) {
  return obtenerListaCombos().find(c => c.id === comboId);
}