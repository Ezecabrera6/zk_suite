# audio/

## voz_cadena_c.py: la voz para el render

```bash
python audio/voz_cadena_c.py toma.mp4 5 C:/ruta/a/mi_video/10_work/audio/voz_c.wav C:/ruta/a/mi_video/12_project/analysis
```

| Parámetro | Qué es |
|---|---|
| `toma.mp4` | la toma de OBS |
| `5` | índice de la pista de audio en ffmpeg (0 = la primera). Conviene grabar el micrófono crudo en su propia pista |
| `voz_c.wav` | salida: mono, 48 kHz, 24 bits, sin normalizar |
| carpeta `analysis` | opcional: deja `voz16k.wav`, que usan los controles |

Cadena: `adeclip` → `highpass 80 Hz` → reducción de ruido (`afftdn`) → −3 dB en 300 Hz → compresor 2:1 →
de-esser → +2 dB en 4 kHz → +1,5 dB de aire en 10 kHz. **Sin compuerta**: los ruidos que importan quedan. Los huecos
sin voz bajan 10 dB con rampas suaves; lo que suena fuerte sin voz (una bolsa, clics) pasa el umbral y queda.
El render nivela después a −14 LUFS.

## analisis_audio.py: medir contra el estándar

```bash
python audio/analisis_audio.py informe.png "Toma|toma.wav" "Final|final.mp4"
```

Por archivo: loudness integrado, true peak, LRA, piso de ruido, hasta dónde llega el espectro y el balance por
bandas, con OK o MAL contra los objetivos (−15 a −13 LUFS, ≤ −1 dBTP, LRA 3–9, piso ≤ −55 dBFS, banda ≥ 12 kHz).
Dibuja la forma de onda y el espectrograma de los primeros 30 s (numpy + PIL, sin matplotlib) y deja un `.json`
al lado del `.png`.
