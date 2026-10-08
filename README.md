# ACE-Step Kaggle Studio

Studio de generación musical para **Kaggle y Google Colab**, siete pestañas, Gradio público y ACE-Step 1.5 GGUF. Proyecto comunitario **no oficial**.

## Ejecución

**Run All instala, abre Gradio y NO finaliza automáticamente.** La última celda permanece activa hasta que pulses Stop/Interrupt o la plataforma cierre el runtime. Si el motor o Gradio se cierran por error, el lanzador intentará reiniciarlos sin matar otros servicios del sistema.

### Kaggle

1. Importa **notebooks/ACE-Step-Kaggle-Studio-Kaggle.ipynb**.
2. En Notebook Settings activa GPU NVIDIA e Internet ON.
3. Ejecuta **Run All**. La última celda imprime un enlace temporal de Gradio y se queda abierta.
4. Usa el Studio y conserva el notebook en ejecución.
5. Para cerrar, pulsa Stop / Interrupt.

**Save Version → Save & Run All:** si el notebook se queda vivo para siempre, esa ejecución de Kaggle NO podrá marcarse como Completed. No se puede terminar la misma ejecución y mantener vivo el servidor a la vez. El notebook hace lo que pediste: prioriza Gradio permanente durante la sesión.

### Google Colab

1. Importa **notebooks/ACE-Step-Kaggle-Studio-Colab.ipynb**.
2. Selecciona Runtime → Change runtime type → GPU NVIDIA.
3. Pulsa Runtime → Run all. Abre el enlace Gradio de la última celda.
4. Deja la sesión conectada; Stop/Interrupt para terminar.

### GPU, CUDA y descargas

- La ruta rápida utiliza un binario **Linux CUDA 13.0** ya compilado (no compila nada en Kaggle con driver R580+).
- Un controlador NVIDIA **R580 o superior** permite la ruta precompilada. El instalador comprueba versión, instala las bibliotecas necesarias y verifica el checksum SHA-256 del ejecutable.
- En GPU con controlador antiguo, intenta compilar con el **nvcc** disponible. Esta ruta requiere Git, CMake y CUDA Toolkit y puede tardar mucho; no fue validada aún en cada imagen Colab. Si faltan herramientas muestra un error explícito.
- Descarga los modelos GGUF de Hugging Face (aproximadamente 13 GB de pesos). Necesita Internet y espacio suficiente.
- Kaggle/Colab pueden terminar sesiones por límites propios. Ningún notebook puede impedir un cierre impuesto por la plataforma.
- Desde v1.0.5, el lanzador detecta las rutas de bibliotecas CUDA 13 instaladas por `pip` tanto en `site-packages` como en `dist-packages`, sin depender de una ruta fija. Antes de iniciar `ace-server`, valida las dependencias enlazadas con `ldd` y muestra cuáles faltan en caso de error. No altera bibliotecas ni procesos de otros Studios.

## Corrección v1.0.1: Cover creativo

La transformación de canciones largas en `cover` (FSQ) puede producir loops aunque el WAV no tenga errores de formato. El modelo **XL Turbo** tiene 8 pasos y una fuerza de referencia de 0.5 condiciona apenas 4 pasos con el audio original. Además, el uso involuntario de `[Instrumental]` impide solicitar canto de manera coherente.

**La pestaña Cover creativo ofrece ahora tres estrategias:**

- **Prueba de 45 segundos (recomendada):** usa `cover` original con una influencia mayor de referencia y solo los primeros 45 segundos. Es deliberadamente un fragmento, no una canción completa.
- **Canción completa (más estable):** utiliza `cover-nofsq` para no perder los detalles por la compresión FSQ. Mantiene mejor la estructura original, aunque puede reducir la libertad del cambio de estilo. La fuerza se adapta al intervalo 0.25–0.45.
- **Cover original FSQ (experimental):** procesa toda la canción por el método anterior; puede fallar en canciones largas.

La letra **queda vacía por defecto**. Si quieres voz, escribe o pega una letra real con estrofas y coro. Si no escribes letra, se solicitará una pista instrumental y se indicará en el resultado.

Estos cambios ayudan a probar mejor el modo, pero **no corrigen de manera garantizada los loops internos del modelo**. El motor GGUF se ejecuta sin LM para Cover; la protección contra repeticiones del LM aplica solo a la pestaña Crear canción.

**Recomendación:** prueba 45 segundos de una salsa, verifica que el resultado te guste y solo después ejecuta la canción completa con el método más estable.

## Audio ligero en todas las pestañas (v1.0.2)

Las siete pestañas presentan una **vista previa MP3 a 128 kbps**, que se descarga rápidamente al navegador. El sistema conserva el **WAV PCM original, sin pérdida**, en un control aparte denominado **Descargar WAV original sin pérdida**. La compresión afecta solo a la vista previa; no cambia el resultado del modelo.

Ejemplo medido: una canción de 378 segundos ocupa 69.2 MB en WAV y solo 5.8 MB en MP3 (92% menos) con la misma duración. Requiere FFmpeg con `libmp3lame`, incluido en las imágenes comunes de Kaggle/Colab; si falta, instálalo en el runtime. El primer procesamiento genera ambas versiones; las siguientes reproducciones solo necesitan el MP3.

El control de referencia de entrada sigue aceptando WAV y MP3: cuando se sube WAV original necesita transmitir el archivo entero una vez al servidor para acondicionarlo al modelo. La optimización de preview reduce el peso **del audio de salida al escuchar**, no el de la subida original.

## Siete pestañas

1. **Crear canción:** XL Turbo Q8 + LM 4B Q8, duración automática, detector de loops y reintentos.
2. **Cover creativo:** XL Q8 sobre canción de referencia.
3. **Remix fiel:** XL Q8, cover-nofsq.
4. **Editar fragmento:** XL Q8, repaint de segundos seleccionados.
5. **Añadir instrumento:** Base Q8, modo lego.
6. **Extraer instrumento:** Base Q8, modo extract.
7. **Completar acompañamiento:** Base Q8, modo complete.

Audios de entrada WAV y MP3 (hasta 150 MB y máximo 10 min); se convierten a WAV de 48 kHz. Empieza probando 10–30 segundos para edición. La autoduración de canciones usa duración 0 para pedir al LM que decida; el máximo técnico es 600 segundos, sin garantía de precisión exacta.

## Cuadernos Kaggle y Google Colab

Los dos notebooks son ligeros y descargan el código directamente de [ThowiLabs/ace-step-kaggle-studio](https://github.com/ThowiLabs/ace-step-kaggle-studio) con `git clone --depth 1 --branch main`. No llevan archivos incrustados ni Base64.

Al volver a ejecutar una sesión, el notebook puede actualizar un clon existente con `git pull --ff-only` si su origen coincide. Si ya existe otra carpeta con el mismo nombre, se detiene con un error claro en lugar de sobrescribirla. El entorno necesita acceso a Internet y GPU NVIDIA.

La última celda inicia Gradio y permanece ejecutándose hasta que se detenga manualmente o finalice el entorno de Kaggle o Colab.

Desde un clon local también se ejecuta con estos tres comandos:

    python -m pip install -r requirements.txt
    python scripts/install.py
    python -u scripts/run.py

El ejecutable se inicia en 127.0.0.1:8085 y Gradio abre un enlace temporal. Variables opcionales: ACE_GPU, ACE_SERVER_PORT, GRADIO_PORT. Para volver a generar los notebooks a partir del código:

    python scripts/build_notebooks.py

Pruebas:

    python scripts/install.py --check
    python -m unittest discover -s tests -v

Las pruebas técnicas comprueban que el audio tenga señal válida, pero no aseguran la calidad artística ni que toda la letra sea interpretada. Los loops de códigos LM son un problema conocido: se detectan secuencias degeneradas y se hacen reintentos, sin garantía absoluta.

## Versionado y mantenimiento

- Rama estable: `main`.
- Versión actual: `v1.0.5` (detección de librerías CUDA y notebooks GitHub).
- Responsable del mantenimiento: [ThowiLabs](https://github.com/ThowiLabs).
- Los commits nuevos se escriben en español con encabezados `Summary:` y `Description:`.
- Los cambios relevantes se documentan en `contexto/` y en los archivos numerados de `tareas/`.
- La distribución completa ZIP incluye el historial Git, no solamente los archivos fuente.
- Repositorio público: [ThowiLabs/ace-step-kaggle-studio](https://github.com/ThowiLabs/ace-step-kaggle-studio). Cada versión local se publica mediante un push de `main` y su tag correspondiente.

Para revisar versiones o regresar a un punto conocido:

    git log --oneline --decorate
    git tag --list
    git switch --detach v1.0.4

Para volver a trabajar en la rama:

    git switch main

## Créditos y uso

Mantenimiento: [ThowiLabs](https://github.com/ThowiLabs). Proyecto comunitario no oficial, sin afiliación a los autores de los motores ni a Kaggle/Colab.

- ACE-Step 1.5: https://github.com/ace-step/ACE-Step-1.5
- acestep.cpp: https://github.com/ServeurpersoCom/acestep.cpp
- Modelos cuantizados CC-TM: https://huggingface.co/CC-TM/ACE-Step-1.5-GGUF
- Binario precompilado: https://github.com/animede/momo-song-v4/releases/tag/v0.1.0-rc1

Los modelos y binarios se descargan al instalar; no se distribuyen dentro del repositorio. Revisa las licencias correspondientes antes de utilizar comercialmente modelos, obras o contenido de terceros.
