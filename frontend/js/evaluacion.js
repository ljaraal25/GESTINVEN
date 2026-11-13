'use strict';
const API=window.GESTINVEN_API_URL;
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x};
const num=n=>Number(n).toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=n=>n==null?'No calculable':num(n)+' %';
const localDate=s=>new Date(s).toLocaleString('es-PE',{timeZone:'America/Lima'});
let summary=[], reported=[], last=null, currentOffset=0, lastParams=null;
function td(tr,text,cls){const x=el('td',text,cls);tr.append(x);return x}
async function request(path){
 const token=sessionStorage.getItem('tokenEvaluacion');
 if(!token)throw new Error('Vuelva a iniciar sesión para obtener acceso a la evaluación.');
 const response=await fetch(API+path,{headers:{Authorization:'Bearer '+token},cache:'no-store'});
 let body;try{body=await response.json()}catch{throw new Error('El servidor no devolvió una respuesta de evaluación. Compruebe que el backend esté actualizado.')}
 if(!response.ok){if(response.status===401)sessionStorage.removeItem('tokenEvaluacion');throw new Error(typeof body.detail==='string'?body.detail:'No se pudo completar la consulta. Revise sus filtros.')}
 return body;
}
function queryPath(params){return '/evaluacion/consultar?'+new URLSearchParams(params).toString()}
function metricField(){return {quiebres:'quiebres_pct',mermas:'mermas_pct',eficiencia:'eficiencia_pct'}[$('metric').value]}
function drawChart(pairs){
 const svg=$('chart');svg.replaceChildren();const ns='http://www.w3.org/2000/svg';
 function add(tag,attrs,text){const x=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))x.setAttribute(k,v);if(text!==undefined)x.textContent=text;svg.append(x);return x}
 add('title',{},'Tasas semanales según la fuente seleccionada');add('desc',{},pairs.map((p,i)=>'Semana '+(i+1)+': pretest '+pct(p.pre)+', postest '+pct(p.post)).join('. '));
 const values=pairs.flatMap(x=>[x.pre,x.post]).filter(x=>x!=null);
 const ymax=$('metric').value==='eficiencia'?100:Math.max(1,Math.ceil(Math.max(0,...values)*1.18)),bottom=235,height=190;
 for(let i=0;i<=4;i++){const y=bottom-height*i/4;add('line',{x1:45,x2:870,y1:y,y2:y,stroke:'#dce5ed'});add('text',{x:37,y:y+4,'text-anchor':'end'},num(ymax*i/4)+'%')}
 pairs.forEach((p,i)=>{const x=74+i*100;for(const[k,dx,color]of[['pre',0,'#7e91a5'],['post',30,'#167c94']]){
 const v=p[k];if(v==null){add('text',{x:x+dx+12.5,y:bottom-8,'text-anchor':'middle',style:'font-size:10px'},'n/d');continue}
 const h=v/ymax*height;add('rect',{x:x+dx,y:bottom-h,width:25,height:h,fill:color});add('text',{x:x+dx+12.5,y:bottom-h-7,'text-anchor':'middle',style:'font-size:10px'},num(v))}
 add('text',{x:x+28,y:260,'text-anchor':'middle'},'Sem. '+(i+1))});
}
function validationMessage(row,metric){
 if(!row)return 'Sin datos';
 if(metric==='mermas'){
  if(!row.validacion_mermas)return 'Servidor pendiente de actualización';
  const parts=[];
  if(row.aperturas_negativas>0)parts.push(row.aperturas_negativas+' apertura(s) negativa(s), saldo total '+num(row.saldo_aperturas_negativas));
  if(row.aperturas_no_calculables>0)parts.push(row.aperturas_no_calculables+' apertura(s) sin datos');
  if(row.perdidas_no_calculables>0)parts.push(row.perdidas_no_calculables+' pérdida(s) sin cantidad');
  if(!(row.qr>0))parts.push('Cantidad inicial no positiva o ausente');
  return parts.length?parts.join(' · '):'Sin incidencias automáticas detectadas';
 }
 if(metric==='eficiencia')return row.sin_apertura>0?row.sin_apertura+' registro(s) sin saldo anterior: porcentaje como cota mínima':'Base disponible para los criterios automáticos';
 return row.cierres_sin_saldo>0?row.cierres_sin_saldo+' cierre(s) sin saldo':row.cierres_negativos>0?row.cierres_negativos+' saldo(s) negativos al cierre':'Sin incidencias automáticas detectadas';
}
function renderComparison(){
 const metric=$('metric').value,field=metricField(),direction=metric==='eficiencia'?1:-1,pairs=[],useExcel=$('comparison-source').value==='excel';
 $('legend-pre').textContent=useExcel?'Pretest reportado en Excel':'Pretest calculado';$('legend-post').textContent=useExcel?'Postest reportado en Excel':'Postest calculado';
 $('comparison').replaceChildren();
 for(let week=1;week<=8;week++){
  const pre=summary.find(x=>x.etapa==='PRE'&&x.semana===week),post=summary.find(x=>x.etapa==='POST'&&x.semana===week);
  const refs=['PRE','POST'].map(phase=>reported.find(x=>x.etapa===phase&&x.semana===week&&x.indicador===metric));
  const a=useExcel?(refs[0]?.valor_pct??null):(pre?.[field]??null),b=useExcel?(refs[1]?.valor_pct??null):(post?.[field]??null);
  const partial=!useExcel&&metric==='eficiencia'&&((pre?.sin_apertura??0)>0||(post?.sin_apertura??0)>0);
  pairs.push({pre:a,post:b,comparable:a!=null&&b!=null&&!partial});
  const tr=el('tr'),label=td(tr,'Semana '+week);
  label.append(el('span','Pre: '+(pre?.desde??'—')+' / '+(pre?.hasta??'—'),'reference'),el('span','Post: '+(post?.desde??'—')+' / '+(post?.hasta??'—'),'reference'));
  const preCell=td(tr,pct(a)),postCell=td(tr,pct(b));
  if(metric==='eficiencia'&&!useExcel){
   if(pre?.sin_apertura>0)preCell.append(el('span','Cota mínima verificada','reference'));
   if(post?.sin_apertura>0)postCell.append(el('span','Cota mínima verificada','reference'));
  }
  const delta=a==null||b==null||partial?null:b-a;
  td(tr,delta==null?(partial?'Alcance parcial':'No calculable'):(delta>0?'+':'')+num(delta),delta==null?'muted':delta*direction>=0?'good':'bad');
  const validation=td(tr);
  if(useExcel&&metric==='eficiencia')validation.append(el('span','Conciliación con la revisión SQL pendiente.','reference'));
  validation.append(el('span','Revisión de datos · Pre: '+validationMessage(pre,metric),'reference'),el('span','Post: '+validationMessage(post,metric),'reference'));
  const action=td(tr),button=el('button','Consultar postest','small-button');button.type='button';
  button.addEventListener('click',()=>{$('query').value=metric==='eficiencia'?'errores':metric;$('phase').value='POST';$('week').value=String(week);$('code').value='';currentOffset=0;runQuery();$('query-panel').scrollIntoView({behavior:'smooth'})});
  action.append(button);$('comparison').append(tr);
 }
 const comparable=pairs.filter(p=>p.comparable),n=comparable.length,calculable=pairs.filter(p=>p.pre!=null&&p.post!=null).length;
 const a=n?comparable.reduce((s,p)=>s+p.pre,0)/n:null,b=n?comparable.reduce((s,p)=>s+p.post,0)/n:null;
 $('comparable').textContent=n+' / 8';$('mean-pre').textContent=pct(a);$('mean-post').textContent=pct(b);
 $('mean-change').textContent=n?((b-a)>0?'+':'')+num(b-a):'No comparable';
 $('mean-change').className=n?((b-a)*direction>=0?'good':'bad'):'muted';
 drawChart(pairs);
}

async function loadComparison(){
 $('refresh-comparison').disabled=true;
 try{
  const [calc,ref]=await Promise.all([request(queryPath({consulta:'comparativo',limite:100})),request(queryPath({consulta:'reportado',limite:100}))]);
  summary=calc.filas;reported=ref.filas;renderComparison();
 }catch(e){summary=[];reported=[];renderComparison();$('connection').textContent=e.message}
 finally{$('refresh-comparison').disabled=false}
}
async function runQuery(reuse=false){
 if($('run').disabled)return;
 const params=reuse?{...lastParams,desplazamiento:currentOffset}:{consulta:$('query').value,etapa:$('phase').value,semana:$('week').value,codigo:$('code').value.trim(),limite:50,desplazamiento:0};
 if(!reuse)currentOffset=0;
 if(params.codigo&&!/^[0-9]{1,12}$/.test(params.codigo)){$('query-message').textContent='Ingrese un código numérico de hasta 12 dígitos.';return}
 $('run').disabled=true;$('previous').disabled=true;$('next').disabled=true;$('csv').disabled=true;$('receipt').disabled=true;
 $('query-message').textContent='Consultando los registros…';
 try{
  const result=await request(queryPath(params));last=result;lastParams=params;
  $('result-head').replaceChildren();$('result-body').replaceChildren();
  const columns=Object.keys(result.filas[0]??{});
  if(columns.length){const header=el('tr');for(const c of columns)header.append(el('th',c));$('result-head').append(header);
  for(const r of result.filas){const tr=el('tr');for(const c of columns)td(tr,r[c]==null?'Sin dato':String(r[c]));$('result-body').append(tr)}}
  else{const tr=el('tr');td(tr,'No hay registros para esta consulta.');$('result-body').append(tr)}
  const first=result.total?currentOffset+1:0,lastRow=currentOffset+result.filas.length;
  $('query-message').textContent=result.titulo+' · '+result.parametros.etapa+' · semana '+result.parametros.semana+' · '+first+'–'+lastRow+' de '+result.total+' filas.';

  const audit=result.auditoria?.guardada?'Bitácora guardada.':'Bitácora NO guardada.';
  $('execution').textContent='Ejecución '+result.ejecucion_id+' · '+localDate(result.ejecutado_utc)+' (Lima) · '+result.duracion_ms+' ms · Solo lectura. '+audit;
  $('page').textContent='Página '+(Math.floor(currentOffset/50)+1)+' de '+Math.max(1,Math.ceil(result.total/50));
  $('previous').disabled=currentOffset===0;$('next').disabled=currentOffset+50>=result.total;
  $('csv').disabled=!result.filas.length;$('receipt').disabled=false;
 }catch(e){last=null;$('query-message').textContent=e.message;$('result-head').replaceChildren();$('result-body').replaceChildren();$('execution').textContent='';$('page').textContent=''}
 finally{$('run').disabled=false}
}
function download(name,content,type){const u=URL.createObjectURL(new Blob([content],{type}));const a=el('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
function csv(rows){return '\ufeff'+rows.map(r=>r.map(v=>{let s=v==null?'':String(v);if(typeof v==='string'&&/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'}).join(';')).join('\r\n')}
async function loadAudit(){
 $('refresh-audit').disabled=true;
 try{const r=await request('/evaluacion/auditoria');$('audit-body').replaceChildren();
 $('audit-state').textContent=r.total+' consultas registradas · Cadena de huellas '+(r.cadena_valida?'coherente.':'CON ALTERACIONES.');
 for(const item of r.eventos){const tr=el('tr');for(const v of [localDate(item.fecha_utc),item.usuario,item.consulta,[(item.parametros.etapa==='POST'?'Postest':'Pretest'),'Semana '+item.parametros.semana,item.parametros.codigo?'Código '+item.parametros.codigo:'Todos los productos'].join(' · '),item.total,item.ejecucion_id])td(tr,String(v));$('audit-body').append(tr)}
 }catch(e){$('audit-state').textContent=e.message}finally{$('refresh-audit').disabled=false}
}
async function initialize(){
 try{
  const m=await request('/evaluacion/fuente');
  if(m.version_calculo!=='2.1')throw new Error('Reinicie el backend local para aplicar la nueva separación de cálculo y validación.');
  $('connection').textContent='Datos disponibles · '+m.conteos.map(x=>x.etapa+': '+x.registros+' movimientos ('+x.excluidos+' excluidos)').join(' · ');
  await loadComparison();
 }catch(e){$('connection').textContent=e.message;$('connection').className='notice error';const link=el('a',' Volver al inicio de sesión');link.href='../login/';$('connection').append(link)}
}
$('query-form').addEventListener('submit',e=>{e.preventDefault();runQuery()});
$('metric').addEventListener('change',()=>{$('comparison-source').value=$('metric').value==='eficiencia'?'excel':'sql';renderComparison()});
$('comparison-source').addEventListener('change',renderComparison);
$('refresh-comparison').addEventListener('click',loadComparison);
$('refresh-audit').addEventListener('click',loadAudit);
$('previous').addEventListener('click',()=>{currentOffset=Math.max(0,currentOffset-50);runQuery(true)});
$('next').addEventListener('click',()=>{currentOffset+=50;runQuery(true)});
$('receipt').addEventListener('click',()=>{if(last)download('ejecucion_'+last.ejecucion_id+'.json',JSON.stringify(last,null,2),'application/json;charset=utf-8')});
$('csv').addEventListener('click',()=>{if(last?.filas.length){const keys=Object.keys(last.filas[0]);download('consulta_'+last.consulta+'_pagina_'+(Math.floor(currentOffset/50)+1)+'.csv',csv([keys,...last.filas.map(r=>keys.map(k=>r[k]))]),'text/csv;charset=utf-8')}});

function exportSourceReview(){
 const rows=[['Indicador','Etapa','Semana','Porcentaje SQL','Porcentaje Excel','Alcance SQL','Validación de datos','Comparación entre fuentes']];
 for(const metric of ['quiebres','mermas','eficiencia'])for(const phase of ['PRE','POST'])for(let week=1;week<=8;week++){
  const row=summary.find(x=>x.etapa===phase&&x.semana===week);
  const ref=reported.find(x=>x.etapa===phase&&x.semana===week&&x.indicador===metric);
  const value=row?.[{quiebres:'quiebres_pct',mermas:'mermas_pct',eficiencia:'eficiencia_pct'}[metric]]??null;
  const reportedValue=ref?.valor_pct??null;
  const partial=metric==='eficiencia'&&(row?.sin_apertura??0)>0;
  const state=value==null||reportedValue==null?'Sin datos suficientes':partial?'Alcances distintos; conciliación pendiente':Math.abs(value-reportedValue)<=0.0051?'Coincide al redondear':'Difiere; revisión pendiente';
  rows.push([metric,phase,week,value,reportedValue,metric==='eficiencia'?(row?.eficiencia_alcance??'Sin datos'):'Cálculo aritmético',validationMessage(row,metric),state]);
 }
 download('revision_SQL_Excel.csv',csv(rows),'text/csv;charset=utf-8');
}
$('export-source-review').addEventListener('click',exportSourceReview);

initialize();
