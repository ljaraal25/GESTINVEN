"""Ejecuta las mismas consultas del sistema desde la terminal."""
import argparse, json
from pathlib import Path
if __package__:
    from . import evaluacion_store as store
else:
    import evaluacion_store as store
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("consulta",choices=store.QUERIES)
p.add_argument("--etapa",choices=["PRE","POST"],default="POST")
p.add_argument("--semana",type=int,default=3)
p.add_argument("--codigo",default="")
p.add_argument("--limite",type=int,default=100)
a=p.parse_args()
r=store.execute(a.consulta,a.etapa,a.semana,a.codigo,a.limite)
r["auditoria"]=store.log_execution(r,"terminal-local")
print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False))
