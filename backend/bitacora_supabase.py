"""Bitácora de accesos correctos; clave privada leída solo por el backend."""
import json
import logging
import os
from pathlib import Path
from urllib import request, error, parse

class ErrorBitacora(RuntimeError):
    pass

def configuracion():
    valores = {}
    archivo = Path(__file__).resolve().parent.parent / '.env'
    if archivo.is_file():
        for linea in archivo.read_text(encoding='utf-8-sig').splitlines():
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            if linea.startswith('export '):
                linea = linea[7:]
            nombre, separador, valor = linea.partition('=')
            if separador and nombre.strip() in ('SUPABASE_URL', 'SUPABASE_SECRET_KEY'):
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
                    valor = valor[1:-1]
                valores[nombre.strip()] = valor
    url = os.environ.get('SUPABASE_URL', valores.get('SUPABASE_URL', '')).strip().rstrip('/')
    clave = os.environ.get('SUPABASE_SECRET_KEY', valores.get('SUPABASE_SECRET_KEY', '')).strip()
    partes = parse.urlsplit(url)
    if (partes.scheme != 'https' or not partes.hostname or
        not partes.hostname.endswith('.supabase.co') or partes.username or
        partes.password or partes.port is not None or partes.path or partes.query or partes.fragment or
        not clave.startswith('sb_secret_') or any(c.isspace() for c in clave)):
        raise ErrorBitacora('Configure SUPABASE_URL y SUPABASE_SECRET_KEY en el backend.')
    return url, clave

class SinRedireccion(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def registrar_inicio(usuario):
    try:
        url, clave = configuracion()
        req = request.Request(
            url + '/rest/v1/bitacora_accesos?select=id,usuario,fecha_hora,evento',
            data=json.dumps({'usuario': usuario}).encode('utf-8'),
            headers={'apikey': clave, 'Content-Type': 'application/json',
                     'Accept': 'application/json', 'Prefer': 'return=representation'},
            method='POST',
        )
        with request.build_opener(SinRedireccion()).open(req, timeout=10) as respuesta:
            registros = json.loads(respuesta.read(65536))
        if not isinstance(registros, list) or len(registros) != 1:
            raise ErrorBitacora('Respuesta de bitácora no confirmada.')
        registro = registros[0]
        if not registro.get('id') or not registro.get('fecha_hora') or registro.get('usuario') != usuario:
            raise ErrorBitacora('Respuesta de bitácora no confirmada.')
        return {'id': registro['id'], 'fecha_hora': registro['fecha_hora']}
    except error.HTTPError as exc:
        logging.error('Bitácora Supabase: HTTP %s.', exc.code)
        raise ErrorBitacora('No se pudo guardar el acceso en Supabase.') from None
    except (OSError, ValueError, TypeError, KeyError):
        logging.error('Bitácora Supabase: error de configuración, red o respuesta.')
        raise ErrorBitacora('No se pudo confirmar el registro de acceso.') from None
