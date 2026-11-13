"""Comparativo central: referencia conservada y cálculo directo en PostgreSQL."""
if __package__:
 from . import supabase_db as db
else:
 import supabase_db as db
ErrorComparativo=db.CloudError
def cargar_comparativo():
 result=db.rpc('gest_comparativo')
 if not isinstance(result,dict) or len(result.get('calculados',[]))!=16 or len(result.get('reportados',[]))!=48:
  raise ErrorComparativo('La migración de movimientos o resultados todavía no está completa en Supabase.')
 return result
