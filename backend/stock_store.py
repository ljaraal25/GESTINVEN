"""Importación de stock con persistencia y confirmación atómica en Supabase."""
from pathlib import Path
import json,time,uuid,hashlib,io,zipfile,unicodedata,re,math
import openpyxl
from xml.etree.ElementTree import ParseError
if __package__:
 from . import supabase_db as db
else:
 import supabase_db as db
MAX_FILE=8*1024*1024
FIELDS=('codigo','descripcion','unidad','stock_actual','stock_utilizable','stock_seguridad')
ALIASES={'CODIGO':'codigo','CODIGO PRODUCTO':'codigo','PRODUCTO':'descripcion','DESCRIPCION':'descripcion','NOMBRE DEL PRODUCTO':'descripcion','UNIDAD':'unidad','STOCK ACTUAL':'stock_actual','STOCK':'stock_actual','STOCK UTILIZABLE':'stock_utilizable','STOCK SEGURIDAD':'stock_seguridad','STOCK DE SEGURIDAD':'stock_seguridad'}
def code(v):
    if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) and float(v).is_integer():v=str(int(v))
    s=str(v or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,39}',s):raise ValueError('Código inválido.')
    return s.zfill(5) if s.isdigit() else s
def key(v):
    return ' '.join(''.join(x for x in unicodedata.normalize('NFD',str(v or '')) if unicodedata.category(x)!='Mn').upper().replace('_',' ').split())

def parse(raw):
    if len(raw)>MAX_FILE:raise ValueError('El archivo supera 8 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if len(z.infolist())>2000 or sum(x.file_size for x in z.infolist())>50*1024*1024:raise ValueError('El archivo descomprimido supera el límite permitido.')
        wb=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
    except (zipfile.BadZipFile,KeyError,ParseError,OSError,openpyxl.utils.exceptions.InvalidFileException):
        raise ValueError('Archivo XLSX inválido.') from None
    result=[];errors=[];seen=set()
    try:
        ws=wb.worksheets[0]
        if ws.max_row>10020 or ws.max_column>100:raise ValueError('Máximo 10 000 filas y 100 columnas.')
        mapping=None
        for rn,row in enumerate(ws.iter_rows(values_only=True),1):
            if not any(v is not None and str(v).strip() for v in row):continue
            if mapping is None:
                found={}
                for i,v in enumerate(row):
                    field=ALIASES.get(key(v))
                    if field:
                        if field in found:raise ValueError('Hay columnas duplicadas para '+field)
                        found[field]=i
                if set(FIELDS)<=found.keys():mapping=found;continue
                if rn>=20:raise ValueError('No se encontró un encabezado con las seis columnas requeridas.')
                continue
            try:
                values={f:row[mapping[f]] if mapping[f]<len(row) else None for f in FIELDS}
                if any(isinstance(v,str) and v.startswith('=') for v in values.values()):raise ValueError('Use valores, no fórmulas.')
                values['codigo']=code(values['codigo'])
                for f in ('descripcion','unidad'):
                    v=values[f]
                    if v is None or not str(v).strip():raise ValueError('Falta '+f)
                    values[f]=str(v).strip()
                    if len(values[f])>300:raise ValueError(f+' demasiado largo.')
                for f in FIELDS[3:]:
                    v=values[f]
                    if isinstance(v,str) and re.fullmatch(r'\d+(\.\d+)?',v.strip()):v=float(v)
                    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1e12:raise ValueError(f+' debe ser un número no negativo.')
                    values[f]=float(v)
                if values['stock_utilizable']>values['stock_actual']:raise ValueError('El stock utilizable supera el actual.')
                if values['codigo'] in seen:raise ValueError('Código duplicado en el archivo.')
                seen.add(values['codigo']);values['fila_excel']=rn;result.append(values)
            except ValueError as e:errors.append({'fila':rn,'mensaje':str(e)})
        if mapping is None:raise ValueError('Faltan columnas: CODIGO, DESCRIPCION, UNIDAD, STOCK_ACTUAL, STOCK_UTILIZABLE y STOCK_SEGURIDAD.')
        if not result and not errors:raise ValueError('El archivo no tiene productos.')
    finally:wb.close()
    return result,errors

def preview(raw,filename,user,base):
 rows,errors=parse(raw)
 if errors:return {'valido':False,'errores':errors[:100],'total_errores':len(errors),'productos':len(rows)}
 current={r['codigo']:r for r in db.todos('productos_stock',{'select':'*','order':'codigo.asc'})}
 created=updated=0;plan=[]
 for row in rows:
  previous=current.get(row['codigo']);before=previous['contenido'] if previous else base.get(row['codigo']);isnew=before is None
  created+=isnew;updated+=not isnew
  plan.append({'despues':row,'antes':before,'revision':previous['revision'] if previous else None,'nuevo':isnew})
 id=str(uuid.uuid4());digest=hashlib.sha256(raw).hexdigest();name=Path(filename).name[:180]
 db.enviar('previas_stock','POST',body={'id':id,'usuario':user,'creado':time.time(),'archivo':name,'sha256':digest,'contenido':plan,'aplicado':False},prefer='return=minimal')
 return {'valido':True,'id':id,'nuevos':created,'actualizados':updated,'total':len(rows),'archivo':name,'sha256':digest,'muestra':[{'codigo':p['despues']['codigo'],'descripcion':p['despues']['descripcion'],'stock_anterior':p['antes'].get('stock_actual') if p['antes'] else None,'stock_nuevo':p['despues']['stock_actual'],'utilizable':p['despues']['stock_utilizable'],'seguridad':p['despues']['stock_seguridad'],'accion':'Nuevo' if p['nuevo'] else 'Actualizar'} for p in plan[:100]]}
def confirm(id,user):
 try:uuid.UUID(id)
 except ValueError:raise ValueError('Vista previa no válida.') from None
 try:return db.rpc('gest_stock_confirmar',{'p_id':id,'p_usuario':user})
 except db.CloudError as exc:
  if exc.status==400:raise ValueError(str(exc)) from None
  raise
def merged(base):
 out={k:dict(v) for k,v in base.items()}
 for r in db.todos('productos_stock',{'select':'codigo,contenido','order':'codigo.asc'}):
  product={**r['contenido'],'importado':True};out[r['codigo']]={**out.get(r['codigo'],{}),**product}
 return out
