# Fecha
2026-10-08

# Objetivo
Mantener ACE-Step Kaggle Studio como repositorio reproducible para Kaggle y Google Colab con interfaces de generación y edición musical.

# Decisiones tomadas
- Rama principal: `main`.
- Preservar el historial Git; prohibido reinicializar el repositorio o reescribir commits publicados.
- Autor de los commits nuevos: `ThowiLabs`, correo `291061271+ThowiLabs@users.noreply.github.com`.
- Descargar pesos GGUF durante la instalación; no incluir pesos ni binarios precompilados en Git.
- Generación y edición musical separadas en siete pestañas; audio de vista previa MP3 128 kbps y descarga WAV completa.
- Los notebooks Kaggle y Colab obtienen el código mediante `git clone` de `https://github.com/ThowiLabs/ace-step-kaggle-studio` y se ejecutan con Run All. No embeben archivos ni Base64.
- Interfaz operativa mientras el entorno de ejecución continúe activo; el cierre forzoso del proveedor está fuera del control del proyecto.

# Arquitectura actual
- `studio_tabs.py`: interfaz de siete modos y procesamiento de archivos de referencia.
- `studio_smart.py`: generación y validación de planificación musical.
- `studio_preview.py`: vista previa comprimida sin modificar WAV original.
- `studio_gguf.py`, `studio_diagnostic.py`: utilidades de servidor y diagnóstico.
- `scripts/install.py`: preparación del motor, GPU y modelos.
- `scripts/run.py`, `scripts/gradio_guard.py`: lanzamiento y ciclo de vida de los procesos.
- `scripts/build_notebooks.py`: construcción de cuadernos autónomos.

# Librerías usadas
Python, Gradio, requests, NumPy, soundfile, huggingface-hub, FFmpeg, `acestep.cpp` y GGUF de ACE-Step 1.5. Git para versionado.

# Archivos importantes modificados
README.md, .gitignore, notebooks/ y los módulos de Studio mencionados anteriormente.

# Problemas encontrados
- Un plan LM degenerado puede producir repeticiones musicales.
- Cover FSQ puede perder estructura, especialmente en entradas largas.
- El primer paquete no contenía `.git/`, `contexto/` ni `tareas/`.
- La sesión de Kaggle o Colab puede finalizar por límites propios de la plataforma.
- Compatibilidad de controladores CUDA antiguos en Colab pendiente de validación.

# Soluciones implementadas
- Diagnóstico y reintentos de LM.
- Cover corto de prueba y variante sin FSQ para audio largo.
- Vista previa MP3 128 kbps con WAV original descargable.
- Cuadernos Kaggle y Colab sin dependencias de un clon Git remoto.
- Historial Git conservado y estructura de trabajo Ponytail agregada.

# Pendientes
- Verificar el notebook en una sesión real de Google Colab.
- Evaluar separadores de stems externos antes de su integración.
- Publicar en GitHub tras autorización de la cuenta.

# Próximos pasos
Validar despliegue, probar calidad de separación y publicar la versión desde la cuenta autorizada.
