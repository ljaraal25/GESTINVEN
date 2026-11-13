from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException

if __package__:
    from .evaluacion_api import router as evaluation_router, issue_evaluation_token
    from .usuarios import validar_credenciales
    from .bitacora_supabase import registrar_inicio, ErrorBitacora
else:
    from evaluacion_api import router as evaluation_router, issue_evaluation_token
    from usuarios import validar_credenciales
    from bitacora_supabase import registrar_inicio, ErrorBitacora
from pydantic import BaseModel

import numpy as np
import joblib
import pandas as pd
from pathlib import Path


app = FastAPI(
    title="SIS_GESTINVEN",
    description="Sistema de Gestión y Predicción de Inventarios",
    version="1.0"
)
app.add_middleware(
    CORSMiddleware,
   allow_origins=[
    "https://ljaraal25.github.io",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://gestinvensite.pages.dev"
],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(evaluation_router)

# Datos que recibirá el login
class LoginRequest(BaseModel):
    usuario: str
    password: str


@app.get("/")
def inicio():
    return {
        "mensaje": "SIS_GESTINVEN funcionando correctamente"
    }


@app.post("/login")
def login(datos: LoginRequest):

    if validar_credenciales(datos.usuario, datos.password):
        try:
            auditoria = registrar_inicio(datos.usuario)
        except ErrorBitacora:
            raise HTTPException(status_code=503, detail="No se pudo registrar el acceso. Intente nuevamente en unos momentos.") from None
        return {
            "auditoria": auditoria,
            "acceso": True,
            "token_evaluacion": issue_evaluation_token(datos.usuario),
            "mensaje": "Inicio de sesión correcto"
        }
    return {
        "acceso": False,
        "mensaje": "Usuario o contraseña incorrectos"
    }
    
import pandas as pd
from pathlib import Path

RUTA_BASE = Path(__file__).resolve().parent.parent
ARCHIVO_RESULTADOS = (
    RUTA_BASE
    / "data"
    / "Resultados_ML_Santa_Luzmila_2026.xlsx"
)
ARCHIVO_MOVIMIENTOS = (
    RUTA_BASE
    / "data"
    / "Editable_Santa_Luzmila_I_Movimientos_Ultimos_12_Meses_2025_2026.xlsx"
)
RUTA_MODELO = (
    RUTA_BASE
    / "modelo"
    / "modelo_random_forest_santa_luzmila.joblib"
)
RUTA_FEATURES = (
    RUTA_BASE
    / "modelo"
    / "features_modelo_santa_luzmila.joblib"
)
modelo_ml = joblib.load(RUTA_MODELO)
features_ml = joblib.load(RUTA_FEATURES)
def calcular_recomendacion(
    prediccion,
    stock_utilizable,
    stock_seguridad
):

    stock_objetivo = (
        prediccion
        + stock_seguridad
    )

    reposicion = max(
        stock_objetivo
        - stock_utilizable,
        0
    )

    return {
        "stock_objetivo": int(
            round(stock_objetivo)
        ),

        "reposicion_sugerida": int(
            round(reposicion)
        )
    }
def preparar_producto_para_modelo(codigo):

    raw = pd.read_excel(
        ARCHIVO_MOVIMIENTOS,
        sheet_name="Mov. Históricos 12M",
        header=None,
        engine="openpyxl"
    )

    columnas = raw.iloc[5].tolist()

    datos = raw.iloc[6:].copy()

    datos.columns = columnas

    datos = datos[
        datos["Nº"].notna()
    ].copy()


    datos["FECHA"] = pd.to_datetime(
        datos["FECHA"],
        errors="coerce"
    )


    datos["SALIDA"] = pd.to_numeric(
        datos["SALIDA"],
        errors="coerce"
    ).fillna(0)


    datos["CODIGO"] = (
        datos["CODIGO"]
        .astype(str)
        .str.extract(
            r"(\d+)",
            expand=False
        )
        .str.zfill(5)
    )


    salidas = datos[
        datos["TIPO DE MOVIMIENTO"]
        .astype(str)
        .str.upper()
        .eq("SALIDA")
    ].copy()


    codigo = str(codigo).zfill(5)

    producto = salidas[
        salidas["CODIGO"] == codigo
    ].copy()


    if producto.empty:
        return None


    producto["MES"] = (
        producto["FECHA"]
        .dt.to_period("M")
    )


    demanda = (
        producto
        .groupby("MES")["SALIDA"]
        .sum()
    )


    meses = pd.period_range(
        start="2025-09",
        end="2026-08",
        freq="M"
    )


    demanda = demanda.reindex(
        meses,
        fill_value=0
    )


    valores = demanda.values.astype(float)


    datos_modelo = {
        "lag_1": valores[-1],
        "lag_2": valores[-2],
        "lag_3": valores[-3],
        "lag_6": valores[-6],

        "ma3": np.mean(
            valores[-3:]
        ),

        "ma6": np.mean(
            valores[-6:]
        ),

        "std3": np.std(
            valores[-3:],
            ddof=1
        ),

        "std6": np.std(
            valores[-6:],
            ddof=1
        ),

        "exp_mean": np.mean(
            valores
        )
    }


    mes_prediccion = 9

    datos_modelo["month_sin"] = np.sin(
        2 * np.pi *
        mes_prediccion / 12
    )

    datos_modelo["month_cos"] = np.cos(
        2 * np.pi *
        mes_prediccion / 12
    )


    X = pd.DataFrame(
        [datos_modelo]
    )

    X = X[
        features_ml
    ].fillna(0)
    return X


def predecir_varios_meses(codigo, meses_futuros=4):

    raw = pd.read_excel(
        ARCHIVO_MOVIMIENTOS,
        sheet_name="Mov. Históricos 12M",
        header=None,
        engine="openpyxl"
    )

    columnas = raw.iloc[5].tolist()

    datos = raw.iloc[6:].copy()
    datos.columns = columnas

    datos = datos[
        datos["Nº"].notna()
    ].copy()

    datos["FECHA"] = pd.to_datetime(
        datos["FECHA"],
        errors="coerce"
    )

    datos["SALIDA"] = pd.to_numeric(
        datos["SALIDA"],
        errors="coerce"
    ).fillna(0)

    datos["CODIGO"] = (
        datos["CODIGO"]
        .astype(str)
        .str.extract(
            r"(\d+)",
            expand=False
        )
        .str.zfill(5)
    )

    salidas = datos[
        datos["TIPO DE MOVIMIENTO"]
        .astype(str)
        .str.upper()
        .eq("SALIDA")
    ].copy()

    codigo = str(codigo).zfill(5)

    producto = salidas[
        salidas["CODIGO"] == codigo
    ].copy()

    if producto.empty:
        return None

    producto["MES"] = (
        producto["FECHA"]
        .dt.to_period("M")
    )

    demanda = (
        producto
        .groupby("MES")["SALIDA"]
        .sum()
    )

    meses_historicos = pd.period_range(
        start="2025-09",
        end="2026-08",
        freq="M"
    )

    demanda = demanda.reindex(
        meses_historicos,
        fill_value=0
    )

    valores = list(
        demanda.values.astype(float)
    )

    resultados = []

    meses_prediccion = pd.period_range(
        start="2026-09",
        periods=meses_futuros,
        freq="M"
    )

    for mes in meses_prediccion:

        arreglo = np.array(
            valores,
            dtype=float
        )

        datos_modelo = {
            "lag_1": arreglo[-1],
            "lag_2": arreglo[-2],
            "lag_3": arreglo[-3],
            "lag_6": arreglo[-6],

            "ma3": np.mean(
                arreglo[-3:]
            ),

            "ma6": np.mean(
                arreglo[-6:]
            ),

            "std3": np.std(
                arreglo[-3:],
                ddof=1
            ),

            "std6": np.std(
                arreglo[-6:],
                ddof=1
            ),

            "exp_mean": np.mean(
                arreglo
            ),

            "month_sin": np.sin(
                2 * np.pi *
                mes.month / 12
            ),

            "month_cos": np.cos(
                2 * np.pi *
                mes.month / 12
            )
        }

        X = pd.DataFrame(
            [datos_modelo]
        )

        X = X[
            features_ml
        ].fillna(0)

        prediccion = modelo_ml.predict(
            X
        )[0]

        prediccion = max(
            prediccion,
            0
        )

        prediccion = int(
            round(prediccion)
        )

        resultados.append({
            "mes": str(mes),
            "prediccion": prediccion
        })

        # Importante:
        # la predicción pasa a formar parte
        # del historial para calcular
        # el siguiente mes
        valores.append(
            prediccion
        )

    return resultados


@app.get("/resumen")
def obtener_resumen():
    resumen = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Resumen",
        engine="openpyxl"
    )
    datos = dict(
        zip(
            resumen["INDICADOR"],
            resumen["VALOR"]
        )
    )
    return {
        "productos_analizados":
            int(datos.get("Productos analizados", 0)),

        "demanda_prevista":
            int(datos.get(
                "Demanda prevista septiembre 2026",
                0
            )),
        "productos_criticos":
            int(datos.get(
                "Productos críticos",
                0
            )),
        "productos_reponer":
            int(datos.get(
                "Productos a reponer",
                0
            ))
    }
@app.get("/predicciones")
def obtener_predicciones():
    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )
    datos = datos.fillna("")

    columnas = [
        "CODIGO",
        "DESCRIPCION",
        "CLASE_ABC",
        "PREDICCION_SEP_2026",
        "STOCK_UTILIZABLE",
        "STOCK_SEGURIDAD",
        "REPOSICION_AJUSTADA",
        "RIESGO",
        "PRIORIDAD",
        "RECOMENDACION"
    ]
    datos = datos[columnas]
    return datos.to_dict(
        orient="records"
    )
    
@app.get("/alertas")
def obtener_alertas():
    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )
    datos = datos.fillna("")

    alertas = datos[
        (datos["RIESGO"].isin(["CRITICO", "ALTO"]))
        |
        (datos["REPOSICION_AJUSTADA"] > 0)
    ].copy()
    columnas = [
        "CODIGO",
        "DESCRIPCION",
        "CLASE_ABC",
        "PREDICCION_SEP_2026",
        "STOCK_UTILIZABLE",
        "REPOSICION_AJUSTADA",
        "RIESGO",
        "PRIORIDAD",
        "RECOMENDACION"
    ]
    alertas = alertas[columnas]

    return alertas.to_dict(
        orient="records"
    )
@app.get("/inventario")
def obtener_inventario():

    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )

    datos = datos.fillna("")

    columnas = [
        "CODIGO",
        "DESCRIPCION",
        "UNIDAD",
        "STOCK_ACTUAL",
        "STOCK_UTILIZABLE",
        "STOCK_SEGURIDAD",
        "RIESGO",
        "RECOMENDACION"
    ]

    inventario = datos[columnas]

    return inventario.to_dict(
        orient="records"
    )
@app.get("/riesgos-resumen")
def obtener_resumen_riesgos():

    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )

    conteo = datos["RIESGO"].value_counts()

    return {
        "critico": int(conteo.get("CRITICO", 0)),
        "alto": int(conteo.get("ALTO", 0)),
        "medio": int(conteo.get("MEDIO", 0)),
        "bajo": int(conteo.get("BAJO", 0))
    }
@app.get("/producto/{codigo}")
def obtener_producto(codigo: str):
    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )
    datos["CODIGO"] = (
        datos["CODIGO"]
        .astype(str)
        .str.zfill(5)
    )
    producto = datos[
        datos["CODIGO"] == codigo.zfill(5)
    ]
    if producto.empty:
        return {
            "encontrado": False,
            "mensaje": "Producto no encontrado"
        }
    fila = producto.iloc[0]
    return {
        "encontrado": True,
        "codigo": str(fila["CODIGO"]),
        "descripcion": (
            ""
            if pd.isna(fila["DESCRIPCION"])
            else str(fila["DESCRIPCION"])
        ),
        "clase_abc": str(fila["CLASE_ABC"]),
        "prediccion": int(fila["PREDICCION_SEP_2026"]),
        "stock_actual": float(fila["STOCK_ACTUAL"]),
        "stock_utilizable": float(fila["STOCK_UTILIZABLE"]),
        "stock_seguridad": float(fila["STOCK_SEGURIDAD"]),
        "reposicion": int(fila["REPOSICION_AJUSTADA"]),
        "riesgo": str(fila["RIESGO"]),
        "prioridad": str(fila["PRIORIDAD"]),
        "recomendacion": str(fila["RECOMENDACION"])
    }
@app.get("/modelo-info")
def obtener_info_modelo():

    return {
        "modelo_cargado": True,
        "tipo_modelo": type(modelo_ml).__name__,
        "numero_variables": len(features_ml),
        "variables": features_ml
    }
    
@app.get("/predecir/{codigo}")
def predecir_producto(codigo: str):

    X = preparar_producto_para_modelo(
        codigo
    )

    if X is None:
        return {
            "encontrado": False,
            "mensaje":
                "No existe historial suficiente para este producto."
        }

    prediccion = modelo_ml.predict(
        X
    )[0]

    prediccion = max(
        prediccion,
        0
    )

    datos = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )

    datos["CODIGO"] = (
        datos["CODIGO"]
        .astype(str)
        .str.zfill(5)
    )

    codigo_limpio = str(
        codigo
    ).zfill(5)

    producto = datos[
        datos["CODIGO"] == codigo_limpio
    ]

    if producto.empty:

        stock_utilizable = 0
        stock_seguridad = 0

    else:

        fila = producto.iloc[0]

        stock_utilizable = float(
            fila["STOCK_UTILIZABLE"]
        )

        stock_seguridad = float(
            fila["STOCK_SEGURIDAD"]
        )

    recomendacion = calcular_recomendacion(
        prediccion,
        stock_utilizable,
        stock_seguridad
    )

    return {
        "encontrado": True,
        "codigo": codigo_limpio,
        "mes_prediccion": "2026-09",

        "prediccion_ml":
            int(round(prediccion)),

        "stock_utilizable":
            int(round(stock_utilizable)),

        "stock_seguridad":
            int(round(stock_seguridad)),

        "stock_objetivo":
            recomendacion[
                "stock_objetivo"
            ],

        "reposicion_sugerida":
            recomendacion[
                "reposicion_sugerida"
            ],

        "modelo":
            "Random Forest"
    }

@app.get("/predecir-periodo/{codigo}")
def predecir_periodo(codigo: str):

    resultados = predecir_varios_meses(
        codigo,
        meses_futuros=4
    )

    if resultados is None:

        return {
            "encontrado": False,
            "mensaje":
                "No existe historial para este producto."
        }

    datos_stock = pd.read_excel(
        ARCHIVO_RESULTADOS,
        sheet_name="Prediccion y Stock",
        engine="openpyxl"
    )

    codigo_normalizado = (
        str(codigo).zfill(5)
    )

    datos_stock["CODIGO"] = (
        datos_stock["CODIGO"]
        .astype(str)
        .str.extract(
            r"(\d+)",
            expand=False
        )
        .str.zfill(5)
    )

    producto = datos_stock[
        datos_stock["CODIGO"]
        == codigo_normalizado
    ]

    if producto.empty:

        return {
            "encontrado": False,
            "mensaje":
                "No se encontró información de stock."
        }

    fila = producto.iloc[0]

    stock_utilizable = float(
        fila["STOCK_UTILIZABLE"]
    )

    stock_seguridad = float(
        fila["STOCK_SEGURIDAD"]
    )

    proyeccion_stock = (
        calcular_stock_proyectado(
            resultados,
            stock_utilizable,
            stock_seguridad
        )
    )

    return {
        "encontrado": True,
        "codigo": codigo_normalizado,
        "modelo": "Random Forest",

        "stock_utilizable":
            int(round(stock_utilizable)),

        "stock_seguridad":
            int(round(stock_seguridad)),

        "predicciones":
            resultados,

        "proyeccion_stock":
            proyeccion_stock
    }
    
def calcular_stock_proyectado(
    predicciones,
    stock_inicial,
    stock_seguridad
):

    stock_actual = float(stock_inicial)

    resultados = []

    for item in predicciones:

        demanda = float(
            item["prediccion"]
        )

        stock_actual = (
            stock_actual
            - demanda
        )

        if stock_actual <= 0:

            estado = "RIESGO DE DESABASTECIMIENTO"

        elif stock_actual <= stock_seguridad:

            estado = "STOCK BAJO"

        else:

            estado = "STOCK SUFICIENTE"

        resultados.append({
            "mes": item["mes"],
            "demanda_prevista": int(demanda),
            "stock_proyectado": int(
                round(stock_actual)
            ),
            "estado": estado
        })

    return resultados

# Stock operativo importado: separado de los datos históricos de evaluación.
if __package__:
    from . import stock_api, stock_store
else:
    import stock_api, stock_store

def catalogo_base_stock():
    datos = pd.read_excel(ARCHIVO_RESULTADOS, sheet_name="Prediccion y Stock", engine="openpyxl")
    catalogo = {}
    for fila in datos.to_dict(orient="records"):
        try:
            codigo = stock_store.code(fila["CODIGO"])
        except ValueError:
            continue
        def texto(nombre):
            valor = fila.get(nombre)
            return None if pd.isna(valor) else str(valor)
        def numero(nombre):
            valor = fila.get(nombre)
            if pd.isna(valor):
                return None
            try:
                valor = float(valor)
                return valor if np.isfinite(valor) else None
            except (ValueError, TypeError):
                return None
        catalogo[codigo] = {
            "codigo": codigo, "descripcion": texto("DESCRIPCION") or "Sin descripción",
            "unidad": texto("UNIDAD") or "Sin unidad", "clase_abc": texto("CLASE_ABC"),
            "prediccion": numero("PREDICCION_SEP_2026"), "stock_actual": numero("STOCK_ACTUAL"),
            "stock_utilizable": numero("STOCK_UTILIZABLE"), "stock_seguridad": numero("STOCK_SEGURIDAD"),
            "reposicion": numero("REPOSICION_AJUSTADA"), "riesgo": texto("RIESGO"),
            "prioridad": texto("PRIORIDAD"), "recomendacion": texto("RECOMENDACION")
        }
    return catalogo

stock_api.configure(catalogo_base_stock, predecir_varios_meses, calcular_stock_proyectado)
app.include_router(stock_api.router)

# Los errores de la base central no exponen claves ni consultas privadas.
if __package__:
    from .supabase_db import CloudError
else:
    from supabase_db import CloudError
from fastapi.responses import JSONResponse
@app.exception_handler(CloudError)
async def error_base_central(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})
