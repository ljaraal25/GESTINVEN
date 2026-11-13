"""Consultas de evaluación sobre un archivo SQLite importado, abierto en solo lectura."""
from pathlib import Path
from contextlib import closing
from datetime import datetime, timezone
import sqlite3, json, os, hashlib, uuid, time
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "evaluacion.sqlite3"
def database_path():
    return Path(os.environ.get("GESTINVEN_EVAL_DB", str(DEFAULT_DB))).resolve()
def connect():
    path = database_path()
    if not path.is_file():
        raise FileNotFoundError("Falta importar data/evaluacion.sqlite3.")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db

BASE = """
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM movimientos m JOIN semanas s
 ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo
 WHERE m.exclusion IS NULL
), cierres AS (
 SELECT *, ROW_NUMBER() OVER (
 PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC
 ) AS ultimo,
 ROW_NUMBER() OVER (
 PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila
 ) AS primero FROM base
)
"""
# Partition by product NAME to preserve the workbook's operational definition.
QUIEBRES = BASE + """
SELECT codigo,producto,fecha,saldo,documento,lote,hoja,fila,numero_original
FROM cierres
WHERE etapa=:etapa AND semana=:semana AND ultimo=1 AND saldo<=1
AND (:codigo='' OR codigo=:codigo)
ORDER BY saldo,codigo,producto
"""
CIERRES_DETALLE = BASE + """
SELECT codigo,producto,fecha,saldo,CASE WHEN saldo<=1 THEN 1 ELSE 0 END AS quiebre,hoja,fila
FROM cierres WHERE etapa=:etapa AND semana=:semana AND ultimo=1
AND (:codigo='' OR codigo=:codigo) ORDER BY codigo,producto
"""
APERTURAS = BASE + """
SELECT codigo,producto,fecha,saldo,ingreso,salida,saldo-ingreso+salida AS apertura_reconstruida,
CASE WHEN saldo IS NULL OR ingreso IS NULL OR salida IS NULL THEN 'NO_CALCULABLE'
WHEN saldo-ingreso+salida<0 THEN 'APERTURA_NEGATIVA' ELSE 'RECONSTRUIDA_PENDIENTE_DE_DOCUMENTO' END AS estado,
hoja,fila FROM cierres WHERE etapa=:etapa AND semana=:semana AND primero=1
AND (:codigo='' OR codigo=:codigo) ORDER BY apertura_reconstruida,codigo
"""
MERMAS = BASE + """
SELECT codigo,producto,fecha,salida AS unidades_perdidas,documento,lote,motivo,hoja,fila
FROM base
WHERE etapa=:etapa AND semana=:semana
AND motivo_clave='PERDIDA POR VENCIMIENTO'
AND (:codigo='' OR codigo=:codigo)
ORDER BY salida DESC,codigo,fecha,fila
"""
EVALUADOS = BASE + """, anteriores AS (
 SELECT *, LAG(saldo) OVER (
 PARTITION BY producto ORDER BY fecha,numero_orden,fila
 ) AS saldo_anterior
 FROM movimientos WHERE exclusion IS NULL AND fecha IS NOT NULL
), revisados AS (
 SELECT b.*, a.saldo_anterior,
 CASE
 WHEN b.completo=0 THEN 'INCOMPLETO'
 WHEN b.ingreso IS NULL OR b.salida IS NULL OR b.saldo IS NULL
   OR b.ingreso<0 OR b.salida<0 OR b.saldo<0 THEN 'CANTIDADES_INVALIDAS'
 WHEN NOT (
   (b.tipo='INGRESO' AND b.ingreso>0 AND b.salida=0 AND b.documento_clave='PECOSA / ABASTECIMIENTO SISMED')
   OR (b.tipo='SALIDA' AND b.salida>0 AND b.ingreso=0 AND b.documento_clave IN ('RECETA / DISPENSACION','ACTA DE BAJA / VENCIMIENTO'))
   OR (b.tipo='AJUSTE' AND b.ingreso=0 AND b.salida=0 AND b.documento_clave='AJUSTE DE INVENTARIO')
 ) THEN 'TIPO_O_DOCUMENTO_INCONSISTENTE'
 WHEN a.saldo_anterior IS NULL THEN 'SIN_APERTURA_VERIFICADA'
 WHEN ABS(b.saldo-(a.saldo_anterior+b.ingreso-b.salida))>0.000001 THEN 'SALDO_INCONSISTENTE'
 ELSE 'COMPLETO_CONSISTENTE' END AS estado
 FROM base b JOIN anteriores a ON b.id=a.id
)
"""
ERRORES = EVALUADOS + """
SELECT codigo,producto,fecha,estado,saldo_anterior,ingreso,salida,saldo,
 campos_faltantes,documento,hoja,fila
FROM revisados
WHERE etapa=:etapa AND semana=:semana AND estado<>'COMPLETO_CONSISTENTE'
AND (:codigo='' OR codigo=:codigo)
ORDER BY estado,codigo,fecha,fila
"""
MOVIMIENTOS = """
SELECT etapa,numero_original,codigo,producto,fecha,tipo,documento,lote,
 registro_sanitario,ingreso,salida,saldo,motivo,exclusion,hoja,fila
FROM movimientos WHERE etapa=:etapa
AND (:semana=0 OR (fecha>=(SELECT desde FROM semanas WHERE etapa=:etapa AND semana=:semana)
 AND fecha<(SELECT fin_exclusivo FROM semanas WHERE etapa=:etapa AND semana=:semana)))
AND (:codigo='' OR codigo=:codigo)
ORDER BY fecha,numero_orden,fila
"""
RESUMEN = EVALUADOS + """, q AS (
 SELECT etapa,semana,COUNT(*) AS productos,
 SUM(CASE WHEN saldo<=1 THEN 1 ELSE 0 END) AS quiebres,
 SUM(CASE WHEN saldo IS NULL THEN 1 ELSE 0 END) AS cierres_sin_saldo,
 SUM(CASE WHEN saldo<0 THEN 1 ELSE 0 END) AS cierres_negativos
 FROM cierres WHERE ultimo=1 GROUP BY etapa,semana
), apertura AS (
 SELECT etapa,semana,SUM(saldo-ingreso+salida) AS qr,
 SUM(CASE WHEN saldo IS NULL OR ingreso IS NULL OR salida IS NULL THEN 1 ELSE 0 END) AS aperturas_no_calculables,
 SUM(CASE WHEN saldo-ingreso+salida<0 THEN 1 ELSE 0 END) AS aperturas_negativas,
 SUM(CASE WHEN saldo-ingreso+salida<0 THEN saldo-ingreso+salida ELSE 0 END) AS saldo_aperturas_negativas,
 MIN(saldo-ingreso+salida) AS apertura_minima
 FROM cierres WHERE primero=1 GROUP BY etapa,semana
), perdidas AS (
 SELECT etapa,semana,SUM(CASE WHEN motivo_clave='PERDIDA POR VENCIMIENTO' THEN salida ELSE 0 END) AS qp,
 SUM(CASE WHEN motivo_clave='PERDIDA POR VENCIMIENTO' AND salida IS NULL THEN 1 ELSE 0 END) AS perdidas_no_calculables
 FROM base GROUP BY etapa,semana
), e AS (
 SELECT etapa,semana,COUNT(*) AS evaluados,
 SUM(CASE WHEN estado='COMPLETO_CONSISTENTE' THEN 1 ELSE 0 END) AS consistentes,
 SUM(CASE WHEN estado='SIN_APERTURA_VERIFICADA' THEN 1 ELSE 0 END) AS sin_apertura
 FROM revisados GROUP BY etapa,semana
), referencia AS (
 SELECT etapa,semana,
 MAX(CASE WHEN indicador='quiebres' THEN valor_pct END) AS quiebres_excel_pct,
 MAX(CASE WHEN indicador='mermas' THEN valor_pct END) AS mermas_excel_pct,
 MAX(CASE WHEN indicador='eficiencia' THEN valor_pct END) AS eficiencia_excel_pct
 FROM tasas_reportadas GROUP BY etapa,semana
)
SELECT s.etapa,s.semana,s.desde,s.hasta,
 q.productos,q.quiebres,q.cierres_sin_saldo,
 CASE WHEN q.cierres_sin_saldo=0 THEN 100.0*q.quiebres/NULLIF(q.productos,0) END AS quiebres_pct,
 apertura.qr,perdidas.qp,apertura.aperturas_no_calculables,apertura.aperturas_negativas,
 CASE WHEN apertura.aperturas_no_calculables=0 AND perdidas.perdidas_no_calculables=0 AND apertura.qr>0
 THEN 100.0*perdidas.qp/apertura.qr END AS mermas_pct,
 e.evaluados,e.consistentes,e.sin_apertura,
 100.0*e.consistentes/NULLIF(e.evaluados,0) AS eficiencia_verificada_pct,
 100.0*e.consistentes/NULLIF(e.evaluados,0) AS eficiencia_pct,
 q.cierres_negativos,apertura.saldo_aperturas_negativas,apertura.apertura_minima,perdidas.perdidas_no_calculables,
 e.evaluados-e.consistentes-e.sin_apertura AS registros_con_incidencias,
 100.0*(e.consistentes+e.sin_apertura)/NULLIF(e.evaluados,0) AS eficiencia_limite_superior_pct,
 CASE WHEN e.sin_apertura>0 THEN 'COTA_MINIMA_VERIFICADA' ELSE 'CALCULO_CON_BASE_COMPLETA' END AS eficiencia_alcance,
 CASE WHEN q.productos IS NULL THEN 'SIN_DATOS'
 WHEN q.cierres_sin_saldo>0 THEN 'CIERRES_SIN_SALDO'
 WHEN q.cierres_negativos>0 THEN 'SALDOS_NEGATIVOS_AL_CIERRE'
 ELSE 'SIN_INCIDENCIAS_AUTOMATICAS' END AS validacion_quiebres,
 CASE WHEN apertura.qr IS NULL THEN 'SIN_DATOS'
 WHEN apertura.aperturas_no_calculables>0 OR perdidas.perdidas_no_calculables>0 THEN 'DATOS_INCOMPLETOS'
 WHEN apertura.qr<=0 THEN 'DENOMINADOR_NO_POSITIVO'
 WHEN apertura.aperturas_negativas>0 THEN 'APERTURAS_NEGATIVAS'
 ELSE 'SIN_INCIDENCIAS_AUTOMATICAS' END AS validacion_mermas,
 CASE WHEN e.evaluados IS NULL THEN 'SIN_DATOS'
 WHEN e.sin_apertura>0 THEN 'SALDO_ANTERIOR_PENDIENTE'
 ELSE 'BASE_DETERMINABLE' END AS validacion_eficiencia,
 referencia.quiebres_excel_pct,referencia.mermas_excel_pct,referencia.eficiencia_excel_pct
FROM semanas s LEFT JOIN q USING(etapa,semana)
LEFT JOIN apertura USING(etapa,semana) LEFT JOIN perdidas USING(etapa,semana)
LEFT JOIN e USING(etapa,semana) LEFT JOIN referencia USING(etapa,semana)
ORDER BY s.etapa DESC,s.semana
"""

INDICADORES = """
WITH r AS (SELECT * FROM v_resumen_semanal)
SELECT etapa,semana,desde,hasta,'quiebres' AS indicador,
 quiebres AS numerador,productos AS denominador,quiebres_pct AS porcentaje_calculado,
 quiebres_excel_pct AS porcentaje_excel,validacion_quiebres AS validacion,
 'INDICADOR_DE_CIERRE' AS alcance,cierres_sin_saldo AS registros_pendientes,
 aperturas_negativas,saldo_aperturas_negativas,
 printf('Cierres negativos: %d; cierres sin saldo: %d',cierres_negativos,cierres_sin_saldo) AS observacion
FROM r
UNION ALL
SELECT etapa,semana,desde,hasta,'mermas',qp,qr,mermas_pct,
 mermas_excel_pct,validacion_mermas,'CALCULO_ARITMETICO_CON_VALIDACION_SEPARADA',
 aperturas_no_calculables+perdidas_no_calculables,
 aperturas_negativas,saldo_aperturas_negativas,
 printf('Aperturas negativas: %d; suma de sus saldos: %.2f; aperturas no calculables: %d; perdidas no calculables: %d',aperturas_negativas,saldo_aperturas_negativas,aperturas_no_calculables,perdidas_no_calculables)
FROM r
UNION ALL
SELECT etapa,semana,desde,hasta,'eficiencia',consistentes,evaluados,eficiencia_pct,
 eficiencia_excel_pct,validacion_eficiencia,eficiencia_alcance,sin_apertura,
 aperturas_negativas,saldo_aperturas_negativas,
 printf('Registros sin saldo anterior verificable: %d; porcentaje mostrado es cota minima cuando hay pendientes',sin_apertura)
FROM r
"""

REPORTADO = """
SELECT etapa,semana,indicador,valor_pct,hoja,celda
FROM tasas_reportadas ORDER BY indicador,etapa,semana
"""
QUERIES = {
 "quiebres": ("Productos con quiebre al cierre semanal", QUIEBRES),
 "cierres": ("Todos los saldos de cierre semanal", CIERRES_DETALLE),
 "aperturas": ("Saldos de apertura reconstruidos y sus incidencias", APERTURAS),
 "mermas": ("Movimientos con pérdidas por vencimiento", MERMAS),
 "errores": ("Registros con incidencias o sin apertura verificable", ERRORES),
 "movimientos": ("Movimientos del período, incluidos los excluidos", MOVIMIENTOS),
 "comparativo": ("Indicadores semanales calculados con SQL", RESUMEN),
 "reportado": ("Tasas reportadas en las fichas del Excel", REPORTADO),
}
METHOD = {
 "quiebres": "Último saldo de cada nombre de producto por semana. Umbral saldo <= 1. Orden: fecha, número original y fila del Excel. Debe confirmarse el orden intradía con los documentos del almacén.",
 "mermas": "Qp: salidas con motivo Pérdida por vencimiento. Qr: suma de (saldo - ingreso + salida) del primer movimiento semanal de cada producto; apertura reconstruida algebraicamente. El porcentaje se calcula aunque existan aperturas negativas; validación y saldos negativos se muestran por separado. Datos faltantes o un denominador no positivo impiden calcularlo.",
 "eficiencia": "12 campos de CODIGO a MOTIVO, coherencia de tipo/documento/cantidades y saldo respecto al movimiento anterior no excluido. Sin saldo previo, el registro queda pendiente y no se presume correcto. La tasa calculada es registros verificados / evaluados; si hay pendientes, es una cota mínima, no una estimación completa de eficiencia. Se muestra también el límite superior posible y el porcentaje reportado en el Excel. Una incidencia se clasifica por el primer criterio incumplido.",
 "comparacion": "Semana ordinal 1–8 de períodos diferentes. Sin datos no equivale a cero. Los resultados SQL se contrastan con las tasas reportadas, sin forzar coincidencias.",
}
def metadata():
    with closing(connect()) as db:
        source = dict(db.execute("SELECT * FROM importacion").fetchone())
        periods = [dict(r) for r in db.execute("SELECT * FROM semanas ORDER BY etapa DESC,semana")]
        counts = [dict(r) for r in db.execute("SELECT etapa,COUNT(*) AS registros,SUM(exclusion IS NOT NULL) AS excluidos FROM movimientos GROUP BY etapa")]
        issues = [dict(r) for r in db.execute("SELECT * FROM observaciones ORDER BY id")]
    return {"fuente":source,"semanas":periods,"conteos":counts,"observaciones":issues,
            "version_calculo":"2.1","metodologia":METHOD,"consultas":[{"id":k,"nombre":v[0]} for k,v in QUERIES.items()],
            "auditoria_persistente_declarada":os.environ.get("GESTINVEN_AUDIT_PERSISTENT")=="1"}

def execute(name, etapa="POST", semana=1, codigo="", limit=100, offset=0):
    if name not in QUERIES: raise ValueError("Consulta no permitida.")
    if etapa not in ("PRE","POST"): raise ValueError("Etapa no válida.")
    if not 1<=semana<=8: raise ValueError("Semana fuera de rango.")
    if not 1<=limit<=500 or offset<0: raise ValueError("Paginación no válida.")
    if codigo:
        if not codigo.isdigit() or len(codigo)>12: raise ValueError("Código no válido.")
        codigo=str(int(codigo)).zfill(5)
    params={"etapa":etapa,"semana":semana,"codigo":codigo}
    sql=QUERIES[name][1].strip()
    started=time.perf_counter()
    at=datetime.now(timezone.utc).isoformat()
    # Every execution reads SQLite; no response cache or imported result arrays.
    with closing(connect()) as db:
        db.set_progress_handler(lambda: 1 if time.perf_counter()-started>8 else 0, 10000)
        total=db.execute("SELECT COUNT(*) FROM ("+sql+")",params).fetchone()[0]
        params_page={**params,"limite":limit,"desplazamiento":offset}
        actual_sql=sql+"\nLIMIT :limite OFFSET :desplazamiento"
        rows=[dict(r) for r in db.execute(actual_sql,params_page)]
        source=dict(db.execute("SELECT * FROM importacion").fetchone())
    return {"consulta":name,"titulo":QUERIES[name][0],"ejecucion_id":str(uuid.uuid4()),
            "ejecutado_utc":at,"duracion_ms":round((time.perf_counter()-started)*1000,3),
            "sql":actual_sql,"parametros":params_page,"total":total,"filas":rows,
            "fuente":source,"metodologia":METHOD,"solo_lectura":True}

def audit_path():
    default=DEFAULT_DB.parent / "evaluacion_auditoria.sqlite3"
    return Path(os.environ.get("GESTINVEN_AUDIT_DB",str(default))).resolve()

def log_execution(result, user):
    path=audit_path()
    if path==database_path(): raise ValueError("La auditoría debe usar otro archivo.")
    path.parent.mkdir(parents=True,exist_ok=True)
    record={"ejecucion_id":result["ejecucion_id"],"fecha_utc":result["ejecutado_utc"],
            "usuario":user,"consulta":result["consulta"],"parametros":result["parametros"],
            "total":result["total"],"duracion_ms":result["duracion_ms"],
            "fuente_sha256":result["fuente"]["sha256"],
            "sql_sha256":hashlib.sha256(result["sql"].encode()).hexdigest(),
            "resultado_pagina_sha256":hashlib.sha256(json.dumps(result["filas"],ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()}
    payload=json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    with closing(sqlite3.connect(path,timeout=10)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY,ejecucion_id TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,anterior TEXT NOT NULL,huella TEXT NOT NULL)")
        db.execute("CREATE TRIGGER IF NOT EXISTS sin_edicion BEFORE UPDATE ON auditoria BEGIN SELECT RAISE(ABORT,'Solo inserciones'); END")
        db.execute("CREATE TRIGGER IF NOT EXISTS sin_borrado BEFORE DELETE ON auditoria BEGIN SELECT RAISE(ABORT,'Solo inserciones'); END")
        db.execute("BEGIN IMMEDIATE")
        previous=db.execute("SELECT huella FROM auditoria ORDER BY id DESC LIMIT 1").fetchone()
        previous=previous[0] if previous else ""
        digest=hashlib.sha256((previous+"\n"+payload).encode()).hexdigest()
        db.execute("INSERT INTO auditoria(ejecucion_id,payload,anterior,huella) VALUES(?,?,?,?)",(result["ejecucion_id"],payload,previous,digest))
        db.commit()
    return {"guardada":True,"huella":digest,
            "persistencia_configurada":os.environ.get("GESTINVEN_AUDIT_PERSISTENT")=="1"}

def audit_events(limit=100):
    path=audit_path()
    if not path.is_file(): return {"eventos":[],"cadena_valida":True,"total":0}
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=10)) as db:
        rows=db.execute("SELECT id,payload,anterior,huella FROM auditoria ORDER BY id").fetchall()
    previous=""; valid=True
    for _,payload,prev,digest in rows:
        expected=hashlib.sha256((previous+"\n"+payload).encode()).hexdigest()
        if prev!=previous or digest!=expected: valid=False
        previous=digest
    events=[{**json.loads(p),"huella":h} for _,p,_,h in rows[-limit:]][::-1]
    return {"eventos":events,"cadena_valida":valid,"total":len(rows),
            "nota":"Registro creado desde la integración; no acredita operaciones históricas. La cadena no sustituye una firma externa ni impide la sustitución del archivo por un administrador."}
