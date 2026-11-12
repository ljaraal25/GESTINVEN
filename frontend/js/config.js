'use strict';
// El frontend local usa el backend local; GitHub Pages conserva el backend publicado.
window.GESTINVEN_API_URL = ['localhost','127.0.0.1'].includes(window.location.hostname)
    ? 'http://127.0.0.1:8000'
    : 'https://api-gestinven.onrender.com';
