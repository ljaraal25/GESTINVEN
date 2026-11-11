const btnCerrarSesion =
    document.getElementById("btnCerrarSesion");


btnCerrarSesion.addEventListener(
    "click",
    function () {

        sessionStorage.removeItem(
            "sesionActiva"
        );

        window.location.href =
            "login.html";
    }
);


async function cargarResumen() {

    try {

        const respuesta = await fetch(
            "https://api-gestinven.onrender.com/resumen"
        );

        const datos = await respuesta.json();

        document.getElementById(
            "totalProductos"
        ).textContent =
            datos.productos_analizados.toLocaleString();


        document.getElementById(
            "demandaPrevista"
        ).textContent =
            datos.demanda_prevista.toLocaleString();


        document.getElementById(
            "productosCriticos"
        ).textContent =
            datos.productos_criticos.toLocaleString();


        document.getElementById(
            "productosReponer"
        ).textContent =
            datos.productos_reponer.toLocaleString();

    } catch (error) {

        console.error(
            "Error al cargar el resumen:",
            error
        );
    }
}


cargarResumen();
async function cargarRiesgos() {

    try {

        const respuesta = await fetch(
            "https://api-gestinven.onrender.com/riesgos-resumen"
        );

        const datos =
            await respuesta.json();


        document.getElementById(
            "riesgoCritico"
        ).textContent =
            datos.critico.toLocaleString();


        document.getElementById(
            "riesgoAlto"
        ).textContent =
            datos.alto.toLocaleString();


        document.getElementById(
            "riesgoMedio"
        ).textContent =
            datos.medio.toLocaleString();


        document.getElementById(
            "riesgoBajo"
        ).textContent =
            datos.bajo.toLocaleString();


    } catch (error) {

        console.error(
            "Error al cargar riesgos:",
            error
        );
    }
}


cargarRiesgos();