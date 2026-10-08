# Tarea 04 — Separación instrumental y stems

Estado: pendiente (investigación concluida, integración no autorizada).

## Objetivo
Mostrar nombres de instrumentos en español, proporcionar instrumental sin voces y descarga ZIP de pistas.

## Límites
- `extract` del modelo Base ofrece 12 categorías aproximadas y no garantiza stems aislados.
- La eliminación de voces requiere probar un motor especializado (HTDemucs/RoFormer).
- Elegir implementación compatible con Kaggle/Colab tras evaluar CUDA, calidad, tiempos y licencias.

## Pasos pendientes
Probar separador externo aislado con audio corto; medir recursos; documentar resultados antes de añadir dependencias o UI nueva.
