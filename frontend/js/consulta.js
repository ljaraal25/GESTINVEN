'use strict';
(()=>{
const $=id=>document.getElementById(id),api=window.GESTINVEN_API_URL;
let preview=null,selectedCode='',uploadBusy=false;
const fmt=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('es-PE'):(v??'Sin historial');
function text(id,value){$(id).textContent=fmt(value)}
async function request(path,options={}){
 const token=sessionStorage.getItem('tokenEvaluacion');
 if(!token)throw new Error('Vuelva a iniciar sesión para cargar o consultar el stock.');
 const r=await fetch(api+path,{...options,headers:{...(options.headers||{}),Authorization:'Bearer '+token},cache:'no-store'});
 const d=await r.json();
 if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'No se pudo completar la operación.');
 return d;
}
function clearPredictions(){
 $('resultadoML').classList.add('oculto');$('tablaPredicciones').replaceChildren();$('tablaStockProyectado').replaceChildren();
}
async function search(){
 const codigo=$('codigoProducto').value.trim();
 clearPredictions();selectedCode='';$('resultado').classList.add('oculto');
 if(!codigo){text('mensaje','Ingrese un código.');return}
 $('btnBuscar').disabled=true;text('mensaje','Consultando…');
 try{
  const d=await request('/stock/producto/'+encodeURIComponent(codigo));
  if(!d.encontrado){text('mensaje',d.mensaje);return}
  selectedCode=d.codigo;
  for(const[id,value]of Object.entries({nombreProducto:d.descripcion,codigoResultado:d.codigo,unidadResultado:d.unidad,abcResultado:d.clase_abc,prediccionResultado:d.prediccion,stockActualResultado:d.stock_actual,stockResultado:d.stock_utilizable,seguridadResultado:d.stock_seguridad,reposicionResultado:d.reposicion,riesgoResultado:d.riesgo,prioridadResultado:d.prioridad,recomendacionResultado:d.recomendacion}))text(id,value);
  text('mensaje',d.importado?'Stock actualizado mediante Excel.':'');
  $('resultado').classList.remove('oculto');
 }catch(e){text('mensaje',e.message)}finally{$('btnBuscar').disabled=false}
}
function row(body,values){const tr=document.createElement('tr');for(const v of values){const td=document.createElement('td');td.textContent=fmt(v);tr.append(td)}body.append(tr);return tr}
$('btnBuscar').addEventListener('click',search);
$('codigoProducto').addEventListener('keydown',e=>{if(e.key==='Enter')search()});
$('btnPredecirML').addEventListener('click',async()=>{
 if(!selectedCode)return;
 const button=$('btnPredecirML');button.disabled=true;text('mensaje','Calculando predicción…');clearPredictions();
 try{
  const d=await request('/stock/producto/'+encodeURIComponent(selectedCode)+'/prediccion');
  if(!d.encontrado){text('mensaje',d.mensaje);return}
  for(const p of d.predicciones)row($('tablaPredicciones'),[p.mes,p.prediccion]);
  for(const p of d.proyeccion_stock)row($('tablaStockProyectado'),[p.mes,p.stock_proyectado,p.estado]);
  for(const[id,v]of Object.entries({mlStock:d.stock_utilizable,mlSeguridad:d.stock_seguridad,mlObjetivo:d.stock_objetivo,mlReposicion:d.reposicion_sugerida,valorPrediccionML:d.predicciones[0]?.prediccion,reposicionResultado:d.reposicion_sugerida,prediccionResultado:d.predicciones[0]?.prediccion}))text(id,v);
  $('resultadoML').classList.remove('oculto');text('mensaje','Predicción calculada con el stock vigente. Cargar stock no agrega historial de demanda.');
 }catch(e){text('mensaje','No se pudo calcular la predicción: '+e.message)}finally{button.disabled=false}
});
$('btnCargarStock').addEventListener('click',()=>{$('panelCargaStock').hidden=!$('panelCargaStock').hidden});
function resetPreview(){preview=null;$('confirmarStock').hidden=true;$('vistaStock').replaceChildren();text('estadoCargaStock','')}
$('archivoStock').addEventListener('change',resetPreview);
$('cancelarStock').addEventListener('click',()=>{if(uploadBusy)return;resetPreview();$('archivoStock').value='';$('panelCargaStock').hidden=true});
function busy(value){uploadBusy=value;for(const id of ['validarStock','confirmarStock','archivoStock','cancelarStock'])$(id).disabled=value}
$('validarStock').addEventListener('click',async()=>{
 const file=$('archivoStock').files[0];resetPreview();
 if(!file){text('estadoCargaStock','Seleccione un Excel .xlsx.');return}
 if(!file.name.toLowerCase().endsWith('.xlsx')||file.size>8*1024*1024){text('estadoCargaStock','Use un archivo .xlsx de hasta 8 MB.');return}
 busy(true);text('estadoCargaStock','Validando archivo…');
 try{
  const d=await request('/stock/validar?archivo='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
  if(!d.valido){text('estadoCargaStock',d.total_errores+' errores. No se modificó el stock.');for(const e of d.errores)row($('vistaStock'),['Fila '+e.fila,e.mensaje]);return}
  preview=d;
  text('estadoCargaStock',d.total+' productos: '+d.nuevos+' nuevos y '+d.actualizados+' existentes. Vista previa de hasta 100 filas; confirme para aplicar.');
  for(const p of d.muestra)row($('vistaStock'),[p.codigo,p.descripcion,p.stock_anterior??'Nuevo',p.stock_nuevo,p.utilizable,p.seguridad,p.accion]);
  $('confirmarStock').hidden=false;
 }catch(e){text('estadoCargaStock',e.message)}finally{busy(false)}
});
$('confirmarStock').addEventListener('click',async()=>{
 if(!preview||uploadBusy)return;
 busy(true);
 try{
  const d=await request('/stock/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:preview.id})});
  preview=null;$('confirmarStock').hidden=true;
  text('estadoCargaStock','Carga guardada: '+d.nuevos+' productos nuevos y '+d.actualizados+' actualizados. Fecha: '+new Date(d.fecha_utc).toLocaleString('es-PE',{timeZone:'America/Lima'})+'. Puede consultarlos por código o ver el inventario.');
  if($('codigoProducto').value.trim())await search();
 }catch(e){preview=null;$('confirmarStock').hidden=true;text('estadoCargaStock',e.message+' Vuelva a validar antes de confirmar.')}finally{busy(false)}
});
})();
