"""Lectura privada del comparativo PRE/POST almacenado en Supabase."""
import json
import os
import re
import math
from urllib import request,parse,error
if __package__:
    from .bitacora_supabase import configuracion,SinRedireccion,ErrorBitacora
else:
    from bitacora_supabase import configuracion,SinRedireccion,ErrorBitacora

RELACIONES={'periodos_evaluacion','semanas_evaluacion','indicadores','resultados_semanales','v_resultados_semanales','v_comparativo_pre_post','v_resumen_pre_post'}
class ErrorComparativo(RuntimeError):pass

def consultar(relacion,parametros=None):
    if relacion not in RELACIONES:raise ValueError('Relación no permitida.')
    try:
        url,key=configuracion()
    except (ErrorBitacora,OSError,ValueError):
        raise ErrorComparativo("Revise la configuración privada de Supabase en el backend.") from None
    query=parse.urlencode(parametros or {'select':'*'})
    req=request.Request(url+'/rest/v1/'+relacion+'?'+query,headers={'apikey':key,'Accept':'application/json'})
    try:
        with request.build_opener(SinRedireccion()).open(req,timeout=20) as response:
            result=json.load(response)
        if not isinstance(result,list):raise ErrorComparativo('Respuesta no válida de Supabase.')
        return result
    except error.HTTPError as exc:
        raise ErrorComparativo('No se pudo consultar '+relacion+' (HTTP '+str(exc.code)+').') from None
    except (OSError,ValueError):
        raise ErrorComparativo('No se pudo confirmar la conexión con Supabase.') from None

def obtener_comparativo(indicador,fuente='EXCEL',archivo_sha256=None):
    if indicador not in ('QUIEBRES','MERMAS','EFICIENCIA') or fuente not in ('EXCEL','SQL'):
        raise ValueError('Indicador o fuente no válida.')
    params={'select':'*','indicador':'eq.'+indicador,'fuente':'eq.'+fuente,'order':'semana.asc'}
    if archivo_sha256:params['archivo_sha256']='eq.'+archivo_sha256
    return consultar('v_comparativo_pre_post',params)


METRICAS={'QUIEBRES':'quiebres','MERMAS':'mermas','EFICIENCIA':'eficiencia'}
CAMPOS_VALIDACION=('cierres_sin_saldo','cierres_negativos','aperturas_negativas','saldo_aperturas_negativas',
'aperturas_no_calculables','perdidas_no_calculables','qr','qp','sin_apertura','evaluados','consistentes',
'eficiencia_alcance','eficiencia_limite_superior_pct','validacion_quiebres','validacion_mermas','validacion_eficiencia')

def organizar_resultados(rows,sha):
    if not re.fullmatch(r'[a-f0-9]{64}',sha or ''):
        raise ErrorComparativo('Versión de datos no válida.')
    summary={};reported=[];seen=set();sources=set()
    for row in rows:
        try:
            week=row['semanas_evaluacion'];period=week['periodos_evaluacion'];indicator=row['indicadores']
            phase=period['etapa'];number=week['numero_semana'];metric=METRICAS[indicator['codigo']];source=row['fuente']
            value=row['porcentaje']
            if phase not in ('PRE','POST') or not isinstance(number,int) or not 1<=number<=8 or source not in ('EXCEL','SQL'):
                raise ValueError()
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError()
            if row['archivo_sha256']!=sha:raise ValueError()
            key=(phase,number,metric,source)
            if key in seen:raise ValueError()
            seen.add(key);sources.add(source)
            item=summary.setdefault((phase,number),{'etapa':phase,'semana':number,'desde':week['fecha_inicio'],'hasta':week['fecha_fin']})
            if item['desde']!=week['fecha_inicio'] or item['hasta']!=week['fecha_fin']:raise ValueError()
            if source=='EXCEL':
                reported.append({'etapa':phase,'semana':number,'indicador':metric,'valor_pct':value,
                                 'hoja':row['hoja_origen'],'celda':row['celda_origen']})
            else:
                item[metric+'_pct']=value
                metadata=(row.get('datos_originales') or {}).get('revision_sql')
                if not isinstance(metadata,dict):raise ValueError()
                if metadata.get('etapa')!=phase or metadata.get('semana')!=number:raise ValueError()
                for field in CAMPOS_VALIDACION:
                    if field in metadata:item[field]=metadata[field]
        except (KeyError,TypeError,ValueError):
            raise ErrorComparativo('Los resultados de Supabase tienen datos incompletos o relaciones inconsistentes.') from None
    expected={(phase,week,metric) for phase in ('PRE','POST') for week in range(1,9) for metric in METRICAS.values()}
    for source in sources:
        if {(a,b,c) for a,b,c,d in seen if d==source}!=expected:
            raise ErrorComparativo('La fuente '+source+' no tiene los 48 resultados semanales completos.')
    if 'EXCEL' not in sources:raise ErrorComparativo('No están disponibles las fichas semanales reportadas en Supabase.')
    return {'origen':'SUPABASE','archivo_sha256':sha,'fuentes_disponibles':sorted(sources),
            'periodos':2,'semanas':16,'indicadores':3,'total_resultados':len(rows),
            'calculados':sorted(summary.values(),key=lambda r:(r['etapa'],r['semana'])),
            'reportados':sorted(reported,key=lambda r:(r['indicador'],r['etapa'],r['semana']))}

def cargar_comparativo():
    sha=os.environ.get('GESTINVEN_COMPARATIVO_SHA256','').strip()
    if not sha:
        latest=consultar('resultados_semanales',{'select':'archivo_sha256','order':'creado_en.desc','limit':1})
        if not latest:raise ErrorComparativo('No hay resultados semanales disponibles en Supabase.')
        sha=latest[0].get('archivo_sha256','')
    if not re.fullmatch(r'[a-f0-9]{64}',sha):raise ErrorComparativo('La versión configurada del comparativo no es válida.')
    rows=consultar('resultados_semanales',{
        'select':'*,semanas_evaluacion(numero_semana,fecha_inicio,fecha_fin,periodos_evaluacion(etapa)),indicadores(codigo,nombre,sentido_mejora)',
        'archivo_sha256':'eq.'+sha,'limit':1000})
    return organizar_resultados(rows,sha)
