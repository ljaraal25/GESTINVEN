-- Ejemplo 1: productos con quiebre al cierre de la semana 3 del postest.
SELECT codigo, producto, fecha, saldo, hoja, fila
FROM v_cierres_semanales
WHERE etapa = 'POST' AND semana = 3 AND saldo <= 1
ORDER BY saldo, codigo;

-- Ejemplo 2: numerador, denominador y porcentaje calculado al ejecutar.
SELECT etapa, semana, quiebres, productos, quiebres_pct
FROM v_resumen_semanal
WHERE etapa = 'POST' AND semana = 3;

-- Ejemplo 3: apertura negativa para examinar un hallazgo de calidad de datos.
SELECT codigo, producto, fecha, saldo, ingreso, salida,
       apertura_reconstruida, hoja, fila
FROM v_aperturas_semanales
WHERE etapa = 'POST' AND semana = 1 AND apertura_reconstruida < 0;

-- Ejemplo 4: pérdidas por vencimiento de la semana 3 del postest.
SELECT codigo, producto, fecha, salida, lote, documento, hoja, fila
FROM v_movimientos_analizados
WHERE etapa = 'POST' AND semana = 3
  AND motivo_clave = 'PERDIDA POR VENCIMIENTO'
ORDER BY salida DESC;

-- Ejemplo 5: casos que requieren verificar el saldo anterior.
SELECT codigo, producto, fecha, estado, saldo_anterior, saldo, hoja, fila
FROM v_evaluacion_registros
WHERE etapa = 'PRE' AND semana = 1
  AND estado = 'SIN_APERTURA_VERIFICADA'
ORDER BY codigo, fecha;

-- Ejemplo 6: tasas reportadas, conservadas como referencia.
SELECT etapa, semana, indicador, valor_pct, hoja, celda
FROM tasas_reportadas
ORDER BY indicador, etapa DESC, semana;


-- Cálculo y validación separados. Ejecutar en la consola sqlite>.
-- Mermas: primera semana del postest.
SELECT etapa, semana, numerador AS unidades_perdidas,
       denominador AS cantidad_inicial,
       ROUND(porcentaje_calculado, 2) AS porcentaje_mermas,
       aperturas_negativas, saldo_aperturas_negativas,
       validacion
FROM v_indicadores_semanales
WHERE indicador = 'mermas' AND etapa = 'POST' AND semana = 1;

-- Todos los datos calculados y reportados del postest, con sus observaciones.
SELECT indicador, etapa, semana, numerador, denominador,
       ROUND(porcentaje_calculado, 2) AS porcentaje_calculado,
       ROUND(porcentaje_excel, 2) AS porcentaje_excel,
       alcance, validacion, registros_pendientes,
       aperturas_negativas, saldo_aperturas_negativas
FROM v_indicadores_semanales
WHERE etapa = 'POST'
ORDER BY indicador, semana;

-- Eficiencia: la tasa verificada es una cota mínima si hay saldos previos pendientes.
SELECT etapa, semana, evaluados, consistentes, sin_apertura,
       registros_con_incidencias,
       ROUND(eficiencia_pct, 2) AS proporcion_verificada_pct,
       ROUND(eficiencia_limite_superior_pct, 2) AS limite_superior_posible_pct,
       eficiencia_alcance, validacion_eficiencia,
       ROUND(eficiencia_excel_pct, 2) AS reportado_excel_pct
FROM v_resumen_semanal
WHERE etapa = 'POST'
ORDER BY semana;

-- Localizar las aperturas negativas que respaldan la observación.
SELECT codigo, producto, fecha, ingreso, salida, saldo,
       apertura_reconstruida, hoja, fila
FROM v_aperturas_semanales
WHERE etapa = 'POST' AND semana = 1 AND apertura_reconstruida < 0;
