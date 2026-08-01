# CICE Coco Pops — aplicación web conectada con Odoo

Esta versión funciona desde navegador y no necesita ejecutar archivos `.bat` o `.ps1`.

## Qué incluye

- Inventario real de productos terminados por categorías.
- Producción del día desde órdenes de fabricación.
- Ventas confirmadas del día.
- Facturación publicada del día.
- Vista adaptable a celular y computadora.
- Actualización automática cada 5 minutos.
- La clave API se guarda únicamente como variable secreta del servidor.

## Publicación sencilla en Render

1. Crea una cuenta en Render.
2. Sube esta carpeta a un repositorio privado de GitHub.
3. En Render elige **New > Blueprint** y selecciona el repositorio.
4. Render detectará `render.yaml`.
5. Cuando solicite `ODOO_API_KEY`, pega la clave API directamente en Render.
6. Pulsa **Deploy**.
7. Render entregará un enlace similar a:
   `https://cice-coco-pops.onrender.com`

No pongas la clave en GitHub, WhatsApp, correo ni dentro del código.

## Prueba local opcional

1. Instala Python 3.11 o superior.
2. Copia `.env.example` como `.env`.
3. Coloca la clave API en `.env`.
4. Ejecuta:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

5. Abre `http://127.0.0.1:8000`.

## Ajustes que deben validarse con datos reales

- Nombre exacto de la base de datos.
- Categorías exactas de producto terminado.
- Unidad adecuada para paletas y nieves.
- Regla real de inventario bajo por producto.
- Campo y horario que Coco Pops considera como “producción del día”.
- Si “ventas del día” debe usar confirmación del pedido, fecha de entrega o factura.

## Seguridad recomendada

Crear posteriormente en Odoo un usuario independiente llamado `CICE Consulta`, con acceso mínimo de lectura. La clave API hereda los permisos del usuario que la creó.
