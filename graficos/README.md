# graficos/

Gráficos dibujados con PIL, cuadro a cuadro o como PNG con alfa para ir encima del video.

## gfx.py: motor de escenas

Escenas animadas (fondo carbón con viñeta y grano, tipografía Poppins, años y citas en Georgia itálica, acento ámbar)
que se dibujan cuadro a cuadro sobre un `Canvas(scale)`. Trae `ease`/`ein` para las entradas y funciones `sc_*` para
cada tipo de escena: textos, cifras, líneas de tiempo, grillas de productos, clips y fotos sobre fondo desenfocado.
Varias escenas tienen el contenido de los videos donde se usaron (sirven de ejemplo de cómo armar una nueva).

Necesita las fuentes Poppins (`Poppins-Bold.ttf`, `Poppins-Medium.ttf`) y Georgia (`georgiai.ttf`, `georgiaz.ttf`)
en `ZK_FUENTES_DIR`, y lee material de `ZK_FOTOS`, `ZK_CLIPS` y `ZK_RECORTES` (PNG de productos recortados).

## zk_style.py: el estilo del canal

Se apoya en `gfx.py`. Escenas `sc_zk_*` con la identidad del canal: pizarra azul con rayos e íconos de línea,
Bahnschrift condensada ámbar con borde negro y sombra corrida, etiqueta de precio (tachado + «% OFF»), sello
«FALSO», productos como stickers con borde blanco y capturas con un óvalo rojo hecho a mano. `OVER = True` lo dibuja
sin fondo para ir encima de la cámara. Quien arma las escenas setea `FOTOS` (carpeta de fotos). Usa scipy.

## Carteles: el estilo oficial

**Lo único aprobado para carteles es el lower third**: abajo a la izquierda, caja oscura mate con esquinas apenas
redondeadas, **sin línea ni barra de color**, rótulo chico en mayúsculas arriba y el dato abajo, en **Consolas Bold**.
Lo demás de esta carpeta (paneles con barra de acento, Segoe UI, stickers, rótulos de sección, objetos tipo Fn+F9) se
rechazó porque «se nota hecho por IA»; queda como motor y como referencia, no para carteles nuevos.

- `lower_third.py`: `lower_third(W, H, rotulo, dato)` devuelve la capa RGBA del tamaño del video. La fuente sale de
  `ZK_FUENTE_CARTEL` (por defecto `C:/Windows/Fonts/consolab.ttf`). Corrido solo arma una hoja de muestra sobre dos
  cuadros (`_cara.png` y `_caja.png` al lado del script).
- `carteles.py`: genera todos los carteles de un video (PNG con alfa + MOV qtrle con fundido de 0,15 s) y los suma al
  `catalogo.json` de la carpeta de salida, que es lo que leen los renders.

```bash
cd graficos
python carteles.py ../ejemplos/m999/carteles.json C:/ruta/a/mi_video/10_work/gfx
```

`carteles.json` es una lista de `[id, rótulo, dato, duración_s]`. Los ids empiezan con `lt_`; en el EDL se anclan al
renglón donde se dice el dato (ver `GRAF` en `ejemplos/m999/edl_manual.py`).

Más ejemplos (los gráficos del Fizz Pro, con objetos dibujados y MOV con alfa) en
[`ejemplos/fizz_pro/gfx/`](../ejemplos/README.md).
