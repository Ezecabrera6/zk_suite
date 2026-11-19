# visor/

Páginas locales para revisar el video en el navegador. Los servidores usan solo la librería estándar de Python,
escuchan en `127.0.0.1`, rechazan pedidos con otro `Host` u `Origin` (una página abierta en el navegador no
puede usarlos) y soportan `Range` (se puede saltar dentro del mp4 sin que vuelva al segundo 0).

## Visor de previews con comentarios

```bash
python visor/servidor.py C:/ruta/a/mi_video [--patron "*_v*_360p.mp4"] [--puerto 8773]
```

Abrir `http://127.0.0.1:8773/visor/`.

Cada render nombra distinto sus previews: pasá el patrón que corresponda.

| Render | `--patron` |
|---|---|
| `ejemplos/m999/render_m999.py --360` | `*_v*_360p.mp4` (el de por defecto) |
| `render/preview_360p.py` | `*_prev_v*.mp4` |
| `render/editar.py preview`, `ejemplos/fizz_pro/render.py` | `*_v*_720p.mp4` |

- Muestra siempre la **última preview** de `11_exports/previews/` que coincide con el patrón, y la lista de las
  anteriores para comparar. Cada 4 s se fija si hay una nueva; si estabas en la última, en pausa y sin un comentario
  a medio escribir, salta sola; si no, avisa arriba.
- Al pausar aparece el campo para comentar **en ese minuto**. Cada comentario queda **atado a la versión** sobre la que
  se hizo: al tocarlo abre esa versión en ese segundo.
- **Enviar a corregir** guarda todo en `12_project/visor_correcciones/<versión>_<fecha>.json` y escribe `ENVIADO …`
  en la consola. Quien edita (o la sesión de Claude que vigila esa carpeta) corrige el EDL y renderiza la versión
  siguiente, que aparece sola en el visor.
- Los comentarios sin enviar se guardan en el navegador por si se recarga la página.

Formato de cada envío:

```json
{"version": "v009", "comentarios": [{"version": "v009", "t": 172.4, "mmss": "2:52", "texto": "mucho rato en lo mismo"}]}
```

## multicam/: editor de corte

```bash
python visor/multicam/servidor.py C:/ruta/a/mi_video [--render ejemplos/fizz_pro/render.py] [--puerto 8771]
```

- `http://127.0.0.1:8771/visor/`: las 3 cámaras (cenital, cara, programa) arriba y la salida abajo, sobre
  `12_project/edl_multicam.json` (ver [edl/edl_auto.py](../edl/README.md#edl_autopy-primer-corte-automático-multicámara)).
  Teclas: `1` `2` `3` eligen la cámara del segmento, `X` lo saca o lo vuelve a meter, `M` cambia entre ver el corte
  y ver todo, flechas para ir de segmento en segmento, `,` `.` cuadro por cuadro y espacio para reproducir.
  Guarda solo y deja una copia en `12_project/analysis/edl_copias/` antes de pisar.
  Espera los proxies en `10_work/proxies/{cenital,cara,programa}.mp4`.
- `…/visor/preview.html`: **preview en vivo** sin renderizar. El botón Actualizar corre el render con `--plan`, que
  escribe `12_project/visor/plan.json` (planos, audio, efectos y gráficos), y el navegador lo reproduce a ×1–×4.
- `…/visor/partes.html?v=v003&slug=fizzpro`: la preview por partes de 1 minuto de `ejemplos/fizz_pro/render.py`
  (sin `--final`), para ir viéndolas mientras salen.
- `…/visor/progreso.html?v=v003`: los planos a medida que el render los termina (sin audio).

El render que se pasa en `--render` tiene que aceptar `v=… --plan` y leer la carpeta del video de `ZK_PROYECTO`, como
[`ejemplos/fizz_pro/render.py`](../ejemplos/fizz_pro/render.py).
