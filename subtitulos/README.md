# subtitulos/

| Script | De dónde saca el texto | Uso |
|---|---|---|
| `srt_render.py` | **transcribe el mp4 final** con Whisper en GPU (lo más confiable) | `python subtitulos/srt_render.py final.mp4 final_es.srt [correcciones.json]` |
| `subtitulos.py` | las palabras de la toma y de las narraciones, mapeadas al tiempo de edición por `render/editar.py` | `python subtitulos/subtitulos.py C:/ruta/a/mi_video/12_project/proyecto.json final` |

Reglas de los dos: cues de hasta 42 caracteres, sin superponerse (YouTube Studio rechaza un SRT con tiempos que se
pisan) y mayúscula después de punto.

- `srt_render.py`: cues de hasta 3,5 s; corta en pausas de más de 0,8 s y en fin de oración. `correcciones.json` es
  `{"regex": "reemplazo"}` para palabras que Whisper entiende mal.
- `subtitulos.py`: necesita `10_work/<slug>/final/timeline_final.json` (lo deja `render/editar.py`) y usa
  `correcciones_subtitulos` del `proyecto.json`. Escribe `11_exports/final/<slug>_subtitulos_es.srt`.
