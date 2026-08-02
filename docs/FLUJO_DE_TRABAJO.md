# Flujo de trabajo profesional de CICE

## Dos versiones del sistema

### Producción
Es la versión que usa la CEO.

- Rama de GitHub: `main`
- Servicio de Render: `CICE-CocoPops`
- Solo recibe cambios ya revisados.

### Desarrollo
Es una copia para probar cambios sin afectar a la CEO.

- Rama de GitHub: `desarrollo`
- Servicio sugerido de Render: `cice-coco-pops-desarrollo`
- Aquí se prueban primero las nuevas funciones.

## Proceso para cada actualización

1. Cambiar GitHub Desktop a la rama `desarrollo`.
2. Copiar los archivos nuevos.
3. Hacer Commit.
4. Hacer Push origin.
5. Abrir el enlace de pruebas de Render.
6. Revisar que Inventario, Producción y Ventas funcionen.
7. Cuando todo esté correcto, crear una solicitud para pasar los cambios a `main`.
8. Render publicará la actualización en el enlace oficial.

## Versiones

- Cambio pequeño o corrección: 5.1.1
- Función nueva compatible: 5.2.0
- Rediseño o cambio grande: 6.0.0

El número actual está guardado en el archivo `VERSION`.

## Validación automática

GitHub revisará automáticamente:

- Que el código de Python tenga sintaxis válida.
- Que las reglas de Paletas y Fabricación sigan funcionando.
- Que la lógica del semáforo de inventario no se rompa.

Si aparece una marca verde en GitHub, la validación terminó correctamente.
Si aparece una X roja, el cambio no debe pasar a producción.
