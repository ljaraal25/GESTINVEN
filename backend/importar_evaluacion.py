"""Importación reproducible del Excel a SQLite, sin alterar el archivo original."""
from contextlib import closing
import argparse, hashlib, json, math, os, sqlite3, unicodedata
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
import openpyxl
SCHEMA="""
CREATE TABLE importacion(id INTEGER PRIMARY KEY CHECK(id=1),archivo TEXT NOT NULL,sha256 TEXT NOT NULL,importado_utc TEXT NOT NULL,procedencia_declarada TEXT NOT NULL,documentos_originales TEXT NOT NULL,version_metodo TEXT NOT NULL);
CREATE TABLE semanas(etapa TEXT NOT NULL CHECK(etapa IN ('PRE','POST')),semana INTEGER NOT NULL CHECK(semana BETWEEN 1 AND 8),desde TEXT NOT NULL,hasta TEXT NOT NULL,fin_exclusivo TEXT NOT NULL,PRIMARY KEY(etapa,semana));
CREATE TABLE movimientos(id INTEGER PRIMARY KEY,etapa TEXT NOT NULL,numero_original TEXT,numero_orden REAL NOT NULL,codigo TEXT,producto TEXT,tip TEXT,fecha TEXT,tipo TEXT,documento TEXT,documento_clave TEXT,lote TEXT,registro_sanitario TEXT,ingreso REAL,salida REAL,saldo REAL,motivo TEXT,motivo_clave TEXT,exclusion TEXT,hoja TEXT NOT NULL,fila INTEGER NOT NULL,completo INTEGER NOT NULL,campos_faltantes TEXT NOT NULL,original_json TEXT NOT NULL,UNIQUE(hoja,fila));
CREATE INDEX idx_movimientos_periodo ON movimientos(etapa,fecha,producto);
CREATE INDEX idx_movimientos_codigo ON movimientos(codigo,fecha);
CREATE TABLE tasas_reportadas(etapa TEXT NOT NULL,semana INTEGER NOT NULL,indicador TEXT NOT NULL,valor_pct REAL NOT NULL,hoja TEXT NOT NULL,celda TEXT NOT NULL,numerador_original TEXT,denominador_original TEXT,PRIMARY KEY(etapa,semana,indicador));
CREATE TABLE observaciones(id INTEGER PRIMARY KEY,referencia TEXT NOT NULL,detalle TEXT NOT NULL);
"""
FIELDS=["CODIGO","NOMBRE DEL PRODUCTO","Tip","FECHA","TIPO DE MOVIMIENTO","DOCUMENTO / ORIGEN","LOTE","REG. SANIT","INGRESO","SALIDA","SALDO","MOTIVO"]
def text(v):
    return None if v is None or str(v).strip()=="" else str(v).strip()
def key(v):
    return "".join(c for c in unicodedata.normalize("NFD",text(v) or "") if unicodedata.category(c)!="Mn").upper()
def number(v):
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) else None
def code(v):
    if isinstance(v,(int,float)) and number(v) is not None and float(v).is_integer(): return str(int(v)).zfill(5)
    s=text(v)
    return s.zfill(5) if s and s.isdigit() else s
def serial(v):
    return v.isoformat() if isinstance(v,(date,datetime)) else v
def build(source, output, replace=False):
    source=Path(source).resolve(); output=Path(output).resolve()
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists() and not replace:
        with closing(sqlite3.connect(output.as_uri()+"?mode=ro",uri=True)) as db:
            previous=db.execute("SELECT sha256 FROM importacion").fetchone()[0]
        if previous==digest:
            print("La misma fuente ya está importada; no se duplicaron registros.")
            return output
        raise ValueError("Existe otra versión de la base. Use otra salida o --reemplazar después de respaldarla.")
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_name(output.name+".importando")
    if temp.exists(): raise FileExistsError("Existe una importación temporal; revísela antes de continuar.")
    w=openpyxl.load_workbook(source,read_only=True,data_only=True)
    db=sqlite3.connect(temp)
    try:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO importacion VALUES(1,?,?,?,?,?,?)",(source.name,digest,datetime.now(timezone.utc).isoformat(),"Registros del almacén, según declaración de la investigadora","Pendientes de vinculación y validación","1.0"))
        for etapa,name in [("PRE","TABLA_PRE-TEST"),("POST","TABLA_POST")]:
            s=w[f"QUIEBRES_{etapa}"]
            for week in range(1,9):
                a=s.cell(12+week,2).value; b=s.cell(12+week,3).value
                if not isinstance(a,datetime) or not isinstance(b,datetime) or (b-a).days!=6:
                    raise ValueError("Fechas de semana no reconocidas.")
                db.execute("INSERT INTO semanas VALUES(?,?,?,?,?)",(etapa,week,a.date().isoformat(),b.date().isoformat(),(b+timedelta(days=1)).date().isoformat()))
            for rn,row in enumerate(w[name].iter_rows(min_row=7,max_col=14,values_only=True),7):
                if not any(v is not None for v in row): continue
                fecha=row[4].date().isoformat() if isinstance(row[4],datetime) else row[4].isoformat() if isinstance(row[4],date) else None
                missing=[FIELDS[i-1] for i in range(1,13) if text(row[i]) is None]
                original=json.dumps([serial(v) for v in row],ensure_ascii=False,allow_nan=False)
                values=(etapa,text(row[0]),number(row[0]) if number(row[0]) is not None else rn,code(row[1]),text(row[2]),text(row[3]),fecha,key(row[5]),text(row[6]),key(row[6]),text(row[7]),text(row[8]),number(row[9]),number(row[10]),number(row[11]),text(row[12]),key(row[12]),text(row[13]),name,rn,int(not missing),", ".join(missing),original)
                db.execute("INSERT INTO movimientos(etapa,numero_original,numero_orden,codigo,producto,tip,fecha,tipo,documento,documento_clave,lote,registro_sanitario,ingreso,salida,saldo,motivo,motivo_clave,exclusion,hoja,fila,completo,campos_faltantes,original_json) VALUES("+",".join("?" for _ in values)+")",values)
                if fecha is None and text(row[13]) is None:
                    db.execute("INSERT INTO observaciones(referencia,detalle) VALUES(?,?)",(f"{name}!E{rn}","Fecha no reconocida sin motivo de exclusión."))
            for prefix,metric in [("QUIEBRES","quiebres"),("MERMAS","mermas"),("EFICIENCIA","eficiencia")]:
                s=w[f"{prefix}_{etapa}"]
                for i in range(1,9):
                    r=12+i; value=s.cell(r,7).value
                    if not isinstance(value,str) or not value.strip().endswith("%"):
                        raise ValueError(f"Tasa no reconocida en {s.title}!G{r}")
                    rate=float(value.strip()[:-1])
                    num=s.cell(r,5 if metric=="eficiencia" else 6).value
                    den=s.cell(r,4 if metric=="eficiencia" else 5).value
                    db.execute("INSERT INTO tasas_reportadas VALUES(?,?,?,?,?,?,?,?)",(etapa,i,metric,rate,s.title,f"G{r}",json.dumps(serial(num)),json.dumps(serial(den))))
                if etapa=="POST" and "pre" in str(s["E2"].value).lower():
                    db.execute("INSERT INTO observaciones(referencia,detalle) VALUES(?,?)",(f"{s.title}!E2","Encabezado Pre Test en ficha de postest."))
                for r in range(13,22):
                    for c in range(4,7):
                        v=s.cell(r,c).value
                        if isinstance(v,datetime) or isinstance(v,float) and not v.is_integer():
                            db.execute("INSERT INTO observaciones(referencia,detalle) VALUES(?,?)",(f"{s.title}!{s.cell(r,c).coordinate}",f"Conteo ambiguo almacenado como {serial(v)}. No se reinterpretó como miles."))
        if __package__:
            from . import evaluacion_store as sql_store
        else:
            import evaluacion_store as sql_store
        views = {
            'v_movimientos_analizados': sql_store.BASE + 'SELECT * FROM base',
            'v_cierres_semanales': sql_store.BASE + 'SELECT * FROM cierres WHERE ultimo=1',
            'v_aperturas_semanales': sql_store.BASE + 'SELECT *,saldo-ingreso+salida AS apertura_reconstruida FROM cierres WHERE primero=1',
            'v_evaluacion_registros': sql_store.EVALUADOS + 'SELECT * FROM revisados',
            'v_resumen_semanal': sql_store.RESUMEN,
            'v_indicadores_semanales': sql_store.INDICADORES,
        }
        for view, query in views.items():
            db.execute('CREATE VIEW ' + view + ' AS ' + query)
        db.commit()
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Fallo de integridad SQLite.")
        print(json.dumps({"fuente_sha256":digest,"conteos":db.execute("SELECT etapa,COUNT(*),SUM(exclusion IS NOT NULL) FROM movimientos GROUP BY etapa").fetchall(),"salida":str(output)},ensure_ascii=False))
    except BaseException:
        db.close(); w.close(); temp.unlink(missing_ok=True)
        raise
    else:
        db.close(); w.close(); os.replace(temp,output)
    return output
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("excel"); p.add_argument("--salida",default=str(Path(__file__).resolve().parent.parent/"data/evaluacion.sqlite3"))
    p.add_argument("--reemplazar",action="store_true")
    a=p.parse_args(); build(a.excel,a.salida,a.reemplazar)
