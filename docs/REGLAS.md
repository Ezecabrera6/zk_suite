# Reglas de edición

Lo que tiene que cumplir cada video, Short o Reel antes de mostrarse. Salen de la referencia de edición elegida para
el canal (el ritmo del canal YANPOL) y de las correcciones hechas sobre cada video. Si una regla choca con lo que pide
quien dirige el video, manda esa persona y se corrige este archivo con la fecha.

## Ritmo (YANPOL)

| Qué | Meta |
|---|---|
| Cambio de plano | cada **2,5 a 3,5 s** en promedio; con dos o más cámaras, **cada ~2 s** (no más de 2 s sin un cambio de cámara) |
| Plano más largo | **6 s** como tope normal, **8 s** como máximo absoluto |
| Cortes por minuto | **12 o más en todos los minutos**, sin pozos |
| Loudness | **−14 LUFS** integrado, true peak **≤ −1 dBTP** |

Antes de mostrar una preview se mide: los renders de `ejemplos/` escriben `informe.json` con el plano promedio, el más
largo, los planos de más de 6 s y los cortes por minuto. Sobre cualquier video se puede medir con ffmpeg
(`select=gt(scene\,0.08),showinfo`). Si no da, no se muestra.

## Cámara según lo que se dice

La cámara no se alterna a ciegas cada 3 s. Cada plano se decide por **lo que se dice** y por **dónde pasa algo**:

- **producto** (cenital cerca) cuando muestra algo («miren», «acá», «tiene», la caja, un botón) o las manos trabajan;
- **cara** cuando habla a cámara: chistes, «suscribite», reacciones, opiniones, o pasa algo en esa cámara;
- **neutro** (programa: producto grande con la cara en un recuadro) cuando no hay nada claro.

Dentro de cada tipo se alternan dos encuadres (normal y apretado), así hay corte cada ~2–3 s sin saltar de idea.
Nunca dos planos iguales seguidos. Los cortes caen al **inicio de una frase** cuando se puede.
En los chistes va la cara, aunque el producto esté en un recuadro. Implementado en `ejemplos/m999/render_m999.py`.

## Imagen

1. **El producto en pantalla casi todo el tiempo.** Ningún dato se dice sin mostrar el objeto. B-roll filmado (caja,
   apertura, manos, detalles, uso real) antes que fotos recortadas.
2. **Los datos se muestran como objetos, no como frases.** El producto grande y la cifra que se arma al lado.
   En pantalla, 4 palabras como máximo.
3. **Una placa nunca dura más de 6 s ni se repite.** Si la idea vuelve, otra imagen u otro encuadre.
4. **Dos gráficos nunca a la vez**, y ninguno encima del logo ni del outro.
5. **Carteles: solo el lower third aprobado** (18/11/2026): abajo a la izquierda, caja oscura mate, sin línea de color,
   rótulo chico en mayúsculas y el dato abajo, en Consolas Bold (`graficos/carteles.py`). Entra cuando se dice el dato,
   no antes. Paneles con barra de acento, Segoe UI, stickers, rótulos de sección y objetos animados tipo «Fn+F9» quedan
   afuera: «se notan hechos por IA».
5. **Prueba real**: un tramo usando el producto, con «tiempo real» si corresponde.
6. B-roll de menos de 2 s no va: se cuela y no pega. Fotos oscuras o fuera de foco tampoco (los renders las filtran
   por luz media y nitidez).

## Corte

- Se cortan **solo** las retomas reales y los silencios largos. Lo natural y lo gracioso queda (una mascota que
  aparece, un chiste, un ruido de la caja): el video tiene que ser divertido y humano.
- «Vamos de nuevo», «empiezo de nuevo» y similares marcan una retoma: lo de antes del marcador se descarta.
- Un tramo termina en silencio y arranca en silencio. Whisper adelanta los finales 0,3–0,5 s: hay que estirar hasta
  que la voz termine (lo marca `control/bordes_edl.py`).
- Cada unión «…final ‖ principio…» se lee entera antes de renderizar: la frase tiene que tener sentido.
- Los huecos entre frases se acortan a ~0,9 s, salvo cuando pasa algo en cuadro sin hablar.

## Gancho

El producto en la caja o en la mano en el primer segundo y la persona hablando con el producto en cuadro. Nada de
«¿Qué onda gente?». Un sponsor o un link puede entrar a los 15 s.

## Audio

- Voz con la cadena C (`audio/voz_cadena_c.py`): EQ, compresor suave y de-esser, **sin compuerta**.
- Entre frases la voz baja 8–10 dB para que no se escuchen las respiraciones.
- Nada de música genérica ni generada. Efectos de sonido de bancos con licencia, uno por gráfico, 14 dB por debajo
  de la voz.
- Master: −14 LUFS integrado y limitador con sobremuestreo (el AAC sube los picos; sin esto el final daba −0,5 dBTP).

## Privacidad

Antes de exportar, revisar en 1080p todo lo que se lee en cuadro: etiquetas de envío (nombre, código postal, número
de envío), pestañas del navegador, barra de tareas, teleprompter. Mientras algo así está en cuadro, va otra cámara o la
imagen en un recuadro chico.

## Lo que se pide para la grabación

- Cámara (no webcam) para la cara, una cenital para el producto y el micrófono crudo en su propia pista de OBS.
- Sin auriculares puestos, el producto en la mesa y una luz de color atrás.
- **De 10 a 15 tomas de B-roll** del producto, de 3 a 5 s cada una: caja, apertura, manos, puertos, uso real.
