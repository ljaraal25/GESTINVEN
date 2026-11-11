const tabla =
    document.getElementById("tablaPredicciones");

const buscador =
    document.getElementById("buscarProducto");

let predicciones = [];


async function cargarPredicciones() {

    try {

        const respuesta = await fetch(
            "http://127.0.0.1:8000/predicciones"
        );

        predicciones =
            await respuesta.json();

        mostrarPredicciones(
            predicciones
        );

    } catch (error) {

        tabla.innerHTML = `
            <tr>
                <td colspan="10">
                    Error al cargar las predicciones.
                </td>
            </tr>
        `;

        console.error(error);
    }
}


function mostrarPredicciones(datos) {

    tabla.innerHTML = "";

    if (datos.length === 0) {

        tabla.innerHTML = `
            <tr>
                <td colspan="10">
                    No se encontraron resultados.
                </td>
            </tr>
        `;

        return;
    }


    datos.forEach(producto => {

        const fila =
            document.createElement("tr");

        fila.innerHTML = `
            <td>${producto.CODIGO}</td>

            <td>
                ${producto.DESCRIPCION || "Sin registro"}
            </td>

            <td>${producto.CLASE_ABC}</td>

            <td>
                ${producto.PREDICCION_SEP_2026}
            </td>

            <td>
                ${producto.STOCK_UTILIZABLE}
            </td>

            <td>
                ${producto.STOCK_SEGURIDAD}
            </td>

            <td>
                ${producto.REPOSICION_AJUSTADA}
            </td>

            <td>${producto.RIESGO}</td>

            <td>${producto.PRIORIDAD}</td>

            <td>${producto.RECOMENDACION}</td>
        `;

        tabla.appendChild(fila);
    });
}


buscador.addEventListener(
    "input",
    function () {

        const texto =
            buscador.value
            .toLowerCase();

        const filtrados =
            predicciones.filter(
                producto => {

                    const codigo =
                        String(
                            producto.CODIGO
                        ).toLowerCase();

                    const descripcion =
                        String(
                            producto.DESCRIPCION
                        ).toLowerCase();

                    return (
                        codigo.includes(texto)
                        ||
                        descripcion.includes(texto)
                    );
                }
            );

        mostrarPredicciones(
            filtrados
        );
    }
);


cargarPredicciones();