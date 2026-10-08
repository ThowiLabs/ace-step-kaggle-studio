# Tarea 06 — Corregir carga de bibliotecas CUDA al iniciar

Estado: completado (12 pruebas automáticas aprobadas; falta comprobación end-to-end con CUDA 13 en sesión nueva).

## Objetivo
Resolver el código 127 del motor precompilado al ejecutar Run All en Kaggle/Colab, sin cambiar modelos ni interrumpir Gradio existente.

## Alcance
- Detectar los directorios reales de bibliotecas NVIDIA CUDA 13 mediante rutas de paquetes Python.
- Dar diagnóstico claro si faltan dependencias al cargar ace-server.
- Mantener notebooks mínimos basados en GitHub y el ciclo persistente de Gradio.
- Incorporar pruebas sin arrancar GPU ni alterar procesos existentes.
- Verificar Git y hacer amend solo sobre el commit local no publicado; preservar tag previo.

## Criterios
- Pruebas para ubicaciones `site-packages`, `dist-packages` y paquetes CUDA separados.
- Validación del binario y mensajes comprensibles en caso de bibliotecas faltantes.
- Suite completa aprobada y cuadernos regenerados sin código embebido.
- No reiniciar ni detener instancias activas, ni servicios Lilith.
