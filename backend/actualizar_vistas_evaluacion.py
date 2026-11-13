"""Actualiza solo las vistas de evaluación; exige respaldo y conserva las tablas fuente."""
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
import sqlite3,json,hashlib,argparse
if __package__:
    from . import evaluacion_store as store
else:
    import evaluacion_store as store
def fingerprint(db):
    h=hashlib.sha256()
    for name in ['importacion','semanas','movimientos','tasas_reportadas','observaciones']:
        h.update(name.encode())
        for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid'):
            h.update(json.dumps(tuple(row),ensure_ascii=False,separators=(',',':')).encode())
    return h.hexdigest()
def actualizar(path,respaldo):
    path=Path(path).resolve();respaldo=Path(respaldo).resolve()
    if not path.is_file():raise FileNotFoundError(path)
    if path==respaldo or respaldo.exists():raise ValueError('El respaldo debe ser un archivo nuevo, distinto de la base.')
    respaldo.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=30)) as db:
        with closing(sqlite3.connect(respaldo)) as backup:db.backup(backup)
        before=fingerprint(db)
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('DROP VIEW IF EXISTS v_indicadores_semanales')
            db.execute('DROP VIEW v_resumen_semanal')
            db.execute('CREATE VIEW v_resumen_semanal AS '+store.RESUMEN)
            db.execute('CREATE VIEW v_indicadores_semanales AS '+store.INDICADORES)
            db.execute('CREATE TABLE IF NOT EXISTS migraciones_evaluacion(version TEXT PRIMARY KEY,fecha_utc TEXT NOT NULL,detalle TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO migraciones_evaluacion VALUES(?,?,?)',('2.1',datetime.now(timezone.utc).isoformat(),'Cálculo aritmético, alcance y validación separados. Movimientos y fichas originales sin modificaciones.'))
            assert db.execute('SELECT COUNT(*) FROM v_resumen_semanal').fetchone()[0]==16
            assert db.execute('SELECT COUNT(*) FROM v_indicadores_semanales').fetchone()[0]==48
            after=fingerprint(db)
            if before!=after:raise ValueError('Las tablas fuente cambiaron; se cancela la actualización.')
            db.commit()
        except BaseException:
            db.rollback();raise
    print(json.dumps({'version':'2.1','tablas_fuente_sin_cambios':True,'sha256_logico':after,'respaldo':str(respaldo)},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',default=str(store.database_path()))
    p.add_argument('--respaldo',required=True)
    a=p.parse_args();actualizar(a.base,a.respaldo)
