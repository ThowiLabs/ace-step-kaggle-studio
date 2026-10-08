# Fecha
2026-10-08

# Objetivo
Documentar la estrategia de control de versiones y entrega conforme a Ponytail.

# Decisiones tomadas
- Conservar el commit raíz `215ed81bd938914522fab973a5a067b209739cb7` sin reescrituras.
- Añadir cambios mediante commits posteriores con texto en español.
- Formato: `Summary:` seguido de una acción; `Description:` seguido de una explicación técnica.
- Autor para nuevos commits: `ThowiLabs <291061271+ThowiLabs@users.noreply.github.com>`.
- Los ZIP descargables deben contener `.git/`, `contexto/` y `tareas/`.
- No empaquetar datos, pesos, audios, certificados, caches ni secretos.
- Registrar las versiones mediante tags Git sin reemplazar ni borrar tags anteriores.

# Arquitectura actual
Un solo repositorio Git con rama `main`, archivos fuente versionados y artefactos de ejecución ignorados.

# Librerías usadas
Git, Python (zipfile y scripts de prueba).

# Archivos importantes modificados
`.gitignore`, `README.md`, `contexto/`, `tareas/`, `scripts/build_notebooks.py`, `notebooks/` y `tests/`.

# Problemas encontrados
El commit inicial se creó con identidad genérica y título en inglés antes de estudiar Ponytail. No se reescribe porque rompería la regla de conservar el historial. La cuenta remota GitHub aún no está autorizada.

# Soluciones implementadas
Los commits nuevos emplean autor ThowiLabs y mensajes en español, y el ZIP incluirá el historial completo. El primer commit queda como antecedente histórico.

# Pendientes
Conectar GitHub para publicar `ThowiLabs/ace-step-kaggle-studio` si la cuenta autorizada dispone de permisos.

# Próximos pasos
Verificar `git log`, `git fsck`, estado de tareas y ZIP exportado; realizar publicación remota.
