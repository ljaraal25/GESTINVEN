const inputCodigo =
    document.getElementById("codigoProducto");

const btnBuscar =
    document.getElementById("btnBuscar");

const mensaje =
    document.getElementById("mensaje");

const resultado =
    document.getElementById("resultado");

const btnPredecirML =
    document.getElementById("btnPredecirML");

const resultadoML =
    document.getElementById("resultadoML");

const valorPrediccionML =
    document.getElementById("valorPrediccionML");

const mlStock =
    document.getElementById("mlStock");

const mlSeguridad =
    document.getElementById("mlSeguridad");

const mlObjetivo =
    document.getElementById("mlObjetivo");

const mlReposicion =
    document.getElementById("mlReposicion");

const tablaPredicciones =
    document.getElementById("tablaPredicciones");

const tablaStockProyectado =
    document.getElementById("tablaStockProyectado");

async function buscarProducto() {

    const codigo =  inputCodigo.value.trim();

    if (codigo === "") {

        mensaje.textContent =
            "Ingrese un código.";

        resultado.classList.add(
            "oculto"
        );

        return;
    }


    try {

        mensaje.textContent =
            "Consultando...";

        const respuesta = await fetch(
            `http://127.0.0.1:8000/producto/${codigo}`
        );

        const datos = await respuesta.json();

const respuestaPredicciones = await fetch(
    `http://127.0.0.1:8000/predecir-periodo/${codigo}`
);

const datosPredicciones = await respuestaPredicciones.json();
        tablaPredicciones.innerHTML = "";
        tablaStockProyectado.innerHTML = "";
datosPredicciones.proyeccion_stock.forEach(item => {

    const fila = document.createElement("tr");

    fila.innerHTML = `
        <td>${convertirMes(item.mes)}</td>

        <td>
            ${item.stock_proyectado.toLocaleString()}
            unidades
        </td>

        <td>
          <span class="estado-stock ${obtenerClaseEstado(item.estado)}">
        ${item.estado}
    </span>
</td>
    `;

    tablaStockProyectado.appendChild(fila);

});
        if (datosPredicciones.encontrado) {

            datosPredicciones.predicciones.forEach(item => {

        const fila = document.createElement("tr");

        fila.innerHTML = `
            <td>${convertirMes(item.mes)}</td>

            <td>
                ${item.prediccion.toLocaleString()}
                unidades
            </td>
        `;

        tablaPredicciones.appendChild(fila);
    });

}
        if (!datos.encontrado) {

            mensaje.textContent =
                datos.mensaje;

            resultado.classList.add(
                "oculto"
            );

            return;
        }


        mensaje.textContent = "";

        document.getElementById(
            "nombreProducto"
        ).textContent =
            datos.descripcion || "Sin descripción";


        document.getElementById(
            "codigoResultado"
        ).textContent =
            datos.codigo;


        document.getElementById(
            "abcResultado"
        ).textContent =
            datos.clase_abc;


        document.getElementById(
            "prediccionResultado"
        ).textContent =
            datos.prediccion.toLocaleString();


        document.getElementById(
            "stockResultado"
        ).textContent =
            datos.stock_utilizable.toLocaleString();


        document.getElementById(
            "seguridadResultado"
        ).textContent =
            datos.stock_seguridad.toLocaleString();


        document.getElementById(
            "reposicionResultado"
        ).textContent =
            datos.reposicion.toLocaleString();


        document.getElementById(
            "riesgoResultado"
        ).textContent =
            datos.riesgo;


        document.getElementById(
            "prioridadResultado"
        ).textContent =
            datos.prioridad;


        document.getElementById(
            "recomendacionResultado"
        ).textContent =
            datos.recomendacion;


        resultado.classList.remove(
            "oculto"
        );


    } catch (error) {

        mensaje.textContent =
            "Error al consultar el producto.";

        resultado.classList.add(
            "oculto"
        );

        console.error(error);
    }
}


btnBuscar.addEventListener(
    "click",
    buscarProducto
);


inputCodigo.addEventListener(
    "keydown",
    function (event) {

        if (event.key === "Enter") {
            buscarProducto();
        }
    }
);
btnPredecirML.addEventListener(
    "click",
    async function () {

        const codigo =
            inputCodigo.value.trim();

        if (codigo === "") {
            return;
        }

        try {

            btnPredecirML.textContent =
             "Calculando predicción...";

            btnPredecirML.disabled = true;

            const respuesta = await fetch(
                `http://127.0.0.1:8000/predecir/${codigo}`
            );

            const datos =
                await respuesta.json();


            if (!datos.encontrado) {

                mensaje.textContent =
                    datos.mensaje;

                resultadoML.classList.add(
                    "oculto"
                );

                return;
            }


            valorPrediccionML.textContent =
                datos.prediccion_ml.toLocaleString();
            mlStock.textContent =
            datos.stock_utilizable.toLocaleString();

            mlSeguridad.textContent =
            datos.stock_seguridad.toLocaleString();

            mlObjetivo.textContent =
            datos.stock_objetivo.toLocaleString();

            mlReposicion.textContent =
            datos.reposicion_sugerida.toLocaleString();
            resultadoML.classList.remove(
                "oculto"
            );


        } catch (error) {

            mensaje.textContent =
                "No se pudo generar la predicción.";
            console.error(error);

        } finally {

            btnPredecirML.textContent =
             "Calcular predicción con ML";
            btnPredecirML.disabled = false;
        }
    }
);
function convertirMes(mes) {

    const nombres = {
        "2026-09": "Septiembre 2026",
        "2026-10": "Octubre 2026",
        "2026-11": "Noviembre 2026",
        "2026-12": "Diciembre 2026"
    };

    return nombres[mes] || mes;
}

function obtenerClaseEstado(estado) {

    if (estado === "STOCK SUFICIENTE") {
        return "estado-suficiente";
    }

    if (estado === "STOCK BAJO") {
        return "estado-bajo";
    }

    if (estado === "RIESGO DE DESABASTECIMIENTO") {
        return "estado-riesgo";
    }

    return "";
}