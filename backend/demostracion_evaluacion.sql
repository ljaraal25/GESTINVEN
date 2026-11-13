-- Ejecutar en Supabase SQL Editor. Los cálculos se ejecutan sobre los movimientos.
SELECT etapa,semana,desde,hasta,quiebres,productos,ROUND(quiebres_pct,2) AS porcentaje_quiebres
FROM public.v_resumen_semanal WHERE etapa='POST' ORDER BY semana;

SELECT etapa,semana,qp,qr,ROUND(mermas_pct,2) AS porcentaje_mermas,aperturas_negativas
FROM public.v_resumen_semanal WHERE etapa='POST' ORDER BY semana;

SELECT etapa,semana,consistentes,evaluados,ROUND(eficiencia_pct,2) AS porcentaje_verificado,
ROUND(eficiencia_excel_pct,2) AS porcentaje_reportado,sin_apertura,eficiencia_alcance
FROM public.v_resumen_semanal WHERE etapa='POST' ORDER BY semana;

SELECT etapa,semana,indicador,numerador,denominador,ROUND(porcentaje_calculado,2) AS calculado,
ROUND(porcentaje_excel,2) AS reportado,validacion,alcance
FROM public.v_indicadores_semanales WHERE etapa='POST' AND semana=1 ORDER BY indicador;
