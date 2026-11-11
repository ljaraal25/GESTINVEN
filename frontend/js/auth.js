const sesionActiva =
    sessionStorage.getItem(
        "sesionActiva"
    );

if (sesionActiva !== "true") {

    window.location.href =
        "login.html";
}