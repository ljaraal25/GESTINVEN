-- Consultas parametrizadas de GESTINVEN. Resultados calculados y validación se muestran por separado.

-- quiebres
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

SELECT codigo,producto,fecha,saldo,documento,lote,hoja,fila,numero_original
FROM cierres
WHERE etapa=:etapa AND semana=:semana AND ultimo=1 AND saldo<=1
AND (:codigo='' OR codigo=:codigo)
ORDER BY saldo,codigo,producto;

-- cierres
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

SELECT codigo,producto,fecha,saldo,CASE WHEN saldo<=1 THEN 1 ELSE 0 END AS quiebre,hoja,fila
FROM cierres WHERE etapa=:etapa AND semana=:semana AND ultimo=1
AND (:codigo='' OR codigo=:codigo) ORDER BY codigo,producto;

-- aperturas
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

SELECT codigo,producto,fecha,saldo,ingreso,salida,saldo-ingreso+salida AS apertura_reconstruida,
CASE WHEN saldo IS NULL OR ingreso IS NULL OR salida IS NULL THEN 'NO_CALCULABLE'
WHEN saldo-ingreso+salida<0 THEN 'APERTURA_NEGATIVA' ELSE 'RECONSTRUIDA_PENDIENTE_DE_DOCUMENTO' END AS estado,
hoja,fila FROM cierres WHERE etapa=:etapa AND semana=:semana AND primero=1
AND (:codigo='' OR codigo=:codigo) ORDER BY apertura_reconstruida,codigo;

-- mermas
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

SELECT codigo,producto,fecha,salida AS unidades_perdidas,documento,lote,motivo,hoja,fila
FROM base
WHERE etapa=:etapa AND semana=:semana
AND motivo_clave='PERDIDA POR VENCIMIENTO'
AND (:codigo='' OR codigo=:codigo)
ORDER BY salida DESC,codigo,fecha,fila;

-- errores
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
, anteriores AS (
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

SELECT codigo,producto,fecha,estado,saldo_anterior,ingreso,salida,saldo,
 campos_faltantes,documento,hoja,fila
FROM revisados
WHERE etapa=:etapa AND semana=:semana AND estado<>'COMPLETO_CONSISTENTE'
AND (:codigo='' OR codigo=:codigo)
ORDER BY estado,codigo,fecha,fila;

-- movimientos
SELECT etapa,numero_original,codigo,producto,fecha,tipo,documento,lote,
 registro_sanitario,ingreso,salida,saldo,motivo,exclusion,hoja,fila
FROM movimientos WHERE etapa=:etapa
AND (:semana=0 OR (fecha>=(SELECT desde FROM semanas WHERE etapa=:etapa AND semana=:semana)
 AND fecha<(SELECT fin_exclusivo FROM semanas WHERE etapa=:etapa AND semana=:semana)))
AND (:codigo='' OR codigo=:codigo)
ORDER BY fecha,numero_orden,fila;

-- comparativo
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
, anteriores AS (
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
ORDER BY s.etapa DESC,s.semana;

-- reportado
SELECT etapa,semana,indicador,valor_pct,hoja,celda
FROM tasas_reportadas ORDER BY indicador,etapa,semana;

