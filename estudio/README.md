# estudio/: editar un video desde los crudos

La página para editar un video nuevo sin tocar código. Se elige la toma de OBS y el estudio hace el resto: voz limpia,
proxy, transcripción y silencios. Después se edita sobre el texto y se renderiza con la cámara según lo que se dice.

```bash
# PowerShell (o cargá el .env con el comando de config.example.env)
$env:ZK_GRABACIONES = "C:/ruta/a/grabaciones_obs"   # solo se lee
$env:ZK_VIDEOS = "C:/ruta/a/videos"                 # acá se crea la carpeta de cada proyecto
python estudio/servidor.py [--puerto 8780]
```

Abrir `http://127.0.0.1:8780/`.

## Flujo

1. **Nuevo video desde los crudos.** Lista las tomas de `ZK_GRABACIONES`: `<fecha hora>.mp4` es el programa y
   `<fecha hora> CAM-<nombre>.mp4` son las ISO de cada cámara. Se elige:
   - la pista del micrófono crudo;
   - el rol de cada cámara: `cara` o `producto`, y el programa queda como `neutro`;
   - qué cámaras hay que dar vuelta (la cenital ISO de OBS viene dada vuelta).

   Los crudos no se copian: el proyecto guarda sus rutas.
2. **Proceso automático**, en orden y con el estado arriba. Si se corta, al reintentar sigue donde quedó.
   - **voz**: cadena C (`audio/voz_cadena_c.py`) → `10_work/audio/voz_c.wav` y `voz16k.wav`;
   - **proxies**: el programa en 640x360 con la voz limpia, para editar en el navegador;
   - **transcripción**: frase por frase (no se pierden las retomas) y con la hora de cada palabra. Usa la GPU si
     está y si no, la CPU (`ZK_WHISPER` cambia el modelo, por defecto `large-v3`);
   - **silencios**: los huecos sin voz, medidos por energía. La primera vez ya quedan cortados los de más de 0,9 s.
3. **Editar.** Todo se guarda como versión: Ctrl+Z vuelve un paso (seguido, cada vez más atrás) y la pestaña Versiones
   vuelve a cualquier punto.

   | Pestaña | Qué hace |
   |---|---|
   | Texto | Clic en una palabra: el video va ahí. Al seleccionar palabras aparecen **Cortar**, **Volver a meter**, **Cámara: cara / producto / neutro / auto** y **Cartel acá**. Lo cortado se ve tachado |
   | Cortes | **Borrar silencios** de más de N segundos; cada corte se puede apagar (los gatos, los ruidos de la caja) |
   | Carteles | El lower third oficial (`graficos/lower_third.py`) en el momento actual del video, con vista previa encima del video |
   | Versiones | Todas las versiones de la edición con su nota |
   | Render | **Preview 360p** o **Final 1080p**, y el informe de ritmo |

   El reproductor en modo «edición» salta los cortes. Abajo está la toma entera: en gris lo cortado, en verde las
   frases, en amarillo los carteles y abajo de color las cámaras forzadas.
4. **Render.** Cada tramo se parte en planos de 1,6 a 3,2 s que arrancan en el inicio de una frase. La cámara sale de
   lo que se dice: al mostrar algo va `producto`, al hablar a cámara va `cara`, y si no hay nada claro alterna.
   Las cámaras forzadas mandan. Son dos encuadres por cámara, nunca dos planos iguales seguidos. Entre frases la voz baja
   8 dB más (sumado a los 10 dB que ya bajó la cadena C en los huecos) y sale a −14 LUFS. Los planos se cachean, así que cambiar un corte solo rehace lo que cambió.
   Salida: `11_exports/previews/<proyecto>_vNNN_360p.mp4` o `11_exports/final/…_1080p.mp4`. El número es la
   versión de la edición.

## Carpeta de cada proyecto

```
<ZK_VIDEOS>/<proyecto>/
  12_project/estudio.json      cámaras, roles y pista de voz
  12_project/edicion.json      la edición actual: cortes, carteles (textos) y cámaras forzadas
  12_project/ediciones/        una copia por versión
  12_project/analysis/         frases.json, silencios.json, voz16k.wav
  10_work/                     proxies, voz, planos cacheados
  11_exports/                  previews y finales
```

Todos los tiempos de `edicion.json` están en **segundos de la toma**: las cámaras de OBS están sincronizadas, así que
un corte vale para todas.

## Lo que todavía no hace

- Logo, outro, música y efectos de sonido. Por ahora se usan los renders de `ejemplos/`.
- B-roll de otros archivos y recuadros (cara chica sobre el producto).
- Detectar retomas solas: `edl/edl_auto.py` lo hace sobre el corte multicámara, pero todavía no está integrado acá.
- Comentarios por versión: para eso sirve el visor (`visor/servidor.py <carpeta del proyecto> --patron "*_360p.mp4"`).
- La vista en vivo muestra solo el programa. El cambio de cámara se ve en el render.

## Seguridad

Escucha solo en `127.0.0.1` y rechaza pedidos con otro `Host` u `Origin`. Los archivos se sirven solo desde la carpeta
de cada proyecto. Las tomas se eligen de la lista de la carpeta de grabaciones: el navegador nunca manda rutas.
