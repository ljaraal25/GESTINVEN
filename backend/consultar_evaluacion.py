"""Consulta de indicadores en Supabase desde una terminal local."""
import argparse,getpass,json
if __package__:
 from .usuarios import validar_credenciales
 from .bitacora_supabase import registrar_inicio
 from . import evaluacion_store as store
else:
 from usuarios import validar_credenciales
 from bitacora_supabase import registrar_inicio
 import evaluacion_store as store

def main():
 parser=argparse.ArgumentParser(description='Consultas de evaluación sobre Supabase, sin base local.')
 parser.add_argument('--consulta',choices=list(store.TITULOS),default='comparativo')
 parser.add_argument('--etapa',choices=['PRE','POST'],default='POST')
 parser.add_argument('--semana',type=int,choices=range(1,9),default=1)
 parser.add_argument('--codigo',default='');parser.add_argument('--usuario')
 args=parser.parse_args();user=args.usuario or input('Usuario: ').strip();password=getpass.getpass('Contraseña: ')
 if not validar_credenciales(user,password):raise SystemExit('Usuario o contraseña incorrectos.')
 registrar_inicio(user)
 result=store.execute(args.consulta,args.etapa,args.semana,args.codigo)
 result['auditoria']=store.log_execution(result,user)
 print(json.dumps({'total':result['total'],'filas':result['filas'],'auditoria':result['auditoria']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
