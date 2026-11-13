BEGIN;
CREATE VIEW public.v_resultados_comparables WITH(security_invoker=true) AS
SELECT etapa,numero_semana,fecha_inicio,fecha_fin,indicador,nombre,sentido_mejora,fuente,porcentaje,observacion,archivo_sha256
FROM public.v_resultados_semanales WHERE fuente='EXCEL' AND archivo_sha256=(SELECT contenido->>'sha256' FROM public.fuentes_evaluacion WHERE id=1)
UNION ALL
SELECT r.etapa,r.semana,r.desde,r.hasta,upper(r.indicador),i.nombre,i.sentido_mejora,'CALCULADO',r.porcentaje_calculado::numeric(10,5),r.observacion,
(SELECT contenido->>'sha256' FROM public.fuentes_evaluacion WHERE id=1)
FROM public.v_indicadores_semanales r JOIN public.indicadores i ON i.codigo=upper(r.indicador);
CREATE OR REPLACE VIEW public.v_comparativo_pre_post WITH(security_invoker=true) AS
SELECT a.indicador,a.nombre,a.numero_semana AS semana,a.fuente,a.archivo_sha256,
a.fecha_inicio AS pre_desde,a.fecha_fin AS pre_hasta,b.fecha_inicio AS post_desde,b.fecha_fin AS post_hasta,
a.porcentaje AS pretest_pct,b.porcentaje AS postest_pct,b.porcentaje-a.porcentaje AS cambio_pp,a.sentido_mejora,
a.observacion AS observacion_pre,b.observacion AS observacion_post
FROM public.v_resultados_comparables a JOIN public.v_resultados_comparables b
ON a.indicador=b.indicador AND a.numero_semana=b.numero_semana AND a.fuente=b.fuente AND a.archivo_sha256=b.archivo_sha256
WHERE a.etapa='PRE' AND b.etapa='POST';
REVOKE ALL ON public.v_resultados_comparables FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.v_resultados_comparables TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
SELECT indicador,fuente,semanas_comparadas,media_pretest_pct,media_postest_pct FROM public.v_resumen_pre_post ORDER BY indicador,fuente;
