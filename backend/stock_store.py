"""Stock operativo: importación de existencias absolutas, con vista previa y auditoría."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
import os,sqlite3,json,time,uuid,hashlib,io,zipfile,unicodedata,re,math
import openpyxl
from xml.etree.ElementTree import ParseError
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
def now():return datetime.now(timezone.utc).isoformat()
def path():return Path(os.environ.get('GESTINVEN_STOCK_DB',str(Path(__file__).resolve().parent.parent/'data/stock_operativo.sqlite3'))).resolve()
@contextmanager
def connect():
    p=path();p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(p,timeout=15);db.row_factory=sqlite3.Row
    try:
        db.executescript("""
CREATE TABLE IF NOT EXISTS productos(codigo TEXT PRIMARY KEY,contenido TEXT NOT NULL,revision TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS previas(id TEXT PRIMARY KEY,usuario TEXT NOT NULL,creado REAL NOT NULL,archivo TEXT NOT NULL,sha256 TEXT NOT NULL,contenido TEXT NOT NULL,aplicado INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS importaciones(id TEXT PRIMARY KEY,fecha_utc TEXT NOT NULL,usuario TEXT NOT NULL,archivo TEXT NOT NULL,sha256 TEXT NOT NULL,nuevos INTEGER NOT NULL,actualizados INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cambios(id INTEGER PRIMARY KEY,importacion_id TEXT NOT NULL,codigo TEXT NOT NULL,antes_json TEXT,despues_json TEXT NOT NULL);
""")
        yield db
    finally:db.close()
def existing(db,c):
    row=db.execute('SELECT contenido,revision FROM productos WHERE codigo=?',(c,)).fetchone()
    return (json.loads(row['contenido']),row['revision']) if row else (None,None)
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
    created=updated=0;plan=[]
    with connect() as db:
        for row in rows:
            previous,revision=existing(db,row['codigo'])
            before=previous or base.get(row['codigo'])
            isnew=before is None
            created+=isnew;updated+=not isnew
            plan.append({'despues':row,'antes':before,'revision':revision,'nuevo':isnew})
        id=str(uuid.uuid4());digest=hashlib.sha256(raw).hexdigest()
        db.execute('INSERT INTO previas VALUES(?,?,?,?,?,?,0)',(id,user,time.time(),Path(filename).name[:180],digest,json.dumps(plan,ensure_ascii=False)))
        db.commit()
    return {'valido':True,'id':id,'nuevos':created,'actualizados':updated,'total':len(rows),'archivo':Path(filename).name[:180],'sha256':digest,
            'muestra':[{'codigo':p['despues']['codigo'],'descripcion':p['despues']['descripcion'],'stock_anterior':p['antes'].get('stock_actual') if p['antes'] else None,'stock_nuevo':p['despues']['stock_actual'],'utilizable':p['despues']['stock_utilizable'],'seguridad':p['despues']['stock_seguridad'],'accion':'Nuevo' if p['nuevo'] else 'Actualizar'} for p in plan[:100]]}
def confirm(id,user):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        record=db.execute('SELECT * FROM previas WHERE id=? AND usuario=?',(id,user)).fetchone()
        if not record:raise ValueError('Vista previa no encontrada.')
        if record['aplicado']:raise ValueError('Esta carga ya fue aplicada.')
        if time.time()-record['creado']>1800:raise ValueError('Vista previa vencida; valide otra vez el archivo.')
        plan=json.loads(record['contenido'])
        for p in plan:
            _,revision=existing(db,p['despues']['codigo'])
            if revision!=p['revision']:raise ValueError('El stock cambió desde la vista previa. Valide otra vez.')
        timestamp=now()
        for p in plan:
            row=p['despues'];row['actualizado_utc']=timestamp;row['importacion_id']=id
            content=json.dumps(row,ensure_ascii=False)
            db.execute('INSERT INTO productos VALUES(?,?,?) ON CONFLICT(codigo) DO UPDATE SET contenido=excluded.contenido,revision=excluded.revision',(row['codigo'],content,id))
            db.execute('INSERT INTO cambios(importacion_id,codigo,antes_json,despues_json) VALUES(?,?,?,?)',(id,row['codigo'],json.dumps(p['antes'],ensure_ascii=False),content))
        nuevos=sum(p['nuevo'] for p in plan)
        db.execute('INSERT INTO importaciones VALUES(?,?,?,?,?,?,?)',(id,timestamp,user,record['archivo'],record['sha256'],nuevos,len(plan)-nuevos))
        db.execute('UPDATE previas SET aplicado=1 WHERE id=?',(id,));db.commit()
    return {'guardado':True,'id':id,'fecha_utc':timestamp,'nuevos':nuevos,'actualizados':len(plan)-nuevos,'total':len(plan)}
def merged(base):
    out={k:dict(v) for k,v in base.items()}
    with connect() as db:
        for row in db.execute('SELECT contenido FROM productos'):
            p=json.loads(row[0]);p['importado']=True;out[p['codigo']]={**out.get(p['codigo'],{}),**p}
    return out
