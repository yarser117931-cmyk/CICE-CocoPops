# CICE Coco Pops

Centro de Inteligencia Empresarial conectado con Odoo.

## Arquitectura

- `app/services/inventory.py`: inventarios y mínimos.
- `app/services/production.py`: producción diaria.
- `app/services/sales.py`: ventas y facturación.
- `app/services/intelligence.py`: alertas y recomendaciones.
- `app/odoo.py`: conexión segura con Odoo.

## Flujo profesional

- `main`: versión oficial para la CEO.
- `desarrollo`: versión de pruebas.
- GitHub valida automáticamente el código antes de publicarlo.
- El archivo `VERSION` indica la versión vigente.
- Consulta `docs/FLUJO_DE_TRABAJO.md` para el proceso completo.

## Seguridad

La clave API de Odoo debe mantenerse únicamente en las variables secretas
de Render. Nunca debe escribirse en GitHub ni dentro del código.
