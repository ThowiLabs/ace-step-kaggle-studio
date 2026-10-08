# Tarea 03 — Versionado persistente Ponytail

Estado: completado (estructura, validación y empaquetado verificados).

## Objetivo
Conservar la rama main, agregar documentación persistente, completar control de versiones y exportar un ZIP con historial Git.

## Pasos
1. Verificar autor GitHub y configuración local del repositorio.
2. Crear `contexto/` y `tareas/`.
3. Ajustar mensajes y documentación para que respeten Ponytail.
4. Regenerar notebooks y ejecutar pruebas.
5. Crear un commit posterior al inicial con autor ThowiLabs.
6. Crear un tag de versión y ZIP que incluya `.git/`.
7. Cambiar el prefijo de esta tarea a `completado-`.

## Verificación
`python -m unittest discover -s tests -v`, `git log --format=fuller`, `git fsck --full`, inspección del ZIP.
