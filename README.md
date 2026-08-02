# CICE Enterprise 1.0

Centro de Inteligencia Ejecutiva de Coco Pops, conectado con Odoo.

## Funciones activas

- Inventario disponible, a la mano y reservado.
- Comparación producto por producto contra stock mínimo.
- Categorías ejecutivas, incluyendo Paletas y Fabricación/Ingredientes agrupadas.
- Producción y ventas del día.
- Prioridades para la CEO.
- Copiloto de consultas controladas.
- Históricos y Data Warehouse cuando `DATABASE_URL` está configurada.

## Arquitectura

- `app/main.py`: rutas web y ciclo de vida.
- `app/services/dashboard.py`: snapshot operativo, concurrencia y caché.
- `app/services/inventory.py`: inventario y categorías.
- `app/services/production.py`: fabricación diaria.
- `app/services/sales.py`: pedidos y facturación.
- `app/services/intelligence.py`: resumen y alertas.
- `app/services/priorities.py`: acciones recomendadas.
- `app/services/copilot.py`: respuestas controladas.
- `app/database.py` y `app/services/warehouse.py`: históricos opcionales.

## Publicación en Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Variables requeridas:

- `ODOO_URL`
- `ODOO_DATABASE`
- `ODOO_API_KEY`
- `TIMEZONE=America/Chihuahua`

Variable opcional:

- `DATABASE_URL` para históricos persistentes.

## Validación

```bash
python -m compileall app
python -m unittest discover -s tests -v
```

La clave de Odoo nunca debe subirse a GitHub.
