"""Usuarios autorizados del sistema; contraseñas verificadas mediante PBKDF2."""
import hashlib
import hmac

ITERACIONES = 260000
USUARIOS = {'76131386': ('34f492a2477cb58beb7d445a1c0537db', 'c14e15a2e9e58486c167e58fd561ad54f029a1d14d207ee8148fa614061ca6de'), '09988919': ('83059c106281eb87687f849779308581', 'bbdcb2622eea099503ea4acf3a3e4465272b6ea6b09c3cda919ac18b5b6ff661'), '72707910': ('e1fc4559e6bfc837e1fa03d07afb75d9', '918a2143de4baa14196aa58761dbf1a5d602ef209d8973377810f5406adcbca0')}

def usuario_habilitado(usuario):
    return usuario in USUARIOS

def validar_credenciales(usuario, password):
    registro = USUARIOS.get(usuario)
    salt, esperado = registro if registro else ('00' * 16, '00' * 32)
    calculado = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), ITERACIONES).hex()
    return hmac.compare_digest(calculado, esperado) and registro is not None
