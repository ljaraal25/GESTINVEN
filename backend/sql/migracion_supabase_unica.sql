BEGIN;
CREATE TABLE IF NOT EXISTS public.fuentes_evaluacion(id integer PRIMARY KEY CHECK(id=1),contenido jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS public.movimientos_evaluacion(
 archivo_sha256 text NOT NULL,id bigint NOT NULL,etapa text NOT NULL,numero_original text,numero_orden double precision NOT NULL,
 codigo text,producto text,tip text,fecha date,tipo text,documento text,documento_clave text,lote text,registro_sanitario text,
 ingreso numeric,salida numeric,saldo numeric,motivo text,motivo_clave text,exclusion text,hoja text NOT NULL,fila integer NOT NULL,
 completo integer NOT NULL,campos_faltantes text NOT NULL,original_json text NOT NULL,PRIMARY KEY(archivo_sha256,id),UNIQUE(archivo_sha256,hoja,fila));
CREATE INDEX IF NOT EXISTS movimientos_evaluacion_periodo_idx ON public.movimientos_evaluacion(archivo_sha256,etapa,fecha,producto);
CREATE INDEX IF NOT EXISTS movimientos_evaluacion_codigo_idx ON public.movimientos_evaluacion(codigo,fecha);
CREATE TABLE IF NOT EXISTS public.observaciones_evaluacion(id bigint PRIMARY KEY,referencia text NOT NULL,detalle text NOT NULL);
CREATE TABLE IF NOT EXISTS public.auditoria_consultas(
 ejecucion_id uuid PRIMARY KEY,payload text NOT NULL,anterior text NOT NULL DEFAULT '',huella text NOT NULL,
 origen text NOT NULL,fecha_utc timestamptz NOT NULL,importado_en timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.productos_stock(codigo text PRIMARY KEY,contenido jsonb NOT NULL,revision uuid NOT NULL);
CREATE TABLE IF NOT EXISTS public.previas_stock(id uuid PRIMARY KEY,usuario text NOT NULL,creado double precision NOT NULL,
 archivo text NOT NULL,sha256 text NOT NULL,contenido jsonb NOT NULL,aplicado boolean NOT NULL DEFAULT false);
CREATE TABLE IF NOT EXISTS public.importaciones_stock(id uuid PRIMARY KEY,fecha_utc timestamptz NOT NULL,usuario text NOT NULL,archivo text NOT NULL,sha256 text NOT NULL,nuevos integer NOT NULL,actualizados integer NOT NULL);
CREATE TABLE IF NOT EXISTS public.cambios_stock(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,importacion_id uuid NOT NULL REFERENCES public.importaciones_stock(id),codigo text NOT NULL,antes_json jsonb,despues_json jsonb NOT NULL);
CREATE VIEW public.v_movimientos_fuente WITH(security_invoker=true) AS SELECT m.* FROM public.movimientos_evaluacion m
WHERE m.archivo_sha256=(SELECT contenido->>'sha256' FROM public.fuentes_evaluacion WHERE id=1);
CREATE VIEW public.v_semanas_base WITH(security_invoker=true) AS SELECT p.etapa,s.numero_semana AS semana,s.fecha_inicio AS desde,s.fecha_fin AS hasta,s.fecha_fin+1 AS fin_exclusivo FROM public.semanas_evaluacion s JOIN public.periodos_evaluacion p ON p.id=s.periodo_id;
CREATE VIEW public.v_tasas_reportadas WITH(security_invoker=true) AS SELECT p.etapa,s.numero_semana AS semana,lower(i.codigo) AS indicador,r.porcentaje AS valor_pct,r.hoja_origen AS hoja,r.celda_origen AS celda FROM public.resultados_semanales r JOIN public.semanas_evaluacion s ON s.id=r.semana_id JOIN public.periodos_evaluacion p ON p.id=s.periodo_id JOIN public.indicadores i ON i.id=r.indicador_id WHERE r.fuente='EXCEL' AND r.archivo_sha256=(SELECT contenido->>'sha256' FROM public.fuentes_evaluacion WHERE id=1);
CREATE VIEW public.v_movimientos_analizados WITH(security_invoker=true) AS 
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s
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
SELECT * FROM base;
CREATE VIEW public.v_cierres_semanales WITH(security_invoker=true) AS 
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s
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
SELECT * FROM cierres WHERE ultimo=1;
CREATE VIEW public.v_aperturas_semanales WITH(security_invoker=true) AS 
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s
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
SELECT *,saldo-ingreso+salida AS apertura_reconstruida FROM cierres WHERE primero=1;
CREATE VIEW public.v_evaluacion_registros WITH(security_invoker=true) AS 
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s
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
, anteriores AS (
 SELECT *, LAG(saldo) OVER (
 PARTITION BY producto ORDER BY fecha,numero_orden,fila
 ) AS saldo_anterior
 FROM public.v_movimientos_fuente WHERE exclusion IS NULL AND fecha IS NOT NULL
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
SELECT * FROM revisados;
CREATE VIEW public.v_resumen_semanal WITH(security_invoker=true) AS 
WITH base AS (
 SELECT m.*, s.semana, s.desde, s.hasta
 FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s
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
, anteriores AS (
 SELECT *, LAG(saldo) OVER (
 PARTITION BY producto ORDER BY fecha,numero_orden,fila
 ) AS saldo_anterior
 FROM public.v_movimientos_fuente WHERE exclusion IS NULL AND fecha IS NOT NULL
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
, q AS (
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
 FROM public.v_tasas_reportadas GROUP BY etapa,semana
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
FROM public.v_semanas_base s LEFT JOIN q USING(etapa,semana)
LEFT JOIN apertura USING(etapa,semana) LEFT JOIN perdidas USING(etapa,semana)
LEFT JOIN e USING(etapa,semana) LEFT JOIN referencia USING(etapa,semana)
ORDER BY s.etapa DESC,s.semana
;
CREATE VIEW public.v_indicadores_semanales WITH(security_invoker=true) AS 
WITH r AS (SELECT * FROM public.v_resumen_semanal)
SELECT etapa,semana,desde,hasta,'quiebres' AS indicador,
 quiebres AS numerador,productos AS denominador,quiebres_pct AS porcentaje_calculado,
 quiebres_excel_pct AS porcentaje_excel,validacion_quiebres AS validacion,
 'INDICADOR_DE_CIERRE' AS alcance,cierres_sin_saldo AS registros_pendientes,
 aperturas_negativas,saldo_aperturas_negativas,
 format('Cierres negativos: %s; cierres sin saldo: %s',cierres_negativos,cierres_sin_saldo) AS observacion
FROM r
UNION ALL
SELECT etapa,semana,desde,hasta,'mermas',qp,qr,mermas_pct,
 mermas_excel_pct,validacion_mermas,'CALCULO_ARITMETICO_CON_VALIDACION_SEPARADA',
 aperturas_no_calculables+perdidas_no_calculables,
 aperturas_negativas,saldo_aperturas_negativas,
 format('Aperturas negativas: %s; suma de sus saldos: %s; aperturas no calculables: %s; perdidas no calculables: %s',aperturas_negativas,saldo_aperturas_negativas,aperturas_no_calculables,perdidas_no_calculables)
FROM r
UNION ALL
SELECT etapa,semana,desde,hasta,'eficiencia',consistentes,evaluados,eficiencia_pct,
 eficiencia_excel_pct,validacion_eficiencia,eficiencia_alcance,sin_apertura,
 aperturas_negativas,saldo_aperturas_negativas,
 format('Registros sin saldo anterior verificable: %s; porcentaje mostrado es cota minima cuando hay pendientes',sin_apertura)
FROM r
;
CREATE FUNCTION public.gest_consulta(p_consulta text,p_etapa text,p_semana integer,p_codigo text,p_limite integer,p_desplazamiento integer) RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,public AS $fn$
DECLARE q text; filas jsonb; total bigint; inicio timestamptz:=clock_timestamp();
BEGIN
 IF p_etapa NOT IN ('PRE','POST') OR p_semana NOT BETWEEN 1 AND 8 OR p_limite NOT BETWEEN 1 AND 500 OR p_desplazamiento<0 OR p_codigo!~'^[0-9]*$' THEN RAISE EXCEPTION 'Parámetros inválidos'; END IF;
 q:=($queries${"quiebres": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n\nSELECT codigo,producto,fecha,saldo,documento,lote,hoja,fila,numero_original\nFROM cierres\nWHERE etapa=$1 AND semana=$2 AND ultimo=1 AND saldo<=1\nAND ($3='' OR codigo=$3)\nORDER BY saldo,codigo,producto", "cierres": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n\nSELECT codigo,producto,fecha,saldo,CASE WHEN saldo<=1 THEN 1 ELSE 0 END AS quiebre,hoja,fila\nFROM cierres WHERE etapa=$1 AND semana=$2 AND ultimo=1\nAND ($3='' OR codigo=$3) ORDER BY codigo,producto", "aperturas": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n\nSELECT codigo,producto,fecha,saldo,ingreso,salida,saldo-ingreso+salida AS apertura_reconstruida,\nCASE WHEN saldo IS NULL OR ingreso IS NULL OR salida IS NULL THEN 'NO_CALCULABLE'\nWHEN saldo-ingreso+salida<0 THEN 'APERTURA_NEGATIVA' ELSE 'RECONSTRUIDA_PENDIENTE_DE_DOCUMENTO' END AS estado,\nhoja,fila FROM cierres WHERE etapa=$1 AND semana=$2 AND primero=1\nAND ($3='' OR codigo=$3) ORDER BY apertura_reconstruida,codigo", "mermas": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n\nSELECT codigo,producto,fecha,salida AS unidades_perdidas,documento,lote,motivo,hoja,fila\nFROM base\nWHERE etapa=$1 AND semana=$2\nAND motivo_clave='PERDIDA POR VENCIMIENTO'\nAND ($3='' OR codigo=$3)\nORDER BY salida DESC,codigo,fecha,fila", "errores": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n, anteriores AS (\n SELECT *, LAG(saldo) OVER (\n PARTITION BY producto ORDER BY fecha,numero_orden,fila\n ) AS saldo_anterior\n FROM public.v_movimientos_fuente WHERE exclusion IS NULL AND fecha IS NOT NULL\n), revisados AS (\n SELECT b.*, a.saldo_anterior,\n CASE\n WHEN b.completo=0 THEN 'INCOMPLETO'\n WHEN b.ingreso IS NULL OR b.salida IS NULL OR b.saldo IS NULL\n   OR b.ingreso<0 OR b.salida<0 OR b.saldo<0 THEN 'CANTIDADES_INVALIDAS'\n WHEN NOT (\n   (b.tipo='INGRESO' AND b.ingreso>0 AND b.salida=0 AND b.documento_clave='PECOSA / ABASTECIMIENTO SISMED')\n   OR (b.tipo='SALIDA' AND b.salida>0 AND b.ingreso=0 AND b.documento_clave IN ('RECETA / DISPENSACION','ACTA DE BAJA / VENCIMIENTO'))\n   OR (b.tipo='AJUSTE' AND b.ingreso=0 AND b.salida=0 AND b.documento_clave='AJUSTE DE INVENTARIO')\n ) THEN 'TIPO_O_DOCUMENTO_INCONSISTENTE'\n WHEN a.saldo_anterior IS NULL THEN 'SIN_APERTURA_VERIFICADA'\n WHEN ABS(b.saldo-(a.saldo_anterior+b.ingreso-b.salida))>0.000001 THEN 'SALDO_INCONSISTENTE'\n ELSE 'COMPLETO_CONSISTENTE' END AS estado\n FROM base b JOIN anteriores a ON b.id=a.id\n)\n\nSELECT codigo,producto,fecha,estado,saldo_anterior,ingreso,salida,saldo,\n campos_faltantes,documento,hoja,fila\nFROM revisados\nWHERE etapa=$1 AND semana=$2 AND estado<>'COMPLETO_CONSISTENTE'\nAND ($3='' OR codigo=$3)\nORDER BY estado,codigo,fecha,fila", "movimientos": "SELECT etapa,numero_original,codigo,producto,fecha,tipo,documento,lote,\n registro_sanitario,ingreso,salida,saldo,motivo,exclusion,hoja,fila\nFROM public.v_movimientos_fuente WHERE etapa=$1\nAND ($2=0 OR (fecha>=(SELECT desde FROM public.v_semanas_base WHERE etapa=$1 AND semana=$2)\n AND fecha<(SELECT fin_exclusivo FROM public.v_semanas_base WHERE etapa=$1 AND semana=$2)))\nAND ($3='' OR codigo=$3)\nORDER BY fecha,numero_orden,fila", "comparativo": "WITH base AS (\n SELECT m.*, s.semana, s.desde, s.hasta\n FROM public.v_movimientos_fuente m JOIN public.v_semanas_base s\n ON m.etapa=s.etapa AND m.fecha>=s.desde AND m.fecha<s.fin_exclusivo\n WHERE m.exclusion IS NULL\n), cierres AS (\n SELECT *, ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha DESC,numero_orden DESC,fila DESC\n ) AS ultimo,\n ROW_NUMBER() OVER (\n PARTITION BY etapa,semana,producto ORDER BY fecha,numero_orden,fila\n ) AS primero FROM base\n)\n, anteriores AS (\n SELECT *, LAG(saldo) OVER (\n PARTITION BY producto ORDER BY fecha,numero_orden,fila\n ) AS saldo_anterior\n FROM public.v_movimientos_fuente WHERE exclusion IS NULL AND fecha IS NOT NULL\n), revisados AS (\n SELECT b.*, a.saldo_anterior,\n CASE\n WHEN b.completo=0 THEN 'INCOMPLETO'\n WHEN b.ingreso IS NULL OR b.salida IS NULL OR b.saldo IS NULL\n   OR b.ingreso<0 OR b.salida<0 OR b.saldo<0 THEN 'CANTIDADES_INVALIDAS'\n WHEN NOT (\n   (b.tipo='INGRESO' AND b.ingreso>0 AND b.salida=0 AND b.documento_clave='PECOSA / ABASTECIMIENTO SISMED')\n   OR (b.tipo='SALIDA' AND b.salida>0 AND b.ingreso=0 AND b.documento_clave IN ('RECETA / DISPENSACION','ACTA DE BAJA / VENCIMIENTO'))\n   OR (b.tipo='AJUSTE' AND b.ingreso=0 AND b.salida=0 AND b.documento_clave='AJUSTE DE INVENTARIO')\n ) THEN 'TIPO_O_DOCUMENTO_INCONSISTENTE'\n WHEN a.saldo_anterior IS NULL THEN 'SIN_APERTURA_VERIFICADA'\n WHEN ABS(b.saldo-(a.saldo_anterior+b.ingreso-b.salida))>0.000001 THEN 'SALDO_INCONSISTENTE'\n ELSE 'COMPLETO_CONSISTENTE' END AS estado\n FROM base b JOIN anteriores a ON b.id=a.id\n)\n, q AS (\n SELECT etapa,semana,COUNT(*) AS productos,\n SUM(CASE WHEN saldo<=1 THEN 1 ELSE 0 END) AS quiebres,\n SUM(CASE WHEN saldo IS NULL THEN 1 ELSE 0 END) AS cierres_sin_saldo,\n SUM(CASE WHEN saldo<0 THEN 1 ELSE 0 END) AS cierres_negativos\n FROM cierres WHERE ultimo=1 GROUP BY etapa,semana\n), apertura AS (\n SELECT etapa,semana,SUM(saldo-ingreso+salida) AS qr,\n SUM(CASE WHEN saldo IS NULL OR ingreso IS NULL OR salida IS NULL THEN 1 ELSE 0 END) AS aperturas_no_calculables,\n SUM(CASE WHEN saldo-ingreso+salida<0 THEN 1 ELSE 0 END) AS aperturas_negativas,\n SUM(CASE WHEN saldo-ingreso+salida<0 THEN saldo-ingreso+salida ELSE 0 END) AS saldo_aperturas_negativas,\n MIN(saldo-ingreso+salida) AS apertura_minima\n FROM cierres WHERE primero=1 GROUP BY etapa,semana\n), perdidas AS (\n SELECT etapa,semana,SUM(CASE WHEN motivo_clave='PERDIDA POR VENCIMIENTO' THEN salida ELSE 0 END) AS qp,\n SUM(CASE WHEN motivo_clave='PERDIDA POR VENCIMIENTO' AND salida IS NULL THEN 1 ELSE 0 END) AS perdidas_no_calculables\n FROM base GROUP BY etapa,semana\n), e AS (\n SELECT etapa,semana,COUNT(*) AS evaluados,\n SUM(CASE WHEN estado='COMPLETO_CONSISTENTE' THEN 1 ELSE 0 END) AS consistentes,\n SUM(CASE WHEN estado='SIN_APERTURA_VERIFICADA' THEN 1 ELSE 0 END) AS sin_apertura\n FROM revisados GROUP BY etapa,semana\n), referencia AS (\n SELECT etapa,semana,\n MAX(CASE WHEN indicador='quiebres' THEN valor_pct END) AS quiebres_excel_pct,\n MAX(CASE WHEN indicador='mermas' THEN valor_pct END) AS mermas_excel_pct,\n MAX(CASE WHEN indicador='eficiencia' THEN valor_pct END) AS eficiencia_excel_pct\n FROM public.v_tasas_reportadas GROUP BY etapa,semana\n)\nSELECT s.etapa,s.semana,s.desde,s.hasta,\n q.productos,q.quiebres,q.cierres_sin_saldo,\n CASE WHEN q.cierres_sin_saldo=0 THEN 100.0*q.quiebres/NULLIF(q.productos,0) END AS quiebres_pct,\n apertura.qr,perdidas.qp,apertura.aperturas_no_calculables,apertura.aperturas_negativas,\n CASE WHEN apertura.aperturas_no_calculables=0 AND perdidas.perdidas_no_calculables=0 AND apertura.qr>0\n THEN 100.0*perdidas.qp/apertura.qr END AS mermas_pct,\n e.evaluados,e.consistentes,e.sin_apertura,\n 100.0*e.consistentes/NULLIF(e.evaluados,0) AS eficiencia_verificada_pct,\n 100.0*e.consistentes/NULLIF(e.evaluados,0) AS eficiencia_pct,\n q.cierres_negativos,apertura.saldo_aperturas_negativas,apertura.apertura_minima,perdidas.perdidas_no_calculables,\n e.evaluados-e.consistentes-e.sin_apertura AS registros_con_incidencias,\n 100.0*(e.consistentes+e.sin_apertura)/NULLIF(e.evaluados,0) AS eficiencia_limite_superior_pct,\n CASE WHEN e.sin_apertura>0 THEN 'COTA_MINIMA_VERIFICADA' ELSE 'CALCULO_CON_BASE_COMPLETA' END AS eficiencia_alcance,\n CASE WHEN q.productos IS NULL THEN 'SIN_DATOS'\n WHEN q.cierres_sin_saldo>0 THEN 'CIERRES_SIN_SALDO'\n WHEN q.cierres_negativos>0 THEN 'SALDOS_NEGATIVOS_AL_CIERRE'\n ELSE 'SIN_INCIDENCIAS_AUTOMATICAS' END AS validacion_quiebres,\n CASE WHEN apertura.qr IS NULL THEN 'SIN_DATOS'\n WHEN apertura.aperturas_no_calculables>0 OR perdidas.perdidas_no_calculables>0 THEN 'DATOS_INCOMPLETOS'\n WHEN apertura.qr<=0 THEN 'DENOMINADOR_NO_POSITIVO'\n WHEN apertura.aperturas_negativas>0 THEN 'APERTURAS_NEGATIVAS'\n ELSE 'SIN_INCIDENCIAS_AUTOMATICAS' END AS validacion_mermas,\n CASE WHEN e.evaluados IS NULL THEN 'SIN_DATOS'\n WHEN e.sin_apertura>0 THEN 'SALDO_ANTERIOR_PENDIENTE'\n ELSE 'BASE_DETERMINABLE' END AS validacion_eficiencia,\n referencia.quiebres_excel_pct,referencia.mermas_excel_pct,referencia.eficiencia_excel_pct\nFROM public.v_semanas_base s LEFT JOIN q USING(etapa,semana)\nLEFT JOIN apertura USING(etapa,semana) LEFT JOIN perdidas USING(etapa,semana)\nLEFT JOIN e USING(etapa,semana) LEFT JOIN referencia USING(etapa,semana)\nORDER BY s.etapa DESC,s.semana", "reportado": "SELECT etapa,semana,indicador,valor_pct,hoja,celda\nFROM public.v_tasas_reportadas ORDER BY indicador,etapa,semana"}$queries$::jsonb)->>p_consulta;
 IF q IS NULL THEN RAISE EXCEPTION 'Consulta no permitida'; END IF;
 EXECUTE 'SELECT count(*) FROM ('||q||') t' INTO total USING p_etapa,p_semana,p_codigo;
 EXECUTE 'SELECT coalesce(jsonb_agg(to_jsonb(t)),''[]''::jsonb) FROM ('||q||' LIMIT $4 OFFSET $5) t' INTO filas USING p_etapa,p_semana,p_codigo,p_limite,p_desplazamiento;
 RETURN jsonb_build_object('filas',filas,'total',total,'ejecucion_id',gen_random_uuid(),'ejecutado_utc',inicio,'duracion_ms',extract(epoch FROM clock_timestamp()-inicio)*1000,'sql',q||' LIMIT $4 OFFSET $5','fuente',(SELECT contenido FROM public.fuentes_evaluacion WHERE id=1),'metodologia',$method${"quiebres": "Último saldo de cada nombre de producto por semana. Umbral saldo <= 1. Orden: fecha, número original y fila del Excel. Debe confirmarse el orden intradía con los documentos del almacén.", "mermas": "Qp: salidas con motivo Pérdida por vencimiento. Qr: suma de (saldo - ingreso + salida) del primer movimiento semanal de cada producto; apertura reconstruida algebraicamente. El porcentaje se calcula aunque existan aperturas negativas; validación y saldos negativos se muestran por separado. Datos faltantes o un denominador no positivo impiden calcularlo.", "eficiencia": "12 campos de CODIGO a MOTIVO, coherencia de tipo/documento/cantidades y saldo respecto al movimiento anterior no excluido. Sin saldo previo, el registro queda pendiente y no se presume correcto. La tasa calculada es registros verificados / evaluados; si hay pendientes, es una cota mínima, no una estimación completa de eficiencia. Se muestra también el límite superior posible y el porcentaje reportado en el Excel. Una incidencia se clasifica por el primer criterio incumplido.", "comparacion": "Semana ordinal 1–8 de períodos diferentes. Sin datos no equivale a cero. Los resultados SQL se contrastan con las tasas reportadas, sin forzar coincidencias."}$method$::jsonb,'solo_lectura',true,'origen','SUPABASE');
END $fn$;
CREATE FUNCTION public.gest_comparativo() RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,public AS $fn$
 SELECT jsonb_build_object('origen','SUPABASE','periodos',2,'semanas',16,'indicadores',3,
 'calculados',coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.etapa,r.semana) FROM public.v_resumen_semanal r),'[]'::jsonb),
 'reportados',coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.indicador,r.etapa,r.semana) FROM public.v_tasas_reportadas r),'[]'::jsonb),
 'archivo_sha256',(SELECT contenido->>'sha256' FROM public.fuentes_evaluacion WHERE id=1),'calculo','POSTGRESQL_EN_CADA_CONSULTA');
$fn$;
CREATE FUNCTION public.gest_stock_confirmar(p_id uuid,p_usuario text) RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,public AS $fn$
DECLARE previa public.previas_stock%rowtype; item jsonb; revision_actual uuid; datos jsonb; ahora timestamptz:=clock_timestamp(); nuevos integer:=0; actualizados integer:=0;
BEGIN
 SELECT * INTO previa FROM public.previas_stock WHERE id=p_id AND usuario=p_usuario FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Vista previa no encontrada'; END IF;
 IF previa.aplicado THEN RAISE EXCEPTION 'Esta carga ya fue aplicada'; END IF;
 IF extract(epoch FROM ahora)-previa.creado>1800 THEN RAISE EXCEPTION 'Vista previa vencida; valide otra vez'; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(previa.contenido) ORDER BY value->'despues'->>'codigo' LOOP
  PERFORM pg_advisory_xact_lock(hashtext('stock:'||(item->'despues'->>'codigo')));
  SELECT revision INTO revision_actual FROM public.productos_stock WHERE codigo=item->'despues'->>'codigo';
  IF revision_actual IS DISTINCT FROM (item->>'revision')::uuid THEN RAISE EXCEPTION 'El stock cambió; valide otra vez'; END IF;
 END LOOP;
 SELECT count(*) FILTER(WHERE (value->>'nuevo')::boolean),count(*) FILTER(WHERE NOT (value->>'nuevo')::boolean) INTO nuevos,actualizados FROM jsonb_array_elements(previa.contenido);
 INSERT INTO public.importaciones_stock VALUES(p_id,ahora,p_usuario,previa.archivo,previa.sha256,nuevos,actualizados);
 FOR item IN SELECT value FROM jsonb_array_elements(previa.contenido) LOOP
  datos:=(item->'despues')||jsonb_build_object('actualizado_utc',ahora,'importacion_id',p_id);
  INSERT INTO public.productos_stock VALUES(datos->>'codigo',datos,p_id) ON CONFLICT(codigo) DO UPDATE SET contenido=excluded.contenido,revision=excluded.revision;
  INSERT INTO public.cambios_stock(importacion_id,codigo,antes_json,despues_json) VALUES(p_id,datos->>'codigo',item->'antes',datos);
 END LOOP;
 UPDATE public.previas_stock SET aplicado=true WHERE id=p_id;
 RETURN jsonb_build_object('guardado',true,'id',p_id,'fecha_utc',ahora,'nuevos',nuevos,'actualizados',actualizados,'total',nuevos+actualizados);
END $fn$;
ALTER TABLE public.fuentes_evaluacion ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fuentes_evaluacion FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.fuentes_evaluacion TO service_role;
ALTER TABLE public.movimientos_evaluacion ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.movimientos_evaluacion FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.movimientos_evaluacion TO service_role;
ALTER TABLE public.observaciones_evaluacion ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.observaciones_evaluacion FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.observaciones_evaluacion TO service_role;
ALTER TABLE public.auditoria_consultas ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.auditoria_consultas FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.auditoria_consultas TO service_role;
ALTER TABLE public.productos_stock ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.productos_stock FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.productos_stock TO service_role;
ALTER TABLE public.previas_stock ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.previas_stock FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.previas_stock TO service_role;
ALTER TABLE public.importaciones_stock ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.importaciones_stock FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.importaciones_stock TO service_role;
ALTER TABLE public.cambios_stock ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.cambios_stock FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.cambios_stock TO service_role;
GRANT UPDATE ON public.productos_stock,public.previas_stock TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public.cambios_stock_id_seq TO service_role;
REVOKE ALL ON public.v_movimientos_fuente FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_movimientos_fuente TO service_role;
REVOKE ALL ON public.v_semanas_base FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_semanas_base TO service_role;
REVOKE ALL ON public.v_tasas_reportadas FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_tasas_reportadas TO service_role;
REVOKE ALL ON public.v_movimientos_analizados FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_movimientos_analizados TO service_role;
REVOKE ALL ON public.v_cierres_semanales FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_cierres_semanales TO service_role;
REVOKE ALL ON public.v_aperturas_semanales FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_aperturas_semanales TO service_role;
REVOKE ALL ON public.v_evaluacion_registros FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_evaluacion_registros TO service_role;
REVOKE ALL ON public.v_resumen_semanal FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_resumen_semanal TO service_role;
REVOKE ALL ON public.v_indicadores_semanales FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_indicadores_semanales TO service_role;
REVOKE ALL ON FUNCTION public.gest_consulta(text,text,integer,text,integer,integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.gest_consulta(text,text,integer,text,integer,integer) TO service_role;
REVOKE ALL ON FUNCTION public.gest_comparativo() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.gest_comparativo() TO service_role;
REVOKE ALL ON FUNCTION public.gest_stock_confirmar(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.gest_stock_confirmar(uuid,text) TO service_role;

CREATE FUNCTION public.gest_metadata() RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,public AS $fn$
 SELECT jsonb_build_object('fuente',(SELECT contenido FROM public.fuentes_evaluacion WHERE id=1),
 'semanas',(SELECT jsonb_agg(to_jsonb(s) ORDER BY etapa,semana) FROM public.v_semanas_base s),
 'conteos',(SELECT jsonb_agg(to_jsonb(c)) FROM (SELECT etapa,count(*) AS registros,count(*) FILTER(WHERE exclusion IS NOT NULL) AS excluidos FROM public.v_movimientos_fuente GROUP BY etapa)c),
 'observaciones',coalesce((SELECT jsonb_agg(to_jsonb(o) ORDER BY id) FROM public.observaciones_evaluacion o),'[]'::jsonb),
 'version_calculo','3.0-postgresql','auditoria_persistente_declarada',true,'origen','SUPABASE');
$fn$;
CREATE FUNCTION public.gest_auditoria() RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,public AS $fn$
 SELECT jsonb_build_object('total',(SELECT count(*) FROM public.auditoria_consultas),
 'eventos',coalesce((SELECT jsonb_agg(t.evento ORDER BY t.fecha_utc DESC) FROM (
 SELECT payload::jsonb||jsonb_build_object('huella',huella,'origen',origen) AS evento,fecha_utc
 FROM public.auditoria_consultas ORDER BY fecha_utc DESC LIMIT 100)t),'[]'::jsonb),'origen','SUPABASE');
$fn$;
REVOKE ALL ON FUNCTION public.gest_metadata(),public.gest_auditoria() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.gest_metadata(),public.gest_auditoria() TO service_role;

NOTIFY pgrst,'reload schema';
COMMIT;
SELECT 'Estructura central creada; pendiente cargar movimientos' AS resultado;
