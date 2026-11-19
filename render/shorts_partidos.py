"""Shorts/Reels 9:16 con pantalla partida (estilo aprobado el 10/11/2026, referencia Drigo): arriba la cara, abajo el
producto desde la cenital, a pantalla completa y sin bordes. Una palabra por vez, minúscula y blanca, sobre la unión de
las dos cámaras. Sin franjas de título, sin gancho escrito, sin tarjeta final, sin música. Woosh suave en cada salto de
tramo. Los carteles, si hay, son los lower thirds de graficos/carteles.py (pedido 18/11: lo demás «se nota IA»).

Cada Short se arma con tramos de la toma (segundos), cortados en el silencio más hondo cerca de cada borde. Los planos
duran ~2,2 s y alternan encuadre (cara normal/cerrada, producto normal/cerca), así nunca hay más de ~2 s sin cambio.

uso: python render/shorts_partidos.py ejemplos/m999/shorts.json [1-9|all]
config (JSON, rutas relativas a ZK_PROYECTO salvo las que empiezan con ZK_TOMA):
  {"cenital": "<ZK_TOMA> CAM-Cenital.mp4", "cara": "<ZK_TOMA> CAM-StreamCam.mp4", "voz": "10_work/audio/voz_c.wav",
   "gfx": "10_work/gfx", "cenital_vf": "hflip,vflip,", "ignorar_izq": 70, "prompt": "...", "corrige": {"mal": "bien"},
   "shorts": [{"n": 1, "slug": "...", "tramos": [[desde, hasta, {opciones}], ...]}]}
  desde/hasta: segundo de la toma o ["min", lo, hi] (corta en el silencio más hondo de esa ventana).
  opciones: {"vista": "ancho"} (producto más abierto), {"gfx": [id_cartel, palabra_ancla]}.
Salida: <ZK_PROYECTO>/11_exports/shorts/short_NN_slug.mp4 + _portada.jpg y 10_work/shorts_vertical/<slug>/informe.json."""
import glob, json, os, pathlib, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CFG_F = pathlib.Path(sys.argv[1]); CFG = json.loads(CFG_F.read_text(encoding="utf-8-sig"))
R = pathlib.Path(os.environ["ZK_PROYECTO"]); TOMA = os.environ.get("ZK_TOMA", "")
ruta = lambda s: pathlib.Path(s.replace("<ZK_TOMA>", TOMA)) if s.startswith("<ZK_TOMA>") else R / s
CEN, CARA, VOZ, GFX = ruta(CFG["cenital"]), ruta(CFG["cara"]), ruta(CFG["voz"]), ruta(CFG.get("gfx", "10_work/gfx"))
CEN_VF = CFG.get("cenital_vf", "")
PROG = ruta(CFG["programa"]) if CFG.get("programa") else None   # la salida de OBS (para tramos con {"pantalla": [x, y, w, h]})
WK = R / "10_work/shorts_vertical"; WK.mkdir(parents=True, exist_ok=True)
OUT = R / "11_exports/shorts"; OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS, SR = 1080, 1920, 30, 48000
TOP_H = 680; BOT_H = H - TOP_H                                    # arriba la cara 1080x680, abajo el producto 1080x1240
CEN_W = round(1080 * W / BOT_H) // 2 * 2                         # ancho de cenital 1920x1080 que entra en 1080x1240 sin deformar
# la cara, normal y más cerrada; los dos llegan hasta abajo del cuadro para no cortar el mentón (pedido 10/11)
CARA_CROPS = [tuple(c) for c in CFG.get("cara_crops", [(1714, 1080, 112, 0), (1430, 900, 256, 120)])]
FF = os.environ.get("ZK_FFMPEG", "ffmpeg")


def run(a):
    r = subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode: raise RuntimeError(r.stderr[-2500:])
    return r.stderr
def lee_wav(f, desde=0.0, dur=None):
    a = [FF, "-v", "error", "-ss", f"{desde:.3f}", "-i", str(f)] + (["-t", f"{dur:.3f}"] if dur else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, np.float32).copy()
def escribe_wav(x, f): subprocess.run([FF, "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(f)], input=x.tobytes(), check=True)
def lufs(f):
    r = run([FF, "-hide_banner", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"])
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", r[r.rfind("Summary:"):]).group(1))


# ---------- cortes en el silencio real
def env_db(x, win=int(0.02 * SR)):
    n = len(x) // win; e = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)); return 20 * np.log10(e + 1e-9)
def punto(v, lado):
    if isinstance(v, (list, tuple)): lo, hi = v[1], v[2]
    else: lo, hi = (v - 0.10, v + 0.06) if lado == "a" else (v - 0.06, v + 0.12)
    x = lee_wav(VOZ, lo, hi - lo); e = env_db(x)
    return lo + (int(np.argmin(e)) + 0.5) * 0.02, float(e.min())


# ---------- encuadre del producto: busca lo rojo (marco del mousepad o del teclado) en la cenital
def cuadro(t, w=480, h=270):
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{t:.3f}", "-i", str(CEN), "-frames:v", "1", "-vf", f"{CEN_VF}scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.int16)
def rojo(img):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]; return ((r > 110) & (r > g * 1.9) & (r > b * 1.7)).astype(np.float32)
def ventana(hist, ancho):
    c = np.convolve(hist, np.ones(ancho), "valid"); return int(np.argmax(c)) + ancho / 2 if c.max() > 0 else len(hist) / 2
MODO = "rojo"   # cómo se encuadra el producto: "rojo" (marco del mousepad/teclado) o "mano" (donde hay movimiento)
def mapa_rojo(a, b, ks=(0.15, 0.5, 0.85)):
    if MODO == "mano":   # pedido 19/11: con el mouse en uso, el marco rojo dejaba la mano y el mouse cortados al costado
        m = sum((np.abs(cuadro(a + (b - a) * k) - cuadro(a + (b - a) * k + 0.25)).sum(2) > 60).astype(np.float32) for k in ks)
    else: m = sum(rojo(cuadro(a + (b - a) * k)) for k in ks)
    m[:, :CFG.get("ignorar_izq", 0)] *= 0.25                   # algo fijo al costado que no es el producto
    return m
S480 = 1920 / 480
def ventana_tramo(a, b):
    """Una ventana por tramo: el producto no salta entre sus planos."""
    cx = ventana(mapa_rojo(a, b, (0.1, 0.3, 0.5, 0.7, 0.9)).sum(0), int(CEN_W / S480 * 0.75)) * S480
    return CEN_W, 1080, int(max(0, min(1920 - CEN_W, cx - CEN_W / 2))) // 2 * 2, 0
def encuadre(a, b, vista, win):
    cw, ch, x, y = win
    if vista == "ancho_z":
        zw, zh = int(cw * 0.88) // 2 * 2, int(ch * 0.88) // 2 * 2; return zw, zh, x + (cw - zw) // 2, (ch - zh) // 2
    if vista == "ancho": return cw, ch, x, y
    m = mapa_rojo(a, b)[:, int(x / S480): int((x + cw) / S480)]
    if vista == "cen":
        zw, zh = 860, round(860 * BOT_H / W) // 2 * 2
        cy = ventana(m.sum(1), int(zh / S480 * 0.6)) * S480 if m.sum() > 50 else 540
        return zw, zh, x + (cw - zw) // 2, int(max(0, min(1080 - zh, cy - zh / 2))) // 2 * 2
    col = m.sum(0); hay = np.where(col > 0.15 * col.max())[0] if m.sum() > 50 else []
    largo = (hay[-1] - hay[0] + 1) * S480 * 1.12 if len(hay) else 0
    zw = int(min(cw - 60, max(720, largo))) // 2 * 2; zh = int(min(1080, zw * BOT_H / W)) // 2 * 2
    cx = x + ventana(col, int(zw / S480 * 0.7)) * S480 if m.sum() > 50 else x + cw / 2
    cy = ventana(m.sum(1), int(zh / S480 * 0.6)) * S480 if m.sum() > 50 else 540
    return zw, zh, int(max(x, min(x + cw - zw, cx - zw / 2))) // 2 * 2, int(max(0, min(1080 - zh, cy - zh / 2))) // 2 * 2


# ---------- Whisper large-v3 en GPU, tramo por tramo (sobre el archivo entero inventa palabras en las uniones)
_modelo = None
def whisper():
    global _modelo
    if _modelo is None:
        for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
            os.add_dll_directory(d); os.environ["PATH"] = d + ";" + os.environ["PATH"]
        from faster_whisper import WhisperModel
        _modelo = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
    return _modelo
def transcribe(wav):
    segs, _ = whisper().transcribe(str(wav), language="es", word_timestamps=True, initial_prompt=CFG.get("prompt"), vad_filter=False, beam_size=5)
    return [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]


def ass_t(t): return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
def subtitulos(palabras, t_fin, path):
    hdr = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
           "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           "Style: S,Segoe UI Black,112,&H00FFFFFF,&H00FFFFFF,&H50000000,&H78000000,0,0,0,0,100,100,0,0,1,4,2,5,40,40,0,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    fix = CFG.get("corrige", {})
    palabras = [dict(p) for p in palabras if p["w"].strip(".,¡!¿?").lower() not in ("ey", "eh", "ehm", "em", "ah", "pues", "hmm")]
    junta = []
    for p in palabras:                                          # «45» + «.000» → «45.000»
        if junta and re.match(r"^\.\d{3}", p["w"]) and re.search(r"\d$", junta[-1]["w"]): junta[-1]["w"] += p["w"]; junta[-1]["e"] = p["e"]
        else: junta.append(p)
    grupos, cur = [], []
    for p in junta:                                             # una palabra por vez; las de 1–2 letras van pegadas a la que sigue
        if cur and (len(cur[-1]["w"].strip(".,¿?¡!…")) > 2 or len(cur) >= 2): grupos.append(cur); cur = []
        cur.append(p)
    if cur: grupos.append(cur)
    with open(path, "w", encoding="utf-8") as f:
        f.write(hdr)
        for k, g in enumerate(grupos):
            txt = " ".join(fix.get(p["w"].strip(".,¿?¡!…").lower(), p["w"].strip(".,¿?¡!…")).lower() for p in g)
            s0, e1 = g[0]["s"], g[-1]["e"] + 0.15
            if k + 1 < len(grupos): e1 = min(e1, grupos[k + 1][0]["s"] - 0.02)
            f.write(f"Dialogue: 0,{ass_t(s0)},{ass_t(min(e1, t_fin))},S,,0,0,0,,{{\\pos(540,{TOP_H})}}{txt}\n")


def placa(gid, path):
    """El cartel recortado a su caja, abajo a la izquierda de la mitad del producto."""
    g = Image.open(GFX / f"{gid}.png").convert("RGBA"); g = g.crop(g.getchannel("A").getbbox())
    esc = min(1.0, 960 / g.width); g = g.resize((round(g.width * esc), round(g.height * esc)), Image.LANCZOS)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.alpha_composite(g, (40, H - g.height - 300)); im.save(path)


def build(s):
    global MODO
    modo_short = s.get("centrar", CFG.get("centrar", "rojo"))   # cada tramo puede pedir el suyo con {"centrar": ...}
    slug = f"short_{s['n']:02d}_{s['slug']}"; wk = WK / slug; wk.mkdir(exist_ok=True)
    tramos = []
    for a, b, o in s["tramos"]:
        (ta, ea), (tb, eb) = punto(a, "a"), punto(b, "b")
        tramos.append({"a": round(ta, 3), "b": round(tb, 3), "borde_db": [round(ea, 1), round(eb, 1)], **o})
    planos, t, k = [], 0.0, 0
    for tr in tramos:
        F = round((tr["b"] - tr["a"]) * FPS); n = max(1, round(F / FPS / 2.2)); base = tr.get("vista", "cen")
        MODO = tr.get("centrar", modo_short); tr["sal"] = t; tr["b"] = tr["a"] + F / FPS; tr["win"] = ventana_tramo(tr["a"], tr["b"])
        cortes = [round(F * j / n) for j in range(n + 1)]
        for j in range(n):
            vista = base if k % 2 == 0 else ("ancho_z" if base == "ancho" else "zoom")
            planos.append({"a": tr["a"] + cortes[j] / FPS, "fr": cortes[j + 1] - cortes[j], "vista": vista, "win": tr["win"], "modo": MODO,
                           "pantalla": tr.get("pantalla")}); k += 1
        t += F / FPS
    t_voz = t
    for i, p in enumerate(planos):
        MODO = p["modo"]
        cw, ch, x, y = encuadre(p["a"], p["a"] + p["fr"] / FPS, p["vista"], p["win"]); qw, qh, qx, qy = CARA_CROPS[i % 2]
        f = wk / f"p{i:02d}_{p['a']:.2f}_{cw}x{ch}+{x}+{y}_{qy}.mp4"; p["archivo"] = str(f)   # el nombre lleva el encuadre: si cambia, se rehace
        p.update(crop=[cw, ch, x, y], cara=[qw, qh, qx, qy])
        extra = []
        if p.get("pantalla"):   # pedido 19/11: cuando se muestra algo en la PC, en el medio va esa parte de la pantalla
            px, py, pw, ph = p["pantalla"]; sh = round(W * ph / pw) // 2 * 2; f = f.with_name(f.stem + f"_pant{px}-{py}.mp4"); p["archivo"] = str(f)
            fc = (f"[0:v]{CEN_VF}crop={cw}:{ch}:{x}:{y},scale={W}:{BOT_H}:flags=lanczos,crop={W}:{BOT_H - sh},setsar=1[ab];"
                  f"[2:v]crop={pw}:{ph}:{px}:{py},scale={W}:{sh}:flags=lanczos,setsar=1[sc];"
                  f"[1:v]crop={qw}:{qh}:{qx}:{qy},scale={W}:{TOP_H}:flags=lanczos,setsar=1[ar];[ar][sc][ab]vstack=inputs=3,fps={FPS},format=yuv420p[v]")
            extra = ["-ss", f"{p['a']:.3f}", "-i", str(PROG)]
        else:
            fc = (f"[0:v]{CEN_VF}crop={cw}:{ch}:{x}:{y},scale={W}:{BOT_H}:flags=lanczos,setsar=1[ab];"
                  f"[1:v]crop={qw}:{qh}:{qx}:{qy},scale={W}:{TOP_H}:flags=lanczos,setsar=1[ar];[ar][ab]vstack=inputs=2,fps={FPS},format=yuv420p[v]")
        if not f.exists():
            run([FF, "-v", "error", "-y", "-ss", f"{p['a']:.3f}", "-i", str(CEN), "-ss", f"{p['a']:.3f}", "-i", str(CARA)] + extra + ["-filter_complex", fc,
                 "-map", "[v]", "-frames:v", str(p["fr"]), "-an", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-g", "30", "-r", str(FPS), str(f)])
    (wk / "lista.txt").write_text("".join(f"file '{pathlib.Path(p['archivo']).as_posix()}'\n" for p in planos), encoding="utf-8")
    base = wk / "base.mp4"; run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(wk / "lista.txt"), "-c", "copy", str(base)])
    total = sum(p["fr"] for p in planos) / FPS
    mix = np.zeros(int((total + 0.5) * SR), np.float32); palabras = []
    for k, tr in enumerate(tramos):
        x = lee_wav(VOZ, tr["a"], tr["b"] - tr["a"]); n = int(0.012 * SR); x[:n] *= np.linspace(0, 1, n); x[-n:] *= np.linspace(1, 0, n)
        i = int(round(tr["sal"] * SR)); mix[i:i + len(x)] += x[: len(mix) - i]
        f = wk / f"tramo_{k:02d}.wav"; escribe_wav(x, f); ws = transcribe(f); tr["solo"] = " ".join(w["w"] for w in ws)
        palabras += [{"w": w["w"], "s": tr["sal"] + w["s"], "e": tr["sal"] + min(w["e"], tr["b"] - tr["a"])} for w in ws]
    (wk / "uniones.txt").write_text("\n".join(f"{k:02d} [{tr['a']:.2f}–{tr['b']:.2f}] {tr['solo']}" for k, tr in enumerate(tramos)), encoding="utf-8")
    gfx = []
    for tr in tramos:
        if "gfx" not in tr: continue
        gid, ancla = tr["gfx"]
        hit = next((p for p in palabras if tr["sal"] - 0.2 <= p["s"] <= tr["sal"] + tr["b"] - tr["a"] and ancla in p["w"].lower()), None)
        en = (hit["s"] if hit else tr["sal"]) + 0.1; gfx.append((gid, en, max(2.5, min(3.5, total - en - 0.2))))
    voz_db = 20 * np.log10(np.sqrt(np.mean(mix[np.abs(mix) > 1e-4] ** 2)) + 1e-9)
    wo = lee_wav(GFX / "sfx/air_woosh_1489.mp3"); e = np.sqrt(np.convolve(wo ** 2, np.ones(2400) / 2400, "same"))
    pico = int(np.argmax(e)); gan = 10 ** ((voz_db - 16 - 20 * np.log10(e.max() + 1e-9)) / 20)
    for tr in tramos[1:]:                                       # woosh suave en cada salto de tramo, con el pico justo en el corte
        i = int(tr["sal"] * SR) - pico
        if i >= 0: mix[i:i + len(wo)] += gan * wo[: len(mix) - i]
    for ren_s, arch, dur in s.get("sfx", []):                   # efectos sueltos: [segundo del Short, archivo en gfx/sfx, duración]
        x = lee_wav(GFX / "sfx" / arch, 0, dur); e = np.sqrt(np.convolve(x ** 2, np.ones(4800) / 4800, "valid"))
        g = 10 ** ((voz_db - 14 - 20 * np.log10(np.percentile(e, 98) + 1e-9)) / 20); i = int(ren_s * SR); mix[i:i + len(x)] += g * x[: len(mix) - i]
    crudo = wk / "mezcla_cruda.wav"; escribe_wav(mix, crudo); mezcla = wk / "mezcla.wav"
    m = run([FF, "-hide_banner", "-i", str(crudo), "-af", "loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json", "-f", "null", "-"])
    j = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
    run([FF, "-v", "error", "-y", "-i", str(crudo), "-af", f"loudnorm=I=-14:TP=-1.5:LRA=8:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
         f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", str(SR), str(mezcla)])
    for _ in range(4):                                          # loudnorm lineal no sube si el pico no deja margen: ganancia + limitador
        falta = -14.0 - lufs(mezcla)
        if abs(falta) <= 0.3: break
        tmp = wk / "mezcla_lim.wav"
        run([FF, "-v", "error", "-y", "-i", str(mezcla), "-af", f"volume={falta + 0.15:.2f}dB,alimiter=limit=0.84:attack=3:release=60:level=false", "-ar", str(SR), str(tmp)])
        tmp.replace(mezcla)
    ass = wk / "subs.ass"; subtitulos([p for p in palabras if p["s"] < t_voz], t_voz, ass)
    ins = [FF, "-v", "error", "-y", "-i", str(base), "-i", str(mezcla)]; fc = [f"[0:v]subtitles='{ass.as_posix().replace(':', chr(92) + ':')}'[s0]"]; last = "[s0]"
    for k, (gid, en, dur) in enumerate(gfx):
        pg = wk / f"gfx_{gid}.png"; placa(gid, pg)
        ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-itsoffset", f"{en:.3f}", "-i", str(pg)]
        fc.append(f"[{2 + k}:v]format=rgba,fade=t=in:st={en:.3f}:d=0.15:alpha=1,fade=t=out:st={en + dur - 0.15:.3f}:d=0.15:alpha=1[g{k}]")
        fc.append(f"{last}[g{k}]overlay=0:0:eof_action=pass[x{k}]"); last = f"[x{k}]"
    fc.append(f"{last}format=yuv420p[v]")
    out = OUT / f"{slug}.mp4"
    run(ins + ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "1:a", "-c:v", "h264_nvenc", "-preset", "p6", "-cq", "20", "-b:v", "0", "-g", "60",
               "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    run([FF, "-v", "error", "-y", "-ss", "0.6", "-i", str(out), "-frames:v", "1", "-q:v", "2", str(OUT / f"{slug}_portada.jpg")])
    rep = {"short": slug, "salida": str(out), "duracion_s": round(total, 2), "planos": len(planos),
           "plano_mas_largo_s": round(max(p["fr"] for p in planos) / FPS, 2), "lufs_final": lufs(out),
           "tramos": [{k_: v for k_, v in tr.items() if k_ != "win"} for tr in tramos], "carteles": gfx}
    (wk / "informe.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k_: rep[k_] for k_ in ("short", "duracion_s", "planos", "plano_mas_largo_s", "lufs_final")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sel = sys.argv[2] if len(sys.argv) > 2 else "all"
    for s in CFG["shorts"]:
        if sel == "all" or str(s["n"]) == sel: build(s)
