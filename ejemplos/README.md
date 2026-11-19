# ejemplos/

Renders reales, tal como quedaron en su video, con las rutas pasadas a variables de entorno. Tienen tiempos, frases y
cámaras de **esa** toma: no se corren sobre otro video sin adaptarlos. Sirven como base para copiar.

## m999/: unboxing grabado sin guion, tres cámaras

El más nuevo y el más completo.

- `edl_manual.py`: el corte por **renglones** de `12_project/analysis/tx_pausas_toma.txt`. Cada tramo es
  `(renglón_desde, renglón_hasta, opciones)`; `CAM` fija la cámara por renglón, `SFX` pone efectos sueltos, `AJ_FIN` y
  `AJ_INI` guardan los bordes corregidos con `control/bordes_edl.py`. Expone `piezas()` y `KEEP`.
- `render_m999.py`: el render multicámara.
  - **Cámara según lo que se dice** (`tipo_de`): palabras de mostrar → cenital; palabras de hablar a cámara → cara;
    si no hay nada claro, donde haya movimiento (la actividad de cada cámara se mide una vez y se guarda en `.npy`).
  - **Corte cada ~2,3 s** en el inicio de la frase más cercana (`cortes_de`), con dos encuadres por tipo y nunca dos
    planos iguales seguidos.
  - **Recuadros** (`pip`): la cara chica sobre el producto o al revés; en la escena de pantalla, dos recuadros.
  - **Blooper** de apertura en blanco y negro con un pitido de 1 kHz.
  - **Bajada de respiraciones**: entre frases la voz baja 8 dB con rampas de 30 ms.
  - Gráficos anclados al renglón donde se dice el dato, nunca dos a la vez ni sobre el logo o el outro.
  - Master a −14 LUFS con limitador con sobremuestreo, y `informe.json` con el ritmo (plano promedio, el más largo,
    cortes por minuto).

```bash
set ZK_PROYECTO=C:/ruta/a/mi_video
set ZK_TOMA=C:/ruta/a/grabaciones/2026-11-18 00-35-59
set ZK_ASSETS=C:/ruta/a/assets
python ejemplos/m999/render_m999.py v=v001 --360      # preview para el visor
python ejemplos/m999/render_m999.py v=v001 --plan     # solo el plan, sin renderizar
python ejemplos/m999/render_m999.py v=v010 --final    # 1920x1080
```

`carteles.json` son los carteles del video en el estilo oficial; se generan con `graficos/carteles.py` en
`10_work/gfx/`, que es donde el render los busca (`catalogo.json`).

Espera `ZK_TOMA + ".mp4"` (programa), `" CAM-StreamCam.mp4"` y `" CAM-Cenital.mp4"` (las ISO de OBS),
`10_work/audio/voz_c.wav` y `10_work/gfx/catalogo.json`.

## fizz_pro/: unboxing de teclado, editado en el visor multicámara

- `render.py`: render desde `12_project/edl_multicam.json` (el corte del [visor multicámara](../visor/README.md)):
  planos de ~3 s que alternan cámara y encuadre, B-roll elegido por la palabra que se dice y filtrado por luz y
  nitidez, tramos de ASMR con el sonido crudo, gráficos anclados a una frase, render final por partes de 1 minuto y
  `--plan` para la preview en vivo. Lee `ZK_PROYECTO`, `ZK_ASSETS` y, si hace falta, `ZK_FFMPEG_DIR`.
- `gfx/gen.py`, `gfx/objetos.py`, `gfx/gen_v1_sticker.py`: los gráficos de ese video (PNG con alfa + MOV qtrle con
  entrada y salida animadas). `gen_v1_sticker.py` importa `graficos/gfx.py` y `graficos/zk_style.py` de la suite.
  Salida en `ZK_GFX_OUT` (tiene que existir, con la miniatura del video al que apunta la tarjeta en
  `_ref/miniatura.jpg`).

## proyecto/: proyecto.json de ejemplo

El formato que leen `render/editar.py`, `render/shorts.py` y `subtitulos/subtitulos.py`, con los valores de un
review real de un celular. Explicado en [render/README.md](../render/README.md).
