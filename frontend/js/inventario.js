'use strict';
(()=>{
const body=document.getElementById('tablaInventario'),search=document.getElementById('buscarInventario');
let rows=[];
function render(){
 const q=search.value.trim().toLocaleLowerCase();
 const found=rows.filter(p=>p.codigo.toLocaleLowerCase().includes(q)||p.descripcion.toLocaleLowerCase().includes(q));
 body.replaceChildren();
 for(const p of found){const tr=document.createElement('tr');for(const v of [p.codigo,p.descripcion,p.unidad,p.stock_actual,p.stock_utilizable,p.stock_seguridad,p.riesgo||'Pendiente',p.recomendacion||'Pendiente']){const td=document.createElement('td');td.textContent=v==null?'Sin dato':String(v);tr.append(td)}body.append(tr)}
 if(!found.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=8;td.textContent='No se encontraron productos.';tr.append(td);body.append(tr)}
}
search.addEventListener('input',render);
(async()=>{try{const token=sessionStorage.getItem('tokenEvaluacion');if(!token)throw new Error('Inicie sesión nuevamente.');const r=await fetch(window.GESTINVEN_API_URL+'/stock/inventario',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw new Error('No se pudo consultar el inventario. Inicie sesión nuevamente.');rows=await r.json();render()}catch(e){body.replaceChildren();const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=8;td.textContent=e.message;tr.append(td);body.append(tr)}})();
})();
