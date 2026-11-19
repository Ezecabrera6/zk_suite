# zk_suite: edición de video por código

Suite para editar videos de YouTube **sin editor visual**: la toma se transcribe con Whisper, el corte se escribe
como un EDL (lista de tramos) sobre esa transcripción, ffmpeg arma el video y un visor web local muestra cada preview
para dejar comentarios con el minuto exacto. Los comentarios vuelven a quien edita (una persona o una sesión de Claude
Code), que corrige el EDL y saca otra versión.

Nació en un canal tech de YouTube, donde cada video se editó así entre octubre y noviembre de 2026. Está en español
porque el canal y las reglas de edición están en español.

> **Estado.** Son herramientas de trabajo reales, sacadas de los proyectos de cada video y limpiadas para publicar.
> Lo de `render/`, `edl/`, `visor/`, `audio/`, `subtitulos/`, `control/` y `vedit/` sirve para cualquier video.
> Lo de `ejemplos/` quedó atado al video donde nació (tiempos, frases y cámaras de esa toma) y se deja como
> referencia para copiar y adaptar. No hay tests automáticos: cada script se probó en su video original.

## Con Claude Code

Cloná el repo, abrilo con Claude Code y pedile «editemos el video nuevo». [`CLAUDE.md`](CLAUDE.md) le explica
la suite, el flujo y las reglas. También se usa a mano: todo está documentado carpeta por carpeta.

## Para editar un video nuevo: el estudio

```bash
python estudio/servidor.py      # http://127.0.0.1:8780/
```

Se elige la toma de OBS y el estudio hace voz, proxy, transcripción y silencios. Después se edita sobre el texto
(cortar palabras, borrar silencios, carteles, cámara por tramo) con versiones y deshacer, y se renderiza con la cámara
según lo que se dice. Ver [estudio/README.md](estudio/README.md).

## El flujo completo (las piezas sueltas)

```
 Toma de OBS multicámara (programa + una ISO por cámara + el micrófono crudo en su propia pista)
   │
   ├─ audio/voz_cadena_c.py ............ voz limpia (cadena C) + voz16k.wav para los controles
   ├─ edl/transcribir*.py ............... transcripción con marcas por palabra (JSON + TXT)
   └─ edl/tx_por_pausas.py ............. transcripción frase por frase: no se pierden las retomas
   │
   ▼
 EDL: qué tramos quedan, en qué orden y con qué cámara
   ├─ edl/edl_auto.py ................... primer corte automático (saca retomas y muletillas)
   ├─ visor/multicam/ ................... editor de corte con las 3 cámaras, en el navegador
   └─ a mano, por renglones de la transcripción (ver ejemplos/m999/edl_manual.py)
   │
   ▼
 control/bordes_edl.py, chequeo_tramos.py, chequeo_edl.py ... ¿algún corte se come una palabra? ¿quedó una retoma?
   │
   ▼
 Render de preview (rápido)
   ├─ render/preview_360p.py ............ 360p desde un edl.json simple
   ├─ render/editar.py preview .......... 720p desde un proyecto.json (toma + narraciones + fotos + rótulos)
   └─ ejemplos/*/render*.py ............. multicámara (--360): cámara según lo que se dice, corte cada ~2,3 s
   │
   ▼
 visor/ ................................ la última preview siempre a mano, comentarios atados a la versión
   │                                     y botón «Enviar a corregir» → correcciones en JSON
   ▼
 Correcciones en el EDL → nueva versión → visor … (se repite hasta el OK)
   │
   ▼
 Render final 1080p (render/editar.py final, o --final en los renders de ejemplo), −14 LUFS / −1 dBTP
   │
   ▼
 control/control_borrador.py .......... frase por frase sobre el final: muletillas, frases colgadas, cuadros negros,
                                         loudness y true peak. Si encuentra algo: «NO SE SUBE».
   │
   ▼
 subtitulos/ (SRT del final) · render/shorts.py (Shorts 9:16) · graficos/ (rótulos y carteles)
```

Las reglas de ritmo y de cámara que siguen todos los renders están en [docs/REGLAS.md](docs/REGLAS.md).

## Estructura

| Carpeta | Qué hay |
|---|---|
| [`estudio/`](estudio/README.md) | **La página para editar un video desde los crudos** (usa las demás piezas) |
| [`render/`](render/README.md) | Render del video largo desde `proyecto.json`, Shorts 9:16 y preview rápida en 360p |
| [`edl/`](edl/README.md) | Transcripción con Whisper (CPU y GPU, entera y pausa por pausa) y primer corte automático |
| [`visor/`](visor/README.md) | Visor de previews con comentarios y el editor de corte multicámara |
| [`audio/`](audio/README.md) | Voz con la cadena C y análisis de audio contra el estándar del canal |
| [`subtitulos/`](subtitulos/README.md) | SRT desde la transcripción de la toma o desde el render final |
| [`control/`](control/README.md) | Controles antes de renderizar y antes de subir |
| [`graficos/`](graficos/README.md) | Motor de escenas dibujadas con PIL, estilo del canal y lower third |
| [`vedit/`](vedit/README.md) | Editor más completo con proxy, timeline versionada, preview en vivo y render parcial |
| [`ejemplos/`](ejemplos/README.md) | Renders multicámara reales (Redragon M999 y Fizz Pro) y un `proyecto.json` de ejemplo |
| [`docs/`](docs/REGLAS.md) | Reglas de edición |

## Carpetas de cada video

Todos los scripts esperan la misma estructura dentro de la carpeta de cada video:

```
mi_video/
  01_main/          tomas de OBS (copia; el original no se toca)
  06_material_usuario/  fotos, capturas y clips de B-roll
  07_narraciones/   narraciones grabadas aparte
  10_work/          temporales (se pueden borrar al terminar)
  11_exports/       previews/, final/, shorts/
  12_project/       proyecto.json o EDL, analysis/ (transcripciones, voz16k.wav), correcciones del visor
```

## Instalación

Requisitos:
- **Python 3.12** (se usó en Windows 11).
- **ffmpeg 6 o más nuevo** en el PATH, con `libx264`. Para el render rápido de los ejemplos hace falta `h264_nvenc`
  (placa NVIDIA); si no hay, cambiá `h264_nvenc` por `libx264` en esos scripts.
- Para Whisper en GPU: CUDA 12 con cuDNN. Los scripts buscan las DLL de `nvidia-*` instaladas con pip en
  `%APPDATA%\Python\Python312\site-packages\nvidia`. Sin GPU, `edl/transcribir.py` transcribe en CPU; los demás scripts de Whisper (`tx_por_pausas.py`, los controles
  y `srt_render.py`) hoy piden CUDA: para correrlos en CPU hay que cambiar `device="cuda", compute_type="int8_float16"`
  por `device="cpu", compute_type="int8"`.

```bash
pip install -r requirements.txt
```

Configuración: copiá `config.example.env` a `.env` (está en `.gitignore`), completá tus rutas y cargalo antes de
correr los scripts. Ninguna ruta personal está escrita en el código.

## Seguridad y privacidad

- Los visores escuchan solo en `127.0.0.1`.
- El repo no lleva medios, transcripciones, correcciones ni logs: el `.gitignore` los deja afuera. Antes de exportar
  un video, revisá en 1080p que no se lea nada privado en cuadro (etiquetas de envío, pantallas, pestañas).

## Licencia

MIT. Ver [LICENSE](LICENSE).
