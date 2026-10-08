# Tarea 05 — Cuadernos basados en GitHub

Estado: completado (notebooks limpios, clonación y actualización GitHub probadas).

## Objetivo
Eliminar Base64 y el código embebido de los notebooks Kaggle y Colab. Ambos deben descargar el código desde https://github.com/ThowiLabs/ace-step-kaggle-studio.

## Alcance
- Cuatro celdas: título, clonar/actualizar desde GitHub, dependencias/modelos y ejecución persistente.
- Mantener siete pestañas y preview MP3 sin tocar el Studio que ya está funcionando.
- Compatibilidad con sesiones nuevas y nuevas ejecuciones usando `git pull --ff-only`.
- Actualizar pruebas, documentación y commit en español.
- Verificar disponibilidad del repositorio de GitHub y, si hay autorización, publicar la nueva revisión.

## Criterios de verificación
- Los dos .ipynb no contienen Base64, archivos ZIP ni código fuente embebido.
- URL de GitHub correcta, lectura de los scripts desde el clon real.
- Todas las pruebas de la suite pasan.
- ZIP de entrega conserva `.git/`, `contexto/` y `tareas/`.

## Estado remoto
Por comprobar después del commit; no prometer un push sin autenticación válida.
