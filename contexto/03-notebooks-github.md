# Fecha
2026-10-08

# Objetivo
Sustituir los notebooks incrustados por cuadernos mínimos que descargan ACE-Step Kaggle Studio desde el repositorio público de ThowiLabs.

# Decisiones tomadas
- Repositorio de código: `https://github.com/ThowiLabs/ace-step-kaggle-studio.git`.
- Rama de ejecución: `main`; actualizaciones mediante `git pull --ff-only`, sin borrar ni sobrescribir cambios locales.
- Cuatro celdas: presentación, obtener código, instalar dependencias/modelos, iniciar Gradio.
- No usar Base64, ZIP comprimido ni código fuente incrustado en los .ipynb.
- Mantener la ejecución de Gradio hasta su detención manual; no alterar instancias existentes.
- Conservar el código del Studio y sus modelos tal como estaban en v1.0.3.

# Arquitectura actual
`scripts/build_notebooks.py` escribe notebooks JSON pequeños; el clon Git es el origen único de las fuentes. `scripts/install.py` prepara el motor y los modelos; `scripts/run.py` abre el Studio con siete pestañas, sin cambio funcional respecto a la revisión anterior.

# Librerías usadas
Python estándar (`json`, `pathlib`, `subprocess`), Git y dependencias existentes de `requirements.txt`. No se agregan dependencias.

# Archivos importantes modificados
`scripts/build_notebooks.py`, ambos notebooks en `notebooks/`, `tests/test_release.py`, `README.md`, `contexto/` y `tareas/`.

# Problemas encontrados
Los notebooks anteriores embebían código comprimido en cadenas Base64 y no seguían los cambios del repositorio público. Además, las pruebas anteriores solo comprobaban el ZIP embebido.

# Soluciones implementadas
Usar `git clone` y `git pull --ff-only` desde ThowiLabs, probar la sintaxis de celdas y prohibir cadenas embebidas; mantener el flujo de instalación y Gradio.

# Pendientes
La revisión debe publicarse en GitHub para que los notebooks descarguen esta versión. Verificar en una sesión limpia de Kaggle y en Colab.

# Próximos pasos
Verificar repositorio público, ejecutar pruebas, crear commit/tag v1.0.4 y publicar desde cuenta GitHub autorizada.
