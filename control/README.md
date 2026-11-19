# control/

Controles para no subir un video con palabras cortadas, retomas o audio fuera de norma. Todos transcriben **frase por
frase** (cada tramo de voz entre silencios, solo y sin contexto): Whisper sobre el archivo entero se saltea justo los
arranques cortados y las retomas.

## Antes de renderizar

Los tres esperan en la carpeta `12_project` del video:
- `narrado/edl_manual.py` con una lista `KEEP` de tuplas `(etiqueta, desde_s, hasta_s, cámara)` (ver
  [`ejemplos/m999/edl_manual.py`](../ejemplos/m999/edl_manual.py));
- `analysis/voz16k.wav` (lo deja [`audio/voz_cadena_c.py`](../audio/README.md)).

Si usás el `edl_manual.py` del ejemplo, definí `ZK_PROYECTO` (lee la transcripción de ahí). Los tres piden GPU (CUDA).

| Script | Qué marca | Uso |
|---|---|---|
| `bordes_edl.py` | tramos que **terminan** con la voz sonando (propone hasta dónde estirar), que **arrancan** con la voz ya sonando, y tramos que son una toma descartada («vamos de nuevo» justo después). Escribe `analysis/uniones_edl.txt` con cada unión «…final ‖ principio…» para **leerla entera** | `python control/bordes_edl.py <video>/12_project` |
| `chequeo_tramos.py` | transcribe cada tramo frase por frase para ver retomas y frases sin terminar | `python control/chequeo_tramos.py <video>/12_project salida.txt` |
| `chequeo_edl.py` | voz (por energía) sin palabras transcriptas: ahí suele esconderse una retoma que Whisper no oyó. Necesita además `analysis/words.json` (`[[palabra, s, e], …]`): sale aplanando la transcripción de `edl/transcribir*.py` (`[[w["w"].strip(), w["s"], w["e"]] for s in tx for w in s["words"]]`) | `python control/chequeo_edl.py <video>/12_project` |

`bordes_edl.py` sale con código 1 si encuentra bordes para revisar. Nunca estirar un borde sin mirar qué hay en la
fuente: si hay una retoma al lado, se corta en el pozo de silencio real.

## Antes de subir: control_borrador.py

```bash
python control/control_borrador.py C:/ruta/a/mi_video/11_exports/final/mi_video_v003.mp4 [informe.txt]
```

Sobre el **render final**:
1. Frase por frase: muletillas de toma («vamos de nuevo», «vámonos», «repito», conteos, claquetas), arranques
   cortados, frases colgadas (terminan en «…» o en «el», «de», «que»…), palabras sueltas, autocorrecciones dentro de
   una frase y frases repetidas.
2. Técnica: cuadros negros, loudness integrado (−14 ± 1 LUFS) y true peak (≤ −1 dBTP).

Escribe el informe con la transcripción completa y sale con código 1 y **NO SE SUBE** si encuentra algo. Se corrige
el EDL, se renderiza de nuevo y se vuelve a correr hasta que diga **APROBADO**. Ignora los últimos ~6 s (el outro).
