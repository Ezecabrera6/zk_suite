# render/

Arman el video con ffmpeg. Todos trabajan sobre la [estructura de carpetas de cada video](../README.md#carpetas-de-cada-video).

## editar.py: video largo desde un proyecto.json

```bash
python render/editar.py C:/ruta/a/mi_video/12_project/proyecto.json preview   # 1280x720 rápido
python render/editar.py C:/ruta/a/mi_video/12_project/proyecto.json final     # 1920x1080, x264 slow crf 17
```

Estructura que arma: **gancho** (una narración sobre un plano de la toma) → **logo** → **cuerpo** (los tramos `keep`
de la toma, partidos por frase en bloques de 6–14 s con encuadre alterno 1.0 / 1.14, fotos a pantalla completa con su
narración y rótulos con panel translúcido) → **outro**. Música baja con ducking (la voz manda) y master a −14 LUFS.

El formato completo está en [`ejemplos/proyecto/proyecto_ejemplo.json`](../ejemplos/proyecto/proyecto_ejemplo.json):

| Clave | Qué es |
|---|---|
| `proyecto` | carpeta del video |
| `slug`, `version` | nombre de salida: `11_exports/previews/<slug>_<version>_720p.mp4` |
| `toma`, `transcripcion` | la toma (relativa al proyecto) y su transcripción en `12_project/analysis/` |
| `narraciones`, `transcripciones_narraciones` | narraciones grabadas aparte, con su transcripción |
| `keep` | tramos `[desde, hasta]` de la toma; un 3.er valor opcional es el aire antes del tramo; `"exacto"` como 4.º no ajusta a las palabras; `"FOTOS"` marca dónde entra el montaje de fotos |
| `gancho` | `{narr, desde, hasta, plano}`: narración del gancho y segundo de la toma que se ve debajo |
| `fotos_vo` | cada foto con el tramo de narración que la describe y su rótulo |
| `graficos` | rótulos anclados al **segundo de la toma**: `sec`, `dato`, `resumen`, `precio`, `veredicto`, `mini`, `numero`, `clave`, `recap`, `captura`, `clip` |
| `musica_vol` | volumen de la música por parte (`gancho`, `logo`, `cuerpo`, `outro`); en el cuerpo, 0,045 |
| `logo`, `outro`, `musica` | opcionales; si no están, salen de `ZK_LOGO`, `ZK_OUTRO`, `ZK_MUSICA` |

Deja en `10_work/<slug>/final/timeline_<modo>.json` el mapa toma → edición, que usa `subtitulos/subtitulos.py`.
Cada parte se cachea por hash: si se cambia un tramo, solo se rehace esa parte.

## shorts.py: Shorts 9:16

```bash
python render/shorts.py C:/ruta/a/mi_video/12_project/proyecto.json all    # o 1, 2, 3…
```

Lee `"shorts"` del mismo `proyecto.json`. Cada escena es `[TIPO, fuente, desde, hasta, opciones]`:
- `CAM`: la cara (`z` = zoom, `cx` = centro horizontal);
- `BROLL`: el plano del producto (`va` = segundo de la toma que se ve) con la voz de la toma o de una narración; se corta
  solo a los ~3 s para no quedar sin producto;
- `FOTO`: la foto entera sobre fondo desenfocado (`img`, `lab`).

Gancho de texto en los primeros 2,6 s, subtítulos grandes por palabra (las `claves` en serif itálica dorada), título
fijo arriba, firma con `ZK_CANAL`, cierre con la miniatura del video largo y −14 LUFS.

## preview_360p.py: preview rápida desde un edl.json

```bash
python render/preview_360p.py C:/ruta/a/mi_video/12_project/edl.json
```

Formato del `edl.json`:

```json
{
  "slug": "mi_video",
  "fuentes": {"toma1": "C:/ruta/a/mi_video/01_main/toma1.mp4"},
  "clips":   {"trailer": "C:/ruta/a/mi_video/06_material_usuario/trailer.mp4"},
  "edl": [
    {"src": "toma1", "partes": [[12.4, 18.9]], "cam": true},
    {"src": "toma1", "partes": [[20.1, 31.0]], "cam": false, "broll": [["trailer", 40.0], ["CARD", "Falta: captura del precio"]]}
  ]
}
```

`cam: true` es un tramo a cámara (alterna normal y cerca cada ~3 s). Con `cam: false` se ve el B-roll en orden o una
placa con lo que falta conseguir. Usa `10_work/prev/` como temporal y lo vacía al empezar. Arriba a la izquierda va el minuto, para comentar «en 1:23 tal cosa». Verifica que
cada plano tenga los cuadros exactos y que video y audio duren lo mismo.

## Variables de entorno

`ZK_LOGO`, `ZK_OUTRO`, `ZK_MUSICA`, `ZK_FUENTE` (tipografía, por defecto Bahnschrift de Windows), `ZK_CANAL`.
Ver [`config.example.env`](../config.example.env).
