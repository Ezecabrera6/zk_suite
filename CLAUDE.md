# CLAUDE.md: cómo usar zk_suite con Claude Code

Esta suite edita videos de YouTube por código. La persona graba con OBS y vos (Claude) llevás la edición: corrés los
procesos, cortás sobre la transcripción, renderizás previews y aplicás las correcciones que te deja en el visor.
Escribile en el idioma en que te escriba. Las reglas de edición están en español porque la suite nació así.

## Antes de empezar un video

1. Leé `docs/REGLAS.md` (ritmo, cámara según lo que se dice, carteles, audio, privacidad). Es lo que se mide en
   cada preview.
2. Revisá que esté la configuración: `.env` a partir de `config.example.env`. Lo mínimo es `ZK_GRABACIONES` (la
   carpeta de OBS) y `ZK_VIDEOS` (dónde se crean los proyectos). Si falta algo, preguntá la ruta; no la inventes.
3. Requisitos: `ffmpeg` en el PATH y `pip install -r requirements.txt`. El estudio usa la GPU si hay CUDA y si no, la
   CPU; los controles de `control/` y `edl/tx_por_pausas.py` hoy piden CUDA (ver el README raíz para pasarlos a CPU).
   Las variables se cargan en la terminal antes de correr; en PowerShell está el comando en `config.example.env`.

## Camino principal: el estudio

```bash
python estudio/servidor.py          # http://127.0.0.1:8780/
```

- La persona elige la toma y las cámaras en «Nuevo video desde los crudos». El estudio hace voz, proxy,
  transcripción y silencios.
- Las mismas operaciones de la página están en `estudio/motor.py`: `operar(slug, {"op": ...})` con `cortar`,
  `restaurar`, `silencios`, `alternar`, `texto`, `borrar_texto`, `camara` y `deshacer`, y `render(slug, "360"|"1080")`.
  Podés editar desde código con esas funciones: cada cambio queda como versión y la página lo muestra.
- Para decidir cortes, leé `12_project/analysis/frases.json` (frase por frase, con la hora de cada palabra). Se cortan
  las retomas («vamos de nuevo», una frase repetida) y los silencios largos. Lo natural y lo gracioso queda.
- Antes de mostrar una preview, mirá `12_project/ultimo_render.json`: plano promedio de ~2–3 s, ninguno de más de 6 s.
- Comentarios por versión: `python visor/servidor.py <carpeta del proyecto> --patron "*_360p.mp4"`. Los comentarios
  llegan a `12_project/visor_correcciones/`. Leelos, corregí y renderizá la versión siguiente.

## Reglas para vos

- **Los crudos no se tocan**: nunca borres, muevas ni sobrescribas nada de `ZK_GRABACIONES` ni de `01_main/`.
- **El final en 1080p, solo con el OK de la persona.** Las previews van en 360p.
- **Privacidad**: antes del final, revisá cuadros en 1080p donde se pueda leer algo privado (etiquetas de envío,
  pestañas, pantallas). Si aparece, avisá y usá otra cámara en ese tramo.
- **Antes de dar un final por bueno**: `python control/control_borrador.py <final.mp4>` tiene que decir APROBADO.
- Cuando la persona corrija algo de la edición que valga para todos los videos, sumalo a `docs/REGLAS.md` con la fecha.
- Los servidores son solo locales (127.0.0.1). No los expongas a la red.

## Mapa

| Carpeta | Para qué |
|---|---|
| `estudio/` | La página y el motor para editar desde los crudos (empezá por acá) |
| `render/`, `edl/`, `visor/`, `audio/`, `subtitulos/`, `control/`, `graficos/` | Las piezas sueltas, cada una con su README |
| `vedit/` | Editor anterior, de una sola fuente, con timeline y render parcial |
| `ejemplos/` | Renders reales de dos videos, para copiar ideas (están atados a esas tomas) |
