const formulario = document.getElementById("formLogin");
const mensaje = document.getElementById("mensaje");

formulario.addEventListener("submit", async function (event) {

    event.preventDefault();

    const usuario = document.getElementById("usuario").value;
    const password = document.getElementById("password").value;

    mensaje.textContent = "Verificando...";

    try {

        const respuesta = await fetch(
            "https://api-gestinven.onrender.com/login",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    usuario: usuario,
                    password: password
                })
            }
        );

        const datos = await respuesta.json();

       if (datos.acceso) {

    sessionStorage.setItem(
        "sesionActiva",
        "true"
    );

    mensaje.textContent =
        "Inicio de sesión correcto";

    setTimeout(function () {

        window.location.href =
            "../dashboard/";

    }, 700);



        } else {

            mensaje.textContent = datos.mensaje;

        }

    } catch (error) {

        mensaje.textContent =
            "No se pudo conectar con el servidor.";

        console.error(error);
    }
}
);