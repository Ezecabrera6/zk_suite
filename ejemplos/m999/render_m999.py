"""Render del unboxing M999 desde narrado/edl_manual.py (base: render.py del Fizz Pro, el aprobado el 10/11).
Ritmo YANPOL (docs/REGLAS.md): cada tramo se parte en planos de ~3 s que alternan cámara y
encuadre. Si hay manos en la cenital va el producto (programa / cenital cerca); si no, también entra la cara.
Fuentes de la toma 2026-11-18 00-35-59 (las tres arrancan en 0 y duran 16:59; la cenital no tiene delay que se note).
Audio: 10_work/audio/voz_c.wav (pista 6 + cadena C, sin compuerta) → −14 LUFS. Sin música (docs/REGLAS.md: nada de música genérica).
uso: python render_m999.py [v=v001] [--final]      (preview 1280x720; --final 1920x1080)"""
import json, math, os, pathlib, re, subprocess, sys, importlib.util
from concurrent.futures import ThreadPoolExecutor
import numpy as np

R = pathlib.Path(os.environ.get("ZK_PROYECTO", "."))                  # carpeta del video (10_work, 11_exports, 12_project)
VER = next((a[2:] for a in sys.argv if a.startswith("v=")), "v001")
FINAL = "--final" in sys.argv
W, H = (1920, 1080) if FINAL else (640, 360) if "--360" in sys.argv else (1280, 720)   # --360: preview rápida para el visor
FPS, SR = 30, 48000
WORK = R / "10_work" / f"render_{VER}{'_1080' if FINAL else ''}"; SHOTS = WORK / "shots"; SHOTS.mkdir(parents=True, exist_ok=True)
OUT = R / "11_exports" / ("final" if FINAL else "previews") / f"m999_{VER}_{H}p.mp4"
ASSETS = pathlib.Path(os.environ.get("ZK_ASSETS", "assets"))          # logo_intro_3s.mp4 y outro.mp4
TOMA = os.environ["ZK_TOMA"]   # ruta de la toma de OBS SIN extensión: OBS graba «<toma>.mp4» y una ISO por cámara
SRC = {"programa": TOMA + ".mp4", "cara": TOMA + " CAM-StreamCam.mp4", "cenital": TOMA + " CAM-Cenital.mp4"}
GFX = R / "10_work" / "gfx"; VOZ = R / "10_work" / "audio" / "voz_c.wav"

def run(a): subprocess.run(a, check=True, capture_output=True)
def probe(f):
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(f)], capture_output=True, text=True).stdout)
    return float(d["format"]["duration"]), any(s["codec_type"] == "audio" for s in d["streams"])
def lee_wav(f, desde=0.0, dur=None):
    a = ["ffmpeg", "-v", "error", "-ss", f"{desde:.3f}", "-i", str(f)] + (["-t", f"{dur:.3f}"] if dur else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, np.float32).copy()

spec = importlib.util.spec_from_file_location("edl", pathlib.Path(__file__).with_name("edl_manual.py")); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)

# ---------- actividad de las manos: movimiento de la cenital cada 0,2 s (se calcula una vez)
ACT_F = R / "12_project/analysis/actividad_cenital.npy"
if not ACT_F.exists():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC["cenital"], "-vf", "fps=5,scale=96:54,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    v = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    m = np.concatenate([[0], np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))]); np.save(ACT_F, np.convolve(m, np.ones(5) / 5, "same"))
ACT = np.load(ACT_F); UMBRAL = float(np.percentile(ACT, 60))
def manos(a, b): seg = ACT[int(a * 5): max(int(a * 5) + 1, int(b * 5))]; return float(seg.mean()) > UMBRAL

VF = {  # la cenital ISO viene dada vuelta (el plugin graba la fuente sin la rotación de la escena)
    "programa": f"scale={W}:{H}", "cara": f"scale={W}:{H}",
    "programa_cerca": f"scale={int(W*1.25)}:{int(H*1.25)},crop={W}:{H}:{int(W*0.06)}:{int(H*0.06)}",
    "cara_apretado": f"crop=1440:810:240:60,scale={W}:{H}",
    "cenital": f"hflip,vflip,scale={int(W*1.15)}:{int(H*1.15)},crop={W}:{H}",
    "cenital_zoom": f"hflip,vflip,scale={int(W*1.5)}:{int(H*1.5)},crop={W}:{H}:{int(W*0.25)}:{int(H*0.22)}"}
# Del 14:13 al 16:22 de la toma la escena de OBS fue la de pantalla (el test del mouse): la captura muestra las pestañas
# («Teleprompter · Redragon M999») y la barra de tareas, así que se recorta a la página. Después aparece el teleprompter
# en la captura: desde ahí solo la StreamCam.
PANTALLA, SOLO_CARA = (853.5, 982.0), 982.0
VF["pantalla"] = f"crop=1627:915:20:105,scale={W}:{H}"
VF["pantalla_cerca"] = f"crop=1300:731:150:150,scale={W}:{H}"
FUENTE = lambda vis: "cenital" if vis.startswith("cenital") else "cara" if vis.startswith("cara") else "programa"
# ---------- criterio de cámara (pedido 18/11: «te falta criterio en la selección de qué cámara mostrás»)
# Cada plano se decide por LO QUE SE DICE en ese plano y por DÓNDE pasa algo:
#  - producto (cenital cerca): muestra algo («miren», «acá», «tiene»…, la caja, la base, el cable) o las manos trabajan;
#  - cara (StreamCam): habla a cámara (chistes, «suscríbanse», «publicidad», «no sé»…) o pasa algo en la StreamCam
#    (gato en el hombro, se levanta);
#  - neutro (programa: producto con la cara en el recuadro) cuando no hay nada claro.
# Dentro de cada tipo se alternan dos encuadres, así hay corte cada ~3 s sin saltar de idea. Los cortes caen al
# principio de una frase cuando se puede.
ACT_CARA_F = R / "12_project/analysis/actividad_cara.npy"
if not ACT_CARA_F.exists():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC["cara"], "-vf", "fps=5,scale=96:54,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    v = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    m = np.concatenate([[0], np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))]); np.save(ACT_CARA_F, np.convolve(m, np.ones(5) / 5, "same"))
ACT_CARA = np.load(ACT_CARA_F); U_CEN = float(np.percentile(ACT, 65)); U_CARA = float(np.percentile(ACT_CARA, 88))
PROD = re.compile(r"\bmir[aeé]n?\b|\bac[aá]\b|\bah[ií]\b|\besto\b|\bpueden ver|\bse ve\b|\btiene\b|\btrae\b|\bcaja|\bbolsa|\bbase\b|\bcable|"
                  r"\bbot[oó]n|\bpines|\bsensor|\bdpi\b|\bloguito|\bcolores|\brojo\b|\bluces|\babajo\b|\bdesliza|\bconect|\benchuf|"
                  r"\babrir|\babriendo|\babierto|\bsellito|\bmanual|\bsticker|\bmousepad|\bclic|\breceptor|\bpesa\b|\bgramos|\bagarra|\bprendido|\bse mueve|\bp[aá]gina|\bprueba|\btest", re.I)
CARA = re.compile(r"suscr[ií]b|\blike\b|coment|publicidad|promoci[oó]n|\bpobre|millonario|youtuber|mal[ií]simo|\bno s[eé]\b|"
                  r"programador|\bgamer|\bnariz|boludear|\bche\b|culpa|protagonistas|grabar|concentrar|vergüenza|me pregunto|"
                  r"ansioso|apurado|\bgato|\bgatos|saludar|teor[ií]a|\bcaro\b|car[ií]simo|regular|\bojal[aá]|\bpelos|ganas", re.I)
def dicho(a, b):
    return " ".join(x[2] for x in E.L[1:] if x[0] < b and x[1] > a)
def tipo_de(a, b, forzado=None):
    if forzado == "cara": return "cara"
    if forzado == "programa": return "neutro"
    if forzado == "producto": return "producto"
    txt = dicho(a, b); i, j = int(a * 5), max(int(a * 5) + 1, int(b * 5))
    cen, car = float(ACT[i:j].mean()), float(ACT_CARA[i:j].mean())
    tp, tf = bool(PROD.search(txt)), bool(CARA.search(txt))
    if tf and not tp: return "cara"                       # habla a cámara
    if tp and not tf: return "producto"                   # muestra algo
    if tp and tf: return "producto" if cen > U_CEN else "cara"
    return "producto" if cen > U_CEN else "cara" if car > U_CARA else "neutro"   # sin palabras claras: donde pasa algo
ENCUADRES = {"producto": ["cenital_zoom", "cenital"], "cara": ["cara", "cara_apretado"], "neutro": ["programa", "programa_cerca"]}
ENC_PANT = {"producto": ["pantalla", "pantalla_cerca"], "cara": ["cara_apretado", "cara"], "neutro": ["pantalla", "cenital_zoom"]}
def cortes_de(a, b):
    """Puntos de corte (s de la toma) dentro del tramo: inicios de frase a 1,6–3,2 s; si no hay, cada ~2,3 s.
    pedido 18/11 (v009 2:52: «no más de 2 segundos sin un cambio de cámara»."""
    ini = [x[0] - 0.1 for x in E.L[1:] if a + 1.4 < x[0] < b - 1.4]; out = [a]
    while b - out[-1] > 3.2:
        c = [x for x in ini if 1.6 <= x - out[-1] <= 3.2]
        out.append(min(c, key=lambda x: abs(x - out[-1] - 2.3)) if c else out[-1] + max(1.6, min(2.3, (b - out[-1]) / 2)))
    return out + [b]
CAMR = getattr(E, "CAM", {})   # cámara pedida por frase (renglón de la toma): cara / producto / ancho / alterna
def renglon_de(a, b):
    ov = [(min(b, x[1]) - max(a, x[0]), k) for k, x in enumerate(E.L) if x and x[0] < b and x[1] > a]
    return max(ov)[1] if ov else None

# ---------- línea de tiempo
piezas, audio, mapa, BLOQUEOS, PIIPS = [], [], [], [], []   # BLOQUEOS: logo, outro y blooper (sin gráficos encima)
t = 0; cuenta = {k: 0 for k in ENCUADRES}; ult = None
for p in E.piezas():
    if p == "BLOOPER":
        a0, b0 = E.BLOOPER; fr = round((b0 - a0) * FPS)
        piezas.append({"tipo": "blooper", "src": SRC["cenital"], "ss": a0, "fr": fr, "vf": VF["cenital"] + ",hue=s=0", "info": "BLOOPER"})
        audio.append((t / FPS, "voz", a0, fr / FPS)); PIIPS.append(t / FPS + E.BLOOPER_PIIP - a0)
        BLOQUEOS.append((t / FPS, (t + fr) / FPS)); t += fr; ult = None; continue
    if p in ("LOGO", "OUTRO"):
        f = ASSETS / ("logo_intro_3s.mp4" if p == "LOGO" else "outro.mp4"); d, a_ = probe(f); fr = round(d * FPS)
        piezas.append({"tipo": p.lower(), "src": str(f), "ss": 0.0, "fr": fr, "vf": f"scale={W}:{H}", "info": p})
        if a_: audio.append((t / FPS, str(f), 0.0, fr / FPS))
        BLOQUEOS.append((t / FPS, (t + fr) / FPS)); t += fr; ult = None; continue
    a, b, op = p; F = max(1, round((b - a) * FPS))
    audio.append((t / FPS, "voz", a, F / FPS, "huecos" not in op)); mapa.append((t / FPS, a, b))   # con «huecos» (gatos, clics) no se baja nada
    cs = [round((c - a) * FPS) for c in cortes_de(a, b)]; cs[-1] = F
    for j in range(len(cs) - 1):
        fr = cs[j + 1] - cs[j]; s0 = a + cs[j] / FPS
        pant = PANTALLA[0] <= s0 < PANTALLA[1]
        cam = CAMR.get(renglon_de(s0, s0 + fr / FPS), op.get("cam"))
        if s0 >= SOLO_CARA: ti, enc = "cara", ENCUADRES["cara"]
        elif pant: ti, enc = "producto", ENC_PANT["producto"]          # v009 9:57: la pantalla siempre, con cara y cenital en recuadros
        else:
            ti = ("cara", "producto")[j % 2] if cam == "alterna" else tipo_de(s0, s0 + fr / FPS, "producto" if cam == "ancho" else cam)
            enc = ENCUADRES[ti]
        vis = enc[cuenta[ti] % 2]
        if vis == ult: cuenta[ti] += 1; vis = enc[cuenta[ti] % 2]     # nunca dos planos iguales seguidos
        cuenta[ti] += 1
        vis = op.get("vis", "cenital" if cam == "ancho" else vis)    # encuadre fijo pedido en el EDL (ancho: que entre todo lo que muestra)
        ss = s0 if not (ti == "producto" and "prod" in op) else op["prod"] + (s0 - a)   # «prod»: el producto sale de otro momento de la toma
        if j == 0 and op.get("primero") and op.get("abre"): vis, ss = op["abre"]
        pz = {"tipo": vis, "src": SRC[FUENTE(vis)], "ss": ss, "fr": fr, "vf": VF[vis], "info": f"{ss:.1f} {ti}"}
        if op.get("pip"):
            fv, fs = op["pip"]; pz["pip"] = (SRC[FUENTE(fv)], s0 if fs is None else fs + (s0 - a), VF[fv])
        if pant:   # la escena de pantalla de OBS ya trae la cara abajo a la derecha: el recuadro va pegado a la esquina y la tapa entera (v011 10:05 «se ve doble mi cámara»)
            pz["pip"], pz["pip2"], pz["pip_esquina"] = (SRC["cara"], s0, VF["cara"]), (SRC["cenital"], s0, VF["cenital"]), True
        piezas.append(pz); ult = vis
    t += F
TOTAL = t / FPS

# ---------- gráficos anclados al renglón donde se dice el dato
GX = {x["id"]: x for x in json.load(open(GFX / "catalogo.json", encoding="utf-8"))["graficos"]}
GX["like"] = {"id": "like", "archivo": "g12_like_suscribite.mov", "dur_sugerida": 3.5, "sfx": [{"archivo": "sfx/classic_click_1117.mp3", "t": 1.35, "vol": 0.08}]}
def salida(s):
    for t0, a, b in mapa:
        if a - 0.2 <= s < b: return t0 + max(0.0, s - a)
pegados, faltan = [], []
for g in E.GRAF:
    gid, ren, off = (tuple(g) + (0.0,))[:3]                       # off: segundos desde que arranca la frase hasta que dice el dato
    en = salida(E.L[ren][0] + off)
    if en is None: faltan.append((gid, ren)); continue
    pegados.append((gid, en + 0.25, min(float(GX[gid]["dur_sugerida"]), 6.0), GX[gid]))
pegados.sort(key=lambda x: x[1])
for k in range(1, len(pegados)):                                   # dos gráficos nunca a la vez
    p0, p1 = pegados[k - 1], pegados[k]
    if p1[1] < p0[1] + p0[2] + 0.3: pegados[k] = (p1[0], p0[1] + p0[2] + 0.3, p1[2], p1[3])

for k, (gid, en, dur, gx) in enumerate(pegados):                  # ni sobre el logo ni sobre el outro
    for a0, b0 in BLOQUEOS:
        if en < b0 and en + dur > a0:
            dur = max(0.0, a0 - en - 0.1)
            pegados[k] = (gid, en, dur, gx)
bajas = [x[0] for x in pegados if x[2] < 2.0]; pegados = [x for x in pegados if x[2] >= 2.0]
if bajas: print("gráficos sacados por pisar el logo/outro:", bajas)

if "--plan" in sys.argv:
    import collections
    print(collections.Counter(p["info"].split()[-1] for p in piezas if " " in p["info"]))
    for p in piezas[:40]: print(f'{p["info"]:>16} {p["tipo"]:<15} {p["fr"]/FPS:4.1f}s  {dicho(float(p["info"].split()[0]), float(p["info"].split()[0]) + p["fr"]/FPS)[:70] if " " in p["info"] else ""}')
    print(json.dumps({"duracion": round(TOTAL, 1), "planos": len(piezas), "graficos": [(x[0], round(x[1], 1)) for x in pegados], "faltan": faltan}, ensure_ascii=False, indent=1)); sys.exit(0)

# ---------- 1) planos de video (nombre por hash: si cambia el corte, no se reusa un plano viejo)
import hashlib
def shot_f(p): return SHOTS / (hashlib.md5(f"{p['src']}|{p['ss']:.3f}|{p['fr']}|{p['vf']}|{p.get('pip')}|{p.get('pip2')}|{p.get('pip_esquina')}|{FINAL}".encode()).hexdigest()[:16] + ".mp4")
def hace(i_p):
    i, p = i_p; f = shot_f(p)
    if f.exists() and f.stat().st_size > 1000: return
    if p.get("pip"):
        ps, pss, pvf = p["pip"]; pw = int(W * 0.36) // 2 * 2; ph = int(pw * 9 / 16) // 2 * 2; m = int(W * 0.025); b = max(3, W // 480)
        caja = lambda k, vf: f"[{k}:v]{vf},scale={pw}:{ph},pad={pw + 2 * b}:{ph + 2 * b}:{b}:{b}:color=0x14161A[p{k}];"
        m1 = 0 if p.get("pip_esquina") else m
        fc = f"[0:v]{p['vf']}[a];" + caja(1, pvf) + f"[a][p1]overlay=W-w-{m1}:H-h-{m1}[o1];"
        ins = ["-ss", f"{p['ss']:.3f}", "-i", p["src"], "-ss", f"{pss:.3f}", "-i", ps]
        if p.get("pip2"):                                                  # segundo recuadro abajo a la izquierda
            s2, ss2, vf2 = p["pip2"]; ins += ["-ss", f"{ss2:.3f}", "-i", s2]
            fc += caja(2, vf2) + f"[o1][p2]overlay={m1}:H-h-{m1}[o2];"; last = "o2"   # simétrico al de la derecha (v012 9:37)
        else: last = "o1"
        filt = ["-filter_complex", fc + f"[{last}]fps={FPS},format=yuv420p[v]", "-map", "[v]"]
        run(["ffmpeg", "-v", "error", "-y"] + ins + ["-frames:v", str(p["fr"]), "-an"]
            + filt + ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19" if FINAL else "24", "-g", "60", "-r", str(FPS), str(f)])
        return
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['ss']:.3f}", "-i", p["src"], "-frames:v", str(p["fr"]), "-an",
         "-vf", p["vf"] + f",fps={FPS},format=yuv420p", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19" if FINAL else "24",
         "-g", "60", "-r", str(FPS), str(f)])
with ThreadPoolExecutor(3) as ex: list(ex.map(hace, enumerate(piezas)))
(WORK / "lista.txt").write_text("".join(f"file '{shot_f(p).as_posix()}'\n" for p in piezas), encoding="utf-8")
base = WORK / "base.mp4"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "lista.txt"), "-c", "copy", str(base)])

# ---------- 2) audio: voz + logo/outro + un efecto suave por gráfico, después −14 LUFS
mix = np.zeros(int(TOTAL * SR) + SR, np.float32)
def pone(x, en, gan=1.0, fade=0.012):
    n = int(fade * SR)
    if len(x) > 2 * n: x[:n] *= np.linspace(0, 1, n); x[-n:] *= np.linspace(1, 0, n)
    i = int(round(en * SR)); j = min(len(mix), i + len(x)); mix[i:j] += gan * x[: j - i]
HABLA = [(x[0] - 0.05, x[1] + 0.35) for x in E.L[1:]]   # Whisper adelanta los finales: margen largo después
def sin_respiraciones(x, desde):
    """v009 5:43 «se escuchan respiraciones al mic»: entre frases la voz baja 8 dB (rampas de 30 ms)."""
    g = np.full(len(x), 0.4, np.float32); t0 = desde
    for a_, b_ in HABLA:
        if b_ > t0 and a_ < t0 + len(x) / SR: g[max(0, int((a_ - t0) * SR)):max(0, int((b_ - t0) * SR))] = 1.0
    k = int(0.03 * SR); return x * np.convolve(g, np.ones(k) / k, "same").astype(np.float32)
for en, fuente, desde, dur, *ducha in audio:
    x = lee_wav(VOZ if fuente == "voz" else fuente, desde, dur)
    pone(sin_respiraciones(x, desde) if (fuente == "voz" and ducha and ducha[0]) else x, en)
def rms_db(x, win):
    if len(x) < win: return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    c = np.concatenate(([0.0], np.cumsum(x.astype(np.float64) ** 2)))
    e = np.sqrt(np.maximum(0, (c[win:] - c[:-win]) / win)); return 20 * np.log10(np.percentile(e, 98) + 1e-9)
voz_db = rms_db(mix[np.abs(mix) > 1e-4], int(0.4 * SR))
for en in PIIPS:                                                   # piiip del blooper: tono de 1 kHz de 0,6 s encima del audio
    n = np.arange(int(0.6 * SR)); tono = np.sin(2 * np.pi * 1000 * n / SR) * 10 ** ((voz_db - 10) / 20) * np.sqrt(2)
    pone(tono.astype(np.float32), en, fade=0.008)
for gid, en, dur, gx in pegados:
    for s in (gx.get("sfx") or [])[:1]:
        x = lee_wav(GFX / s["archivo"]); pone(x, max(0, en + float(s.get("t", 0))), 10 ** ((voz_db - 16 - rms_db(x, int(0.1 * SR))) / 20), fade=0.002)
for ren, off, arch, dur_ in getattr(E, "SFX", []):                 # efectos sueltos por frase (chistes), sin cartel
    en = salida(E.L[ren][0])
    if en is None: continue
    x = lee_wav(GFX / "sfx" / arch, 0, dur_); pone(x, en + off, 10 ** ((voz_db - 14 - rms_db(x, int(0.1 * SR))) / 20), fade=0.02)
crudo = WORK / "mezcla_cruda.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(crudo)], input=mix.tobytes(), check=True)
m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(crudo), "-af", "loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
j = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
mezcla = WORK / "mezcla.wav"
run(["ffmpeg", "-v", "error", "-y", "-i", str(crudo), "-af",
     f"loudnorm=I=-14:TP=-1.5:LRA=8:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
     "-ar", str(SR), str(mezcla)])
def integ(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", r[r.rfind("Summary:"):]).group(1))
# Siempre: ganancia hasta −14 y limitador con sobremuestreo (el AAC sube los picos: v004 dio −0,5 dBTP sin esto)
falta_db = -14.0 - integ(mezcla)
tmp = WORK / "mezcla_lim.wav"
run(["ffmpeg", "-v", "error", "-y", "-i", str(mezcla), "-af", f"volume={falta_db + 1.3:.2f}dB,aresample=192000,alimiter=limit=0.76:attack=1:release=50:level=false,aresample={SR}", str(tmp)])
tmp.replace(mezcla)
LUFS_FINAL = integ(mezcla)

# ---------- 3) gráficos encima, por partes de 1 minuto en paralelo, y el archivo entero con la mezcla
PARTE_S = 60.0; PARTES = WORK / "partes"; PARTES.mkdir(exist_ok=True); n_partes = math.ceil(TOTAL / PARTE_S)
def hace_parte(k):
    t0 = k * PARTE_S; d = min(PARTE_S, TOTAL - t0); f = PARTES / f"parte_{k + 1:02d}.mp4"
    ins, fc, last, m_ = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{d:.3f}", "-i", str(base)], [], "[0:v]", 0
    for gid, en, dur, gx in pegados:
        if en + dur <= t0 or en >= t0 + d: continue
        src_g = str(GFX / gx["archivo"])
        ins += (["-itsoffset", f"{en - t0:.3f}", "-i", src_g] if en >= t0 else ["-ss", f"{t0 - en:.3f}", "-i", src_g])
        a_, b_ = max(0.0, en - t0), en + dur - t0
        fc.append(f"[{m_ + 1}:v]scale={W}:{H},format=rgba[g{m_}]")
        fc.append(f"{last}[g{m_}]overlay=0:0:eof_action=pass:enable='between(t,{a_:.3f},{b_:.3f})'[v{m_}]"); last = f"[v{m_}]"; m_ += 1
    run(ins + (["-filter_complex", ";".join(fc), "-map", last] if fc else ["-map", "0:v"]) + ["-an",
        "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19" if FINAL else "23", "-g", "60", str(f)])
    print(f"parte {k + 1}/{n_partes} lista", flush=True)
with ThreadPoolExecutor(2) as ex: list(ex.map(hace_parte, range(n_partes)))
(PARTES / "lista.txt").write_text("".join(f"file '{(PARTES / f'parte_{k + 1:02d}.mp4').as_posix()}'\n" for k in range(n_partes)), encoding="utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(PARTES / "lista.txt"), "-i", str(mezcla), "-map", "0:v", "-map", "1:a",
     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(OUT)])

# ---------- informe del ritmo (REGLAS_DE_EDICION.md)
dur_p = [p["fr"] / FPS for p in piezas]; cuerpo = [d for p, d in zip(piezas, dur_p) if p["tipo"] not in ("logo", "outro")]
inicio = np.cumsum([0] + dur_p[:-1]); por_min = {}
for p, s0 in zip(piezas, inicio): por_min[int(s0 // 60)] = por_min.get(int(s0 // 60), 0) + 1
rep = {"version": VER, "salida": str(OUT), "duracion_s": round(TOTAL, 1), "planos": len(piezas),
       "plano_promedio_s": round(float(np.mean(cuerpo)), 2), "plano_mas_largo_s": round(max(cuerpo), 2),
       "planos_de_mas_de_6s": sum(d > 6 for d in cuerpo), "cortes_por_minuto": por_min,
       "graficos": [(gid, round(en, 1)) for gid, en, _, _ in pegados], "graficos_sin_ancla": faltan,
       "loudness_antes": j["input_i"], "lufs_final": LUFS_FINAL}
(WORK / "informe.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
json.dump(piezas, open(WORK / "piezas.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(json.dumps(rep, ensure_ascii=False))
