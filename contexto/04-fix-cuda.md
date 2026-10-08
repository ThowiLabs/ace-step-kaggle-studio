# Fecha
2026-10-08

# Objetivo
Corregir el error de inicio `ace-server` con código 127 en cuadernos de Kaggle/Colab al utilizar el motor CUDA 13 precompilado.

# Decisiones tomadas
- Resolver la causa en `scripts/run.py` para conservar los notebooks pequeños y sin Base64/ZIP.
- Detectar dinámicamente rutas NVIDIA de CUDA 13 a partir de ubicaciones de paquetes Python, tanto `site-packages` como `dist-packages`; preservar `LD_LIBRARY_PATH` anterior.
- Validar enlaces dinámicos mediante `ldd` antes de lanzar procesos y señalar bibliotecas faltantes sin mensajes engañosos.
- No ejecutar ni reiniciar ACE-Step ni Gradio durante el arreglo: las instancias existentes siguen bajo control del usuario.
- El usuario solicitó `amend` del último commit local. El `main` remoto seguía en `72a637c` y la versión `v1.0.4` no estaba publicada. Para preservar etiquetas anteriores, la corrección usa `v1.0.5` sin mover `v1.0.4`.

# Arquitectura actual
El notebook clona GitHub, instala pesos con `scripts/install.py` e invoca `scripts/run.py`. Este último prepara el entorno con rutas CUDA detectadas, comprueba `ace-server` y abre después la interfaz de siete pestañas.

# Librerías usadas
Python estándar: `site`, `sysconfig`, `pathlib`, `subprocess`; el sistema `ldd`. No se añadieron dependencias de Python.

# Archivos importantes modificados
`scripts/run.py`, `tests/test_release.py`, `scripts/build_notebooks.py`, dos notebooks, `README.md`, `contexto/04-fix-cuda.md`, `tareas/06-completado-corregir-arranque-cuda.md`.

# Problemas encontrados
- La ruta CUDA13 se construía exclusivamente desde `sys.prefix` y `site-packages/nvidia/cu13/lib`, pero la plataforma puede usar `dist-packages` u otras carpetas NVIDIA.
- `pip` reportó conflictos de dependencias de Starlette independientes del error de carga del binario.
- El mensaje de finalización confundía un error de arranque con una detención manual.
- En el host PL2 actual no se detectaron paquetes `nvidia-cuda-runtime` / `nvidia-cublas` versión 13 para validar directamente el motor precompilado; evitar iniciar un motor adicional con GPU ocupada.

# Soluciones implementadas
- `cuda_library_dirs` busca bibliotecas con sufijo `.so.13` entre los paquetes NVIDIA instalados y agrega sus carpetas a `LD_LIBRARY_PATH`.
- `check_engine_dependencies` comprueba el cargador dinámico con `ldd` y explica los nombres de bibliotecas faltantes.
- Mensaje correcto de finalización en caso de excepción.
- Versiones de metadatos de notebook actualizadas a `1.0.5` (siguen teniendo cuatro celdas).
- Suite offline ampliada de 8 a 12 pruebas; 12/12 aprobadas. Los tests que usan Gradio emitieron avisos `ResourceWarning` por event loops, sin fallos.

# Pendientes
- Verificar el despliegue end-to-end en una nueva sesión limpia de Kaggle con las librerías CUDA 13 realmente instaladas y en Google Colab GPU.
- Publicar `main` y el tag nuevo cuando exista acceso GitHub autorizado, sin `force push`.
- Separación de stems permanece en su tarea independiente.

# Próximos pasos
Ejecutar los cuadernos actualizados desde un clon del repo publicado; confirmar `ace-server` con generación breve, preservando instancias previas.
