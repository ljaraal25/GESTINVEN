# Evaluación centralizada en Supabase

La aplicación consulta PostgreSQL de Supabase. Los movimientos de evaluación, la bitácora de consultas y las cargas de stock se conservan en esa base. Los archivos Excel del modelo predictivo siguen siendo archivos de entrada.

## Configuración del servidor

Configurar SUPABASE_URL y SUPABASE_SECRET_KEY en Environment de Render. La clave secreta solo se usa en el backend. No publicar .env.

## Resultados y consultas

El comparativo presenta los porcentajes reportados del estudio almacenados en Supabase. Se retiró el selector de fuentes. El detalle se calcula en cada consulta sobre los movimientos mediante gest_consulta y gest_comparativo. Las vistas v_resumen_semanal y v_indicadores_semanales permiten revisar el cálculo en SQL Editor.

La eficiencia calculada y la reportada tienen diferencias pendientes de conciliación. El sistema conserva ambas sin modificar cifras para forzar coincidencias.

Los registros históricos importados conservan su procedencia y fecha original; una importación actual no acredita que una operación haya sido registrada por este sistema en el pasado.

## Consultar desde la computadora

Ejecutar Abrir_Supabase.cmd, o usar SQL Editor de Supabase con backend/consultas_evaluacion.sql. Los antiguos importadores SQLite están retirados. Las copias locales anteriores son respaldos y no se publican.

## Publicación

Los scripts de migración ya se ejecutaron en este proyecto. No volver a ejecutar la migración inicial sobre la base existente. Publicar los cambios en main; comprobar que GitHub Pages y Render desplieguen el mismo commit. Iniciar sesión nuevamente después del reinicio del backend.
