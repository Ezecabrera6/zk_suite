"""Render del Fizz Pro desde el corte del visor (edl_multicam.json) + B-roll + gráficos + audio preparados.
Ritmo YANPOL (docs/REGLAS.md): cada tramo se parte en planos de ~3 s que alternan cámara,
encuadre y B-roll que coincide con lo que se dice. Sin música (docs/REGLAS.md: nada de música genérica).
uso: python render.py [v=v001] [--final]      (preview 1280x720; --final 1920x1080 solo con el OK de quien dirige el video)
"""
import json, math, os, pathlib, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
import numpy as np

FFD = pathlib.Path(os.environ["ZK_FFMPEG_DIR"]) if os.environ.get("ZK_FFMPEG_DIR") else None
FF, FP = (str(FFD / "ffmpeg"), str(FFD / "ffprobe")) if FFD else ("ffmpeg", "ffprobe")
R = pathlib.Path(os.environ.get("ZK_PROYECTO", "."))                 # carpeta del video (01_main, 10_work, 11_exports, 12_project)
VER = next((a[2:] for a in sys.argv if a.startswith("v=")), "v001")
FINAL = "--final" in sys.argv
W, H = (1920, 1080) if FINAL else (1280, 720)
FPS, SR = 30, 48000
WORK = R / "10_work" / f"render_{VER}"; SHOTS = WORK / "shots"; SHOTS.mkdir(parents=True, exist_ok=True)
OUT = R / "11_exports" / ("final" if FINAL else "previews") / f"fizzpro_{VER}_{H}p.mp4"
ASSETS = pathlib.Path(os.environ.get("ZK_ASSETS", "assets"))         # logo_intro_3s.mp4 y outro.mp4
SRC = {"programa": R / "01_main/toma_programa.mp4", "cara": R / "01_main/toma_cara.mp4", "cenital": R / "01_main/toma_cenital_cruda.mp4"}
TECLADO_PRUEBA = (1403.0, 1411.0)       # 8 s de tipeo limpio sin voz (informe de audio)
TIPEO_BAJO_VOZ = (1427.0, 1540.0)       # prueba de tipeo hablando: la pista 6 va debajo de la voz

def run(a): subprocess.run(a, check=True, capture_output=True)
def probe(f):
    d = json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(f)], capture_output=True, text=True).stdout)
    return float(d["format"]["duration"]), any(s["codec_type"] == "audio" for s in d["streams"])
def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()); return re.sub(r"[^a-z0-9% ]", "", "".join(c for c in s if not unicodedata.combining(c)))
def lee_wav(f, desde=0.0, dur=None):
    a = [FF, "-v", "error", "-ss", f"{desde:.3f}", "-i", str(f)] + (["-t", f"{dur:.3f}"] if dur else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, np.float32).copy()

# ---------- materiales
EDL = [s for s in json.load(open(R / "12_project/edl_multicam.json", encoding="utf-8"))["segmentos"] if not s.get("fuera")]
if any(s["a"] > 1380 for s in EDL):   # la muestra de tipeo solo si esa parte de la toma sigue en el corte (10/11: se cortó)
    EDL.append({"a": TECLADO_PRUEBA[0], "b": TECLADO_PRUEBA[1], "cam": "programa", "txt": "[prueba de sonido: tipeo]", "audio": "teclado"})
# pedido 10/11: «cuando digo les voy a hacer ASMR tenés que dejar eso, porque estoy haciendo ruidos». Esos tramos van
# enteros (con los silencios) y con el sonido crudo de la pista 6, sin el filtro de la voz que se come los ruidos.
ASMR = [(144.6, 152.4, "esto puede ser un poquito ASMR (rompe la caja)"), (235.6, 247.0, "les voy a hacer un toque de ASMR (burbujas)"),
        (320.7, 328.0, "a ver si pueden escuchar un poco")]
for a, b, txt in ASMR:
    pisados = [s for s in EDL if not (s["b"] <= a or s["a"] >= b)]
    cam = pisados[0]["cam"] if pisados else "programa"          # respeta la cámara elegida a mano en el visor
    EDL = [s for s in EDL if s["b"] <= a or s["a"] >= b]
    EDL.append({"a": a, "b": b, "cam": cam, "txt": txt, "audio": "teclado"})
EDL.sort(key=lambda s: s.get("orden", s["a"]))   # «orden» mueve un tramo: el final con el golpe va después de la prueba de doblarlo
BR = json.load(open(R / "10_work/broll/catalogo.json", encoding="utf-8")); BR = BR if isinstance(BR, list) else BR["clips"]
# pedido 10/11: «las fotos que pusiste se ven de mala calidad o con falta de luz, cuando es así no las pongas».
# Filtro: luz media del cuadro ≥ 60 (0–255) y nitidez (varianza del laplaciano a 640 px) ≥ 300; nada de WhatsApp ni fondos desenfocados.
def apto(c):
    if re.search(r"_wa\b|_wa\.|blur", c["archivo"]): return False
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{c['dur'] / 2:.2f}", "-i", str(R / "10_work/broll" / c["archivo"]), "-frames:v", "1",
                          "-vf", "scale=640:360,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    y = np.frombuffer(raw, np.uint8).reshape(360, 640).astype(np.float32)
    lap = (4 * y[1:-1, 1:-1] - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]).var()
    c["luz"], c["nitidez"] = round(float(y.mean()), 1), round(float(lap), 1)
    return c["luz"] >= 60 and c["nitidez"] >= 300
BR_DESCARTADOS = [c["archivo"] for c in BR if not apto(c)]
BR = [c for c in BR if c["archivo"] not in BR_DESCARTADOS]
_gx = json.load(open(R / "10_work/gfx/catalogo.json", encoding="utf-8"))
GX = {g["id"]: g for g in (_gx["graficos"] if isinstance(_gx, dict) else _gx)}
# Recuadros de referencia (pedido 10/11): imágenes de lo que nombra y no está en cuadro, arriba a la derecha.
# Vienen como PNG a pantalla completa con alfa, así entran igual que un gráfico.
_ins_f = R / "10_work/insertos/catalogo.json"
INSERTOS = json.load(open(_ins_f, encoding="utf-8")) if _ins_f.exists() else []
INSERTOS = INSERTOS if isinstance(INSERTOS, list) else INSERTOS.get("insertos", [])
for i_ in INSERTOS:
    GX[i_["id"]] = {"id": i_["id"], "archivo": "../insertos/" + i_["archivo"], "dur_sugerida": i_.get("dur_sugerida", 3.5), "sfx": []}
TEMAS = [  # palabra que se dice en ESE plano → etiqueta de B-roll (pedido 10/11: «los B-roll del 0 al 2 no están enganchados»)
    (r"caja|golpead|cinta|abrir|abrirlo|romp|etiqueta", "caja"), (r"barra|espacio|espaciadora", "barra_roja"), (r"escape|\besc\b", "esc_rojo"),
    (r"dragon", "dragon"), (r"\bluz\b|luces|colores|ilumin|rgb|oscur", "luces"), (r"chiquit|tamano|control de tele|mis manos", "tamano")]
# Continuidad: lo que muestra el B-roll del celu (sacado DESPUÉS de grabar) no puede aparecer antes de que pase en la toma.
SACA_TECLADO, PONE_ROJAS, PRENDE_LUCES = 253.8, 621.2, 678.5     # «ahí está el teclado» · «re clean salió» · «está haciendo luces»
def permitido(c, t_toma):
    e = set(c["etiquetas"])
    if t_toma < SACA_TECLADO: return e <= {"caja", "frente", "rgb", "logo", "switch_red", "3_modos", "dragon", "manos", "mano", "tamano", "qr", "specs"} and "caja" in e
    if t_toma < PONE_ROJAS and e & {"barra_roja", "esc_rojo"}: return False
    if t_toma < PRENDE_LUCES and "luces" in e: return False
    return True
# pedido 10/11: «el B-roll debe ir cuando no estoy haciendo nada con el teclado, o cuando digo veredicto, o hablo mucho
# sin hacer nada en el teclado». Mientras usa el teclado (manos moviéndose en la cenital o tipeo) va la cámara.
ACT = np.load(R / "12_project/analysis/actividad_cenital.npy")          # movimiento de la cenital cada 0,2 s, suavizado a 1 s
_au = json.load(open(R / "10_work/audio/analisis.json", encoding="utf-8"))
TIPEO = [(x["desde"], x["hasta"]) for x in _au.get("teclado", [])] + [(1427.0, 1540.0), (1575.0, 1611.0)]   # sin voz + pruebas hablando
VEREDICTO = (1190.5, 1251.5)
def usando_teclado(a, b):
    if any(a < h and b > d for d, h in TIPEO): return True
    # pedido 10/11: «no lo pongas en momentos de menos de 1 s de no movimiento». Quieto TODO el plano, con medio segundo
    # de margen antes y después: alcanza un pico de movimiento para que vaya la cámara (antes se miraba el promedio).
    seg = ACT[max(0, int((a - 0.5) * 5)): max(int(a * 5) + 1, int((b + 0.5) * 5))]
    return float(seg.max()) > 5.5                                    # hablar quieto da 3,5–4,5; manipular, 6–12
uso_br = {c["archivo"]: 0 for c in BR}; ult_br = None
BROLL_PANTALLA_COMPLETA = False   # pedido 10/11: «mejor sacá el B-roll completo, o poné imágenes en partes libres de la
                                   # pantalla cuando hablo de algo que se pueda identificar» → van como recuadros (INSERTOS)
def broll_para(txt, frames, t_toma, generico=False):
    global ult_br
    if not BROLL_PANTALLA_COMPLETA: return None
    if frames < 2.0 * FPS: return None   # pedido 10/11, 2:50: un B-roll de 1 s «se cuela» y no pega; mínimo 2 s
    t = norm(txt); tags = [tag for pat, tag in TEMAS if re.search(pat, t)]
    if not tags:
        if not generico: return None     # sin palabra que lo ancle, solo en charla larga o en el veredicto
        tags = ["caja"] if t_toma < SACA_TECLADO else ["teclado", "caja"]
    cand = [c for c in BR if c["dur"] * FPS >= frames and c["archivo"] != ult_br and uso_br[c["archivo"]] < 1
            and set(c["etiquetas"]) & set(tags) and permitido(c, t_toma)]
    if not cand: return None
    c = sorted(cand, key=lambda c: (uso_br[c["archivo"]], -c.get("calidad", 2)))[0]
    uso_br[c["archivo"]] += 1; ult_br = c["archivo"]; return c

VF = {  # encuadres (la cenital cruda viene dada vuelta: el plugin graba la fuente sin la rotación de la escena)
    "programa": f"scale={W}:{H}", "cara": f"scale={W}:{H}", "broll": f"scale={W}:{H}",
    "cara_apretado": f"crop=1440:810:240:40,scale={W}:{H}",
    "cenital": f"hflip,vflip,scale={int(W*1.2)}:{int(H*1.2)},crop={W}:{H}",
    "cenital_zoom": f"hflip,vflip,scale={int(W*1.5)}:{int(H*1.5)},crop={W}:{H}:{int(W*0.25)}:{int(H*0.2)}"}
ALT = {"programa": "cenital_zoom", "cenital": "programa", "cara": "cara_apretado"}

# ---------- línea de tiempo (en cuadros) + audio
piezas, audio, anclas = [], [], []      # piezas de video; audio: (salida_s, fuente, desde, dur, gan); anclas: (salida_s, texto)
t = 0; g = 0; logo_puesto = False
logo_d, logo_a = probe(ASSETS / "logo_intro_3s.mp4")
for k, s in enumerate(EDL):
    F = max(1, round((s["b"] - s["a"]) * FPS)); t0 = t
    src_audio = "teclado" if s.get("audio") == "teclado" else "voz"
    audio.append((t / FPS, src_audio, s["a"], F / FPS, 1.0))
    # (sacado 10/11) la pista 6 debajo de la voz duplicaba la voz: esa pista también tiene la voz cruda. Pedido: «fijate que
    # no se duplique el audio». La pista 6 va sola, en lugar de la voz, solo en tramos sin voz o de ASMR.
    anclas.append((t / FPS, s["txt"], s))
    n = max(1, round(F / 90)); cortes = [round(F * j / n) for j in range(n + 1)]
    tipeo = s.get("audio") == "teclado" or (s["b"] > TIPEO_BAJO_VOZ[0] and s["a"] < TIPEO_BAJO_VOZ[1])
    for j in range(n):
        fr = cortes[j + 1] - cortes[j]; off = cortes[j] / FPS
        base = s["cam"]; vis = base if j % 2 == 0 else ALT[base]
        t_toma = s["a"] + off
        quieto = not usando_teclado(t_toma, t_toma + fr / FPS) or VEREDICTO[0] <= t_toma < VEREDICTO[1]
        if s["a"] >= 52 and not tipeo and quieto and g % 2 == 1:
            L = len(s["txt"]); ventana = s["txt"][int(L * cortes[j] / F): int(L * cortes[j + 1] / F) + 1]   # lo que se dice en este plano
            generico = (s["b"] - s["a"]) >= 6.0 or VEREDICTO[0] <= t_toma < VEREDICTO[1]   # «hablo mucho sin hacer nada» o veredicto
            c = broll_para(ventana, fr, t_toma, generico)
            if c: piezas.append({"tipo": "broll", "src": str(R / "10_work/broll" / c["archivo"]), "ss": 0.0, "fr": fr, "vf": VF["broll"], "info": c["archivo"]}); g += 1; continue
        cam_src = "cenital" if vis.startswith("cenital") else "cara" if vis.startswith("cara") else "programa"
        piezas.append({"tipo": vis, "src": str(SRC[cam_src]), "ss": s["a"] + off, "fr": fr, "vf": VF[vis], "info": f"{s['a'] + off:.1f}"})
        g += 1
    t += F
    if not logo_puesto and s["b"] <= 16.5 and (k + 1 < len(EDL) and EDL[k + 1]["a"] > 16.5):   # gancho → logo 3 s
        lf = round(logo_d * FPS); piezas.append({"tipo": "logo", "src": str(ASSETS / "logo_intro_3s.mp4"), "ss": 0.0, "fr": lf, "vf": f"scale={W}:{H}", "info": "logo"})
        if logo_a: audio.append((t / FPS, str(ASSETS / "logo_intro_3s.mp4"), 0.0, lf / FPS, 1.0))
        t += lf; logo_puesto = True
out_d, out_a = probe(ASSETS / "outro.mp4"); of = round(out_d * FPS)
piezas.append({"tipo": "outro", "src": str(ASSETS / "outro.mp4"), "ss": 0.0, "fr": of, "vf": f"scale={W}:{H}", "info": "outro"})
if out_a: audio.append((t / FPS, str(ASSETS / "outro.mp4"), 0.0, of / FPS, 1.0))
t += of; TOTAL = t / FPS

# ---------- gráficos anclados a lo que se dice (primera vez que aparece la frase en el corte)
GRAF = [("g05_precio", "60000"), ("g06_no_es_publicidad", "lo compre yo para mi"), ("g09_seccion_1_unboxing", "vamos a abrirlo"),
        ("g03_modos", "modo 24"), ("g09_seccion_2_accesorios", "que mas trajo"), ("g02_switch_red", "no queria los azules"),
        ("g09_seccion_3_luces", "haciendo luces"), ("g01_60_por_ciento", "teclado 60"), ("g04_fn_f9", "cambia la iluminacion"),
        ("g11_idea_kvm", "a un switch"), ("g09_seccion_4_conexiones", "bluetooth 1"), ("g09_seccion_5_prueba_de_sonido", "prueba de sonido tipeo"),
        ("g08_tiempo_real", "probar la escritura"), ("g09_seccion_6_lo_malo", "negativas"), ("g07_lo_malo", "flechitas que eso"),
        ("g10_tarjeta_cybermonday", "cyber monday"), ("g09_seccion_7_veredicto", "mi veredicto"),
        ("g12_like_suscribite", "denme like"), ("g13_vamos_por_3000", "a nada de los 3000")]   # pedido 10/11: faltaban en el CTA
GRAF += [(i_["id"], i_["frase"]) for i_ in INSERTOS]
pegados, faltan = [], []
def donde(frase):   # segundo de salida donde se dice la frase: inicio del tramo + su posición dentro del texto
    for ts, txt, s in anclas:
        n = norm(txt); i = n.find(frase)
        if i >= 0: return ts + (s["b"] - s["a"]) * i / max(1, len(n))
    return None
for gid, frase in GRAF:
    hit = donde(frase)
    if hit is None or gid not in GX: faltan.append((gid, frase)); continue
    gx = GX[gid]; dur = min(float(gx.get("dur_sugerida", 4)), 6.0) if gid != "g08_tiempo_real" else 6.0
    pegados.append((gid, hit + 0.25, dur, gx))

# ---------- 0) --plan: solo el plan para la preview en vivo del navegador (como un editor: se ve antes, se exporta al final)
if "--plan" in sys.argv:
    URL_CAM = {"programa": "programa", "cara": "cara", "cara_apretado": "cara", "cenital": "cenital", "cenital_zoom": "cenital"}
    ESTILO = {"cenital": [1.2, 50, 50], "cenital_zoom": [1.5, 50, 40], "cara_apretado": [1.3333, 50, 14.8]}  # escala y origen (%) = mismo encuadre que VF
    out, s0 = [], 0
    for p in piezas:
        if p["tipo"] in URL_CAM: url = f"/10_work/proxies/{URL_CAM[p['tipo']]}.mp4"
        elif p["tipo"] == "broll": url = f"/10_work/broll/{p['info']}"
        else: url = f"/10_work/proxies/{p['tipo']}.mp4"                     # logo / outro (copiados ahí)
        out.append({"t": round(s0 / FPS, 3), "d": round(p["fr"] / FPS, 3), "url": url, "ss": round(p["ss"], 3),
                    "tipo": p["tipo"], "esc": ESTILO.get(p["tipo"])}); s0 += p["fr"]
    voz = lee_wav(R / "10_work/audio/voz_c.wav"); vdb = 20 * np.log10(np.sqrt(np.mean(voz[np.abs(voz) > 1e-4] ** 2)) + 1e-9)
    gan_total = 10 ** ((-14 - (-28.3)) / 20)          # la voz de la toma da −28,3 LUFS; el limitador del navegador cuida los picos
    sfx = []
    for gid, en, dur, gx in pegados:
        for s in (gx.get("sfx") or [])[:1]:
            x = lee_wav(R / "10_work/gfx" / s["archivo"]); e = np.sqrt(np.convolve(x ** 2, np.ones(4800) / 4800, "valid"))
            sdb = 20 * np.log10(np.percentile(e, 98) + 1e-9) if len(e) else -40
            sfx.append({"t": round(max(0, en + float(s.get("t", 0))), 3), "url": f"/10_work/gfx/{s['archivo']}", "gan": round(float(10 ** ((vdb - 14 - sdb) / 20)), 4)})
    aud = []
    for en, fuente, desde, dur, gan in audio:
        url = {"voz": "/10_work/audio/voz_c.wav", "teclado": "/10_work/audio/teclado_crudo.wav"}.get(fuente)
        if url: aud.append({"t": round(en, 3), "d": round(dur, 3), "url": url, "desde": round(desde, 3), "gan": gan})
    plan = {"version": VER, "duracion": round(TOTAL, 3), "piezas": out, "audio": aud, "sfx": sfx, "gan_total": round(gan_total, 3),
            "graficos": [{"id": gid, "t": round(en, 3), "d": round(dur, 3), "png": f"/10_work/gfx/{gx['archivo'].replace('.mov', '.png')}"} for gid, en, dur, gx in pegados],
            "faltan": faltan, "broll_descartados": BR_DESCARTADOS}
    (R / "12_project/visor").mkdir(parents=True, exist_ok=True)
    (R / "12_project/visor/plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"plan": "ok", "duracion": plan["duracion"], "piezas": len(out), "graficos": len(pegados), "broll": sum(p["tipo"] == "broll" for p in out)}))
    sys.exit(0)

# ---------- 1) planos de video
def hace(i_p):
    i, p = i_p; f = SHOTS / f"{i:04d}.mp4"
    if f.exists() and f.stat().st_size > 1000: return
    run([FF, "-v", "error", "-y", "-ss", f"{p['ss']:.3f}", "-i", p["src"], "-frames:v", str(p["fr"]), "-an",
         "-vf", p["vf"] + f",fps={FPS},format=yuv420p", "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "21" if FINAL else "24",
         "-g", "60", "-r", str(FPS), str(f)])
with ThreadPoolExecutor(4) as ex: list(ex.map(hace, enumerate(piezas)))
(WORK / "lista.txt").write_text("".join(f"file '{(SHOTS / f'{i:04d}.mp4').as_posix()}'\n" for i in range(len(piezas))), encoding="utf-8")
base = WORK / "base.mp4"
run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "lista.txt"), "-c", "copy", str(base)])

# ---------- 2) audio: voz + teclado + logo/outro + efectos, después −14 LUFS
mix = np.zeros(int(TOTAL * SR) + SR, np.float32)
VOZ, TEC = R / "10_work/audio/voz_c.wav", R / "10_work/audio/teclado_crudo.wav"
def pone(x, en, gan=1.0, fade=0.008):
    n = int(fade * SR)
    if len(x) > 2 * n: x[:n] *= np.linspace(0, 1, n); x[-n:] *= np.linspace(1, 0, n)
    i = int(round(en * SR)); j = min(len(mix), i + len(x)); mix[i:j] += gan * x[: j - i]
for en, fuente, desde, dur, gan in audio:
    f = VOZ if fuente == "voz" else TEC if fuente == "teclado" else pathlib.Path(fuente)
    pone(lee_wav(f, desde, dur), en, gan)
# Efectos: pedido 10/11 «los ruidos cuando aparecen estas cosas son muy fuertes». Uno solo por gráfico y nivelado
# 14 dB por debajo de la voz (medido por energía de los 100 ms más fuertes de cada efecto contra la voz hablada).
def rms_db(x, win):
    if len(x) < win: return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    # media móvil por sumas acumuladas: O(n). Con np.convolve sobre 14 min de voz eran ~10^11 operaciones (10/11: el render se colgó)
    c = np.concatenate(([0.0], np.cumsum(x.astype(np.float64) ** 2)))
    e = np.sqrt(np.maximum(0, (c[win:] - c[:-win]) / win)); return 20 * np.log10(np.percentile(e, 98) + 1e-9)
voz_db = rms_db(mix[np.abs(mix) > 1e-4], int(0.4 * SR))
for gid, en, dur, gx in pegados:
    for s in (gx.get("sfx") or [])[:1]:
        x = lee_wav(R / "10_work/gfx" / s["archivo"])
        gan = 10 ** ((voz_db - 14 - rms_db(x, int(0.1 * SR))) / 20)
        pone(x, max(0, en + float(s.get("t", 0))), gan, fade=0.002)
crudo = WORK / "mezcla_cruda.wav"
subprocess.run([FF, "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(crudo)], input=mix.tobytes(), check=True)
m = subprocess.run([FF, "-hide_banner", "-i", str(crudo), "-af", "loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
j = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
mezcla = WORK / "mezcla.wav"
run([FF, "-v", "error", "-y", "-i", str(crudo), "-af",
     f"loudnorm=I=-14:TP=-1.5:LRA=8:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
     "-ar", str(SR), str(mezcla)])
# loudnorm «lineal» no sube si el pico no le da margen (v001 quedó en −15,8): se completa con ganancia + limitador a −1,5 dB
def integ(f):
    r = subprocess.run([FF, "-hide_banner", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", r[r.rfind("Summary:"):]).group(1))
falta_db = -14.0 - integ(mezcla)
if abs(falta_db) > 0.4:
    tmp = WORK / "mezcla_lim.wav"
    run([FF, "-v", "error", "-y", "-i", str(mezcla), "-af", f"volume={falta_db + 0.3:.2f}dB,alimiter=limit=0.84:attack=3:release=60:level=false", "-ar", str(SR), str(tmp)])
    tmp.replace(mezcla)
LUFS_FINAL = integ(mezcla)

# ---------- 3) gráficos encima + audio, ESCALONADO: partes de 1 minuto terminadas (con audio y gráficos) que se pueden
# ir viendo mientras salen las siguientes (pedido 10/11: «la versión final escalonada así voy viendo qué va y qué no»).
PARTE_S = 60.0
PARTES = OUT.parent / f"fizzpro_{VER}_partes"; PARTES.mkdir(parents=True, exist_ok=True)
n_partes = math.ceil(TOTAL / PARTE_S)
(PARTES / "partes.json").write_text(json.dumps({"version": VER, "total": n_partes, "duracion_s": round(TOTAL, 1)}), encoding="utf-8")
def hace_parte(k):   # pedido 10/11: «prioridad en procesar el video, poné al máximo la PC» → 3 partes en paralelo
    t0 = k * PARTE_S; d = min(PARTE_S, TOTAL - t0); f = PARTES / f"parte_{k + 1:02d}.mp4"
    ins, fc, last = [FF, "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{d:.3f}", "-i", str(base),
                     "-ss", f"{t0:.3f}", "-t", f"{d:.3f}", "-i", str(mezcla)], [], "[0:v]"
    m = 0
    for gid, en, dur, gx in pegados:
        if en + dur <= t0 or en >= t0 + d: continue
        src_g = str(R / "10_work/gfx" / gx["archivo"])
        lp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}"] if src_g.endswith(".png") else []   # imagen fija: se repite
        if en >= t0: ins += lp + ["-itsoffset", f"{en - t0:.3f}", "-i", src_g]          # empieza dentro de esta parte
        else: ins += lp + ["-ss", f"{t0 - en:.3f}", "-i", src_g]                        # venía de la parte anterior
        a_, b_ = max(0.0, en - t0), en + dur - t0
        fc.append(f"[{m + 2}:v]scale={W}:{H},format=rgba[g{m}]")
        fc.append(f"{last}[g{m}]overlay=0:0:eof_action=pass:enable='between(t,{a_:.3f},{b_:.3f})'[v{m}]"); last = f"[v{m}]"; m += 1
    run(ins + (["-filter_complex", ";".join(fc), "-map", last] if fc else ["-map", "0:v"]) + ["-map", "1:a",
        "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "20" if FINAL else "23", "-g", "60", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(f)])
    print(f"parte {k + 1}/{n_partes} lista", flush=True)
with ThreadPoolExecutor(3) as ex: list(ex.map(hace_parte, range(n_partes)))
# el archivo completo: video de las partes pegado sin recodificar + la mezcla entera (así no quedan cortes de audio entre partes)
(PARTES / "lista.txt").write_text("".join(f"file '{(PARTES / f'parte_{k + 1:02d}.mp4').as_posix()}'\n" for k in range(n_partes)), encoding="utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(PARTES / "lista.txt"), "-i", str(mezcla), "-map", "0:v", "-map", "1:a",
     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(OUT)])

# ---------- informe del ritmo (lo pide REGLAS_DE_EDICION.md antes de mostrar)
dur_p = [p["fr"] / FPS for p in piezas]
cuerpo = [d for p, d in zip(piezas, dur_p) if p["tipo"] not in ("logo", "outro")]
inicio = np.cumsum([0] + dur_p[:-1]); por_min = {}
for p, s0 in zip(piezas, inicio): por_min[int(s0 // 60)] = por_min.get(int(s0 // 60), 0) + 1
rep = {"version": VER, "salida": str(OUT), "duracion_s": round(TOTAL, 1), "planos": len(piezas),
       "plano_promedio_s": round(float(np.mean(cuerpo)), 2), "plano_mas_largo_s": round(max(cuerpo), 2),
       "planos_de_mas_de_6s": sum(d > 6 for d in cuerpo), "cortes_por_minuto": por_min,
       "broll_usados": {k: v for k, v in uso_br.items() if v}, "graficos": [(gid, round(en, 1)) for gid, en, _, _ in pegados],
       "graficos_sin_ancla": faltan, "loudness_medido_antes": j["input_i"], "lufs_final": LUFS_FINAL,
       "broll_descartados_por_calidad": BR_DESCARTADOS,
       "broll_planos": [(round(float(s0), 1), p["info"]) for p, s0 in zip(piezas, inicio) if p["tipo"] == "broll"]}
(WORK / "informe.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
json.dump(piezas, open(WORK / "piezas.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(json.dumps({k: v for k, v in rep.items() if k not in ("broll_usados", "cortes_por_minuto")}, ensure_ascii=False, indent=1))
print("cortes por minuto:", por_min)
