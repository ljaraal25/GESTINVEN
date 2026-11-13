from fastapi import APIRouter,Depends,Request,Query,HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
if __package__:
 from . import stock_store as store
 from .evaluacion_api import require_user
else:
 import stock_store as store
 from evaluacion_api import require_user
router=APIRouter(prefix='/stock',tags=['Stock operativo'])
_catalog=None;_predict=None;_project=None
def configure(catalog,predict,project):
 global _catalog,_predict,_project
 _catalog,_predict,_project=catalog,predict,project
def catalog():return store.merged(_catalog())
def present(p):
 p=dict(p)
 if p.get('importado'):
  prediction=p.get('prediccion')
  p.update(riesgo='Pendiente de recalcular',prioridad='Pendiente',recomendacion='Stock actualizado; revisar la predicción.')
  p['reposicion']=max(prediction+p['stock_seguridad']-p['stock_utilizable'],0) if prediction is not None else None
 return p
@router.post('/validar')
async def validar(request:Request,archivo:str=Query(...,max_length=180),user:str=Depends(require_user)):
 if not archivo.lower().endswith('.xlsx'):raise HTTPException(422,'Seleccione un archivo .xlsx.')
 raw=bytearray()
 async for chunk in request.stream():
  raw.extend(chunk)
  if len(raw)>store.MAX_FILE:raise HTTPException(413,'Máximo 8 MB.')
 try:return await run_in_threadpool(lambda:store.preview(bytes(raw),archivo,user,_catalog()))
 except (ValueError,TypeError,IndexError) as e:raise HTTPException(422,str(e)) from None
class Confirmation(BaseModel):id:str
@router.post('/confirmar')
def confirmar(body:Confirmation,user:str=Depends(require_user)):
 try:return store.confirm(body.id,user)
 except ValueError as e:raise HTTPException(409,str(e)) from None
@router.get('/inventario')
def inventario(user:str=Depends(require_user)):
 return [present(p) for p in sorted(catalog().values(),key=lambda x:x['codigo'])]
@router.get('/producto/{codigo}')
def producto(codigo:str,user:str=Depends(require_user)):
 try:p=catalog().get(store.code(codigo))
 except ValueError:raise HTTPException(422,'Código inválido.') from None
 return {'encontrado':True,**present(p)} if p else {'encontrado':False,'mensaje':'Producto no encontrado.'}
@router.get('/producto/{codigo}/prediccion')
def prediccion(codigo:str,user:str=Depends(require_user)):
 try:codigo=store.code(codigo)
 except ValueError:raise HTTPException(422,'Código inválido.') from None
 p=catalog().get(codigo)
 if not p:return {'encontrado':False,'mensaje':'Producto no encontrado.'}
 predictions=_predict(codigo)
 if not predictions:return {'encontrado':False,'mensaje':'Producto registrado sin historial de demanda; no se puede generar una predicción todavía.'}
 if p.get('stock_utilizable') is None or p.get('stock_seguridad') is None:raise HTTPException(422,'Complete los datos de stock antes de calcular la proyección.')
 projected=_project(predictions,p['stock_utilizable'],p['stock_seguridad'])
 first=predictions[0]['prediccion']
 return {'encontrado':True,'codigo':codigo,'modelo':'Random Forest','predicciones':predictions,'proyeccion_stock':projected,
 'stock_utilizable':p['stock_utilizable'],'stock_seguridad':p['stock_seguridad'],
 'stock_objetivo':first+p['stock_seguridad'],'reposicion_sugerida':max(first+p['stock_seguridad']-p['stock_utilizable'],0)}
