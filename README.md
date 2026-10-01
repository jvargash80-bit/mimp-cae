# MIMP-CAE — Sistema de separación de aulas

Sistema web para reservar automáticamente 3 aulas y 2 salones por horario.

## Características

- Reservas por fecha y hora.
- Confirmación automática si el espacio está libre.
- Bloqueo de cruces de horario.
- 3 aulas y 2 salones configurados.
- Consulta y cancelación de reservas.
- PostgreSQL en Render mediante `DATABASE_URL`.
- SQLite como respaldo para desarrollo local.
- Endpoint `/healthz` para comprobar el servicio.

## Publicación en Render

El proyecto incluye `render.yaml` para crear el Web Service y PostgreSQL automáticamente desde un Blueprint.

1. Sube el contenido de esta carpeta a un repositorio de GitHub.
2. En Render crea un **New Blueprint Instance** y selecciona el repositorio.
3. Render leerá `render.yaml` y configurará el servicio `mimp-cae` y la base de datos `mimp-cae-db`.
4. Revisa el plan **Free** y despliega.
5. Abre la URL `.onrender.com` que Render entregue.

### Importante sobre el plan gratuito

Render permite actualmente Web Services y Postgres gratuitos, pero su documentación indica que los Web Services gratuitos se suspenden tras inactividad y que las bases de datos Postgres gratuitas **expiran a los 30 días**. Por ello esta configuración es apropiada para pruebas/demostración, no para guardar datos institucionales reales a largo plazo sin cambiar el plan y la estrategia de respaldo.

## Ejecución local

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Sin `DATABASE_URL`, la aplicación usa SQLite localmente. Con `DATABASE_URL`, usa PostgreSQL.
