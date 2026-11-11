const tabla =
    document.getElementById("tablaInventario");

const buscador =
    document.getElementById("buscarInventario");

let inventario = [];


async function cargarInventario() {

    try {

        const respuesta = await fetch(
            "https://api-gestinven.onrender.com/inventario"
        );

        inventario =
            await respuesta.json();

        mostrarInventario(
            inventario
        );

    } catch (error) {

        tabla.innerHTML = `
            <tr>
                <td colspan="8">
                    Error al cargar el inventario.
                </td>
            </tr>
        `;

        console.error(error);
    }
}


function mostrarInventario(datos) {

    tabla.innerHTML = "";

    if (datos.length === 0) {

        tabla.innerHTML = `
            <tr>
                <td colspan="8">
                    No se encontraron productos.
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

            <td>
                ${producto.UNIDAD || "-"}
            </td>

            <td>
                ${producto.STOCK_ACTUAL}
            </td>

            <td>
                ${producto.STOCK_UTILIZABLE}
            </td>

            <td>
                ${producto.STOCK_SEGURIDAD}
            </td>

            <td>
                ${producto.RIESGO}
            </td>

            <td>
                ${producto.RECOMENDACION}
            </td>
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
            inventario.filter(
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

        mostrarInventario(
            filtrados
        );
    }
);


cargarInventario();