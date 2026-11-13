"""Acceso privado a PostgreSQL de Supabase desde el backend."""
import json
from urllib import request,parse,error
if __package__:
 from .bitacora_supabase import configuracion,SinRedireccion,ErrorBitacora
else:
 from bitacora_supabase import configuracion,SinRedireccion,ErrorBitacora
class CloudError(RuntimeError):
 def __init__(self,message='No se pudo consultar Supabase.',status=None):super().__init__(message);self.status=status

def enviar(recurso,method='GET',params=None,body=None,prefer=None):
 if not recurso or recurso.startswith('/') or '://' in recurso:raise ValueError('Recurso no permitido.')
 try:url,key=configuracion()
 except (ErrorBitacora,OSError,ValueError):raise CloudError('Revise la configuración privada de Supabase.') from None
 query=('?'+parse.urlencode(params)) if params else ''
 headers={'apikey':key,'Accept':'application/json'}
 if body is not None:headers['Content-Type']='application/json'
 if prefer:headers['Prefer']=prefer
 req=request.Request(url+'/rest/v1/'+recurso+query,data=json.dumps(body,ensure_ascii=False,allow_nan=False).encode() if body is not None else None,headers=headers,method=method)
 try:
  with request.build_opener(SinRedireccion()).open(req,timeout=40) as response:raw=response.read()
  return json.loads(raw) if raw else None
 except error.HTTPError as exc:
  message='No se pudo completar la operación en Supabase.'
  if recurso=='rpc/gest_stock_confirmar':
   try:
    detail=json.loads(exc.read()).get('message','')
    if any(x in detail for x in ['Vista previa','carga ya','stock cambió']):message=detail
   except (ValueError,OSError):pass
  raise CloudError(message,exc.code) from None
 except (OSError,ValueError):raise CloudError('No se pudo confirmar la conexión con Supabase.') from None

def rpc(nombre,params=None):return enviar('rpc/'+nombre,'POST',body=params or {})
def todos(tabla,params=None):
 result=[];offset=0
 while True:
  page=enviar(tabla,params={**(params or {}),'limit':500,'offset':offset})
  if not isinstance(page,list):raise CloudError('Respuesta incompleta de Supabase.')
  result.extend(page)
  if len(page)<500:return result
  offset+=500
  if offset>200000:raise CloudError('La consulta supera el límite permitido.')
