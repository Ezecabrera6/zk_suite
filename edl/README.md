# edl/

De la toma a la lista de tramos que quedan.

## Transcripción

| Script | Para qué | Uso |
|---|---|---|
| `transcribir.py` | toma entera con marcas por palabra, en CPU (int8) | `python edl/transcribir.py toma.mp4 12_project/analysis/transcript_toma.json` |
| `transcribir_gpu.py` | lo mismo en GPU, varias tomas a la vez | `python edl/transcribir_gpu.py SALIDA_DIR toma1.mp4 [toma2.mp4 …]` (pista con `ZK_PISTA`, por defecto 4) |
| `tx_por_pausas.py` | **frase por frase**: cada tramo de voz entre silencios se transcribe solo | `python edl/tx_por_pausas.py toma.mp4 12_project/analysis/tx_pausas_toma.txt [pista]` |

Whisper sobre el archivo entero se saltea arranques cortados y retomas («y el G… vamos de nuevo»). Para elegir tramos
conviene `tx_por_pausas.py`: no se pierde nada.

Formatos de salida:
- JSON de `transcribir*.py`: `[{"start", "end", "text", "words": [{"w", "s", "e"}]}]`, más un `.txt` con un
  renglón por segmento.
- TXT de `tx_por_pausas.py`: un renglón por frase, `m:ss.ss-m:ss.ss texto`. El **número de renglón** es la referencia
  para armar el EDL a mano (ver `ejemplos/m999/edl_manual.py`).

Todos usan `faster-whisper` con el modelo `large-v3` en español.

## edl_auto.py: primer corte automático (multicámara)

```bash
python edl/edl_auto.py C:/ruta/a/mi_video/12_project --cara-hasta 52 [--chau 1250-1296] [--forzar]
```

Lee `analysis/tx_pausas_toma.txt` y escribe `edl_multicam.json`:
- cada frase entra como segmento (las cámaras de OBS están sincronizadas, así que vale el mismo tiempo para todas);
- quedan marcadas como `fuera` (no se borran: el visor las muestra tachadas) las **retomas** (una frase muy parecida
  dicha en los 90 s siguientes), las muletillas sueltas, lo que Whisper inventa sobre ruidos y, con `--chau`, una
  tanda de despedidas;
- une frases seguidas en segmentos de hasta 9 s;
- cámara sugerida: `cara` hasta `--cara-hasta` segundos (el gancho), después alterna `programa` y `cenital`.

No pisa un `edl_multicam.json` existente (tiene las elecciones hechas a mano) salvo con `--forzar`.
El corte se ajusta después en el [visor multicámara](../visor/README.md#multicam-editor-de-corte).

Formato: `{"version", "segmentos": [{"a", "b", "txt", "fuera", "por_que", "cam"}]}`. Un segmento puede llevar `orden`
para moverlo de lugar y `audio: "teclado"` para usar el sonido crudo.

## EDL por renglones (a mano)

Para videos grabados sin guion, el corte se escribe a mano sobre los renglones de `tx_pausas_toma.txt`:
`(renglón_desde, renglón_hasta, opciones)`, con marcadores `"LOGO"`, `"OUTRO"` y `"BLOOPER"`. Las opciones fijan la
cámara (`cam`), el encuadre (`vis`), un recuadro (`pip`) o cuánto silencio dejar (`huecos`). El ejemplo completo,
con su función `piezas()` y la lista `KEEP` que leen los controles, está en
[`ejemplos/m999/edl_manual.py`](../ejemplos/m999/edl_manual.py).
