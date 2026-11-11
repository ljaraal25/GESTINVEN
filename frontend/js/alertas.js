const tabla =
    document.getElementById("tablaAlertas");


async function cargarAlertas() {

    try {

        const respuesta = await fetch(
            "http://127.0.0.1:8000/alertas"
        );

        const alertas =
            await respuesta.json();

        tabla.innerHTML = "";

        if (alertas.length === 0) {

            tabla.innerHTML = `
                <tr>
                    <td colspan="9">
                        No existen alertas.
                    </td>
                </tr>
            `;

            return;
        }

        alertas.forEach(producto => {

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
                    ${producto.REPOSICION_AJUSTADA}
                </td>

                <td>${producto.RIESGO}</td>

                <td>${producto.PRIORIDAD}</td>

                <td>${producto.RECOMENDACION}</td>
            `;

            tabla.appendChild(fila);
        });

    } catch (error) {

        tabla.innerHTML = `
            <tr>
                <td colspan="9">
                    Error al cargar las alertas.
                </td>
            </tr>
        `;

        console.error(error);
    }
}


cargarAlertas();