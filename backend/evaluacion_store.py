"""Consultas de evaluación ejecutadas en PostgreSQL de Supabase."""
import json,hashlib,re
if __package__:
 from . import supabase_db as db
else:
 import supabase_db as db
CloudError=db.CloudError
TITULOS={'quiebres':'Productos con quiebre al cierre semanal','cierres':'Todos los saldos de cierre semanal','aperturas':'Saldos de apertura reconstruidos y sus incidencias','mermas':'Movimientos con pérdidas por vencimiento','errores':'Registros con incidencias o sin apertura verificable','movimientos':'Movimientos del período, incluidos los excluidos','comparativo':'Indicadores semanales calculados en PostgreSQL','reportado':'Tasas reportadas conservadas del Excel'}
def metadata():return db.rpc('gest_metadata')
def execute(name,etapa='POST',semana=1,codigo='',limit=100,offset=0):
 if name not in TITULOS or etapa not in ('PRE','POST') or not 1<=semana<=8 or not 1<=limit<=500 or offset<0:raise ValueError('Parámetros de consulta inválidos.')
 if codigo:
  if not re.fullmatch(r'[0-9]{1,12}',codigo):raise ValueError('Código no válido.')
  codigo=str(int(codigo)).zfill(5)
 result=db.rpc('gest_consulta',{'p_consulta':name,'p_etapa':etapa,'p_semana':semana,'p_codigo':codigo,'p_limite':limit,'p_desplazamiento':offset})
 if not isinstance(result,dict) or result.get('fuente') is None:raise CloudError('La fuente de evaluación todavía no está cargada en Supabase.')
 result.update(consulta=name,titulo=TITULOS[name],parametros={'etapa':etapa,'semana':semana,'codigo':codigo,'limite':limit,'desplazamiento':offset})
 return result
def log_execution(result,user):
 record={'ejecucion_id':result['ejecucion_id'],'fecha_utc':result['ejecutado_utc'],'usuario':user,'consulta':result['consulta'],'parametros':result['parametros'],'total':result['total'],'duracion_ms':result['duracion_ms'],'fuente_sha256':result['fuente']['sha256'],'sql_sha256':hashlib.sha256(result['sql'].encode()).hexdigest(),'resultado_pagina_sha256':hashlib.sha256(json.dumps(result['filas'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
 payload=json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);digest=hashlib.sha256(payload.encode()).hexdigest()
 db.enviar('auditoria_consultas','POST',body={'ejecucion_id':record['ejecucion_id'],'payload':payload,'anterior':'','huella':digest,'origen':'SUPABASE','fecha_utc':record['fecha_utc']},prefer='resolution=ignore-duplicates,return=minimal')
 return {'guardada':True,'huella':digest,'persistencia_configurada':True,'origen':'SUPABASE'}
def audit_events(limit=100):return db.rpc('gest_auditoria')
