# vedit/

Editor más completo, con la misma idea (Claude orquesta, ffmpeg renderiza, el navegador muestra), pensado para un
video con una fuente principal. Es el primer sistema que se armó; los renders de `ejemplos/` vinieron después y son
más simples. Solo librería estándar + Pillow; `faster-whisper` es opcional.

```bash
python vedit/main.py --project C:/ruta/a/mi_video check        # prueba de verdad cada encoder → 12_project/hardware.json
python vedit/main.py --project C:/ruta/a/mi_video proxy        # proxy 720p30 incremental (se puede cortar y retomar)
python vedit/main.py --project C:/ruta/a/mi_video watch        # preview en vivo en el navegador (127.0.0.1:8765)
python vedit/main.py --project C:/ruta/a/mi_video timeline list|show|undo|restore N
python vedit/main.py --project C:/ruta/a/mi_video preview --from 120 --to 160    # render parcial (tiempo de la fuente)
python vedit/main.py --project C:/ruta/a/mi_video preview --full
python vedit/main.py --project C:/ruta/a/mi_video transcribe   # faster-whisper → transcript.json
python vedit/main.py --project C:/ruta/a/mi_video subtitles    # SRT / VTT / ASS
python vedit/main.py --project C:/ruta/a/mi_video render --confirm   # final desde los originales
```

En lugar de `--project` se puede usar la variable `VEDIT_PROJECT`.

## Cómo funciona

- **Proyecto**: `12_project/project.json` con `sources.main.path` (relativo a la carpeta del video). Todas las rutas
  en los JSON son relativas, así el proyecto se puede mover.
- **Timeline** (`vedit/timeline.py`): la fuente de verdad, no destructiva y versionada (`timelines/vNNN.json` +
  `timeline_current.json`); se puede deshacer y volver a cualquier versión. Cada clip lleva su in/out, efectos,
  recuadros y gráficos.
- **Proxy** (`vedit/proxy.py`): 720p30 con GOP de 1 s para buscar al instante en el navegador, por bloques cacheados
  y con el audio normalizado para que suene como el final. El original nunca se toca.
- **Render** (`vedit/render.py`): cada clip es un segmento cacheado por hash (fuente, in/out, efectos, perfil); si
  cambia un corte, solo se rehace ese segmento. Se unen sin recomprimir el video.
- **Gráficos** (`vedit/graphics.py`): PNG con alfa dibujados con Pillow y cacheados por hash; los mismos en la
  preview del navegador y en el render.
- **Servidor** (`vedit/server.py` + `ui/`): la interfaz se recarga sola cuando cambia la timeline. `ui/ab.html` y
  `ui/compare.html` comparan dos versiones lado a lado.

## Variables de entorno

`VEDIT_PROJECT`, `VEDIT_FFMPEG`, `VEDIT_FFPROBE`, `VEDIT_FONT`, `VEDIT_STAGE_DIR`. Los gráficos buscan Poppins en
`04_graphics/fonts/` dentro del proyecto y, si no está, una fuente del sistema.

Restos del video donde nació (no molestan): el modo A/B espera archivos de una edición previa
(`editorial_conform.json`, `timeline_preedited_base.json`) y `compare.html` usa etiquetas de ese video.
