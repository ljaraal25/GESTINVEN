"""API de consultas predefinidas: datos privados, SQL parametrizado y sesión firmada."""
import base64, hashlib, hmac, json, os, secrets, sqlite3, time, logging
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
if __package__:
    from . import evaluacion_store as store
    from .usuarios import usuario_habilitado
    from . import comparativo_supabase as comparativo_cloud
else:
    import evaluacion_store as store
    from usuarios import usuario_habilitado
    import comparativo_supabase as comparativo_cloud
router=APIRouter(prefix="/evaluacion",tags=["Evaluación SQL"])
_SECRET=os.environ.get("GESTINVEN_SESSION_SECRET")
_KEY=hashlib.sha256(_SECRET.encode()).digest() if _SECRET else secrets.token_bytes(32)
def b64(raw): return base64.urlsafe_b64encode(raw).decode().rstrip("=")
def issue_evaluation_token(user):
    payload=b64(json.dumps({"sub":user,"exp":int(time.time())+8*3600},separators=(",",":")).encode())
    return payload+"."+b64(hmac.new(_KEY,payload.encode(),hashlib.sha256).digest())
def require_user(authorization: str | None = Header(default=None)):
    try:
        if not authorization or not authorization.startswith("Bearer "): raise ValueError()
        payload,signature=authorization[7:].split(".")
        expected=b64(hmac.new(_KEY,payload.encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(signature,expected): raise ValueError()
        claims=json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))
        if not isinstance(claims.get("exp"),int) or claims["exp"]<=time.time() or not claims.get("sub"): raise ValueError()
        if not usuario_habilitado(str(claims["sub"])): raise ValueError()
        return str(claims["sub"])
    except (ValueError,TypeError,KeyError,UnicodeError):
        raise HTTPException(status_code=401,detail="Inicie sesión otra vez para consultar la evaluación.") from None
def no_cache(response):
    response.headers["Cache-Control"]="no-store"
def run_safe(fn):
    try: return fn()
    except FileNotFoundError:
        raise HTTPException(status_code=503,detail="La base SQLite de evaluación todavía no está instalada en este servidor.") from None
    except sqlite3.Error:
        logging.exception("Error de SQLite de evaluación")
        raise HTTPException(status_code=503,detail="No se pudo consultar la base de evaluación.") from None

@router.get("/fuente")
def fuente(response: Response,user: str=Depends(require_user)):
    no_cache(response)
    return run_safe(store.metadata)

@router.get("/consultar")
def consultar(response: Response,
    consulta: Literal["quiebres","cierres","aperturas","mermas","errores","movimientos","comparativo","reportado"]="quiebres",
    etapa: Literal["PRE","POST"]="POST",semana: int=Query(1,ge=1,le=8),
    codigo: str=Query("",max_length=12,pattern=r"^\d*$"),
    limite: int=Query(100,ge=1,le=500),desplazamiento: int=Query(0,ge=0),
    user: str=Depends(require_user)):
    no_cache(response)
    result=run_safe(lambda:store.execute(consulta,etapa,semana,codigo,limite,desplazamiento))
    try:
        result["auditoria"]=store.log_execution(result,user)
    except (OSError,sqlite3.Error,ValueError):
        logging.exception("No se pudo guardar la bitácora de evaluación")
        result["auditoria"]={"guardada":False,"mensaje":"La consulta se ejecutó, pero la bitácora no pudo guardarse."}
    return result

@router.get("/auditoria")
def auditoria(response: Response,user: str=Depends(require_user)):
    no_cache(response)
    try: return store.audit_events()
    except (OSError,sqlite3.Error,ValueError):
        raise HTTPException(status_code=503,detail="No se pudo revisar la bitácora.") from None


@router.get('/comparativo-supabase')
def comparativo_supabase(response: Response,user: str=Depends(require_user)):
    no_cache(response)
    try:
        return comparativo_cloud.cargar_comparativo()
    except comparativo_cloud.ErrorComparativo as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from None
